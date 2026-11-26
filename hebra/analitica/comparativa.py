"""Proves i compres per dia, comparades (v0.7).

Respon a «com ha anat aquest període comparat amb…» i deixa triar:
  * amb què es compara: el període anterior de la mateixa durada, el mateix període de l'any passat
    o una col·lecció (temporada) de la marca, alineats per dia (dia 1 amb dia 1);
  * una franja d'hores (p. ex. només el matí, 10-14 h);
  * les condicions del dia (p. ex. només els dies de pluja, o els que no en feia), que la botiga o la marca
    marquen a «Connexions i dades». Més endavant es podran omplir soles amb dades de meteorologia.
"""

import sqlite3
from datetime import date, timedelta

from . import base
from .base import Filtre

CONDICIONS = ("pluja", "calor", "fred", "festiu", "rebaixes", "esdeveniment")
FRANGES = {"mati": (10, 14), "migdia": (14, 17), "tarda": (17, 22)}


def condicions(con: sqlite3.Connection, f: Filtre) -> dict[str, set[str]]:
    """{data: {condicions}} del període (de la botiga, o de qualsevol botiga si són totes)."""
    out: dict[str, set[str]] = {}
    for r in con.execute("""SELECT data, condicio FROM condicio_dia WHERE data BETWEEN ? AND ?
                            AND (? IS NULL OR botiga_id = ?)""",
                         (f.des.isoformat(), f.fins.isoformat(), f.botiga_id, f.botiga_id)):
        out.setdefault(r["data"], set()).add(r["condicio"])
    return out


def _dies(con: sqlite3.Connection, f: Filtre, hores: tuple[int, int] | None, condicio: str | None) -> list[dict]:
    """Una fila per dia del període amb proves, compres i conversió. Els dies que no compleixen la condició
    surten amb `None` (no zero): no es compten ni es dibuixen."""
    cond = condicions(con, f)
    per_dia: dict[str, list[int]] = {}
    d = f.des
    while d <= f.fins:
        per_dia[d.isoformat()] = [0, 0]
        d += timedelta(days=1)
    for p in base.proves_valides(con, f):
        h = base.dt(p["inici"]).hour
        if hores and not hores[0] <= h < hores[1]:
            continue
        c = per_dia.setdefault(p["inici"][:10], [0, 0])
        c[0] += 1
        c[1] += p["venuda"]
    out = []
    for dia, (n, c) in sorted(per_dia.items()):
        cs = sorted(cond.get(dia, set()))
        compleix = condicio is None or (condicio[1:] not in cs if condicio.startswith("!") else condicio in cs)
        out.append({"data": dia, "condicions": cs, "compleix": compleix,
                    "proves": n if compleix else None, "compres": c if compleix else None,
                    "conversio": base.frac(c, n) if compleix else None})
    return out


def _total(dies: list[dict]) -> dict:
    n = sum(d["proves"] or 0 for d in dies)
    c = sum(d["compres"] or 0 for d in dies)
    return {"proves": n, "compres": c, "conversio": base.frac(c, n), "dies": sum(1 for d in dies if d["compleix"])}


def comparativa(con: sqlite3.Connection, f: Filtre, compara: str | None = None, colleccio: int | None = None,
                franja: str | None = None, condicio: str | None = None) -> dict:
    """`GET /analitica/comparativa`. ValueError si un paràmetre no és vàlid."""
    hores = FRANGES.get(franja) if franja else None
    if franja and not hores:
        raise ValueError("Franja desconeguda")
    if condicio is not None and not (0 < len(condicio.lstrip("!").strip()) <= 30):
        raise ValueError("Condició no vàlida")
    dies = _dies(con, f, hores, condicio)
    llarg = (f.fins - f.des).days
    cmp_f, etiqueta = None, None
    if compara == "anterior":
        cmp_f = base.amb_dates(f, f.des - timedelta(days=llarg + 1), f.des - timedelta(days=1))
        etiqueta = "Període anterior"
    elif compara == "any":
        try:
            des = f.des.replace(year=f.des.year - 1)
        except ValueError:   # 29 de febrer
            des = f.des.replace(year=f.des.year - 1, day=28)
        cmp_f, etiqueta = base.amb_dates(f, des, des + timedelta(days=llarg)), "L'any passat"
    elif compara == "colleccio":
        c = con.execute("SELECT * FROM colleccio WHERE id = ?", (colleccio,)).fetchone()
        if not c:
            raise ValueError("Aquesta col·lecció no existeix")
        des = date.fromisoformat(c["des"])
        fins = min(date.fromisoformat(c["fins"]), des + timedelta(days=llarg))
        cmp_f, etiqueta = base.amb_dates(f, des, fins), c["nom"]
    elif compara:
        raise ValueError("Comparació desconeguda")
    out = {"dies": dies, "total": _total(dies), "franja": franja, "condicio": condicio,
           "condicions_disponibles": sorted({x for (x,) in con.execute("SELECT DISTINCT condicio FROM condicio_dia")}
                                            | set(CONDICIONS)),
           "comparacio": None}
    if cmp_f:
        cd = _dies(con, cmp_f, hores, condicio)
        out["comparacio"] = {"etiqueta": etiqueta, "des": cmp_f.des.isoformat(), "fins": cmp_f.fins.isoformat(),
                             "dies": cd, "total": _total(cd)}
    return out


def colleccions(con: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT id, nom, des, fins FROM colleccio ORDER BY des DESC")]
