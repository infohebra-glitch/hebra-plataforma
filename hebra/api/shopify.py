"""Sincronització amb Shopify (només admin). Vegeu hebra/shopify.py."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from hebra import shopify

from .comu import NOMES_ADMIN, bd, rol

router = APIRouter(tags=["shopify"])


@router.post("/shopify/sincronitza")
def sincronitza(botiga: str, con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*NOMES_ADMIN))) -> dict:
    try:
        return shopify.sincronitza(con, botiga)
    except shopify.ErrorShopify as e:
        raise HTTPException(400, str(e))
