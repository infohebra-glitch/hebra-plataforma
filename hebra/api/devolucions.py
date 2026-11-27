"""v0.9: devolucions online. Comparativa amb el provador, mapa de motius i esborrat (només marca o admin).

La importació del CSV és a importacions.py (`POST /importa/devolucions`), amb la resta de fitxers.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from hebra import analitica, devolucions

from .comu import MARCA_O_MES, bd, filtre, rol

router = APIRouter(tags=["devolucions online"])


@router.get("/provador-online")
def provador_online(model: str | None = None, f: analitica.Filtre = Depends(filtre),
                    con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    return analitica.provador_online(con, f, model)


@router.get("/devolucions/mapa")
def llista_mapa(con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    return devolucions.llista_mapa(con) | {"importat": devolucions.resum(con)}


class CanviMapa(BaseModel):
    codi: str = Field(max_length=devolucions.MAX_CODI)
    motiu: str = Field(min_length=1, max_length=40)
    sentit: str | None = None


@router.put("/devolucions/mapa")
def desa_mapa(cos: CanviMapa, con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    try:
        return devolucions.desa_mapa(con, cos.codi, cos.motiu, cos.sentit)
    except KeyError:
        raise HTTPException(404, "Aquest motiu no surt a cap devolució")
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.delete("/devolucions")
def esborra(con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    """Esborra les devolucions que ha pujat la marca (no les del lot de prova)."""
    return {"esborrades": devolucions.esborra(con)}
