"""Resum del tauler (`GET /resum`) i l'acció principal que acompanya resum i informes.

KPI (només proves de confiança alta i mitjana):
  * conversió (insight 2) = compres atribuïdes ÷ proves;
  * venut sense provar (4) = unitats venudes − compres atribuïdes;
  * peces per sessió (12) = mitjana d'etiquetes diferents a les sessions amb alguna prova;
  * demanda perduda (7), peticions i temps de resposta (9, 10), peces abandonades (13);
  * taxa de resposta del motiu (8) = respostes ÷ sessions de fitxa.

Acció principal: UNA sola, la primera que es compleixi d'aquesta llista
  1. un model molt provat i poc venut (insight 3)             -> PROD
  2. una variant demanada >= 2 cops sense estoc (insight 7)   -> BOT
  3. una talla que no quadra (insight 6)                      -> PROD
  4. estoc parat (insight 14)                                 -> PROD
  5. risc de rebaixa (insight 15)                             -> CEO
  6. una prova en curs sense mostra suficient (insight 18)    -> MKT
  7. cap prova al període: revisar el lector                  -> BOT
"""

import sqlite3
from collections import defaultdict
from datetime import date, timedelta

from . import Filtre, base, inventari as estoc_mod, experimentacio as exp_mod, per_model as models_mod
from . import temps_real as alertes_mod, cabina as servei_mod, per_talla as talles_mod


def kpi(con: sqlite3.Connection, f: Filtre, proves: list | None = None) -> dict:
    proves = base.proves_valides(con, f) if proves is None else proves
    compres = sum(p["venuda"] for p in proves)
    conversio = base.frac(compres, len(proves))
    ant = base.proves_valides(con, base.anterior(f))
    conversio_ant = base.frac(sum(p["venuda"] for p in ant), len(ant))
    sess = base.sessions(con, f)
    per_sessio: dict[int, set] = defaultdict(set)
    for p in proves:
        per_sessio[p["sessio_id"]].add(p["epc"])
    unitats = sum(v["quantitat"] for v in base.vendes(con, f))
    sense_provar = max(unitats - compres, 0)
    pet = base.peticions(con, f)
    mediana, sota = servei_mod.temps_resposta(pet)
    respostes = len(base.nfc(con, f, "motiu_no_compra"))
    sessions_fitxa = len({e["sessio_nfc"] for e in base.nfc(con, f, "obre_fitxa")})
    return {
        "proves": len(proves), "compres_atribuides": compres, "conversio": conversio,
        "conversio_periode_anterior": conversio_ant, "variacio_conversio": base.resta(conversio, conversio_ant),
        "sessions": len(sess),
        "peces_per_sessio": base.frac(sum(len(s) for s in per_sessio.values()), len(per_sessio), 2),
        "unitats_venudes": unitats, "venut_sense_provar": sense_provar,
        "venut_sense_provar_pct": base.frac(sense_provar, unitats),
        "peticions_talla": len(pet), "temps_resposta_mediana_s": mediana, "pct_resposta_sota_90s": sota,
        "peces_abandonades": len(base.abandonades(con, f)),
        "demanda_perduda": sum(1 for p in pet if base.es_perduda(p)),
        "respostes_motiu": respostes, "taxa_resposta_motiu": base.frac(respostes, sessions_fitxa),
        "proves_ambigues": base.n_ambigues(con, f),
    }


def serie_diaria(con: sqlite3.Connection, f: Filtre, proves: list) -> list[dict]:
    grups = exp_mod.grup_origen_per_dia(con, f)
    per_dia: dict[str, list[int]] = {}
    d = f.des
    while d <= f.fins:
        per_dia[d.isoformat()] = [0, 0]
        d += timedelta(days=1)
    for p in proves:
        c = per_dia.setdefault(p["inici"][:10], [0, 0])
        c[0] += 1
        c[1] += p["venuda"]
    return [{"data": dia, "proves": n, "compres": c, "conversio": base.frac(c, n), "grup_origen": grups.get(dia)}
            for dia, (n, c) in sorted(per_dia.items())]


def resum(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /resum`."""
    proves = base.proves_valides(con, f)
    return {
        "periode": base.periode(f),
        "kpi": kpi(con, f, proves),
        "serie_diaria": serie_diaria(con, f, proves),
        "accio": accio_principal(con, f),
        "alertes_obertes": len(alertes_mod.alertes(con, f)["alertes"]),
    }


def accio_principal(con: sqlite3.Connection, f: Filtre, dies_limit: int = 7) -> dict | None:
    """L'acció més clara del període (vegeu l'ordre al principi del mòdul), o None si no n'hi ha cap."""
    limit: date = f.fins + timedelta(days=dies_limit)
    taula = models_mod.taula_models(con, f)

    marcats = [m for m in taula if m["molt_provat_poc_venut"]]
    if marcats:
        m = marcats[0]
        motiu = (f" El motiu més citat a la fitxa és «{base.MOTIUS.get(m['motiu_principal'], m['motiu_principal'])}»."
                 if m["motiu_principal"] else "")
        return base.accio(
            f"Revisar «{m['nom']}»: {m['proves']} proves i {m['compres']} compres ({base.pct_txt(m['conversio'])}), "
            f"molt per sota de la referència ({base.pct_txt(m['conversio_referencia'])}).{motiu} "
            f"Mirar preu, exposició o tall abans de rebaixar.",
            "molt_provat_poc_venut", m["model"], "PROD", limit)

    perduda = talles_mod.demanda_perduda(con, f)["per_variant"]
    if perduda and perduda[0]["n"] >= 2:
        v = perduda[0]
        return base.accio(
            f"Reposar «{v['nom']}» {v['color'] or ''} en talla {v['talla']}: s'ha demanat {v['n']} cops i no hi era.",
            "demanda_perduda", v["model"], "BOT", limit)

    t = talles_mod.talles(con, f)["no_quadra"]
    if t:
        return base.accio(f"Revisar el patró de la talla {t[0]['talla']} de «{t[0]['nom']}». {t[0]['text']}",
                          "talla_no_quadra", t[0]["model"], "PROD", limit)

    parat = estoc_mod.estoc_parat(con, f)
    if parat:
        p = parat[0]
        return base.accio(
            f"Traspassar «{p['nom']}» en {p['talla']} ({p['unitats']} u., {p['dies_sense_activitat']} dies sense "
            f"cap prova ni venda) a una altra botiga o al web abans de rebaixar-la.",
            "estoc_parat", p["model"], "PROD", limit)

    risc = estoc_mod.risc_rebaixa(con, f, taula)
    if risc:
        r = risc[0]
        cob = f"{base.num_txt(r['cobertura_setmanes'], 0)} setmanes" if r["cobertura_setmanes"] else "sense vendes"
        return base.accio(f"Decidir què fer amb «{r['nom']}» abans de rebaixes: {r['unitats']} u. ({cob} de cobertura).",
                          "risc_rebaixa", r["model"], "CEO", limit)

    for e in exp_mod.experiments(con, f)["experiments"]:
        if e["estat"] == "actiu" and not e["mostra_suficient"]:
            return base.accio(f"Mantenir la prova «{e['id']}» fins al {e['fi']} sense canviar res: encara no hi ha "
                              f"prou proves per grup ({e['proves_minimes']}).",
                              "experiment", None, "MKT", limit)

    if not taula:
        return base.accio("Comprovar que el lector i les vendes arriben: no hi ha cap prova al període.",
                          "qualitat_dada", None, "BOT", f.fins + timedelta(days=1))
    return None
