"""Motor de proves: de lectures UHF i sensors de cabina a "proves".

Regla (Proposta MVP, secció 3.3; valors a hebra/config.py):

  Sessió de cabina: comença quan la porta es tanca i hi ha presència; acaba
  quan la porta és oberta i no hi ha ningú durant `tancament_sessio_s` segons.

  Prova: un EPC llegit per l'antena d'aquella cabina durant la sessió, amb RSSI
  mitjà per sobre del llindar de la cabina, durant `durada_minima_s` o més, amb
  `lectures_minimes` o més, i no assignat a una cabina veïna.

  Confiança: si l'EPC també es llegeix a una cabina veïna en el mateix moment,
  es compara l'RSSI mitjà. Marge >= marge_alta -> alta; >= marge_mitjana ->
  mitjana; per sota -> ambigua. Si la veïna guanya, la prova és de la veïna.
  Els informes només compten alta i mitjana.

El motor és determinista i idempotent per sessió: es pot tornar a executar
sobre les mateixes dades i dona el mateix resultat.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import cataleg, control
from .config import ReglaProva


def _dt(text: str) -> datetime:
    return datetime.fromisoformat(text)


# ---------------------------------------------------------------- Sessions


@dataclass
class Sessio:
    cabina_id: str
    inici: datetime
    fi: datetime


def detecta_sessions(esdeveniments: list[tuple[datetime, str]], cabina_id: str,
                     regla: ReglaProva) -> list[Sessio]:
    """Màquina d'estats sobre els esdeveniments de porta i presència d'una cabina.

    `esdeveniments` és una llista (ts, tipus) ordenada per ts.
    Una sessió que no es tanca (p. ex. tall de dades) no es compta.
    """
    porta_tancada = False
    presencia = False
    inici: datetime | None = None
    buida_des_de: datetime | None = None  # porta oberta i sense presència des de...
    sessions: list[Sessio] = []

    def potser_tanca(ara: datetime) -> None:
        nonlocal inici, buida_des_de
        if inici and buida_des_de and ara - buida_des_de >= timedelta(seconds=regla.tancament_sessio_s):
            sessions.append(Sessio(cabina_id, inici, buida_des_de))
            inici = None
            buida_des_de = None

    for ts, tipus in esdeveniments:
        potser_tanca(ts)
        if tipus == "porta_tancada":
            porta_tancada = True
        elif tipus == "porta_oberta":
            porta_tancada = False
        elif tipus == "presencia_si":
            presencia = True
        elif tipus == "presencia_no":
            presencia = False

        if inici is None and porta_tancada and presencia:
            inici = ts
        if inici is not None:
            if not porta_tancada and not presencia:
                buida_des_de = buida_des_de or ts
            else:
                buida_des_de = None
    # Últim esdeveniment: si ja feia prou estona que estava buida, la tanquem.
    if inici and buida_des_de:
        potser_tanca(buida_des_de + timedelta(seconds=regla.tancament_sessio_s))
    return sessions


# ---------------------------------------------------------------- Proves


@dataclass
class Candidata:
    epc: str
    durada_s: float
    n_lectures: int
    rssi_mitja: float


def _lectures_epc(con: sqlite3.Connection, cabina_id: str, inici: str, fi: str) -> dict[str, Candidata]:
    """Agrega, per EPC, les lectures de les antenes d'una cabina dins d'un interval."""
    files = con.execute(
        """SELECT l.epc, MIN(l.inici) AS primer, MAX(l.fi) AS darrer,
                  SUM(l.n_lectures) AS n,
                  SUM(l.rssi_mitja * l.n_lectures) / SUM(l.n_lectures) AS rssi,
                  MIN(a.llindar_rssi) AS llindar
           FROM lectura_agregada l JOIN antena a ON a.id = l.antena_id
           WHERE a.cabina_id = ? AND l.fi >= ? AND l.inici <= ?
           GROUP BY l.epc""",
        (cabina_id, inici, fi),
    ).fetchall()
    resultat = {}
    for f in files:
        if f["rssi"] < f["llindar"]:
            continue  # massa feble: probablement una peça de fora la cabina
        durada = (_dt(f["darrer"]) - _dt(f["primer"])).total_seconds()
        resultat[f["epc"]] = Candidata(f["epc"], durada, f["n"], f["rssi"])
    return resultat


def confianca(rssi_propi: float, rssi_veina: float | None, regla: ReglaProva) -> str | None:
    """Retorna 'alta' | 'mitjana' | 'ambigua', o None si la peça és de la veïna."""
    if rssi_veina is None:
        return "alta"
    marge = rssi_propi - rssi_veina
    if marge >= regla.marge_alta_db:
        return "alta"
    if marge >= regla.marge_mitjana_db:
        return "mitjana"
    if marge > -regla.marge_mitjana_db:
        return "ambigua"
    return None  # la veïna la llegeix clarament més fort


def processa_cabina(con: sqlite3.Connection, cabina_id: str, regla: ReglaProva) -> int:
    """Recalcula sessions i proves d'una cabina a partir de tots els seus esdeveniments.

    Retorna el nombre de proves creades. Esborra abans les sessions i proves
    anteriors de la cabina (i les atribucions que en depenen) perquè el càlcul
    sigui idempotent.
    """
    cabina = con.execute("SELECT * FROM cabina WHERE id = ?", (cabina_id,)).fetchone()
    veines = [v for v in cabina["veines"].split(",") if v]

    con.execute(
        "DELETE FROM atribucio WHERE prova_id IN (SELECT p.id FROM prova p JOIN sessio s ON s.id = p.sessio_id WHERE s.cabina_id = ?)",
        (cabina_id,))
    con.execute("DELETE FROM prova WHERE sessio_id IN (SELECT id FROM sessio WHERE cabina_id = ?)", (cabina_id,))
    con.execute("DELETE FROM sessio WHERE cabina_id = ?", (cabina_id,))

    esdeveniments = [(_dt(f["ts"]), f["tipus"]) for f in con.execute(
        "SELECT ts, tipus FROM sensor_event WHERE cabina_id = ? ORDER BY ts, id", (cabina_id,))]

    creades = 0
    for s in detecta_sessions(esdeveniments, cabina_id, regla):
        inici, fi = s.inici.isoformat(), s.fi.isoformat()
        grup = control.grup_del_dia(con, cabina["botiga_id"], "origen", s.inici.date().isoformat())
        sessio_id = con.execute(
            "INSERT INTO sessio (cabina_id, inici, fi, grup) VALUES (?, ?, ?, ?)",
            (cabina_id, inici, fi, grup)).lastrowid

        veines_lectures = [_lectures_epc(con, v, inici, fi) for v in veines]
        for cand in _lectures_epc(con, cabina_id, inici, fi).values():
            if cand.durada_s < regla.durada_minima_s or cand.n_lectures < regla.lectures_minimes:
                continue  # "pas": la peça hi ha estat massa poca estona
            rssi_veina = max((vl[cand.epc].rssi_mitja for vl in veines_lectures if cand.epc in vl), default=None)
            conf = confianca(cand.rssi_mitja, rssi_veina, regla)
            if conf is None:
                continue
            con.execute(
                """INSERT INTO prova (sessio_id, epc, gtin, durada_s, n_lectures, rssi_mitja, confianca)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sessio_id, cand.epc, cataleg.gtin_de_epc(con, cand.epc), cand.durada_s,
                 cand.n_lectures, round(cand.rssi_mitja, 1), conf))
            creades += 1
    con.commit()
    return creades


def processa_botiga(con: sqlite3.Connection, botiga_id: str, regla: ReglaProva) -> int:
    cabines = con.execute("SELECT id FROM cabina WHERE botiga_id = ?", (botiga_id,)).fetchall()
    return sum(processa_cabina(con, c["id"], regla) for c in cabines)
