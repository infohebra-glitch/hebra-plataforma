"""Paràmetres per botiga (taula `parametre`): lectura per a la marca, escriptura només admin."""

import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from hebra import db

from .comu import MARCA_O_MES, NOMES_ADMIN, bd, rol

router = APIRouter(tags=["paràmetres"])

CLAU_VALIDA = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


class Parametres(BaseModel):
    botiga_id: str = "*"
    valors: dict[str, str | int | float]


def _llegeix(con: sqlite3.Connection, botiga_id: str) -> dict:
    files = con.execute("SELECT clau, valor FROM parametre WHERE botiga_id = ? ORDER BY clau", (botiga_id,))
    return {"botiga_id": botiga_id, "valors": {f["clau"]: f["valor"] for f in files}}


@router.get("/parametres")
def parametres(botiga: str = "*", con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    return _llegeix(con, botiga)


@router.put("/parametres")
def desa(cos: Parametres, con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*NOMES_ADMIN))) -> dict:
    if cos.botiga_id != "*" and not con.execute("SELECT 1 FROM botiga WHERE id = ?", (cos.botiga_id,)).fetchone():
        raise HTTPException(400, f"Botiga desconeguda: {cos.botiga_id}")
    for clau in cos.valors:
        if not CLAU_VALIDA.match(clau):
            raise HTTPException(400, f"Nom de paràmetre no vàlid: {clau}")
    for clau, valor in cos.valors.items():
        db.desa_parametre(con, cos.botiga_id, clau, str(valor))
    return _llegeix(con, cos.botiga_id)
