"""Simulador d'una botiga pilot: genera dades de prova realistes sense maquinari.

Serveix per veure la plataforma funcionant de punta a punta i per provar el
motor abans de tenir el lector. TOTES les dades són inventades.

Què simula:
  * 1 botiga (BCN-01), 3 cabines en fila (C1-C2-C3, veïnes entre si), 1 antena per cabina;
  * catàleg: les 4 peces del fitxer d'origen de prova, amb totes les talles;
  * sessions de cabina amb porta i presència, de dilluns a dissabte, 10 h - 20 h;
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
ORIGEN_PROVA = Path(__file__).resolve().parent.parent / "dades" / "origen-prova.json"

# Probabilitat de compra després d'una prova, per categoria (inventat).
CONVERSIO_BASE = {"camisa": 0.34, "jersei": 0.30, "vestit": 0.10, "texans": 0.27}
EFECTE_ORIGEN = 0.06   # punts de conversió que suma ensenyar l'origen (inventat)
# Talla que no quadra (insight 6): els texans en 38 es venen molt menys (inventat).
FACTOR_TALLA = {("TX-26-IND", "38"): 0.35}
SECCIONS_FITXA = ("talles", "cura", "preguntes")
# Variants que ningú no prova: estoc parat (insight 14). No tenen etiqueta.
EXTRES = [("08400000990017", "S", 6), ("08400000990024", "M", 4)]
MODEL_EXTRA = ("FL-25-GRS", "Gris", "faldilla", 65.0)
ESTOC_VESTIT = 90   # la marca n'ha comprat massa: risc de rebaixa (insight 15)
PROB_MOTIU = {"vestit": ["talla", "talla", "tall", "preu"], "default": ["preu", "color", "talla", "qualitat", "altre"]}


def prepara_botiga(con: sqlite3.Connection) -> None:
    con.execute("INSERT OR IGNORE INTO botiga (id, nom, nivell) VALUES (?, ?, 'cabina')", (BOTIGA, "Botiga de prova"))
    for i, c in enumerate(CABINES):
        veines = ",".join(CABINES[j] for j in (i - 1, i + 1) if 0 <= j < len(CABINES))
        con.execute("INSERT OR IGNORE INTO cabina (id, botiga_id, nom, veines) VALUES (?, ?, ?, ?)",
                    (c, BOTIGA, f"Cabina {i + 1}", veines))
        con.execute("INSERT OR IGNORE INTO antena (id, cabina_id, port, llindar_rssi) VALUES (?, ?, ?, -60)",
                    (f"R700-1:{i + 1}", c, i + 1))
    con.commit()
    cataleg.importa_origen(con, ORIGEN_PROVA, genera_talles=True)


def _peces_fisiques(con: sqlite3.Connection, per_sku: int = 3) -> list[tuple[str, sqlite3.Row]]:
    """Crea `per_sku` etiquetes (EPC + token NFC) per a cada SKU del catàleg."""
    from . import epc as epc_mod
    peces = []
    for k in con.execute("SELECT * FROM catalog_sku ORDER BY gtin").fetchall():
        g = k["gtin"]
        # GTIN-14 -> prefix d'empresa de 7 dígits (com al fitxer de prova) i referència.
        empresa, ref = g[1:8], g[0] + g[8:13]
        for s in range(per_sku):
            sg = epc_mod.Sgtin(empresa, ref, str(900000 + s))
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


def simula(con: sqlite3.Connection, inici: date, setmanes: int = 1, llavor: int = 7,
           fins: date | None = None) -> dict:
    """Simula `setmanes` setmanes des d'`inici`. Amb `fins`, no genera cap dia posterior (res al futur)."""
    rng = random.Random(llavor)
    rng2 = random.Random(llavor * 1000 + 1)  # només per a les dades del tauler
    prepara_botiga(con)
    peces = _peces_fisiques(con)
    dies = [inici + timedelta(days=d) for d in range(setmanes * 7)]
    dies = [d for d in dies if d.weekday() != 6 and (fins is None or d <= fins)]  # diumenge tancat
    darrer_dia = max(dies)
    control.desa_assignacio(con, BOTIGA, "origen", control.sorteja(BOTIGA, "origen", inici, setmanes))

    lot = {"lectures": [], "sensors": []}
    files_venda = []
    resum = {"sessions": 0, "peces_provades": 0}

    for dia in dies:
        grup = control.grup_del_dia(con, BOTIGA, "origen", dia.isoformat())
        for ci, cabina in enumerate(CABINES):
            antena = f"R700-1:{ci + 1}"
            veines = [f"R700-1:{j + 1}" for j in (ci - 1, ci + 1) if 0 <= j < len(CABINES)]
            t = datetime(dia.year, dia.month, dia.day, 10, rng.randint(0, 30), tzinfo=ZONA)
            while t.hour < 20:
                durada = timedelta(seconds=rng.randint(150, 600))
                fi = t + durada
                lot["sensors"] += [
                    {"cabina": cabina, "ts": t.isoformat(), "tipus": "porta_tancada"},
                    {"cabina": cabina, "ts": (t + timedelta(seconds=2)).isoformat(), "tipus": "presencia_si"},
                    {"cabina": cabina, "ts": fi.isoformat(), "tipus": "porta_oberta"},
                    {"cabina": cabina, "ts": (fi + timedelta(seconds=3)).isoformat(), "tipus": "presencia_no"},
                ]
                resum["sessions"] += 1
                sessio_nfc = fitxa.nova_sessio()
                for epc, k in rng.sample(peces, rng.randint(1, 3)):
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
                        hora = fi + timedelta(minutes=rng.randint(2, 15))
                        files_venda.append([hora.isoformat(), BOTIGA, k["gtin"], 1, k["preu_eur"], f"T{rng.randint(10**5, 10**6)}"])
                    elif toca and rng.random() < 0.35:
                        motiu = rng.choice(PROB_MOTIU.get(k["categoria"], PROB_MOTIU["default"]))
                        fitxa.registra(con, sessio_nfc, BOTIGA, k["gtin"], "motiu_no_compra", "ca", motiu,
                                       ts=(fi - timedelta(seconds=5)).isoformat())
                t = fi + timedelta(minutes=rng.randint(5, 45))
        # Algunes vendes sense prova (compra directa)
        for _ in range(rng.randint(0, 3)):
            _, k = rng.choice(peces)
            hora = datetime(dia.year, dia.month, dia.day, rng.randint(10, 19), rng.randint(0, 59), tzinfo=ZONA)
            files_venda.append([hora.isoformat(), BOTIGA, k["gtin"], 1, k["preu_eur"], f"T{rng.randint(10**5, 10**6)}"])

    res = passarella.desa_lot(con, lot)
    sortida = io.StringIO()
    w = csv.writer(sortida)
    w.writerow(["data_hora", "botiga", "gtin", "quantitat", "import", "tiquet"])
    w.writerows(files_venda)
    vendes.importa_csv(con, sortida.getvalue())

    _talla_esgotada(con, darrer_dia)
    _dades_tauler(con, inici, setmanes, darrer_dia, rng2)

    regla = carrega().regla
    resum["proves_detectades"] = proves.processa_botiga(con, BOTIGA, regla)
    resum["vendes_atribuides"] = vendes.atribueix(con, BOTIGA)
    resum["peces_abandonades"] = _abandonades(con, darrer_dia, rng2)
    resum["lectures"] = res.lectures
    resum["linies_venda"] = len(files_venda)
    resum["csv_vendes"] = sortida.getvalue()
    return resum


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


