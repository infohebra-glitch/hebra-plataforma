"""Els informes B-G (docs/ESPECIFICACIO.md, «Els 7 informes»; blocs a docs/API.md).

Cada informe és {tipus, titol, periode, blocs, accio, avisos, xifres, grafics} (les dues
darreres claus, de la v0.3, a informes_grafics.py). Cada bloc és
{id, titol, text, dades}: `text` és una frase per llegir, `dades` els números.

Regles comunes:
  * acaba amb UNA acció concreta (resum.accio_principal; si no n'hi ha cap,
    una acció de reserva pròpia del tipus d'informe);
  * `avisos` diu honestament el que no podem afirmar: mostra petita, vendes
    sense hora, atribució aproximada, motius amb poca resposta, dades simulades,
    experiments sense diferència demostrable i que els euros són estimacions.
  * El resum diari (B) és del darrer dia del filtre (`Filtre.fins`).
"""

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import timedelta

from . import Filtre, base, estadistica
from . import temps_real as alertes_mod, inventari as estoc_mod, experimentacio as exp_mod, per_model as models_mod
from . import nfc as nfc_mod, tauler as resum_mod, cabina as servei_mod, per_talla as talles_mod, palanques as valor_mod
from . import informes_grafics

TITOLS = {
    "diari": "Resum diari",
    "setmanal": "Informe setmanal",
    "mensual": "Informe mensual d'accions",
    "temporada": "Informe de fi de temporada",
    "pilot": "Informe final del pilot",
    "mango": "Pilot de Mango",
}
DIES_LIMIT = {"diari": 1, "setmanal": 7, "mensual": 14, "temporada": 30, "pilot": 14, "mango": 14}
PROVES_MOSTRA_PETITA = 100
TAXA_MOTIU_BAIXA = 0.2


def _bloc(id_: str, titol: str, text: str, dades) -> dict:
    return {"id": id_, "titol": titol, "text": text, "dades": dades}


# ---------------------------------------------------------------- Blocs reutilitzables


def _xifres(k: dict, titol: str = "Tres xifres") -> dict:
    text = (f"{k['proves']} proves, {k['compres_atribuides']} compres després de provar "
            f"(conversió {base.pct_txt(k['conversio'])}"
            + (f", {base.punts_txt(k['variacio_conversio'])} respecte del període anterior" if k["variacio_conversio"] is not None else "")
            + f"). {k['venut_sense_provar']} unitats venudes sense provar.")
    claus = ("proves", "compres_atribuides", "conversio", "conversio_periode_anterior", "variacio_conversio",
             "unitats_venudes", "venut_sense_provar", "venut_sense_provar_pct", "sessions", "proves_ambigues")
    return _bloc("xifres", titol, text, {c: k[c] for c in claus})


def _molt_provat(taula: list[dict], n: int = 5) -> dict:
    marcats = [m for m in taula if m["molt_provat_poc_venut"]][:n]
    if marcats:
        text = "Molt provats i poc venuts: " + "; ".join(
            f"«{m['nom']}» ({m['proves']} proves, {base.pct_txt(m['conversio'])})" for m in marcats) + "."
    else:
        text = "Cap model molt provat i poc venut al període."
    dades = [{c: m[c] for c in ("model", "nom", "categoria", "proves", "compres", "conversio",
                                "conversio_categoria", "motiu_principal")} for m in marcats]
    return _bloc("molt_provat", "Molt provat, poc venut", text, dades)


def _talla_no_quadra(t: dict) -> dict:
    nq = t["no_quadra"]
    return _bloc("talla_no_quadra", "La talla que no quadra",
                 nq[0]["text"] if nq else "Cap talla que es provi molt i es vengui molt menys que la resta.", nq)


def _demanda(con, f) -> dict:
    d = talles_mod.demanda_perduda(con, f)
    return _bloc("demanda_perduda", "Demanda perduda", d["text"], d)


def _motius(con, f) -> dict:
    m = nfc_mod.motius(con, f)
    if m["respostes"]:
        top = m["per_motiu"][0]
        text = (f"{m['respostes']} respostes ({base.pct_txt(m['taxa_resposta'])} de les sessions de fitxa). "
                f"El motiu més citat: {base.MOTIUS.get(top['motiu'], top['motiu']).lower()} ({base.pct_txt(top['pct'])}).")
    else:
        text = "Cap resposta al motiu de no compra al període."
    return _bloc("motius", "Per què no se l'emporten", text, m)


