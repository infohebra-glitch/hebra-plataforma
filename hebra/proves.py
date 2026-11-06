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

Nivell Bàsic (botiga.nivell = 'basic', sense sensors de porta ni de presència):
  no hi ha sessions de cabina reals. Cada EPC llegit per l'antena de la zona
  forma "estades" (lectures seguides amb buits < `BUIT_ZONA_S`); les estades
  que se solapen s'agrupen en una "entrada a zona", que es desa a `sessio`.
  Una estada amb `durada_minima_s` i `lectures_minimes` és una prova. Els
  informes ho han de dir: són **entrades a zona**, no sessions de cabina
  (vegeu `etiqueta_sessions`).

El motor és determinista i idempotent per sessió: es pot tornar a executar
sobre les mateixes dades i dona el mateix resultat. Només es recalcula des del
primer esdeveniment que encara es conserva (vegeu hebra/retencio.py): les
sessions i proves més antigues es mantenen.

Després de cada cabina es busquen les peces abandonades (hebra/alertes.py).
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import alertes, cataleg, control
from .config import ReglaProva


BUIT_ZONA_S = 60  # nivell Bàsic: buit màxim entre lectures d'una mateixa estada a la zona


def _dt(text: str) -> datetime:
    return datetime.fromisoformat(text)


def etiqueta_sessions(nivell: str) -> str:
    """Com s'han d'anomenar les sessions als informes segons el nivell de la botiga."""
    return "entrades a zona" if nivell == "basic" else "sessions de cabina"


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


def _esborra_des_de(con: sqlite3.Connection, cabina_id: str, des: str | None) -> None:
    """Esborra sessions, proves i atribucions de la cabina que comencen a partir de `des` (None = totes)."""
    filtre = "cabina_id = ?" + (" AND inici >= ?" if des else "")
    params = (cabina_id, des) if des else (cabina_id,)
    con.execute(f"""DELETE FROM atribucio WHERE prova_id IN (SELECT p.id FROM prova p
                    WHERE p.sessio_id IN (SELECT id FROM sessio WHERE {filtre}))""", params)
    con.execute(f"DELETE FROM prova WHERE sessio_id IN (SELECT id FROM sessio WHERE {filtre})", params)
    con.execute(f"DELETE FROM sessio WHERE {filtre}", params)


