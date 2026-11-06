"""Importació de fitxers CSV: vendes, estoc (botiga o més) i catàleg (només admin)."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from hebra import admin, estoc, vendes

from .comu import BOTIGA_O_MES, NOMES_ADMIN, bd, rol

router = APIRouter(prefix="/importa", tags=["importació"])

MIDA_MAXIMA = 10 * 1024 * 1024


async def _text(fitxer: UploadFile) -> str:
    dades = await fitxer.read(MIDA_MAXIMA + 1)
    if len(dades) > MIDA_MAXIMA:
        raise HTTPException(400, "El fitxer és massa gran (màxim 10 MB)")
    try:
        return dades.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "El fitxer ha de ser un CSV en UTF-8")


def _nomes_la_seva(u: dict, text: str) -> None:
    """Un usuari de botiga només pot importar files de la seva botiga."""
    if u["rol"] != "botiga":
        return
    files, _ = estoc.llegeix_csv(text)
    alienes = {f.get("botiga") for f in files} - {u["botiga_id"]}
    if alienes:
        raise HTTPException(403, "El fitxer té files d'una altra botiga: només pots importar les de la teva")


@router.post("/vendes")
async def importa_vendes(fitxer: UploadFile, con: sqlite3.Connection = Depends(bd),
                         u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    text = await _text(fitxer)
    _nomes_la_seva(u, text)
    n, errors = vendes.importa_csv(con, text)
    botigues = [u["botiga_id"]] if u["rol"] == "botiga" else [f["id"] for f in con.execute("SELECT id FROM botiga")]
    for b in botigues:
        vendes.atribueix(con, b)
    return {"importades": n, "errors": errors[:200]}


@router.post("/estoc")
async def importa_estoc(fitxer: UploadFile, con: sqlite3.Connection = Depends(bd),
                        u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    text = await _text(fitxer)
    _nomes_la_seva(u, text)
    n, errors = estoc.importa_csv(con, text)
    return {"importades": n, "errors": errors[:200]}


@router.post("/cataleg")
async def importa_cataleg(fitxer: UploadFile, con: sqlite3.Connection = Depends(bd),
                          _u: dict = Depends(rol(*NOMES_ADMIN))) -> dict:
    n, errors = admin.importa_cataleg(con, await _text(fitxer))
    return {"importades": n, "errors": errors[:200]}
