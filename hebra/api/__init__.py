"""API del tauler (v2): /api/v2/... Contracte a docs/API.md.

Cada mòdul és un `APIRouter`; `router` els agrupa amb el prefix /api/v2.
La connexió i la configuració es llegeixen de `request.app.state` (hebra/app.py).
"""

from fastapi import APIRouter

from . import analitica, flux, importacions, operacio, parametres, sessio, shopify, usuaris

router = APIRouter(prefix="/api/v2")
for _m in (sessio, analitica, operacio, importacions, parametres, usuaris, shopify, flux):
    router.include_router(_m.router)
