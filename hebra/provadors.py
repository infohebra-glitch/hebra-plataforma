"""Provadors en directe (especificació v0.3, B): estat de cada cabina ara mateix.

Estat d'una cabina, a partir dels darrers `sensor_event` i de les lectures recents:
  * `ocupada`: porta tancada i presència (hi ha una sessió en curs);
  * `porta_oberta`: hi ha presència però la porta és oberta (p. ex. demana una talla);
  * `lliure`: no hi ha presència;
  * `sense_dades`: cap sensor ni cap lectura en les darreres `HORES_SENSE_DADES` hores.
  Si la cabina no té sensors (nivell Bàsic), l'estat surt només de les lectures:
  `ocupada` si hi ha peces dins, si no `lliure`.
`des_de` és el moment del canvi a l'estat actual (l'esdeveniment de sensor que hi ha portat).

Peces dins: EPC llegits per les antenes de la cabina amb RSSI mitjà ≥ llindar de l'antena
en els darrers `FINESTRA_PECES_S` segons. Si una cabina veïna de la mateixa botiga també
la llegeix, és de la que la llegeix més fort. El `des_de` d'una peça és l'inici de la
seva presència contínua a la cabina (buits < `alertes.BUIT_MAXIM_S`).

`peticions_obertes`: peticions pendents o en camí de la botiga amb el camp `cabina`
igual a l'id de la cabina, al seu nom o al seu número («2» ↔ «Cabina 2»); el client
l'escriu a mà a la fitxa. `avui`: sessions ja processades del dia (el càlcul periòdic
de proves les crea; poden anar uns minuts endarrerides).

Flux SSE: `notifica_lot` publica l'esdeveniment `cabina` (el mateix objecte) quan entra
un lot de la passarel·la que afecta la cabina, com a molt un cop cada `THROTTLE_S`
segons per cabina (els lots arriben cada 5-10 s; si se'n salta un, el següent l'actualitza).
"""

import re
import sqlite3
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

from . import alertes, temps

FINESTRA_PECES_S = 60
HORES_SENSE_DADES = 2
THROTTLE_S = 5.0
_HISTORIA_SENSORS = 400  # darrers esdeveniments de sensor que es miren per saber des de quan dura l'estat

_darrera_publicacio: dict[str, float] = {}
_pany = threading.Lock()


def _dt(text: str) -> datetime:
    return datetime.fromisoformat(text)


def _estat_sensors(esdeveniments: list[sqlite3.Row]) -> tuple[str | None, str | None]:
    """(estat, des_de) a partir dels esdeveniments de sensor en ordre cronològic. (None, None) si no n'hi ha."""
    porta_tancada, presencia = False, False
    estat, des_de = None, None
    for e in esdeveniments:
        if e["tipus"] in ("porta_tancada", "porta_oberta"):
            porta_tancada = e["tipus"] == "porta_tancada"
        else:
            presencia = e["tipus"] == "presencia_si"
        nou = ("ocupada" if porta_tancada else "porta_oberta") if presencia else "lliure"
        if nou != estat:
            estat, des_de = nou, e["ts"]
    return estat, des_de


def _num(text: str | None) -> str | None:
    m = re.search(r"(\d+)\s*$", text or "")
    return str(int(m.group(1))) if m else None


def _es_de_la_cabina(valor: str | None, cabina: sqlite3.Row) -> bool:
    if not valor:
        return False
    v = valor.strip().lower()
    return v in (cabina["id"].lower(), cabina["nom"].lower()) or (_num(v) is not None and _num(v) == _num(cabina["nom"]))


def _nom(origen_json: str | None, model: str | None) -> str | None:
    return alertes._nom_model(origen_json, model) if model else None


def _peces(con: sqlite3.Connection, cabines: list[sqlite3.Row], ara: datetime) -> dict[str, list[dict]]:
    """{cabina_id: [peça]} amb les peces que hi són ara (cada EPC a la cabina que el llegeix més fort)."""
    des = (ara - timedelta(seconds=FINESTRA_PECES_S)).isoformat()
    ids = [c["id"] for c in cabines]
    if not ids:
        return {}
    marques = ",".join("?" * len(ids))
    files = con.execute(
        f"""SELECT a.cabina_id, l.epc, SUM(l.rssi_mitja * l.n_lectures) / SUM(l.n_lectures) AS rssi,
                   MIN(a.llindar_rssi) AS llindar
            FROM lectura_agregada l JOIN antena a ON a.id = l.antena_id
            WHERE a.cabina_id IN ({marques}) AND l.fi >= ? AND l.inici <= ?
            GROUP BY a.cabina_id, l.epc""", (*ids, des, ara.isoformat())).fetchall()
    millor: dict[str, tuple[float, str]] = {}
    for f in files:
        if f["rssi"] >= f["llindar"] and (f["epc"] not in millor or f["rssi"] > millor[f["epc"]][0]):
            millor[f["epc"]] = (f["rssi"], f["cabina_id"])
    out: dict[str, list[dict]] = defaultdict(list)
    limit_enrere = (ara - timedelta(hours=HORES_SENSE_DADES)).isoformat()
    for epc, (_, cabina_id) in sorted(millor.items()):
        k = con.execute("""SELECT k.model, k.talla, k.color, k.origen_json FROM etiqueta e
                           JOIN catalog_sku k ON k.gtin = e.gtin WHERE e.epc = ?""", (epc,)).fetchone()
        lectures = con.execute(
            """SELECT l.inici, l.fi FROM lectura_agregada l JOIN antena a ON a.id = l.antena_id
               WHERE a.cabina_id = ? AND l.epc = ? AND l.fi >= ? AND l.inici <= ? ORDER BY l.fi DESC""",
            (cabina_id, epc, limit_enrere, ara.isoformat())).fetchall()
        des_de = lectures[0]["inici"] if lectures else None
        for anterior in lectures[1:]:  # enrere mentre la presència és contínua
            if (_dt(des_de) - _dt(anterior["fi"])).total_seconds() >= alertes.BUIT_MAXIM_S:
                break
            des_de = min(des_de, anterior["inici"])
        out[cabina_id].append({"epc": epc, "model": k["model"] if k else None,
                               "nom": _nom(k["origen_json"], k["model"]) if k else None,
                               "talla": k["talla"] if k else None, "color": k["color"] if k else None,
                               "des_de": des_de})
    return out


