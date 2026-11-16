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
sobre les mateixes dades i dona el mateix resultat. Cada execució només refà el
tros que les dades noves poden canviar (vegeu «Recàlcul incremental»), i mai
abans del primer esdeveniment que encara es conserva (hebra/retencio.py): les
sessions i proves més antigues es mantenen.

Després de cada cabina es busquen les peces abandonades (hebra/alertes.py).
"""

import hashlib
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
           FROM antena a JOIN lectura_agregada l INDEXED BY ix_lectura_antena_temps ON l.antena_id = a.id
           WHERE a.cabina_id = ? AND l.inici >= ? AND l.fi >= ? AND l.inici <= ?
           GROUP BY l.epc""",
        (cabina_id, (_dt(inici) - MARGE_LECTURES).isoformat(), inici, fi),
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


def _esborra_des_de(con: sqlite3.Connection, cabina_id: str, des: str | None, estricte: bool = False) -> None:
    """Esborra sessions, proves i atribucions de la cabina que comencen a partir de `des` (None = totes).
    Amb `estricte`, només les que comencen després de `des`."""
    filtre = "cabina_id = ?" + ((" AND inici > ?" if estricte else " AND inici >= ?") if des else "")
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


# ---------------------------------------------------------------- Recàlcul incremental
#
# Recalcular tota la història de la cabina cada 5 minuts no aguanta un pilot de 8 setmanes
# (minuts de càlcul amb la base de dades bloquejada). Per això es desa fins on s'ha calculat
# (taula `estat_calcul`) i només es refà el tros que les dades noves poden canviar:
#
#   * dades noves = files de `lectura_agregada` (de qualsevol cabina de la botiga, per les
#     veïnes) i de `sensor_event` (de la cabina) amb id més gran que l'últim vist;
#   * es reprèn des del final de l'última sessió que va acabar com a mínim `MARGE_REPRESA`
#     abans de la dada nova més antiga. Just després d'una sessió tancada la màquina d'estats
#     és a zero (porta oberta, ningú dins), i per tant el resultat és el mateix que recalculant-ho tot;
#   * si canvia la regla, els llindars de les antenes o les veïnes (la `signatura`), o amb
#     `tot=True`, es recalcula tot el període del qual encara hi ha dades crues.

MARGE_REPRESA = timedelta(hours=3)  # cobreix lectures que arriben tard i el canvi d'hora
MARGE_LECTURES = timedelta(hours=2)  # una lectura agregada dura segons; marge ample per a l'índex


def _signatura(con: sqlite3.Connection, cabina: sqlite3.Row, regla: ReglaProva) -> str:
    veines = sorted(v for v in cabina["veines"].split(",") if v)
    antenes = con.execute(
        f"""SELECT id, cabina_id, llindar_rssi FROM antena WHERE cabina_id IN ({",".join("?" * (len(veines) + 1))})
            ORDER BY id""", (cabina["id"], *veines)).fetchall()
    text = repr((regla.durada_minima_s, regla.lectures_minimes, regla.marge_alta_db, regla.marge_mitjana_db,
                 regla.tancament_sessio_s, BUIT_ZONA_S, cabina["nivell"], veines, [tuple(a) for a in antenes]))
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _punt_de_represa(con: sqlite3.Connection, cabina: sqlite3.Row, estat: sqlite3.Row | None, signatura: str,
                     tot: bool) -> tuple[bool, str | None]:
    """(cal recalcular?, des d'on). `des` None = tot el període amb dades crues."""
    if tot or estat is None or estat["signatura"] != signatura:
        return True, None
    lectura = con.execute(
        """SELECT MIN(l.inici) FROM lectura_agregada l JOIN antena a ON a.id = l.antena_id
           JOIN cabina c ON c.id = a.cabina_id WHERE l.id > ? AND c.botiga_id = ?""",
        (estat["darrera_lectura_id"], cabina["botiga_id"])).fetchone()[0]
    sensor = con.execute("SELECT MIN(ts) FROM sensor_event WHERE id > ? AND cabina_id = ?",
                         (estat["darrer_sensor_id"], cabina["id"])).fetchone()[0]
    noves = [_dt(x) for x in (lectura, sensor) if x]
    if not noves:
        return False, None
    try:
        tall = (min(noves) - MARGE_REPRESA).isoformat()
    except TypeError:  # hores amb zona i sense barrejades: no ens en refiem
        return True, None
    fila = con.execute("SELECT MAX(fi) FROM sessio WHERE cabina_id = ? AND fi < ?", (cabina["id"], tall)).fetchone()
    return True, fila[0]


def _proves_del_periode(con: sqlite3.Connection, cabina_id: str, primer: str | None) -> int:
    """Proves de la cabina des de la primera dada crua que encara es conserva."""
    return con.execute(
        """SELECT COUNT(*) FROM prova p JOIN sessio s ON s.id = p.sessio_id
           WHERE s.cabina_id = ? AND (? IS NULL OR s.inici >= ?)""", (cabina_id, primer, primer)).fetchone()[0]


