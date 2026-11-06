"""Informes: al moment, programats, lliurats, PDF i correu (docs/ESPECIFICACIO-v3.md, E.3 i E.4).

ORDRE DE LES RUTES: les rutes fixes (`/informes/programacio`, `/informes/lliurats`...)
i les que acaben en `.pdf` es declaren ABANS de `/informes/{tipus}`; si no, el
paràmetre `{tipus}` les capturaria (Starlette prova les rutes per ordre).

Permisos: la programació la gestiona la marca (la botiga la veu, només la seva);
els lliurats els veu tothom (la botiga, només els de la seva botiga, no els de
totes les botigues); enviar per correu, qualsevol que pugui veure l'informe.
"""

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from hebra import analitica, correu, informe_pdf, informes_programats as ip, temps

from .comu import BOTIGA_O_MES, MARCA_O_MES, bd, botiga_permesa, data, filtre, rol, usuari

router = APIRouter(tags=["informes"])

TipusInforme = Literal["diari", "setmanal", "mensual", "temporada", "pilot", "mango"]
_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _tipus(tipus: str) -> str:
    if tipus not in ip.TIPUS:
        raise HTTPException(404, f"Informe desconegut: {tipus}")
    return tipus


def _pdf(contingut: bytes, nom: str) -> Response:
    return Response(contingut, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{nom}"'})


class Destinataris(BaseModel):
    destinataris: list[str] = Field(min_length=1, max_length=correu.MAX_DESTINATARIS)


def _envia(fn):
    """Crida un enviament i converteix ErrorCorreu en 400 amb el motiu."""
    try:
        return fn()
    except correu.ErrorCorreu as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------- Programació


class NovaProgramacio(BaseModel):
    botiga_id: str | None = None
    tipus: TipusInforme
    actiu: bool = True
    dia_setmana: int | None = Field(default=None, ge=0, le=6)
    dia_mes: int | None = Field(default=None, ge=1, le=28)
    data: str | None = None
    hora: str = "08:00"
    destinataris: list[str] = Field(default_factory=list, max_length=correu.MAX_DESTINATARIS)


class CanviProgramacio(BaseModel):
    botiga_id: str | None = None
    tipus: TipusInforme | None = None
    actiu: bool | None = None
    dia_setmana: int | None = Field(default=None, ge=0, le=6)
    dia_mes: int | None = Field(default=None, ge=1, le=28)
    data: str | None = None
    hora: str | None = None
    destinataris: list[str] | None = Field(default=None, max_length=correu.MAX_DESTINATARIS)


def _valida_programacio(con: sqlite3.Connection, v: dict) -> dict:
    """Valida la programació sencera (després d'aplicar-hi els canvis) i la normalitza."""
    if v.get("botiga_id") and not con.execute("SELECT 1 FROM botiga WHERE id = ?", (v["botiga_id"],)).fetchone():
        raise HTTPException(400, f"Botiga desconeguda: {v['botiga_id']}")
    if not _HORA.match(v.get("hora") or ""):
        raise HTTPException(400, "Hora no vàlida (format HH:MM)")
    t = v["tipus"]
    if t == "setmanal" and v.get("dia_setmana") is None:
        raise HTTPException(400, "Un informe setmanal necessita «dia_setmana» (0 = dilluns)")
    if t == "mensual" and v.get("dia_mes") is None:
        raise HTTPException(400, "Un informe mensual necessita «dia_mes» (1-28)")
    if t in ip.UNA_VEGADA:
        if not v.get("data"):
            raise HTTPException(400, f"Un informe «{t}» es genera una vegada: cal «data»")
        data(v["data"], "data")
    # Només es desen els camps que fan servir el tipus.
    v["dia_setmana"] = v.get("dia_setmana") if t == "setmanal" else None
    v["dia_mes"] = v.get("dia_mes") if t == "mensual" else None
    v["data"] = v.get("data") if t in ip.UNA_VEGADA else None
    dest = v.get("destinataris") or []
    if isinstance(dest, str):
        dest = json.loads(dest)
    try:
        v["destinataris"] = correu.valida_destinataris(dest) if dest else []
    except correu.ErrorCorreu as e:
        raise HTTPException(400, str(e))
    return v


@router.get("/informes/programacio")
def llista_programacio(botiga: str | None = None, con: sqlite3.Connection = Depends(bd),
                       u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    b = botiga_permesa(con, u, botiga)
    files = con.execute("SELECT * FROM programacio_informe WHERE (? IS NULL OR botiga_id = ?) ORDER BY id",
                        (b, b)).fetchall()
    ara = datetime.now(timezone.utc)
    return {"programacions": [ip.programacio_json(con, f, ara) for f in files]}


@router.post("/informes/programacio")
def nova_programacio(cos: NovaProgramacio, con: sqlite3.Connection = Depends(bd),
                     _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    v = _valida_programacio(con, cos.model_dump())
    pid = con.execute(
        """INSERT INTO programacio_informe (botiga_id, tipus, actiu, dia_setmana, dia_mes, data, hora, destinataris, creada)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (v["botiga_id"], v["tipus"], int(v["actiu"]), v["dia_setmana"], v["dia_mes"], v["data"], v["hora"],
         json.dumps(v["destinataris"]), temps.ara())).lastrowid
    con.commit()
    return ip.programacio(con, pid)


@router.patch("/informes/programacio/{pid}")
def canvia_programacio(pid: int, cos: CanviProgramacio, con: sqlite3.Connection = Depends(bd),
                       _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    fila = con.execute("SELECT * FROM programacio_informe WHERE id = ?", (pid,)).fetchone()
    if fila is None:
        raise HTTPException(404, "Programació no trobada")
    canvis = cos.model_dump(exclude_unset=True)
    for camp in ("tipus", "actiu", "hora", "destinataris"):
        if camp in canvis and canvis[camp] is None:
            raise HTTPException(400, f"«{camp}» no pot ser buit")
    v = _valida_programacio(con, dict(fila) | canvis)
    con.execute("""UPDATE programacio_informe SET botiga_id = ?, tipus = ?, actiu = ?, dia_setmana = ?, dia_mes = ?,
                   data = ?, hora = ?, destinataris = ? WHERE id = ?""",
                (v["botiga_id"], v["tipus"], int(bool(v["actiu"])), v["dia_setmana"], v["dia_mes"], v["data"],
                 v["hora"], json.dumps(v["destinataris"]), pid))
    con.commit()
    return ip.programacio(con, pid)


@router.delete("/informes/programacio/{pid}")
def esborra_programacio(pid: int, con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    if not con.execute("SELECT 1 FROM programacio_informe WHERE id = ?", (pid,)).fetchone():
        raise HTTPException(404, "Programació no trobada")
    # Els lliurats es queden (programacio_id passa a NULL).
    con.execute("UPDATE informe_lliurat SET programacio_id = NULL WHERE programacio_id = ?", (pid,))
    con.execute("DELETE FROM programacio_informe WHERE id = ?", (pid,))
    con.commit()
    return {"ok": True}


# ---------------------------------------------------------------- Lliurats


class NouLliurat(BaseModel):
    tipus: TipusInforme
    botiga: str | None = None
    des: str
    fins: str


def _lliurat_permes(con: sqlite3.Connection, u: dict, lid: int) -> sqlite3.Row:
    f = ip.lliurat(con, lid)
    if f is None or (u["rol"] == "botiga" and f["botiga_id"] != u["botiga_id"]):
        raise HTTPException(404, "Informe no trobat")
    return f


@router.get("/informes/lliurats")
def llista_lliurats(botiga: str | None = None, tipus: str | None = None, con: sqlite3.Connection = Depends(bd),
                    u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    if tipus:
        _tipus(tipus)
    b = botiga_permesa(con, u, botiga)
    files = con.execute(
        """SELECT * FROM informe_lliurat WHERE (? IS NULL OR botiga_id = ?) AND (? IS NULL OR tipus = ?)
           ORDER BY generat DESC, id DESC LIMIT 500""", (b, b, tipus, tipus)).fetchall()
    return {"lliurats": [ip.lliurat_resum(f) for f in files]}


@router.post("/informes/lliurats")
def nou_lliurat(cos: NouLliurat, con: sqlite3.Connection = Depends(bd), u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    """«Genera ara»: calcula l'informe del període i el desa com a lliurat (no l'envia)."""
    b = botiga_permesa(con, u, cos.botiga)
    des, fins = data(cos.des, "des"), data(cos.fins, "fins")
    if des > fins:
        raise HTTPException(400, "«des» ha de ser anterior o igual a «fins»")
    lid = ip.genera(con, cos.tipus, b, des, fins)
    return ip.lliurat_resum(ip.lliurat(con, lid))


@router.get("/informes/lliurats/{lid}.pdf")
def lliurat_pdf(lid: int, con: sqlite3.Connection = Depends(bd), u: dict = Depends(usuari)) -> Response:
    f = _lliurat_permes(con, u, lid)
    inf = json.loads(f["dades_json"])
    return _pdf(informe_pdf.pdf(con, inf, f["botiga_id"], f["generat"]), informe_pdf.nom_fitxer(inf, f["botiga_id"]))


@router.post("/informes/lliurats/{lid}/envia")
def envia_lliurat(lid: int, cos: Destinataris, request: Request, con: sqlite3.Connection = Depends(bd),
                  u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    _lliurat_permes(con, u, lid)
    _envia(lambda: ip.envia_lliurat(con, request.app.state.cfg, lid, cos.destinataris))
    return {"ok": True}


@router.get("/informes/lliurats/{lid}")
def lliurat_json(lid: int, con: sqlite3.Connection = Depends(bd), u: dict = Depends(usuari)) -> dict:
    """L'informe tal com es va generar (mateixa forma que `GET /informes/{tipus}`)."""
    return json.loads(_lliurat_permes(con, u, lid)["dades_json"])


# ---------------------------------------------------------------- Al moment (amb el filtre comú)


def _informe(con: sqlite3.Connection, f: analitica.Filtre, tipus: str) -> dict:
    return analitica.informe(con, f, _tipus(tipus))


@router.get("/informes/{tipus}.pdf")
def informe_pdf_ara(tipus: str, f: analitica.Filtre = Depends(filtre), con: sqlite3.Connection = Depends(bd)) -> Response:
    inf = _informe(con, f, tipus)
    return _pdf(informe_pdf.pdf(con, inf, f.botiga_id), informe_pdf.nom_fitxer(inf, f.botiga_id))


@router.post("/informes/{tipus}/envia")
def envia_ara(tipus: str, cos: Destinataris, request: Request, f: analitica.Filtre = Depends(filtre),
              con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    _tipus(tipus)
    cfg = request.app.state.cfg
    if not correu.configurat(cfg):   # abans de calcular res
        raise HTTPException(400, "El correu no està configurat")
    inf = _informe(con, f, tipus)
    _envia(lambda: ip.envia_informe(con, cfg, inf, f.botiga_id, cos.destinataris))
    return {"ok": True}


@router.get("/informes/{tipus}")
def informe(tipus: str, f: analitica.Filtre = Depends(filtre), con: sqlite3.Connection = Depends(bd)) -> dict:
    """Informe calculat al moment (forma a docs/API.md, amb `xifres` i `grafics` des de la v0.3)."""
    return _informe(con, f, tipus)

