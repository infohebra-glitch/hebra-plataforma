"""Imatges de les peces (v0.5, hebra/imatges.py). Marca o més.

  GET    /imatges                       cada model i color del catàleg amb la seva imatge (o silueta)
  PUT    /imatges/{model}?color=        cos JSON {"data_url": "data:image/jpeg;base64,..."} o {"url": "https://..."}
  DELETE /imatges/{model}?color=        torna a la silueta
"""

import base64
import binascii
import sqlite3

from fastapi import APIRouter, Body, Depends, HTTPException

from hebra import imatges

from .comu import MARCA_O_MES, bd, rol

router = APIRouter(prefix="/imatges", tags=["imatges"])


@router.get("")
def llista(con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    return {"imatges": imatges.llista(con)}


def _model(con: sqlite3.Connection, model: str) -> None:
    if not con.execute("SELECT 1 FROM catalog_sku WHERE model = ?", (model,)).fetchone():
        raise HTTPException(404, f"Model desconegut: {model}")


@router.put("/{model}")
def desa(model: str, color: str = "", cos: dict = Body(...), con: sqlite3.Connection = Depends(bd),
         _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    _model(con, model)
    try:
        if cos.get("url"):
            return imatges.des_de_url(con, model, color, str(cos["url"]))
        data_url = str(cos.get("data_url") or "")
        if not data_url.startswith("data:image/") or ";base64," not in data_url:
            raise imatges.ErrorImatge("Envia una imatge (data URL en base64) o una URL")
        try:
            dades = base64.b64decode(data_url.split(";base64,", 1)[1], validate=True)
        except (binascii.Error, ValueError) as e:
            raise imatges.ErrorImatge("La imatge no està ben codificada") from e
        return imatges.desa(con, model, color, dades, font="pujada")
    except imatges.ErrorImatge as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/{model}")
def esborra(model: str, color: str = "", con: sqlite3.Connection = Depends(bd),
            _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    return {"esborrada": imatges.esborra(con, model, color)}
