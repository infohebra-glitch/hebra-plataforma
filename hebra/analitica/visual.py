"""`GET /panorama` (v0.5): les dades dels gràfics del tauler «Panorama», a la manera de les eines del
sector (Sensormatic Fitting Room 360, Crave, Nedap iD Cloud): de la peça tocada a la peça venuda,
quan s'omplen els provadors, quines categories converteixen, quanta estona s'hi passa i quines
peces (amb la seva foto) mouen la botiga.

Tot surt de les mateixes taules que la resta del tauler (proves de confiança alta i mitjana).
"""

import sqlite3
from collections import Counter, defaultdict
from datetime import timedelta

from . import Filtre, base

HORES = list(range(9, 22))               # 9 h - 21 h (franja de botiga)
TRAMS_MINUTS = [(0, 3), (3, 6), (6, 10), (10, 15), (15, 25), (25, None)]


def _hora_local(text: str):
    return base.dt(text)


def panorama(con: sqlite3.Connection, f: Filtre) -> dict:
    from hebra import imatges

    proves = base.proves_valides(con, f)
    info = base.info_models(con)
    res = imatges.Resolutor(con)
    vendes = base.vendes(con, f)
    pet = base.peticions(con, f)

    # 1. Embut: tocs a la fitxa NFC -> proves -> compres després de provar
    tocs = len({e["sessio_nfc"] for e in base.nfc(con, f, "obre_fitxa")})
    compres = sum(p["venuda"] for p in proves)
    embut = [
        {"clau": "tocs", "nom": "Tocs a la fitxa NFC", "n": tocs},
        {"clau": "proves", "nom": "Peces provades", "n": len(proves)},
        {"clau": "peticions", "nom": "Peticions de talla", "n": len(pet)},
        {"clau": "compres", "nom": "Compres després de provar", "n": compres},
    ]

    # 2. Mapa de calor: proves per dia de la setmana i hora
    calor = [[0] * len(HORES) for _ in range(7)]
    for p in proves:
        t = _hora_local(p["inici"])
        if t.hour in HORES:
            calor[t.weekday()][HORES.index(t.hour)] += 1

    # 3. Conversió per categoria
    cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for p in proves:
        c = p["categoria"] or "sense catàleg"
        cat[c][0] += 1
        cat[c][1] += p["venuda"]
    per_categoria = sorted(({"categoria": c, "proves": n, "compres": v, "conversio": base.frac(v, n)}
                            for c, (n, v) in cat.items()), key=lambda r: -r["proves"])

    # 4. Temps a la cabina (durada de les sessions amb alguna prova) i peces per sessió
    sess = {p["sessio_id"]: (p["inici"], p["fi"]) for p in proves}
    trams = [0] * len(TRAMS_MINUTS)
    minuts = []
    for ini, fi in sess.values():
        m = (base.dt(fi) - base.dt(ini)).total_seconds() / 60
        minuts.append(m)
        for i, (a, b) in enumerate(TRAMS_MINUTS):
            if m >= a and (b is None or m < b):
                trams[i] += 1
                break
    per_sessio = Counter(Counter(p["sessio_id"] for p in proves).values())
    peces_sessio = [{"peces": k if k < 5 else "5+", "sessions": 0} for k in range(1, 6)]
    for k, n in per_sessio.items():
        peces_sessio[min(k, 5) - 1]["sessions"] += n

    # 5. Peces (amb foto): proves, compres, conversió i tendència diària
    dies = []
    d = f.des
    while d <= f.fins:
        dies.append(d.isoformat())
        d += timedelta(days=1)
    idx = {x: i for i, x in enumerate(dies)}
    pm: dict[str, dict] = {}
    for p in proves:
        if not p["model"]:
            continue
        r = pm.setdefault(p["model"], {"proves": 0, "compres": 0, "serie": [0] * len(dies)})
        r["proves"] += 1
        r["compres"] += p["venuda"]
        i = idx.get(p["inici"][:10])
        if i is not None:
            r["serie"][i] += 1
    venudes = Counter()
    ingressos = Counter()
    for v in vendes:
        if v["model"]:
            venudes[v["model"]] += v["quantitat"]
            ingressos[v["model"]] += v["import_eur"] or 0
    estoc = base.estoc_per_gtin(con, f.botiga_id)
    setm = max(base.setmanes(f), 1 / 7)
    peces = []
    for m in set(pm) | set(venudes):
        i = info.get(m, {"nom": m, "categoria": None, "color": None, "preu": None, "gtins": []})
        r = pm.get(m, {"proves": 0, "compres": 0, "serie": [0] * len(dies)})
        e = base.estoc_de(estoc, i["gtins"])
        ritme = venudes[m] / setm
        peces.append({
            "model": m, "nom": i["nom"], "categoria": i["categoria"], "color": i["color"], "preu": i["preu"],
            "imatge": res.de(m, i["color"], i["categoria"], i["nom"])["url"],
            "proves": r["proves"], "compres": r["compres"], "conversio": base.frac(r["compres"], r["proves"]),
            "unitats_venudes": venudes[m], "ingressos": round(ingressos[m], 2), "estoc": e,
            "cobertura_setmanes": round(e / ritme, 1) if e is not None and ritme > 0 else None,
            "serie": r["serie"],
        })
    peces.sort(key=lambda x: (-x["proves"], -x["unitats_venudes"], x["model"]))

    # 6. Motius de no compra (tots els models)
    motius = Counter(e["valor"] for e in base.nfc(con, f, "motiu_no_compra"))
    total_motius = sum(motius.values())

    return {
        "periode": base.periode(f),
        "dies": dies,
        "embut": embut,
        "mapa_calor": {"hores": HORES, "dies_setmana": ["dl", "dt", "dc", "dj", "dv", "ds", "dg"], "proves": calor},
        "per_categoria": per_categoria,
        "temps_cabina": {"trams": [{"des": a, "fins": b, "sessions": n} for (a, b), n in zip(TRAMS_MINUTS, trams)],
                         "mediana_minuts": round(base.mediana(minuts), 1) if minuts else None},
        "peces_per_sessio": peces_sessio,
        "peces": peces,
        "motius": [{"motiu": k, "nom": base.nom_motiu(con, k), "n": v, "pct": base.frac(v, total_motius)}
                   for k, v in motius.most_common()],
    }
