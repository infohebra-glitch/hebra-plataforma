"""Fitxa NFC configurable per la marca (v0.3, A.3): configuració, contingut per model i previsualització.

Rutes (marca+):
  GET/PUT /fitxa/config?botiga=           general (sense botiga) o la parcial d'una botiga
  GET     /fitxa/models                   models del catàleg i en quins idiomes tenen contingut propi
  GET     /fitxa/models/{model}           contingut propi per idioma i el fitxer d'origen
  PUT     /fitxa/models/{model}/{idioma}  desa el contingut propi (un objecte buit l'esborra)
  GET     /fitxa/previsualitza?model=&botiga=&idioma=
          HTML de la fitxa tal com la veuria el client, per a un iframe del tauler.
          No registra cap esdeveniment: no porta l'script ni formularis actius.
"""

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from hebra import fitxa as fitxa_mod
from hebra import fitxa_config, textos

from .comu import MARCA_O_MES, bd, botiga_permesa, rol

router = APIRouter(prefix="/fitxa", tags=["fitxa NFC"])

_plantilles = Jinja2Templates(directory=Path(fitxa_mod.__file__).with_name("templates"))
_plantilles.env.globals["pais"] = textos.pais


def _err(e: fitxa_config.ErrorConfig):
    raise HTTPException(400, str(e))


@router.get("/config")
def config(request: Request, botiga: str | None = None, con: sqlite3.Connection = Depends(bd),
           u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    return fitxa_config.resposta(con, botiga_permesa(con, u, botiga))


@router.put("/config")
def desa_config(cos: dict = Body(...), botiga: str | None = None, con: sqlite3.Connection = Depends(bd),
                u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    b = botiga_permesa(con, u, botiga)
    try:
        fitxa_config.desa(con, b, cos)
    except fitxa_config.ErrorConfig as e:
        _err(e)
    return fitxa_config.resposta(con, b)


def _origen(con: sqlite3.Connection, model: str) -> dict | None:
    fila = con.execute("""SELECT origen_json FROM catalog_sku WHERE model = ? AND origen_json IS NOT NULL
                          ORDER BY rowid LIMIT 1""", (model,)).fetchone()
    return json.loads(fila["origen_json"]) if fila else None


def _model_existeix(con: sqlite3.Connection, model: str) -> None:
    if not con.execute("SELECT 1 FROM catalog_sku WHERE model = ?", (model,)).fetchone():
        raise HTTPException(404, f"Model desconegut: {model}")


@router.get("/models")
def models(con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    idiomes: dict[str, list[str]] = {}
    for f in con.execute("SELECT model, idioma FROM contingut_model ORDER BY model, idioma"):
        idiomes.setdefault(f["model"], []).append(f["idioma"])
    out = []
    for f in con.execute("""SELECT model, MIN(categoria) AS categoria, MAX(origen_json IS NOT NULL) AS te_origen,
                                   MAX(origen_json) AS origen_json
                            FROM catalog_sku GROUP BY model ORDER BY model"""):
        propi = fitxa_config.contingut(con, f["model"]).get("ca", {})
        nom = propi.get("nom") or fitxa_mod.tr(json.loads(f["origen_json"] or "{}").get("nom"), "ca") or f["model"]
        out.append({"model": f["model"], "nom": nom, "categoria": f["categoria"],
                    "idiomes_amb_contingut": idiomes.get(f["model"], []), "te_origen": bool(f["te_origen"])})
    return {"models": out}


@router.get("/models/{model}")
def model(model: str, con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    _model_existeix(con, model)
    return {"model": model, "contingut": fitxa_config.contingut(con, model), "origen": _origen(con, model)}


@router.put("/models/{model}/{idioma}")
def desa_model(model: str, idioma: str, cos: dict = Body(...), con: sqlite3.Connection = Depends(bd),
               _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    _model_existeix(con, model)
    try:
        fitxa_config.desa_contingut(con, model, idioma, cos)
    except fitxa_config.ErrorConfig as e:
        _err(e)
    return {"ok": True}


@router.get("/previsualitza", response_class=HTMLResponse)
def previsualitza(request: Request, model: str, botiga: str | None = None, idioma: str | None = None,
                  con: sqlite3.Connection = Depends(bd), u: dict = Depends(rol(*MARCA_O_MES))):
    """La fitxa d'una peça del model (la primera variant) amb la configuració efectiva de la botiga."""
    b = botiga_permesa(con, u, botiga)
    peca = con.execute("""SELECT NULL AS epc, 'previsualitzacio' AS nfc_token, k.* FROM catalog_sku k
                          WHERE k.model = ? ORDER BY k.rowid LIMIT 1""", (model,)).fetchone()
    if peca is None:
        raise HTTPException(404, f"Model desconegut: {model}")
    cfg = fitxa_config.efectiva(con, b)
    lang = fitxa_mod.tria_idioma(idioma, None, cfg["idiomes"])
    context = fitxa_mod.context_pagina(con, peca, b, lang, cfg, s="", ok=None,
                                       previsualitza={"model": model, "botiga": b or ""})
    return _plantilles.TemplateResponse(request, "fitxa.html", context, headers={"Cache-Control": "no-store"})