def _avui(con: sqlite3.Connection, cabina_id: str, dia: str) -> dict:
    s = con.execute(
        """SELECT COUNT(*) AS n, AVG((julianday(fi) - julianday(inici)) * 86400) AS durada FROM sessio
           WHERE cabina_id = ? AND substr(inici, 1, 10) = ?""", (cabina_id, dia)).fetchone()
    proves = con.execute(
        """SELECT COUNT(*) FROM prova p JOIN sessio s ON s.id = p.sessio_id
           WHERE s.cabina_id = ? AND substr(s.inici, 1, 10) = ? AND p.confianca IN ('alta', 'mitjana')""",
        (cabina_id, dia)).fetchone()[0]
    return {"sessions": s["n"], "proves": proves,
            "durada_mitjana_s": round(s["durada"]) if s["durada"] is not None else None}


def directe(con: sqlite3.Connection, botiga_id: str | None, ara: str | None = None,
            cabines: set[str] | None = None) -> dict:
    """`GET /provadors/directe`: estat de les cabines (d'una botiga o de totes) i resum.

    `cabines` limita el càlcul a unes cabines (per al flux SSE); el resum és només d'aquestes.
    """
    ara = ara or temps.ara()
    ara_dt = _dt(ara)
    dia = ara[:10]
    llindar_dades = (ara_dt - timedelta(hours=HORES_SENSE_DADES)).isoformat()
    totes = con.execute("""SELECT id, nom, botiga_id FROM cabina WHERE (? IS NULL OR botiga_id = ?)
                           ORDER BY botiga_id, id""", (botiga_id, botiga_id)).fetchall()
    # Les peces es reparteixen entre totes les cabines de la botiga (veïnes), encara que només en calculem unes.
    peces = {}
    for b in sorted({c["botiga_id"] for c in totes}):
        peces |= _peces(con, [c for c in totes if c["botiga_id"] == b], ara_dt)
    obertes = con.execute(
        """SELECT botiga_id, cabina FROM peticio_talla WHERE estat IN ('pendent', 'en_cami')
           AND (? IS NULL OR botiga_id = ?) AND cabina IS NOT NULL""", (botiga_id, botiga_id)).fetchall()

    out = []
    for c in totes:
        if cabines is not None and c["id"] not in cabines:
            continue
        sensors = con.execute("""SELECT ts, tipus FROM sensor_event WHERE cabina_id = ? AND ts <= ?
                                 ORDER BY ts DESC, id DESC LIMIT ?""", (c["id"], ara, _HISTORIA_SENSORS)).fetchall()
        sensors = list(reversed(sensors))
        lectura = con.execute("""SELECT MAX(l.fi) FROM lectura_agregada l JOIN antena a ON a.id = l.antena_id
                                 WHERE a.cabina_id = ? AND l.inici <= ?""", (c["id"], ara)).fetchone()[0]
        dins = peces.get(c["id"], [])
        darrera = max([x for x in (sensors[-1]["ts"] if sensors else None, lectura) if x], default=None)
        if darrera is None or darrera < llindar_dades:
            estat, des_de = "sense_dades", darrera
        elif sensors:
            estat, des_de = _estat_sensors(sensors)
        else:  # sense sensors (nivell Bàsic): només les lectures
            estat = "ocupada" if dins else "lliure"
            des_de = min((p["des_de"] for p in dins if p["des_de"]), default=lectura)
        out.append({"cabina_id": c["id"], "nom": c["nom"], "botiga_id": c["botiga_id"], "estat": estat,
                    "des_de": des_de, "peces": dins,
                    "peticions_obertes": sum(1 for p in obertes
                                             if p["botiga_id"] == c["botiga_id"] and _es_de_la_cabina(p["cabina"], c)),
                    "avui": _avui(con, c["id"], dia)})
    return {"generat": ara, "cabines": out, "resum": {
        "ocupades": sum(1 for c in out if c["estat"] in ("ocupada", "porta_oberta")),
        "lliures": sum(1 for c in out if c["estat"] == "lliure"),
        "sessions_avui": sum(c["avui"]["sessions"] for c in out),
        "proves_avui": sum(c["avui"]["proves"] for c in out)}}


def notifica_lot(con: sqlite3.Connection, cabines: set[str], ara: str | None = None) -> int:
    """Publica l'esdeveniment SSE `cabina` de les cabines afectades per un lot (màx. un cop cada 5 s per cabina).

    Retorna quantes cabines s'han publicat.
    """
    rellotge = time.monotonic()
    with _pany:
        toca = {c for c in cabines if rellotge - _darrera_publicacio.get(c, -THROTTLE_S) >= THROTTLE_S}
        for c in toca:
            _darrera_publicacio[c] = rellotge
    if not toca:
        return 0
    for c in directe(con, None, ara, cabines=toca)["cabines"]:
        alertes.bus.publica("cabina", c, c["botiga_id"])
    return len(toca)
