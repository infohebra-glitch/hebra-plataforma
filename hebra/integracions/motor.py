"""Integracions desades (taula `integracio`), registre de sincronitzacions i bucle de fons.

  * Cada integració activa es sincronitza cada `interval_min` minuts (per defecte 60, mínim 15),
    comptats des de l'inici de l'intent anterior (encara que fallés: no s'insisteix més sovint).
  * Vendes: des de la darrera sincronització bona menys 2 dies (per agafar devolucions); la
    primera vegada, els darrers 30 dies. Després, `vendes.atribueix` de les botigues tocades.
  * Cada execució queda a `sync_registre` (se'n guarden les 200 darreres per integració).
  * Les botigues configurades a l'antiga (paràmetres shopify_* i HEBRA_SHOPIFY_TOKEN_<BOTIGA>)
    es continuen sincronitzant cada hora si no tenen una integració Shopify activa (l'hora es
    compta des de l'intent anterior, paràmetre `shopify_darrer_intent`, encara que fallés).
  * Abast per defecte de Shopify i Square: vendes i estoc. El catàleg s'ha de demanar; i quan
    es demana, només crea els GTIN nous i actualitza el preu dels que ja hi són (vegeu desa.cataleg).
  * `prova` amb `id` només fa servir el secret desat si la configuració nova apunta al mateix
    lloc (domini de Shopify, entorn de Square, servidors de les URL del CSV); si no, cal tornar a
    escriure'l. El mateix val per a `actualitza`: el secret no se'n va mai a un destí nou.
"""

import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from .. import db, vendes
from . import PROVEIDORS, connector, shopify, xifratge
from .base import ABAST, ErrorIntegracio

log = logging.getLogger("hebra.integracions")

INTERVAL_DEFECTE = 60
INTERVAL_MINIM = 15
INTERVAL_MAXIM = 7 * 24 * 60
DIES_MARGE = 2
DIES_INICIALS = 30
REGISTRES_GUARDATS = 200
RESUM = ("cataleg", "linies_venda", "devolucions", "estoc")
ABAST_DEFECTE = ("vendes", "estoc")  # Shopify i Square: el catàleg, només si es demana
CLAUS_SECRETES = {"token", "secret", "testimoni", "access_token", "authorization", "contrasenya", "password", "api_key"}

_pany = threading.Lock()
_en_curs: set[int] = set()


class NoTrobada(ErrorIntegracio):
    pass


class EnCurs(ErrorIntegracio):
    pass


def _ara() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _dt(text: str | None) -> datetime | None:
    if not text:
        return None
    d = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- lectura


def a_json(f: sqlite3.Row) -> dict:
    """Integracio (ESPECIFICACIO-v3 F.3). Mai el secret: només si n'hi ha."""
    return {"id": f["id"], "botiga_id": f["botiga_id"], "proveidor": f["proveidor"],
            "config": json.loads(f["config_json"] or "{}"), "te_secret": bool(f["secret_xifrat"]),
            "actiu": bool(f["actiu"]), "abast": json.loads(f["abast"] or "[]"), "interval_min": f["interval_min"],
            "darrera_sync": f["darrera_sync"], "estat": f["estat"], "missatge": f["missatge"]}


def obte(con: sqlite3.Connection, iid: int) -> sqlite3.Row:
    f = con.execute("SELECT * FROM integracio WHERE id = ?", (iid,)).fetchone()
    if f is None:
        raise NoTrobada("Integració no trobada")
    return f


def llista(con: sqlite3.Connection) -> list[dict]:
    return [a_json(f) for f in con.execute("SELECT * FROM integracio ORDER BY id")]


def registre(con: sqlite3.Connection, iid: int, n: int = 20) -> list[dict]:
    obte(con, iid)
    return [{"inici": f["inici"], "fi": f["fi"], "estat": f["estat"],
             "resum": json.loads(f["resum_json"]) if f["resum_json"] else None, "error": f["error"]}
            for f in con.execute("""SELECT * FROM sync_registre WHERE integracio_id = ?
                                    ORDER BY inici DESC, id DESC LIMIT ?""", (iid, n))]


# ---------------------------------------------------------------- validació i escriptura


def _comprova_botiga(con: sqlite3.Connection, botiga_id: str | None) -> None:
    if botiga_id and not con.execute("SELECT 1 FROM botiga WHERE id = ?", (botiga_id,)).fetchone():
        raise ErrorIntegracio(f"Botiga desconeguda: {botiga_id}")


