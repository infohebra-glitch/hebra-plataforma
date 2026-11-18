"""Eines d'administració per posar en marxa una botiga real.

  python -m hebra.admin botiga  desplegament/botiga.example.json
  python -m hebra.admin cataleg cataleg.csv          # variants de la marca (un GTIN per fila)
  python -m hebra.admin origen  origen.json          # fitxa d'origen (format hebra-origen/0.2)
  python -m hebra.admin etiquetes etiquetes.csv --botiga BCN-01 --url https://plataforma... --sortida nfc.csv
  python -m hebra.admin control --botiga BCN-01 --inici 2026-11-23 --setmanes 6
  python -m hebra.admin processa --botiga BCN-01
  python -m hebra.admin usuari --correu anna@marca.cat --nom Anna --rol marca          # demana la contrasenya
  python -m hebra.admin usuari --correu bcn@marca.cat --nom "Botiga BCN" --rol botiga --botiga BCN-01
  python -m hebra.admin estoc estoc.csv              # botiga,gtin,unitats
  python -m hebra.admin shopify --botiga BCN-01      # sincronitza comandes i estoc (només lectura)
  python -m hebra.admin retencio                     # esborra lectures i sensors més antics que HEBRA_RETENCIO_DIES
  python -m hebra.admin claus                        # genera claus aleatòries per a /etc/hebra/plataforma.env (només per pantalla)
  python -m hebra.admin comprova                     # revisa la configuració abans d'engegar en producció
  python -m hebra.admin copia --carpeta /opt/copies  # còpia de seguretat de la base de dades (n'hi ha 14 de guardades)

Formats CSV (capçalera obligatòria, separador coma o punt i coma):
  cataleg.csv:   gtin,model,color,talla,categoria,preu
  etiquetes.csv: epc,gtin     (epc en hex, com el llegeix el lector; gtin opcional si l'EPC és SGTIN-96)
"""

import argparse
import csv
import getpass
import io
import json
import secrets
import sqlite3
import sys
from datetime import date
from pathlib import Path

from . import alertes, auth, cataleg, control, db, estoc, proves, retencio, shopify, vendes
from .integracions import ErrorIntegracio
from .integracions import motor as integracions_motor
from . import epc as epc_mod
from .config import carrega


def _llegeix_csv(ruta: str) -> list[dict]:
    return _llegeix_text_csv(Path(ruta).read_text(encoding="utf-8-sig"))


def _llegeix_text_csv(text: str) -> list[dict]:
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
    n, errors = importa_cataleg(con, Path(ruta).read_text(encoding="utf-8-sig"))
    return f"{n} variants importades" + (f"; errors: {errors[:10]}" if errors else "")


def importa_cataleg(con: sqlite3.Connection, text: str) -> tuple[int, list[str]]:
    """Importa variants del catàleg (gtin,model,color,talla,categoria,preu). Retorna (importades, errors)."""
    n, errors = 0, []
    for i, f in enumerate(_llegeix_text_csv(text), start=2):
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
    return n, errors


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


def sincronitza_shopify(con: sqlite3.Connection, clau: str, botiga_id: str) -> dict:
    """La integració Shopify activa de la botiga (desada des del tauler) o, si no n'hi ha,
    la configuració antiga (paràmetres shopify_* i HEBRA_SHOPIFY_TOKEN_<BOTIGA>)."""
    fila = con.execute("""SELECT id FROM integracio WHERE proveidor = 'shopify' AND actiu = 1 AND botiga_id = ?
                          ORDER BY id LIMIT 1""", (botiga_id,)).fetchone()
    if fila:
        return integracions_motor.sincronitza(con, clau, fila["id"])
    return shopify.sincronitza(con, botiga_id)


def claus() -> str:
    """Valors nous per a la configuració de producció. No es desen enlloc: es copien al fitxer d'entorn."""
    return "\n".join([
        "HEBRA_ENTORN=produccio",
        "HEBRA_COOKIE_SECURE=1",
        f"HEBRA_SECRET={secrets.token_urlsafe(48)}",
        f"HEBRA_CLAU_PASSARELLA={secrets.token_urlsafe(32)}",
        f"HEBRA_SAL_TIQUET={secrets.token_urlsafe(24)}",
        "# HEBRA_CONTRASENYA_BOTIGA=   (buida: les pàgines antigues /botiga queden desactivades)",
    ])


