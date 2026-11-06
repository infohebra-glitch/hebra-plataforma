"""Xifres, gràfics i blocs nous dels informes (v0.3, docs/ESPECIFICACIO-v3.md, E.2).

`enriqueix` afegeix a l'informe de `informes.informe` (sense treure'n res):

  * `xifres`:  [{"etiqueta", "valor", "unitat", "variacio", "vs"}]
  * `grafics`: [{"id", "titol", "tipus", "unitat", "eix_x", "series": [{"nom", "valors"}], "nota"}]
  * alguns blocs nous (p. ex. les cinc línies del diari o el dubte de talla de la temporada).

El frontend i el PDF (hebra/grafics_svg.py) dibuixen els mateixos gràfics.

Variació d'una xifra: si la unitat és `pct`, és la DIFERÈNCIA en fracció (0,03 = +3 punts);
per a la resta (`enter`, `eur`, `segons`) és el canvi RELATIU ((ara − abans) ÷ abans).
`None` si no hi ha amb què comparar.

Demanda perduda en euros (estimació): Σ PVP de les variants demanades que no hi eren ×
conversió del període (la probabilitat que s'haguessin comprat si hi haguessin estat).
"""

import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta

from . import Filtre, base, experimentacio as exp_mod, inventari as estoc_mod, per_model as models_mod
from . import cabina as servei_mod, nfc as nfc_mod, palanques as valor_mod, per_talla as talles_mod
from . import tauler as resum_mod

DIES = ("dl", "dt", "dc", "dj", "dv", "ds", "dg")
PROVES_MINIMES_MODEL = 5      # per entrar als rànquings de models per conversió
PROVES_MINIMES_CATEGORIA = 20  # per dibuixar la corba de talles d'una categoria
DIES_ABANS_DECISIO = 14


# ---------------------------------------------------------------- Peces


def grafic(id_: str, titol: str, tipus: str, unitat: str, eix_x: list, series: list[dict],
           nota: str | None = None) -> dict:
    return {"id": id_, "titol": titol, "tipus": tipus, "unitat": unitat, "eix_x": [str(x) for x in eix_x],
            "series": series, "nota": nota}


def serie(nom: str, valors: list) -> dict:
    return {"nom": nom, "valors": list(valors)}


def xifra(etiqueta: str, valor, unitat: str, abans=None, vs: str | None = None) -> dict:
    var = variacio(valor, abans, unitat)
    return {"etiqueta": etiqueta, "valor": valor, "unitat": unitat, "variacio": var,
            "vs": vs if var is not None else None}


def variacio(ara, abans, unitat: str) -> float | None:
    if ara is None or abans is None:
        return None
    if unitat == "pct":
        return round(ara - abans, 3)
    return round((ara - abans) / abans, 3) if abans else None


def _setmana(d: date) -> str:
    return f"S{d.isocalendar().week}"


def _dia(d: date) -> str:
    return f"{DIES[d.weekday()]} {d.day}"


def _setmanes(f: Filtre) -> list[tuple[date, date]]:
    """Setmanes (dilluns-diumenge) que toquen el període, retallades al període."""
    out, d = [], base.dilluns(f.des)
    while d <= f.fins:
        out.append((max(d, f.des), min(d + timedelta(days=6), f.fins)))
        d += timedelta(days=7)
    return out


def demanda_perduda_eur(con: sqlite3.Connection, f: Filtre, conversio: float | None) -> float | None:
    preus = dict(con.execute("SELECT gtin, preu_eur FROM catalog_sku").fetchall())
    perdudes = [p for p in base.peticions(con, f) if base.es_perduda(p)]
    if conversio is None:
        return None
    return round(sum(preus.get(p["gtin_demanat"]) or 0 for p in perdudes) * conversio, 2)


def _vs(f: Filtre) -> str:
    return {1: "el mateix dia de la setmana passada", 7: "setmana anterior"}.get(base.dies(f), "període anterior")


