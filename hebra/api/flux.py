"""`GET /api/v2/flux`: alertes en directe per al dependent amb Server-Sent Events.

Esdeveniments: `peticio`, `abandonada`, `alerta` (vegeu hebra/alertes.py), amb `data: <JSON>`.
Cada `BATEC_S` segons s'envia un comentari (`: batec`) perquè els proxies no tallin la
connexió. Passats `DURADA_MAXIMA_S` el servidor tanca el flux i el navegador
(EventSource) es reconnecta sol al cap de `retry` ms: així no queden connexions òrfenes.
"""

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from hebra import alertes, temps

from .comu import BOTIGA_O_MES, botiga_permesa, rol

router = APIRouter(tags=["operació"])

BATEC_S = 15.0
DURADA_MAXIMA_S = 30 * 60.0


async def _genera(botiga: str | None):
    sub = alertes.bus.subscriu(botiga)
    bucle = asyncio.get_running_loop()
    fi = bucle.time() + DURADA_MAXIMA_S
    try:
        yield f"retry: 3000\n: connectat {json.dumps({'botiga_id': botiga, 'ara': temps.ara()})}\n\n"
        while (restant := fi - bucle.time()) > 0:
            try:
                ev = await asyncio.wait_for(sub.cua.get(), timeout=min(BATEC_S, restant))
            except TimeoutError:
                yield ": batec\n\n"
                continue
            yield ev.sse()
    finally:
        alertes.bus.dessubscriu(sub)


@router.get("/flux")
async def flux(request: Request, botiga: str | None = None, u: dict = Depends(rol(*BOTIGA_O_MES))):
    b = botiga_permesa(request.app.state.con, u, botiga)
    return StreamingResponse(_genera(b), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
