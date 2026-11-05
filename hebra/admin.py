"""Eines d'administració per posar en marxa una botiga real.

  python -m hebra.admin botiga  desplegament/botiga.example.json
  python -m hebra.admin cataleg cataleg.csv          # variants de la marca (un GTIN per fila)
  python -m hebra.admin origen  origen.json          # fitxa d'origen (format hebra-origen/0.2)
  python -m hebra.admin etiquetes etiquetes.csv --botiga BCN-01 --url https://plataforma... --sortida nfc.csv
  python -m hebra.admin control --botiga BCN-01 --inici 2026-11-23 --setmanes 6
  python -m hebra.admin processa --botiga BCN-01

Formats CSV (capçalera obligatòria, separador coma o punt i coma):
  cataleg.csv:   gtin,model,color,talla,categoria,preu
  etiquetes.csv: epc,gtin     (epc en hex, com el llegeix el lector; gtin opcional si l'EPC és SGTIN-96)
"""

import argparse
import csv
import io
import json
import secrets
import sqlite3
from datetime import date
from pathlib import Path

from . import cataleg, control, db, proves, vendes
from . import epc as epc_mod
from .config import carrega


def _llegeix_csv(ruta: str) -> list[dict]:
    text = Path(ruta).read_text(encoding="utf-8-sig")
    sep = ";" if text[:2048].count(";") > text[:2048].count(",") else ","
    return [{k.strip().lower(): (v or "").strip() for k, v in fila.items()}
            for fila in csv.DictReader(io.StringIO(text), delimiter=sep)]


def botiga(con: sqlite3.Connection, ruta: str) -> str:
    """Dona d'alta (o actualitza) una botiga amb les cabines i antenes d'un JSON."""
    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    con.execute("""INSERT INTO botiga (id, nom, nivell, zona_horaria) VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET nom=excluded.nom, nivell=excluded.nivell,
                   zona_horaria=excluded.zona_horaria""",
                (d["id"], d["nom"], d.get("nivell", "cabina"), d.get("zona_horaria", "Europe/Madrid")))
    for c in d["cabines"]:
        con.execute("""INSERT INTO cabina (id, botiga_id, nom, veines) VALUES (?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET nom=excluded.nom, veines=excluded.veines""",
                    (c["id"], d["id"], c["nom"], ",".join(c.get("veines", []))))
        for a in c["antenes"]:
            con.execute("""INSERT INTO antena (id, cabina_id, port, llindar_rssi) VALUES (?, ?, ?, ?)
                           ON CONFLICT(id) DO UPDATE SET cabina_id=excluded.cabina_id, port=excluded.port,
                           llindar_rssi=excluded.llindar_rssi""",
                        (a["id"], c["id"], a["port"], a.get("llindar_rssi", -60)))
    con.commit()
    return f"Botiga {d['id']}: {len(d['cabines'])} cabines"


def cataleg_csv(con: sqlite3.Connection, ruta: str) -> str:
    n, errors = 0, []
    for i, f in enumerate(_llegeix_csv(ruta), start=2):
        try:
            gtin = f["gtin"].zfill(14)
            if not gtin.isdigit() or epc_mod.digit_control(gtin[:13]) != gtin[13]:
                raise ValueError(f"GTIN no vàlid {f['gtin']!r}")
            con.execute(
                """INSERT INTO catalog_sku (gtin, model, color, talla, categoria, preu_eur) VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(gtin) DO UPDATE SET model=excluded.model, color=excluded.color, talla=excluded.talla,
                   categoria=excluded.categoria, preu_eur=excluded.preu_eur""",
                (gtin, f["model"], f["color"], f["talla"], f.get("categoria") or "altres",
                 float(f["preu"].replace(",", ".")) if f.get("preu") else None))
            n += 1
        except (KeyError, ValueError) as e:
            errors.append(f"Línia {i}: {e}")
    # Les variants noves hereten la fitxa d'origen d'una altra variant del mateix model.
    con.execute("""UPDATE catalog_sku SET origen_json = (
                     SELECT k2.origen_json FROM catalog_sku k2
                     WHERE k2.model = catalog_sku.model AND k2.origen_json IS NOT NULL LIMIT 1)
                   WHERE origen_json IS NULL""")
    con.commit()
    return f"{n} variants importades" + (f"; errors: {errors[:10]}" if errors else "")


