"""Lot de prova (hebra/lot_prova.py): carregar dades inventades i esborrar-les d'un clic."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from hebra import lot_prova

from .comu import MARCA_O_MES, bd, rol

router = APIRouter(tags=["lot de prova"])


@router.get("/lot-prova")
def estat(con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    return lot_prova.estat(con)


@router.post("/lot-prova")
def carrega(con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    try:
        return lot_prova.carrega(con)
    except lot_prova.ErrorLot as e:
        raise HTTPException(409, str(e))


@router.delete("/lot-prova")
def esborra(con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    try:
        return lot_prova.esborra(con)
    except lot_prova.ErrorLot as e:
        raise HTTPException(409, str(e))