def _conversio_models(taula: list[dict]) -> tuple[list[dict], list[dict]]:
    """(top 5, cua 5) de models per conversió amb un mínim de proves."""
    amb = sorted((m for m in taula if m["proves"] >= PROVES_MINIMES_MODEL and m["conversio"] is not None),
                 key=lambda m: (-m["conversio"], -m["proves"], m["model"]))
    if len(amb) <= 10:   # pocs models: la meitat de dalt i la de baix, sense repetir-ne cap
        meitat = (len(amb) + 1) // 2
        return amb[:meitat], list(reversed(amb[meitat:]))
    return amb[:5], list(reversed(amb[-5:]))


def _grafic_models(id_: str, titol: str, models: list[dict]) -> dict:
    return grafic(id_, titol, "barres", "pct", [m["nom"] for m in models],
                  [serie("Conversió", [m["conversio"] for m in models])],
                  f"Models amb {PROVES_MINIMES_MODEL} proves o més.")


def _per_setmana(con: sqlite3.Connection, f: Filtre, proves: list) -> list[tuple[str, int, int]]:
    out = []
    for des, fins in _setmanes(f):
        ps = [p for p in proves if des.isoformat() <= p["inici"][:10] <= fins.isoformat()]
        out.append((_setmana(des), len(ps), sum(p["venuda"] for p in ps)))
    return out


def _conversio_setmanal(con, f, proves) -> dict:
    files = _per_setmana(con, f, proves)
    return grafic("conversio_setmanal", "Conversió de provador per setmana", "linia", "pct",
                  [s for s, _, _ in files], [serie("Conversió", [base.frac(c, n) for _, n, c in files])])


def _peces_per_sessio(proves: list) -> dict:
    files = servei_mod.peces_per_sessio(proves)
    eix = [f"{r['peces']}{'+' if r['peces'] == servei_mod.MAX_PECES else ''}" for r in files]
    amb = [round(r["sessions"] * (r["pct_amb_compra"] or 0)) for r in files]
    return grafic("peces_per_sessio", "Sessions per nombre de peces provades", "barres_apilades", "enter", eix,
                  [serie("Amb compra", amb), serie("Sense compra", [r["sessions"] - a for r, a in zip(files, amb)])])


def _motius_donut(con, f) -> dict:
    m = nfc_mod.motius(con, f)
    return grafic("motius", "Per què no se l'emporten", "donut", "enter",
                  [base.MOTIUS.get(x["motiu"], x["motiu"]) for x in m["per_motiu"]],
                  [serie("Respostes", [x["n"] for x in m["per_motiu"]])],
                  f"{m['respostes']} respostes a la fitxa ({base.pct_txt(m['taxa_resposta'])} de les sessions de fitxa).")


def _origen_setmanal(con, f, proves) -> dict:
    grups = exp_mod.grup_origen_per_dia(con, f)
    eix, amb, sense = [], [], []
    for des, fins in _setmanes(f):
        c = {"amb": [0, 0], "sense": [0, 0]}
        for p in proves:
            dia = p["inici"][:10]
            g = grups.get(dia) or p["grup"]
            if des.isoformat() <= dia <= fins.isoformat() and g in c:
                c[g][0] += 1
                c[g][1] += p["venuda"]
        eix.append(_setmana(des))
        amb.append(base.frac(c["amb"][1], c["amb"][0]))
        sense.append(base.frac(c["sense"][1], c["sense"][0]))
    return grafic("conversio_origen", "Conversió setmanal amb i sense l'origen a la fitxa", "linia", "pct", eix,
                  [serie("Amb origen", amb), serie("Sense origen", sense)],
                  "Dies sortejats (grup de control). Una diferència d'una setmana no demostra res.")


# ---------------------------------------------------------------- Per tipus


