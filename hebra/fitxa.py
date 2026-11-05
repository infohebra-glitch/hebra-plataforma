"""Lògica de la fitxa NFC (el que veu el client quan toca la peça amb el mòbil).

Privacitat (Proposta MVP, secció de dades):
  * sense galetes ni analítica de tercers;
  * `sessio_nfc` és un id aleatori que es genera en obrir la pàgina i viatja en
    un camp ocult dels formularis; no s'emmagatzema al mòbil;
  * cap esdeveniment de la fitxa s'uneix amb una compra o amb una persona.
"""

import json
import secrets
import sqlite3

from . import cataleg, control, temps

IDIOMES = ("ca", "es", "fr", "en")
# Si el contingut d'origen no té l'idioma, provem aquests en ordre.
RESERVA = {"ca": ["ca", "es"], "es": ["es", "ca"], "fr": ["fr", "es", "ca"], "en": ["en", "es", "ca"]}

TIPUS = {"obre_fitxa", "veu_origen", "demana_talla", "motiu_no_compra"}
MOTIUS_VALIDS = {"talla", "tall", "preu", "color", "qualitat", "altre"}


def nova_sessio() -> str:
    return secrets.token_urlsafe(12)


def tr(valor, idioma: str):
    """Tria la traducció d'un camp multiidioma ({"ca": ..., "es": ...}) o el retorna tal qual."""
    if isinstance(valor, dict) and any(k in valor for k in IDIOMES):
        for i in RESERVA.get(idioma, ["ca"]):
            if valor.get(i):
                return valor[i]
        return next(iter(valor.values()))
    return valor


def peca_per_token(con: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    return con.execute(
        """SELECT e.epc, e.nfc_token, k.* FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
           WHERE e.nfc_token = ?""", (token,)).fetchone()


def dades_fitxa(con: sqlite3.Connection, fila: sqlite3.Row, botiga_id: str | None, idioma: str) -> dict:
    origen = json.loads(fila["origen_json"] or "{}")
    variants = cataleg.variants_del_model(con, fila["model"], fila["color"])
    estoc = origen.get("estoc", {})
    avui = temps.ara()[:10]
    return {
        "gtin": fila["gtin"],
        "token": fila["nfc_token"],
        "nom": tr(origen.get("nom", fila["model"]), idioma),
        "color": tr(origen.get("color", fila["color"]), idioma),
        "talla": fila["talla"],
        "preu": fila["preu_eur"],
        "descripcio": tr(origen.get("descripcio", ""), idioma),
        "ajust": tr(origen.get("ajust", ""), idioma),
        "teixit": tr(origen.get("teixit_detall", ""), idioma),
        "composicio": [{"material": tr(c["material"], idioma), "pct": c["pct"], "pais": c.get("pais")}
                       for c in origen.get("composicio", [])],
        "cura": [tr(c, idioma) for c in origen.get("cura", [])],
        "etapes": [{"etapa": e["etapa"], "pais": e.get("pais"), "regio": tr(e.get("regio", ""), idioma),
                    "actor": tr(e.get("actor", ""), idioma), "data": e.get("data")}
                   for e in origen.get("etapes", [])],
        "certificats": [{"nom": c["nom"], "abast": tr(c.get("abast", ""), idioma)} for c in origen.get("certificats", [])],
        "talles": [{"gtin": v["gtin"], "talla": v["talla"], "estoc": estoc.get(v["talla"]),
                    "actual": v["gtin"] == fila["gtin"]} for v in variants],
        "faq": [{"q": tr(f["q"], idioma), "a": tr(f["a"], idioma)}
                for f in origen.get("faq", []) + origen.get("faq_general", [])],
        "mostra_origen": control.mostra_origen(con, botiga_id, avui),
    }


def registra(con: sqlite3.Connection, sessio_nfc: str, botiga_id: str | None, gtin: str,
             tipus: str, idioma: str, valor: str | None = None, ts: str | None = None) -> None:
    if tipus not in TIPUS:
        raise ValueError(f"tipus d'esdeveniment desconegut: {tipus}")
    if tipus == "motiu_no_compra" and valor not in MOTIUS_VALIDS:
        raise ValueError(f"motiu desconegut: {valor}")
    ts = ts or temps.ara()
    grup = control.grup_del_dia(con, botiga_id, "origen", ts[:10]) if botiga_id else None
    con.execute(
        """INSERT INTO esdeveniment_nfc (sessio_nfc, ts, botiga_id, gtin, tipus, valor, idioma, grup)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (sessio_nfc, ts, botiga_id, gtin, tipus, valor, idioma if idioma in IDIOMES else "ca", grup))
    con.commit()


def demana_talla(con: sqlite3.Connection, sessio_nfc: str, botiga_id: str, gtin_origen: str,
                 gtin_demanat: str, idioma: str, cabina: str | None = None, ts: str | None = None) -> int:
    """Crea una petició de talla per al dependent. Retorna l'id de la petició."""
    demanat = cataleg.sku(con, gtin_demanat)
    if demanat is None:
        raise ValueError("talla desconeguda")
    origen = json.loads(demanat["origen_json"] or "{}")
    estoc = origen.get("estoc", {}).get(demanat["talla"])
    ts = ts or temps.ara()
    registra(con, sessio_nfc, botiga_id, gtin_origen, "demana_talla", idioma, demanat["talla"], ts)
    cur = con.execute(
        """INSERT INTO peticio_talla (sessio_nfc, botiga_id, gtin_origen, gtin_demanat, talla_demanada,
                                      cabina, hora_peticio, disponible)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (sessio_nfc, botiga_id, gtin_origen, gtin_demanat, demanat["talla"], cabina, ts,
         None if estoc is None else int(estoc > 0)))
    con.commit()
    return cur.lastrowid


def resol_peticio(con: sqlite3.Connection, peticio_id: int, estat: str, ts: str | None = None) -> None:
    if estat not in ("lliurada", "no_disponible"):
        raise ValueError(estat)
    con.execute("UPDATE peticio_talla SET estat = ?, hora_resolta = ? WHERE id = ? AND estat = 'pendent'",
                (estat, ts or temps.ara(), peticio_id))
    con.commit()
