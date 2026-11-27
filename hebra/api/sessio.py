"""Sessió del tauler: POST/DELETE /sessio i GET /jo."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from hebra import auth

from .comu import usuari

router = APIRouter(tags=["sessió"])


class Credencials(BaseModel):
    correu: str = Field(max_length=254)
    contrasenya: str = Field(max_length=200)


class CanviContrasenya(BaseModel):
    actual: str = Field(max_length=200)
    nova: str = Field(min_length=10, max_length=200)


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
    response.set_cookie(auth.NOM_GALETA, auth.signa(estat.cfg.secret, fila["id"], versio=fila["versio_sessio"]), max_age=auth.DURADA_SESSIO_S,
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


@router.post("/jo/contrasenya")
def canvia_contrasenya(cos: CanviContrasenya, request: Request, response: Response, u: dict = Depends(usuari)) -> dict:
    """Cada persona es pot canviar la seva contrasenya. Tanca les altres sessions i renova aquesta."""
    estat = request.app.state
    clau = f"{_ip(request)}|{u['correu']}"
    if estat.limit_sessio.bloquejat(clau):
        raise HTTPException(429, "Massa intents. Torna-ho a provar d'aquí a una estona.")
    fila = auth.autentica(estat.con, u["correu"], cos.actual)
    if fila is None:
        estat.limit_sessio.falla(clau)
        raise HTTPException(400, "La contrasenya actual no és correcta")
    estat.con.execute("UPDATE usuari SET hash_contrasenya = ?, versio_sessio = versio_sessio + 1 WHERE id = ?",
                      (auth.hash_contrasenya(cos.nova), fila["id"]))
    estat.con.commit()
    response.set_cookie(auth.NOM_GALETA, auth.signa(estat.cfg.secret, fila["id"], versio=fila["versio_sessio"] + 1),
                        max_age=auth.DURADA_SESSIO_S, httponly=True, samesite="lax", secure=estat.cfg.galeta_segura,
                        path="/")
    return {"ok": True}
