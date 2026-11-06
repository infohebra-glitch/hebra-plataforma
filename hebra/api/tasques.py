"""Estoc parat en CSV i tasques de botiga (docs/ESPECIFICACIO-v3.md, D i D.1).

`GET /estoc` (amb els suggeriments) és a analitica.py; aquí hi ha la descàrrega CSV
i les tasques. Un usuari de botiga només veu i toca les tasques de la seva botiga.
"""

import csv
import io
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from hebra import analitica, tasques

from .comu import BOTIGA_O_MES, bd, botiga_permesa, comprova_botiga, filtre, rol

router = APIRouter(tags=["estoc i tasques"])

COLUMNES_CSV = ("botiga_id", "gtin", "model", "nom", "color", "talla", "categoria", "unitats", "valor_eur",
                "dies_parat", "darrera_prova", "darrera_venda", "proves_altres_botigues", "vendes_altres_botigues",
                "suggeriment", "botiga_desti", "text_suggeriment", "tasca_pendent")


def _num(x) -> str:
    """Decimals amb coma, perquè el full de càlcul en català l'obri bé (el separador és «;»)."""
    return "" if x is None else str(x).replace(".", ",") if isinstance(x, float) else str(x)


@router.get("/estoc/parat.csv")
def estoc_parat_csv(categoria: str | None = None, f: analitica.Filtre = Depends(filtre),
                    con: sqlite3.Connection = Depends(bd)) -> Response:
    """Estoc parat amb el mateix filtre que `GET /estoc` (i, opcionalment, una categoria)."""
    parat = analitica.estoc(con, f)["parat"]
    if categoria:
        parat = [p for p in parat if p["categoria"] == categoria]
    sortida = io.StringIO()
    w = csv.writer(sortida, delimiter=";")
    w.writerow(COLUMNES_CSV)
    for p in parat:
        s = p["suggeriment"] or {}
        w.writerow([_num(p[c]) for c in COLUMNES_CSV[:14]]
                   + [s.get("accio", ""), s.get("botiga_desti") or "", s.get("text", ""),
                      p["tasca"]["id"] if p["tasca"] else ""])
    nom = f"estoc-parat-{f.botiga_id or 'totes'}-{f.fins.isoformat()}.csv"
    # BOM perquè Excel reconegui l'UTF-8 (accents).
    return Response("﻿" + sortida.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})


# ---------------------------------------------------------------- Tasques


class NovaTasca(BaseModel):
    botiga_id: str | None = None          # usuari de botiga: per defecte, la seva
    tipus: Literal["traspassar", "moure_a_sala", "promocio", "retornar", "revisar", "recompte", "altre"]
    titol: str | None = Field(default=None, max_length=200)   # sense títol, se'n genera un
    detall: str | None = Field(default="", max_length=2000)   # null = sense detall
    gtin: str | None = Field(default=None, pattern=r"^\d{1,14}$")
    unitats: int | None = Field(default=None, ge=1, le=100000)
    botiga_desti: str | None = None


class CanviTasca(BaseModel):
    estat: Literal["feta", "descartada", "pendent"]


def _botiga_existeix(con: sqlite3.Connection, b: str) -> bool:
    return con.execute("SELECT 1 FROM botiga WHERE id = ?", (b,)).fetchone() is not None


@router.get("/tasques")
def llista_tasques(botiga: str | None = None, estat: str | None = None, con: sqlite3.Connection = Depends(bd),
                   u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    if estat and estat not in tasques.ESTATS:
        raise HTTPException(400, f"Estat desconegut: {estat}")
    return {"tasques": tasques.llista(con, botiga_permesa(con, u, botiga), estat)}


@router.post("/tasques")
def nova_tasca(cos: NovaTasca, con: sqlite3.Connection = Depends(bd), u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    """Crea una tasca pendent. Si ja n'hi ha una de pendent amb la mateixa botiga, tipus i GTIN, la retorna."""
    botiga_id = cos.botiga_id or (u["botiga_id"] if u["rol"] == "botiga" else None)
    if not botiga_id:
        raise HTTPException(400, "Cal indicar la botiga de la tasca")
    comprova_botiga(u, botiga_id)
    if not _botiga_existeix(con, botiga_id):
        raise HTTPException(400, f"Botiga desconeguda: {botiga_id}")
    gtin = cos.gtin.zfill(14) if cos.gtin else None
    if gtin and not con.execute("SELECT 1 FROM catalog_sku WHERE gtin = ?", (gtin,)).fetchone():
        raise HTTPException(400, f"GTIN desconegut: {gtin}")
    if cos.botiga_desti:
        if cos.tipus != "traspassar":
            raise HTTPException(400, "Només un traspàs té botiga de destí")
        if cos.botiga_desti == botiga_id or not _botiga_existeix(con, cos.botiga_desti):
            raise HTTPException(400, f"Botiga de destí no vàlida: {cos.botiga_desti}")
    elif cos.tipus == "traspassar":
        raise HTTPException(400, "Un traspàs necessita la botiga de destí")
    t, _nova = tasques.crea(con, botiga_id, cos.tipus, cos.titol, cos.detall or "", gtin, cos.unitats, cos.botiga_desti,
                            creada_per=u["id"])
    return t


@router.patch("/tasques/{tid}")
def canvia_tasca(tid: int, cos: CanviTasca, con: sqlite3.Connection = Depends(bd),
                 u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    t = tasques.tasca(con, tid)
    if t is None:
        raise HTTPException(404, "Tasca no trobada")
    comprova_botiga(u, t["botiga_id"])
    return tasques.canvia_estat(con, tid, cos.estat, u["id"])
