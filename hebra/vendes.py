"""Vendes: importació de CSV i atribució de vendes a proves (Proposta MVP, 3.4 i 3.7).

Format CSV mínim (capçalera obligatòria, separador coma o punt i coma):

    data_hora,botiga,gtin,quantitat,import,tiquet
    2026-11-16T12:31:00+01:00,BCN-01,08400000123457,1,69.00,T-000123

  * `data_hora` pot ser només una data (AAAA-MM-DD). Llavors l'atribució és per dia.
  * `sku` s'accepta com a sinònim de `gtin`.
  * `quantitat` negativa = devolució.
  * `tiquet` es desa xifrat (SHA-256 amb sal); mai en clar.

Atribució: el mateix GTIN, a la mateixa botiga, entre l'inici de la prova i el
tancament del dia. Cada línia de venda s'aparella amb una sola prova i al revés.
Només compten les proves de confiança alta o mitjana.
"""

import csv
import hashlib
import io
import os
import sqlite3
from datetime import datetime

from . import temps

SAL_TIQUET = os.environ.get("HEBRA_SAL_TIQUET", "hebra-mvp")

ALIES = {"sku": "gtin", "data": "data_hora", "hora": "data_hora", "import_eur": "import", "qty": "quantitat"}


def _hash_tiquet(tiquet: str) -> str | None:
    if not tiquet:
        return None
    return hashlib.sha256(f"{SAL_TIQUET}:{tiquet}".encode()).hexdigest()


def importa_csv(con: sqlite3.Connection, text: str) -> tuple[int, list[str]]:
    """Importa un CSV de vendes. Retorna (línies importades, errors per línia)."""
    mostra = text[:2048]
    separador = ";" if mostra.count(";") > mostra.count(",") else ","
    lector = csv.DictReader(io.StringIO(text), delimiter=separador)
    if lector.fieldnames is None:
        return 0, ["El fitxer és buit"]
    lector.fieldnames = [ALIES.get(c.strip().lower(), c.strip().lower()) for c in lector.fieldnames]

    falten = {"data_hora", "botiga", "gtin", "quantitat"} - set(lector.fieldnames)
    if falten:
        return 0, [f"Falten columnes: {', '.join(sorted(falten))}"]

    botigues = {f["id"] for f in con.execute("SELECT id FROM botiga")}
    importades, errors = 0, []
    for num, fila in enumerate(lector, start=2):
        try:
            moment = fila["data_hora"].strip()
            if len(moment) == 10:
                ts, data = None, datetime.fromisoformat(moment).date().isoformat()
            else:
                ts = temps.local(moment)
                data = ts[:10]
            botiga = fila["botiga"].strip()
            if botiga not in botigues:
                raise ValueError(f"botiga desconeguda {botiga!r}")
            quantitat = int(fila["quantitat"])
            imp = fila.get("import", "").strip().replace(",", ".")
            con.execute(
                """INSERT INTO venda_linia (botiga_id, ts, data, gtin, quantitat, import_eur, tiquet_hash, devolucio)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (botiga, ts, data, fila["gtin"].strip().zfill(14), quantitat,
                 float(imp) if imp else None, _hash_tiquet(fila.get("tiquet", "").strip()),
                 1 if quantitat < 0 else 0),
            )
            importades += 1
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f"Línia {num}: {e}")
    con.commit()
    return importades, errors


def atribueix(con: sqlite3.Connection, botiga_id: str) -> int:
    """Recalcula totes les atribucions d'una botiga. Retorna quantes n'ha fet."""
    con.execute(
        """DELETE FROM atribucio WHERE venda_id IN (SELECT id FROM venda_linia WHERE botiga_id = ?)""",
        (botiga_id,))

    proves = con.execute(
        """SELECT p.id, p.gtin, s.inici FROM prova p
           JOIN sessio s ON s.id = p.sessio_id JOIN cabina c ON c.id = s.cabina_id
           WHERE c.botiga_id = ? AND p.gtin IS NOT NULL AND p.confianca IN ('alta', 'mitjana')
           ORDER BY s.inici, p.id""", (botiga_id,)).fetchall()
    vendes = con.execute(
        """SELECT id, gtin, ts, data FROM venda_linia
           WHERE botiga_id = ? AND quantitat > 0
           ORDER BY data, COALESCE(ts, data || 'T23:59:59'), id""", (botiga_id,)).fetchall()

    # Índex de proves lliures per (gtin, dia), en ordre cronològic.
    lliures: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for p in proves:
        lliures.setdefault((p["gtin"], p["inici"][:10]), []).append(p)

    fetes = 0
    for v in vendes:
        candidates = lliures.get((v["gtin"], v["data"]), [])
        if v["ts"]:
            # La prova ha d'haver començat abans de la venda; triem la més antiga.
            moment_venda = datetime.fromisoformat(v["ts"])
            tria = next((p for p in candidates if datetime.fromisoformat(p["inici"]) <= moment_venda), None)
            regla = "mateix_gtin_hora"
        else:
            tria = candidates[0] if candidates else None
            regla = "mateix_gtin_dia"
        if tria:
            candidates.remove(tria)
            con.execute("INSERT INTO atribucio (prova_id, venda_id, regla) VALUES (?, ?, ?)",
                        (tria["id"], v["id"], regla))
            fetes += 1
    con.commit()
    return fetes
