"""Estoc de botiga per GTIN (taula `estoc`).

Fonts: CSV que puja la botiga o la marca, o Shopify (`hebra/shopify.py`).
Format CSV (capçalera obligatòria, separador coma o punt i coma):

    botiga,gtin,unitats
    BCN-01,08400000123457,3

Cada fila substitueix les unitats que hi havia d'aquell GTIN a aquella botiga.
La fitxa NFC fa servir aquesta taula per dir si una talla està esgotada; si un
GTIN no hi és, fa servir l'estoc fix del fitxer d'origen (dades de prova).
"""

import csv
import io
import sqlite3

from . import temps

ALIES = {"sku": "gtin", "botiga_id": "botiga", "quantitat": "unitats", "estoc": "unitats"}


def llegeix_csv(text: str) -> tuple[list[dict], list[str]]:
    """Llegeix un CSV amb capçalera i retorna (files amb claus normalitzades, errors de format)."""
    mostra = text[:2048]
    separador = ";" if mostra.count(";") > mostra.count(",") else ","
    lector = csv.DictReader(io.StringIO(text), delimiter=separador)
    if lector.fieldnames is None:
        return [], ["El fitxer és buit"]
    lector.fieldnames = [ALIES.get(c.strip().lower(), c.strip().lower()) for c in lector.fieldnames]
    return [{k: (v or "").strip() for k, v in f.items() if k} for f in lector], []


def desa(con: sqlite3.Connection, botiga_id: str, gtin: str, unitats: int, font: str = "csv",
         ts: str | None = None) -> None:
    con.execute(
        """INSERT INTO estoc (botiga_id, gtin, unitats, actualitzat, font) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(botiga_id, gtin) DO UPDATE SET unitats = excluded.unitats,
             actualitzat = excluded.actualitzat, font = excluded.font""",
        (botiga_id, gtin, unitats, ts or temps.ara(), font))


def importa_csv(con: sqlite3.Connection, text: str) -> tuple[int, list[str]]:
    """Importa un CSV d'estoc. Retorna (files importades, errors per línia)."""
    files, errors = llegeix_csv(text)
    if errors:
        return 0, errors
    if files and not {"botiga", "gtin", "unitats"} <= set(files[0]):
        falten = {"botiga", "gtin", "unitats"} - set(files[0])
        return 0, [f"Falten columnes: {', '.join(sorted(falten))}"]
    botigues = {f["id"] for f in con.execute("SELECT id FROM botiga")}
    n = 0
    for num, f in enumerate(files, start=2):
        try:
            if f["botiga"] not in botigues:
                raise ValueError(f"botiga desconeguda {f['botiga']!r}")
            gtin = f["gtin"].zfill(14)
            if not gtin.isdigit() or len(gtin) != 14:
                raise ValueError(f"GTIN no vàlid {f['gtin']!r}")
            unitats = int(f["unitats"])
            if unitats < 0:
                raise ValueError("les unitats no poden ser negatives")
            desa(con, f["botiga"], gtin, unitats)
            n += 1
        except (ValueError, KeyError) as e:
            errors.append(f"Línia {num}: {e}")
    con.commit()
    return n, errors


def unitats(con: sqlite3.Connection, botiga_id: str | None, gtin: str) -> int | None:
    """Unitats a la botiga segons la taula `estoc`, o None si no en sabem res."""
    if not botiga_id:
        return None
    fila = con.execute("SELECT unitats FROM estoc WHERE botiga_id = ? AND gtin = ?", (botiga_id, gtin)).fetchone()
    return fila["unitats"] if fila else None