def _diari(con, f, k, inf) -> None:
    ant = base.amb_dates(f, f.des - timedelta(days=7), f.fins - timedelta(days=7))
    ka = resum_mod.kpi(con, ant)
    vs = _vs(f)
    inf["xifres"] = [
        xifra("Proves", k["proves"], "enter", ka["proves"], vs),
        xifra("Compres després de provar", k["compres_atribuides"], "enter", ka["compres_atribuides"], vs),
        xifra("Peticions de talla", k["peticions_talla"], "enter", ka["peticions_talla"], vs),
    ]
    obertes = sum(1 for a in base.abandonades(con, f) if not a["resolta"])
    perduda = talles_mod.demanda_perduda(con, f)["per_variant"]
    linies = [
        f"{base.plural(k['proves'], 'prova', 'proves')} a les cabines ({base.plural(k['sessions'], 'sessió', 'sessions')}).",
        f"{base.plural(k['compres_atribuides'], 'compra', 'compres')} després de provar "
        f"(conversió {base.pct_txt(k['conversio'])}); {k['venut_sense_provar']} u. venudes sense provar.",
        f"{base.plural(k['peticions_talla'], 'petició', 'peticions')} de talla; resposta mediana "
        f"{k['temps_resposta_mediana_s'] if k['temps_resposta_mediana_s'] is not None else '—'} s "
        f"({base.pct_txt(k['pct_resposta_sota_90s'])} per sota de 90 s).",
        f"{base.plural(k['peces_abandonades'], 'peça oblidada', 'peces oblidades')} a les cabines"
        + (f" ({obertes} encara per recollir)." if obertes else "."),
        (f"Talla més demanada sense estoc: «{perduda[0]['nom']}» en {perduda[0]['talla']} "
         f"({base.plural(perduda[0]['n'], 'petició', 'peticions')})." if perduda
         else "Cap talla demanada que no hi fos."),
    ]
    inf["blocs"].insert(0, {"id": "cinc_linies", "titol": "El dia en cinc línies", "text": " ".join(linies),
                            "dades": {"linies": linies}})
    per_hora: Counter = Counter(base.dt(s["inici"]).hour for s in base.sessions(con, f))
    hores = list(range(min(per_hora, default=10), max(per_hora, default=20) + 1))
    inf["grafics"] = [grafic("sessions_hora", "Sessions de cabina per hora", "barres", "enter",
                             [f"{h} h" for h in hores], [serie("Sessions", [per_hora[h] for h in hores])])]


def _setmanal(con, f, k, inf) -> None:
    fa = base.anterior(f)
    ka = resum_mod.kpi(con, fa)
    vs = _vs(f)
    inf["xifres"] = [
        xifra("Proves", k["proves"], "enter", ka["proves"], vs),
        xifra("Conversió de provador", k["conversio"], "pct", ka["conversio"], vs),
        xifra("Venut sense provar", k["venut_sense_provar"], "enter", ka["venut_sense_provar"], vs),
        xifra("Demanda perduda (estimació)", demanda_perduda_eur(con, f, k["conversio"]), "eur",
              demanda_perduda_eur(con, fa, ka["conversio"]), vs),
        xifra("Temps de resposta (mediana)", k["temps_resposta_mediana_s"], "segons", ka["temps_resposta_mediana_s"], vs),
    ]
    proves = base.proves_valides(con, f)
    dies = resum_mod.serie_diaria(con, f, proves)
    per_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for p in proves:
        c = per_cat[p["categoria"] or "sense catàleg"]
        c[0] += 1
        c[1] += p["venuda"]
    cats = sorted(per_cat, key=lambda c: -per_cat[c][0])
    top, cua = _conversio_models(models_mod.taula_models(con, f, proves))
    inf["grafics"] = [
        grafic("proves_compres_dia", "Proves i compres per dia", "barres", "enter",
               [_dia(date.fromisoformat(d["data"])) for d in dies],
               [serie("Proves", [d["proves"] for d in dies]), serie("Compres", [d["compres"] for d in dies])]),
        grafic("conversio_categoria", "Conversió per categoria", "barres", "pct", cats,
               [serie("Conversió", [base.frac(per_cat[c][1], per_cat[c][0]) for c in cats])]),
        _grafic_models("top_models", "Els 5 models que més converteixen", top),
        _grafic_models("cua_models", "Els 5 models que menys converteixen", cua),
        _peces_per_sessio(proves),
        _motius_donut(con, f),
    ]


