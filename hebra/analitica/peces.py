"""Peça a peça: historial d'una etiqueta (insight 24) i senyals de pèrdua (insight 25).

Historial: proves (de qualsevol confiança, amb la cabina), venda atribuïda a
alguna de les seves proves, peces abandonades i esdeveniments de la fitxa NFC.
La fitxa NFC no guarda l'EPC, només el GTIN: un esdeveniment s'hi enganxa si és
del mateix GTIN i botiga DURANT una prova d'aquesta peça (és aproximat i el
detall ho diu).

Senyals de pèrdua (insight 25, només si el paràmetre `senyals_perdua` = 1):
etiquetes que entren a una cabina al període i després no es tornen a llegir
enlloc (ni lectures ni proves) ni s'han venut, i el darrer cop que es van veure
és com a mínim 24 h abans de la darrera dada de la botiga. Es compten per
cabina i hora; MAI per persona.
"""

import sqlite3
from collections import Counter
from datetime import timedelta

from . import Filtre, base

HORES_SENSE_VEURE = 24


def historial_peca(con: sqlite3.Connection, epc: str) -> dict | None:
    """`GET /peces/{epc}/historial`. None si l'EPC no és cap etiqueta ni té proves (l'API respon 404)."""
    etiqueta = con.execute("SELECT gtin FROM etiqueta WHERE epc = ?", (epc,)).fetchone()
    proves = con.execute(
        """SELECT p.id, p.gtin, p.confianca, p.durada_s, s.inici, s.fi, c.botiga_id, c.nom AS cabina
           FROM prova p JOIN sessio s ON s.id = p.sessio_id JOIN cabina c ON c.id = s.cabina_id
           WHERE p.epc = ? ORDER BY s.inici""", (epc,)).fetchall()
    if etiqueta is None and not proves:
        return None
    gtin = etiqueta["gtin"] if etiqueta else proves[0]["gtin"]
    k = con.execute("SELECT model, talla FROM catalog_sku WHERE gtin = ?", (gtin,)).fetchone()
    info = base.info_models(con)

    events = []
    for p in proves:
        events.append({"ts": p["inici"], "tipus": "prova",
                       "detall": f"{p['cabina']} · {round(p['durada_s'])} s · confiança {p['confianca']}"})
        for e in con.execute(
                """SELECT ts, tipus, valor FROM esdeveniment_nfc
                   WHERE gtin = ? AND botiga_id = ? AND ts >= ? AND ts <= ? ORDER BY ts""",
                (p["gtin"], p["botiga_id"], p["inici"], p["fi"])):
            valor = f" ({e['valor']})" if e["valor"] else ""
            events.append({"ts": e["ts"], "tipus": "nfc",
                           "detall": f"{e['tipus']}{valor} · aproximat: mateix GTIN durant la prova"})
    ids = [p["id"] for p in proves]
    if ids:
        for v in con.execute(
                f"""SELECT v.ts, v.data, v.import_eur, a.regla FROM atribucio a JOIN venda_linia v ON v.id = a.venda_id
                    WHERE a.prova_id IN ({','.join('?' * len(ids))})""", ids):
            imp = f" · {base.num_txt(v['import_eur'])} €" if v["import_eur"] is not None else ""
            events.append({"ts": v["ts"] or v["data"], "tipus": "venda", "detall": f"Venda atribuïda ({v['regla']}){imp}"})
    for a in con.execute(
            """SELECT pa.detectada, pa.resolta, c.nom FROM peca_abandonada pa JOIN cabina c ON c.id = pa.cabina_id
               WHERE pa.epc = ?""", (epc,)):
        estat = f"resolta {a['resolta']}" if a["resolta"] else "no resolta"
        events.append({"ts": a["detectada"], "tipus": "abandonada", "detall": f"{a['nom']} · {estat}"})
    events.sort(key=lambda e: e["ts"])
    return {"epc": epc, "gtin": gtin, "model": k["model"] if k else None,
            "nom": base.nom_model(info, k["model"]) if k else None,
            "talla": k["talla"] if k else None, "esdeveniments": events}


def perdues(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /perdues`. Si el paràmetre no és actiu, no es calcula res."""
    if base.par(con, f, "senyals_perdua") != 1:
        return {"actiu": False, "per_zona_hora": [], "total": 0}
    p = base.params(f)
    darrera_dada = con.execute(
        "SELECT MAX(s.fi) FROM sessio s JOIN cabina c ON c.id = s.cabina_id WHERE (:b IS NULL OR c.botiga_id = :b)",
        p).fetchone()[0]
    if not darrera_dada:
        return {"actiu": True, "per_zona_hora": [], "total": 0}
    limit = base.dt(darrera_dada) - timedelta(hours=HORES_SENSE_VEURE)

    # Darrera prova de cada EPC provat al període (de qualsevol període posterior també).
    darrera: dict[str, tuple] = {}
    for r in con.execute(
            """SELECT p.epc, s.fi, s.cabina_id FROM prova p JOIN sessio s ON s.id = p.sessio_id
               WHERE p.epc IN (SELECT p2.epc FROM prova p2 JOIN sessio s2 ON s2.id = p2.sessio_id
                               JOIN cabina c2 ON c2.id = s2.cabina_id
                               WHERE s2.inici >= :des AND s2.inici < :fins AND (:b IS NULL OR c2.botiga_id = :b))""", p):
        if r["epc"] not in darrera or base.dt(r["fi"]) > darrera[r["epc"]][0]:
            darrera[r["epc"]] = (base.dt(r["fi"]), r["cabina_id"])
    venuts = {r[0] for r in con.execute("SELECT DISTINCT p.epc FROM atribucio a JOIN prova p ON p.id = a.prova_id")}
    lectures = {r[0]: base.dt(r[1]) for r in con.execute("SELECT epc, MAX(fi) FROM lectura_agregada GROUP BY epc")}

    per: Counter = Counter()
    for epc, (fi, cabina) in darrera.items():
        vista = max(fi, lectures.get(epc, fi))
        if epc in venuts or vista > fi + timedelta(minutes=1) or fi > limit or not (f.des <= fi.date() <= f.fins):
            continue
        per[(cabina, fi.hour)] += 1
    return {"actiu": True,
            "per_zona_hora": [{"cabina": c, "hora": h, "n": n} for (c, h), n in sorted(per.items())],
            "total": sum(per.values())}