def _abast(proveidor: str, abast, config: dict) -> list[str]:
    if abast is None:
        if proveidor == "csv_url":
            from .csv_url import TIPUS
            return [t for t in ABAST if config.get(TIPUS[t])]
        return list(ABAST_DEFECTE)
    if not isinstance(abast, list) or not abast or not set(abast) <= set(ABAST):
        raise ErrorIntegracio("«abast» ha de ser una llista amb «cataleg», «vendes» i/o «estoc»")
    return [a for a in ABAST if a in abast]


def _interval(valor) -> int:
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise ErrorIntegracio("«interval_min» ha de ser un nombre de minuts")
    if n < INTERVAL_MINIM:
        raise ErrorIntegracio(f"L'interval mínim és de {INTERVAL_MINIM} minuts")
    if n > INTERVAL_MAXIM:
        raise ErrorIntegracio("L'interval màxim és d'una setmana")
    return n


def _config(con: sqlite3.Connection, proveidor: str, config, botiga_id: str | None, abast: list[str]) -> dict:
    if proveidor not in PROVEIDORS:
        raise ErrorIntegracio(f"Proveïdor desconegut: {proveidor!r} (shopify, square o csv_url)")
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise ErrorIntegracio("«config» ha de ser un objecte")
    if CLAUS_SECRETES & {k.lower() for k in config}:
        raise ErrorIntegracio("El testimoni d'accés va a «secret», no a «config» (la configuració no és secreta)")
    c = PROVEIDORS[proveidor].valida(config, botiga_id, abast)
    for b in (c.get("ubicacions") or {}).values():
        _comprova_botiga(con, b)
    return c


def crea(con: sqlite3.Connection, clau: str, dades: dict) -> dict:
    proveidor = dades.get("proveidor")
    botiga_id = dades.get("botiga_id") or None
    _comprova_botiga(con, botiga_id)
    config = dades.get("config") or {}
    if proveidor not in PROVEIDORS:
        raise ErrorIntegracio(f"Proveïdor desconegut: {proveidor!r} (shopify, square o csv_url)")
    abast = _abast(proveidor, dades.get("abast"), config)
    config = _config(con, proveidor, config, botiga_id, abast)
    secret = (dades.get("secret") or "").strip()
    if proveidor in ("shopify", "square") and not secret:
        raise ErrorIntegracio("Cal el testimoni d'accés")
    interval = _interval(dades.get("interval_min", INTERVAL_DEFECTE) or INTERVAL_DEFECTE)
    cur = con.execute(
        """INSERT INTO integracio (botiga_id, proveidor, config_json, secret_xifrat, actiu, abast, interval_min,
                                   estat, creada) VALUES (?, ?, ?, ?, ?, ?, ?, 'mai', ?)""",
        (botiga_id, proveidor, json.dumps(config, ensure_ascii=False), xifratge.xifra(clau, secret) if secret else None,
         0 if dades.get("actiu") is False else 1, json.dumps(abast), interval, _ara().isoformat()))
    con.commit()
    return a_json(obte(con, cur.lastrowid))


def actualitza(con: sqlite3.Connection, clau: str, iid: int, canvis: dict) -> dict:
    """Canvia config / secret / actiu / abast / interval_min / botiga_id. Secret "" l'esborra."""
    f = obte(con, iid)
    botiga_id = canvis["botiga_id"] or None if "botiga_id" in canvis else f["botiga_id"]
    _comprova_botiga(con, botiga_id)
    config = canvis["config"] if canvis.get("config") is not None else json.loads(f["config_json"] or "{}")
    abast = _abast(f["proveidor"], canvis["abast"], config) if canvis.get("abast") is not None \
        else json.loads(f["abast"] or "[]")
    config = _config(con, f["proveidor"], config, botiga_id, abast)
    secret_xifrat = f["secret_xifrat"]
    secret_nou = "secret" in canvis and canvis["secret"] is not None
    if secret_nou:
        s = canvis["secret"].strip()
        if not s and f["proveidor"] in ("shopify", "square"):
            raise ErrorIntegracio("Cal el testimoni d'accés")
        secret_xifrat = xifratge.xifra(clau, s) if s else None
    elif secret_xifrat and not _mateix_desti(f["proveidor"], config, json.loads(f["config_json"] or "{}")):
        raise ErrorIntegracio(SECRET_DESTI_NOU.format(_nom_desti(f["proveidor"])))
    interval = _interval(canvis["interval_min"]) if canvis.get("interval_min") is not None else f["interval_min"]
    actiu = (1 if canvis["actiu"] else 0) if canvis.get("actiu") is not None else f["actiu"]
    con.execute("""UPDATE integracio SET botiga_id = ?, config_json = ?, secret_xifrat = ?, actiu = ?, abast = ?,
                   interval_min = ? WHERE id = ?""",
                (botiga_id, json.dumps(config, ensure_ascii=False), secret_xifrat, actiu, json.dumps(abast),
                 interval, iid))
    con.commit()
    return a_json(obte(con, iid))