def resultat_decisions(con: sqlite3.Connection, f: Filtre) -> list[dict]:
    """Decisions amb model creades al període: conversió del model abans (14 dies) i després (fins al final)."""
    out = []
    for d in con.execute(
            """SELECT * FROM decisio WHERE model IS NOT NULL AND (:b IS NULL OR botiga_id = :b OR botiga_id IS NULL)
               AND creada >= :des AND creada < :fins ORDER BY creada""", base.params(f)):
        dia = base.dt(d["creada"]).date()
        abans = base.amb_dates(f, dia - timedelta(days=DIES_ABANS_DECISIO), dia - timedelta(days=1))
        despres = base.amb_dates(f, dia + timedelta(days=1), f.fins)
        files = []
        for periode in (abans, despres):
            ps = [p for p in base.proves_valides(con, periode) if p["model"] == d["model"]] if periode.des <= periode.fins else []
            files.append((len(ps), sum(p["venuda"] for p in ps)))
        out.append({"id": d["id"], "titol": d["titol"], "model": d["model"], "creada": d["creada"], "estat": d["estat"],
                    "resultat": d["resultat"], "proves_abans": files[0][0], "conversio_abans": base.frac(files[0][1], files[0][0]),
                    "proves_despres": files[1][0], "conversio_despres": base.frac(files[1][1], files[1][0])})
    return out


def _mensual(con, f, k, inf) -> None:
    fa = base.anterior(f)
    ka = resum_mod.kpi(con, fa)
    vs = _vs(f)
    e = estoc_mod.estoc(con, f)
    v = valor_mod.valor(con, f)
    recuperat = round(sum(p["valor_eur"] or 0 for p in v["palanques"]), 2)
    inf["xifres"] = [
        xifra("Proves", k["proves"], "enter", ka["proves"], vs),
        xifra("Conversió de provador", k["conversio"], "pct", ka["conversio"], vs),
        xifra("Estoc parat (unitats)", e["resum_parat"]["unitats"], "enter"),
        xifra("Estoc parat (valor)", e["resum_parat"]["valor_eur"], "eur"),
        xifra("Valor estimat recuperat", recuperat, "eur"),
        xifra("Demanda perduda (estimació)", demanda_perduda_eur(con, f, k["conversio"]), "eur",
              demanda_perduda_eur(con, fa, ka["conversio"]), vs),
    ]
    dec = resultat_decisions(con, f)
    if dec:
        text = " ".join(f"«{d['titol']}»: {base.pct_txt(d['conversio_abans'])} abans, "
                        f"{base.pct_txt(d['conversio_despres'])} després." for d in dec)
    else:
        text = "Cap decisió sobre un model aquest mes."
    inf["blocs"].insert(1, {"id": "decisions_resultat", "titol": "Decisions del mes: abans i després",
                            "text": text, "dades": dec})
    proves = base.proves_valides(con, f)
    perduda = talles_mod.demanda_perduda(con, f)["per_variant"]
    per_model: Counter = Counter()
    for p in perduda:
        per_model[p["nom"]] += p["n"]
    top_perduda = per_model.most_common(8)
    rp = e["resum_parat"]["per_categoria"]
    inf["grafics"] = [
        _conversio_setmanal(con, f, proves),
        grafic("decisions_abans_despres", "Conversió del model abans i després de cada decisió", "barres", "pct",
               [d["titol"] for d in dec],
               [serie("Abans", [d["conversio_abans"] for d in dec]),
                serie("Després", [d["conversio_despres"] for d in dec])],
               f"Abans: els {DIES_ABANS_DECISIO} dies anteriors a la decisió. No és una prova amb grup de control."),
        grafic("estoc_parat_categoria", "Estoc parat per categoria (valor a PVP)", "donut", "eur",
               [c["categoria"] for c in rp], [serie("Valor", [c["valor_eur"] for c in rp])],
               f"{e['resum_parat']['unitats']} u. sense cap prova ni venda en "
               f"{base.par(con, f, 'dies_estoc_parat')} dies."),
        grafic("demanda_perduda_model", "Demanda perduda per model (peticions sense estoc)", "barres", "enter",
               [n for n, _ in top_perduda], [serie("Peticions", [x for _, x in top_perduda])]),
    ]


