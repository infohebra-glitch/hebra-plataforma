"""Lògica de la fitxa NFC (el que veu el client quan toca la peça amb el mòbil).

Privacitat (Proposta MVP, secció de dades):
  * sense galetes ni analítica de tercers;
  * `sessio_nfc` és un id aleatori que es genera en obrir la pàgina i viatja en
    un camp ocult dels formularis; no s'emmagatzema al mòbil;
  * cap esdeveniment de la fitxa s'uneix amb una compra o amb una persona.

La pàgina funciona sense JavaScript. Només hi ha un script en línia molt petit
(`SCRIPT_SECCIONS`, autoritzat a la CSP pel seu hash) que, quan el client obre
una secció plegable (talles, cura, preguntes), ho envia amb `navigator.sendBeacon`
a la mateixa plataforma (`POST /p/{token}/seccio`). Sense galetes ni emmagatzematge.

v0.3: la marca configura la fitxa (hebra/fitxa_config.py): ordre i visibilitat de les
seccions, botons, idiomes, textos, color i logo, motius i com es mostra l'estoc; i en
pot reescriure el contingut per model i idioma (taula `contingut_model`).
"""

import base64
import hashlib
import json
import re
import secrets
import sqlite3
from datetime import datetime, timedelta

from . import alertes, cataleg, control, estoc, fitxa_config, temps

IDIOMES = ("ca", "es", "fr", "en")
# Si el contingut d'origen no té l'idioma, provem aquests en ordre.
RESERVA = {"ca": ["ca", "es"], "es": ["es", "ca"], "fr": ["fr", "es", "ca"], "en": ["en", "es", "ca"]}

TIPUS = {"obre_fitxa", "veu_origen", "demana_talla", "demana_assistencia", "motiu_no_compra", "veu_seccio"}
MOTIUS_VALIDS = set(fitxa_config.MOTIUS)
SECCIONS = {"talles", "cura", "preguntes"}
TITOL_COMBINA = {"ca": "Combina amb", "es": "Combina con", "fr": "À associer avec", "en": "Goes well with"}

# Estats de la petició de talla i transicions permeses (pendent -> en_cami -> lliurada | no_disponible).
TRANSICIONS = {"pendent": {"en_cami", "lliurada", "no_disponible"}, "en_cami": {"lliurada", "no_disponible"}}
ESTATS_FINALS = {"lliurada", "no_disponible"}

# Script de la fitxa: el text ha de ser exactament aquest perquè el hash de la CSP quadri.
SCRIPT_SECCIONS = (
    "(function(){var f=document.getElementById('seccions');if(!f||!navigator.sendBeacon)return;"
    "var vist={};document.querySelectorAll('details[data-seccio]').forEach(function(d){"
    "var salta=d.open;d.addEventListener('toggle',function(){if(salta){salta=false;return;}"
    "var s=d.getAttribute('data-seccio');if(!d.open||vist[s])return;vist[s]=1;"
    "var p=new URLSearchParams(new FormData(f));p.set('seccio',s);"
    "navigator.sendBeacon(f.action,p);});});})();")
HASH_SCRIPT = "sha256-" + base64.b64encode(hashlib.sha256(SCRIPT_SECCIONS.encode()).digest()).decode()


_SESSIO = re.compile(r"^[A-Za-z0-9_-]{8,40}$")

# Límits de les peticions que arriben al dependent des de la fitxa (pública): algú amb l'enllaç
# d'una peça no ha de poder omplir de falses alarmes la pantalla de la botiga.
MAX_OBERTES_PER_SESSIO = 3      # peticions pendents o en camí d'una mateixa visita
MAX_PER_BOTIGA = 20             # peticions noves per botiga cada `FINESTRA_BOTIGA_MIN` minuts
FINESTRA_BOTIGA_MIN = 10


class MassaPeticions(Exception):
    """S'ha arribat al límit de peticions (de la visita o de la botiga)."""


def nova_sessio() -> str:
    return secrets.token_urlsafe(12)


