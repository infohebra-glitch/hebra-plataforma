"""Sessions de provador (especificació v0.3, C): què es prova junt i quan hi ha dubte de talla.

Població: les sessions de cabina del període amb almenys una prova vàlida (confiança
alta o mitjana). Una sessió sense cap prova vàlida no diu res de què s'ha provat.

Definicions:
  * Peces per sessió: EPC diferents amb prova vàlida a la sessió.
  * Sessió amb compra: alguna de les seves proves té venda atribuïda.
  * Unitats comprades: proves de la sessió amb venda atribuïda.
  * Provades juntes: parells de models a la mateixa sessió (mínim `MIN_SESSIONS_PARELL`).
    Lift = P(A i B a la mateixa sessió) / (P(A)·P(B)), amb P sobre les sessions del període.
    `conversio_conjunta` = sessions on s'han comprat tots dos ÷ sessions on s'han provat junts
    (i `conversio_alguna`, on se n'ha comprat almenys un).
  * Mateix model, diferent talla: a la sessió hi ha dos o més GTIN del mateix model i color
    amb talles diferents. «comprada» diu quina talla s'ha comprat (venda atribuïda) o «cap».
    Si se n'han comprat dues, compten totes dues.
  * `mostra_petita` a cada fila amb menys de `MOSTRA_PETITA` sessions.
"""

import sqlite3
from collections import Counter, defaultdict
from itertools import combinations

from . import Filtre, base

MOSTRA_PETITA = 10
MIN_SESSIONS_PARELL = 3
MAX_PARELLS = 20
TRAMS_PECES = ("1", "2", "3", "4", "5+")
TRAMS_DURADA = (("<2 min", 0, 120), ("2-5 min", 120, 300), ("5-10 min", 300, 600), (">10 min", 600, float("inf")))


class _Sessio:
    __slots__ = ("id", "inici", "durada_s", "epcs", "venudes", "models", "per_variant")

    def __init__(self, sid: int, inici: str, fi: str):
        self.id, self.inici = sid, inici
        self.durada_s = (base.dt(fi) - base.dt(inici)).total_seconds()
        self.epcs: set[str] = set()
        self.venudes = 0
        self.models: dict[str, bool] = {}  # model -> s'ha comprat a la sessió
        # (model, color) -> {talla: comprada}
        self.per_variant: dict[tuple, dict[str, bool]] = defaultdict(dict)

    @property
    def amb_compra(self) -> bool:
        return self.venudes > 0


def _sessions(con: sqlite3.Connection, f: Filtre) -> list[_Sessio]:
    sess: dict[int, _Sessio] = {}
    for p in base.proves_valides(con, f):
        s = sess.get(p["sessio_id"])
        if s is None:
            s = sess[p["sessio_id"]] = _Sessio(p["sessio_id"], p["inici"], p["fi"])
        if p["epc"] not in s.epcs:
            s.epcs.add(p["epc"])
            s.venudes += p["venuda"]
        if p["model"]:
            s.models[p["model"]] = s.models.get(p["model"], False) or bool(p["venuda"])
            talles = s.per_variant[(p["model"], p["color"])]
            talles[p["talla"]] = talles.get(p["talla"], False) or bool(p["venuda"])
    return sorted(sess.values(), key=lambda s: (s.inici, s.id))


def _petita(n: int) -> bool:
    return n < MOSTRA_PETITA


def _dubtes(sess: list[_Sessio]) -> list[tuple[_Sessio, str, str, list[str]]]:
    """(sessió, model, color, talles ordenades) per a cada model provat en dues talles o més a la sessió."""
    out = []
    for s in sess:
        for (model, color), talles in s.per_variant.items():
            if len(talles) >= 2:
                out.append((s, model, color, sorted(talles, key=base.ordre_talla)))
    return out


def _parells_talla(dubtes: list, info: dict, model: str | None = None) -> list[dict]:
    grups: dict[tuple, list] = defaultdict(list)
    for s, m, color, talles in dubtes:
        if model is None or m == model:
            grups[(m, color, "+".join(talles))].append((s, m, color, talles))
    files = []
    for (m, color, combinacio), llista in grups.items():
        comprada: Counter = Counter({t: 0 for t in llista[0][3]})
        comprada["cap"] = 0
        for s, _, _, talles in llista:
            compres = [t for t in talles if s.per_variant[(m, color)][t]]
            for t in compres:
                comprada[t] += 1
            if not compres:
                comprada["cap"] += 1
        files.append({"model": m, "nom": base.nom_model(info, m), "color": color, "talles": combinacio,
                      "sessions": len(llista), "comprada": dict(comprada), "mostra_petita": _petita(len(llista))})
    files.sort(key=lambda r: (-r["sessions"], r["model"], r["talles"]))
    return files


def _resum_model(sess: list[_Sessio], dubtes: list, model: str) -> dict:
    """Dubte de talla d'un model: sessions amb dubte, % sobre les sessions del model i talla més comprada."""
    sessions_model = sum(1 for s in sess if model in s.models)
    amb_dubte = [(s, color, talles) for s, m, color, talles in dubtes if m == model]
    ids = {s.id for s, _, _ in amb_dubte}
    compres: Counter = Counter()
    for s, color, talles in amb_dubte:
        for t in talles:
            compres[t] += s.per_variant[(model, color)][t]
    top = [t for t, n in compres.most_common() if n > 0]
    return {"sessions_dubte": len(ids), "sessions_model": sessions_model,
            "pct_sessions_model": base.frac(len(ids), sessions_model),
            "talla_mes_comprada": top[0] if top else None, "mostra_petita": _petita(len(ids))}


