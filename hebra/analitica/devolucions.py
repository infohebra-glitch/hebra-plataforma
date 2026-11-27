"""Provador i online: el motiu de no compra al provador comparat amb el motiu de devolució online (v0.9).

Sempre en agregat, per model i talla (mai per persona; vegeu hebra/devolucions.py).

  * Provador: respostes `motiu_no_compra` de la fitxa NFC (respecten el filtre de botiga).
    «Només mirava» no entra a la comparació (online no té sentit).
  * Online: unitats tornades al període (data de la devolució), de tota la marca: la botiga en línia
    no és cap botiga física, així que el filtre de botiga no hi aplica.
  * Comparables: les categories que existeixen als dos llocs. Les que només tenen sentit online
    («no era com a la foto», defecte, enviament, canvi d'opinió) es compten a part.

Coincidència = Σ min(p_provador, p_online) sobre les categories comparables, cada distribució
normalitzada sobre les seves respostes comparables. 100 % = el mateix repartiment de motius; 0 % = cap
motiu en comú. Només es calcula amb `MIN_COMPARAR` respostes o més a cada costat.

Sentit de la talla:
  * online: «massa petita» / «massa gran» quan el motiu ho diu;
  * provador: peticions de talla des de la fitxa cap a una talla més gran (la provada anava petita)
    o més petita (anava gran).
"""

import sqlite3
from collections import Counter, defaultdict

from hebra import devolucions as dev

from . import Filtre, base

MIN_COMPARAR = dev.MIN_COMPARAR
DIVERGENT = 0.5


def _dist(c: Counter, claus: set[str]) -> dict[str, float]:
    n = sum(c[k] for k in claus)
    return {k: c[k] / n for k in claus} if n else {}


def coincidencia(prov: Counter, onl: Counter, comparables: set[str]) -> float | None:
    np_ = sum(prov[k] for k in comparables)
    no = sum(onl[k] for k in comparables)
    if np_ < MIN_COMPARAR or no < MIN_COMPARAR:
        return None
    p, q = _dist(prov, comparables), _dist(onl, comparables)
    return round(sum(min(p[k], q[k]) for k in comparables), 3)


def _sentit_provador(con: sqlite3.Connection, f: Filtre) -> dict[str, Counter]:
    """{model: Counter(petita=…, gran=…)} a partir de les peticions de talla de la fitxa."""
    talla = {r["gtin"]: (r["model"], r["talla"]) for r in con.execute("SELECT gtin, model, talla FROM catalog_sku")}
    out: dict[str, Counter] = defaultdict(Counter)
    for p in base.peticions(con, f):
        a, b = talla.get(p["gtin_origen"]), talla.get(p["gtin_demanat"])
        if not a or not b or a[0] != b[0]:
            continue
        oa, ob = base.ordre_talla(a[1]), base.ordre_talla(b[1])
        if ob > oa:
            out[a[0]]["petita"] += 1      # en demana una de més gran: la provada li anava petita
        elif ob < oa:
            out[a[0]]["gran"] += 1
    return out


def _principal(c: Counter, claus: set[str]) -> str | None:
    millor = [(n, k) for k, n in c.items() if k in claus and n]
    return max(millor)[1] if millor else None


def _lectura(nom_p: str | None, nom_o: str | None, coin: float | None, sentit_o: Counter) -> str:
    if coin is None:
        return "Encara poques respostes per comparar-ho."
    if coin >= 0.7:
        base_txt = f"Coincideix: als dos llocs el motiu principal és «{nom_o}»." if nom_p == nom_o else \
            "Coincideix bastant: el repartiment de motius s'assembla."
    elif coin >= DIVERGENT:
        base_txt = (f"Coincideix a mitges: als dos llocs sobretot «{nom_p}»." if nom_p == nom_o else
                    f"Coincideix a mitges: al provador sobretot «{nom_p}», online «{nom_o}».")
    elif nom_p == nom_o:
        base_txt = (f"Coincideix poc: el motiu principal és «{nom_p}» als dos llocs, però la resta de motius "
                    "es reparteix molt diferent.")
    else:
        base_txt = f"No coincideix: al provador diuen «{nom_p}» i online «{nom_o}». El problema online pot ser un altre."
    if sentit_o["petita"] + sentit_o["gran"] >= 3:
        sentit = "petita" if sentit_o["petita"] >= sentit_o["gran"] else "gran"
        base_txt += f" Online, quan és la talla, va massa {sentit}."
    return base_txt


