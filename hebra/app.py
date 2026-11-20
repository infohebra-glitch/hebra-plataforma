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
import re
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

from . import __version__, api, auth, db, fitxa, fitxa_config, informes, passarella, proves, retencio, temps, textos, vendes
from . import informes_programats, provadors
from .integracions import motor as integracions_motor
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
# La previsualització de la fitxa (v0.3, A.3) es mostra dins d'un iframe del tauler (mateix origen).
IFRAME_MATEIX_ORIGEN = ("/api/v2/fitxa/previsualitza",)
CSP_IFRAME = CSP.replace("frame-ancestors 'none'", "frame-ancestors 'self'")


def processa_tot() -> None:
    """Recalcula proves i atribucions de totes les botigues (amb una connexió pròpia)."""
    c = db.connecta(cfg.ruta_bd)
    try:
        for b in c.execute("SELECT id FROM botiga").fetchall():
            proves.processa_botiga(c, b["id"], cfg.regla)
            vendes.atribueix(c, b["id"])
    finally:
        c.close()


def sincronitza_integracions() -> dict:
    """v0.3 F: sincronitza les integracions a qui toca (cada `interval_min`) i les botigues amb
    Shopify per variables d'entorn (v0.2, cada hora). Amb una connexió pròpia."""
    c = db.connecta(cfg.ruta_bd)
    try:
        return integracions_motor.sincronitza_pendents(c, cfg.secret)
    finally:
        c.close()


async def _bucle_integracions() -> None:
    """Cada minut mira si a alguna integració li toca sincronitzar-se (vegeu hebra/integracions/motor.py)."""
    while True:
        await asyncio.sleep(60)
        try:
            n = await asyncio.to_thread(sincronitza_integracions)
            if n:
                log.info("Integracions: %s", n)
        except Exception:
            log.exception("Error sincronitzant les integracions")


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


def informes_programats_pendents() -> list[int]:
    """Genera (i envia, si hi ha SMTP) els informes programats que toquen (amb una connexió pròpia)."""
    c = db.connecta(cfg.ruta_bd)
    try:
        return informes_programats.executa_pendents(c, cfg)
    finally:
        c.close()


async def _bucle_informes() -> None:
    """Cada minut mira si toca generar algun informe programat (v0.3, E.1)."""
    while True:
        await asyncio.sleep(60)
        try:
            fets = await asyncio.to_thread(informes_programats_pendents)
            if fets:
                log.info("Informes programats generats: %s", fets)
        except Exception:
            log.exception("Error generant els informes programats")


def publica_cabines_pendents() -> int:
    """Publica l'estat de les cabines que el throttle de 5 s havia deixat pendents (amb una connexió pròpia)."""
    c = db.connecta(cfg.ruta_bd)
    try:
        return provadors.publica_pendents(c)
    finally:
        c.close()


async def _bucle_cabines() -> None:
    """Cada segon: si una cabina té un canvi pendent i ja ha passat la finestra, se'n publica l'estat (SSE)."""
    while True:
        await asyncio.sleep(1)
        if not provadors.hi_ha_pendents():
            continue
        try:
            await asyncio.to_thread(publica_cabines_pendents)
        except Exception:
            log.exception("Error publicant l'estat de les cabines")


@asynccontextmanager
async def _cicle_de_vida(_app):
    tasques = [asyncio.create_task(_bucle_retencio())] if cfg.retencio_dies > 0 else []
    if cfg.processa_cada_min > 0:
        tasques.append(asyncio.create_task(_bucle_processament()))
    tasques.append(asyncio.create_task(_bucle_integracions()))
    tasques.append(asyncio.create_task(_bucle_informes()))
    tasques.append(asyncio.create_task(_bucle_cabines()))
    yield
    for t in tasques:
        t.cancel()


MIDA_MAXIMA_COS = 12 * 1024 * 1024   # importacions CSV (10 MB) i lots de la passarel·la
METODES_SEGURS = ("GET", "HEAD", "OPTIONS")
# Rutes amb sessió del navegador (galeta o HTTP Basic): només s'accepten escriptures des de la mateixa web.
RUTES_AMB_SESSIO = ("/api/v2/", "/botiga/")
SENSE_MEMORIA_CAU = ("/p/", "/api/", "/botiga/")