def _desa_prova(con, sessio_id: int, cand: Candidata, conf: str) -> None:
    con.execute(
        """INSERT INTO prova (sessio_id, epc, gtin, durada_s, n_lectures, rssi_mitja, confianca)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (sessio_id, cand.epc, cataleg.gtin_de_epc(con, cand.epc), cand.durada_s,
         cand.n_lectures, round(cand.rssi_mitja, 1), conf))


def processa_cabina(con: sqlite3.Connection, cabina_id: str, regla: ReglaProva) -> int:
    """Recalcula sessions i proves d'una cabina a partir de tots els seus esdeveniments.

    Retorna el nombre de proves creades. Esborra abans les sessions i proves
    anteriors de la cabina (i les atribucions que en depenen) perquè el càlcul
    sigui idempotent. Si la botiga és de nivell Bàsic, fa servir només les lectures.
    """
    cabina = con.execute(
        "SELECT c.*, b.nivell FROM cabina c JOIN botiga b ON b.id = c.botiga_id WHERE c.id = ?",
        (cabina_id,)).fetchone()
    if cabina["nivell"] == "basic":
        creades = _processa_zona_basic(con, cabina, regla)
        con.commit()
        return creades

    veines = [v for v in cabina["veines"].split(",") if v]
    esdeveniments = [(_dt(f["ts"]), f["tipus"]) for f in con.execute(
        "SELECT ts, tipus FROM sensor_event WHERE cabina_id = ? ORDER BY ts, id", (cabina_id,))]
    # Només recalculem el període del qual encara tenim esdeveniments (la retenció esborra els antics).
    _esborra_des_de(con, cabina_id, esdeveniments[0][0].isoformat() if esdeveniments else None)

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
            _desa_prova(con, sessio_id, cand, conf)
            creades += 1
    con.commit()
    alertes.detecta_abandonades(con, cabina_id)
    return creades


# ---------------------------------------------------------------- Nivell Bàsic


@dataclass
class Estada:
    """Presència contínua d'un EPC a la zona (lectures amb buits < BUIT_ZONA_S)."""
    epc: str
    inici: datetime
    fi: datetime
    n_lectures: int
    suma_rssi: float

    @property
    def rssi_mitja(self) -> float:
        return self.suma_rssi / self.n_lectures


def estades_zona(lectures: list[tuple[str, datetime, datetime, int, float, float]],
                 buit_s: float = BUIT_ZONA_S) -> list[Estada]:
    """Agrupa lectures (epc, inici, fi, n, rssi_mitja, llindar) en estades per EPC.

    Les lectures per sota del llindar de l'antena no compten (peça de fora la zona).
    """
    obertes: dict[str, Estada] = {}
    estades: list[Estada] = []
    for epc, inici, fi, n, rssi, llindar in sorted(lectures, key=lambda x: (x[1], x[0])):
        if rssi < llindar:
            continue
        e = obertes.get(epc)
        if e and (inici - e.fi).total_seconds() < buit_s:
            e.fi = max(e.fi, fi)
            e.n_lectures += n
            e.suma_rssi += rssi * n
        else:
            e = obertes[epc] = Estada(epc, inici, fi, n, rssi * n)
            estades.append(e)
    return estades


def entrades_zona(estades: list[Estada]) -> list[tuple[datetime, datetime, list[Estada]]]:
    """Estades que se solapen en el temps = una mateixa entrada a zona (una persona amb diverses peces)."""
    grups: list[tuple[datetime, datetime, list[Estada]]] = []
    for e in sorted(estades, key=lambda x: x.inici):
        if grups and e.inici <= grups[-1][1]:
            inici, fi, llista = grups[-1]
            grups[-1] = (inici, max(fi, e.fi), llista + [e])
        else:
            grups.append((e.inici, e.fi, [e]))
    return grups


def _processa_zona_basic(con: sqlite3.Connection, cabina: sqlite3.Row, regla: ReglaProva) -> int:
    files = con.execute(
        """SELECT l.epc, l.inici, l.fi, l.n_lectures, l.rssi_mitja, a.llindar_rssi
           FROM lectura_agregada l JOIN antena a ON a.id = l.antena_id
           WHERE a.cabina_id = ? ORDER BY l.inici, l.id""", (cabina["id"],)).fetchall()
    lectures = [(f["epc"], _dt(f["inici"]), _dt(f["fi"]), f["n_lectures"], f["rssi_mitja"], f["llindar_rssi"])
                for f in files]
    _esborra_des_de(con, cabina["id"], lectures[0][1].isoformat() if lectures else None)
    veines = [v for v in cabina["veines"].split(",") if v]

    creades = 0
    for inici, fi, estades in entrades_zona(estades_zona(lectures)):
        grup = control.grup_del_dia(con, cabina["botiga_id"], "origen", inici.date().isoformat())
        sessio_id = con.execute("INSERT INTO sessio (cabina_id, inici, fi, grup) VALUES (?, ?, ?, ?)",
                                (cabina["id"], inici.isoformat(), fi.isoformat(), grup)).lastrowid
        for e in estades:
            cand = Candidata(e.epc, (e.fi - e.inici).total_seconds(), e.n_lectures, e.rssi_mitja)
            if cand.durada_s < regla.durada_minima_s or cand.n_lectures < regla.lectures_minimes:
                continue
            rssi_veina = max((vl[e.epc].rssi_mitja for vl in
                              (_lectures_epc(con, v, e.inici.isoformat(), e.fi.isoformat()) for v in veines)
                              if e.epc in vl), default=None)
            conf = confianca(cand.rssi_mitja, rssi_veina, regla)
            if conf is None:
                continue
            _desa_prova(con, sessio_id, cand, conf)
            creades += 1
    return creades


def processa_botiga(con: sqlite3.Connection, botiga_id: str, regla: ReglaProva) -> int:
    cabines = con.execute("SELECT id FROM cabina WHERE botiga_id = ?", (botiga_id,)).fetchall()
    return sum(processa_cabina(con, c["id"], regla) for c in cabines)
