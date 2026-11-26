"""Xifres, gràfics i blocs nous dels informes (v0.3, docs/ESPECIFICACIO-v3.md, E.2).

`enriqueix` afegeix a l'informe de `informes.informe` (sense treure'n res):

  * `xifres`:  [{"etiqueta", "valor", "unitat", "variacio", "vs"}]
  * `grafics`: [{"id", "titol", "tipus", "unitat", "eix_x", "series": [{"nom", "valors"}], "nota", "destaca"}]
  * alguns blocs nous (p. ex. les cinc línies del diari o el dubte de talla de la temporada).

El frontend i el PDF (hebra/grafics_svg.py) dibuixen els mateixos gràfics.

Variació d'una xifra: si la unitat és `pct`, és la DIFERÈNCIA en fracció (0,03 = +3 punts);
per a la resta (`enter`, `eur`, `segons`) és el canvi RELATIU ((ara − abans) ÷ abans).
`None` si no hi ha amb què comparar.

Demanda perduda en euros (estimació): Σ PVP de les variants demanades que no hi eren ×
conversió del període (la probabilitat que s'haguessin comprat si hi haguessin estat).
"""

import json
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
           nota: str | None = None, destaca: list[bool] | None = None) -> dict:
    """`destaca` (opcional): per a cada element de `eix_x`, si s'ha de remarcar (p. ex. «molt provat, poc venut»).
    `lectura` (v0.7) s'omple en acabar l'informe (`llegeix`): què hi veiem i què en podem fer."""
    return {"id": id_, "titol": titol, "tipus": tipus, "unitat": unitat, "eix_x": [str(x) for x in eix_x],
            "series": series, "nota": nota, "destaca": destaca, "lectura": None}


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


def _mapa_peces(taula: list[dict]) -> dict:
    """«On és cada peça»: proves contra conversió de cada model, el mateix gràfic que a Peces del tauler."""
    ms = [m for m in taula if m["proves"] and m["conversio"] is not None]
    return grafic("mapa_peces", "On és cada peça: proves i conversió de cada model", "dispersio", "pct",
               [m["nom"] or m["model"] for m in ms],
               [serie("Proves", [m["proves"] for m in ms]), serie("Conversió", [m["conversio"] for m in ms])],
               "A la dreta, els models més provats; a dalt, els que més es compren després de provar-los. "
               "Les línies són la mitjana. En vermell, «molt provat, poc venut»: cal mirar-ne la talla, el preu o el tall.",
               [bool(m.get("molt_provat_poc_venut")) for m in ms])


