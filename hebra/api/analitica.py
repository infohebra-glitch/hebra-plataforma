"""Rutes d'analítica (GET, filtre comú). Cada una crida la funció homònima de `hebra.analitica`.

La funció es busca en el moment de la petició (`getattr`), de manera que les rutes
funcionen tan bon punt el mòdul d'analítica la defineix. Si encara no hi és: 501.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from hebra import analitica

from .comu import bd, filtre, usuari

router = APIRouter(tags=["analítica"])

def _crida(nom: str, *args):
    fn = getattr(analitica, nom, None)
    if fn is None:
        raise HTTPException(501, f"L'analítica «{nom}» encara no està disponible")
    resultat = fn(*args)
    if resultat is None:
        raise HTTPException(404, "No trobat")
    return resultat


def _ruta(ruta: str, nom: str) -> None:
    def endpoint(f: analitica.Filtre = Depends(filtre), con: sqlite3.Connection = Depends(bd)) -> dict:
        return _crida(nom, con, f)
    endpoint.__name__ = f"analitica_{nom}"
    endpoint.__doc__ = f"Crida `hebra.analitica.{nom}(con, f)` (forma a docs/API.md)."
    router.add_api_route(ruta, endpoint, methods=["GET"])


for _ruta_, _nom in [("/resum", "resum"), ("/models", "models"), ("/talles", "talles"),
                     ("/demanda-perduda", "demanda_perduda"), ("/motius", "motius"), ("/servei", "servei"),
                     ("/estoc", "estoc"), ("/fitxa-nfc", "fitxa_nfc"), ("/experiments", "experiments"),
                     ("/alertes", "alertes"), ("/valor", "valor"), ("/perdues", "perdues"),
                     ("/estat-sistema", "estat_sistema"), ("/sessions", "sessions"),
                     ("/panorama", "panorama")]:
    _ruta(_ruta_, _nom)


@router.get("/models/{model}")
def model_detall(model: str, f: analitica.Filtre = Depends(filtre), con: sqlite3.Connection = Depends(bd)) -> dict:
    return _crida("model_detall", con, f, model)


# `GET /informes/{tipus}` és a informes.py (v0.3), amb la programació, els lliurats i el PDF.


@router.get("/peces/{epc}/historial")
def historial_peca(epc: str, con: sqlite3.Connection = Depends(bd), _u: dict = Depends(usuari)) -> dict:
    return _crida("historial_peca", con, epc)


# ---------------------------------------------------------------- v0.7: comparar, col·leccions i condicions del dia

import re  # noqa: E402
from datetime import date as _date  # noqa: E402

from pydantic import BaseModel, Field  # noqa: E402

from hebra import temps  # noqa: E402

from .comu import BOTIGA_O_MES, MARCA_O_MES, botiga_permesa, rol  # noqa: E402

_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@router.get("/comparativa")
def comparativa(compara: str | None = None, colleccio: int | None = None, franja: str | None = None,
                condicio: str | None = None, f: analitica.Filtre = Depends(filtre),
                con: sqlite3.Connection = Depends(bd)) -> dict:
    """Proves i compres per dia, comparades amb el període anterior, l'any passat o una col·lecció,
    amb filtre de franja d'hores i de condicions del dia (vegeu hebra/analitica/comparativa.py)."""
    try:
        return analitica.comparativa(con, f, compara, colleccio, franja, condicio)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


class NovaColleccio(BaseModel):
    nom: str = Field(min_length=1, max_length=60)
    des: str = Field(pattern=_DATA.pattern)
    fins: str = Field(pattern=_DATA.pattern)


@router.get("/colleccions")
def llista_colleccions(con: sqlite3.Connection = Depends(bd), _u: dict = Depends(usuari)) -> list[dict]:
    return analitica.colleccions(con)


@router.post("/colleccions")
def nova_colleccio(cos: NovaColleccio, con: sqlite3.Connection = Depends(bd),
                   _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    try:
        if _date.fromisoformat(cos.fins) < _date.fromisoformat(cos.des):
            raise ValueError
    except ValueError as e:
        raise HTTPException(422, "Les dates no són vàlides") from e
    cid = con.execute("INSERT INTO colleccio (nom, des, fins) VALUES (?, ?, ?)",
                      (cos.nom.strip(), cos.des, cos.fins)).lastrowid
    con.commit()
    return {"id": cid, "nom": cos.nom.strip(), "des": cos.des, "fins": cos.fins}


@router.delete("/colleccions/{cid}")
def esborra_colleccio(cid: int, con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    n = con.execute("DELETE FROM colleccio WHERE id = ?", (cid,)).rowcount
    con.commit()
    if not n:
        raise HTTPException(404, "No trobat")
    return {"ok": True}


class CondicioDia(BaseModel):
    botiga_id: str | None = None
    data: str = Field(pattern=_DATA.pattern)
    condicio: str = Field(min_length=1, max_length=30)


@router.get("/condicions")
def llista_condicions(botiga: str | None = None, con: sqlite3.Connection = Depends(bd),
                      u: dict = Depends(usuari)) -> list[dict]:
    b = botiga_permesa(con, u, botiga)
    return [dict(r) for r in con.execute(
        "SELECT botiga_id, data, condicio FROM condicio_dia WHERE (? IS NULL OR botiga_id = ?) ORDER BY data DESC LIMIT 400",
        (b, b))]


@router.post("/condicions")
def nova_condicio(cos: CondicioDia, con: sqlite3.Connection = Depends(bd), u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    b = botiga_permesa(con, u, cos.botiga_id)
    botigues = [b] if b else [r[0] for r in con.execute("SELECT id FROM botiga")]
    c = cos.condicio.strip().lower()
    con.executemany("INSERT OR IGNORE INTO condicio_dia (botiga_id, data, condicio) VALUES (?, ?, ?)",
                    [(x, cos.data, c) for x in botigues])
    con.commit()
    return {"ok": True, "botigues": len(botigues), "data": cos.data, "condicio": c, "ts": temps.ara()}


@router.delete("/condicions")
def esborra_condicio(data: str, condicio: str, botiga: str | None = None, con: sqlite3.Connection = Depends(bd),
                     u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    b = botiga_permesa(con, u, botiga)
    n = con.execute("DELETE FROM condicio_dia WHERE data = ? AND condicio = ? AND (? IS NULL OR botiga_id = ?)",
                    (data, condicio, b, b)).rowcount
    con.commit()
    return {"ok": True, "esborrades": n}
