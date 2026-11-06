"""Aplicació web de Hebra (FastAPI).

Zones:
  * /p/{token}       Fitxa NFC per al client (pública, sense galetes).
  * /app/...         Tauler de la marca i web del dependent (frontend/dist, si està compilat).
  * /api/v2/...      API del tauler (galeta de sessió `hebra_sessio`; contracte a docs/API.md).
  * /botiga/...      Pàgines antigues del dependent, vendes i informe (HTTP Basic de botiga).
  * /api/v1/...      Entrada de la passarel·la (clau a la capçalera X-Hebra-Clau).

Arrencada:  uvicorn hebra.app:app --reload   (un sol procés: les alertes en directe són en memòria)
"""

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__, api, auth, db, fitxa, informes, passarella, proves, retencio, temps, textos, vendes
from .config import carrega

ARREL = Path(__file__).parent
cfg = carrega()
con = db.ConnexioPerFil(cfg.ruta_bd)  # una connexió per fil (vegeu db.ConnexioPerFil)
db.inicialitza(con)

log = logging.getLogger("hebra")

# Capçaleres de seguretat. La CSP només permet recursos propis i l'script en línia de la fitxa (pel seu hash).
CSP = ("default-src 'self'; script-src 'self' '" + fitxa.HASH_SCRIPT + "'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
       "form-action 'self'; frame-ancestors 'none'")
SENSE_CSP = ("/api/docs", "/openapi.json")  # la documentació interactiva carrega Swagger UI d'un CDN


def processa_tot() -> None:
    """Recalcula proves i atribucions de totes les botigues (amb una connexió pròpia)."""
    c = db.connecta(cfg.ruta_bd)
    try:
        for b in c.execute("SELECT id FROM botiga").fetchall():
            proves.processa_botiga(c, b["id"], cfg.regla)
            vendes.atribueix(c, b["id"])
    finally:
        c.close()


async def _bucle_processament() -> None:
    while True:
        await asyncio.sleep(cfg.processa_cada_min * 60)
        try:
            await asyncio.to_thread(processa_tot)
        except Exception:
            log.exception("Error recalculant les proves")


def neteja_dades() -> dict:
    c = db.connecta(cfg.ruta_bd)
    try:
        return retencio.neteja(c, cfg.retencio_dies)
    finally:
        c.close()


async def _bucle_retencio() -> None:
    """Un cop en arrencar i després cada 24 h: esborra lectures i sensors més antics que HEBRA_RETENCIO_DIES."""
    while True:
        try:
            n = await asyncio.to_thread(neteja_dades)
            log.info("Retenció de dades: %s", n)
        except Exception:
            log.exception("Error esborrant dades antigues")
        await asyncio.sleep(24 * 3600)


@asynccontextmanager
async def _cicle_de_vida(_app):
    tasques = [asyncio.create_task(_bucle_retencio())] if cfg.retencio_dies > 0 else []
    if cfg.processa_cada_min > 0:
        tasques.append(asyncio.create_task(_bucle_processament()))
    yield
    for t in tasques:
        t.cancel()