def sessio_valida(s: str | None) -> bool:
    """La sessió tècnica és un text curt que genera el servidor; qualsevol altra cosa es rebutja."""
    return bool(s) and _SESSIO.match(s) is not None


def botiga_existent(con: sqlite3.Connection, botiga_id: str | None) -> str | None:
    """L'id de la botiga si existeix; si no (enllaç manipulat o mal gravat), None."""
    if not botiga_id or len(botiga_id) > 40:
        return None
    fila = con.execute("SELECT id FROM botiga WHERE id = ?", (botiga_id,)).fetchone()
    return fila["id"] if fila else None


def neteja_cabina(text: str | None) -> str | None:
    """El que el client escriu al camp «cabina»: sense caràcters de control i 20 caràcters com a molt."""
    net = "".join(c for c in (text or "") if c.isprintable()).strip()[:20]
    return net or None


def _peticio_oberta(con: sqlite3.Connection, sessio_nfc: str, botiga_id: str, gtin_demanat: str,
                    tipus: str) -> int | None:
    fila = con.execute(
        """SELECT id FROM peticio_talla WHERE sessio_nfc = ? AND botiga_id = ? AND gtin_demanat = ? AND tipus = ?
           AND estat IN ('pendent', 'en_cami') ORDER BY id LIMIT 1""",
        (sessio_nfc, botiga_id, gtin_demanat, tipus)).fetchone()
    return fila["id"] if fila else None


def _comprova_limits(con: sqlite3.Connection, sessio_nfc: str, botiga_id: str, ts: str) -> None:
    obertes = con.execute(
        "SELECT COUNT(*) FROM peticio_talla WHERE sessio_nfc = ? AND estat IN ('pendent', 'en_cami')",
        (sessio_nfc,)).fetchone()[0]
    if obertes >= MAX_OBERTES_PER_SESSIO:
        raise MassaPeticions("Ja tens peticions en marxa: de seguida t'atenen")
    des = (datetime.fromisoformat(ts) - timedelta(minutes=FINESTRA_BOTIGA_MIN)).isoformat(timespec="seconds")
    recents = con.execute(
        "SELECT COUNT(*) FROM peticio_talla WHERE botiga_id = ? AND julianday(hora_peticio) >= julianday(?) "
        "AND julianday(hora_peticio) <= julianday(?)",
        (botiga_id, des, ts)).fetchone()[0]
    if recents >= MAX_PER_BOTIGA:
        raise MassaPeticions("Ara mateix hi ha moltes peticions: demana-ho a una persona de la botiga")


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


def tria_idioma(lang: str | None, accept_language: str | None, oferts: list[str]) -> str:
    """Idioma de la pàgina: el demanat (si s'ofereix), el del navegador (si s'ofereix) o el primer de la marca."""
    if lang in oferts:
        return lang
    preferit = (accept_language or "")[:2].lower()
    return preferit if preferit in oferts else oferts[0]


def _contingut(con: sqlite3.Connection, model: str, idioma: str) -> tuple[dict, list[dict]]:
    """(contingut propi en l'idioma exacte, contingut en els idiomes de reserva) d'un model."""
    tot = fitxa_config.contingut(con, model)
    return tot.get(idioma, {}), [tot[i] for i in RESERVA.get(idioma, ["ca"]) if i != idioma and i in tot]


