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
                     ("/estat-sistema", "estat_sistema"), ("/sessions", "sessions")]:
    _ruta(_ruta_, _nom)


@router.get("/models/{model}")
def model_detall(model: str, f: analitica.Filtre = Depends(filtre), con: sqlite3.Connection = Depends(bd)) -> dict:
    return _crida("model_detall", con, f, model)


# `GET /informes/{tipus}` és a informes.py (v0.3), amb la programació, els lliurats i el PDF.


@router.get("/peces/{epc}/historial")
def historial_peca(epc: str, con: sqlite3.Connection = Depends(bd), _u: dict = Depends(usuari)) -> dict:
    return _crida("historial_peca", con, epc)
