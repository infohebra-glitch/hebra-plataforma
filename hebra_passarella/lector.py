"""Client del lector Impinj R700 amb la "Impinj IoT Device Interface" (REST).

Què fa:
  1. Desa al lector un "preset" d'inventari amb les antenes i la potència.
  2. L'engega.
  3. Llegeix el flux d'esdeveniments (una línia JSON per esdeveniment) i
     retorna cada lectura d'etiqueta.

IMPORTANT (per verificar amb el lector real, amb el Xavier):
  * Els camins de l'API depenen de la versió del firmware. Per defecte fem servir
    els de la v1 i es poden canviar a la configuració (`[lector]` de passarella.toml).
    El lector publica la seva documentació Swagger: comproveu-hi els camins.
  * La interfície RFID del lector ha d'estar posada a "Impinj IoT Device Interface"
    (per defecte a partir del firmware 8.2).
  * L'esdeveniment documentat per Impinj és:
      {"TagInventoryEvent": {"epc": "<base64url>", "antennaPort": 1, "peakRssiCdbm": -5700},
       "timestamp": "2018-10-24T17:17:50.324240614Z"}
    Acceptem també les variants "tagInventoryEvent" i "epcHex".
"""

import base64
import binascii
import json
import logging
import ssl
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

log = logging.getLogger(__name__)


@dataclass
class Lectura:
    epc_hex: str
    port: int
    rssi_dbm: float
    ts: datetime


@dataclass
class ConfigLector:
    url: str                                  # p. ex. https://192.168.1.50
    usuari: str = "root"
    contrasenya: str = "impinj"
    verifica_tls: bool = False                # el lector porta un certificat autosignat
    preset_id: str = "hebra"
    cami_preset: str = "/api/v1/profiles/inventory/presets/{id}"
    cami_inici: str = "/api/v1/profiles/inventory/presets/{id}/start"
    cami_aturada: str = "/api/v1/profiles/stop"
    cami_flux: str = "/api/v1/data/stream"
    ports: tuple[int, ...] = (1, 2, 3)        # un port per cabina
    potencia_cdbm: int = 1500                 # 15 dBm: baixa, per no llegir la cabina del costat
    sessio: int = 2
    poblacio_estimada: int = 16


def preset(cfg: ConfigLector) -> dict:
    """Preset d'inventari segons l'esquema d'Impinj (camps obligatoris per antena)."""
    return {
        "id": cfg.preset_id,
        "antennaConfigs": [
            {
                "antennaPort": p,
                "transmitPowerCdbm": cfg.potencia_cdbm,
                "inventorySession": cfg.sessio,
                "inventorySearchMode": "dual-target",   # torna a llegir les etiquetes que es queden quietes
                "estimatedTagPopulation": cfg.poblacio_estimada,
                "rfMode": "auto-set-dense-reader",
            }
            for p in cfg.ports
        ],
    }


def interpreta(linia: str) -> Lectura | None:
    """Converteix una línia del flux en una Lectura (o None si no és una lectura d'etiqueta)."""
    linia = linia.strip()
    if not linia:
        return None
    try:
        ev = json.loads(linia)
    except json.JSONDecodeError:
        log.warning("Línia del flux no és JSON: %.80s", linia)
        return None
    tag = ev.get("TagInventoryEvent") or ev.get("tagInventoryEvent")
    if not tag:
        return None  # p. ex. EndOfCycleEvent
    if tag.get("epcHex"):
        epc_hex = tag["epcHex"]
    elif tag.get("epc"):
        b64 = tag["epc"]
        b64 += "=" * (-len(b64) % 4)
        epc_hex = binascii.b2a_hex(base64.urlsafe_b64decode(b64)).decode()
    else:
        return None
    ts_text = ev.get("timestamp")
    ts = _ts(ts_text) if ts_text else datetime.now(timezone.utc)
    return Lectura(epc_hex.upper(), int(tag.get("antennaPort", 0)),
                   float(tag.get("peakRssiCdbm", -9000)) / 100.0, ts)


def _ts(text: str) -> datetime:
    """Impinj dona nanosegons ("...50.324240614Z"); Python només n'accepta 6 decimals."""
    text = text.replace("Z", "+00:00")
    if "." in text:
        cap, resta = text.split(".", 1)
        decimals = resta[:len(resta) - len(resta.lstrip("0123456789"))]  # només els dígits del principi
        zona = resta[len(decimals):]
        text = f"{cap}.{decimals[:6].ljust(6, '0')}{zona}"
    return datetime.fromisoformat(text)


class ClientLector:
    def __init__(self, cfg: ConfigLector):
        self.cfg = cfg
        self._ctx = ssl.create_default_context()
        if not cfg.verifica_tls:
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE
        credencials = base64.b64encode(f"{cfg.usuari}:{cfg.contrasenya}".encode()).decode()
        self._capcaleres = {"Authorization": f"Basic {credencials}"}

    def _crida(self, metode: str, cami: str, cos: dict | None = None, timeout: float = 10):
        dades = json.dumps(cos).encode() if cos is not None else None
        capc = dict(self._capcaleres, **({"Content-Type": "application/json"} if dades else {}))
        req = urllib.request.Request(self.cfg.url.rstrip("/") + cami, data=dades, method=metode, headers=capc)
        return urllib.request.urlopen(req, context=self._ctx, timeout=timeout)

    def prepara_i_engega(self) -> None:
        cid = self.cfg.preset_id
        try:
            self._crida("POST", self.cfg.cami_aturada).close()
        except Exception as e:  # pot ser que no estigués llegint
            log.info("Aturada prèvia: %s", e)
        self._crida("PUT", self.cfg.cami_preset.format(id=cid), preset(self.cfg)).close()
        self._crida("POST", self.cfg.cami_inici.format(id=cid)).close()
        log.info("Lector engegat amb el preset %s (ports %s)", cid, self.cfg.ports)

    def lectures(self) -> Iterator[Lectura]:
        """Flux infinit de lectures. Si es talla la connexió, reconnecta i reengega."""
        espera = 2
        while True:
            try:
                self.prepara_i_engega()
                with self._crida("GET", self.cfg.cami_flux, timeout=300) as resposta:
                    espera = 2
                    for linia in resposta:
                        lectura = interpreta(linia.decode("utf-8", "replace"))
                        if lectura:
                            yield lectura
            except Exception as e:
                log.error("Connexió amb el lector perduda (%s). Reintent en %s s", e, espera)
                time.sleep(espera)
                espera = min(espera * 2, 60)