def _capcalera(scope, nom: bytes) -> str:
    return next((v.decode("latin-1") for k, v in scope.get("headers", []) if k == nom), "")


async def _respon(send, estat: int, detall: str) -> None:
    cos = ('{"detail": "' + detall + '"}').encode()
    await send({"type": "http.response.start", "status": estat,
                "headers": [(b"content-type", b"application/json; charset=utf-8"),
                            (b"content-length", str(len(cos)).encode())]})
    await send({"type": "http.response.body", "body": cos})


class Proteccions:
    """Middleware ASGI (no fa de tap amb el flux SSE):

      * afegeix les capçaleres de seguretat a cada resposta;
      * rebutja cossos de petició massa grans (413), encara que no declarin la mida;
      * a les rutes amb sessió del navegador, rebutja les escriptures que venen d'una altra
        web (capçalera Origin diferent del nostre domini): defensa contra CSRF a més de SameSite.
    """

    def __init__(self, app, segura: bool):
        self.app, self.segura = app, segura

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        cami = scope["path"]
        amb_csp = not cami.startswith(SENSE_CSP)
        iframe = cami.startswith(IFRAME_MATEIX_ORIGEN)

        async def envia(missatge):
            if missatge["type"] == "http.response.start":
                h = list(missatge.get("headers", []))
                h += [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer"),
                      (b"x-frame-options", b"SAMEORIGIN" if iframe else b"DENY"),
                      (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), interest-cohort=()"),
                      (b"x-robots-tag", b"noindex, nofollow")]
                if amb_csp:
                    h.append((b"content-security-policy", (CSP_IFRAME if iframe else CSP).encode()))
                if self.segura:
                    h.append((b"strict-transport-security", b"max-age=31536000"))
                if cami.startswith(SENSE_MEMORIA_CAU) and not any(k.lower() == b"cache-control" for k, _ in h):
                    h.append((b"cache-control", b"no-store"))
                missatge = dict(missatge, headers=h)
            await send(missatge)

        if scope["method"] not in METODES_SEGURS:
            origen = _capcalera(scope, b"origin")
            if origen and origen != "null" and cami.startswith(RUTES_AMB_SESSIO):
                from urllib.parse import urlsplit
                if urlsplit(origen).netloc.lower() != _capcalera(scope, b"host").lower():
                    return await _respon(envia, 403, "Petició des d'un altre lloc web")
            declarada = _capcalera(scope, b"content-length")
            if declarada.isdigit() and int(declarada) > MIDA_MAXIMA_COS:
                return await _respon(envia, 413, "La petició és massa gran")
            rebut = 0

            async def rep():
                nonlocal rebut
                missatge = await receive()
                if missatge["type"] == "http.request":
                    rebut += len(missatge.get("body", b""))
                    if rebut > MIDA_MAXIMA_COS:
                        raise HTTPException(413, "La petició és massa gran")
                return missatge

            return await self.app(scope, rep, envia)
        await self.app(scope, receive, envia)


# Sense CORS: el tauler se serveix des del mateix origen (/app) i l'API no accepta altres orígens.
# La documentació interactiva de l'API només en desenvolupament.
app = FastAPI(title="Hebra", version=__version__, docs_url=None if cfg.produccio else "/api/docs", redoc_url=None,
              openapi_url=None if cfg.produccio else "/openapi.json", lifespan=_cicle_de_vida)
app.add_middleware(Proteccions, segura=cfg.galeta_segura)
app.mount("/static", StaticFiles(directory=ARREL / "static"), name="static")
app.state.con = con
app.state.cfg = cfg
app.state.limit_sessio = auth.LimitIntents(maxim=10, finestra_s=15 * 60)
app.state.limit_fitxa = auth.CubellTestimonis(capacitat=30, ritme=0.5)       # formularis de la fitxa
app.state.limit_fitxa_get = auth.CubellTestimonis(capacitat=60, ritme=1.0)   # obrir fitxes
app.state.limit_no_trobada = auth.LimitIntents(maxim=20, finestra_s=10 * 60)  # qui prova codis de fitxa a l'atzar
app.state.limit_botiga = auth.LimitIntents(maxim=10, finestra_s=15 * 60)     # usuari bàsic de /botiga
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


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def limit_fitxa(request: Request) -> None:
    """Límit de peticions per IP als formularis públics de la fitxa NFC."""
    if not request.app.state.limit_fitxa.permet(_ip(request)):
        raise HTTPException(429, "Massa peticions. Espera un moment.")


