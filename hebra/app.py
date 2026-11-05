"""Aplicació web de Hebra (FastAPI).

Tres públics, tres zones:
  * /p/{token}       Fitxa NFC per al client (pública, sense galetes).
  * /botiga/...      Web del dependent, vendes i informe (contrasenya de botiga).
  * /api/v1/...      Entrada de la passarel·la (clau a la capçalera X-Hebra-Clau).

Arrencada:  uvicorn hebra.app:app --reload
"""

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__, db, fitxa, informes, passarella, proves, temps, textos, vendes
from .config import carrega

ARREL = Path(__file__).parent
cfg = carrega()
con = db.connecta(cfg.ruta_bd)
db.inicialitza(con)

log = logging.getLogger("hebra")


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


@asynccontextmanager
async def _cicle_de_vida(_app):
    tasca = asyncio.create_task(_bucle_processament()) if cfg.processa_cada_min > 0 else None
    yield
    if tasca:
        tasca.cancel()


app = FastAPI(title="Hebra", version=__version__, docs_url="/api/docs", redoc_url=None, lifespan=_cicle_de_vida)
app.mount("/static", StaticFiles(directory=ARREL / "static"), name="static")
plantilles = Jinja2Templates(directory=ARREL / "templates")
plantilles.env.globals["pais"] = textos.pais
seguretat = HTTPBasic()


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


@app.get("/", response_class=HTMLResponse)
def inici(request: Request):
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
        "idiomes": fitxa.IDIOMES, "b": b or "", "s": s, "ok": ok})


def _torna(token: str, b: str, lang: str, s: str, ok: str) -> RedirectResponse:
    from urllib.parse import urlencode
    return RedirectResponse(f"/p/{token}?{urlencode({'b': b, 'lang': lang, 's': s, 'ok': ok})}", status_code=303)


@app.post("/p/{token}/origen")
def veu_origen(token: str, b: str = Form(""), lang: str = Form("ca"), s: str = Form(...)):
    peca = fitxa.peca_per_token(con, token) or _404()
    fitxa.registra(con, s, b or None, peca["gtin"], "veu_origen", lang)
    return _torna(token, b, lang, s, "origen")


@app.post("/p/{token}/motiu")
def motiu(token: str, motiu: str = Form(...), b: str = Form(""), lang: str = Form("ca"), s: str = Form(...)):
    peca = fitxa.peca_per_token(con, token) or _404()
    try:
        fitxa.registra(con, s, b or None, peca["gtin"], "motiu_no_compra", lang, motiu)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _torna(token, b, lang, s, "motiu")


@app.post("/p/{token}/talla")
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


def _404():
    raise HTTPException(404, "Peça no trobada")


# ---------------------------------------------------------------- Botiga (dependent i informes)


@app.get("/botiga/peticions", response_class=HTMLResponse)
def peticions(request: Request, b: str | None = None, _: str = Depends(usuari_botiga)):
    files = con.execute(
        """SELECT pt.*, k.model, k.color FROM peticio_talla pt JOIN catalog_sku k ON k.gtin = pt.gtin_demanat
           WHERE (? IS NULL OR pt.botiga_id = ?) ORDER BY pt.estat = 'pendent' DESC, pt.hora_peticio DESC LIMIT 50""",
        (b, b)).fetchall()
    return plantilles.TemplateResponse(request, "peticions.html", {"files": files, "b": b or ""})


@app.post("/botiga/peticions/{pid}")
def resol(pid: int, estat: str = Form(...), b: str = Form(""), _: str = Depends(usuari_botiga)):
    try:
        fitxa.resol_peticio(con, pid, estat)
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
    return plantilles.TemplateResponse(request, "informe.html", {
        "r": dades, "anterior": (dilluns - timedelta(days=7)).isoformat(),
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
