"""Models: proves, conversió i «molt provat, poc venut» (insights 1, 2, 3, 4, 6, 8).

Regla «molt provat, poc venut» (insight 3):
  proves >= N al període, on N = `n_molt_provat` (10) × setmanes del període
  (mínim una setmana), i conversió baixa respecte del seu grup de referència.

Grup de referència i «conversió baixa»:
  * si la categoria té 4 o més models amb proves: la categoria, i conversió baixa
    vol dir quartil inferior (quartil 1);
  * si en té menys: tots els models del filtre, i conversió baixa vol dir per
    sota del 60 % de la conversió conjunta d'aquests models (com l'informe antic).
  `quartil_categoria` és el quartil dins del grup de referència quan aquest té
  4 o més models; si no, és None (amb menys de 4 models un quartil no diu res).
"""

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import timedelta

from . import Filtre, base

FACTOR_CONVERSIO_BAIXA = 0.6
MODELS_MINIMS_QUARTIL = 4


def taula_models(con: sqlite3.Connection, f: Filtre, proves: list | None = None) -> list[dict]:
    """Una fila per model amb proves o vendes al període (forma de `GET /models`), més dues claus
    internes: `conversio_baixa` i `conversio_referencia` (la del grup de referència)."""
    proves = base.proves_valides(con, f) if proves is None else proves
    info = base.info_models(con)
    estoc = base.estoc_per_gtin(con, f.botiga_id)

    comptes: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for p in proves:
        if p["model"]:
            comptes[p["model"]][0] += 1
            comptes[p["model"]][1] += p["venuda"]
    venudes: Counter = Counter()
    for v in base.vendes(con, f):
        if v["model"]:
            venudes[v["model"]] += v["quantitat"]
    motius: dict[str, Counter] = defaultdict(Counter)
    for e in base.nfc(con, f, "motiu_no_compra"):
        if e["model"]:
            motius[e["model"]][e["valor"]] += 1
    perduda: Counter = Counter(p["model"] for p in base.peticions(con, f) if base.es_perduda(p) and p["model"])

    # Conversió per categoria i grup de referència
    per_cat: dict[str, list[str]] = defaultdict(list)
    for m in comptes:
        per_cat[info.get(m, {}).get("categoria") or "?"].append(m)

    def conv(ms: list[str]) -> float | None:
        return base.frac(sum(comptes[m][1] for m in ms), sum(comptes[m][0] for m in ms))

    conv_tots = conv(list(comptes))
    quartil_tots = base.quartils({m: comptes[m][1] / comptes[m][0] for m in comptes}) \
        if len(comptes) >= MODELS_MINIMS_QUARTIL else {}
    n_min = base.par(con, f, "n_molt_provat") * max(1.0, base.setmanes(f))

    files = []
    for m in set(comptes) | set(venudes):
        i = info.get(m, {"nom": m, "categoria": None, "preu": None, "gtins": []})
        n, c = comptes[m] if m in comptes else (0, 0)
        cat = i["categoria"] or "?"
        germans = per_cat.get(cat, [])
        conversio = base.frac(c, n)
        if len(germans) >= MODELS_MINIMS_QUARTIL:
            quartil = base.quartils({g: comptes[g][1] / comptes[g][0] for g in germans}).get(m)
            baixa = quartil == 1
            referencia = conv(germans)
        else:
            referencia = conv_tots
            quartil = quartil_tots.get(m)
            baixa = conversio is not None and conv_tots is not None and conversio < FACTOR_CONVERSIO_BAIXA * conv_tots
        motiu = motius[m].most_common(1)
        files.append({
            "model": m, "nom": i["nom"], "categoria": i["categoria"], "preu": i["preu"],
            "proves": n, "compres": c, "conversio": conversio,
            "conversio_categoria": conv(germans) if germans else None,
            "quartil_categoria": quartil if n else None,
            "molt_provat_poc_venut": bool(n >= n_min and baixa),
            "venut_sense_provar": max(venudes[m] - c, 0),
            "estoc": base.estoc_de(estoc, i["gtins"]),
            "motiu_principal": motiu[0][0] if motiu else None,
            "demanda_perduda": perduda[m],
            "conversio_baixa": bool(n and baixa),
            "conversio_referencia": referencia,
        })
    files.sort(key=lambda r: (-r["proves"], r["model"]))
    return files