def sessions(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /sessions`: peces per sessió, models provats junts, dubte de talla, durada i hora."""
    info = base.info_models(con)
    sess = _sessions(con, f)
    n = len(sess)
    peces = [len(s.epcs) for s in sess]
    mediana = base.mediana(peces)

    # Per nombre de peces
    trams: dict[str, list[_Sessio]] = {t: [] for t in TRAMS_PECES}
    for s in sess:
        trams[TRAMS_PECES[min(len(s.epcs), 5) - 1]].append(s)
    per_nombre = [{"peces": t, "sessions": len(ss), "amb_compra": sum(s.amb_compra for s in ss),
                   "conversio_sessio": base.frac(sum(s.amb_compra for s in ss), len(ss)),
                   "unitats_comprades": sum(s.venudes for s in ss), "mostra_petita": _petita(len(ss))}
                  for t, ss in trams.items()]

    # Provades juntes
    per_model: Counter = Counter()
    junts: dict[tuple, list[_Sessio]] = defaultdict(list)
    for s in sess:
        ms = sorted(s.models)
        per_model.update(ms)
        for a, b in combinations(ms, 2):
            junts[(a, b)].append(s)
    parells = []
    for (a, b), ss in junts.items():
        k = len(ss)
        if k < MIN_SESSIONS_PARELL:
            continue
        parells.append({"model_a": a, "nom_a": base.nom_model(info, a), "model_b": b, "nom_b": base.nom_model(info, b),
                        "sessions": k, "lift": round(k * n / (per_model[a] * per_model[b]), 2),
                        "conversio_conjunta": base.frac(sum(1 for s in ss if s.models[a] and s.models[b]), k),
                        "conversio_alguna": base.frac(sum(1 for s in ss if s.models[a] or s.models[b]), k),
                        "mostra_petita": _petita(k)})
    parells.sort(key=lambda r: (-r["sessions"], -r["lift"], r["model_a"], r["model_b"]))

    # Mateix model, diferent talla
    dubtes = _dubtes(sess)
    ids_dubte = {s.id for s, *_ in dubtes}
    models_dubte = sorted({m for _, m, _, _ in dubtes})
    per_model_dubte = []
    for m in models_dubte:
        r = _resum_model(sess, dubtes, m)
        per_model_dubte.append({"model": m, "nom": base.nom_model(info, m), "sessions_dubte": r["sessions_dubte"],
                                "pct_sessions_model": r["pct_sessions_model"],
                                "talla_mes_comprada": r["talla_mes_comprada"], "mostra_petita": r["mostra_petita"]})
    per_model_dubte.sort(key=lambda r: (-r["sessions_dubte"], r["model"]))

    # Per durada i per hora
    per_durada = []
    for nom, des, fins in TRAMS_DURADA:
        ss = [s for s in sess if des <= s.durada_s < fins]
        per_durada.append({"tram": nom, "sessions": len(ss),
                           "conversio_sessio": base.frac(sum(s.amb_compra for s in ss), len(ss)),
                           "mostra_petita": _petita(len(ss))})
    hores: dict[int, list[_Sessio]] = defaultdict(list)
    for s in sess:
        hores[base.dt(s.inici).hour].append(s)
    per_hora = [{"hora": h, "sessions": len(ss), "conversio_sessio": base.frac(sum(s.amb_compra for s in ss), len(ss)),
                 "mostra_petita": _petita(len(ss))} for h, ss in sorted(hores.items())]

    return {
        "periode": base.periode(f),
        "kpi": {"sessions": n,
                "peces_per_sessio_mitjana": round(sum(peces) / n, 2) if n else None,
                "peces_per_sessio_mediana": mediana,
                "durada_mitjana_s": round(sum(s.durada_s for s in sess) / n) if n else None,
                "pct_sessions_amb_compra": base.frac(sum(s.amb_compra for s in sess), n),
                "mostra_petita": _petita(n)},
        "per_nombre_peces": per_nombre,
        "provades_juntes": parells[:MAX_PARELLS],
        "mateix_model_diferent_talla": {
            "sessions": len(ids_dubte), "pct_sessions": base.frac(len(ids_dubte), n),
            "parells_talla": _parells_talla(dubtes, info), "per_model": per_model_dubte},
        "per_durada": per_durada,
        "per_hora": per_hora,
    }


def dubte_talla_model(con: sqlite3.Connection, f: Filtre, model: str) -> dict | None:
    """Bloc «Dubte de talla» de la fitxa d'un model (`model_detall.dubte_talla`). None si el model no s'ha provat."""
    sess = _sessions(con, f)
    dubtes = _dubtes(sess)
    r = _resum_model(sess, dubtes, model)
    if not r["sessions_model"]:
        return None
    parells = [{k: p[k] for k in ("color", "talles", "sessions", "comprada", "mostra_petita")}
               for p in _parells_talla(dubtes, base.info_models(con), model)]
    return {"sessions": r["sessions_dubte"], "sessions_model": r["sessions_model"],
            "pct_sessions_model": r["pct_sessions_model"], "talla_mes_comprada": r["talla_mes_comprada"],
            "mostra_petita": r["mostra_petita"], "parells_talla": parells}