def dubte_talla(proves: list, info: dict) -> list[dict]:
    """Per model: sessions on s'ha provat el mateix model i color en dues talles o més."""
    per_sessio: dict[tuple, set] = defaultdict(set)
    for p in proves:
        if p["model"]:
            per_sessio[(p["sessio_id"], p["model"], p["color"])].add(p["talla"])
    sessions_model: dict[str, set] = defaultdict(set)
    dubte: Counter = Counter()
    for (s, model, _), talles in per_sessio.items():
        sessions_model[model].add(s)
        if len(talles) >= 2:
            dubte[model] += 1
    files = [{"model": m, "nom": base.nom_model(info, m), "sessions_dubte": n,
              "pct_sessions_model": base.frac(n, len(sessions_model[m]))} for m, n in dubte.items()]
    return sorted(files, key=lambda r: (-(r["pct_sessions_model"] or 0), r["model"]))


def _temporada(con, f, k, inf) -> None:
    proves = base.proves_valides(con, f)
    info = base.info_models(con)
    taula = models_mod.taula_models(con, f, proves)
    inf["xifres"] = [
        xifra("Proves", k["proves"], "enter"),
        xifra("Conversió de provador", k["conversio"], "pct"),
        xifra("Unitats venudes", k["unitats_venudes"], "enter"),
        xifra("Demanda perduda (estimació)", demanda_perduda_eur(con, f, k["conversio"]), "eur"),
    ]
    grafics = []
    taula_ct = talles_mod.taula_categoria_talla(proves)
    per_cat: dict[str, list[dict]] = defaultdict(list)
    for r in taula_ct:
        per_cat[r["categoria"]].append(r)
    for cat, files in sorted(per_cat.items(), key=lambda kv: -sum(r["proves"] for r in kv[1]))[:6]:
        n, c = sum(r["proves"] for r in files), sum(r["compres"] for r in files)
        if n < PROVES_MINIMES_CATEGORIA:
            continue
        grafics.append(grafic(f"talles_{cat}", f"Corba de talles: {cat}", "barres", "pct", [r["talla"] for r in files],
                              [serie("% de les proves", [base.frac(r["proves"], n) for r in files]),
                               serie("% de les compres", [base.frac(r["compres"], c) for r in files])],
                              "Si una talla es prova molt més que no es compra, potser el patró no hi quadra."))
    top, cua = _conversio_models(taula)
    grafics += [_grafic_models("models_repetir", "Models a repetir (més conversió)", top),
                _grafic_models("models_canviar", "Models a canviar (menys conversió)", cua)]
    dubte = dubte_talla(proves, info)
    grafics.append(grafic("dubte_talla", "Dubte de talla: sessions amb el mateix model en dues talles", "barres", "pct",
                          [d["nom"] for d in dubte[:8]], [serie("% de sessions del model", [d["pct_sessions_model"] for d in dubte[:8]])]))
    e = exp_mod.efecte_origen(con, f)
    if e:
        grafics.append(grafic("efecte_origen", "Conversió amb i sense l'origen a la fitxa", "barres", "pct",
                              ["Amb origen", "Sense origen"],
                              [serie("Conversió", [e["grups"]["amb"]["conversio"], e["grups"]["sense"]["conversio"]])],
                              e["conclusio"]))
    inf["grafics"] = grafics

    motius = {m["model"]: m["motiu_principal"] for m in taula}
    canviar = [f"«{m['nom']}» ({base.pct_txt(m['conversio'])}"
               + (f", motiu: {base.MOTIUS.get(motius[m['model']], motius[m['model']]).lower()}" if motius.get(m["model"]) else "")
               + ")" for m in cua]
    corba = talles_mod.talles(con, f)["corba"]
    recomana = []
    if top:
        recomana.append("Repetir: " + ", ".join(f"«{m['nom']}» ({base.pct_txt(m['conversio'])})" for m in top) + ".")
    if canviar:
        recomana.append("Canviar o no repetir: " + ", ".join(canviar) + ".")
    for c in corba[:3]:
        recomana.append(f"Corba per a «{c['nom']}»: " + ", ".join(
            f"{t['talla']} {base.pct_txt(t['proposta_pct'])}" for t in c["talles"]) + ".")
    if dubte and (dubte[0]["pct_sessions_model"] or 0) >= 0.15:
        recomana.append(f"Revisar la guia de talles de «{dubte[0]['nom']}»: en el "
                        f"{base.pct_txt(dubte[0]['pct_sessions_model'])} de les sessions es prova en dues talles.")
    inf["blocs"] += [
        {"id": "dubte_talla", "titol": "Dubte de talla per model",
         "text": (f"«{dubte[0]['nom']}» es prova en dues talles o més en el {base.pct_txt(dubte[0]['pct_sessions_model'])} "
                  "de les seves sessions." if dubte else "Cap model provat en dues talles a la mateixa sessió."),
         "dades": dubte},
        {"id": "recomanacions_comanda", "titol": "Recomanacions per a la propera comanda",
         "text": " ".join(recomana) or "Encara no hi ha prou proves per recomanar res.",
         "dades": {"repetir": top, "canviar": cua, "corba": corba}},
    ]