def esborra(con: sqlite3.Connection, iid: int) -> None:
    obte(con, iid)
    con.execute("DELETE FROM sync_registre WHERE integracio_id = ?", (iid,))
    con.execute("DELETE FROM integracio WHERE id = ?", (iid,))
    con.commit()


def desti(proveidor: str, config: dict) -> set[str]:
    """On s'envia el secret amb aquesta configuració: domini de Shopify, entorn de Square o
    servidors (esquema + host + port) de les URL del CSV."""
    config = config or {}
    if proveidor == "shopify":
        return {str(config.get("domini") or "").strip().lower().rstrip("/")}
    if proveidor == "square":
        return {str(config.get("entorn") or "produccio")}
    if proveidor == "csv_url":
        from .csv_url import TIPUS
        out = set()
        for clau_url in TIPUS.values():
            if config.get(clau_url):
                u = urlsplit(str(config[clau_url]).strip())
                out.add(f"{u.scheme.lower()}://{(u.netloc or '').lower()}")
        return out
    return set()


def _mateix_desti(proveidor: str, nova: dict, desada: dict) -> bool:
    return desti(proveidor, nova) <= desti(proveidor, desada)


SECRET_DESTI_NOU = ("Has canviat on es connecta ({}): per seguretat, torna a escriure el testimoni "
                    "d'accés (el desat no s'envia a un lloc nou)")


def _nom_desti(proveidor: str) -> str:
    return {"shopify": "el domini de Shopify", "square": "l'entorn de Square"}.get(proveidor, "les adreces dels fitxers")


def _secret(clau: str, f: sqlite3.Row) -> str | None:
    return xifratge.desxifra(clau, f["secret_xifrat"]) if f["secret_xifrat"] else None


def prova(con: sqlite3.Connection, clau: str, proveidor: str | None, config: dict | None, secret: str | None,
          iid: int | None = None, botiga_id: str | None = None) -> dict:
    """Prova la connexió sense desar res. Amb `iid`, el que no s'enviï es pren de la integració desada."""
    reutilitza = False
    if iid is not None:
        f = obte(con, iid)
        proveidor = f["proveidor"]
        desada = json.loads(f["config_json"] or "{}")
        config = config or desada
        botiga_id = botiga_id or f["botiga_id"]
        reutilitza = not secret and bool(f["secret_xifrat"])
    config = _config(con, proveidor or "", config or {}, botiga_id, [])
    if reutilitza:
        # El secret desat només va al mateix lloc on ja anava (si no, es podria fer arribar a qualsevol servidor).
        if not _mateix_desti(proveidor, config, desada):
            raise ErrorIntegracio(SECRET_DESTI_NOU.format(_nom_desti(proveidor)))
        try:
            secret = _secret(clau, f)
        except xifratge.SecretIllegible as e:
            raise ErrorIntegracio(str(e))
    if proveidor in ("shopify", "square") and not secret:
        raise ErrorIntegracio("Cal el testimoni d'accés")
    return connector(proveidor, config, secret, botiga_id).prova()


# ---------------------------------------------------------------- sincronització


def finestra(darrera_sync: str | None, ara: datetime) -> datetime:
    """Inici de la finestra de vendes: la darrera sincronització bona menys 2 dies (o 30 dies enrere)."""
    d = _dt(darrera_sync)
    return (d - timedelta(days=DIES_MARGE)) if d else ara - timedelta(days=DIES_INICIALS)


def toca(interval_min: int, darrer_intent: str | None, ara: datetime) -> bool:
    d = _dt(darrer_intent)
    return d is None or ara - d >= timedelta(minutes=max(INTERVAL_MINIM, interval_min or INTERVAL_DEFECTE))


@contextmanager
def _bloqueja(iid: int):
    with _pany:
        if iid in _en_curs:
            raise EnCurs("Aquesta integració ja s'està sincronitzant: espera que acabi")
        _en_curs.add(iid)
    try:
        yield
    finally:
        with _pany:
            _en_curs.discard(iid)


def _missatge(resum: dict, errors: list) -> str:
    text = (f"{resum['cataleg']} variants, {resum['linies_venda']} línies de venda, "
            f"{resum['devolucions']} devolucions, {resum['estoc']} d'estoc")
    return text + (f"; {len(errors)} files amb errors" if errors else "")