def comprova_configuracio() -> tuple[list[str], list[str]]:
    """(errors, avisos) de la configuració llegida de l'entorn, sense arrencar res."""
    import os
    from .config import Config, problemes_produccio
    cfg = Config()
    errors, avisos = [], []
    if not cfg.produccio:
        errors.append("HEBRA_ENTORN no és «produccio»")
    errors += problemes_produccio(cfg)
    if os.environ.get("HEBRA_SAL_TIQUET", "hebra-mvp") in ("hebra-mvp", "canvia-aquesta-sal", ""):
        errors.append("HEBRA_SAL_TIQUET encara és la d'exemple (canvieu-la ABANS de pujar vendes: després no es pot canviar)")
    carpeta = Path(cfg.ruta_bd).resolve().parent
    if not os.access(carpeta, os.W_OK):
        errors.append(f"No es pot escriure a la carpeta de la base de dades ({carpeta})")
    if not Path(cfg.frontend_dist, "index.html").exists():
        avisos.append(f"No hi ha tauler compilat a {cfg.frontend_dist} (cal «npm run build» a frontend/)")
    if not cfg.smtp_host:
        avisos.append("Sense HEBRA_SMTP_HOST: els informes es generen però no s'envien per correu")
    return errors, avisos


def copia(ruta_bd: str, carpeta: str, dies: int = 14) -> str:
    """Còpia consistent de la base de dades en marxa (API de còpia de SQLite), comprovada i amb rotació."""
    from datetime import datetime
    destí = Path(carpeta)
    destí.mkdir(parents=True, exist_ok=True)
    fitxer = destí / f"hebra-{datetime.now():%Y-%m-%d_%H%M}.db"
    origen = sqlite3.connect(ruta_bd)
    try:
        sortida = sqlite3.connect(fitxer)
        try:
            origen.backup(sortida)
            if sortida.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                fitxer.unlink(missing_ok=True)
                raise RuntimeError("La còpia no ha passat la comprovació d'integritat")
        finally:
            sortida.close()
    finally:
        origen.close()
    fitxer.chmod(0o600)
    antigues = sorted(destí.glob("hebra-*.db"))[:-max(1, dies)]
    for f in antigues:
        f.unlink()
    return f"{fitxer} ({fitxer.stat().st_size // 1024} KB; {len(antigues)} d'antigues esborrades)"


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
    u = sub.add_parser("usuari", help="crea un usuari del tauler")
    u.add_argument("--correu", required=True)
    u.add_argument("--nom", required=True)
    u.add_argument("--rol", required=True, choices=auth.ROLS)
    u.add_argument("--botiga", help="obligatori per al rol botiga")
    u.add_argument("--contrasenya", help="si no s'indica, es demana (no queda a l'historial)")
    sub.add_parser("estoc").add_argument("fitxer")
    sub.add_parser("shopify").add_argument("--botiga", required=True)
    sub.add_parser("retencio")
    sub.add_parser("claus")
    sub.add_parser("comprova")
    k = sub.add_parser("copia")
    k.add_argument("--carpeta", required=True)
    k.add_argument("--dies", type=int, default=14, help="quantes còpies es guarden")
    args = ap.parse_args()

    # Ordres que no han d'arrencar la configuració (la de producció es pot negar a carregar-se).
    if args.ordre == "claus":
        print(claus())
        return
    if args.ordre == "comprova":
        errors, avisos = comprova_configuracio()
        for e in errors:
            print("✗", e)
        for a in avisos:
            print("!", a)
        print("Tot a punt per a producció." if not errors else f"{len(errors)} problema(es) per resoldre.")
        sys.exit(1 if errors else 0)
    if args.ordre == "copia":
        import os
        print(copia(os.environ.get("HEBRA_BD", "hebra.db"), args.carpeta, args.dies))
        return

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
        n_proves = proves.processa_botiga(con, args.botiga, cfg.regla, tot=True)  # a mà: tot el període
        n_atrib = vendes.atribueix(con, args.botiga)
        n_aband = sum(alertes.detecta_abandonades(con, c["id"], tot=True) for c in con.execute(
            "SELECT id FROM cabina WHERE botiga_id = ?", (args.botiga,)).fetchall())
        print(f"{n_proves} proves, {n_atrib} vendes atribuïdes, {n_aband} peces abandonades noves")
    elif args.ordre == "usuari":
        contrasenya = args.contrasenya
        if not contrasenya:
            contrasenya = getpass.getpass("Contrasenya: ")
            if contrasenya != getpass.getpass("Repeteix-la: "):
                sys.exit("Les contrasenyes no coincideixen")
        try:
            uid = auth.crea_usuari(con, args.correu, args.nom, args.rol, contrasenya, args.botiga)
        except ValueError as e:
            sys.exit(str(e))
        print(f"Usuari {uid} creat: {args.correu} ({args.rol})")
    elif args.ordre == "estoc":
        n, errors = estoc.importa_csv(con, Path(args.fitxer).read_text(encoding="utf-8-sig"))
        print(f"{n} files d'estoc importades" + (f"; errors: {errors[:10]}" if errors else ""))
    elif args.ordre == "shopify":
        try:
            print(sincronitza_shopify(con, cfg.secret, args.botiga))
        except ErrorIntegracio as e:
            sys.exit(str(e))
    elif args.ordre == "retencio":
        print(retencio.neteja(con, cfg.retencio_dies))


if __name__ == "__main__":
    main()
