"""Lot de prova: dades inventades per veure la plataforma plena, que s'esborren d'un sol clic.

Serveix perquè una marca (o l'equip de Hebra en una demo) vegi com quedarà el tauler abans de tenir
dades reals, sense barrejar-les mai amb les reals:

  * tot va a una botiga pròpia, `PROVA-01` («Botiga de prova»), amb 3 cabines i antenes `PROVA-R700:n`;
  * el catàleg és el del fitxer de prova (dades/origen-prova.json) amb números de sèrie propis;
  * no escriu cap paràmetre general ni cap programació d'informes de tota la marca, i les seves
    programacions no tenen destinataris: no s'envia mai cap correu;
  * en carregar-lo es desa (taula `lot_prova`) quins GTIN i etiquetes ha creat. En esborrar-lo
    només s'esborra la botiga de prova (totes les files de qualsevol taula amb `botiga_id` o
    `cabina_id` seus) i aquests GTIN i etiquetes. Res més.

Les dades reals de la marca no es toquen ni en carregar ni en esborrar el lot.

v0.7: el lot es comporta com una botiga oberta. En carregar-lo arriba fins a l'hora d'ara (també el
matí d'avui), i després `posa_al_dia` hi afegeix, cada pocs minuts, els clients que haurien passat pels
provadors des de l'última vegada, amb el ritme d'un dia de botiga (hebra/simulador.py, `horari_cabina`).
Així els gràfics, el «Resum d'avui» i els informes diaris sempre tenen dades recents.
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta

from . import alertes, simulador, temps

BOTIGA = "PROVA-01"
NOM = "Botiga de prova"
CABINES = [f"{BOTIGA}-C{i}" for i in (1, 2, 3)]
LECTOR = "PROVA-R700"
SERIE_BASE = 700000
SETMANES = 2
MAX_DIES_AL_DIA = 14   # si la plataforma ha estat aturada més dies, només s'omplen els últims 14

_bloqueig = threading.Lock()


class ErrorLot(Exception):
    """El lot no es pot carregar o esborrar (missatge en català per a l'usuari)."""


def _crea_taula(con: sqlite3.Connection) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS lot_prova (
        botiga_id  TEXT PRIMARY KEY,
        creat      TEXT NOT NULL,
        des        TEXT NOT NULL,
        fins       TEXT NOT NULL,
        gtins_json TEXT NOT NULL,     -- GTIN que ha creat el lot (s'esborren amb ell)
        epcs_json  TEXT NOT NULL,     -- etiquetes que ha creat el lot
        resum_json TEXT NOT NULL,
        fins_ts    TEXT)              -- v0.7: fins a quina hora hi ha clients simulats""")
    if not any(c["name"] == "fins_ts" for c in con.execute("PRAGMA table_info(lot_prova)")):
        con.execute("ALTER TABLE lot_prova ADD COLUMN fins_ts TEXT")


@contextmanager
def _mode_prova():
    """El simulador escriu a la botiga de prova, aïllat, i sense avisos en directe mentre genera."""
    desat = {k: getattr(simulador, k) for k in ("BOTIGA", "CABINES", "LECTOR", "NOM_BOTIGA", "SERIE_BASE", "AILLAT")}
    publica = alertes.bus.publica
    try:
        simulador.BOTIGA, simulador.CABINES, simulador.LECTOR = BOTIGA, CABINES, LECTOR
        simulador.NOM_BOTIGA, simulador.SERIE_BASE, simulador.AILLAT = NOM, SERIE_BASE, True
        alertes.bus.publica = lambda *a, **k: None
        yield
    finally:
        for k, v in desat.items():
            setattr(simulador, k, v)
        alertes.bus.publica = publica


def estat(con: sqlite3.Connection) -> dict:
    """`GET /lot-prova`: si hi ha lot carregat, de quan és i què conté."""
    _crea_taula(con)
    f = con.execute("SELECT * FROM lot_prova WHERE botiga_id = ?", (BOTIGA,)).fetchone()
    if not f:
        return {"carregat": False, "botiga_id": BOTIGA, "nom": NOM}
    return {"carregat": True, "botiga_id": BOTIGA, "nom": NOM, "creat": f["creat"], "des": f["des"],
            "fins": f["fins"], "resum": json.loads(f["resum_json"])}


def _taules_amb(con: sqlite3.Connection, columna: str) -> list[str]:
    taules = [r["name"] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    return [t for t in taules
            if t != "lot_prova" and any(c["name"] == columna for c in con.execute(f'PRAGMA table_info("{t}")'))]


def carrega(con: sqlite3.Connection, avui: date | None = None) -> dict:
    """Crea la botiga de prova amb `SETMANES` setmanes de pilot simulat. Sense `avui`, arriba fins a
    l'hora d'ara; amb `avui` (proves), acaba ahir."""
    with _bloqueig:
        _crea_taula(con)
        if con.execute("SELECT 1 FROM lot_prova WHERE botiga_id = ?", (BOTIGA,)).fetchone():
            raise ErrorLot("Ja hi ha un lot de prova carregat. Esborra'l abans de tornar-lo a carregar.")
        if con.execute("SELECT 1 FROM botiga WHERE id = ?", (BOTIGA,)).fetchone():
            raise ErrorLot(f"Ja existeix una botiga «{BOTIGA}» que no és del lot de prova: no la toquem.")
        ara = None if avui else datetime.fromisoformat(temps.ara())
        avui = avui or ara.date()
        ahir = avui - timedelta(days=1)
        inici = ahir - timedelta(days=ahir.weekday(), weeks=SETMANES - 1)
        gtins_abans = {r[0] for r in con.execute("SELECT gtin FROM catalog_sku")}
        epcs_abans = {r[0] for r in con.execute("SELECT epc FROM etiqueta")}

        try:
            with _mode_prova():
                resum = simulador.simula(con, inici, SETMANES, fins=ahir, ara=ara)
        except Exception:
            # El simulador desa per parts: si falla a mitges, esborrem el que hagi creat.
            con.rollback()
            _esborra_botiga(con, {r[0] for r in con.execute("SELECT gtin FROM catalog_sku")} - gtins_abans,
                            {r[0] for r in con.execute("SELECT epc FROM etiqueta")} - epcs_abans)
            con.commit()
            raise

        gtins = sorted({r[0] for r in con.execute("SELECT gtin FROM catalog_sku")} - gtins_abans)
        epcs = sorted({r[0] for r in con.execute("SELECT epc FROM etiqueta")} - epcs_abans)
        resum.pop("csv_vendes", None)
        resum = {"sessions": resum["sessions"], "proves": resum["proves_detectades"],
                 "vendes": resum["linies_venda"], "peces": len(simulador.MODELS_PROVA)}
        fins_ts = ara or datetime.combine(ahir, time(23, 59, 59), simulador.ZONA)
        con.execute("""INSERT INTO lot_prova (botiga_id, creat, des, fins, gtins_json, epcs_json, resum_json, fins_ts)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (BOTIGA, temps.ara(), inici.isoformat(), fins_ts.date().isoformat(), json.dumps(gtins),
                     json.dumps(epcs), json.dumps(resum), fins_ts.isoformat(timespec="seconds")))
        con.commit()
        return estat(con)


def posa_al_dia(con: sqlite3.Connection, ara: datetime | None = None) -> int:
    """Afegeix al lot de prova els clients que haurien passat pels provadors des de l'última vegada
    (fins a `ara`). Retorna quantes sessions noves hi ha. No fa res si no hi ha lot carregat."""
    ara = ara or datetime.fromisoformat(temps.ara())
    with _bloqueig:
        _crea_taula(con)
        f = con.execute("SELECT * FROM lot_prova WHERE botiga_id = ?", (BOTIGA,)).fetchone()
        if not f:
            return 0
        des = datetime.fromisoformat(f["fins_ts"]) if f["fins_ts"] else \
            datetime.combine(date.fromisoformat(f["fins"]), time(23, 59, 59), simulador.ZONA)
        des = max(des, ara - timedelta(days=MAX_DIES_AL_DIA))
        if ara - des < timedelta(minutes=1):
            return 0
        epcs = json.loads(f["epcs_json"])
        q = ",".join("?" * len(epcs))
        peces = [(r["epc"], r) for r in con.execute(
            f"""SELECT e.epc, s.* FROM etiqueta e JOIN catalog_sku s ON s.gtin = e.gtin
                WHERE e.epc IN ({q}) ORDER BY s.gtin, e.epc""", epcs)] if epcs else []
        try:
            with _mode_prova():
                r = simulador.avanca(con, peces, des, ara, date.fromisoformat(f["des"]))
        except Exception:
            con.rollback()
            raise
        resum = json.loads(f["resum_json"])
        resum["sessions"] = resum.get("sessions", 0) + r["sessions"]
        resum["vendes"] = resum.get("vendes", 0) + r["linies_venda"]
        resum["proves"] = con.execute(
            """SELECT COUNT(*) FROM prova p JOIN sessio s ON s.id = p.sessio_id
               WHERE s.cabina_id IN (SELECT id FROM cabina WHERE botiga_id = ?)""", (BOTIGA,)).fetchone()[0]
        con.execute("UPDATE lot_prova SET fins = ?, fins_ts = ?, resum_json = ? WHERE botiga_id = ?",
                    (ara.date().isoformat(), ara.isoformat(timespec="seconds"), json.dumps(resum), BOTIGA))
        con.commit()
        return r["sessions"]


def _esborra_botiga(con: sqlite3.Connection, gtins: set[str], epcs: set[str]) -> dict:
    """Esborra la botiga de prova i el que en depèn. Retorna quantes files s'han esborrat per taula."""
    n: dict[str, int] = {}

    def esborra(sql: str, params: tuple, taula: str) -> None:
        k = con.execute(sql, params).rowcount
        if k:
            n[taula] = n.get(taula, 0) + k

    cab = [r[0] for r in con.execute("SELECT id FROM cabina WHERE botiga_id = ?", (BOTIGA,))]
    q = ",".join("?" * len(cab))
    if cab:
        ant = [r[0] for r in con.execute(f"SELECT id FROM antena WHERE cabina_id IN ({q})", cab)]
        sessions = f"SELECT id FROM sessio WHERE cabina_id IN ({q})"
        proves = f"SELECT id FROM prova WHERE sessio_id IN ({sessions})"
        esborra(f"DELETE FROM atribucio WHERE prova_id IN ({proves})", tuple(cab), "atribucio")
        esborra(f"DELETE FROM prova WHERE sessio_id IN ({sessions})", tuple(cab), "prova")
        if ant:
            qa = ",".join("?" * len(ant))
            esborra(f"DELETE FROM lectura_agregada WHERE antena_id IN ({qa})", tuple(ant), "lectura_agregada")
    esborra("""DELETE FROM atribucio WHERE venda_id IN (SELECT id FROM venda_linia WHERE botiga_id = ?)""",
            (BOTIGA,), "atribucio")
    # Experiments de la botiga: primer el que en depèn.
    exps = [r[0] for r in con.execute("SELECT id FROM experiment WHERE botiga_id = ?", (BOTIGA,))]
    if exps:
        qe = ",".join("?" * len(exps))
        esborra(f"DELETE FROM assignacio_model WHERE experiment IN ({qe})", tuple(exps), "assignacio_model")
        esborra(f"DELETE FROM decisio WHERE experiment_id IN ({qe})", tuple(exps), "decisio")
    esborra("DELETE FROM tasca WHERE botiga_desti = ?", (BOTIGA,), "tasca")
    esborra("""DELETE FROM sync_registre WHERE integracio_id IN (SELECT id FROM integracio WHERE botiga_id = ?)""",
            (BOTIGA,), "sync_registre")
    # Qualsevol taula amb cabina_id o botiga_id (també les que s'hi afegeixin en el futur).
    if cab:
        for t in _taules_amb(con, "cabina_id"):
            if t != "antena":
                esborra(f'DELETE FROM "{t}" WHERE cabina_id IN ({q})', tuple(cab), t)
        esborra(f"DELETE FROM antena WHERE cabina_id IN ({q})", tuple(cab), "antena")
    for t in _taules_amb(con, "botiga_id"):
        if t not in ("botiga", "cabina"):
            esborra(f'DELETE FROM "{t}" WHERE botiga_id = ?', (BOTIGA,), t)
    esborra("DELETE FROM cabina WHERE botiga_id = ?", (BOTIGA,), "cabina")
    esborra("DELETE FROM botiga WHERE id = ?", (BOTIGA,), "botiga")
    # Catàleg i etiquetes que va crear el lot (no els que ja hi eren).
    for e in epcs:
        esborra("DELETE FROM etiqueta WHERE epc = ?", (e,), "etiqueta")
    for g in gtins:
        esborra("DELETE FROM etiqueta WHERE gtin = ?", (g,), "etiqueta")
        esborra("DELETE FROM catalog_sku WHERE gtin = ?", (g,), "catalog_sku")
    models_buits = [r[0] for r in con.execute(
        "SELECT DISTINCT model FROM contingut_model WHERE model NOT IN (SELECT model FROM catalog_sku)")]
    for m in models_buits:
        if m in simulador.MODELS_PROVA:
            esborra("DELETE FROM contingut_model WHERE model = ?", (m,), "contingut_model")
    return n


def esborra(con: sqlite3.Connection) -> dict:
    """Esborra el lot de prova sencer. Les dades reals no es toquen."""
    with _bloqueig:
        _crea_taula(con)
        f = con.execute("SELECT * FROM lot_prova WHERE botiga_id = ?", (BOTIGA,)).fetchone()
        if not f:
            raise ErrorLot("No hi ha cap lot de prova carregat.")
        try:
            n = _esborra_botiga(con, set(json.loads(f["gtins_json"])), set(json.loads(f["epcs_json"])))
            con.execute("DELETE FROM lot_prova WHERE botiga_id = ?", (BOTIGA,))
            con.commit()
        except Exception:
            con.rollback()
            raise
        return {"esborrat": True, "files": sum(n.values()), "per_taula": n}