def _dades_tauler(con: sqlite3.Connection, inici: date, setmanes: int, darrer_dia: date, rng: random.Random) -> None:
    """Estoc, faldilla sense proves, experiment, pilot, recomptes, decisions i paràmetres (idempotent)."""
    fi = inici + timedelta(days=setmanes * 7 - 1)
    model, color, categoria, preu = MODEL_EXTRA
    for gtin, talla, _ in EXTRES:
        con.execute("""INSERT OR IGNORE INTO catalog_sku (gtin, model, color, talla, categoria, preu_eur, origen_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""", (gtin, model, color, talla, categoria, preu,
                                                      json.dumps({"nom": {"ca": "Faldilla de llana"}})))
    # Una venda antiga de la faldilla: fa més de 21 dies que no es mou.
    antiga = datetime.combine(inici - timedelta(days=35), datetime.min.time(), ZONA).replace(hour=12)
    if not con.execute("SELECT 1 FROM venda_linia WHERE gtin = ? AND data = ?",
                       (EXTRES[0][0], antiga.date().isoformat())).fetchone():
        con.execute("""INSERT INTO venda_linia (botiga_id, ts, data, gtin, quantitat, import_eur)
                       VALUES (?, ?, ?, ?, 1, ?)""", (BOTIGA, antiga.isoformat(), antiga.date().isoformat(), EXTRES[0][0], preu))

    actualitzat = datetime.combine(darrer_dia, datetime.min.time(), ZONA).replace(hour=21).isoformat()
    unitats: dict[str, int] = {g: u for g, _, u in EXTRES}
    for k in con.execute("SELECT gtin, model, talla, origen_json FROM catalog_sku WHERE origen_json IS NOT NULL"):
        if k["gtin"] in unitats:
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

    exp_id = f"origen-{inici:%Y-%m}"
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
        con.execute("INSERT OR IGNORE INTO parametre (botiga_id, clau, valor) VALUES ('*', ?, ?)", (clau, valor))
    con.commit()


def _abandonades(con: sqlite3.Connection, darrer_dia: date, rng: random.Random) -> int:
    """Unes quantes peces abandonades els darrers dies (insight 13); una ja resolta."""
    candidates = con.execute(
        """SELECT p.epc, s.cabina_id, s.fi FROM prova p JOIN sessio s ON s.id = p.sessio_id
           WHERE p.confianca != 'ambigua' AND s.inici >= ? ORDER BY p.id""",
        ((darrer_dia - timedelta(days=2)).isoformat(),)).fetchall()
    tria = rng.sample(candidates, min(4, len(candidates)))
    for i, c in enumerate(tria):
        detectada = datetime.fromisoformat(c["fi"]) + timedelta(minutes=30)
        resolta = (detectada + timedelta(minutes=20)).isoformat() if i == 0 else None
        con.execute("""INSERT OR IGNORE INTO peca_abandonada (epc, cabina_id, detectada, resolta)
                       VALUES (?, ?, ?, ?)""", (c["epc"], c["cabina_id"], detectada.isoformat(), resolta))
    con.commit()
    return len(tria)


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
