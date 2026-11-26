"""Simulador d'una botiga pilot: genera dades de prova realistes sense maquinari.

Serveix per veure la plataforma funcionant de punta a punta i per provar el
motor abans de tenir el lector. TOTES les dades són inventades.

Què simula:
  * 1 botiga (BCN-01), 3 cabines en fila (C1-C2-C3, veïnes entre si), 1 antena per cabina;
  * catàleg: les 4 peces del fitxer d'origen de prova, amb totes les talles;
  * sessions de cabina amb porta i presència, de dilluns a dissabte, 10 h - 21 h, amb el ritme d'una
    botiga de veritat (v0.7): puntes a migdia i a la tarda, dilluns fluix, dissabte ple;
  * lectures agregades cada 10 s, amb "passos" curts i lectures creuades a la cabina veïna;
  * vendes en CSV amb una conversió diferent per model (el vestit "es prova i no es ven");
  * grup de control de l'origen per dies, amb un efecte petit i inventat;
  * esdeveniments de la fitxa NFC (també les seccions vistes) i peticions de talla,
    algunes encara obertes l'últim dia i una talla esgotada demanada 3 cops;
  * per al tauler: estoc per GTIN (amb talles a zero i una faldilla que ningú no prova),
    l'experiment d'origen, el pilot amb criteris d'èxit, recomptes d'estoc,
    decisions, peces abandonades i els paràmetres per defecte.

El que s'ha afegit per al tauler fa servir un generador aleatori propi, de manera
que les proves i vendes simulades són les mateixes que abans.

v0.3 D-E: tasques de botiga d'exemple, programacions d'informes per defecte i els
informes lliurats de les setmanes simulades.

v0.3 (generador propi `rng3`, tampoc no canvia el que hi havia): algunes sessions
amb 4-5 peces, sessions amb el mateix model en dues talles (dubte de talla, i de
vegades se n'acaba comprant una) i peticions d'assistència des de la fitxa.

Ús:  python -m hebra.simulador --setmanes 2 --inici 2026-11-16
"""

import argparse
import csv
import io
import json
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import cataleg, control, db, fitxa, passarella, proves, vendes
from .config import carrega

ZONA = ZoneInfo("Europe/Madrid")
BOTIGA = "BCN-01"
CABINES = ["BCN-01-C1", "BCN-01-C2", "BCN-01-C3"]
LECTOR = "R700-1"            # les antenes es diuen «LECTOR:port»
NOM_BOTIGA = "Botiga de prova"
SERIE_BASE = 900000          # número de sèrie de les etiquetes simulades
# Mode aïllat (lot de prova dins d'una plataforma amb dades reals, hebra/lot_prova.py): només toca la botiga
# simulada i els GTIN del fitxer de prova; no crea paràmetres generals ni informes de tota la marca.
AILLAT = False
ORIGEN_PROVA = Path(__file__).resolve().parent.parent / "dades" / "origen-prova.json"
# v0.5: foto de producte de cada model de prova (dades/fotos-prova/<model>.jpg, imatges generades per a la demo)
FOTOS_PROVA = ORIGEN_PROVA.parent / "fotos-prova"

# Probabilitat de compra després d'una prova, per categoria (inventat).
CONVERSIO_BASE = {"camisa": 0.34, "jersei": 0.30, "vestit": 0.10, "texans": 0.27}
EFECTE_ORIGEN = 0.06   # punts de conversió que suma ensenyar l'origen (inventat)
# Talla que no quadra (insight 6): els texans en 38 es venen molt menys (inventat).
FACTOR_TALLA = {("TX-26-IND", "38"): 0.35}
SECCIONS_FITXA = ("talles", "cura", "preguntes")
# Variants que ningú no prova: estoc parat (insight 14). No tenen etiqueta.
EXTRES = [("08400000990017", "S", 6), ("08400000990024", "M", 4)]
MODEL_EXTRA = ("FL-25-GRS", "Gris", "faldilla", 65.0)
# Models del lot de prova: els del fitxer d'origen de prova i la faldilla extra.
MODELS_PROVA = frozenset({p["model"] for p in json.loads(ORIGEN_PROVA.read_text(encoding="utf-8"))["peces"]}
                         | {MODEL_EXTRA[0]})
# v0.3: probabilitats per sessió (inventades)
PROB_DUBTE_TALLA = 0.10    # el client s'emporta el mateix model en una altra talla
PROB_COMPRA_DUBTE = 0.45   # i n'acaba comprant la segona talla
PROB_MOLTES_PECES = 0.12   # sessió de 4 o 5 peces
PROB_ASSISTENCIA = 0.05    # demana que l'atenguin des de la fitxa
ESTOC_VESTIT = 90   # la marca n'ha comprat massa: risc de rebaixa (insight 15)
PROB_MOTIU = {"vestit": ["talla", "talla", "tall", "preu"], "default": ["preu", "color", "talla", "qualitat", "altre"]}


