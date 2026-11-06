"""Importació del catàleg i de les dades d'origen (format hebra-origen/0.2).

El fitxer d'origen descriu una peça física per model (EPC, talla, origen...).
Per al MVP en creem:
  * una fila de `catalog_sku` per a cada talla del model (un GTIN per talla);
  * una fila d'`etiqueta` per a la peça del fitxer (EPC + token NFC).

Amb una marca real, les variants (un GTIN per talla) s'importen abans des del seu
catàleg (`python -m hebra.admin cataleg`), i aquí només s'hi enganxa la fitxa
d'origen a totes les variants del model.

Amb `genera_talles=True` (només el simulador) es creen GTIN de prova per a les
altres talles sumant 1000 a la referència del model.
"""

import json
import logging
import secrets
import sqlite3
from pathlib import Path

from . import epc as epc_mod

log = logging.getLogger(__name__)

FORMAT_ACCEPTAT = "hebra-origen/0.2"


def gtin_per_talla(sgtin: epc_mod.Sgtin, index: int, index_base: int) -> str:
    """GTIN de prova per a la talla `index`, partint de la talla de la peça (`index_base`)."""
    ref = int(sgtin.referencia) + (index - index_base) * 1000  # separació ampla per no xocar entre models
    variant = epc_mod.Sgtin(sgtin.prefix_empresa, str(ref).zfill(len(sgtin.referencia)), sgtin.serie)
    return variant.gtin


def importa_origen(con: sqlite3.Connection, ruta: str | Path, genera_talles: bool = False) -> int:
    """Importa un fitxer hebra-origen. Retorna quantes variants del catàleg tenen ara aquesta fitxa."""
    dades = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if dades.get("format") != FORMAT_ACCEPTAT:
        raise ValueError(f"Format no suportat: {dades.get('format')!r} (esperat {FORMAT_ACCEPTAT})")

    total = 0
    for peca in dades["peces"]:
        sgtin = epc_mod.descodifica(peca["epc"])
        if peca.get("gtin") and peca["gtin"] != sgtin.gtin:
            # El fitxer de prova té dígits de control inventats: fem servir el de l'EPC.
            log.warning("GTIN %s del fitxer no quadra amb l'EPC (%s); fem servir el de l'EPC",
                        peca["gtin"], sgtin.gtin)

        talles = [t["talla"] for t in peca.get("talles", [])] or [peca["talla"]]
        index_base = talles.index(peca["talla"]) if peca["talla"] in talles else 0
        estoc = {t["talla"]: t.get("estoc") for t in peca.get("talles", [])}
        origen = dict(peca, faq_general=dades.get("faq_general", []), estoc=estoc)

        for i, talla in enumerate(talles):
            if i != index_base and not genera_talles:
                continue
            gtin = sgtin.gtin if i == index_base else gtin_per_talla(sgtin, i, index_base)
            con.execute(
                """INSERT INTO catalog_sku (gtin, model, color, talla, categoria, preu_eur, origen_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(gtin) DO UPDATE SET model=excluded.model, color=excluded.color,
                     talla=excluded.talla, categoria=excluded.categoria,
                     preu_eur=excluded.preu_eur, origen_json=excluded.origen_json""",
                (gtin, peca["model"], peca["color"]["ca"], talla, peca.get("forma", "altres"),
                 peca.get("preu_eur"), json.dumps(origen, ensure_ascii=False)),
            )

        # La fitxa d'origen és del model: l'enganxem a totes les seves variants ja conegudes.
        n = con.execute("UPDATE catalog_sku SET origen_json = ? WHERE model = ?",
                        (json.dumps(origen, ensure_ascii=False), peca["model"])).rowcount
        total += n
        con.execute(
            """INSERT INTO etiqueta (epc, nfc_token, gtin) VALUES (?, ?, ?)
               ON CONFLICT(epc) DO UPDATE SET gtin=excluded.gtin""",
            (sgtin.urn, nou_token(), sgtin.gtin),
        )
    con.commit()
    return total


def nou_token() -> str:
    """Token aleatori per a la URL del xip NFC (no es pot endevinar la fitxa d'una altra peça)."""
    return secrets.token_urlsafe(9)


def sku(con: sqlite3.Connection, gtin: str) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM catalog_sku WHERE gtin = ?", (gtin,)).fetchone()


def variants_del_model(con: sqlite3.Connection, model: str, color: str) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM catalog_sku WHERE model = ? AND color = ? ORDER BY rowid", (model, color)
    ).fetchall()


def gtin_de_epc(con: sqlite3.Connection, epc: str) -> str | None:
    """Tradueix un EPC a GTIN: primer la taula d'etiquetes, després la descodificació SGTIN."""
    fila = con.execute("SELECT gtin FROM etiqueta WHERE epc = ?", (epc,)).fetchone()
    if fila:
        return fila["gtin"]
    try:
        gtin = epc_mod.descodifica(epc).gtin
    except ValueError:
        return None
    return gtin if sku(con, gtin) else None