def limit_fitxa_get(request: Request) -> None:
    """Límit per IP en obrir fitxes, i bloqueig de qui prova molts codis que no existeixen."""
    ip = _ip(request)
    if request.app.state.limit_no_trobada.bloquejat(ip) or not request.app.state.limit_fitxa_get.permet(ip):
        raise HTTPException(429, "Massa peticions. Espera un moment.")


def usuari_botiga(request: Request, cred: HTTPBasicCredentials = Depends(seguretat)) -> str:
    if not cfg.botiga_antiga_activa:
        raise HTTPException(404, "Aquesta pàgina no està activada: fes servir el tauler (/app)")
    ip = _ip(request)
    if request.app.state.limit_botiga.bloquejat(ip):
        raise HTTPException(429, "Massa intents. Torna-ho a provar d'aquí a una estona.")
    ok = (secrets.compare_digest(cred.username.encode(), cfg.usuari_botiga.encode())
          and secrets.compare_digest(cred.password.encode(), cfg.contrasenya_botiga.encode()))
    if not ok:
        request.app.state.limit_botiga.falla(ip)
        raise HTTPException(401, "Credencials incorrectes", headers={"WWW-Authenticate": "Basic"})
    return cred.username


def clau_passarella(x_hebra_clau: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_hebra_clau.encode(), cfg.clau_passarella.encode()):
        raise HTTPException(401, "Clau de passarel·la incorrecta")


@app.get("/salut")
def salut() -> dict:
    """Per al monitor: 200 si la web i la base de dades responen."""
    try:
        con.execute("SELECT 1 FROM botiga LIMIT 1").fetchall()
    except Exception:
        log.exception("La base de dades no respon")
        raise HTTPException(503, "La base de dades no respon")
    return {"estat": "ok", "versio": __version__}


def _dist() -> Path | None:
    d = Path(cfg.frontend_dist)
    return d if (d / "index.html").is_file() else None


@app.get("/", response_class=HTMLResponse)
def inici(request: Request):
    if _dist() or cfg.produccio:
        return RedirectResponse("/app/", status_code=307)
    # Només en desenvolupament: pàgina d'inici amb una fitxa d'exemple.
    exemple = con.execute("SELECT nfc_token FROM etiqueta ORDER BY rowid LIMIT 1").fetchone()
    botiga = con.execute("SELECT id FROM botiga ORDER BY id LIMIT 1").fetchone()
    return plantilles.TemplateResponse(request, "inici.html", {
        "token": exemple["nfc_token"] if exemple else None, "botiga": botiga["id"] if botiga else None})


# ---------------------------------------------------------------- Fitxa NFC (client)
#
# És l'única part pública: tothom qui té l'enllaç d'una peça la pot obrir, des d'on sigui.
# Per això tot el que arriba es valida aquí: la botiga ha d'existir, la sessió tècnica ha de
# tenir la forma que genera el servidor, i les peticions al dependent tenen límits (hebra/fitxa.py).

_ROBOTS = re.compile(r"bot|crawl|spider|preview|whatsapp|facebookexternalhit|slack|telegram|twitter|discord|"
                     r"linkedin|pinterest|curl|wget|python-requests|headless", re.IGNORECASE)


def _peca(request: Request, token: str):
    peca = fitxa.peca_per_token(con, token) if 6 <= len(token) <= 64 else None
    if peca is None:
        request.app.state.limit_no_trobada.falla(_ip(request))
        raise HTTPException(404, "Peça no trobada")
    return peca


def _sessio_form(s: str) -> str:
    if not fitxa.sessio_valida(s):
        raise HTTPException(400, "Torna a obrir la fitxa tocant la peça amb el mòbil")
    return s


def _botiga_form(b: str) -> str:
    botiga = fitxa.botiga_existent(con, b)
    if botiga is None:
        raise HTTPException(400, "Aquesta acció necessita saber la botiga: torna a tocar la peça amb el mòbil")
    return botiga


