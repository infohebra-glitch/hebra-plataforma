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

Camps opcionals (passarel·la v0.4):
  * `"ref"` a cada lectura i sensor: una referència única. Si la passarel·la torna a enviar un
    element (no li ha arribat la resposta), no es desa dues vegades;
  * `"passarella": {"id", "pendents", "versio", "ara"}`: senyal de vida. Un lot buit amb aquest
    camp és un batec: així es veu que la passarel·la és viva encara que no entri ningú.
Els elements rebutjats (antena o cabina desconeguda, dades mal formades) es compten a
`passarella_estat` i surten a l'estat del sistema: una antena mal anomenada no passa desapercebuda.

Després de desar el lot es publica l'estat en directe de les cabines afectades
(esdeveniment SSE `cabina`, hebra/provadors.py). És un avís de millor esforç: si falla,
es registra i la resposta a la passarel·la continua sent bona (el lot ja és desat).
"""

import logging
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from . import epc as epc_mod
from . import provadors, temps

log = logging.getLogger("hebra.passarella")

TIPUS_SENSOR = {"porta_tancada", "porta_oberta", "presencia_si", "presencia_no"}
MAXIM_ELEMENTS = 5000  # per lot; la passarel·la n'envia 2000 com a molt


class LotMassaGran(ValueError):
    pass


@dataclass
class Resultat:
    lectures: int = 0
    sensors: int = 0
    errors: list[str] | None = None
    repetits: int = 0


def _text(valor, nom: str, maxim: int = 100) -> str:
    if not isinstance(valor, str) or not valor or len(valor) > maxim:
        raise ValueError(f"«{nom}» no vàlid")
    return valor


def _ref(valor) -> str | None:
    return None if valor is None else _text(str(valor), "ref", 80)


def _rssi(valor, nom: str) -> float:
    x = float(valor)
    if not math.isfinite(x) or not -150 <= x <= 30:
        raise ValueError(f"«{nom}» fora de rang: {valor!r}")
    return x


def desa_lot(con: sqlite3.Connection, lot: dict, maxim: int | None = None) -> Resultat:
    res = Resultat(errors=[])
    if not isinstance(lot, dict):
        raise ValueError("El lot ha de ser un objecte JSON")
    lectures, sensors = lot.get("lectures") or [], lot.get("sensors") or []
    if not isinstance(lectures, list) or not isinstance(sensors, list):
        raise ValueError("«lectures» i «sensors» han de ser llistes")
    if maxim is not None and len(lectures) + len(sensors) > maxim:
        raise LotMassaGran(f"Massa elements en un lot (màxim {maxim})")
    antenes, cabina_antena = {}, {}
    for f in con.execute("""SELECT a.id, a.cabina_id, b.zona_horaria FROM antena a JOIN cabina c ON c.id = a.cabina_id
                            JOIN botiga b ON b.id = c.botiga_id"""):
        antenes[f["id"]], cabina_antena[f["id"]] = f["zona_horaria"], f["cabina_id"]
    afectades: set[str] = set()
    cabines = {f["id"]: f["zona_horaria"] for f in con.execute(
        "SELECT c.id, b.zona_horaria FROM cabina c JOIN botiga b ON b.id = c.botiga_id")}

    try:
        for i, l in enumerate(lectures):
            try:
                if l["antena"] not in antenes:
                    raise ValueError(f"antena desconeguda {l['antena']!r}")
                zona = antenes[l["antena"]]
                inici, fi, n = temps.local(l["inici"], zona), temps.local(l["fi"], zona), int(l["n"])
                if n < 1:
                    raise ValueError("«n» ha de ser 1 o més")
                if datetime.fromisoformat(fi) < datetime.fromisoformat(inici):
                    raise ValueError("«fi» és anterior a «inici»")
                cur = con.execute(
                    """INSERT INTO lectura_agregada (epc, antena_id, inici, fi, n_lectures, rssi_max, rssi_mitja, ref)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(ref) DO NOTHING""",
                    (epc_mod.normalitza(_text(l["epc"], "epc")), l["antena"], inici, fi, n,
                     _rssi(l["rssi_max"], "rssi_max"), _rssi(l["rssi_mitja"], "rssi_mitja"), _ref(l.get("ref"))))
                if cur.rowcount:
                    res.lectures += 1
                    afectades.add(cabina_antena[l["antena"]])
                else:
                    res.repetits += 1
            except (KeyError, ValueError, TypeError, AttributeError) as e:
                res.errors.append(f"lectura {i}: {e}")

        for i, s in enumerate(sensors):
            try:
                if s["tipus"] not in TIPUS_SENSOR:
                    raise ValueError(f"tipus desconegut {s['tipus']!r}")
                if s["cabina"] not in cabines:
                    raise ValueError(f"cabina desconeguda {s['cabina']!r}")
                cur = con.execute(
                    "INSERT INTO sensor_event (cabina_id, ts, tipus, ref) VALUES (?, ?, ?, ?) ON CONFLICT(ref) DO NOTHING",
                    (s["cabina"], temps.local(s["ts"], cabines[s["cabina"]]), s["tipus"], _ref(s.get("ref"))))
                if cur.rowcount:
                    res.sensors += 1
                    afectades.add(s["cabina"])
                else:
                    res.repetits += 1
            except (KeyError, ValueError, TypeError, AttributeError) as e:
                res.errors.append(f"sensor {i}: {e}")
        _senyal_de_vida(con, lot.get("passarella"), res.errors)
        con.commit()
    except Exception:
        con.rollback()  # o tot el lot o res: la passarel·la el tornarà a enviar
        raise
    if res.errors:
        log.warning("Lot amb %s elements rebutjats: %s", len(res.errors), res.errors[:3])
    if afectades:
        # El lot ja és desat: si l'avís en directe falla, la passarel·la no ha de rebre un error
        # (el tornaria a enviar).
        try:
            provadors.notifica_lot(con, afectades)
        except Exception:
            log.exception("No s'ha pogut publicar l'estat en directe de les cabines %s", sorted(afectades))
    return res


def _senyal_de_vida(con: sqlite3.Connection, info, errors: list[str]) -> None:
    """Anota quan s'ha vist la passarel·la i quants elements se li han rebutjat."""
    if not isinstance(info, dict):
        if not errors:
            return
        info = {}
    pid = str(info.get("id") or "")[:60]
    pendents = info.get("pendents")
    pendents = pendents if isinstance(pendents, int) and not isinstance(pendents, bool) and pendents >= 0 else None
    ara = temps.ara()
    desfasament = None
    try:
        if info.get("ara"):
            desfasament = round((datetime.fromisoformat(str(info["ara"]).replace("Z", "+00:00"))
                                 - datetime.fromisoformat(ara)).total_seconds())
    except (ValueError, TypeError):
        pass
    con.execute(
        """INSERT INTO passarella_estat (id, vista, pendents, versio, desfasament_s) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET vista = excluded.vista, pendents = excluded.pendents,
             versio = excluded.versio, desfasament_s = excluded.desfasament_s""",
        (pid, ara, pendents, str(info.get("versio") or "")[:20] or None, desfasament))
    if errors:
        con.execute("""UPDATE passarella_estat SET rebutjats = rebutjats + ?, darrer_error = ?, darrer_error_ts = ?
                       WHERE id = ?""", (len(errors), errors[0][:300], ara, pid))


def estat(con: sqlite3.Connection) -> list[dict]:
    """Passarel·les vistes (per a l'estat del sistema)."""
    ara = datetime.fromisoformat(temps.ara())
    out = []
    for f in con.execute("SELECT * FROM passarella_estat ORDER BY id"):
        minuts = round((ara - datetime.fromisoformat(f["vista"])).total_seconds() / 60, 1)
        out.append({"id": f["id"], "vista": f["vista"], "minuts_sense_senyal": minuts, "pendents": f["pendents"],
                    "versio": f["versio"], "desfasament_s": f["desfasament_s"], "rebutjats": f["rebutjats"],
                    "darrer_error": f["darrer_error"], "darrer_error_ts": f["darrer_error_ts"],
                    "alerta": minuts > MINUTS_ALERTA or abs(f["desfasament_s"] or 0) > DESFASAMENT_ALERTA_S})
    return out


MINUTS_ALERTA = 10            # la passarel·la envia un batec cada minut
DESFASAMENT_ALERTA_S = 30     # rellotge de la Raspberry mal posat: les proves no quadrarien amb les vendes