def prepara_botiga(con: sqlite3.Connection) -> None:
    con.execute("INSERT OR IGNORE INTO botiga (id, nom, nivell) VALUES (?, ?, 'cabina')", (BOTIGA, NOM_BOTIGA))
    for i, c in enumerate(CABINES):
        veines = ",".join(CABINES[j] for j in (i - 1, i + 1) if 0 <= j < len(CABINES))
        con.execute("INSERT OR IGNORE INTO cabina (id, botiga_id, nom, veines) VALUES (?, ?, ?, ?)",
                    (c, BOTIGA, f"Cabina {i + 1}", veines))
        con.execute("INSERT OR IGNORE INTO antena (id, cabina_id, port, llindar_rssi) VALUES (?, ?, ?, -60)",
                    (f"{LECTOR}:{i + 1}", c, i + 1))
    con.commit()
    cataleg.importa_origen(con, ORIGEN_PROVA, genera_talles=True)
    fotos_prova(con)


def fotos_prova(con: sqlite3.Connection) -> int:
    """Desa la foto de cada model de prova que és al catàleg i encara no en té (la marca la pot canviar
    des del tauler). Es crida també en arrencar la plataforma, per a les dades de prova d'abans de la v0.5."""
    from . import imatges
    ja = {r["model"] for r in con.execute("SELECT DISTINCT model FROM imatge_peca")}
    cataleg_ = {r["model"] for r in con.execute("SELECT DISTINCT model FROM catalog_sku")}
    n = 0
    for f in sorted(FOTOS_PROVA.glob("*.jpg")):
        if f.stem in cataleg_ and f.stem not in ja:
            imatges.desa(con, f.stem, "", f.read_bytes(), font="prova")
            n += 1
    return n


def _peces_fisiques(con: sqlite3.Connection, per_sku: int = 3) -> list[tuple[str, sqlite3.Row]]:
    """Crea `per_sku` etiquetes (EPC + token NFC) per a cada SKU del catàleg (en mode aïllat, només dels
    models de prova)."""
    from . import epc as epc_mod
    peces = []
    files = con.execute("SELECT * FROM catalog_sku ORDER BY gtin").fetchall()
    if AILLAT:
        models = set(MODELS_PROVA)
        files = [k for k in files if k["model"] in models]
    for k in files:
        g = k["gtin"]
        # GTIN-14 -> prefix d'empresa de 7 dígits (com al fitxer de prova) i referència.
        empresa, ref = g[1:8], g[0] + g[8:13]
        for s in range(per_sku):
            sg = epc_mod.Sgtin(empresa, ref, str(SERIE_BASE + s))
            con.execute("INSERT OR IGNORE INTO etiqueta (epc, nfc_token, gtin) VALUES (?, ?, ?)",
                        (sg.urn, cataleg.nou_token(), g))
            peces.append((sg.urn, k))
    con.commit()
    return peces


def _lectures(epc: str, antena: str, inici: datetime, fi: datetime, rssi: float, rng: random.Random) -> list[dict]:
    out, t = [], inici
    while t < fi:
        seg = min(t + timedelta(seconds=10), fi)
        mitja = rssi + rng.uniform(-3, 3)
        out.append({"epc": epc, "antena": antena, "inici": t.isoformat(), "fi": seg.isoformat(),
                    "n": rng.randint(6, 15), "rssi_max": round(mitja + rng.uniform(1, 4), 1),
                    "rssi_mitja": round(mitja, 1)})
        t = seg
    return out


# v0.7: ritme d'un dia de botiga de veritat (inventat però versemblant). Una cabina s'omple més o menys
# segons l'hora (puntes a migdia i a la tarda, calma a l'hora de dinar) i el dia (dilluns fluix, dissabte
# ple); la tercera cabina només s'omple quan hi ha cua. Obert de dilluns a dissabte, de 10 h a 21 h.
OBERTURA, TANCAMENT = 10, 21
AFLUENCIA_HORA = {10: 0.35, 11: 0.6, 12: 0.9, 13: 1.0, 14: 0.55, 15: 0.45, 16: 0.65, 17: 0.95,
                  18: 1.25, 19: 1.35, 20: 0.8}
AFLUENCIA_DIA = (0.7, 0.75, 0.8, 0.9, 1.15, 1.6)   # dilluns ... dissabte
PES_CABINA = (1.0, 0.85, 0.6)


def horari_cabina(dia: date, ci: int, llavor: int = 7) -> list[tuple[datetime, datetime]]:
    """Les sessions (entra, surt) d'una cabina un dia. Sempre les mateixes per a un mateix dia i cabina,
    de manera que es poden generar a trossos (el lot de prova es va posant al dia cada pocs minuts)."""
    if dia.weekday() == 6:
        return []
    rng = random.Random(f"{llavor}-{dia.isoformat()}-{ci}")
    pes = PES_CABINA[ci] if ci < len(PES_CABINA) else 0.5
    obertura = datetime(dia.year, dia.month, dia.day, OBERTURA, 0, tzinfo=ZONA)
    # El primer client no entra just en obrir: com més fluix és el matí, més tarda.
    t = obertura + timedelta(minutes=min(rng.uniform(2, 30) / max(AFLUENCIA_DIA[dia.weekday()] * pes * 0.6, 0.15), 120))
    ultima = datetime(dia.year, dia.month, dia.day, TANCAMENT - 1, 40, tzinfo=ZONA)
    out = []
    while t <= ultima:
        intensitat = AFLUENCIA_HORA.get(t.hour, 0.3) * AFLUENCIA_DIA[dia.weekday()] * pes
        fi = t + timedelta(seconds=rng.randint(150, 600))
        out.append((t, fi))
        espera = rng.uniform(4, 40) / max(intensitat, 0.15)
        t = fi + timedelta(minutes=min(max(espera, 0.5), 100))
    return out


