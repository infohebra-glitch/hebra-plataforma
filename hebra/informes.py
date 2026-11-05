"""Informe setmanal «provat, venut, convertit» (Proposta MVP, secció 5.2 C).

Retorna un diccionari amb les dades; la plantilla informe.html el pinta.
Regles que l'informe declara sempre:
  * només compten les proves de confiança alta i mitjana;
  * l'efecte de l'origen només es dona com a resultat si cada grup té una mostra
    mínima; si no, es diu "mostra insuficient" (no prometem percentatges);
  * "venut sense provar" són unitats venudes que no s'han aparellat amb cap prova.
"""

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta

PROVES_MINIMES_PER_GRUP = 30      # proposta; es recalcula amb les dades de les setmanes 2-3
PROVES_MINIMES_ALERTA = 5         # per marcar un model com a "molt provat, poc venut"
FACTOR_ALERTA = 0.6               # ... si converteix menys del 60 % de la mitjana de la botiga

MOTIUS = {
    "talla": "Talla",
    "tall": "Tall o forma",
    "preu": "Preu",
    "color": "Color",
    "qualitat": "Qualitat o teixit",
    "altre": "Altre",
}


def _conv(compres: int, proves: int) -> float | None:
    return round(compres / proves, 3) if proves else None


def setmanal(con: sqlite3.Connection, botiga_id: str, dilluns: date) -> dict:
    inici = dilluns.isoformat()
    fi = (dilluns + timedelta(days=7)).isoformat()

    proves = con.execute(
        """SELECT p.id, p.gtin, p.confianca, s.grup, s.inici,
                  k.model, k.color, k.talla, k.categoria, k.origen_json,
                  (a.venda_id IS NOT NULL) AS venuda
           FROM prova p
           JOIN sessio s ON s.id = p.sessio_id
           JOIN cabina c ON c.id = s.cabina_id
           LEFT JOIN catalog_sku k ON k.gtin = p.gtin
           LEFT JOIN atribucio a ON a.prova_id = p.id
           WHERE c.botiga_id = ? AND s.inici >= ? AND s.inici < ?""",
        (botiga_id, inici, fi)).fetchall()
    valides = [p for p in proves if p["confianca"] in ("alta", "mitjana")]

    unitats_venudes = con.execute(
        """SELECT COALESCE(SUM(quantitat), 0) FROM venda_linia
           WHERE botiga_id = ? AND data >= ? AND data < ? AND quantitat > 0""",
        (botiga_id, inici, fi[:10])).fetchone()[0]
    atribuides = sum(1 for p in valides if p["venuda"])

    # ---- Per categoria i talla
    per_cat_talla: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    for p in valides:
        clau = (p["categoria"] or "sense catàleg", p["talla"] or "?")
        per_cat_talla[clau][0] += 1
        per_cat_talla[clau][1] += p["venuda"]
    # Ordre natural de talles: lletres de petita a gran, i números de menor a major.
    lletres = ["XXS", "XS", "S", "M", "L", "XL", "XXL"]

    def ordre_talla(t: str) -> tuple:
        return (0, lletres.index(t), 0) if t in lletres else (1, 0, float(t)) if t.replace(".", "").isdigit() else (2, 0, 0)

    taula_cat_talla = [
        {"categoria": c, "talla": t, "proves": n, "compres": v, "conversio": _conv(v, n)}
        for (c, t), (n, v) in sorted(per_cat_talla.items(), key=lambda kv: (kv[0][0], ordre_talla(kv[0][1])))
    ]

    # ---- Per model: molt provat, poc venut
    conv_botiga = _conv(atribuides, len(valides)) or 0
    per_model: dict[str, list] = defaultdict(lambda: [0, 0, None])
    for p in valides:
        m = per_model[p["model"] or p["gtin"] or "?"]
        m[0] += 1
        m[1] += p["venuda"]
        if p["origen_json"] and m[2] is None:
            m[2] = json.loads(p["origen_json"])["nom"]["ca"]
    models = []
    for model, (n, v, nom) in sorted(per_model.items(), key=lambda kv: -kv[1][0]):
        conv = _conv(v, n)
        alerta = n >= PROVES_MINIMES_ALERTA and conv is not None and conv < conv_botiga * FACTOR_ALERTA
        models.append({"model": model, "nom": nom or model, "proves": n, "compres": v,
                       "conversio": conv, "alerta": alerta})

    # ---- Efecte de l'origen (grup de control per dies)
    grups = {}
    for g in ("amb", "sense"):
        del_grup = [p for p in valides if p["grup"] == g]
        n, v = len(del_grup), sum(p["venuda"] for p in del_grup)
        grups[g] = {"proves": n, "compres": v, "conversio": _conv(v, n)}
    hi_ha_mostra = all(grups[g]["proves"] >= PROVES_MINIMES_PER_GRUP for g in grups)
    diferencia = None
    if hi_ha_mostra:
        diferencia = round(grups["amb"]["conversio"] - grups["sense"]["conversio"], 3)

    # ---- Demanda perduda i motius de no compra (de la fitxa NFC)
    perdudes = con.execute(
        """SELECT k.model, k.color, pt.talla_demanada, COUNT(*) AS n
           FROM peticio_talla pt JOIN catalog_sku k ON k.gtin = pt.gtin_origen
           WHERE pt.botiga_id = ? AND pt.hora_peticio >= ? AND pt.hora_peticio < ?
             AND (pt.estat = 'no_disponible' OR pt.disponible = 0)
           GROUP BY k.model, k.color, pt.talla_demanada ORDER BY n DESC""",
        (botiga_id, inici, fi)).fetchall()
    motius = Counter(
        f["valor"] for f in con.execute(
            """SELECT valor FROM esdeveniment_nfc
               WHERE botiga_id = ? AND tipus = 'motiu_no_compra' AND ts >= ? AND ts < ?""",
            (botiga_id, inici, fi)))
    peticions = con.execute(
        """SELECT COUNT(*) AS n,
                  AVG(CASE WHEN hora_resolta IS NOT NULL
                      THEN (julianday(hora_resolta) - julianday(hora_peticio)) * 86400 END) AS segons
           FROM peticio_talla WHERE botiga_id = ? AND hora_peticio >= ? AND hora_peticio < ?""",
        (botiga_id, inici, fi)).fetchone()

    # ---- Acció de la setmana: una sola, la més clara
    accio = None
    alertes = [m for m in models if m["alerta"]]
    if alertes:
        m = alertes[0]
        motiu_top = Counter(f["valor"] for f in con.execute(
            """SELECT e.valor FROM esdeveniment_nfc e JOIN catalog_sku k ON k.gtin = e.gtin
               WHERE e.botiga_id = ? AND e.tipus = 'motiu_no_compra' AND e.ts >= ? AND e.ts < ? AND k.model = ?""",
            (botiga_id, inici, fi, m["model"]))).most_common(1)
        per_que = f" El motiu més citat a la seva fitxa és «{MOTIUS.get(motiu_top[0][0], motiu_top[0][0])}»." if motiu_top else ""
        accio = (f"Revisar «{m['nom']}»: {m['proves']} proves i {m['compres']} compres aquesta setmana, "
                 f"molt per sota de la conversió mitjana de la botiga.{per_que}")
    elif perdudes:
        p = perdudes[0]
        accio = f"Reposar {p['model']} {p['color']} en talla {p['talla_demanada']}: s'ha demanat {p['n']} cops i no hi era."

    return {
        "botiga_id": botiga_id,
        "inici": inici,
        "fi": (dilluns + timedelta(days=6)).isoformat(),
        "totals": {
            "proves": len(valides),
            "ambigues": len(proves) - len(valides),
            "compres_atribuides": atribuides,
            "conversio": _conv(atribuides, len(valides)),
            "unitats_venudes": unitats_venudes,
            "venut_sense_provar": max(unitats_venudes - atribuides, 0),
        },
        "per_categoria_talla": taula_cat_talla,
        "models": models,
        "origen": {"grups": grups, "hi_ha_mostra": hi_ha_mostra, "diferencia": diferencia,
                   "minim": PROVES_MINIMES_PER_GRUP},
        "demanda_perduda": [dict(p) for p in perdudes],
        "motius": [{"motiu": MOTIUS.get(k, k), "n": n} for k, n in motius.most_common()],
        "peticions": {"n": peticions["n"], "segons_mitjans": round(peticions["segons"]) if peticions["segons"] else None},
        "accio": accio,
    }