def processa_cabina(con: sqlite3.Connection, cabina_id: str, regla: ReglaProva, tot: bool = False) -> int:
    """Posa al dia les sessions i proves d'una cabina.

    Només recalcula el tros que les dades noves poden canviar (vegeu «Recàlcul incremental»);
    amb `tot=True`, tot el període del qual encara hi ha dades crues. És idempotent.
    Retorna el nombre de proves de la cabina en aquest període (no només les noves).
    Si la botiga és de nivell Bàsic, fa servir només les lectures.
    """
    cabina = con.execute(
        "SELECT c.*, b.nivell FROM cabina c JOIN botiga b ON b.id = c.botiga_id WHERE c.id = ?",
        (cabina_id,)).fetchone()
    basic = cabina["nivell"] == "basic"
    # Fins on hi ha dades ara: el que arribi mentre calculem es tornarà a mirar la propera vegada.
    max_lectura = con.execute("SELECT COALESCE(MAX(id), 0) FROM lectura_agregada").fetchone()[0]
    max_sensor = con.execute("SELECT COALESCE(MAX(id), 0) FROM sensor_event").fetchone()[0]
    estat = con.execute("SELECT * FROM estat_calcul WHERE cabina_id = ?", (cabina_id,)).fetchone()
    signatura = _signatura(con, cabina, regla)
    if basic:
        primer = con.execute("""SELECT MIN(l.inici) FROM lectura_agregada l JOIN antena a ON a.id = l.antena_id
                                WHERE a.cabina_id = ?""", (cabina_id,)).fetchone()[0]
    else:
        primer = con.execute("SELECT MIN(ts) FROM sensor_event WHERE cabina_id = ?", (cabina_id,)).fetchone()[0]
    primer = _dt(primer).isoformat() if primer else None

    cal, des = _punt_de_represa(con, cabina, estat, signatura, tot)
    if cal:
        try:
            if basic:
                _processa_zona_basic(con, cabina, regla, des)
            else:
                _processa_amb_sensors(con, cabina, regla, des)
            con.execute(
                """INSERT INTO estat_calcul (cabina_id, darrera_lectura_id, darrer_sensor_id, signatura)
                   VALUES (?, ?, ?, ?) ON CONFLICT(cabina_id) DO UPDATE SET
                     darrera_lectura_id = excluded.darrera_lectura_id, darrer_sensor_id = excluded.darrer_sensor_id,
                     signatura = excluded.signatura""", (cabina_id, max_lectura, max_sensor, signatura))
            con.commit()
        except Exception:
            con.rollback()
            raise
    if not basic:
        alertes.detecta_abandonades(con, cabina_id)
    return _proves_del_periode(con, cabina_id, primer)


def _processa_amb_sensors(con: sqlite3.Connection, cabina: sqlite3.Row, regla: ReglaProva, des: str | None) -> None:
    cabina_id = cabina["id"]
    veines = [v for v in cabina["veines"].split(",") if v]
    esdeveniments = [(_dt(f["ts"]), f["tipus"]) for f in con.execute(
        "SELECT ts, tipus FROM sensor_event WHERE cabina_id = ? AND (? IS NULL OR ts > ?) ORDER BY ts, id",
        (cabina_id, des, des))]
    if des:
        _esborra_des_de(con, cabina_id, des, estricte=True)
    else:
        # Només recalculem el període del qual encara tenim esdeveniments (la retenció esborra els antics).
        _esborra_des_de(con, cabina_id, esdeveniments[0][0].isoformat() if esdeveniments else None)

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


def _processa_zona_basic(con: sqlite3.Connection, cabina: sqlite3.Row, regla: ReglaProva, des: str | None) -> None:
    files = con.execute(
        """SELECT l.epc, l.inici, l.fi, l.n_lectures, l.rssi_mitja, a.llindar_rssi
           FROM lectura_agregada l JOIN antena a ON a.id = l.antena_id
           WHERE a.cabina_id = ? AND (? IS NULL OR l.inici > ?) ORDER BY l.inici, l.id""",
        (cabina["id"], des, des)).fetchall()
    lectures = [(f["epc"], _dt(f["inici"]), _dt(f["fi"]), f["n_lectures"], f["rssi_mitja"], f["llindar_rssi"])
                for f in files]
    if des:
        _esborra_des_de(con, cabina["id"], des, estricte=True)
    else:
        _esborra_des_de(con, cabina["id"], lectures[0][1].isoformat() if lectures else None)
    veines = [v for v in cabina["veines"].split(",") if v]

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


def _repara_gtin(con: sqlite3.Connection, botiga_id: str) -> None:
    """Proves d'una peça que no era al catàleg quan es va llegir: si ara ja hi és, se li posa el GTIN."""
    files = con.execute(
        """SELECT DISTINCT p.epc FROM prova p JOIN sessio s ON s.id = p.sessio_id JOIN cabina c ON c.id = s.cabina_id
           WHERE c.botiga_id = ? AND p.gtin IS NULL""", (botiga_id,)).fetchall()
    for f in files:
        gtin = cataleg.gtin_de_epc(con, f["epc"])
        if gtin:
            con.execute("UPDATE prova SET gtin = ? WHERE epc = ? AND gtin IS NULL", (gtin, f["epc"]))
    con.commit()


def processa_botiga(con: sqlite3.Connection, botiga_id: str, regla: ReglaProva, tot: bool = False) -> int:
    cabines = con.execute("SELECT id FROM cabina WHERE botiga_id = ?", (botiga_id,)).fetchall()
    n = sum(processa_cabina(con, c["id"], regla, tot) for c in cabines)
    _repara_gtin(con, botiga_id)
    return n
