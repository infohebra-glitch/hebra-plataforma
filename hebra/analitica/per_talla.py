"""Talles: conversió per talla, talla que no quadra, corba proposada i demanda perduda (insights 5, 6, 7).

Talla que no quadra (insight 6): una talla d'un model amb >= 10 proves que
converteix menys de la meitat que la resta de talles del mateix model (que també
han de sumar >= 10 proves), i almenys 10 punts per sota.

Corba proposada (insight 5): per a cada talla, 0,7 × % de compres + 0,3 × % de
proves, arrodonit a 5 punts. Si el model no té cap compra, només el % de proves.
Només models amb >= 10 proves al període.
"""

import sqlite3
from collections import Counter, defaultdict

from . import Filtre, base

PROVES_MINIMES_TALLA = 10
FACTOR_NO_QUADRA = 0.5
DIFERENCIA_MINIMA_NO_QUADRA = 0.10
PES_COMPRES = 0.7


def _per_model_talla(proves) -> dict[str, dict[str, list[int]]]:
    out: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for p in proves:
        if p["model"]:
            out[p["model"]][p["talla"]][0] += 1
            out[p["model"]][p["talla"]][1] += p["venuda"]
    return out


def taula_categoria_talla(proves) -> list[dict]:
    per: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    for p in proves:
        clau = (p["categoria"] or "sense catàleg", p["talla"] or "?")
        per[clau][0] += 1
        per[clau][1] += p["venuda"]
    return [{"categoria": c, "talla": t, "proves": n, "compres": v, "conversio": base.frac(v, n)}
            for (c, t), (n, v) in sorted(per.items(), key=lambda kv: (kv[0][0], base.ordre_talla(kv[0][1])))]


def no_quadra(per_model: dict, info: dict) -> list[dict]:
    """Insight 6: talles que es proven i no es venen comparades amb la resta del mateix model."""
    out = []
    for model, talles in per_model.items():
        total_n = sum(n for n, _ in talles.values())
        total_c = sum(c for _, c in talles.values())
        for talla, (n, c) in talles.items():
            resta_n, resta_c = total_n - n, total_c - c
            if n < PROVES_MINIMES_TALLA or resta_n < PROVES_MINIMES_TALLA:
                continue
            conv, conv_resta = c / n, resta_c / resta_n
            if conv < FACTOR_NO_QUADRA * conv_resta and conv_resta - conv >= DIFERENCIA_MINIMA_NO_QUADRA:
                nom = base.nom_model(info, model)
                ven = (f"no s'ha venut cap cop en {n} proves" if c == 0
                       else f"es ven a {base.un_de_cada(conv)} proves")
                out.append({
                    "model": model, "nom": nom, "talla": talla,
                    "conversio": round(conv, 3), "conversio_resta_talles": round(conv_resta, 3),
                    "text": (f"«{nom}» en {talla} {ven}; la resta de talles, a {base.un_de_cada(conv_resta)}. "
                             f"Pot ser el patró de la {talla}."),
                })
    out.sort(key=lambda r: r["conversio"] - r["conversio_resta_talles"])
    return out


def corba(per_model: dict, info: dict, estoc: dict[str, int], con: sqlite3.Connection) -> list[dict]:
    """Insight 5: % de proves, de compres i d'estoc per talla, i la corba proposada."""
    out = []
    for model in sorted(per_model, key=lambda m: -sum(n for n, _ in per_model[m].values())):
        talles = per_model[model]
        total_n = sum(n for n, _ in talles.values())
        total_c = sum(c for _, c in talles.values())
        if total_n < PROVES_MINIMES_TALLA:
            continue
        estoc_talla: dict[str, int] = defaultdict(int)
        coneguda = False
        totes = set(talles)
        for v in con.execute("SELECT gtin, talla FROM catalog_sku WHERE model = ?", (model,)):
            totes.add(v["talla"])
            if v["gtin"] in estoc:
                coneguda = True
                estoc_talla[v["talla"]] += estoc[v["gtin"]]
        total_e = sum(estoc_talla.values())
        files = []
        for t in sorted(totes, key=base.ordre_talla):
            n, c = talles.get(t, (0, 0))
            pp, pc = n / total_n, (c / total_c if total_c else None)
            proposta = PES_COMPRES * pc + (1 - PES_COMPRES) * pp if pc is not None else pp
            files.append({"talla": t, "pct_proves": round(pp, 3),
                          "pct_compres": round(pc, 3) if pc is not None else None,
                          "pct_estoc": base.frac(estoc_talla[t], total_e) if coneguda else None,
                          "proposta_pct": base.arrodoneix_5_punts(proposta)})
        out.append({"model": model, "nom": base.nom_model(info, model), "talles": files})
    return out


def talles(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /talles`: taula categoria × talla, talles que no quadren i corba proposada."""
    proves = base.proves_valides(con, f)
    info = base.info_models(con)
    per_model = _per_model_talla(proves)
    return {
        "taula": taula_categoria_talla(proves),
        "no_quadra": no_quadra(per_model, info),
        "corba": corba(per_model, info, base.estoc_per_gtin(con, f.botiga_id), con),
    }


def demanda_perduda(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /demanda-perduda` (insight 7): peticions de talla que no hi eren, per variant demanada."""
    info = base.info_models(con)
    estoc = base.estoc_per_gtin(con, f.botiga_id)
    perdudes = [p for p in base.peticions(con, f) if base.es_perduda(p)]
    per: Counter = Counter(p["gtin_demanat"] for p in perdudes)
    dades = {p["gtin_demanat"]: p for p in perdudes}
    files = [{"model": dades[g]["model"], "nom": base.nom_model(info, dades[g]["model"]),
              "color": dades[g]["color"], "talla": dades[g]["talla_demanada"], "n": n, "estoc": estoc.get(g)}
             for g, n in sorted(per.items(), key=lambda kv: (-kv[1], kv[0]))]
    total = len(perdudes)
    if not total:
        text = "Cap petició de talla sense estoc al període."
    else:
        top = files[0]
        text = (f"{base.plural(total, 'petició', 'peticions')} de talles que no hi eren; "
                f"{top['n']} {'era' if top['n'] == 1 else 'eren'} «{top['nom']}» en {top['talla']}.")
    return {"total": total, "per_variant": files, "text": text}
