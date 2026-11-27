"""Devolucions online: importar el fitxer de la marca i traduir-ne els motius (v0.9).

Per què: al provador el client diu (a la fitxa NFC) per què no s'emporta una peça. A la botiga en línia,
quan torna una peça, també en dona un motiu. Comparar-los per model i per talla diu si el problema és
el mateix als dos llocs (p. ex. «talla» als dos: el patró va petit) o no (al provador «preu», online
«no era com a la foto»: el problema online és la foto, no la peça).

Què NO fa, a propòsit:
  * no uneix mai una persona del provador amb un client online. No es pot (el provador no sap qui
    és ningú) i no cal: la comparació és per model, talla i període, sempre en agregat;
  * no desa cap dada personal. El fitxer només ha de portar data, GTIN, unitats i motiu. Si porta
    columnes com correu, nom, adreça o telèfon, s'ignoren i l'importador avisa;
  * el comentari lliure del client (si n'hi ha) es llegeix per deduir-ne la categoria i es llença:
    no es desa enlloc;
  * el número de comanda (si n'hi ha) només serveix per fer una empremta (SHA-256 amb sal) que evita
    comptar dues vegades la mateixa línia si es torna a pujar el fitxer.

Format CSV (capçalera obligatòria, separador coma o punt i coma, UTF-8):

    data,gtin,quantitat,motiu,comentari,comanda
    2026-11-20,08400000123457,1,TALLA_PEQUENA,,PED-88812

  * obligatòries: `data` i `gtin` (o `sku`/`ean`), i `motiu` o `comentari`;
  * `quantitat` per defecte 1; `comentari` i `comanda` opcionals.

Categories: les mateixes del provador (fitxa_config.MOTIUS i els motius propis de la marca), més
quatre que només tenen sentit online (DOMES_ONLINE). La talla, a més, pot portar un sentit:
«massa petita» o «massa gran».
"""

import csv
import hashlib
import io
import os
import re
import sqlite3
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta

from . import fitxa_config

SAL = os.environ.get("HEBRA_SAL_TIQUET", "hebra-mvp")

NOMES_ONLINE = {
    "diferent_foto": "No era com a la foto o la descripció",
    "defecte": "Defecte o arribada malmesa",
    "enviament": "Enviament: tard o peça equivocada",
    "canvi_opinio": "Ha canviat d'opinió",
}
SENTITS = ("petita", "gran")

ALIES = {"sku": "gtin", "ean": "gtin", "codi_barres": "gtin", "data_devolucio": "data", "fecha": "data",
         "date": "data", "data_hora": "data", "qty": "quantitat", "unitats": "quantitat", "cantidad": "quantitat",
         "quantity": "quantitat", "motivo": "motiu", "reason": "motiu", "motiu_devolucio": "motiu",
         "comentario": "comentari", "comment": "comentari", "observaciones": "comentari",
         "pedido": "comanda", "order": "comanda", "order_id": "comanda", "comanda_id": "comanda"}

# Columnes que no volem ni llegir: si hi són, s'ignoren i l'importador ho diu.
_PERSONALS = re.compile(r"(mail|correu|correo|nom\b|^nom|name|nombre|client|customer|telef|phone|movil|mobil|"
                        r"adre|address|direcc|domicil|dni|nif|nie|cp\b|postal|zip|iban|tarjeta|card|usuari|user)")

MAX_CODI = 60
MIN_COMPARAR = 5


def categories(con: sqlite3.Connection) -> dict[str, str]:
    """{clau: nom} de les categories a què es pot assignar un motiu de devolució."""
    from .analitica import base
    cats = {k: v for k, v in base.noms_motius(con).items() if k != "nomes_mirava"}
    return {**cats, **NOMES_ONLINE}


# ---------------------------------------------------------------- Classificació automàtica


