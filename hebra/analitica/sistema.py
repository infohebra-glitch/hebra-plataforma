"""Estat del sistema (manual del client, pantalla «Estat del sistema»).

Per a l'encarregada i per a Hebra: si cada cabina envia dades, quan va arribar
l'última venda i quantes peces llegides no són a la taula d'etiquetes.
Una cabina en alerta fa més de `HORES_ALERTA` hores que no envia res: més que una
nit de tancament, o sigui que alguna cosa falla (xarxa, lector o passarel·la).
Després d'un diumenge o d'un festiu també sortirà en alerta fins a la primera prova.
"""

import sqlite3
from datetime import datetime

from . import Filtre

HORES_ALERTA = 24


def _mes_recent(*valors: str | None) -> str | None:
    vs = [v for v in valors if v]
    return max(vs) if vs else None


def estat_sistema(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /estat-sistema`: darrera dada de cada cabina, darrera venda i % de peces desconegudes."""
    b = f.botiga_id
    ara = datetime.now().astimezone()
    cabines = []
    for c in con.execute("""SELECT c.id, c.nom, c.botiga_id FROM cabina c
                            WHERE (? IS NULL OR c.botiga_id = ?) ORDER BY c.botiga_id, c.id""", (b, b)):
        lectura = con.execute("""SELECT MAX(l.fi) FROM lectura_agregada l JOIN antena a ON a.id = l.antena_id
                                 WHERE a.cabina_id = ?""", (c["id"],)).fetchone()[0]
        sensor = con.execute("SELECT MAX(ts) FROM sensor_event WHERE cabina_id = ?", (c["id"],)).fetchone()[0]
        darrera = _mes_recent(lectura, sensor)
        hores = None
        if darrera:
            hores = round((ara - datetime.fromisoformat(darrera)).total_seconds() / 3600, 1)
        cabines.append({"cabina_id": c["id"], "nom": c["nom"], "botiga_id": c["botiga_id"],
                        "darrera_lectura": lectura, "darrer_sensor": sensor,
                        "hores_sense_dades": hores,
                        "alerta": darrera is None or (hores is not None and hores > HORES_ALERTA)})

    venda = con.execute("SELECT MAX(COALESCE(ts, data)) FROM venda_linia WHERE (? IS NULL OR botiga_id = ?)",
                        (b, b)).fetchone()[0]

    fi = f.fi_exclusiu_iso
    epcs = con.execute(
        """SELECT COUNT(DISTINCT l.epc) AS n, COUNT(DISTINCT CASE WHEN e.epc IS NULL THEN l.epc END) AS desconeguts
           FROM lectura_agregada l JOIN antena a ON a.id = l.antena_id JOIN cabina c ON c.id = a.cabina_id
           LEFT JOIN etiqueta e ON e.epc = l.epc
           WHERE (? IS NULL OR c.botiga_id = ?) AND l.inici >= ? AND l.inici < ?""",
        (b, b, f.inici_iso, fi)).fetchone()
    return {
        "cabines": cabines,
        "darrera_venda": venda,
        "dies_sense_vendes": ((ara.date() - datetime.fromisoformat(venda[:10]).date()).days if venda else None),
        "peces_llegides": epcs["n"],
        "peces_desconegudes": epcs["desconeguts"],
        "pct_desconegudes": (epcs["desconeguts"] / epcs["n"]) if epcs["n"] else None,
        "hores_alerta": HORES_ALERTA,
        "generat": ara.isoformat(timespec="seconds"),
        "periode": {"des": f.inici_iso, "fins": f.fins.isoformat()},
    }


__all__ = ["estat_sistema"]