def simula(con: sqlite3.Connection, inici: date, setmanes: int = 1, llavor: int = 7,
           fins: date | None = None, ara: datetime | None = None) -> dict:
    """Simula `setmanes` setmanes des d'`inici`. Amb `fins`, no genera cap dia posterior (res al futur).
    Amb `ara`, també el dia d'avui fins a aquesta hora (les sessions que ja s'han acabat)."""
    rng2 = random.Random(llavor * 1000 + 1)  # només per a les dades del tauler
    prepara_botiga(con)
    peces = _peces_fisiques(con)
    dies = [inici + timedelta(days=d) for d in range(setmanes * 7)]
    limit = ara.date() if ara else fins
    dies = [d for d in dies if d.weekday() != 6 and (limit is None or d <= limit)]  # diumenge tancat
    if ara and dies and dies[-1] == ara.date() and ara.hour < OBERTURA + 1:
        dies.pop()  # avui encara no ha passat res
    darrer_dia = max(dies)
    control.desa_assignacio(con, BOTIGA, "origen", control.sorteja(BOTIGA, "origen", inici, setmanes))

    resum = _simula_franja(con, peces, dies, None, ara, darrer_dia, llavor)

    dia_talla = darrer_dia
    if ara and datetime.combine(darrer_dia, datetime.min.time(), ZONA).replace(hour=18, minute=20) > ara:
        dia_talla = dies[-2] if len(dies) > 1 else darrer_dia
    _talla_esgotada(con, dia_talla)
    _dades_tauler(con, inici, setmanes, darrer_dia, rng2, ara)

    regla = carrega().regla
    resum["proves_detectades"] = proves.processa_botiga(con, BOTIGA, regla)
    resum["vendes_atribuides"] = vendes.atribueix(con, BOTIGA)
    resum["peces_abandonades"] = _abandonades(con, darrer_dia, rng2, ara)
    resum["tasques"] = _tasques(con, inici, darrer_dia)
    resum["informes_lliurats"] = _informes(con, inici, setmanes, _fins_informes(fins, ara))
    return resum


def _fins_informes(fins: date | None, ara: datetime | None) -> date | None:
    """Fins a quin dia es generen els informes lliurats (el diari d'avui surt a les 8:01 amb les dades d'ahir)."""
    if ara is None:
        return fins
    return ara.date() - timedelta(days=1 if ara.hour >= 8 else 2)


def avanca(con: sqlite3.Connection, peces: list[tuple[str, sqlite3.Row]], des: datetime, ara: datetime,
           inici: date, llavor: int = 7) -> dict:
    """Afegeix les sessions de cabina que s'han acabat entre `des` i `ara` (cap al futur), amb les seves
    vendes, fitxes i peticions, i torna a calcular proves, vendes atribuïdes i informes. És el que fa que
    el lot de prova sembli una botiga oberta: cada pocs minuts hi ha clients nous. No crea peces noves."""
    dies, d = [], des.date()
    while d <= ara.date():
        if d.weekday() != 6:
            dies.append(d)
        d += timedelta(days=1)
    resum = _simula_franja(con, peces, dies, des, ara, None, llavor) if dies and peces else \
        {"sessions": 0, "peces_provades": 0, "lectures": 0, "linies_venda": 0, "csv_vendes": ""}
    if resum["sessions"]:
        resum["proves_detectades"] = proves.processa_botiga(con, BOTIGA, carrega().regla)
        resum["vendes_atribuides"] = vendes.atribueix(con, BOTIGA)
    setmanes = (ara.date() - inici).days // 7 + 1
    resum["informes_lliurats"] = _informes(con, inici, setmanes, _fins_informes(None, ara))
    return resum


