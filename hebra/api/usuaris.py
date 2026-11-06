"""Gestió d'usuaris del tauler (només admin)."""

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from hebra import auth

from .comu import NOMES_ADMIN, bd, rol

router = APIRouter(prefix="/usuaris", tags=["usuaris"])


class NouUsuari(BaseModel):
    correu: str
    nom: str
    rol: Literal["admin", "marca", "botiga"]
    botiga_id: str | None = None
    contrasenya: str


class CanviUsuari(BaseModel):
    nom: str | None = None
    actiu: bool | None = None
    contrasenya: str | None = None


def _json(fila: sqlite3.Row) -> dict:
    return auth.usuari_json(fila) | {"actiu": bool(fila["actiu"]), "creat": fila["creat"]}


@router.get("")
def usuaris(con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*NOMES_ADMIN))) -> dict:
    return {"usuaris": [_json(f) for f in con.execute("SELECT * FROM usuari ORDER BY correu")]}


@router.post("")
def nou(cos: NouUsuari, con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*NOMES_ADMIN))) -> dict:
    try:
        uid = auth.crea_usuari(con, cos.correu, cos.nom, cos.rol, cos.contrasenya, cos.botiga_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"usuari": _json(con.execute("SELECT * FROM usuari WHERE id = ?", (uid,)).fetchone())}


@router.patch("/{uid}")
def canvia(uid: int, cos: CanviUsuari, con: sqlite3.Connection = Depends(bd),
           u: dict = Depends(rol(*NOMES_ADMIN))) -> dict:
    if not con.execute("SELECT 1 FROM usuari WHERE id = ?", (uid,)).fetchone():
        raise HTTPException(404, "Usuari no trobat")
    if cos.actiu is False and uid == u["id"]:
        raise HTTPException(400, "No et pots desactivar a tu mateix")
    if cos.nom:
        con.execute("UPDATE usuari SET nom = ? WHERE id = ?", (cos.nom.strip(), uid))
    if cos.actiu is not None:
        con.execute("UPDATE usuari SET actiu = ? WHERE id = ?", (int(cos.actiu), uid))
    if cos.contrasenya:
        if len(cos.contrasenya) < 10:
            raise HTTPException(400, "La contrasenya ha de tenir 10 caràcters o més")
        con.execute("UPDATE usuari SET hash_contrasenya = ? WHERE id = ?", (auth.hash_contrasenya(cos.contrasenya), uid))
    con.commit()
    return {"usuari": _json(con.execute("SELECT * FROM usuari WHERE id = ?", (uid,)).fetchone())}
