"""Servei a la cabina: peticions, temps de resposta, ocupació i peces per sessió (insights 9-12).

  * Peticions de talla per sessió (9) = peticions ÷ sessions de cabina.
  * Temps de resposta (10): mediana de segons entre la petició i el lliurament
    (només les lliurades), i % per sota de 90 s.
  * Ocupació (11): `pct_temps_totes_plenes` = temps amb totes les cabines de la
    botiga ocupades ÷ temps obert. «Obert» és, per a cada dia, de la primera
    sessió a l'última (no coneixem l'horari real). El mapa reparteix aquest
    temps per dia de la setmana (0 = dilluns) i hora; `sessions` són les que
    hi comencen.
  * Peces per sessió (12): etiquetes diferents provades a la sessió (5 = 5 o
    més), i % de sessions amb alguna compra atribuïda.
"""

import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from . import Filtre, base

SEGONS_OBJECTIU = 90
MAX_PECES = 5


def _reparteix(a: datetime, b: datetime, acc: dict) -> None:
    """Suma a `acc[(dia_setmana, hora)]` els segons de l'interval [a, b) que cauen a cada hora."""
    while a < b:
        seguent = a.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        tram = min(b, seguent)
        acc[(a.weekday(), a.hour)] += (tram - a).total_seconds()
        a = tram


def ocupacio(con: sqlite3.Connection, sess: list) -> dict:
    cabines = dict(con.execute("SELECT botiga_id, COUNT(*) FROM cabina GROUP BY botiga_id").fetchall())
    per_dia: dict[tuple, list] = defaultdict(list)
    comencen: Counter = Counter()
    durades = []
    for s in sess:
        a, b = base.dt(s["inici"]), base.dt(s["fi"])
        per_dia[(s["botiga_id"], s["inici"][:10])].append((a, b))
        comencen[(a.weekday(), a.hour)] += 1
        durades.append((b - a).total_seconds())

    obert: dict = defaultdict(float)
    ple: dict = defaultdict(float)
    for (botiga, _), ints in per_dia.items():
        _reparteix(min(a for a, _ in ints), max(b for _, b in ints), obert)
        # Escombrada: +1 quan comença una sessió, -1 quan acaba (els finals primer si coincideixen).
        punts = sorted([(a, 1) for a, _ in ints] + [(b, -1) for _, b in ints])
        ocupades, anterior = 0, None
        for t, d in punts:
            if anterior is not None and t > anterior and ocupades >= cabines.get(botiga, 1):
                _reparteix(anterior, t, ple)
            ocupades += d
            anterior = t

    total_obert = sum(obert.values())
    mapa = [{"dia_setmana": d, "hora": h, "sessions": comencen[(d, h)],
             "pct_totes_plenes": base.frac(ple[(d, h)], obert[(d, h)])}
            for d, h in sorted(set(obert) | set(comencen))]
    return {
        "durada_mitjana_s": round(sum(durades) / len(durades)) if durades else None,
        "pct_temps_totes_plenes": base.frac(sum(ple.values()), total_obert),
        "mapa": mapa,
    }


def peces_per_sessio(proves: list) -> list[dict]:
    per_sessio: dict[int, set] = defaultdict(set)
    compra: dict[int, bool] = defaultdict(bool)
    for p in proves:
        per_sessio[p["sessio_id"]].add(p["epc"])
        compra[p["sessio_id"]] |= bool(p["venuda"])
    grups: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for s, epcs in per_sessio.items():
        g = grups[min(len(epcs), MAX_PECES)]
        g[0] += 1
        g[1] += compra[s]
    return [{"peces": k, "sessions": n, "pct_amb_compra": base.frac(c, n)} for k, (n, c) in sorted(grups.items())]


def temps_resposta(peticions: list) -> tuple[float | None, float | None]:
    """(mediana en segons, % lliurades per sota de 90 s)."""
    segons = [s for s in (base.segons_resposta(p) for p in peticions) if s is not None]
    med = base.mediana(segons)
    return (round(med) if med is not None else None,
            base.frac(sum(1 for s in segons if s < SEGONS_OBJECTIU), len(segons)))


def servei(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /servei`."""
    pet = base.peticions(con, f)
    sess = base.sessions(con, f)
    mediana, sota = temps_resposta(pet)
    estats = Counter(p["estat"] for p in pet)
    return {
        "peticions": len(pet),
        "peticions_per_sessio": base.frac(len(pet), len(sess), 2),
        "mediana_s": mediana,
        "pct_sota_90s": sota,
        "per_estat": {e: estats[e] for e in ("pendent", "en_cami", "lliurada", "no_disponible")},
        "ocupacio": ocupacio(con, sess),
        "peces_per_sessio": peces_per_sessio(base.proves_valides(con, f)),
    }