def _unitat_metrica(metrica: str | None) -> str:
    m = metrica or ""
    if m.endswith("_s"):
        return "segons"
    if any(x in m for x in ("pct", "taxa", "conversio", "error", "diferencia")):
        return "pct"
    return "enter"


def _pilot(con, f, k, inf) -> None:
    criteris = next((b["dades"] for b in inf["blocs"] if b["id"] == "criteris"), [])
    inf["xifres"] = [dict(xifra(c.get("descripcio") or c.get("metrica"), c.get("valor"), _unitat_metrica(c.get("metrica"))),
                          objectiu=c.get("objectiu"), compleix=c.get("compleix")) for c in criteris] or [
        xifra("Proves", k["proves"], "enter"), xifra("Conversió de provador", k["conversio"], "pct")]
    proves = base.proves_valides(con, f)
    files = _per_setmana(con, f, proves)
    inf["grafics"] = [
        _origen_setmanal(con, f, proves),
        _conversio_setmanal(con, f, proves),
        grafic("proves_compres_setmana", "Proves i compres per setmana", "barres", "enter", [s for s, _, _ in files],
               [serie("Proves", [n for _, n, _ in files]), serie("Compres", [c for _, _, c in files])]),
    ]


def _mango(con, f, k, inf) -> None:
    dossier = next((b["dades"] for b in inf["blocs"] if b["id"] == "kpi"), {})
    etiquetes = {"proves": ("Proves", "enter"), "conversio": ("Conversió de provador", "pct"),
                 "venut_sense_provar_pct": ("Venut sense provar", "pct"),
                 "temps_resposta_mediana_s": ("Temps de resposta (mediana)", "segons"),
                 "demanda_perduda": ("Peticions sense estoc", "enter"),
                 "peces_abandonades": ("Peces oblidades", "enter"),
                 "peticions_per_sessio": ("Peticions per sessió", "enter"),
                 "tocs_per_sessio": ("Tocs de fitxa per sessió", "enter")}
    inf["xifres"] = [xifra(et, dossier.get(c), u) for c, (et, u) in etiquetes.items() if c in dossier]
    proves = base.proves_valides(con, f)
    inf["grafics"] = [_origen_setmanal(con, f, proves), _conversio_setmanal(con, f, proves), _motius_donut(con, f)]


_PER_TIPUS = {"diari": _diari, "setmanal": _setmanal, "mensual": _mensual, "temporada": _temporada,
              "pilot": _pilot, "mango": _mango}


def enriqueix(con: sqlite3.Connection, f: Filtre, tipus: str, k: dict, inf: dict) -> dict:
    """Afegeix `xifres`, `grafics` i els blocs nous a l'informe `inf` (el modifica i el retorna)."""
    inf.setdefault("xifres", [])
    inf.setdefault("grafics", [])
    _PER_TIPUS[tipus](con, f, k, inf)
    return inf