def provador_online(con: sqlite3.Connection, f: Filtre, model: str | None = None) -> dict:
    """`GET /provador-online`: motius del provador i de les devolucions online, en conjunt i per model."""
    info = base.info_models(con)
    noms = dev.categories(con)
    respostes = [e for e in base.nfc(con, f, "motiu_no_compra") if e["valor"] != "nomes_mirava"]
    retorns = dev.files(con, f.inici_iso, f.fi_exclusiu_iso)
    if model is not None:
        respostes = [e for e in respostes if e["model"] == model]
        retorns = [r for r in retorns if r["model"] == model]
    comparables = set(noms) - set(dev.NOMES_ONLINE)

    prov, onl = Counter(), Counter()
    per_model_p: dict[str, Counter] = defaultdict(Counter)
    per_model_o: dict[str, Counter] = defaultdict(Counter)
    sentit_o: dict[str, Counter] = defaultdict(Counter)
    per_talla: dict[tuple, Counter] = defaultdict(Counter)
    for e in respostes:
        prov[e["valor"]] += 1
        per_model_p[e["model"] or e["gtin"]][e["valor"]] += 1
    for r in retorns:
        q = r["quantitat"]
        onl[r["motiu"]] += q
        m = r["model"] or r["gtin"]
        per_model_o[m][r["motiu"]] += q
        if r["sentit"]:
            sentit_o[m][r["sentit"]] += q
            sentit_o["*"][r["sentit"]] += q
        if r["motiu"] == "talla":
            per_talla[(m, r["talla"])][r["sentit"] or "sense"] += q
    sentit_p = _sentit_provador(con, f)
    if model is not None:
        sentit_p = {model: sentit_p.get(model, Counter())}
    sentit_p_total = sum(sentit_p.values(), Counter())

    n_prov = sum(prov[k] for k in comparables)
    n_onl_comp = sum(onl[k] for k in comparables)
    n_onl = sum(onl.values())
    claus = sorted({k for k in prov | onl if k in comparables},
                   key=lambda k: -(base.frac(prov[k], n_prov) or 0) - (base.frac(onl[k], n_onl_comp) or 0))
    coin = coincidencia(prov, onl, comparables)

    models = []
    for m in sorted(set(per_model_p) | set(per_model_o)):
        cp, co = per_model_p[m], per_model_o[m]
        c = coincidencia(cp, co, comparables)
        pp, po = _principal(cp, comparables), _principal(co, set(noms))
        models.append({
            "model": m, "nom": base.nom_model(info, m),
            "respostes_provador": sum(cp.values()), "devolucions_online": sum(co.values()),
            "motiu_provador": pp, "motiu_online": po,
            "provador": dict(cp), "online": dict(co),
            "nomes_online": sum(co[k] for k in dev.NOMES_ONLINE),
            "coincidencia": c, "divergent": c is not None and c < DIVERGENT,
            "talla_online": {"petita": sentit_o[m]["petita"], "gran": sentit_o[m]["gran"]},
            "talla_provador": {"petita": sentit_p.get(m, Counter())["petita"], "gran": sentit_p.get(m, Counter())["gran"]},
            "lectura": _lectura(noms.get(pp), noms.get(_principal(co, comparables)), c, sentit_o[m]),
        })
    models.sort(key=lambda x: (x["coincidencia"] is None, x["coincidencia"] if x["coincidencia"] is not None else 0,
                               -(x["respostes_provador"] + x["devolucions_online"])))

    talles = [{"model": m, "nom": base.nom_model(info, m), "talla": t,
               "petita": c["petita"], "gran": c["gran"], "sense": c["sense"]}
              for (m, t), c in sorted(per_talla.items(), key=lambda kv: (kv[0][0], base.ordre_talla(kv[0][1])))]

    divergents = [x for x in models if x["divergent"]]
    if not retorns:
        text = "Encara no hi ha devolucions online en aquest període. Puja el fitxer de devolucions a Connexions i dades."
    elif coin is None:
        text = (f"{base.plural(n_onl, 'unitat tornada', 'unitats tornades')} online i "
                f"{base.plural(n_prov, 'resposta', 'respostes')} al provador: encara poques per comparar.")
    else:
        text = (f"Els motius del provador i els de les devolucions online coincideixen en un {base.pct_txt(coin)}. "
                + (f"{base.plural(len(divergents), 'model no coincideix', 'models no coincideixen')}: "
                   f"{', '.join(x['nom'] for x in divergents[:3])}." if divergents else "Cap model amb motius molt diferents."))

    return {
        "periode": base.periode(f),
        "respostes_provador": n_prov, "devolucions_online": n_onl,
        "nomes_online": n_onl - n_onl_comp, "pct_nomes_online": base.frac(n_onl - n_onl_comp, n_onl),
        "coincidencia": coin,
        "categories": [{"motiu": k, "nom": noms.get(k, k),
                        "provador": prov[k], "pct_provador": base.frac(prov[k], n_prov),
                        "online": onl[k], "pct_online": base.frac(onl[k], n_onl_comp)} for k in claus],
        "nomes_online_detall": [{"motiu": k, "nom": v, "online": onl[k], "pct": base.frac(onl[k], n_onl)}
                                for k, v in dev.NOMES_ONLINE.items() if onl[k]],
        "talla_sentit": {"online": {"petita": sentit_o["*"]["petita"], "gran": sentit_o["*"]["gran"]},
                         "provador": {"petita": sentit_p_total["petita"], "gran": sentit_p_total["gran"]}},
        "models": models, "talles": talles,
        "etiquetes": noms, "minim": MIN_COMPARAR,
        "text": text, "importat": dev.resum(con),
    }
