"""Estoc: estoc parat, risc de rebaixa i precisió d'estoc de la zona (insights 14, 15, 23).

Estoc parat (14): GTIN amb unitats > 0 i cap prova (de cap confiança) ni cap
  venda en els `dies_estoc_parat` (21) dies que acaben a `Filtre.fins`.
  `dies_sense_activitat` = dies des de l'última prova o venda; si no n'hi ha
  hagut mai, dies des de la primera dada de la botiga (és un mínim).
  Amb totes les botigues, una fila per GTIN: suma de les botigues on està parat.

Risc de rebaixa (15): models amb cobertura > `setmanes_cobertura` (8) setmanes
  i conversió baixa (la mateixa regla que «molt provat, poc venut», vegeu
  models.py) o sense cap prova. Cobertura = unitats ÷ vendes setmanals del
  període; None si no s'ha venut res (cobertura infinita).

Precisió (23): recomptes manuals contra lectura RFID fins a `Filtre.fins`.
  error_mitja_pct = Σ|manual − rfid| ÷ Σ manual.
"""

import sqlite3
from collections import defaultdict
from datetime import date, timedelta

from . import Filtre, base, per_model as models_mod


def _darrera_activitat(con: sqlite3.Connection, f: Filtre) -> dict[tuple, str]:
    p = base.params(f)
    out: dict[tuple, str] = {}
    for r in con.execute(
            """SELECT c.botiga_id, p.gtin, MAX(substr(s.inici, 1, 10)) AS dia
               FROM prova p JOIN sessio s ON s.id = p.sessio_id JOIN cabina c ON c.id = s.cabina_id
               WHERE p.gtin IS NOT NULL AND s.inici < :fins AND (:b IS NULL OR c.botiga_id = :b)
               GROUP BY c.botiga_id, p.gtin""", p):
        out[(r["botiga_id"], r["gtin"])] = r["dia"]
    for r in con.execute(
            """SELECT botiga_id, gtin, MAX(data) AS dia FROM venda_linia
               WHERE data < :fins AND (:b IS NULL OR botiga_id = :b) GROUP BY botiga_id, gtin""", p):
        clau = (r["botiga_id"], r["gtin"])
        out[clau] = max(out.get(clau, ""), r["dia"])
    return out


def _primera_dada(con: sqlite3.Connection, botiga_id: str) -> date | None:
    r = con.execute(
        """SELECT MIN(d) FROM (
             SELECT MIN(substr(s.inici, 1, 10)) AS d FROM sessio s JOIN cabina c ON c.id = s.cabina_id
             WHERE c.botiga_id = ?
             UNION ALL SELECT MIN(data) FROM venda_linia WHERE botiga_id = ?)""",
        (botiga_id, botiga_id)).fetchone()[0]
    return date.fromisoformat(r) if r else None


def estoc_parat(con: sqlite3.Connection, f: Filtre) -> list[dict]:
    dies = base.par(con, f, "dies_estoc_parat")
    inici_finestra = (f.fins - timedelta(days=dies - 1)).isoformat()
    darrera = _darrera_activitat(con, f)
    info = base.info_models(con)
    primeres: dict[str, date | None] = {}
    per_gtin: dict[str, dict] = {}
    for e in con.execute(
            """SELECT e.botiga_id, e.gtin, e.unitats, k.model, k.talla FROM estoc e
               LEFT JOIN catalog_sku k ON k.gtin = e.gtin
               WHERE e.unitats > 0 AND (:b IS NULL OR e.botiga_id = :b)
               ORDER BY e.gtin, e.botiga_id""", {"b": f.botiga_id}):
        ultim = darrera.get((e["botiga_id"], e["gtin"]))
        if ultim and ultim >= inici_finestra:
            continue
        if ultim:
            sense = (f.fins - date.fromisoformat(ultim)).days
        else:
            if e["botiga_id"] not in primeres:
                primeres[e["botiga_id"]] = _primera_dada(con, e["botiga_id"])
            primera = primeres[e["botiga_id"]]
            sense = (f.fins - primera).days + 1 if primera else dies
        fila = per_gtin.get(e["gtin"])
        if fila is None:
            per_gtin[e["gtin"]] = {"gtin": e["gtin"], "model": e["model"], "nom": base.nom_model(info, e["model"]),
                                   "talla": e["talla"], "unitats": e["unitats"], "dies_sense_activitat": sense}
        else:
            fila["unitats"] += e["unitats"]
            fila["dies_sense_activitat"] = min(fila["dies_sense_activitat"], sense)
    return sorted(per_gtin.values(), key=lambda r: (-r["dies_sense_activitat"], -r["unitats"], r["gtin"]))


def risc_rebaixa(con: sqlite3.Connection, f: Filtre, taula: list[dict] | None = None) -> list[dict]:
    taula = models_mod.taula_models(con, f) if taula is None else taula
    limit = base.par(con, f, "setmanes_cobertura")
    info = base.info_models(con)
    estoc = base.estoc_per_gtin(con, f.botiga_id)
    venudes: dict[str, int] = defaultdict(int)
    for v in base.vendes(con, f):
        if v["model"]:
            venudes[v["model"]] += v["quantitat"]
    per_model = {r["model"]: r for r in taula}
    out = []
    for model, i in info.items():
        unitats = base.estoc_de(estoc, i["gtins"])
        if not unitats or unitats <= 0:
            continue
        r = per_model.get(model, {"proves": 0, "conversio": None, "quartil_categoria": None, "conversio_baixa": False})
        setmanals = venudes[model] / base.setmanes(f)
        cobertura = round(unitats / setmanals, 1) if setmanals else None
        if (cobertura is None or cobertura > limit) and (r["conversio_baixa"] or r["proves"] == 0):
            out.append({"model": model, "nom": i["nom"], "unitats": unitats, "cobertura_setmanes": cobertura,
                        "conversio": r["conversio"], "quartil_categoria": r["quartil_categoria"]})
    return sorted(out, key=lambda r: -r["unitats"])


def precisio(con: sqlite3.Connection, f: Filtre) -> dict | None:
    files = con.execute(
        "SELECT manual, rfid FROM recompte_estoc WHERE data < :fins AND (:b IS NULL OR botiga_id = :b)",
        base.params(f)).fetchall()
    if not files:
        return None
    manual = sum(r["manual"] for r in files)
    return {"recomptes": len(files),
            "error_mitja_pct": base.frac(sum(abs(r["manual"] - r["rfid"]) for r in files), manual)}


def estoc(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /estoc`."""
    return {"parat": estoc_parat(con, f), "risc_rebaixa": risc_rebaixa(con, f), "precisio": precisio(con, f)}