@app.get("/p/{token}", response_class=HTMLResponse, dependencies=[Depends(limit_fitxa_get)])
def fitxa_peca(request: Request, token: str, b: str | None = None, lang: str | None = None,
               s: str | None = None, ok: str | None = None):
    """Pàgina que obre el mòbil en tocar l'etiqueta NFC.

    La URL gravada a l'NFC és /p/{token}?b={botiga}. `s` és la sessió tècnica
    (només dins la pàgina); si no hi és, és un toc nou i el registrem.
    """
    peca = _peca(request, token)
    b = fitxa.botiga_existent(con, b)  # una botiga que no existeix es tracta com «sense botiga»
    cfg_fitxa = fitxa_config.efectiva(con, b)  # v0.3: configuració de la marca (general + botiga)
    idioma = fitxa.tria_idioma(lang, request.headers.get("accept-language"), cfg_fitxa["idiomes"])
    if not fitxa.sessio_valida(s):
        s = fitxa.nova_sessio()
        # Les previsualitzacions d'enllaços (WhatsApp, cercadors...) no són tocs de clients: no es compten.
        if not _ROBOTS.search(request.headers.get("user-agent", "")):
            fitxa.registra(con, s, b, peca["gtin"], "obre_fitxa", idioma)
    if ok not in ("talla", "assistencia", "motiu", "origen", "limit"):
        ok = None
    return plantilles.TemplateResponse(request, "fitxa.html",
                                       fitxa.context_pagina(con, peca, b, idioma, cfg_fitxa, s, ok))


def _accio_activa(b: str | None, accio: str) -> None:
    """La marca pot desactivar un botó de la fitxa: el formulari tampoc s'accepta."""
    if not fitxa_config.efectiva(con, b or None)["accions"].get(accio, True):
        raise HTTPException(400, "Aquesta acció no està activada en aquesta botiga")


def _torna(token: str, b: str | None, lang: str, s: str, ok: str) -> RedirectResponse:
    from urllib.parse import urlencode
    lang = lang if lang in fitxa.IDIOMES else "ca"
    return RedirectResponse(f"/p/{token}?{urlencode({'b': b or '', 'lang': lang, 's': s, 'ok': ok})}", status_code=303)


@app.post("/p/{token}/origen", dependencies=[Depends(limit_fitxa)])
def veu_origen(request: Request, token: str, b: str = Form(""), lang: str = Form("ca"), s: str = Form(...)):
    peca, s, b = _peca(request, token), _sessio_form(s), fitxa.botiga_existent(con, b)
    fitxa.registra(con, s, b, peca["gtin"], "veu_origen", lang)
    return _torna(token, b, lang, s, "origen")


@app.post("/p/{token}/motiu", dependencies=[Depends(limit_fitxa)])
def motiu(request: Request, token: str, motiu: str = Form(...), b: str = Form(""), lang: str = Form("ca"),
          s: str = Form(...)):
    peca, s, b = _peca(request, token), _sessio_form(s), fitxa.botiga_existent(con, b)
    _accio_activa(b, "per_que_no")
    if fitxa.ja_ha_dit_motiu(con, s, peca["gtin"]):  # un motiu per visita i peça
        return _torna(token, b, lang, s, "motiu")
    if fitxa_config.es_propi(motiu) and motiu not in fitxa_config.efectiva(con, b)["motius"]:
        raise HTTPException(400, "Motiu desconegut")  # un motiu propi ha d'existir a la configuració
    try:
        fitxa.registra(con, s, b, peca["gtin"], "motiu_no_compra", lang, motiu)
    except ValueError:
        raise HTTPException(400, "Motiu desconegut")
    return _torna(token, b, lang, s, "motiu")


@app.post("/p/{token}/talla", dependencies=[Depends(limit_fitxa)])
def talla(request: Request, token: str, gtin: str = Form(...), cabina: str = Form(""), b: str = Form(""),
          lang: str = Form("ca"), s: str = Form(...)):
    peca, s, b = _peca(request, token), _sessio_form(s), _botiga_form(b)
    _accio_activa(b, "demana_talla")
    try:
        fitxa.demana_talla(con, s, b, peca["gtin"], gtin[:14], lang, fitxa.neteja_cabina(cabina))
    except fitxa.MassaPeticions:
        return _torna(token, b, lang, s, "limit")
    except ValueError:
        raise HTTPException(400, "Talla desconeguda")
    return _torna(token, b, lang, s, "talla")