def _simula_franja(con: sqlite3.Connection, peces: list[tuple[str, sqlite3.Row]], dies: list[date],
                   des: datetime | None, ara: datetime | None, darrer_dia: date | None, llavor: int) -> dict:
    """Les sessions dels `dies` que s'acaben dins (des, ara], i les vendes sense prova d'aquests dies."""
    per_gtin: dict[str, list[tuple[str, sqlite3.Row]]] = {}
    for epc, k in peces:
        per_gtin.setdefault(k["gtin"], []).append((epc, k))
    lot = {"lectures": [], "sensors": []}
    files_venda: list[list] = []
    resum = {"sessions": 0, "peces_provades": 0}

    def dins(ts: datetime) -> bool:
        return (des is None or ts > des) and (ara is None or ts <= ara)

    def ven(hora: datetime, k: sqlite3.Row, rng: random.Random) -> None:
        if ara is not None and hora > ara:
            hora = ara  # el tiquet es fa ara mateix
        files_venda.append([hora.isoformat(), BOTIGA, k["gtin"], 1, k["preu_eur"], f"T{rng.randint(10**5, 10**6)}"])

    for dia in dies:
        grup = control.grup_del_dia(con, BOTIGA, "origen", dia.isoformat())
        for ci, cabina in enumerate(CABINES):
            antena = f"{LECTOR}:{ci + 1}"
            veines = [f"{LECTOR}:{j + 1}" for j in (ci - 1, ci + 1) if 0 <= j < len(CABINES)]
            for t, fi in horari_cabina(dia, ci, llavor):
                if not dins(fi + timedelta(seconds=3)):
                    continue
                rng = random.Random(f"{llavor}-{cabina}-{t.isoformat()}-a")
                rng2 = random.Random(f"{llavor}-{cabina}-{t.isoformat()}-b")
                rng3 = random.Random(f"{llavor}-{cabina}-{t.isoformat()}-c")
                lot["sensors"] += [
                    {"cabina": cabina, "ts": t.isoformat(), "tipus": "porta_tancada"},
                    {"cabina": cabina, "ts": (t + timedelta(seconds=2)).isoformat(), "tipus": "presencia_si"},
                    {"cabina": cabina, "ts": fi.isoformat(), "tipus": "porta_oberta"},
                    {"cabina": cabina, "ts": (fi + timedelta(seconds=3)).isoformat(), "tipus": "presencia_no"},
                ]
                resum["sessions"] += 1
                sessio_nfc = fitxa.nova_sessio()
                triades = rng.sample(peces, min(len(peces), rng.randint(1, 3)))
                for epc, k in triades:
                    pas = rng.random() < 0.15  # entra i surt de seguida: no és prova
                    entra = t + timedelta(seconds=rng.randint(5, 20))
                    surt = entra + timedelta(seconds=30) if pas else fi - timedelta(seconds=rng.randint(5, 20))
                    lot["lectures"] += _lectures(epc, antena, entra, surt, -50, rng)
                    if veines and rng.random() < 0.3:  # la cabina del costat també la veu, més fluix
                        lot["lectures"] += _lectures(epc, rng.choice(veines), entra, surt, rng.choice([-58, -53]), rng)
                    if pas:
                        continue
                    resum["peces_provades"] += 1

                    # Fitxa NFC
                    toca = rng.random() < 0.45
                    if toca:
                        fitxa.registra(con, sessio_nfc, BOTIGA, k["gtin"], "obre_fitxa", rng.choice(fitxa.IDIOMES),
                                       ts=(entra + timedelta(seconds=40)).isoformat())
                        if grup == "amb" and rng.random() < 0.5:
                            fitxa.registra(con, sessio_nfc, BOTIGA, k["gtin"], "veu_origen", "ca",
                                           ts=(entra + timedelta(seconds=60)).isoformat())
                        if rng2.random() < 0.6:
                            _veu_seccio(con, sessio_nfc, k["gtin"], rng2.choice(SECCIONS_FITXA), grup,
                                        (entra + timedelta(seconds=70)).isoformat())
                        if rng.random() < 0.12:
                            germanes = [v for v in cataleg.variants_del_model(con, k["model"], k["color"]) if v["gtin"] != k["gtin"]]
                            if germanes:
                                ts_p = entra + timedelta(seconds=90)
                                pid = fitxa.demana_talla(con, sessio_nfc, BOTIGA, k["gtin"], rng.choice(germanes)["gtin"],
                                                         "ca", cabina, ts=ts_p.isoformat())
                                fila = con.execute("SELECT disponible FROM peticio_talla WHERE id = ?", (pid,)).fetchone()
                                estat = "lliurada" if fila["disponible"] != 0 else "no_disponible"
                                ts_r = (ts_p + timedelta(seconds=rng.randint(40, 150))).isoformat()
                                if dia == darrer_dia and estat == "lliurada" and rng2.random() < 0.5:
                                    _deixa_oberta(con, pid, rng2.choice(["pendent", "en_cami"]))
                                else:
                                    fitxa.resol_peticio(con, pid, estat, ts_r)

                    # Compra?
                    p = CONVERSIO_BASE.get(k["categoria"], 0.25) + (EFECTE_ORIGEN if grup == "amb" and toca else 0)
                    p *= FACTOR_TALLA.get((k["model"], k["talla"]), 1)
                    if rng.random() < p:
                        ven(fi + timedelta(minutes=rng.randint(2, 15)), k, rng)
                    elif toca and rng.random() < 0.35:
                        motiu = rng.choice(PROB_MOTIU.get(k["categoria"], PROB_MOTIU["default"]))
                        fitxa.registra(con, sessio_nfc, BOTIGA, k["gtin"], "motiu_no_compra", "ca", motiu,
                                       ts=(fi - timedelta(seconds=5)).isoformat())
                _novetats_sessio(con, lot, files_venda, triades, peces, per_gtin, cabina, antena, t, fi,
                                 sessio_nfc, dia == darrer_dia, rng3, ven)
        # Algunes vendes sense prova (compra directa), més els dies forts
        rng = random.Random(f"{llavor}-{dia.isoformat()}-directes")
        for _ in range(rng.randint(0, round(3 * AFLUENCIA_DIA[dia.weekday()]))):
            _, k = rng.choice(peces)
            hora = datetime(dia.year, dia.month, dia.day, rng.randint(OBERTURA, TANCAMENT - 1), rng.randint(0, 59),
                            tzinfo=ZONA)
            if dins(hora):
                ven(hora, k, rng)

    res = passarella.desa_lot(con, lot)
    sortida = io.StringIO()
    w = csv.writer(sortida)
    w.writerow(["data_hora", "botiga", "gtin", "quantitat", "import", "tiquet"])
    w.writerows(files_venda)
    if files_venda:
        vendes.importa_csv(con, sortida.getvalue())
    resum["lectures"] = res.lectures
    resum["linies_venda"] = len(files_venda)
    resum["csv_vendes"] = sortida.getvalue()
    return resum