def _servei(con, f) -> dict:
    s = servei_mod.servei(con, f)
    text = (f"{s['peticions']} peticions de talla ({base.num_txt(s['peticions_per_sessio'])} per sessió); "
            f"mediana de resposta {s['mediana_s'] if s['mediana_s'] is not None else '—'} s, "
            f"{base.pct_txt(s['pct_sota_90s'])} per sota de 90 s. "
            f"Totes les cabines plenes el {base.pct_txt(s['ocupacio']['pct_temps_totes_plenes'])} del temps.")
    return _bloc("servei", "Servei a la cabina", text, s)


def _corba(t: dict) -> dict:
    c = t["corba"]
    if c:
        m = c[0]
        talles = ", ".join(f"{x['talla']} {base.pct_txt(x['proposta_pct'])}" for x in m["talles"])
        text = f"Corba proposada per a «{m['nom']}»: {talles} (70 % compres, 30 % proves)."
    else:
        text = "Encara no hi ha prou proves per proposar cap corba de talles."
    return _bloc("corba", "Corba de talles", text, c)


def decisions(con: sqlite3.Connection, f: Filtre) -> list[dict]:
    """Registre de decisions (informe D): les creades fins a `fins` que són del període o encara obertes."""
    files = con.execute(
        """SELECT * FROM decisio WHERE (:b IS NULL OR botiga_id = :b OR botiga_id IS NULL)
             AND creada < :fins AND (creada >= :des OR estat IN ('proposada', 'acceptada') OR resultat IS NOT NULL)
           ORDER BY creada DESC, id DESC""", base.params(f)).fetchall()
    return [dict(r) for r in files]


def _decisions(con, f) -> dict:
    d = decisions(con, f)
    fetes = [x for x in d if x["estat"] == "feta"]
    amb_resultat = [x for x in d if x["resultat"]]
    text = (f"{base.plural(len(d), 'decisió', 'decisions')}: {base.plural(len(fetes), 'feta', 'fetes')}, "
            f"{len(amb_resultat)} amb resultat apuntat." if d else "Cap decisió registrada.")
    if amb_resultat:
        text += f" Última: «{amb_resultat[0]['titol']}» → {amb_resultat[0]['resultat']}"
    return _bloc("decisions", "Registre de decisions", text, d)


def _prova_en_curs(con, f) -> dict:
    exps = [e for e in exp_mod.experiments(con, f)["experiments"] if e["estat"] in ("actiu", "previst")]
    text = " ".join(f"«{e['id']}»: {e['conclusio']}" for e in exps) or "Cap prova en curs."
    return _bloc("prova_en_curs", "Prova en curs", text, exps)


# ---------------------------------------------------------------- Avisos


def avisos(con: sqlite3.Connection, f: Filtre, k: dict) -> list[str]:
    out = []
    if base.dades_simulades(con, f.botiga_id):
        out.append("Dades simulades: les ha inventat el simulador. Cap xifra d'aquest informe és un resultat real.")
    if k["proves"] < PROVES_MOSTRA_PETITA:
        out.append(f"Mostra petita: {k['proves']} proves al període. Les conversions per model i talla poden "
                   "canviar molt amb poques proves més.")
    sense_hora = con.execute(
        """SELECT COUNT(*) FROM venda_linia WHERE ts IS NULL AND data >= :des AND data < :fins
           AND (:b IS NULL OR botiga_id = :b)""", base.params(f)).fetchone()[0]
    if sense_hora:
        out.append(f"Vendes per CSV sense hora: {sense_hora} línies només porten la data i s'atribueixen a "
                   "qualsevol prova del mateix GTIN aquell dia.")
    out.append("Compres atribuïdes: és una aproximació (mateix GTIN, mateixa botiga, el mateix dia després de "
               "la prova). No sabem si qui compra és qui ha provat.")
    total = k["proves"] + k["proves_ambigues"]
    if total and k["proves_ambigues"] / total > 0.1:
        out.append(f"{k['proves_ambigues']} proves ambigües ({base.pct_txt(k['proves_ambigues'] / total)}) no "
                   "s'han comptat: lectures que podien ser de la cabina del costat.")
    if k["respostes_motiu"] and (k["taxa_resposta_motiu"] or 0) < TAXA_MOTIU_BAIXA:
        out.append(f"Motius: només respon el {base.pct_txt(k['taxa_resposta_motiu'])} de les sessions de fitxa; "
                   "no representen tots els clients.")
    return out


