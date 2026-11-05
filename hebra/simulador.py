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
  * esdeveniments de la fitxa NFC i peticions de talla.

Ús:  python -m hebra.simulador --setmanes 2 --inici 2026-11-16
"""

import argparse
import io
import csv
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


def simula(con: sqlite3.Connection, inici: date, setmanes: int = 1, llavor: int = 7) -> dict:
    rng = random.Random(llavor)
    prepara_botiga(con)
    peces = _peces_fisiques(con)
    control.desa_assignacio(con, BOTIGA, "origen", control.sorteja(BOTIGA, "origen", inici, setmanes))

    lot = {"lectures": [], "sensors": []}
    files_venda = []
    resum = {"sessions": 0, "peces_provades": 0}

    for d in range(setmanes * 7):
        dia = inici + timedelta(days=d)
        if dia.weekday() == 6:
            continue  # diumenge tancat
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
                        if rng.random() < 0.12:
                            germanes = [v for v in cataleg.variants_del_model(con, k["model"], k["color"]) if v["gtin"] != k["gtin"]]
                            if germanes:
                                ts_p = entra + timedelta(seconds=90)
                                pid = fitxa.demana_talla(con, sessio_nfc, BOTIGA, k["gtin"], rng.choice(germanes)["gtin"],
                                                         "ca", cabina, ts=ts_p.isoformat())
                                fila = con.execute("SELECT disponible FROM peticio_talla WHERE id = ?", (pid,)).fetchone()
                                estat = "lliurada" if fila["disponible"] != 0 else "no_disponible"
                                fitxa.resol_peticio(con, pid, estat, (ts_p + timedelta(seconds=rng.randint(40, 150))).isoformat())

                    # Compra?
                    p = CONVERSIO_BASE.get(k["categoria"], 0.25) + (EFECTE_ORIGEN if grup == "amb" and toca else 0)
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

    regla = carrega().regla
    resum["proves_detectades"] = proves.processa_botiga(con, BOTIGA, regla)
    resum["vendes_atribuides"] = vendes.atribueix(con, BOTIGA)
    resum["lectures"] = res.lectures
    resum["linies_venda"] = len(files_venda)
    resum["csv_vendes"] = sortida.getvalue()
    return resum


def main() -> None:
    ap = argparse.ArgumentParser(description="Omple la base de dades amb un pilot simulat.")
    ap.add_argument("--inici", default="2026-11-16", help="dilluns d'inici (AAAA-MM-DD)")
    ap.add_argument("--setmanes", type=int, default=2)
    ap.add_argument("--csv", help="desa també el CSV de vendes generat en aquest fitxer")
    args = ap.parse_args()

    cfg = carrega()
    con = db.connecta(cfg.ruta_bd)
    db.inicialitza(con)
    resum = simula(con, date.fromisoformat(args.inici), args.setmanes)
    if args.csv:
        Path(args.csv).write_text(resum["csv_vendes"], encoding="utf-8")
    resum.pop("csv_vendes")
    print("Simulació feta a", cfg.ruta_bd)
    for k, v in resum.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
