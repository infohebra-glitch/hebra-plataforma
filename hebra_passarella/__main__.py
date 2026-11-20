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
    # Per defecte es fa servir el rellotge de la passarel·la (Raspberry, sincronitzat per NTP): el del
    # lector pot estar desajustat i les proves es calculen amb les hores.
    usa_lector = l.get("usa_rellotge_lector", False)
    avisat = [0.0]

    def buida() -> None:  # una finestra tancada no ha d'esperar que arribi una altra lectura
        while not atura.is_set():
            atura.wait(1)
            cua.afegeix("lectura", agregador.tanca(datetime.now(timezone.utc)))
    threading.Thread(target=buida, daemon=True, name="buidat").start()

    for lectura in ClientLector(config).lectures():
        if atura.is_set():
            break
        ara = datetime.now(timezone.utc)
        if abs((lectura.ts - ara).total_seconds()) > 30 and time.monotonic() - avisat[0] > 600:
            log.warning("El rellotge del lector va %.0f s desfasat respecte a la passarel·la",
                        (lectura.ts - ara).total_seconds())
            avisat[0] = time.monotonic()
        agregador.afegeix(lectura.epc_hex, lectura.port, lectura.rssi_dbm, lectura.ts if usa_lector else ara)
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
    def lector_amb_vigilancia() -> None:
        try:
            fil_lector(cfg, cua, atura)
            log.error("El lector ha tancat el flux de lectures")
        except Exception:
            log.exception("El fil del lector ha caigut")
        atura.set()  # sortir fa que systemd reiniciï la passarel·la en lloc de quedar-se sorda
        errors.append(1)

    errors: list[int] = []
    threading.Thread(target=lector_amb_vigilancia, daemon=True, name="lector").start()
    log.info("Passarel·la en marxa. Plataforma: %s", cfg["plataforma"]["url"])
    try:
        while not atura.is_set():
            atura.wait(1)
    except KeyboardInterrupt:
        pass
    log.info("Aturant (%s elements pendents a la cua, s'enviaran en tornar a arrencar)", cua.mida())
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