# ---------------------------------------------------------------- Novetats v0.3


def _novetats_sessio(con: sqlite3.Connection, lot: dict, files_venda: list, triades: list, peces: list,
                     per_gtin: dict, cabina: str, antena: str, t: datetime, fi: datetime, sessio_nfc: str,
                     darrer_dia: bool, rng: random.Random, ven) -> None:
    """Afegeix a una sessió peces de més (dubte de talla, sessions grans) i, de vegades, una petició d'assistència."""
    dins = {epc for epc, _ in triades}
    extres: list[tuple[str, sqlite3.Row, float]] = []  # (epc, sku, probabilitat de compra)
    if rng.random() < PROB_DUBTE_TALLA:
        _, k = rng.choice(triades)
        germanes = cataleg.variants_del_model(con, k["model"], k["color"])
        i = next(j for j, v in enumerate(germanes) if v["gtin"] == k["gtin"])
        veines = [germanes[j] for j in (i - 1, i + 1) if 0 <= j < len(germanes)]
        candidates = [pf for v in veines for pf in per_gtin.get(v["gtin"], []) if pf[0] not in dins]
        if candidates:
            epc, k2 = rng.choice(candidates)
            extres.append((epc, k2, PROB_COMPRA_DUBTE))
            dins.add(epc)
    if rng.random() < PROB_MOLTES_PECES:
        for epc, k2 in rng.sample(peces, rng.randint(2, 3)):
            if epc not in dins and len(dins) < 5:
                extres.append((epc, k2, CONVERSIO_BASE.get(k2["categoria"], 0.25)))
                dins.add(epc)
    for epc, k2, p in extres:
        entra = t + timedelta(seconds=rng.randint(5, 20))
        lot["lectures"] += _lectures(epc, antena, entra, fi - timedelta(seconds=rng.randint(5, 20)), -50, rng)
        if rng.random() < p:
            ven(fi + timedelta(minutes=rng.randint(2, 15)), k2, rng)
    if rng.random() < PROB_ASSISTENCIA:
        _, k = rng.choice(triades)
        ts = t + timedelta(seconds=rng.randint(60, 120))
        pid = fitxa.demana_assistencia(con, sessio_nfc, BOTIGA, k["gtin"], "ca", cabina, ts=ts.isoformat())
        if darrer_dia and rng.random() < 0.4:
            _deixa_oberta(con, pid, "pendent")
        else:
            fitxa.resol_peticio(con, pid, "lliurada", (ts + timedelta(seconds=rng.randint(30, 140))).isoformat())


# ---------------------------------------------------------------- Dades per al tauler


def _veu_seccio(con: sqlite3.Connection, sessio_nfc: str, gtin: str, seccio: str, grup: str | None, ts: str) -> None:
    """La fitxa NFC registra quina secció obre el client (talles, cura, preguntes). Insert directe:
    no depèn de la versió de fitxa.TIPUS."""
    con.execute("""INSERT INTO esdeveniment_nfc (sessio_nfc, ts, botiga_id, gtin, tipus, valor, idioma, grup)
                   VALUES (?, ?, ?, ?, 'veu_seccio', ?, 'ca', ?)""", (sessio_nfc, ts, BOTIGA, gtin, seccio, grup))


def _deixa_oberta(con: sqlite3.Connection, peticio_id: int, estat: str) -> None:
    con.execute("UPDATE peticio_talla SET estat = ?, hora_resolta = NULL WHERE id = ?", (estat, peticio_id))
    con.commit()


