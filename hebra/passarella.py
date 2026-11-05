"""Entrada de dades de la passarel·la de botiga (Raspberry Pi al costat del lector).

La passarel·la llegeix el lector (Impinj R700: REST/MQTT/LLRP, per decidir amb
el Xavier), filtra per prefix d'EPC, dedupa i agrega lectures en finestres de
5-10 s, i envia lots al núvol. Si cau la xarxa, guarda fins a 7 dies i reenvia.

Format del lot (JSON) que espera el núvol:

    {
      "lectures": [
        {"epc": "urn:epc:id:sgtin:...", "antena": "R700-1:1",
         "inici": "2026-11-16T12:00:00+01:00", "fi": "2026-11-16T12:00:10+01:00",
         "n": 12, "rssi_max": -48.0, "rssi_mitja": -51.5}
      ],
      "sensors": [
        {"cabina": "BCN-01-C1", "ts": "2026-11-16T12:00:00+01:00", "tipus": "porta_tancada"}
      ]
    }
"""

import sqlite3
from dataclasses import dataclass

from . import epc as epc_mod
from . import temps

TIPUS_SENSOR = {"porta_tancada", "porta_oberta", "presencia_si", "presencia_no"}


@dataclass
class Resultat:
    lectures: int = 0
    sensors: int = 0
    errors: list[str] | None = None


def desa_lot(con: sqlite3.Connection, lot: dict) -> Resultat:
    res = Resultat(errors=[])
    antenes = {f["id"]: f["zona_horaria"] for f in con.execute(
        "SELECT a.id, b.zona_horaria FROM antena a JOIN cabina c ON c.id = a.cabina_id JOIN botiga b ON b.id = c.botiga_id")}
    cabines = {f["id"]: f["zona_horaria"] for f in con.execute(
        "SELECT c.id, b.zona_horaria FROM cabina c JOIN botiga b ON b.id = c.botiga_id")}

    for i, l in enumerate(lot.get("lectures", [])):
        try:
            zona = antenes[l["antena"]]
            con.execute(
                """INSERT INTO lectura_agregada (epc, antena_id, inici, fi, n_lectures, rssi_max, rssi_mitja)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (epc_mod.normalitza(l["epc"]), l["antena"], temps.local(l["inici"], zona),
                 temps.local(l["fi"], zona), int(l["n"]), float(l["rssi_max"]), float(l["rssi_mitja"])))
            res.lectures += 1
        except (KeyError, ValueError, TypeError) as e:
            res.errors.append(f"lectura {i}: {e!r}")

    for i, s in enumerate(lot.get("sensors", [])):
        try:
            if s["tipus"] not in TIPUS_SENSOR:
                raise ValueError(f"tipus desconegut {s['tipus']!r}")
            con.execute("INSERT INTO sensor_event (cabina_id, ts, tipus) VALUES (?, ?, ?)",
                        (s["cabina"], temps.local(s["ts"], cabines[s["cabina"]]), s["tipus"]))
            res.sensors += 1
        except (KeyError, ValueError, TypeError) as e:
            res.errors.append(f"sensor {i}: {e!r}")
    con.commit()
    return res