@app.post("/p/{token}/assistencia", dependencies=[Depends(limit_fitxa)])
def assistencia(request: Request, token: str, cabina: str = Form(""), b: str = Form(""), lang: str = Form("ca"),
                s: str = Form(...)):
    """«Vull que m'atenguin» (v0.3, A.4): avís a la web del dependent, a la mateixa llista que les peticions de talla."""
    peca, s, b = _peca(request, token), _sessio_form(s), _botiga_form(b)
    _accio_activa(b, "demana_assistencia")
    try:
        fitxa.demana_assistencia(con, s, b, peca["gtin"], lang, fitxa.neteja_cabina(cabina))
    except fitxa.MassaPeticions:
        return _torna(token, b, lang, s, "limit")
    return _torna(token, b, lang, s, "assistencia")


@app.post("/p/{token}/seccio", status_code=204, dependencies=[Depends(limit_fitxa)])
def seccio(request: Request, token: str, seccio: str = Form(...), b: str = Form(""), lang: str = Form("ca"),
           s: str = Form(...)):
    """Balisa (navigator.sendBeacon) quan el client obre una secció plegable de la fitxa (insight 16)."""
    peca, s, b = _peca(request, token), _sessio_form(s), fitxa.botiga_existent(con, b)
    if fitxa_config.es_propi(seccio) and seccio not in fitxa_config.efectiva(con, b)["seccions"]["ordre"]:
        raise HTTPException(400, "Secció desconeguda")
    try:
        fitxa.registra(con, s, b, peca["gtin"], "veu_seccio", lang, seccio)
    except ValueError:
        raise HTTPException(400, "Secció desconeguda")
    return Response(status_code=204)


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
    b = fitxa.botiga_existent(con, b)
    return RedirectResponse(f"/botiga/peticions?b={b}" if b else "/botiga/peticions", status_code=303)


@app.get("/botiga/vendes", response_class=HTMLResponse)
def vendes_form(request: Request, _: str = Depends(usuari_botiga)):
    return plantilles.TemplateResponse(request, "vendes.html", {"resultat": None})


@app.post("/botiga/vendes", response_class=HTMLResponse)
async def vendes_puja(request: Request, fitxer: UploadFile, _: str = Depends(usuari_botiga)):
    try:
        text = (await fitxer.read(MIDA_MAXIMA_COS)).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "El fitxer ha de ser un CSV en UTF-8")

    def importa():
        n, errors, repetides = vendes.importa_csv_sense_repetir(con, text)
        atribuides = {b["id"]: vendes.atribueix(con, b["id"]) for b in con.execute("SELECT id FROM botiga").fetchall()}
        return {"importades": n, "errors": errors[:50], "atribuides": atribuides, "repetides": repetides}
    return plantilles.TemplateResponse(request, "vendes.html", {"resultat": await asyncio.to_thread(importa)})


@app.get("/botiga/informe", response_class=HTMLResponse)
def informe(request: Request, b: str, setmana: str | None = None, _: str = Depends(usuari_botiga)):
    if not con.execute("SELECT 1 FROM botiga WHERE id = ?", (b,)).fetchone():
        raise HTTPException(404, "Botiga desconeguda")
    if setmana:
        try:
            dilluns = date.fromisoformat(setmana)
        except ValueError:
            raise HTTPException(400, "Setmana no vàlida (format AAAA-MM-DD)")
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
    try:
        res = passarella.desa_lot(con, lot, passarella.MAXIM_ELEMENTS)
    except passarella.LotMassaGran as e:
        raise HTTPException(413, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"lectures": res.lectures, "sensors": res.sensors, "repetits": res.repetits, "errors": res.errors[:100]}


@app.post("/api/v1/processa", dependencies=[Depends(clau_passarella)])
def processa(botiga: str, tot: bool = False) -> dict:
    """Posa al dia sessions, proves i atribucions d'una botiga. Amb `tot=1` ho recalcula tot
    (després de canviar el catàleg o les etiquetes, per exemple)."""
    if not con.execute("SELECT 1 FROM botiga WHERE id = ?", (botiga,)).fetchone():
        raise HTTPException(404, f"Botiga desconeguda: {botiga}")
    n_proves = proves.processa_botiga(con, botiga, cfg.regla, tot)
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
