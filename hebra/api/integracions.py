"""Integracions (ESPECIFICACIO-v3 F.3): Shopify, Square i CSV per URL. Només marca o admin.

El secret (testimoni d'accés) s'envia en crear o canviar la integració i no es torna mai:
la resposta només diu `"te_secret": true`.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from hebra.integracions import ErrorIntegracio, motor

from .comu import MARCA_O_MES, bd, rol

router = APIRouter(prefix="/integracions", tags=["integracions"])
marca = Depends(rol(*MARCA_O_MES))


class NovaIntegracio(BaseModel):
    botiga_id: str | None = None
    proveidor: str
    config: dict = {}
    secret: str | None = None
    abast: list[str] | None = None
    interval_min: int | None = None
    actiu: bool = True


class CanviIntegracio(BaseModel):
    botiga_id: str | None = None
    config: dict | None = None
    secret: str | None = None
    actiu: bool | None = None
    abast: list[str] | None = None
    interval_min: int | None = None


class ProvaIntegracio(BaseModel):
    proveidor: str | None = None
    config: dict | None = None
    secret: str | None = None
    id: int | None = None
    botiga_id: str | None = None


def _clau(request: Request) -> str:
    return request.app.state.cfg.secret


def _error(e: ErrorIntegracio) -> HTTPException:
    if isinstance(e, motor.NoTrobada):
        return HTTPException(404, str(e))
    if isinstance(e, motor.EnCurs):
        return HTTPException(409, str(e))
    return HTTPException(400, str(e))


@router.get("")
def llista(con: sqlite3.Connection = Depends(bd), _u: dict = marca) -> dict:
    return {"integracions": motor.llista(con)}


@router.post("")
def crea(cos: NovaIntegracio, request: Request, con: sqlite3.Connection = Depends(bd), _u: dict = marca) -> dict:
    try:
        return motor.crea(con, _clau(request), cos.model_dump())
    except ErrorIntegracio as e:
        raise _error(e)


@router.post("/prova")
def prova(cos: ProvaIntegracio, request: Request, con: sqlite3.Connection = Depends(bd), _u: dict = marca) -> dict:
    if cos.id is None and not cos.proveidor:
        raise HTTPException(400, "Cal el proveïdor (shopify, square o csv_url)")
    try:
        detall = motor.prova(con, _clau(request), cos.proveidor, cos.config, cos.secret, cos.id, cos.botiga_id)
    except ErrorIntegracio as e:
        raise _error(e)
    return {"ok": True, "detall": detall}


@router.patch("/{iid}")
def canvia(iid: int, cos: CanviIntegracio, request: Request, con: sqlite3.Connection = Depends(bd),
           _u: dict = marca) -> dict:
    canvis = {k: getattr(cos, k) for k in cos.model_fields_set}
    try:
        return motor.actualitza(con, _clau(request), iid, canvis)
    except ErrorIntegracio as e:
        raise _error(e)


@router.delete("/{iid}")
def esborra(iid: int, con: sqlite3.Connection = Depends(bd), _u: dict = marca) -> dict:
    try:
        motor.esborra(con, iid)
    except ErrorIntegracio as e:
        raise _error(e)
    return {"ok": True}


@router.post("/{iid}/sincronitza")
def sincronitza(iid: int, request: Request, con: sqlite3.Connection = Depends(bd), _u: dict = marca) -> dict:
    try:
        return {"resum": motor.sincronitza(con, _clau(request), iid)}
    except ErrorIntegracio as e:
        raise _error(e)


@router.get("/{iid}/registre")
def registre(iid: int, con: sqlite3.Connection = Depends(bd), _u: dict = marca) -> dict:
    try:
        return {"registre": motor.registre(con, iid)}
    except ErrorIntegracio as e:
        raise _error(e)