def models(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /models`: tots els models amb proves o vendes, dels més provats als menys."""
    files = taula_models(con, f)
    for r in files:
        r.pop("conversio_baixa")
        r.pop("conversio_referencia")
    return {"models": files}


def molt_provat_poc_venut(con: sqlite3.Connection, f: Filtre) -> list[dict]:
    """Els models marcats per l'insight 3, dels més provats als menys."""
    return [r for r in taula_models(con, f) if r["molt_provat_poc_venut"]]


def model_detall(con: sqlite3.Connection, f: Filtre, model: str) -> dict | None:
    """`GET /models/{model}`: el detall d'un model. None si el model no és al catàleg (l'API respon 404).

    `canvis_de_talla` d'una talla: peticions de talla fetes amb aquesta talla a la mà (gtin_origen).
    `provat_amb`: altres models provats a la mateixa sessió de cabina (sessions diferents).
    `dubte_talla` (v0.3): sessions on s'ha provat en dues talles o més (hebra/analitica/sessions.py).
    """
    from . import experimentacio as experiments  # evita la importació circular
    from .sessions import dubte_talla_model

    info = base.info_models(con).get(model)
    if info is None:
        return None
    variants = con.execute("SELECT * FROM catalog_sku WHERE model = ? ORDER BY rowid", (model,)).fetchall()
    variants = sorted(variants, key=lambda v: (v["color"], base.ordre_talla(v["talla"])))
    estoc = base.estoc_per_gtin(con, f.botiga_id)

    totes = base.proves_valides(con, f)
    proves = [p for p in totes if p["model"] == model]
    n, c = len(proves), sum(p["venuda"] for p in proves)
    venudes = sum(v["quantitat"] for v in base.vendes(con, f) if v["model"] == model)
    motius = Counter(e["valor"] for e in base.nfc(con, f, "motiu_no_compra") if e["model"] == model)
    sessions_fitxa = len({e["sessio_nfc"] for e in base.nfc(con, f, "obre_fitxa") if e["model"] == model})
    peticions = base.peticions(con, f)

    per_gtin: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for p in proves:
        per_gtin[p["gtin"]][0] += 1
        per_gtin[p["gtin"]][1] += p["venuda"]
    perduda = Counter(p["gtin_demanat"] for p in peticions if base.es_perduda(p))
    canvis = Counter(p["gtin_origen"] for p in peticions)
    talles = [{
        "talla": v["talla"], "gtin": v["gtin"],
        "proves": per_gtin[v["gtin"]][0], "compres": per_gtin[v["gtin"]][1],
        "conversio": base.frac(per_gtin[v["gtin"]][1], per_gtin[v["gtin"]][0]),
        "pct_proves": base.frac(per_gtin[v["gtin"]][0], n),
        "pct_compres": base.frac(per_gtin[v["gtin"]][1], c),
        "estoc": estoc.get(v["gtin"]),
        "demanda_perduda": perduda[v["gtin"]],
        "canvis_de_talla": canvis[v["gtin"]],
    } for v in variants]

    total_motius = sum(motius.values())
    serie: dict[str, list[int]] = {}
    d = base.dilluns(f.des)
    while d <= f.fins:
        serie[d.isoformat()] = [0, 0]
        d += timedelta(days=7)
    for p in proves:
        s = serie.setdefault(base.dilluns(base.dt(p["inici"]).date()).isoformat(), [0, 0])
        s[0] += 1
        s[1] += p["venuda"]

    sessions_model = {p["sessio_id"] for p in proves}
    amb: dict[str, set] = defaultdict(set)
    for p in totes:
        if p["sessio_id"] in sessions_model and p["model"] and p["model"] != model:
            amb[p["model"]].add(p["sessio_id"])
    tots_info = base.info_models(con)

    return {
        "model": model, "nom": info["nom"], "categoria": info["categoria"], "color": info["color"],
        "preu": info["preu"],
        "kpi": {"proves": n, "compres": c, "conversio": base.frac(c, n),
                "venut_sense_provar": max(venudes - c, 0),
                "respostes_motiu": total_motius, "taxa_resposta_motiu": base.frac(total_motius, sessions_fitxa)},
        "talles": talles,
        "motius": [{"motiu": k, "n": v, "pct": base.frac(v, total_motius)} for k, v in motius.most_common()],
        "serie_setmanal": [{"setmana": s, "proves": a, "compres": b, "conversio": base.frac(b, a)}
                           for s, (a, b) in sorted(serie.items())],
        "provat_amb": [{"model": m, "nom": base.nom_model(tots_info, m), "sessions": len(s)}
                       for m, s in sorted(amb.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:5]],
        "origen": origen_resum(info["origen"]),
        "efecte_origen": experiments.efecte_origen(con, f, model),
        "dubte_talla": dubte_talla_model(con, f, model),
    }


def origen_resum(origen: dict | None) -> dict | None:
    """Etapes i composició de la fitxa d'origen (en català), o None si el model no en té."""
    if not origen:
        return None

    def ca(v):
        return v.get("ca") or next(iter(v.values()), "") if isinstance(v, dict) else v

    return {
        "etapes": [{"etapa": e.get("etapa"), "pais": e.get("pais"), "regio": ca(e.get("regio", ""))}
                   for e in origen.get("etapes", [])],
        "composicio": [{"material": ca(c.get("material")), "pct": (c["pct"] / 100 if c.get("pct") is not None else None), "pais": c.get("pais")}
                       for c in origen.get("composicio", [])],
    }


def pais_confeccio(origen_json: str | dict | None) -> str | None:
    """País de l'etapa de confecció de la fitxa d'origen (per a l'informe de temporada)."""
    origen = json.loads(origen_json) if isinstance(origen_json, str) else origen_json
    for e in (origen or {}).get("etapes", []):
        if e.get("etapa") == "confeccio":
            return e.get("pais")
    return None
