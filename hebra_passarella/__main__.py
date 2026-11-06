"""Punt d'entrada de la passarel·la:  python -m hebra_passarella passarella.toml

Tres fils:
  * lector  -> agregador -> cua   (lectures UHF)
  * sensors -> cua                (porta i presència, per interrupcions GPIO)
  * cua     -> plataforma         (lots cada 5 s, reintents, 7 dies de memòria)
"""

import argparse
import logging
import signal
import threading
import time
import tomllib
from datetime import datetime, timezone

from .agregador import Agregador
from .cua import Cua, bucle_enviament
from .lector import ClientLector, ConfigLector
from .sensors import ConfigCabina

log = logging.getLogger("hebra_passarella")


def carrega(ruta: str) -> dict:
    with open(ruta, "rb") as f:
        return tomllib.load(f)


def fil_lector(cfg: dict, cua: Cua, atura: threading.Event) -> None:
    l = cfg["lector"]
    config = ConfigLector(
        url=l["url"], usuari=l.get("usuari", "root"), contrasenya=l.get("contrasenya", "impinj"),
        verifica_tls=l.get("verifica_tls", False), ports=tuple(l.get("ports", [1, 2, 3])),
        potencia_cdbm=l.get("potencia_cdbm", 1500),
        **{k: l[k] for k in ("cami_preset", "cami_inici", "cami_aturada", "cami_flux") if k in l})
    agregador = Agregador(l.get("nom", "R700-1"), cfg.get("finestra_s", 10),
                          tuple(p.upper() for p in l.get("prefixos_epc", [])))
    darrer_buidat = time.monotonic()
    for lectura in ClientLector(config).lectures():
        if atura.is_set():
            break
        agregador.afegeix(lectura.epc_hex, lectura.port, lectura.rssi_dbm, lectura.ts)
        if time.monotonic() - darrer_buidat >= 1:
            cua.afegeix("lectura", agregador.tanca(datetime.now(timezone.utc)))
            darrer_buidat = time.monotonic()
    cua.afegeix("lectura", agregador.tanca(datetime.now(timezone.utc), tot=True))


def main() -> None:
    ap = argparse.ArgumentParser(description="Passarel·la de botiga de Hebra")
    ap.add_argument("config", help="fitxer passarella.toml")
    ap.add_argument("--sense-sensors", action="store_true", help="no llegeixis els GPIO (proves amb només el lector)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = carrega(args.config)
    cua = Cua(cfg.get("cua", "cua-hebra.db"))
    atura = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: atura.set())

    if not args.sense_sensors and cfg.get("cabines"):
        from .sensors import engega
        engega([ConfigCabina(**c) for c in cfg["cabines"]], lambda ev: cua.afegeix("sensor", [ev]))

    threading.Thread(target=bucle_enviament, args=(cua, cfg["plataforma"]["url"], cfg["plataforma"]["clau"]),
                     kwargs={"atura": atura}, daemon=True, name="enviament").start()
    threading.Thread(target=fil_lector, args=(cfg, cua, atura), daemon=True, name="lector").start()
    log.info("Passarel·la en marxa. Plataforma: %s", cfg["plataforma"]["url"])
    try:
        while not atura.is_set():
            atura.wait(1)
    except KeyboardInterrupt:
        pass
    log.info("Aturant (%s elements pendents a la cua, s'enviaran en tornar a arrencar)", cua.mida())


if __name__ == "__main__":
    main()