def etiquetes(con: sqlite3.Connection, ruta: str, botiga_id: str, url: str, sortida: str) -> str:
    """Aparella cada EPC (UHF) amb un token NFC aleatori i escriu la llista d'URL per gravar als xips.

    El token és aleatori (no es pot endevinar la fitxa d'una altra peça). Si l'EPC ja tenia
    token, es manté: així es pot tornar a executar sense invalidar etiquetes ja gravades.
    """
    files_sortida, errors = [], []
    for i, f in enumerate(_llegeix_csv(ruta), start=2):
        try:
            epc = epc_mod.normalitza(f["epc"])
            gtin = (f.get("gtin") or "").zfill(14) if f.get("gtin") else epc_mod.descodifica(f["epc"]).gtin
            if cataleg.sku(con, gtin) is None:
                raise ValueError(f"GTIN {gtin} no és al catàleg")
            existent = con.execute("SELECT nfc_token FROM etiqueta WHERE epc = ?", (epc,)).fetchone()
            token = existent["nfc_token"] if existent else secrets.token_urlsafe(9)
            con.execute("""INSERT INTO etiqueta (epc, nfc_token, gtin) VALUES (?, ?, ?)
                           ON CONFLICT(epc) DO UPDATE SET gtin=excluded.gtin""", (epc, token, gtin))
            files_sortida.append([f["epc"], gtin, f"{url.rstrip('/')}/p/{token}?b={botiga_id}"])
        except (KeyError, ValueError) as e:
            errors.append(f"Línia {i}: {e}")
    con.commit()
    with open(sortida, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["epc", "gtin", "url_nfc"])
        w.writerows(files_sortida)
    return f"{len(files_sortida)} etiquetes; URL per gravar als xips NFC a {sortida}" + (f"; errors: {errors[:10]}" if errors else "")


def main() -> None:
    ap = argparse.ArgumentParser(description="Administració de Hebra")
    sub = ap.add_subparsers(dest="ordre", required=True)
    sub.add_parser("botiga").add_argument("fitxer")
    sub.add_parser("cataleg").add_argument("fitxer")
    sub.add_parser("origen").add_argument("fitxer")
    e = sub.add_parser("etiquetes")
    e.add_argument("fitxer")
    e.add_argument("--botiga", required=True)
    e.add_argument("--url", required=True, help="URL pública de la plataforma")
    e.add_argument("--sortida", default="etiquetes-nfc.csv")
    c = sub.add_parser("control")
    c.add_argument("--botiga", required=True)
    c.add_argument("--inici", required=True, help="primer dia de mesura (AAAA-MM-DD)")
    c.add_argument("--setmanes", type=int, default=6)
    sub.add_parser("processa").add_argument("--botiga", required=True)
    args = ap.parse_args()

    cfg = carrega()
    con = db.connecta(cfg.ruta_bd)
    db.inicialitza(con)
    if args.ordre == "botiga":
        print(botiga(con, args.fitxer))
    elif args.ordre == "cataleg":
        print(cataleg_csv(con, args.fitxer))
    elif args.ordre == "origen":
        print(f"{cataleg.importa_origen(con, args.fitxer)} variants amb origen")
    elif args.ordre == "etiquetes":
        print(etiquetes(con, args.fitxer, args.botiga, args.url, args.sortida))
    elif args.ordre == "control":
        a = control.sorteja(args.botiga, "origen", date.fromisoformat(args.inici), args.setmanes)
        control.desa_assignacio(con, args.botiga, "origen", a)
        print(f"{len(a)} dies assignats: {sum(g == 'amb' for g in a.values())} amb origen, "
              f"{sum(g == 'sense' for g in a.values())} sense")
    elif args.ordre == "processa":
        print(f"{proves.processa_botiga(con, args.botiga, cfg.regla)} proves, "
              f"{vendes.atribueix(con, args.botiga)} vendes atribuïdes")


if __name__ == "__main__":
    main()