def _avis_experiment(e: dict | None) -> list[str]:
    if e is None:
        return ["Efecte de l'origen: no hi ha cap experiment amb grup de control; no en podem dir res."]
    if not e["mostra_suficient"] or e["p_valor"] is None or e["p_valor"] >= exp_mod.ALFA:
        return [f"No podem afirmar que «{e['variable']}» faci vendre més: {e['conclusio'][0].lower()}{e['conclusio'][1:]}"]
    return []


def _avis_valor() -> str:
    return "Els euros són estimacions amb els paràmetres de la marca (marge, quota...); no són resultats."


def _avis_estoc(con, f) -> list[str]:
    out = []
    if not con.execute("SELECT 1 FROM estoc WHERE (:b IS NULL OR botiga_id = :b) LIMIT 1", {"b": f.botiga_id}).fetchone():
        out.append("Sense dades d'estoc: no es poden calcular l'estoc parat ni el risc de rebaixa.")
    primera = con.execute(
        """SELECT MIN(s.inici) FROM sessio s JOIN cabina c ON c.id = s.cabina_id
           WHERE (:b IS NULL OR c.botiga_id = :b)""", {"b": f.botiga_id}).fetchone()[0]
    dies = base.par(con, f, "dies_estoc_parat")
    if primera:
        tenim = (f.fins - base.dt(primera).date()).days + 1
        if tenim < dies:
            out.append(f"Estoc parat: només hi ha {tenim} dies de proves (la regla en demana {dies}); "
                       "una peça «parada» potser només és nova.")
    return out


# ---------------------------------------------------------------- Blocs per tipus


def _diari(con, f, k):
    al = alertes_mod.alertes(con, f)["alertes"]
    per_tipus = Counter(a["tipus"] for a in al)
    text_al = (", ".join(f"{n} {t.replace('_', ' ')}" for t, n in per_tipus.most_common()) or "Cap alerta oberta") + "."
    return [_xifres(k, "Ahir"),
            _bloc("alertes", "Alertes", text_al, al),
            _servei(con, f)], []


def _setmanal(con, f, k):
    t = talles_mod.talles(con, f)
    return [_xifres(k), _molt_provat(models_mod.taula_models(con, f)), _talla_no_quadra(t),
            _demanda(con, f), _motius(con, f), _servei(con, f)], []


def _mensual(con, f, k):
    t = talles_mod.talles(con, f)
    ant = {(r["categoria"], r["talla"]): r["conversio"]
           for r in talles_mod.taula_categoria_talla(base.proves_valides(con, base.anterior(f)))}
    taula = [dict(r, conversio_anterior=ant.get((r["categoria"], r["talla"])),
                  tendencia=base.resta(r["conversio"], ant.get((r["categoria"], r["talla"])))) for r in t["taula"]]
    pujen = [r for r in taula if (r["tendencia"] or 0) >= 0.05]
    baixen = [r for r in taula if (r["tendencia"] or 0) <= -0.05]
    if any(r["tendencia"] is not None for r in taula):
        text_tend = (f"{len(pujen)} combinacions de categoria i talla pugen 5 punts o més respecte del període "
                     f"anterior; {len(baixen)} en baixen.")
    else:
        text_tend = "Sense dades del període anterior per comparar la tendència."
    e = estoc_mod.estoc(con, f)
    fx = nfc_mod.fitxa_nfc(con, f)
    v = valor_mod.valor(con, f)
    amb_euros = [p for p in v["palanques"] if p["valor_eur"]]
    blocs = [
        _decisions(con, f),
        _bloc("conversio_categoria_talla", "Conversió per categoria i talla",
              text_tend, taula),
        _corba(t),
        _bloc("estoc", "Estoc parat i risc de rebaixa",
              f"{len(e['parat'])} variants sense cap prova ni venda en {base.par(con, f, 'dies_estoc_parat')} dies "
              f"({sum(p['unitats'] for p in e['parat'])} u.); "
              f"{base.plural(len(e['risc_rebaixa']), 'model', 'models')} amb risc de rebaixa.", e),
        _bloc("fitxa_nfc", "Fitxa NFC i idiomes",
              f"{fx['tocs']} tocs ({base.num_txt(fx['tocs_per_sessio'])} per sessió de cabina). Idioma principal: "
              f"{fx['idiomes'][0]['idioma'] if fx['idiomes'] else '—'}.", fx),
        _prova_en_curs(con, f),
        _bloc("valor", "Valor estimat",
              "Estimació (no resultat): " + "; ".join(f"{p['palanca'].lower()} {base.num_txt(p['valor_eur'], 0)} €"
                                                      for p in amb_euros) + "." if amb_euros
              else "Encara no hi ha dades per estimar cap palanca en euros.", v),
    ]
    return blocs, [_avis_valor()] + _avis_estoc(con, f) + _avis_experiment(exp_mod.efecte_origen(con, f))