def dades_fitxa(con: sqlite3.Connection, fila: sqlite3.Row, botiga_id: str | None, idioma: str,
                cfg: dict | None = None) -> dict:
    """Dades de la fitxa d'una peça. Cada camp: contingut propi de la marca en l'idioma (`contingut_model`),
    si no, el fitxer d'origen, i si no, el contingut propi en un idioma de reserva.
    `mostra_origen` ja combina la visibilitat de la configuració i el grup de control del dia."""
    cfg = cfg or fitxa_config.efectiva(con, botiga_id)
    origen = json.loads(fila["origen_json"] or "{}")
    propi, reserva = _contingut(con, fila["model"], idioma)

    def camp(clau: str, de_origen):
        if propi.get(clau):
            return propi[clau]
        if de_origen:
            return de_origen
        return next((r[clau] for r in reserva if r.get(clau)), de_origen)
    variants = cataleg.variants_del_model(con, fila["model"], fila["color"])
    estoc_origen = origen.get("estoc", {})
    avui = temps.ara()[:10]

    def unitats(v: sqlite3.Row) -> int | None:
        # Primer l'estoc real de la botiga (CSV o Shopify); si no en tenim, el del fitxer d'origen.
        u = estoc.unitats(con, botiga_id, v["gtin"])
        return estoc_origen.get(v["talla"]) if u is None else u

    return {
        "gtin": fila["gtin"],
        "token": fila["nfc_token"],
        "nom": camp("nom", tr(origen.get("nom"), idioma)) or fila["model"],
        "color": tr(origen.get("color", fila["color"]), idioma),
        "talla": fila["talla"],
        "preu": fila["preu_eur"],
        "descripcio": camp("descripcio", tr(origen.get("descripcio", ""), idioma)),
        "ajust": camp("ajust", tr(origen.get("ajust", ""), idioma)),
        "guia_talles": camp("guia_talles", tr(origen.get("guia_talles", ""), idioma)),
        "teixit": tr(origen.get("teixit_detall", ""), idioma),
        "composicio": [{"material": tr(c["material"], idioma), "pct": c["pct"], "pais": c.get("pais")}
                       for c in origen.get("composicio", [])],
        "cura": camp("cura", [tr(c, idioma) for c in origen.get("cura", [])]),
        "etapes": [{"etapa": e["etapa"], "pais": e.get("pais"), "regio": tr(e.get("regio", ""), idioma),
                    "actor": tr(e.get("actor", ""), idioma), "data": e.get("data")}
                   for e in origen.get("etapes", [])],
        "certificats": [{"nom": c["nom"], "abast": tr(c.get("abast", ""), idioma)} for c in origen.get("certificats", [])],
        "talles": [{"gtin": v["gtin"], "talla": v["talla"], "estoc": unitats(v),
                    "actual": v["gtin"] == fila["gtin"]} for v in variants],
        "faq": camp("faq", [{"q": tr(f["q"], idioma), "a": tr(f["a"], idioma)}
                            for f in origen.get("faq", []) + origen.get("faq_general", [])]),
        "origen_amagat_per_control": not control.mostra_origen(con, botiga_id, avui),
        "mostra_origen": cfg["seccions"]["visibles"].get("origen", True) and control.mostra_origen(con, botiga_id, avui),
        "combina": _combina(con, camp("combina", origen.get("combina") or []), idioma),
        "titol_combina": TITOL_COMBINA.get(idioma, TITOL_COMBINA["ca"]),
    }


def _combina(con: sqlite3.Connection, models: list, idioma: str) -> list[str]:
    """Noms dels models que el fitxer d'origen suggereix combinar (només es mostren, sense enllaç)."""
    noms = []
    for m in models[:6]:
        if not isinstance(m, str):
            continue
        propi, reserva = _contingut(con, m, idioma)
        nom = propi.get("nom") or next((r["nom"] for r in reserva if r.get("nom")), None)
        if not nom:
            fila = con.execute("SELECT origen_json FROM catalog_sku WHERE model = ? AND origen_json IS NOT NULL LIMIT 1",
                               (m,)).fetchone()
            nom = tr(json.loads(fila["origen_json"]).get("nom"), idioma) if fila else None
        noms.append(nom or m)
    return noms


