"""Sessió del tauler: POST/DELETE /sessio i GET /jo."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from hebra import auth

from .comu import usuari

router = APIRouter(tags=["sessió"])


class Credencials(BaseModel):
    correu: str
    contrasenya: str


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"


@router.post("/sessio")
def inicia(cos: Credencials, request: Request, response: Response) -> dict:
    estat = request.app.state
    clau = f"{_ip(request)}|{cos.correu.strip().lower()}"
    if estat.limit_sessio.bloquejat(clau):
        raise HTTPException(429, "Massa intents. Torna-ho a provar d'aquí a una estona.")
    fila = auth.autentica(estat.con, cos.correu, cos.contrasenya)
    if fila is None:
        estat.limit_sessio.falla(clau)
        raise HTTPException(401, "Correu o contrasenya incorrectes")
    estat.limit_sessio.reinicia(clau)
    response.set_cookie(auth.NOM_GALETA, auth.signa(estat.cfg.secret, fila["id"]), max_age=auth.DURADA_SESSIO_S,
                        httponly=True, samesite="lax", secure=estat.cfg.galeta_segura, path="/")
    return {"usuari": auth.usuari_json(fila)}


@router.delete("/sessio")
def tanca(request: Request, response: Response) -> dict:
    response.delete_cookie(auth.NOM_GALETA, path="/", httponly=True, samesite="lax",
                           secure=request.app.state.cfg.galeta_segura)
    return {"ok": True}


@router.get("/jo")
def jo(request: Request, u: dict = Depends(usuari)) -> dict:
    con = request.app.state.con
    if u["rol"] == "botiga":
        files = con.execute("SELECT id, nom, nivell FROM botiga WHERE id = ?", (u["botiga_id"],)).fetchall()
    else:
        files = con.execute("SELECT id, nom, nivell FROM botiga ORDER BY id").fetchall()
    return {"usuari": u, "botigues": [dict(f) for f in files]}