def _sessions_hora(con, f) -> dict:
    """Quan s'omplen els provadors: sessions per hora (al tauler, el mapa de calor de Servei i del Resum)."""
    per_hora: Counter = Counter(base.dt(s["inici"]).hour for s in base.sessions(con, f))
    hores = list(range(min(per_hora, default=10), max(per_hora, default=20) + 1))
    return grafic("sessions_hora", "Quan s'omplen els provadors: sessions per hora", "barres", "enter",
                  [f"{h} h" for h in hores], [serie("Sessions", [per_hora[h] for h in hores])],
                  "Per posar-hi més gent a les hores fortes i reposar abans.")


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
                  [base.nom_motiu(con, x["motiu"]) for x in m["per_motiu"]],
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
    inf["grafics"] = [_sessions_hora(con, f)]


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
    taula = models_mod.taula_models(con, f, proves)
    top, cua = _conversio_models(taula)
    # El mateix ordre que el tauler: com ha anat, quines peces cal mirar, per què, i quan hi ha gent.
    inf["grafics"] = [
        grafic("proves_compres_dia", "Proves i compres per dia", "barres", "enter",
               [_dia(date.fromisoformat(d["data"])) for d in dies],
               [serie("Proves", [d["proves"] for d in dies]), serie("Compres", [d["compres"] for d in dies])]),
        _mapa_peces(taula),
        _grafic_models("top_models", "Els 5 models que més converteixen", top),
        _grafic_models("cua_models", "Els 5 models que menys converteixen", cua),
        grafic("conversio_categoria", "Conversió per categoria", "barres", "pct", cats,
               [serie("Conversió", [base.frac(per_cat[c][1], per_cat[c][0]) for c in cats])]),
        _motius_donut(con, f),
        _peces_per_sessio(proves),
        _sessions_hora(con, f),
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


def _dades_bloc(inf: dict, bid: str):
    """Les dades d'un bloc que l'informe ja ha calculat (None si no hi és)."""
    return next((b["dades"] for b in inf.get("blocs") or [] if b.get("id") == bid), None)


def _mensual(con, f, k, inf) -> None:
    fa = base.anterior(f)
    ka = resum_mod.kpi(con, fa)
    vs = _vs(f)
    # Els blocs «estoc» i «valor» (informes._mensual) ja porten estoc() i valor(): no es tornen a calcular.
    e = _dades_bloc(inf, "estoc") or estoc_mod.estoc(con, f)
    v = _dades_bloc(inf, "valor") or valor_mod.valor(con, f)
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
        _mapa_peces(models_mod.taula_models(con, f, proves)),
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
               + (f", motiu: {base.nom_motiu(con, motius[m['model']]).lower()}" if motius.get(m["model"]) else "")
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
    for g in inf["grafics"]:
        g["lectura"] = llegeix(g)
    # La marca tria quins gràfics surten a cada tipus d'informe i en quin ordre (v0.7).
    inf["grafics_disponibles"] = [{"id": g["id"], "titol": g["titol"]} for g in inf["grafics"]]
    triats = grafics_triats(con, tipus)
    inf["grafics_triats"] = triats
    if triats is not None:
        per_id = {g["id"]: g for g in inf["grafics"]}
        inf["grafics"] = [per_id[i] for i in triats if i in per_id]
    return inf


def grafics_triats(con: sqlite3.Connection, tipus: str) -> list[str] | None:
    """Ids dels gràfics que la marca vol en aquest tipus d'informe, en ordre; None = tots (per defecte)."""
    try:
        r = con.execute("SELECT grafics_json FROM config_informe WHERE tipus = ?", (tipus,)).fetchone()
    except sqlite3.OperationalError:   # base de dades antiga encara sense la taula
        return None
    return json.loads(r[0]) if r else None


def desa_grafics_triats(con: sqlite3.Connection, tipus: str, ids: list[str] | None) -> None:
    """Desa la tria (None o llista buida de restabliment = tornar a tots)."""
    if ids is None:
        con.execute("DELETE FROM config_informe WHERE tipus = ?", (tipus,))
    else:
        con.execute("""INSERT INTO config_informe (tipus, grafics_json, actualitzat) VALUES (?, ?, datetime('now'))
                       ON CONFLICT(tipus) DO UPDATE SET grafics_json = excluded.grafics_json,
                       actualitzat = excluded.actualitzat""", (tipus, json.dumps(ids)))
    con.commit()


# ---------------------------------------------------------------- Lectura de cada gràfic (v0.7)
# Un informe no és només gràfics: sota cadascun, dues o tres frases amb les xifres que importen
# (què hi veiem) i què en pot fer la marca o la botiga. Es calcula de les mateixes dades del gràfic.

ACCIO_MOTIU = {
    "talla": "Revisa el patronatge o la proporció de talles de la propera comanda.",
    "tall": "Comenta-ho amb disseny: el tall o la forma no convenç quan es prova.",
    "preu": "Prova una altra exposició o acompanya-la d'una peça que la justifiqui abans de rebaixar.",
    "color": "Mira si hi ha el color que es busca i com s'exposa.",
    "qualitat": "Fes-ne arribar el comentari a producte: el teixit no convenç a la mà.",
}


def _f(v, unitat: str) -> str:
    from ..grafics_svg import format_valor
    return format_valor(v, unitat)


def _parells(g: dict, k: int = 0) -> list[tuple[str, float]]:
    vals = g["series"][k]["valors"] if len(g["series"]) > k else []
    return [(e, v) for e, v in zip(g["eix_x"], vals) if v is not None]


def llegeix(g: dict) -> str | None:
    """Dues o tres frases sobre el gràfic `g`: què hi veiem i què en podem fer. None si no hi ha dades."""
    try:
        return _LECTURES.get(g["id"].split("_")[0] if g["id"].startswith("talles_") else g["id"], _lectura_general)(g)
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        return None


def _lectura_general(g: dict) -> str | None:
    pp = _parells(g)
    if len(pp) < 2:
        return None
    alt, baix = max(pp, key=lambda x: x[1]), min(pp, key=lambda x: x[1])
    return f"El valor més alt és «{alt[0]}» ({_f(alt[1], g['unitat'])}) i el més baix, «{baix[0]}» ({_f(baix[1], g['unitat'])})."


def _l_proves_compres(g: dict) -> str | None:
    proves, compres = _parells(g, 0), dict(_parells(g, 1))
    dia = "la setmana" if g["id"].endswith("setmana") else "el dia"
    if not proves or not sum(v for _, v in proves):
        return None
    tp, tc = sum(v for _, v in proves), sum(compres.values())
    fort = max(proves, key=lambda x: x[1])
    conv = [(e, compres.get(e, 0) / v) for e, v in proves if v >= 10]
    text = (f"{_f(tp, 'enter')} proves i {_f(tc, 'enter')} compres després de provar: {_f(tc / tp, 'pct')} de conversió. "
            f"{dia.capitalize()} amb més proves va ser {fort[0]} ({_f(fort[1], 'enter')}).")
    if len(conv) >= 2:
        pitjor = min(conv, key=lambda x: x[1])
        text += (f" {dia.split()[0].capitalize()} de conversió més baixa, {pitjor[0]} ({_f(pitjor[1], 'pct')}): "
                 f"si hi havia molta gent, mira si n'hi havia prou a la sala per portar talles.")
    return text


def _l_mapa(g: dict) -> str | None:
    noms, proves, conv = g["eix_x"], g["series"][0]["valors"], g["series"][1]["valors"]
    if not noms:
        return None
    mitja = sum(conv) / len(conv)
    dest = [(n, p, c) for n, p, c, d in zip(noms, proves, conv, g.get("destaca") or [False] * len(noms)) if d]
    if not dest:
        return (f"Cap model és alhora molt provat i poc venut: la col·lecció es comporta bé al provador "
                f"(conversió mitjana {_f(mitja, 'pct')}).")
    llista = "; ".join(f"«{n}»: {_f(p, 'enter')} proves i {_f(c, 'pct')} de conversió" for n, p, c in dest)
    if len(dest) == 1:
        accio = "La gent l'agafa, però no se l'emporta: mira'n el motiu més citat i la talla que falla abans de rebaixar-la."
    else:
        accio = "La gent les agafa, però no se les emporta: mira'n el motiu més citat i la talla que falla abans de rebaixar-les."
    return f"A mirar: {llista}, davant d'una mitjana de {_f(mitja, 'pct')}. {accio}"


def _l_top(g: dict) -> str | None:
    pp = _parells(g)
    if not pp:
        return None
    m = pp[0]
    return (f"«{m[0]}» és el model que més converteix ({_f(m[1], 'pct')}). "
            f"Assegura't que no en falti cap talla: cada petició sense estoc és una venda gairebé feta.")


def _l_cua(g: dict) -> str | None:
    pp = _parells(g)
    if not pp:
        return None
    m = pp[0]
    return (f"«{m[0]}» és el que menys converteix ({_f(m[1], 'pct')}). "
            f"Abans de rebaixar-lo, mira per què no se l'emporten: si és la talla, el problema és de producte, no de preu.")


def _l_categories(g: dict) -> str | None:
    pp = _parells(g)
    if len(pp) < 2:
        return None
    alt, baix = max(pp, key=lambda x: x[1]), min(pp, key=lambda x: x[1])
    return (f"La categoria que més es compra després de provar és {alt[0]} ({_f(alt[1], 'pct')}); la que menys, "
            f"{baix[0]} ({_f(baix[1], 'pct')}). Compara sempre un model amb la seva categoria, no amb tota la botiga.")


def _l_motius(g: dict) -> str | None:
    pp = _parells(g)
    total = sum(v for _, v in pp)
    if not total:
        return None
    m = max(pp, key=lambda x: x[1])
    clau = next((k for k in ACCIO_MOTIU if k in m[0].lower()), None)
    return (f"El motiu més citat és «{m[0]}» ({_f(m[1] / total, 'pct')} de {_f(total, 'enter')} respostes). "
            + (ACCIO_MOTIU[clau] if clau else "Llegeix les respostes «altre» per veure si hi ha un motiu nou."))


def _l_peces_sessio(g: dict) -> str | None:
    amb, sense = g["series"][0]["valors"], g["series"][1]["valors"]
    files = [(e, a, a + b) for e, a, b in zip(g["eix_x"], amb, sense) if a + b >= 5]
    if len(files) < 2:
        return None
    una = next((f for f in files if f[0] == "1"), files[0])
    millor = max(files, key=lambda f: f[1] / f[2])
    if millor is una:
        return f"Qui entra amb una sola peça és qui més compra ({_f(una[1] / una[2], 'pct')} de les sessions)."
    return (f"Qui entra amb {millor[0]} peces compra en el {_f(millor[1] / millor[2], 'pct')} de les sessions, davant del "
            f"{_f(una[1] / una[2], 'pct')} de qui n'entra una. Proposar una segona peça (el «combina amb» de la fitxa) ajuda.")


def _l_hores(g: dict) -> str | None:
    pp = _parells(g)
    total = sum(v for _, v in pp)
    if not total or len(pp) < 3:
        return None
    # La franja de dues hores seguides amb més sessions, i l'hora més tranquil·la.
    i = max(range(len(pp) - 1), key=lambda j: pp[j][1] + pp[j + 1][1])
    franja = pp[i][1] + pp[i + 1][1]
    calma = min(pp, key=lambda x: x[1])
    return (f"La franja més plena és de {pp[i][0]} a {int(pp[i + 1][0].split()[0]) + 1} h ({_f(franja / total, 'pct')} de les "
            f"sessions). Reforça la sala i reposa talles abans d'aquesta hora; la més tranquil·la és a les {calma[0]}.")


def _l_setmanal(g: dict) -> str | None:
    pp = _parells(g)
    if not pp:
        return None
    if len(pp) == 1:
        return (f"Conversió de provador de la setmana {pp[0][0]}: {_f(pp[0][1], 'pct')}. "
                f"Amb dues setmanes o més s'hi veurà si puja o baixa.")
    a, b = pp[0], pp[-1]
    dif = (b[1] - a[1]) * 100
    sentit = "puja" if dif > 0.5 else "baixa" if dif < -0.5 else "es manté"
    return (f"La conversió {sentit}: de {_f(a[1], 'pct')} ({a[0]}) a {_f(b[1], 'pct')} ({b[0]}). "
            f"Una setmana sola no és tendència; mira-ho al costat de les decisions del mes.")


def _l_decisions(g: dict) -> str | None:
    pp = list(zip(g["eix_x"], g["series"][0]["valors"], g["series"][1]["valors"]))
    pp = [(n, a, d) for n, a, d in pp if a is not None and d is not None]
    if not pp:
        return "Aquest mes no hi ha cap decisió sobre un model amb proves abans i després."
    millors = [n for n, a, d in pp if d - a > 0.02]
    exemple = f" (per exemple, «{millors[0]}»)" if millors else ""
    return (f"{len(millors)} de {len(pp)} decisions han millorat la conversió del model{exemple}. "
            "Sense grup de control és una pista, no una prova: si una ha funcionat, repeteix-la en una altra botiga.")


def _l_estoc(g: dict) -> str | None:
    pp = _parells(g)
    total = sum(v for _, v in pp)
    if not total:
        return "No hi ha estoc parat: tot el que hi ha a la botiga s'ha provat o venut."
    m = max(pp, key=lambda x: x[1])
    return (f"Hi ha {_f(total, 'eur')} de roba (a PVP) que ningú no ha provat ni comprat; la major part és {m[0]} "
            f"({_f(m[1], 'eur')}). Primer, comprova que és a la sala i no al magatzem; després, mou-la o traspassa-la.")


def _l_perduda(g: dict) -> str | None:
    pp = _parells(g)
    total = sum(v for _, v in pp)
    if not total:
        return "Cap client ha demanat una talla que no hi fos."
    m = max(pp, key=lambda x: x[1])
    return (f"{_f(total, 'enter')} peticions de talles que no hi eren; la que més, «{m[0]}» ({_f(m[1], 'enter')}). "
            f"Reposa aquesta talla primer: són clients que ja havien triat la peça.")


def _l_talles(g: dict) -> str | None:
    pp = _parells(g)
    if len(pp) < 2:
        return None
    alt, baix = max(pp, key=lambda x: x[1]), min(pp, key=lambda x: x[1])
    return (f"La talla que més converteix és la {alt[0]} ({_f(alt[1], 'pct')}); la que menys, la {baix[0]} "
            f"({_f(baix[1], 'pct')}). Si una talla es prova molt i es compra poc, sol ser el patronatge d'aquella talla.")


def _l_repetir(g: dict) -> str | None:
    pp = _parells(g)
    if not pp:
        return None
    noms = ", ".join(f"«{n}» ({_f(v, 'pct')})" for n, v in pp[:3])
    return f"Per repetir o ampliar a la propera temporada: {noms}. Es proven i, sobretot, se les emporten."


def _l_canviar(g: dict) -> str | None:
    pp = _parells(g)
    if not pp:
        return None
    noms = ", ".join(f"«{n}» ({_f(v, 'pct')})" for n, v in sorted(pp, key=lambda x: x[1])[:3])
    return (f"Per canviar abans de tornar-los a comprar: {noms}. Creua-ho amb el motiu de no compra "
            f"i la corba de talles de cada un.")


def _l_dubte(g: dict) -> str | None:
    pp = _parells(g)
    if not pp:
        return None
    m = max(pp, key=lambda x: x[1])
    return (f"«{m[0]}» és el model que més es prova en dues talles alhora ({_f(m[1], 'pct')} de les sessions): "
            f"la talla no orienta prou. Posa la taula de mides a la fitxa i revisa si talla gran o petit.")


def _l_origen(g: dict) -> str | None:
    noms = [x["nom"] for x in g["series"]]
    if len(g["series"]) == 2 and g["tipus"] == "linia":   # setmanal: mitjana de les setmanes
        vals = [[v for v in x["valors"] if v is not None] for x in g["series"]]
        if not all(vals):
            return None
        amb, sense = (sum(v) / len(v) for v in vals)
    else:
        d = dict(_parells(g))
        if len(d) < 2:
            return None
        amb, sense = d.get(noms[0] if noms[0] != "Conversió" else "Amb origen"), d.get("Sense origen")
        if amb is None or sense is None:
            return None
    dif = (amb - sense) * 100
    punts = f"{abs(dif):.1f}".replace(".", ",")
    return (f"Amb l'origen a la fitxa, {_f(amb, 'pct')} de conversió; sense, {_f(sense, 'pct')} "
            f"({'+' if dif >= 0 else '−'}{punts} punts). Fins que la prova no tingui prou proves, "
            f"no en treguis conclusions: el resultat i l'interval són a «Origen i proves».")


_LECTURES = {
    "models_repetir": _l_repetir, "models_canviar": _l_canviar, "dubte_talla": _l_dubte,
    "efecte_origen": _l_origen, "conversio_origen": _l_origen,
    "proves_compres_dia": _l_proves_compres, "proves_compres_setmana": _l_proves_compres,
    "mapa_peces": _l_mapa, "top_models": _l_top, "cua_models": _l_cua, "conversio_categoria": _l_categories,
    "motius": _l_motius, "peces_per_sessio": _l_peces_sessio, "sessions_hora": _l_hores,
    "conversio_setmanal": _l_setmanal, "decisions_abans_despres": _l_decisions,
    "estoc_parat_categoria": _l_estoc, "demanda_perduda_model": _l_perduda, "talles": _l_talles,
}