class CapcaleresSeguretat:
    """Middleware ASGI (no fa de tap amb el flux SSE): afegeix les capçaleres de seguretat a cada resposta."""

    def __init__(self, app, segura: bool):
        self.app, self.segura = app, segura

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        amb_csp = not scope["path"].startswith(SENSE_CSP)

        async def envia(missatge):
            if missatge["type"] == "http.response.start":
                h = list(missatge.get("headers", []))
                h += [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer"),
                      (b"x-frame-options", b"DENY"),
                      (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), interest-cohort=()")]
                if amb_csp:
                    h.append((b"content-security-policy", CSP.encode()))
                if self.segura:
                    h.append((b"strict-transport-security", b"max-age=31536000"))
                missatge = dict(missatge, headers=h)
            await send(missatge)

        await self.app(scope, receive, envia)


# Sense CORS: el tauler se serveix des del mateix origen (/app) i l'API no accepta altres orígens.
app = FastAPI(title="Hebra", version=__version__, docs_url="/api/docs", redoc_url=None, lifespan=_cicle_de_vida)
app.add_middleware(CapcaleresSeguretat, segura=cfg.galeta_segura)
app.mount("/static", StaticFiles(directory=ARREL / "static"), name="static")
app.state.con = con
app.state.cfg = cfg
app.state.limit_sessio = auth.LimitIntents(maxim=10, finestra_s=15 * 60)
app.state.limit_fitxa = auth.CubellTestimonis(capacitat=30, ritme=0.5)
app.include_router(api.router)
plantilles = Jinja2Templates(directory=ARREL / "templates")
plantilles.env.globals["pais"] = textos.pais
seguretat = HTTPBasic()


@app.exception_handler(RequestValidationError)
async def _error_validacio(request: Request, exc: RequestValidationError):
    """A /api/v2 els errors de dades són 400 amb un missatge en català (docs/API.md)."""
    if not request.url.path.startswith("/api/v2"):
        from fastapi.exception_handlers import request_validation_exception_handler
        return await request_validation_exception_handler(request, exc)
    camps = sorted({".".join(str(x) for x in e.get("loc", [])[1:]) or "cos" for e in exc.errors()})
    return JSONResponse({"detail": f"Dades no vàlides: {', '.join(camps)}"}, status_code=400)


def limit_fitxa(request: Request) -> None:
    """Límit de peticions per IP als formularis públics de la fitxa NFC."""
    ip = request.client.host if request.client else "?"
    if not request.app.state.limit_fitxa.permet(ip):
        raise HTTPException(429, "Massa peticions. Espera un moment.")


def usuari_botiga(cred: HTTPBasicCredentials = Depends(seguretat)) -> str:
    ok = (secrets.compare_digest(cred.username.encode(), cfg.usuari_botiga.encode())
          and secrets.compare_digest(cred.password.encode(), cfg.contrasenya_botiga.encode()))
    if not ok:
        raise HTTPException(401, "Credencials incorrectes", headers={"WWW-Authenticate": "Basic"})
    return cred.username


def clau_passarella(x_hebra_clau: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_hebra_clau.encode(), cfg.clau_passarella.encode()):
        raise HTTPException(401, "Clau de passarel·la incorrecta")


def _idioma(lang: str | None, request: Request) -> str:
    if lang in fitxa.IDIOMES:
        return lang
    preferit = request.headers.get("accept-language", "ca")[:2].lower()
    return preferit if preferit in fitxa.IDIOMES else "ca"


@app.get("/salut")
def salut() -> dict:
    return {"estat": "ok", "versio": __version__}


def _dist() -> Path | None:
    d = Path(cfg.frontend_dist)
    return d if (d / "index.html").is_file() else None


@app.get("/", response_class=HTMLResponse)
def inici(request: Request):
    if _dist():
        return RedirectResponse("/app/", status_code=307)
    exemple = con.execute("SELECT nfc_token FROM etiqueta ORDER BY rowid LIMIT 1").fetchone()
    botiga = con.execute("SELECT id FROM botiga ORDER BY id LIMIT 1").fetchone()
    return plantilles.TemplateResponse(request, "inici.html", {
        "token": exemple["nfc_token"] if exemple else None, "botiga": botiga["id"] if botiga else None})


# ---------------------------------------------------------------- Fitxa NFC (client)


@app.get("/p/{token}", response_class=HTMLResponse)
def fitxa_peca(request: Request, token: str, b: str | None = None, lang: str | None = None,
               s: str | None = None, ok: str | None = None):
    """Pàgina que obre el mòbil en tocar l'etiqueta NFC.

    La URL gravada a l'NFC és /p/{token}?b={botiga}. `s` és la sessió tècnica
    (només dins la pàgina); si no hi és, és un toc nou i el registrem.
    """
    peca = fitxa.peca_per_token(con, token)
    if peca is None:
        raise HTTPException(404, "Peça no trobada")
    idioma = _idioma(lang, request)
    if not s:
        s = fitxa.nova_sessio()
        fitxa.registra(con, s, b, peca["gtin"], "obre_fitxa", idioma)
    return plantilles.TemplateResponse(request, "fitxa.html", {
        "p": fitxa.dades_fitxa(con, peca, b, idioma), "t": textos.TEXTOS[idioma], "lang": idioma,
        "idiomes": fitxa.IDIOMES, "b": b or "", "s": s, "ok": ok, "script": fitxa.SCRIPT_SECCIONS})


def _torna(token: str, b: str, lang: str, s: str, ok: str) -> RedirectResponse:
    from urllib.parse import urlencode
    return RedirectResponse(f"/p/{token}?{urlencode({'b': b, 'lang': lang, 's': s, 'ok': ok})}", status_code=303)


@app.post("/p/{token}/origen", dependencies=[Depends(limit_fitxa)])
def veu_origen(token: str, b: str = Form(""), lang: str = Form("ca"), s: str = Form(...)):
    peca = fitxa.peca_per_token(con, token) or _404()
    fitxa.registra(con, s, b or None, peca["gtin"], "veu_origen", lang)
    return _torna(token, b, lang, s, "origen")


@app.post("/p/{token}/motiu", dependencies=[Depends(limit_fitxa)])
def motiu(token: str, motiu: str = Form(...), b: str = Form(""), lang: str = Form("ca"), s: str = Form(...)):
    peca = fitxa.peca_per_token(con, token) or _404()
    try:
        fitxa.registra(con, s, b or None, peca["gtin"], "motiu_no_compra", lang, motiu)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _torna(token, b, lang, s, "motiu")


@app.post("/p/{token}/talla", dependencies=[Depends(limit_fitxa)])
def talla(token: str, gtin: str = Form(...), cabina: str = Form(""), b: str = Form(""),
          lang: str = Form("ca"), s: str = Form(...)):
    peca = fitxa.peca_per_token(con, token) or _404()
    if not b:
        raise HTTPException(400, "La petició de talla necessita saber la botiga")
    try:
        fitxa.demana_talla(con, s, b, peca["gtin"], gtin, lang, cabina[:20] or None)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _torna(token, b, lang, s, "talla")


@app.post("/p/{token}/seccio", status_code=204, dependencies=[Depends(limit_fitxa)])
def seccio(token: str, seccio: str = Form(...), b: str = Form(""), lang: str = Form("ca"), s: str = Form(...)):
    """Balisa (navigator.sendBeacon) quan el client obre una secció plegable de la fitxa (insight 16)."""
    peca = fitxa.peca_per_token(con, token) or _404()
    try:
        fitxa.registra(con, s[:40], b or None, peca["gtin"], "veu_seccio", lang, seccio)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return Response(status_code=204)


def _404():
    raise HTTPException(404, "Peça no trobada")


# ---------------------------------------------------------------- Botiga (dependent i informes)


@app.get("/botiga/peticions", response_class=HTMLResponse)
def peticions(request: Request, b: str | None = None, _: str = Depends(usuari_botiga)):
    files = con.execute(
        """SELECT pt.*, k.model, k.color FROM peticio_talla pt JOIN catalog_sku k ON k.gtin = pt.gtin_demanat
           WHERE (? IS NULL OR pt.botiga_id = ?) ORDER BY pt.estat IN ('pendent', 'en_cami') DESC, pt.hora_peticio DESC LIMIT 50""",
        (b, b)).fetchall()
    return plantilles.TemplateResponse(request, "peticions.html", {"files": files, "b": b or ""})


@app.post("/botiga/peticions/{pid}")
def resol(pid: int, estat: str = Form(...), b: str = Form(""), _: str = Depends(usuari_botiga)):
    try:
        fitxa.resol_peticio(con, pid, estat)  # si la transició no és permesa (ja resolta), no fa res
    except ValueError:
        raise HTTPException(400, "Estat no vàlid")
    return RedirectResponse(f"/botiga/peticions?b={b}" if b else "/botiga/peticions", status_code=303)


@app.get("/botiga/vendes", response_class=HTMLResponse)
def vendes_form(request: Request, _: str = Depends(usuari_botiga)):
    return plantilles.TemplateResponse(request, "vendes.html", {"resultat": None})


@app.post("/botiga/vendes", response_class=HTMLResponse)
async def vendes_puja(request: Request, fitxer: UploadFile, _: str = Depends(usuari_botiga)):
    text = (await fitxer.read()).decode("utf-8-sig")
    n, errors = vendes.importa_csv(con, text)
    atribuides = {b["id"]: vendes.atribueix(con, b["id"]) for b in con.execute("SELECT id FROM botiga").fetchall()}
    return plantilles.TemplateResponse(request, "vendes.html", {
        "resultat": {"importades": n, "errors": errors[:50], "atribuides": atribuides}})


@app.get("/botiga/informe", response_class=HTMLResponse)
def informe(request: Request, b: str, setmana: str | None = None, _: str = Depends(usuari_botiga)):
    if setmana:
        dilluns = date.fromisoformat(setmana)
    else:
        darrera = con.execute(
            "SELECT MAX(s.inici) FROM sessio s JOIN cabina c ON c.id = s.cabina_id WHERE c.botiga_id = ?",
            (b,)).fetchone()[0]
        avui = date.fromisoformat(darrera[:10]) if darrera else date.fromisoformat(temps.ara()[:10])
        dilluns = avui - timedelta(days=avui.weekday())
    dilluns -= timedelta(days=dilluns.weekday())
    dades = informes.setmanal(con, b, dilluns)
    nivell = con.execute("SELECT nivell FROM botiga WHERE id = ?", (b,)).fetchone()
    return plantilles.TemplateResponse(request, "informe.html", {
        "r": dades, "nivell": nivell["nivell"] if nivell else "cabina", "anterior": (dilluns - timedelta(days=7)).isoformat(),
        "seguent": (dilluns + timedelta(days=7)).isoformat()})


# ---------------------------------------------------------------- API de la passarel·la


@app.post("/api/v1/lots", dependencies=[Depends(clau_passarella)])
def rep_lot(lot: dict) -> dict:
    """Rep un lot de lectures agregades i esdeveniments de sensors (vegeu hebra/passarella.py)."""
    res = passarella.desa_lot(con, lot)
    return {"lectures": res.lectures, "sensors": res.sensors, "errors": res.errors}


@app.post("/api/v1/processa", dependencies=[Depends(clau_passarella)])
def processa(botiga: str) -> dict:
    """Recalcula sessions, proves i atribucions d'una botiga. Es pot cridar cada nit (cron)."""
    n_proves = proves.processa_botiga(con, botiga, cfg.regla)
    n_atrib = vendes.atribueix(con, botiga)
    return {"proves": n_proves, "atribucions": n_atrib}


# ---------------------------------------------------------------- Tauler (frontend compilat)


@app.get("/app", include_in_schema=False)
def app_sense_barra():
    return RedirectResponse("/app/", status_code=307)


@app.get("/app/{ruta:path}", include_in_schema=False)
def tauler(ruta: str):
    """Serveix frontend/dist. Qualsevol camí que no sigui un fitxer torna index.html (SPA)."""
    dist = _dist()
    if dist is None:
        raise HTTPException(404, "El tauler no està compilat (cal `npm run build` a frontend/)")
    arrel = dist.resolve()
    fitxer = (arrel / ruta).resolve()
    if ruta and fitxer.is_file() and fitxer.is_relative_to(arrel):
        cau = "public, max-age=31536000, immutable" if "/assets/" in f"/{ruta}" else "no-cache"
        return FileResponse(fitxer, headers={"Cache-Control": cau})
    return FileResponse(arrel / "index.html", headers={"Cache-Control": "no-cache"})
