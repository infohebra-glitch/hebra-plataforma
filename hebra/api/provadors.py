"""Provadors en directe (v0.3, B): `GET /provadors/directe?botiga=`. Lògica a hebra/provadors.py.

Tots els rols; un usuari de botiga només veu la seva. L'actualització en directe arriba
pel flux SSE (`/flux`, esdeveniment `cabina`).
"""

import sqlite3

from fastapi import APIRouter, Depends

from hebra import provadors

from .comu import BOTIGA_O_MES, bd, botiga_permesa, rol

router = APIRouter(tags=["operació"])


@router.get("/provadors/directe")
def directe(botiga: str | None = None, con: sqlite3.Connection = Depends(bd),
            u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    return provadors.directe(con, botiga_permesa(con, u, botiga))