def _feedback_disseny(con, f) -> dict:
    """Insight 22: conversió i motius agregats per atribut de la peça (forma, teixit, color, composició)."""
    info = base.info_models(con)
    proves = base.proves_valides(con, f)
    motius_model: dict[str, Counter] = defaultdict(Counter)
    for e in base.nfc(con, f, "motiu_no_compra"):
        motius_model[e["model"]][e["valor"]] += 1

    def atributs(model: str) -> dict:
        i = info.get(model, {})
        o = i.get("origen") or {}
        comp = sorted(o.get("composicio", []), key=lambda c: -(c.get("pct") or 0))
        material = comp[0]["material"] if comp else None
        if isinstance(material, dict):
            material = material.get("ca")
        return {"forma": i.get("categoria"), "teixit": o.get("textura"), "color": i.get("color"), "composicio": material}

    per: dict[str, dict] = {a: defaultdict(lambda: [0, 0, Counter()]) for a in ("forma", "teixit", "color", "composicio")}
    for p in proves:
        if not p["model"]:
            continue
        for a, valor in atributs(p["model"]).items():
            if valor:
                per[a][valor][0] += 1
                per[a][valor][1] += p["venuda"]
    for model, c in motius_model.items():
        for a, valor in atributs(model).items():
            if valor and valor in per[a]:
                per[a][valor][2].update(c)
    dades = {a: [{"valor": v, "proves": n, "compres": c, "conversio": base.frac(c, n),
                  "motiu_principal": m.most_common(1)[0][0] if m else None}
                 for v, (n, c, m) in sorted(vals.items(), key=lambda kv: -kv[1][0])]
             for a, vals in per.items()}
    pitjor = min((r for r in dades["teixit"] if r["proves"] >= 20), key=lambda r: r["conversio"] or 0, default=None)
    text = (f"El teixit que menys converteix és {pitjor['valor']} ({base.pct_txt(pitjor['conversio'])}"
            + (f"; motiu més citat: {pitjor['motiu_principal']}" if pitjor["motiu_principal"] else "") + ")."
            if pitjor else "Encara no hi ha prou proves per atribut.")
    return _bloc("feedback_disseny", "Feedback de disseny", text, dades)


def _temporada(con, f, k):
    taula = models_mod.taula_models(con, f)
    per_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for m in taula:
        per_cat[m["categoria"] or "?"][0] += m["proves"]
        per_cat[m["categoria"] or "?"][1] += m["compres"]
    families = sorted(({"categoria": c, "proves": n, "compres": v, "conversio": base.frac(v, n)}
                       for c, (n, v) in per_cat.items()), key=lambda r: -(r["conversio"] or 0))
    ranquing = sorted(({c: m[c] for c in ("model", "nom", "categoria", "proves", "compres", "conversio")}
                       for m in taula if m["proves"]), key=lambda r: -(r["conversio"] or 0))
    t = talles_mod.talles(con, f)
    e = exp_mod.efecte_origen(con, f)
    info = base.info_models(con)
    paisos: Counter = Counter()
    for v in base.vendes(con, f):
        paisos[models_mod.pais_confeccio(info.get(v["model"], {}).get("origen")) or "desconegut"] += v["quantitat"]
    paisos_llista = [{"pais": p, "unitats": n} for p, n in paisos.most_common()]
    blocs = [
        _bloc("ranquing", "Rànquing per família i model",
              (f"La família que més converteix és {families[0]['categoria']} ({base.pct_txt(families[0]['conversio'])}); "
               f"el model, «{ranquing[0]['nom']}» ({base.pct_txt(ranquing[0]['conversio'])}).") if ranquing
              else "Cap prova al període.", {"families": families, "models": ranquing}),
        _feedback_disseny(con, f),
        _corba(t),
        _bloc("efecte_origen", "Efecte de l'origen", e["conclusio"] if e else "Cap experiment d'origen.", e),
        _demanda(con, f),
        _bloc("pais_fabricacio", "Unitats per país de fabricació",
              ", ".join(f"{p['pais']} {p['unitats']} u." for p in paisos_llista) or "Cap venda al període.",
              paisos_llista),
    ]
    return blocs, _avis_experiment(e)