def _talla_esgotada(con: sqlite3.Connection, dia: date) -> None:
    """Tres clients demanen la camisa de lli en L (sense estoc) el darrer dia: alerta de talla esgotada."""
    m = con.execute("SELECT gtin FROM catalog_sku WHERE model = 'CL-24-NAT' AND talla = 'M'").fetchone()
    l_ = con.execute("SELECT gtin FROM catalog_sku WHERE model = 'CL-24-NAT' AND talla = 'L'").fetchone()
    if not m or not l_:
        return
    for i, (h, mi) in enumerate([(17, 5), (17, 40), (18, 15)]):
        ts = datetime(dia.year, dia.month, dia.day, h, mi, tzinfo=ZONA)
        pid = fitxa.demana_talla(con, fitxa.nova_sessio(), BOTIGA, m["gtin"], l_["gtin"], "ca", CABINES[i],
                                 ts=ts.isoformat())
        if i < 2:
            fitxa.resol_peticio(con, pid, "no_disponible", (ts + timedelta(seconds=70)).isoformat())


def _dades_tauler(con: sqlite3.Connection, inici: date, setmanes: int, darrer_dia: date, rng: random.Random,
                  ara: datetime | None = None) -> None:
    """Estoc, faldilla sense proves, experiment, pilot, recomptes, decisions i paràmetres (idempotent)."""
    fi = inici + timedelta(days=setmanes * 7 - 1)
    model, color, categoria, preu = MODEL_EXTRA
    for gtin, talla, _ in EXTRES:
        con.execute("""INSERT OR IGNORE INTO catalog_sku (gtin, model, color, talla, categoria, preu_eur, origen_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""", (gtin, model, color, talla, categoria, preu,
                                                      json.dumps({"nom": {"ca": "Faldilla de llana"}})))
    fotos_prova(con)
    # Una venda antiga de la faldilla: fa més de 21 dies que no es mou.
    antiga = datetime.combine(inici - timedelta(days=35), datetime.min.time(), ZONA).replace(hour=12)
    if not con.execute("SELECT 1 FROM venda_linia WHERE gtin = ? AND data = ?",
                       (EXTRES[0][0], antiga.date().isoformat())).fetchone():
        con.execute("""INSERT INTO venda_linia (botiga_id, ts, data, gtin, quantitat, import_eur)
                       VALUES (?, ?, ?, ?, 1, ?)""", (BOTIGA, antiga.isoformat(), antiga.date().isoformat(), EXTRES[0][0], preu))

    actualitzat_ = datetime.combine(darrer_dia, datetime.min.time(), ZONA).replace(hour=21)
    actualitzat = (min(actualitzat_, ara) if ara else actualitzat_).isoformat()
    unitats: dict[str, int] = {g: u for g, _, u in EXTRES}
    for k in con.execute("SELECT gtin, model, talla, origen_json FROM catalog_sku WHERE origen_json IS NOT NULL"):
        if k["gtin"] in unitats or (AILLAT and k["model"] not in MODELS_PROVA):
            continue
        u = (json.loads(k["origen_json"]).get("estoc") or {}).get(k["talla"]) or 0
        unitats[k["gtin"]] = ESTOC_VESTIT if k["model"] == "VV-26-VRD" and u else u
    con.executemany("""INSERT INTO estoc (botiga_id, gtin, unitats, actualitzat, font) VALUES (?, ?, ?, ?, 'csv')
                       ON CONFLICT(botiga_id, gtin) DO UPDATE SET unitats = excluded.unitats,
                         actualitzat = excluded.actualitzat""",
                    [(BOTIGA, g, u, actualitzat) for g, u in sorted(unitats.items())])

    # Recompte manual contra RFID a l'inici (insight 23)
    if not con.execute("SELECT 1 FROM recompte_estoc WHERE botiga_id = ?", (BOTIGA,)).fetchone():
        for g in sorted(unitats, key=lambda g: (-unitats[g], g))[:6]:
            manual = unitats[g]
            con.execute("INSERT INTO recompte_estoc (botiga_id, data, gtin, manual, rfid) VALUES (?, ?, ?, ?, ?)",
                        (BOTIGA, inici.isoformat(), g, manual, max(0, manual - rng.choice([0, 0, 0, 1, 2]))))

    exp_id = f"origen-{inici:%Y-%m}" + (f"-{BOTIGA.lower()}" if AILLAT else "")
    con.execute("""INSERT OR IGNORE INTO experiment (id, botiga_id, variable, hipotesi, unitat, inici, fi, proves_minimes, estat)
                   VALUES (?, ?, 'origen', ?, 'dia', ?, ?, 30, 'actiu')""",
                (exp_id, BOTIGA, "Ensenyar l'origen a la fitxa NFC fa que es compri més després de provar.",
                 inici.isoformat(), fi.isoformat()))
    criteris = [
        {"id": "c1", "descripcio": "Proves de confiança alta o mitjana", "metrica": "pct_proves_valides",
         "objectiu": 0.85, "comparador": ">="},
        {"id": "c2", "descripcio": "Mediana de resposta a les peticions de talla", "metrica": "temps_resposta_mediana_s",
         "objectiu": 120, "comparador": "<="},
        {"id": "c3", "descripcio": "Clients que responen el motiu de no compra", "metrica": "taxa_resposta_motiu",
         "objectiu": 0.10, "comparador": ">="},
        {"id": "c4", "descripcio": "Error de l'estoc RFID contra el recompte manual", "metrica": "error_estoc_pct",
         "objectiu": 0.05, "comparador": "<="},
    ]
    con.execute("""INSERT OR IGNORE INTO pilot (botiga_id, inici, fi, criteris_json, taxa_error_observacio)
                   VALUES (?, ?, ?, ?, 0.04)""",
                (BOTIGA, (inici - timedelta(days=7)).isoformat(), (inici + timedelta(days=41)).isoformat(),
                 json.dumps(criteris, ensure_ascii=False)))

    if not con.execute("SELECT 1 FROM decisio WHERE botiga_id = ?", (BOTIGA,)).fetchone():
        dia1 = (inici + timedelta(days=4)).isoformat() + "T19:00:00+01:00"
        dia2 = (inici + timedelta(days=8)).isoformat() + "T19:00:00+01:00"
        con.executemany(
            """INSERT INTO decisio (botiga_id, creada, titol, descripcio, insight, model, responsable, data_limit,
                                   estat, experiment_id, resultat) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(BOTIGA, dia1, "Moure el vestit de viscosa a l'entrada", "Es prova molt i es ven poc.",
              "molt_provat_poc_venut", "VV-26-VRD", "BOT", (inici + timedelta(days=7)).isoformat(), "feta", None,
              "Fet el dia 5. Una setmana després la conversió no ha canviat: el problema sembla la talla."),
             (BOTIGA, dia2, "Demanar la camisa de lli en L", "Peticions de la L sense estoc.",
              "demanda_perduda", "CL-24-NAT", "PROD", (inici + timedelta(days=14)).isoformat(), "acceptada", None, None),
             (BOTIGA, dia2, "Mantenir la prova de l'origen fins al final", "",
              "experiment", None, "MKT", fi.isoformat(), "proposada", exp_id, None)])

    for clau, valor in (("marge_peca", "40"), ("quota_mensual", "350"), ("dades_simulades", "1")):
        con.execute("INSERT OR IGNORE INTO parametre (botiga_id, clau, valor) VALUES (?, ?, ?)",
                    (BOTIGA if AILLAT else "*", clau, valor))
    con.commit()


def _abandonades(con: sqlite3.Connection, darrer_dia: date, rng: random.Random, ara: datetime | None = None) -> int:
    """Unes quantes peces abandonades els darrers dies (insight 13); una ja resolta."""
    candidates = con.execute(
        f"""SELECT p.epc, s.cabina_id, s.fi FROM prova p JOIN sessio s ON s.id = p.sessio_id
           WHERE p.confianca != 'ambigua' AND s.inici >= ? AND s.cabina_id IN ({",".join("?" * len(CABINES))})
           ORDER BY p.id""",
        ((darrer_dia - timedelta(days=2)).isoformat(), *CABINES)).fetchall()
    if ara is not None:  # cap peça «abandonada» que encara no s'hauria pogut detectar
        candidates = [c for c in candidates if datetime.fromisoformat(c["fi"]) + timedelta(minutes=30) <= ara]
    tria = rng.sample(candidates, min(4, len(candidates)))
    for i, c in enumerate(tria):
        detectada = datetime.fromisoformat(c["fi"]) + timedelta(minutes=30)
        resolta = (detectada + timedelta(minutes=20)).isoformat() if i == 0 else None
        con.execute("""INSERT OR IGNORE INTO peca_abandonada (epc, cabina_id, detectada, resolta)
                       VALUES (?, ?, ?, ?)""", (c["epc"], c["cabina_id"], detectada.isoformat(), resolta))
    con.commit()
    return len(tria)


# ---------------------------------------------------------------- v0.3 D-E: tasques i informes


def _tasques(con: sqlite3.Connection, inici: date, darrer_dia: date) -> int:
    """Unes quantes tasques de botiga: dues de pendents, una de feta i una de descartada (idempotent)."""
    from . import tasques
    if con.execute("SELECT 1 FROM tasca WHERE botiga_id = ?", (BOTIGA,)).fetchone():
        return 0
    l_ = con.execute("SELECT gtin FROM catalog_sku WHERE model = 'CL-24-NAT' AND talla = 'L'").fetchone()
    vestit = con.execute("SELECT gtin FROM catalog_sku WHERE model = 'VV-26-VRD' ORDER BY gtin LIMIT 1").fetchone()

    def hora(d: date, h: int) -> str:
        return datetime.combine(d, datetime.min.time(), ZONA).replace(hour=h).isoformat()
    noves = [
        ("recompte", "Recompte de la zona de provadors", "Comparar el recompte manual amb la lectura RFID.",
         None, None, inici, "feta"),
        ("moure_a_sala", None, "No s'ha provat mai: probablement és al magatzem.", EXTRES[0][0], None, darrer_dia,
         "pendent"),
        ("altre", "Demanar la camisa de lli en L", "Tres clients l'han demanada avui i no n'hi ha.",
         l_["gtin"] if l_ else None, None, darrer_dia, "pendent"),
        ("promocio", "Posar el vestit de viscosa a l'aparador", "Proposta descartada: el problema és la talla.",
         vestit["gtin"] if vestit else None, None, inici + timedelta(days=5), "descartada"),
    ]
    for tipus, titol, detall, gtin, unitats, dia, estat in noves:
        t, _ = tasques.crea(con, BOTIGA, tipus, titol, detall, gtin, unitats, ts=hora(dia, 10), notifica=False)
        if estat != "pendent":
            tasques.canvia_estat(con, t["id"], estat, ts=hora(dia, 18), notifica=False)
    return len(noves)


def programacions() -> list[tuple]:
    """(tipus, botiga, dia_setmana, dia_mes, destinataris). En mode aïllat, només les de la botiga simulada
    i sense destinataris: un lot de prova no ha d'enviar mai cap correu."""
    p = [("diari", BOTIGA, None, None, ["botiga.bcn@marca.example"]),
         ("setmanal", BOTIGA, 0, None, ["botiga.bcn@marca.example", "direccio@marca.example"]),
         ("mensual", None, None, 1, ["direccio@marca.example", "producte@marca.example"]),
         ("temporada", None, None, None, ["direccio@marca.example", "producte@marca.example"])]
    if AILLAT:
        return [(t, b, ds, dm, []) for t, b, ds, dm, _ in p if b == BOTIGA]
    return p


def _informes(con: sqlite3.Connection, inici: date, setmanes: int, fins: date | None) -> int:
    """Programacions per defecte (diari 08:00, setmanal dilluns 08:00, mensual dia 1 08:00 i temporada en
    acabar el pilot) i els informes lliurats de les setmanes simulades, com si el bucle de fons els hagués
    generat cada matí. No s'envien: els lliurats queden «no_enviat». Idempotent."""
    from . import informes_programats as ip
    final = inici + timedelta(days=setmanes * 7)        # el dilluns després de l'última setmana
    if fins is not None:
        final = min(final, fins + timedelta(days=1))
    # «Creades» el primer dia simulat a les 0 h: el primer lliurat és el diari d'aquell dia.
    creada = datetime.combine(inici + timedelta(days=1), datetime.min.time(), ZONA).isoformat()
    n = 0
    for tipus, botiga, dia_setmana, dia_mes, destinataris in programacions():
        fila = con.execute("SELECT * FROM programacio_informe WHERE tipus = ? AND botiga_id IS ?",
                           (tipus, botiga)).fetchone()
        if fila is None:
            data_ = (inici + timedelta(days=42)).isoformat() if tipus == "temporada" else None
            pid = con.execute(
                """INSERT INTO programacio_informe (botiga_id, tipus, actiu, dia_setmana, dia_mes, data, hora,
                                                    destinataris, creada) VALUES (?, ?, 1, ?, ?, ?, '08:00', ?, ?)""",
                (botiga, tipus, dia_setmana, dia_mes, data_, json.dumps(destinataris), creada)).lastrowid
            fila = con.execute("SELECT * FROM programacio_informe WHERE id = ?", (pid,)).fetchone()
        prog = dict(fila)
        d = inici + timedelta(days=1)
        while d <= final:
            ocurrencia = ip.toca(prog, datetime.combine(d, datetime.min.time(), ZONA).replace(hour=8, minute=1),
                                 ZONA.key)
            if ocurrencia is not None:
                des, fi = ip.periode(tipus, ocurrencia.date())
                if not con.execute("SELECT 1 FROM informe_lliurat WHERE programacio_id = ? AND des = ?",
                                   (prog["id"], des.isoformat())).fetchone():
                    ip.genera(con, tipus, botiga, des, fi, prog["id"], ocurrencia.isoformat())
                    n += 1
                prog["darrera_execucio"] = ocurrencia.isoformat()
                con.execute("UPDATE programacio_informe SET darrera_execucio = ? WHERE id = ?",
                            (prog["darrera_execucio"], prog["id"]))
            d += timedelta(days=1)
    con.commit()
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Omple la base de dades amb un pilot simulat.")
    ap.add_argument("--inici", help="dilluns d'inici (AAAA-MM-DD); per defecte, perquè l'última setmana simulada sigui l'actual")
    ap.add_argument("--setmanes", type=int, default=2)
    ap.add_argument("--csv", help="desa també el CSV de vendes generat en aquest fitxer")
    args = ap.parse_args()

    cfg = carrega()
    con = db.connecta(cfg.ruta_bd)
    db.inicialitza(con)
    if args.inici:
        inici = date.fromisoformat(args.inici)
    else:  # acaba ahir: el tauler mostra dades de seguida i no hi ha res al futur
        ahir = date.today() - timedelta(days=1)
        inici = ahir - timedelta(days=ahir.weekday(), weeks=args.setmanes - 1)
    resum = simula(con, inici, args.setmanes,
                   fins=None if args.inici else date.today() - timedelta(days=1))
    if args.csv:
        Path(args.csv).write_text(resum["csv_vendes"], encoding="utf-8")
    resum.pop("csv_vendes")
    print("Simulació feta a", cfg.ruta_bd)
    for k, v in resum.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