def registra(con: sqlite3.Connection, sessio_nfc: str, botiga_id: str | None, gtin: str,
             tipus: str, idioma: str, valor: str | None = None, ts: str | None = None) -> None:
    if tipus not in TIPUS:
        raise ValueError(f"tipus d'esdeveniment desconegut: {tipus}")
    if tipus == "motiu_no_compra" and valor not in MOTIUS_VALIDS and not fitxa_config.es_propi(valor):
        raise ValueError(f"motiu desconegut: {valor}")
    if tipus == "veu_seccio" and valor not in SECCIONS and not fitxa_config.es_propi(valor):
        raise ValueError(f"secció desconeguda: {valor}")
    ts = ts or temps.ara()
    grup = control.grup_del_dia(con, botiga_id, "origen", ts[:10]) if botiga_id else None
    con.execute(
        """INSERT INTO esdeveniment_nfc (sessio_nfc, ts, botiga_id, gtin, tipus, valor, idioma, grup)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (sessio_nfc, ts, botiga_id, gtin, tipus, valor, idioma if idioma in IDIOMES else "ca", grup))
    con.commit()


def ja_ha_dit_motiu(con: sqlite3.Connection, sessio_nfc: str, gtin: str) -> bool:
    return con.execute("""SELECT 1 FROM esdeveniment_nfc WHERE sessio_nfc = ? AND gtin = ?
                          AND tipus = 'motiu_no_compra' LIMIT 1""", (sessio_nfc, gtin)).fetchone() is not None


def demana_talla(con: sqlite3.Connection, sessio_nfc: str, botiga_id: str, gtin_origen: str,
                 gtin_demanat: str, idioma: str, cabina: str | None = None, ts: str | None = None) -> int:
    """Crea una petició de talla per al dependent. Retorna l'id de la petició.

    La talla demanada ha de ser una altra variant del mateix model i color que la peça que el
    client té a la mà (no es pot demanar qualsevol producte del catàleg des d'una fitxa).
    """
    demanat = cataleg.sku(con, gtin_demanat)
    origen_sku = cataleg.sku(con, gtin_origen)
    if demanat is None or origen_sku is None or (demanat["model"], demanat["color"]) != (
            origen_sku["model"], origen_sku["color"]):
        raise ValueError("talla desconeguda")
    origen = json.loads(demanat["origen_json"] or "{}")
    disponible = alertes.disponible(con, botiga_id, gtin_demanat, origen.get("estoc", {}).get(demanat["talla"]))
    ts = ts or temps.ara()
    repetida = _peticio_oberta(con, sessio_nfc, botiga_id, gtin_demanat, "talla")
    if repetida:  # doble toc al botó: la petició ja hi és
        return repetida
    _comprova_limits(con, sessio_nfc, botiga_id, ts)
    registra(con, sessio_nfc, botiga_id, gtin_origen, "demana_talla", idioma, demanat["talla"], ts)
    cur = con.execute(
        """INSERT INTO peticio_talla (sessio_nfc, botiga_id, gtin_origen, gtin_demanat, talla_demanada,
                                      cabina, hora_peticio, disponible)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (sessio_nfc, botiga_id, gtin_origen, gtin_demanat, demanat["talla"], cabina, ts, disponible))
    con.commit()
    alertes.notifica_peticio(con, cur.lastrowid, nova=True)
    return cur.lastrowid


def demana_assistencia(con: sqlite3.Connection, sessio_nfc: str, botiga_id: str, gtin_origen: str,
                       idioma: str, cabina: str | None = None, ts: str | None = None) -> int:
    """«Vull que m'atenguin» (A.4): una petició de tipus 'assistencia' a la mateixa llista del dependent.

    Té gtin_demanat = gtin_origen (la peça que el client té a la mà) i talla_demanada = ''.
    """
    if cataleg.sku(con, gtin_origen) is None:
        raise ValueError("peça desconeguda")
    ts = ts or temps.ara()
    repetida = _peticio_oberta(con, sessio_nfc, botiga_id, gtin_origen, "assistencia")
    if repetida:
        return repetida
    _comprova_limits(con, sessio_nfc, botiga_id, ts)
    registra(con, sessio_nfc, botiga_id, gtin_origen, "demana_assistencia", idioma, None, ts)
    cur = con.execute(
        """INSERT INTO peticio_talla (sessio_nfc, botiga_id, gtin_origen, gtin_demanat, talla_demanada,
                                      cabina, hora_peticio, disponible, tipus)
           VALUES (?, ?, ?, ?, '', ?, ?, NULL, 'assistencia')""",
        (sessio_nfc, botiga_id, gtin_origen, gtin_origen, cabina, ts))
    con.commit()
    alertes.notifica_peticio(con, cur.lastrowid, nova=True)
    return cur.lastrowid


def context_pagina(con: sqlite3.Connection, peca: sqlite3.Row, botiga_id: str | None, idioma: str,
                   cfg: dict, s: str, ok: str | None, previsualitza: dict | None = None) -> dict:
    """Context de la plantilla `fitxa.html` (la fitxa real i la previsualització del tauler).

    `previsualitza` (només el tauler): {"model", "botiga"}; la pàgina no porta l'script ni
    formularis actius, i els enllaços d'idioma tornen a la previsualització.
    """
    from . import textos
    t = textos.TEXTOS[idioma]
    return {"p": dades_fitxa(con, peca, botiga_id, idioma, cfg), "t": t, "lang": idioma,
            "idiomes": cfg["idiomes"], "b": botiga_id or "", "s": s, "ok": ok, "script": SCRIPT_SECCIONS,
            "cfg": cfg, "seccions": [x for x in cfg["seccions"]["ordre"] if cfg["seccions"]["visibles"].get(x, True)],
            "accions": cfg["accions"], "ap": cfg["aparença"],
            "benvinguda": tr(cfg["textos"].get("benvinguda") or None, idioma) or "",
            "peu": tr(cfg["textos"].get("peu") or None, idioma) or "",
            "motius": motius_pagina(cfg, idioma),
            "propies": {x["id"]: {"titol": fitxa_config.text_idioma(x.get("titol"), idioma),
                                  "text": fitxa_config.text_idioma(x.get("text"), idioma),
                                  "plegable": x.get("plegable", False)}
                        for x in cfg.get("seccions_propies", [])},
            "text_accent": text_sobre(cfg["aparença"].get("color_principal") or "#14457D"),
            "previsualitza": previsualitza}


def text_sobre(color: str) -> str:
    """Color del text sobre el color de la marca: blanc si hi ha prou contrast (WCAG 4,5:1), si no, fosc."""
    try:
        canals = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    except (ValueError, IndexError):
        return "#FFFFFF"
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canals]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return "#FFFFFF" if 1.05 / (lum + 0.05) >= 4.5 else "#0B1522"