def _criteris(con, f, k) -> dict:
    fila = con.execute("SELECT * FROM pilot WHERE botiga_id = ?", (f.botiga_id,)).fetchone() if f.botiga_id else None
    criteris = json.loads(fila["criteris_json"]) if fila else []
    fx = nfc_mod.fitxa_nfc(con, f)
    pr = estoc_mod.precisio(con, f)
    e = exp_mod.efecte_origen(con, f)
    total = k["proves"] + k["proves_ambigues"]
    metriques = dict(k, pct_proves_valides=base.frac(k["proves"], total), tocs_per_sessio=fx["tocs_per_sessio"],
                     error_estoc_pct=pr["error_mitja_pct"] if pr else None,
                     diferencia_origen=e["diferencia"] if e else None, p_valor_origen=e["p_valor"] if e else None)
    comparadors = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
                   "<": lambda a, b: a < b, "==": lambda a, b: a == b}
    files = []
    for c in criteris:
        valor = metriques.get(c.get("metrica"))
        comp = comparadors.get(c.get("comparador", ">="))
        compleix = None if valor is None or comp is None else bool(comp(valor, c.get("objectiu")))
        files.append(dict(c, valor=valor, compleix=compleix))
    fets = sum(1 for c in files if c["compleix"])
    text = (f"Es compleixen {fets} de {len(files)} criteris d'èxit." if files
            else "El pilot no té criteris d'èxit definits (taula pilot).")
    return _bloc("criteris", "Criteris d'èxit", text, files)


def _pilot(con, f, k):
    fila = con.execute("SELECT taxa_error_observacio FROM pilot WHERE botiga_id = ?", (f.botiga_id,)).fetchone() \
        if f.botiga_id else None
    p = base.params(f)
    sense_cataleg = con.execute(
        """SELECT COUNT(*) FROM prova pr JOIN sessio s ON s.id = pr.sessio_id JOIN cabina c ON c.id = s.cabina_id
           WHERE pr.gtin IS NULL AND s.inici >= :des AND s.inici < :fins AND (:b IS NULL OR c.botiga_id = :b)""",
        p).fetchone()[0]
    linies = con.execute(
        """SELECT COUNT(*), SUM(ts IS NULL) FROM venda_linia WHERE data >= :des AND data < :fins
           AND (:b IS NULL OR botiga_id = :b)""", p).fetchone()
    total = k["proves"] + k["proves_ambigues"]
    qualitat = {"pct_ambigues": base.frac(k["proves_ambigues"], total), "proves_sense_cataleg": sense_cataleg,
                "taxa_error_observacio": fila["taxa_error_observacio"] if fila else None,
                "linies_venda": linies[0], "pct_vendes_sense_hora": base.frac(linies[1] or 0, linies[0])}
    wil = estadistica.wilson(k["compres_atribuides"], k["proves"])
    pc = {c: k[c] for c in ("proves", "compres_atribuides", "conversio", "unitats_venudes", "venut_sense_provar")}
    pc["conversio_ic95"] = [round(x, 3) for x in wil] if wil else None
    pr = estoc_mod.precisio(con, f)
    e = exp_mod.efecte_origen(con, f)
    no_podem = [
        "Que qui compra sigui qui ha provat: l'atribució és per GTIN i dia, no per persona.",
        "Per què no compra qui no respon la fitxa: els motius només són de qui respon.",
    ] + _avis_experiment(e)
    if (qualitat["taxa_error_observacio"] or 0) > 0:
        no_podem.append(f"Que cada prova sigui exacta: a l'observació manual el sistema s'equivoca en un "
                        f"{base.pct_txt(qualitat['taxa_error_observacio'])} dels casos.")
    blocs = [
        _criteris(con, f, k),
        _bloc("qualitat_dada", "Qualitat de la dada",
              f"{base.pct_txt(qualitat['pct_ambigues'])} de proves ambigües (no comptades), {sense_cataleg} proves "
              f"d'etiquetes fora del catàleg, {base.pct_txt(qualitat['pct_vendes_sense_hora'])} de vendes sense hora.",
              qualitat),
        _bloc("proves_compra", "Proves contra compra",
              f"{k['proves']} proves i {k['compres_atribuides']} compres: conversió {base.pct_txt(k['conversio'])}"
              + (f" (IC del 95 %: {base.pct_txt(wil[0])} a {base.pct_txt(wil[1])})." if wil else "."), pc),
        _decisions(con, f),
        _bloc("precisio_estoc", "Precisió d'estoc de la zona",
              f"{pr['recomptes']} recomptes; l'RFID s'aparta del recompte manual un {base.pct_txt(pr['error_mitja_pct'])}."
              if pr else "Cap recompte manual registrat.", pr),
        _bloc("no_podem_afirmar", "Què no podem afirmar", " ".join(no_podem), no_podem),
    ]
    return blocs, []