def sincronitza(con: sqlite3.Connection, clau: str, iid: int, ara: datetime | None = None) -> dict:
    """Sincronitza una integració ara. Torna el resum; si falla, ErrorIntegracio (i queda al registre)."""
    with _bloqueja(iid):
        f = obte(con, iid)
        ara = ara or _ara()
        inici = ara.isoformat()
        rid = con.execute("INSERT INTO sync_registre (integracio_id, inici, estat) VALUES (?, ?, 'en_curs')",
                          (iid, inici)).lastrowid
        con.commit()
        try:
            conn = connector(f["proveidor"], json.loads(f["config_json"] or "{}"), _secret(clau, f), f["botiga_id"])
            r = conn.aplica(con, json.loads(f["abast"] or "[]"), finestra(f["darrera_sync"], ara), ara)
            for b in r.get("_botigues") or []:
                vendes.atribueix(con, b)
            resum = {k: int(r.get(k) or 0) for k in RESUM}
            errors = r.get("errors") or []
            desat = dict(resum, errors=errors) if errors else resum
            con.execute("UPDATE sync_registre SET fi = ?, estat = 'ok', resum_json = ? WHERE id = ?",
                        (_ara().isoformat(), json.dumps(desat, ensure_ascii=False), rid))
            con.execute("UPDATE integracio SET darrera_sync = ?, estat = 'ok', missatge = ? WHERE id = ?",
                        (inici, _missatge(resum, errors), iid))
            con.commit()
            return desat
        except Exception as e:
            con.rollback()
            if isinstance(e, (ErrorIntegracio, xifratge.SecretIllegible)):
                text = str(e)
            else:
                log.exception("Error inesperat sincronitzant la integració %s", iid)
                text = f"Error inesperat ({type(e).__name__}): avisa l'equip de Hebra"
            con.execute("UPDATE sync_registre SET fi = ?, estat = 'error', error = ? WHERE id = ?",
                        (_ara().isoformat(), text, rid))
            con.execute("UPDATE integracio SET estat = 'error', missatge = ? WHERE id = ?", (text, iid))
            con.commit()
            raise ErrorIntegracio(text) from e
        finally:
            con.execute("""DELETE FROM sync_registre WHERE integracio_id = ? AND id NOT IN (
                             SELECT id FROM sync_registre WHERE integracio_id = ? ORDER BY id DESC LIMIT ?)""",
                        (iid, iid, REGISTRES_GUARDATS))
            con.commit()


def pendents(con: sqlite3.Connection, ara: datetime) -> list[int]:
    """Integracions actives que ja els toca sincronitzar-se."""
    files = con.execute("""SELECT i.id, i.interval_min, (SELECT MAX(inici) FROM sync_registre r
                                                       WHERE r.integracio_id = i.id) AS darrer
                           FROM integracio i WHERE i.actiu = 1 ORDER BY i.id""").fetchall()
    return [f["id"] for f in files if toca(f["interval_min"], f["darrer"], ara)]


def botigues_antigues(con: sqlite3.Connection) -> list[str]:
    """Botigues amb Shopify per variables d'entorn (v0.2) i sense integració Shopify activa."""
    amb_integracio = {f[0] for f in con.execute(
        "SELECT botiga_id FROM integracio WHERE proveidor = 'shopify' AND actiu = 1 AND botiga_id IS NOT NULL")}
    return [b["id"] for b in con.execute("SELECT id FROM botiga ORDER BY id")
            if b["id"] not in amb_integracio and db.parametre(con, b["id"], "shopify_domini")
            and os.environ.get(shopify.nom_variable_token(b["id"]))]


def sincronitza_pendents(con: sqlite3.Connection, clau: str, ara: datetime | None = None) -> dict:
    """Una volta del bucle de fons. Torna {id o botiga: resum o {"error"}} del que s'ha fet."""
    ara = ara or _ara()
    fet: dict = {}
    for iid in pendents(con, ara):
        try:
            fet[iid] = sincronitza(con, clau, iid, ara)
        except ErrorIntegracio as e:
            fet[iid] = {"error": str(e)}
    for b in botigues_antigues(con):
        darrer = max((d for d in (_dt(db.parametre(con, b, "shopify_darrer_intent")),
                                  _dt(db.parametre(con, b, "shopify_darrera_sync"))) if d), default=None)
        if not toca(60, darrer.isoformat() if darrer else None, ara):
            continue
        # Es marca l'intent abans: si falla, no es torna a provar cada minut sinó d'aquí a una hora.
        db.desa_parametre(con, b, "shopify_darrer_intent", ara.isoformat())
        con.commit()
        try:
            fet[f"shopify:{b}"] = shopify.sincronitza(con, b)
        except Exception as e:
            con.rollback()
            if not isinstance(e, ErrorIntegracio):
                log.exception("Error inesperat sincronitzant Shopify (configuració antiga) de %s", b)
            fet[f"shopify:{b}"] = {"error": str(e)}
    return fet