def motius_pagina(cfg: dict, idioma: str) -> list[tuple[str, str]]:
    """[(clau, text)] dels motius que veu el client: els estàndard (amb la redacció de la marca, si en té)
    i els propis, en l'ordre de la configuració."""
    from . import textos
    t = textos.TEXTOS[idioma]
    propis = {x["id"]: x for x in cfg.get("motius_propis", [])}
    redactats = cfg.get("textos_motius", {})
    out = []
    for m in cfg["motius"]:
        if m in propis:
            text = fitxa_config.text_idioma(propis[m].get("text"), idioma)
        else:
            text = (redactats.get(m) or {}).get(idioma) or t["motius"].get(m, m)
        if text:
            out.append((m, text))
    return out


def resol_peticio(con: sqlite3.Connection, peticio_id: int, estat: str, ts: str | None = None) -> bool:
    """Canvia l'estat d'una petició: pendent -> en_cami -> lliurada | no_disponible.

    Retorna True si ha canviat; False si la petició no existeix o la transició no és
    permesa (p. ex. ja estava lliurada). `hora_resolta` es posa en arribar a un estat final.
    """
    if estat not in ("en_cami", *ESTATS_FINALS):
        raise ValueError(estat)
    origens = [e for e, destins in TRANSICIONS.items() if estat in destins]
    cur = con.execute(
        f"""UPDATE peticio_talla SET estat = ?, hora_resolta = ? WHERE id = ?
            AND estat IN ({",".join("?" * len(origens))})""",
        (estat, (ts or temps.ara()) if estat in ESTATS_FINALS else None, peticio_id, *origens))
    con.commit()
    if cur.rowcount:
        alertes.notifica_peticio(con, peticio_id, nova=False)
    return bool(cur.rowcount)
