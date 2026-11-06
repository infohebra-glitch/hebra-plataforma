"""Desa el que porten els connectors a les taules de sempre (catalog_sku, venda_linia, estoc).

Les vendes fan servir el mateix xifrat de tiquet que `vendes.py` (`<proveïdor>:<id>`): un tiquet
ja importat no es torna a importar, i per això es pot tornar a demanar una finestra de dies
que se solapa amb l'anterior (per agafar devolucions tardanes) sense duplicar res.
"""

import sqlite3

from .. import estoc as estoc_mod
from .. import temps, vendes as vendes_mod


def cataleg(con: sqlite3.Connection, variants: list[dict], crea: bool = True, camp_extern: str | None = None) -> int:
    """Crea o actualitza variants. Amb `crea=False` només enganxa l'id extern a les que ja hi són."""
    assert camp_extern in (None, "variant_shopify")
    n = 0
    for v in variants:
        if not v.get("gtin"):
            continue
        if crea:
            con.execute(
                """INSERT INTO catalog_sku (gtin, model, color, talla, categoria, preu_eur) VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(gtin) DO UPDATE SET model=excluded.model, color=excluded.color, talla=excluded.talla,
                   categoria=excluded.categoria, preu_eur=excluded.preu_eur""",
                (v["gtin"], v["model"], v.get("color") or "", v.get("talla") or "", v.get("categoria") or "altres",
                 v.get("preu_eur")))
            n += 1
        if camp_extern and v.get("id_extern"):
            c = con.execute(f"UPDATE catalog_sku SET {camp_extern} = ? WHERE gtin = ?", (str(v["id_extern"]), v["gtin"]))
            n += 0 if crea else c.rowcount
    if crea:
        # Les variants noves hereten la fitxa d'origen d'una altra variant del mateix model (com admin.importa_cataleg).
        con.execute("""UPDATE catalog_sku SET origen_json = (
                         SELECT k2.origen_json FROM catalog_sku k2
                         WHERE k2.model = catalog_sku.model AND k2.origen_json IS NOT NULL LIMIT 1)
                       WHERE origen_json IS NULL""")
    con.commit()
    return n


def _zona(con: sqlite3.Connection, cau: dict, botiga_id: str) -> str | None:
    if botiga_id not in cau:
        f = con.execute("SELECT zona_horaria FROM botiga WHERE id = ?", (botiga_id,)).fetchone()
        cau[botiga_id] = f["zona_horaria"] if f else None
    return cau[botiga_id]


def vendes(con: sqlite3.Connection, linies: list[dict], mapa: dict) -> dict:
    """Desa línies de venda. Torna {"tiquets","linies","devolucions","botigues"}."""
    zones: dict = {}
    per_tiquet: dict[tuple, list[dict]] = {}
    for li in linies:
        ub = li.get("ubicacio")
        botiga = mapa.get(None if ub is None else str(ub))
        if not botiga or not li.get("gtin") or not li.get("quantitat"):
            continue
        per_tiquet.setdefault((botiga, li["tiquet"]), []).append(li)

    n_tiquets = n_linies = n_dev = 0
    botigues = set()
    for (botiga, tiquet), files in per_tiquet.items():
        zona = _zona(con, zones, botiga)
        if zona is None:
            continue
        h = vendes_mod._hash_tiquet(tiquet)
        if con.execute("SELECT 1 FROM venda_linia WHERE botiga_id = ? AND tiquet_hash = ? LIMIT 1",
                       (botiga, h)).fetchone():
            continue  # ja importat
        pare = files[0].get("requereix")
        if pare and not con.execute("SELECT 1 FROM venda_linia WHERE botiga_id = ? AND tiquet_hash = ? LIMIT 1",
                                    (botiga, vendes_mod._hash_tiquet(pare))).fetchone():
            continue  # devolució d'una venda que no es va importar (p. ex. comanda cancel·lada)
        positives = 0
        for li in files:
            ts = temps.local(li["ts"], zona)
            q = int(li["quantitat"])
            dev = 1 if li.get("devolucio") or q < 0 else 0
            imp = li.get("import_eur")
            con.execute(
                """INSERT INTO venda_linia (botiga_id, ts, data, gtin, quantitat, import_eur, tiquet_hash, devolucio)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (botiga, ts, ts[:10], li["gtin"], q, None if imp is None else round(float(imp), 2), h, dev))
            if dev:
                n_dev += 1
            else:
                n_linies += 1
                positives += 1
        n_tiquets += 1 if positives else 0
        botigues.add(botiga)
    con.commit()
    return {"tiquets": n_tiquets, "linies": n_linies, "devolucions": n_dev, "botigues": sorted(botigues)}


def estoc(con: sqlite3.Connection, nivells: list[dict], mapa: dict, font: str) -> int:
    zones: dict = {}
    n = 0
    for nv in nivells:
        ub = nv.get("ubicacio")
        botiga = mapa.get(None if ub is None else str(ub))
        if not botiga or not nv.get("gtin") or nv.get("unitats") is None:
            continue
        zona = _zona(con, zones, botiga)
        if zona is None:
            continue
        estoc_mod.desa(con, botiga, nv["gtin"], max(0, int(nv["unitats"])), font=font, ts=temps.ara(zona))
        n += 1
    con.commit()
    return n