def _net(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[_\-/.,;:()]+", " ", t).strip()


_REGLES: list[tuple[str, str | None, re.Pattern]] = [(m, s, re.compile(p)) for m, s, p in [
    ("defecte", None, r"\b(defect|malm|danad|damag|roto|rota\b|trenca|broken|descos|mancha|taca|stain|faulty|abim|forat|agujer|hole)"),
    ("diferent_foto", None, r"\b(foto|imagen|imatge|photo|picture|descrip|described|como en la web|com a la web|no es como|no era com|no era como|not as|pas conforme|diferente a|diferent de)"),
    ("talla", "petita", r"(\b(pequen|petit|small|estret|estrech|ajustad|tight|apreta|menor)|\bxica|massa just|muy just)"),
    ("talla", "gran", r"\b(grande|gran\b|grans\b|big|large|ampl|ancho|loose|holgad|folgad|mayor|enorme)"),
    ("talla", None, r"\b(talla|size|taille|mida|medida|no me queda|no em queda|doesn ?t fit|does not fit|not fit|fit\b)"),
    ("enviament", None, r"\b(tard|late\b|retras|delay|equivoca|wrong|incorrect|error|no es el que|no era el que|duplica|no llego|no ha arribat)"),
    ("tall", None, r"\b(forma|silueta|corte|cut\b|shape|tall\b|patron|patro\b|favorec|estil|style|como queda|com queda|largo|llarg|long\b|corto|curt|short)"),
    ("color", None, r"\b(color|colour|couleur|tono|tonalitat)"),
    ("qualitat", None, r"\b(calidad|qualitat|quality|qualite|tejido|teixit|fabric|material|tela\b|tacte|tacto|transparen|pica\b|pilling|bolitas)"),
    ("preu", None, r"\b(precio|preu|price|prix|caro|car\b|expensive|barat|cheaper|descuento|descompte|rebaj|rebaix|oferta)"),
    ("canvi_opinio", None, r"\b(cambi\w* de opinion|ya no lo quiero|ja no el vull|ja no la vull|no lo necesito|no el necessito|change\w* (my )?mind|no longer|ja no|ya no)"),
]]


def classifica(text: str | None) -> tuple[str | None, str | None]:
    """(categoria, sentit) deduïts d'un motiu o comentari. (None, None) si no se n'endevina cap."""
    t = _net(text or "")
    if not t:
        return None, None
    for motiu, sentit, patro in _REGLES:
        if patro.search(t):
            return motiu, sentit
    return None, None


def neteja_codi(text: str | None) -> str:
    """El motiu tal com ve, curt i sense res que sembli un correu, un telèfon o un número llarg."""
    t = (text or "").strip()
    t = re.sub(r"\S+@\S+", "", t)
    t = re.sub(r"\+?\d[\d\s]{6,}\d", "", t)
    return re.sub(r"\s+", " ", t).strip()[:MAX_CODI].lower()


def _ref(*parts: str) -> str:
    return hashlib.sha256(("devolucio:" + SAL + ":" + "|".join(parts)).encode()).hexdigest()


# ---------------------------------------------------------------- Mapa de motius


def mapa(con: sqlite3.Connection) -> dict[str, tuple[str, str | None]]:
    return {r["codi"]: (r["motiu"], r["sentit"]) for r in con.execute("SELECT codi, motiu, sentit FROM devolucio_mapa")}


def assegura_mapa(con: sqlite3.Connection, codi: str) -> None:
    """Afegeix el codi al mapa amb la traducció automàtica si encara no hi és."""
    if not codi:
        return
    motiu, sentit = classifica(codi)
    con.execute("INSERT OR IGNORE INTO devolucio_mapa (codi, motiu, sentit, manual) VALUES (?, ?, ?, 0)",
                (codi, motiu or "altre", sentit))


def desa_mapa(con: sqlite3.Connection, codi: str, motiu: str, sentit: str | None) -> dict:
    """La marca tria a quina categoria va un dels seus motius. ValueError si la categoria no existeix."""
    if motiu not in categories(con):
        raise ValueError(f"Categoria desconeguda: {motiu}")
    if sentit is not None and (motiu != "talla" or sentit not in SENTITS):
        raise ValueError("El sentit (massa petita o massa gran) només val per a la talla")
    if not con.execute("SELECT 1 FROM devolucio_mapa WHERE codi = ?", (codi,)).fetchone():
        raise KeyError(codi)
    con.execute("UPDATE devolucio_mapa SET motiu = ?, sentit = ?, manual = 1 WHERE codi = ?", (motiu, sentit, codi))
    con.commit()
    return {"codi": codi, "motiu": motiu, "sentit": sentit, "manual": True}


def llista_mapa(con: sqlite3.Connection) -> dict:
    """Els motius de la marca que han sortit a les devolucions, amb quantes unitats i a què es tradueixen."""
    n = Counter()
    for r in con.execute("SELECT codi, SUM(quantitat) AS u FROM devolucio_online GROUP BY codi"):
        n[r["codi"]] = r["u"]
    files = [{"codi": r["codi"], "motiu": r["motiu"], "sentit": r["sentit"], "manual": bool(r["manual"]),
              "unitats": n[r["codi"]], "suggeriment": classifica(r["codi"])[0]}
             for r in con.execute("SELECT * FROM devolucio_mapa ORDER BY codi")]
    files.sort(key=lambda x: (-x["unitats"], x["codi"]))
    return {"codis": files, "categories": [{"clau": k, "nom": v, "nomes_online": k in NOMES_ONLINE}
                                            for k, v in categories(con).items()]}


# ---------------------------------------------------------------- Lectura de les devolucions


def files(con: sqlite3.Connection, des: str, fins_exclusiu: str) -> list[dict]:
    """Devolucions del període amb el model, la talla i el motiu ja traduït (categoria i sentit)."""
    m = mapa(con)
    out = []
    for r in con.execute(
            """SELECT d.*, k.model, k.talla FROM devolucio_online d LEFT JOIN catalog_sku k ON k.gtin = d.gtin
               WHERE d.data >= ? AND d.data < ?""", (des, fins_exclusiu)):
        motiu, sentit = m.get(r["codi"], (None, None)) if r["codi"] else (None, None)
        if motiu in (None, "altre") and r["motiu_comentari"]:
            motiu, sentit = r["motiu_comentari"], r["sentit_comentari"]
        elif motiu == "talla" and sentit is None and r["motiu_comentari"] == "talla":
            sentit = r["sentit_comentari"]
        out.append({"data": r["data"], "gtin": r["gtin"], "model": r["model"], "talla": r["talla"],
                    "quantitat": r["quantitat"], "motiu": motiu or "altre", "sentit": sentit if motiu == "talla" else None})
    return out


def resum(con: sqlite3.Connection) -> dict:
    fila = con.execute("SELECT COUNT(*) AS n, SUM(quantitat) AS u, MIN(data) AS des, MAX(data) AS fins "
                       "FROM devolucio_online").fetchone()
    return {"linies": fila["n"], "unitats": fila["u"] or 0, "des": fila["des"], "fins": fila["fins"]}


# ---------------------------------------------------------------- Importació


def importa_csv(con: sqlite3.Connection, text: str, lot_prova: bool = False) -> dict:
    """Importa un CSV de devolucions online. Retorna {importades, repetides, errors, avisos}."""
    mostra = text[:2048]
    separador = ";" if mostra.count(";") > mostra.count(",") else ","
    lector = csv.DictReader(io.StringIO(text), delimiter=separador)
    if lector.fieldnames is None:
        return {"importades": 0, "repetides": 0, "errors": ["El fitxer és buit"], "avisos": []}
    originals = [c.strip() for c in lector.fieldnames]
    noms = [ALIES.get(c.lower().replace(" ", "_"), c.lower().replace(" ", "_")) for c in originals]
    lector.fieldnames = noms
    avisos = []
    personals = [o for o, n in zip(originals, noms)
                 if n not in {"data", "gtin", "quantitat", "motiu", "comentari", "comanda"} and _PERSONALS.search(n)]
    if personals:
        avisos.append("S'han ignorat columnes que poden tenir dades personals (no les llegim ni les desem): "
                      + ", ".join(personals) + ". La propera vegada es poden treure del fitxer.")
    falten = {"data", "gtin"} - set(noms)
    if falten:
        return {"importades": 0, "repetides": 0, "errors": [f"Falten columnes: {', '.join(sorted(falten))}"],
                "avisos": avisos}
    if not {"motiu", "comentari"} & set(noms):
        return {"importades": 0, "repetides": 0, "errors": ["Cal una columna «motiu» o «comentari»"], "avisos": avisos}

    gtins = {r[0] for r in con.execute("SELECT gtin FROM catalog_sku")}
    importades, repetides, errors, vistes = 0, 0, [], Counter()
    sense_motiu = 0
    for num, fila in enumerate(lector, start=2):
        try:
            d = (fila.get("data") or "").strip()[:10]
            data = datetime.fromisoformat(d).date().isoformat() if "-" in d else \
                datetime.strptime(d, "%d/%m/%Y").date().isoformat()
            gtin = re.sub(r"\D", "", fila.get("gtin") or "").zfill(14)
            if gtin not in gtins:
                raise ValueError(f"GTIN que no és al catàleg ({(fila.get('gtin') or '').strip()!r})")
            q = (fila.get("quantitat") or "").strip()
            quantitat = abs(int(float(q.replace(",", ".")))) if q else 1
            if quantitat == 0:
                raise ValueError("quantitat 0")
            codi = neteja_codi(fila.get("motiu"))
            motiu_c, sentit_c = classifica(fila.get("comentari"))  # el comentari no es desa
            if not codi and not motiu_c:
                sense_motiu += 1
            comanda = (fila.get("comanda") or "").strip()
            clau = (comanda, gtin) if comanda else (data, gtin, codi, str(quantitat), motiu_c or "")
            vistes[clau] += 1
            ref = _ref(*clau, str(vistes[clau]))
            assegura_mapa(con, codi)
            cur = con.execute(
                """INSERT OR IGNORE INTO devolucio_online
                   (ref, data, gtin, quantitat, codi, motiu_comentari, sentit_comentari, lot_prova)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (ref, data, gtin, quantitat, codi, motiu_c, sentit_c, int(lot_prova)))
            if cur.rowcount:
                importades += 1
            else:
                repetides += 1
        except (ValueError, TypeError) as e:
            errors.append(f"Línia {num}: {e}")
    con.commit()
    if sense_motiu:
        avisos.append(f"{sense_motiu} línies no tenen motiu: compten com a «Altre».")
    return {"importades": importades, "repetides": repetides, "errors": errors, "avisos": avisos}


def esborra(con: sqlite3.Connection) -> int:
    """Esborra totes les devolucions importades per la marca (no les del lot de prova)."""
    n = con.execute("DELETE FROM devolucio_online WHERE lot_prova = 0").rowcount
    _neteja_mapa(con)
    con.commit()
    return n


def esborra_lot_prova(con: sqlite3.Connection) -> int:
    n = con.execute("DELETE FROM devolucio_online WHERE lot_prova = 1").rowcount
    _neteja_mapa(con)
    return n


def _neteja_mapa(con: sqlite3.Connection) -> None:
    """Treu del mapa els codis automàtics que ja no surten a cap devolució (els triats a mà es queden)."""
    con.execute("""DELETE FROM devolucio_mapa WHERE manual = 0
                   AND codi NOT IN (SELECT DISTINCT codi FROM devolucio_online)""")


# ---------------------------------------------------------------- Dades de prova


# Codis com els que fa servir una botiga en línia (en castellà, com és habitual a l'Estat).
_CODIS_PROVA = {
    "talla_petita": "TALLA PEQUEÑA", "talla_gran": "TALLA GRANDE", "tall": "NO ME FAVORECE",
    "color": "COLOR DIFERENTE", "qualitat": "CALIDAD", "preu": "PRECIO",
    "diferent_foto": "NO ES COMO EN LA FOTO", "defecte": "DEFECTUOSO", "enviament": "LLEGÓ TARDE",
    "canvi_opinio": "YA NO LO QUIERO",
}


def simula(con: sqlite3.Connection, des: date, fins: date, gtins: list[str], llavor: int = 9,
           lot_prova: bool = False) -> int:
    """Devolucions online inventades per a la demo i les proves: s'assemblen al provador en uns models
    i no en uns altres (perquè la comparativa tingui alguna cosa a dir)."""
    import random
    rng = random.Random(llavor)
    info = {r["gtin"]: dict(r) for r in con.execute("SELECT gtin, model, talla, categoria FROM catalog_sku")}
    models = sorted({info[g]["model"] for g in gtins if g in info})
    linies = ["data,gtin,quantitat,motiu,comentari,comanda"]
    dies = (fins - des).days + 1
    n = 0
    for i, m in enumerate(models):
        perfil = i % 4
        variants = [g for g in gtins if info.get(g, {}).get("model") == m]
        for k in range(rng.randint(8, 14) * max(1, round(dies / 7))):  # unes 8-14 per model i setmana
            g = rng.choice(variants)
            if perfil == 0:      # com al provador: talla, i va petita
                clau = rng.choices(["talla_petita", "talla_gran", "tall", "qualitat", "canvi_opinio"], [6, 1, 1, 1, 1])[0]
            elif perfil == 1:    # al provador diuen preu; online, la foto enganya
                clau = rng.choices(["diferent_foto", "color", "talla_gran", "preu", "canvi_opinio"], [5, 3, 1, 1, 1])[0]
            elif perfil == 2:    # qualitat als dos llocs
                clau = rng.choices(["qualitat", "talla_petita", "defecte", "canvi_opinio"], [5, 1, 2, 1])[0]
            else:                # online va gran
                clau = rng.choices(["talla_gran", "tall", "enviament", "canvi_opinio"], [5, 2, 1, 2])[0]
            dia = des + timedelta(days=rng.randrange(dies))
            linies.append(f"{dia.isoformat()},{g},1,{_CODIS_PROVA[clau]},,DEMO-{llavor}-{m}-{k}")
            n += 1
    importa_csv(con, "\n".join(linies), lot_prova=lot_prova)
    return n