def _mango(con, f, k):
    fx = nfc_mod.fitxa_nfc(con, f)
    e = exp_mod.efecte_origen(con, f)
    s = servei_mod.servei(con, f)
    dossier = {c: k[c] for c in ("proves", "conversio", "venut_sense_provar_pct", "temps_resposta_mediana_s",
                                 "demanda_perduda", "peces_abandonades")}
    dossier["peticions_per_sessio"] = s["peticions_per_sessio"]
    dossier["tocs_per_sessio"] = fx["tocs_per_sessio"]
    # Últim metre: de les sessions de fitxa dels dies amb l'origen visible, quantes l'obren.
    grups = exp_mod.grup_origen_per_dia(con, f)
    obren = {e_["sessio_nfc"] for e_ in base.nfc(con, f, "obre_fitxa") if grups.get(e_["ts"][:10]) != "sense"}
    veuen = {e_["sessio_nfc"] for e_ in base.nfc(con, f, "veu_origen")} & obren
    ultim = {"sessions_fitxa_amb_origen": len(obren), "veuen_origen": len(veuen),
             "pct_veuen_origen": base.frac(len(veuen), len(obren)), "idiomes": fx["idiomes"], "experiment": e}
    blocs = [
        _bloc("kpi", "KPI del dossier",
              f"{k['proves']} proves, conversió {base.pct_txt(k['conversio'])}, "
              f"{base.num_txt(fx['tocs_per_sessio'])} tocs de fitxa per sessió, resposta mediana "
              f"{k['temps_resposta_mediana_s'] if k['temps_resposta_mediana_s'] is not None else '—'} s.", dossier),
        _bloc("ultim_metre", "L'últim metre de l'origen",
              f"El {base.pct_txt(ultim['pct_veuen_origen'])} de les sessions de fitxa amb l'origen visible l'obren. "
              + (e["conclusio"] if e else "Sense grup de control, no en sabem l'efecte en la compra."), ultim),
    ]
    return blocs, _avis_experiment(e)


_BLOCS = {"diari": _diari, "setmanal": _setmanal, "mensual": _mensual, "temporada": _temporada,
          "pilot": _pilot, "mango": _mango}


def _accio_reserva(tipus: str, f: Filtre) -> dict:
    limit = f.fins + timedelta(days=DIES_LIMIT[tipus])
    if tipus in ("pilot", "mango"):
        return base.accio("Decidir si es continua el pilot amb els criteris d'èxit d'aquest informe a la mà.",
                          "pilot", None, "CEO", limit)
    return base.accio("Cap senyal clar: confirmar amb la botiga que hi ha estoc de la talla més demanada "
                      "per a la setmana vinent.", "servei", None, "BOT", limit)


def informe(con: sqlite3.Connection, f: Filtre, tipus: str) -> dict:
    """`GET /informes/{tipus}`. ValueError si el tipus no existeix (l'API respon 404)."""
    if tipus not in _BLOCS:
        raise ValueError(f"Tipus d'informe desconegut: {tipus}")
    if tipus == "diari":
        f = Filtre(f.botiga_id, f.fins, f.fins)
    k = resum_mod.kpi(con, f)
    blocs, avisos_tipus = _BLOCS[tipus](con, f, k)
    acc = resum_mod.accio_principal(con, f, DIES_LIMIT[tipus]) or _accio_reserva(tipus, f)
    inf = {"tipus": tipus, "titol": TITOLS[tipus], "periode": base.periode(f), "blocs": blocs,
           "accio": acc, "avisos": avisos(con, f, k) + avisos_tipus}
    # v0.3: xifres amb variació, gràfics (els mateixos al tauler i al PDF) i alguns blocs nous.
    return informes_grafics.enriqueix(con, f, tipus, k, inf)
