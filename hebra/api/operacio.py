"""Operació de botiga i de la marca: peticions de talla, peces abandonades, decisions,
experiments (creació amb sorteig) i recomptes d'estoc."""

import random
import sqlite3
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from hebra import alertes, control, fitxa, temps

from .comu import BOTIGA_O_MES, MARCA_O_MES, bd, botiga_permesa, comprova_botiga, data, rol

router = APIRouter(tags=["operació"])


# ---------------------------------------------------------------- Peticions de talla


class CanviPeticio(BaseModel):
    estat: Literal["en_cami", "lliurada", "no_disponible"]


@router.get("/peticions")
def peticions(estat: str | None = None, botiga: str | None = None, con: sqlite3.Connection = Depends(bd),
              u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    if estat and estat not in ("pendent", "en_cami", "lliurada", "no_disponible"):
        raise HTTPException(400, f"Estat desconegut: {estat}")
    b = botiga_permesa(con, u, botiga)
    files = con.execute(
        alertes.SQL_PETICIONS + """ WHERE (? IS NULL OR pt.botiga_id = ?) AND (? IS NULL OR pt.estat = ?)
        ORDER BY pt.estat IN ('pendent', 'en_cami') DESC, pt.hora_peticio DESC LIMIT 200""",
        (b, b, estat, estat)).fetchall()
    ara = temps.ara()
    return {"peticions": [alertes.peticio_json(f, ara) for f in files]}


@router.patch("/peticions/{pid}")
def canvia_peticio(pid: int, cos: CanviPeticio, con: sqlite3.Connection = Depends(bd),
                   u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    p = alertes.peticio(con, pid)
    if p is None:
        raise HTTPException(404, "Petició no trobada")
    comprova_botiga(u, p["botiga_id"])
    if not fitxa.resol_peticio(con, pid, cos.estat):
        raise HTTPException(400, f"No es pot passar de «{p['estat']}» a «{cos.estat}»")
    return alertes.peticio(con, pid)


# ---------------------------------------------------------------- Peces abandonades


class CanviAbandonada(BaseModel):
    resolta: bool


@router.get("/abandonades")
def abandonades(obertes: int = 0, botiga: str | None = None, con: sqlite3.Connection = Depends(bd),
                u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    b = botiga_permesa(con, u, botiga)
    files = con.execute(
        alertes.SQL_ABANDONADES + """ WHERE (? IS NULL OR c.botiga_id = ?) AND (? = 0 OR a.resolta IS NULL)
        ORDER BY a.detectada DESC LIMIT 200""", (b, b, obertes)).fetchall()
    return {"abandonades": [alertes.abandonada_json(f) for f in files]}


@router.patch("/abandonades/{aid}")
def canvia_abandonada(aid: int, cos: CanviAbandonada, con: sqlite3.Connection = Depends(bd),
                      u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    fila = con.execute(alertes.SQL_ABANDONADES + " WHERE a.id = ?", (aid,)).fetchone()
    if fila is None:
        raise HTTPException(404, "Peça abandonada no trobada")
    comprova_botiga(u, fila["botiga_id"])
    con.execute("UPDATE peca_abandonada SET resolta = ? WHERE id = ?", (temps.ara() if cos.resolta else None, aid))
    con.commit()
    res = alertes.abandonada_json(con.execute(alertes.SQL_ABANDONADES + " WHERE a.id = ?", (aid,)).fetchone())
    alertes.bus.publica("abandonada", dict(res, accio="canvi"), res["botiga_id"])
    return res


# ---------------------------------------------------------------- Decisions


ESTATS_DECISIO = ("proposada", "acceptada", "feta", "descartada")
CAMPS_DECISIO = ("botiga_id", "titol", "descripcio", "insight", "model", "responsable", "data_limit", "estat",
                 "experiment_id", "resultat")


class NovaDecisio(BaseModel):
    titol: str = Field(min_length=1, max_length=200)
    botiga_id: str | None = None
    descripcio: str = ""
    insight: str | None = None
    model: str | None = None
    responsable: str | None = None
    data_limit: str | None = None
    estat: Literal["proposada", "acceptada", "feta", "descartada"] = "proposada"
    experiment_id: str | None = None
    resultat: str | None = None


class CanviDecisio(BaseModel):
    titol: str | None = Field(default=None, min_length=1, max_length=200)
    botiga_id: str | None = None
    descripcio: str | None = None
    insight: str | None = None
    model: str | None = None
    responsable: str | None = None
    data_limit: str | None = None
    estat: Literal["proposada", "acceptada", "feta", "descartada"] | None = None
    experiment_id: str | None = None
    resultat: str | None = None


def _decisio(con: sqlite3.Connection, did: int) -> dict:
    fila = con.execute("SELECT * FROM decisio WHERE id = ?", (did,)).fetchone()
    if fila is None:
        raise HTTPException(404, "Decisió no trobada")
    return {k: fila[k] for k in ("id", "botiga_id", "creada", *CAMPS_DECISIO[1:])}


def _valida_decisio(con: sqlite3.Connection, valors: dict) -> None:
    if valors.get("data_limit"):
        data(valors["data_limit"], "data_limit")
    if valors.get("botiga_id") and not con.execute("SELECT 1 FROM botiga WHERE id = ?", (valors["botiga_id"],)).fetchone():
        raise HTTPException(400, f"Botiga desconeguda: {valors['botiga_id']}")
    if valors.get("experiment_id") and not con.execute(
            "SELECT 1 FROM experiment WHERE id = ?", (valors["experiment_id"],)).fetchone():
        raise HTTPException(400, f"Experiment desconegut: {valors['experiment_id']}")


@router.get("/decisions")
def decisions(botiga: str | None = None, estat: str | None = None, con: sqlite3.Connection = Depends(bd),
              u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    b = botiga_permesa(con, u, botiga)
    files = con.execute("""SELECT id FROM decisio WHERE (? IS NULL OR botiga_id = ? OR botiga_id IS NULL)
                           AND (? IS NULL OR estat = ?) ORDER BY creada DESC, id DESC""",
                        (b, b, estat, estat)).fetchall()
    return {"decisions": [_decisio(con, f["id"]) for f in files]}


@router.post("/decisions")
def nova_decisio(cos: NovaDecisio, con: sqlite3.Connection = Depends(bd), _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    valors = cos.model_dump()
    _valida_decisio(con, valors)
    did = con.execute(
        f"INSERT INTO decisio (creada, {', '.join(CAMPS_DECISIO)}) VALUES (?{', ?' * len(CAMPS_DECISIO)})",
        (temps.ara(), *[valors[k] for k in CAMPS_DECISIO])).lastrowid
    con.commit()
    return _decisio(con, did)


@router.patch("/decisions/{did}")
def canvia_decisio(did: int, cos: CanviDecisio, con: sqlite3.Connection = Depends(bd),
                   _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    _decisio(con, did)
    valors = cos.model_dump(exclude_unset=True)
    if "titol" in valors and valors["titol"] is None:
        raise HTTPException(400, "El títol no pot ser buit")
    if "estat" in valors and valors["estat"] is None:
        raise HTTPException(400, "Estat no vàlid")
    _valida_decisio(con, valors)
    if valors:
        con.execute(f"UPDATE decisio SET {', '.join(f'{k} = ?' for k in valors)} WHERE id = ?",
                    (*valors.values(), did))
        con.commit()
    return _decisio(con, did)


# ---------------------------------------------------------------- Experiments


class NouExperiment(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    botiga_id: str
    variable: Literal["origen", "preu", "exposicio", "peticio_talla", "combina", "altre"]
    hipotesi: str = Field(min_length=1)
    unitat: Literal["dia", "model"] = "dia"
    inici: str
    setmanes: int = Field(default=6, ge=1, le=26)
    proves_minimes: int = Field(default=30, ge=1)


@router.post("/experiments")
def nou_experiment(cos: NouExperiment, con: sqlite3.Connection = Depends(bd),
                   _u: dict = Depends(rol(*MARCA_O_MES))) -> dict:
    """Crea l'experiment i en fa el sorteig.

    Unitat 'dia': `control.sorteja` (equilibrat per dia de la setmana) a `assignacio`
    amb experiment = id. Si la variable és 'origen', la mateixa assignació es desa també
    amb experiment = 'origen', que és el que consulta la fitxa NFC per amagar l'origen.
    Unitat 'model': la meitat dels models del catàleg (barrejats amb llavor fixa) són 'amb'.
    """
    inici = data(cos.inici, "inici")
    if not con.execute("SELECT 1 FROM botiga WHERE id = ?", (cos.botiga_id,)).fetchone():
        raise HTTPException(400, f"Botiga desconeguda: {cos.botiga_id}")
    if con.execute("SELECT 1 FROM experiment WHERE id = ?", (cos.id,)).fetchone():
        raise HTTPException(400, f"Ja hi ha un experiment amb l'id {cos.id}")
    fi = inici + timedelta(days=cos.setmanes * 7 - 1)
    estat = "previst" if inici > date.fromisoformat(temps.ara()[:10]) else "actiu"
    con.execute("""INSERT INTO experiment (id, botiga_id, variable, hipotesi, unitat, inici, fi, proves_minimes, estat)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (cos.id, cos.botiga_id, cos.variable, cos.hipotesi, cos.unitat, inici.isoformat(), fi.isoformat(),
                 cos.proves_minimes, estat))
    if cos.unitat == "dia":
        a = control.sorteja(cos.botiga_id, cos.id, inici, cos.setmanes)
        control.desa_assignacio(con, cos.botiga_id, cos.id, a)
        if cos.variable == "origen":
            control.desa_assignacio(con, cos.botiga_id, "origen", a)
        grups = list(a.values())
    else:
        models = [f["model"] for f in con.execute("SELECT DISTINCT model FROM catalog_sku ORDER BY model")]
        random.Random(f"2026:{cos.botiga_id}:{cos.id}").shuffle(models)
        grups = []
        for i, m in enumerate(models):
            g = "amb" if i % 2 == 0 else "sense"
            con.execute("INSERT INTO assignacio_model (experiment, model, grup) VALUES (?, ?, ?)", (cos.id, m, g))
            grups.append(g)
    con.commit()
    fila = con.execute("SELECT * FROM experiment WHERE id = ?", (cos.id,)).fetchone()
    return dict(fila) | {"assignacio": {"amb": grups.count("amb"), "sense": grups.count("sense")}}


# ---------------------------------------------------------------- Recomptes d'estoc (insight 23)


class Recompte(BaseModel):
    botiga_id: str
    data: str
    gtin: str = Field(pattern=r"^\d{1,14}$")
    manual: int = Field(ge=0)
    rfid: int = Field(ge=0)


@router.post("/recomptes")
def recompte(cos: Recompte, con: sqlite3.Connection = Depends(bd),
             u: dict = Depends(rol(*BOTIGA_O_MES))) -> dict:
    comprova_botiga(u, cos.botiga_id)
    data(cos.data, "data")
    if not con.execute("SELECT 1 FROM botiga WHERE id = ?", (cos.botiga_id,)).fetchone():
        raise HTTPException(400, f"Botiga desconeguda: {cos.botiga_id}")
    rid = con.execute("INSERT INTO recompte_estoc (botiga_id, data, gtin, manual, rfid) VALUES (?, ?, ?, ?, ?)",
                      (cos.botiga_id, cos.data, cos.gtin.zfill(14), cos.manual, cos.rfid)).lastrowid
    con.commit()
    return dict(con.execute("SELECT * FROM recompte_estoc WHERE id = ?", (rid,)).fetchone())
