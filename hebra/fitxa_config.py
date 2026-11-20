"""Configuració de la fitxa NFC per la marca (especificació v0.3, A.1-A.2).

Dos nivells de configuració (taula `config_fitxa`):
  * general (`botiga_id = '*'`): es desa sencera, completada amb `DEFECTE`;
  * per botiga: parcial; només els camps que canvien respecte de la general.
La configuració **efectiva** d'una botiga és `DEFECTE` ← general ← botiga
(fusió profunda dels diccionaris; les llistes se substitueixen senceres).

Contingut per model i idioma (taula `contingut_model`): camps opcionals que, si
hi són, passen per davant del fitxer d'origen (`catalog_sku.origen_json`).

Tot es valida aquí (`valida_config`, `valida_contingut`), amb missatges en català
que l'API retorna tal qual com a 400 (`ErrorConfig`).
"""

import base64
import copy
import json
import re
import sqlite3

from . import temps

IDIOMES = ("ca", "es", "fr", "en")
SECCIONS = ("talles", "composicio", "origen", "cura", "combina", "faq")
MOTIUS = ("talla", "tall", "preu", "color", "qualitat", "nomes_mirava", "altre")
MODES_ESTOC = ("no", "disponibilitat", "unitats")
ACCIONS_BOOL = ("demana_talla", "demana_assistencia", "per_que_no")
TEXTOS = ("benvinguda", "peu")
LOGO_MAX_BYTES = 100 * 1024
# Seccions i motius propis de la marca (escrits a mà al tauler). Identificador «p-...».
ID_PROPI = re.compile(r"^p-[a-z0-9-]{1,30}$")
MAX_SECCIONS_PROPIES = 12
MAX_MOTIUS_PROPIS = 10
TEXT_SECCIO_MAX = 4000
TEXT_MAX = 1000
GENERAL = "*"

DEFECTE = {
    "seccions": {"ordre": list(SECCIONS), "visibles": {s: True for s in SECCIONS}},
    "accions": {"demana_talla": True, "demana_assistencia": True, "per_que_no": True,
                "mostra_estoc": "disponibilitat"},
    "idiomes": list(IDIOMES),
    "textos": {"benvinguda": {}, "peu": {}},
    "aparença": {"color_principal": "#14457D", "logo_data_url": None, "nom_marca": "Hebra"},
    "motius": ["talla", "tall", "preu", "color", "qualitat", "altre"],
    # [{"id": "p-...", "titol": {idioma: text}, "text": {idioma: text}, "plegable": bool}]
    "seccions_propies": [],
    # [{"id": "p-...", "text": {idioma: text}}]
    "motius_propis": [],
    # Redacció pròpia dels motius estàndard: {motiu: {idioma: text}}
    "textos_motius": {},
}

_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_LOGO = re.compile(r"^data:image/(png|svg\+xml);base64,([A-Za-z0-9+/=\s]+)$")
_CAMPS_CONTINGUT = ("nom", "descripcio", "ajust", "cura", "guia_talles", "faq", "combina")


class ErrorConfig(ValueError):
    """Configuració o contingut no vàlid (missatge en català per a l'usuari)."""


# ---------------------------------------------------------------- Validació


def _llista_coneguda(valor, coneguts: tuple, nom: str, buida: bool = False) -> list:
    if not isinstance(valor, list) or (not valor and not buida):
        raise ErrorConfig(f"«{nom}» ha de ser una llista{'' if buida else ' no buida'}")
    desconeguts = [v for v in valor if v not in coneguts]
    if desconeguts:
        raise ErrorConfig(f"Valors desconeguts a «{nom}»: {', '.join(map(str, desconeguts))}")
    if len(set(valor)) != len(valor):
        raise ErrorConfig(f"Valors repetits a «{nom}»")
    return list(valor)


def _text(valor, nom: str, maxim: int = TEXT_MAX) -> str:
    if not isinstance(valor, str):
        raise ErrorConfig(f"«{nom}» ha de ser un text")
    if len(valor) > maxim:
        raise ErrorConfig(f"«{nom}» és massa llarg (màxim {maxim} caràcters)")
    return valor


def _logo(valor) -> str | None:
    if valor is None or valor == "":
        return None
    m = _LOGO.match(valor) if isinstance(valor, str) else None
    if not m:
        raise ErrorConfig("El logo ha de ser una imatge PNG o SVG en data URI (base64)")
    try:
        mida = len(base64.b64decode(re.sub(r"\s", "", m.group(2)), validate=True))
    except ValueError:
        raise ErrorConfig("El logo no és un base64 vàlid")
    if mida > LOGO_MAX_BYTES:
        raise ErrorConfig("El logo fa més de 100 KB")
    return valor


def es_propi(clau) -> bool:
    return isinstance(clau, str) and ID_PROPI.match(clau) is not None


def _ids(valor, coneguts: tuple, nom: str, buida: bool = False) -> list:
    """Com `_llista_coneguda`, però també admet identificadors propis («p-...»)."""
    if not isinstance(valor, list) or (not valor and not buida):
        raise ErrorConfig(f"«{nom}» ha de ser una llista{'' if buida else ' no buida'}")
    dolents = [v for v in valor if v not in coneguts and not es_propi(v)]
    if dolents:
        raise ErrorConfig(f"Valors desconeguts a «{nom}»: {', '.join(map(str, dolents))}")
    if len(set(valor)) != len(valor):
        raise ErrorConfig(f"Valors repetits a «{nom}»")
    return list(valor)


def _per_idioma(valor, nom: str, maxim: int) -> dict:
    valor = _diccionari(valor or {}, nom)
    _llista_coneguda(list(valor), IDIOMES, nom, buida=True)
    return {i: _text(x, f"{nom}.{i}", maxim).strip() for i, x in valor.items() if isinstance(x, str) and x.strip()}


def _propis(valor, nom: str, maxim: int, camps: dict) -> list:
    """Llista d'elements propis {"id": "p-...", camp: {idioma: text}, ...}."""
    if not isinstance(valor, list):
        raise ErrorConfig(f"«{nom}» ha de ser una llista")
    if len(valor) > maxim:
        raise ErrorConfig(f"«{nom}»: com a màxim {maxim}")
    out, vistos = [], set()
    for i, x in enumerate(valor):
        x = _diccionari(x, f"{nom}[{i}]")
        if not es_propi(x.get("id")):
            raise ErrorConfig(f"«{nom}[{i}].id» ha de ser del tipus «p-nom» (minúscules, xifres i guions)")
        if x["id"] in vistos:
            raise ErrorConfig(f"Identificador repetit a «{nom}»: {x['id']}")
        vistos.add(x["id"])
        sobrants = set(x) - {"id", *camps}
        if sobrants:
            raise ErrorConfig(f"Camps desconeguts a «{nom}[{i}]»: {', '.join(sorted(sobrants))}")
        net = {"id": x["id"]}
        for camp, (tipus, llarg) in camps.items():
            if tipus == "text":
                net[camp] = _per_idioma(x.get(camp), f"{nom}[{i}].{camp}", llarg)
            elif tipus == "bool":
                if not isinstance(x.get(camp, False), bool):
                    raise ErrorConfig(f"«{nom}[{i}].{camp}» ha de ser true o false")
                net[camp] = x.get(camp, False)
        primer = next(iter(camps))
        if not net[primer]:
            raise ErrorConfig(f"«{nom}[{i}]» necessita el text «{primer}» com a mínim en un idioma")
        out.append(net)
    return out


def _diccionari(valor, nom: str) -> dict:
    if not isinstance(valor, dict):
        raise ErrorConfig(f"«{nom}» ha de ser un objecte")
    return valor


def valida_config(cfg, parcial: bool = False) -> dict:
    """Valida una ConfigFitxa i la retorna neta (només camps coneguts).

    Amb `parcial=True` (configuració d'una botiga) tots els camps són opcionals.
    Una configuració general (`parcial=False`) també pot ser parcial: es completa
    amb `DEFECTE` en desar-la.
    """
    cfg = _diccionari(cfg, "configuració")
    sobrants = set(cfg) - set(DEFECTE)
    if sobrants:
        raise ErrorConfig(f"Camps desconeguts: {', '.join(sorted(sobrants))}")
    net: dict = {}
    if "seccions" in cfg:
        s = _diccionari(cfg["seccions"], "seccions")
        if set(s) - {"ordre", "visibles"}:
            raise ErrorConfig("«seccions» només admet «ordre» i «visibles»")
        net["seccions"] = {}
        if "ordre" in s:
            net["seccions"]["ordre"] = _ids(s["ordre"], SECCIONS, "seccions.ordre")
        if "visibles" in s:
            v = _diccionari(s["visibles"], "seccions.visibles")
            _ids(list(v), SECCIONS, "seccions.visibles", buida=True)
            if not all(isinstance(x, bool) for x in v.values()):
                raise ErrorConfig("«seccions.visibles» ha de tenir valors true/false")
            net["seccions"]["visibles"] = dict(v)
    if "accions" in cfg:
        a = _diccionari(cfg["accions"], "accions")
        _llista_coneguda(list(a), (*ACCIONS_BOOL, "mostra_estoc"), "accions", buida=True)
        for k in ACCIONS_BOOL:
            if k in a and not isinstance(a[k], bool):
                raise ErrorConfig(f"«accions.{k}» ha de ser true o false")
        if "mostra_estoc" in a and a["mostra_estoc"] not in MODES_ESTOC:
            raise ErrorConfig("«accions.mostra_estoc» ha de ser «no», «disponibilitat» o «unitats»")
        net["accions"] = dict(a)
    if "idiomes" in cfg:
        net["idiomes"] = _llista_coneguda(cfg["idiomes"], IDIOMES, "idiomes")
    if "textos" in cfg:
        t = _diccionari(cfg["textos"], "textos")
        _llista_coneguda(list(t), TEXTOS, "textos", buida=True)
        net["textos"] = {}
        for clau, per_idioma in t.items():
            per_idioma = _diccionari(per_idioma or {}, f"textos.{clau}")
            _llista_coneguda(list(per_idioma), IDIOMES, f"textos.{clau}", buida=True)
            net["textos"][clau] = {i: _text(x, f"textos.{clau}.{i}") for i, x in per_idioma.items()}
    if "aparença" in cfg:
        ap = _diccionari(cfg["aparença"], "aparença")
        _llista_coneguda(list(ap), ("color_principal", "logo_data_url", "nom_marca"), "aparença", buida=True)
        net["aparença"] = {}
        if "color_principal" in ap:
            if not isinstance(ap["color_principal"], str) or not _COLOR.match(ap["color_principal"]):
                raise ErrorConfig("El color principal ha de tenir el format #RRGGBB")
            net["aparença"]["color_principal"] = ap["color_principal"].upper()
        if "logo_data_url" in ap:
            net["aparença"]["logo_data_url"] = _logo(ap["logo_data_url"])
        if "nom_marca" in ap:
            net["aparença"]["nom_marca"] = _text(ap["nom_marca"], "aparença.nom_marca", 60).strip() or "Hebra"
    if "motius" in cfg:
        net["motius"] = _ids(cfg["motius"], MOTIUS, "motius", buida=True)
    if "seccions_propies" in cfg:
        net["seccions_propies"] = _propis(cfg["seccions_propies"], "seccions_propies", MAX_SECCIONS_PROPIES,
                                          {"titol": ("text", 80), "text": ("text", TEXT_SECCIO_MAX), "plegable": ("bool", 0)})
    if "motius_propis" in cfg:
        net["motius_propis"] = _propis(cfg["motius_propis"], "motius_propis", MAX_MOTIUS_PROPIS, {"text": ("text", 80)})
    if "textos_motius" in cfg:
        tm = _diccionari(cfg["textos_motius"], "textos_motius")
        _llista_coneguda(list(tm), MOTIUS, "textos_motius", buida=True)
        net["textos_motius"] = {m: _per_idioma(x, f"textos_motius.{m}", 80) for m, x in tm.items()}
    return net


def fusiona(base: dict, canvis: dict | None) -> dict:
    """Fusió profunda: els diccionaris es combinen; la resta de valors (llistes incloses) se substitueixen."""
    out = copy.deepcopy(base)
    for k, v in (canvis or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = fusiona(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def normalitza(cfg: dict) -> dict:
    """Completa l'ordre de seccions amb les que hi falten (al final): totes tenen un lloc.

    Les seccions i els motius propis que ja no existeixen (esborrats) es treuen de l'ordre,
    de la visibilitat i de la llista de motius.
    """
    propies = [x["id"] for x in cfg.get("seccions_propies", [])]
    totes = (*SECCIONS, *propies)
    ordre = [s for s in cfg["seccions"]["ordre"] if s in totes]
    cfg["seccions"]["ordre"] = ordre + [s for s in totes if s not in ordre]
    cfg["seccions"]["visibles"] = {k: v for k, v in cfg["seccions"]["visibles"].items() if k in totes}
    motius_propis = {x["id"] for x in cfg.get("motius_propis", [])}
    cfg["motius"] = [m for m in cfg["motius"] if m in MOTIUS or m in motius_propis]
    return cfg


def text_idioma(per_idioma: dict | None, idioma: str) -> str:
    """El text en l'idioma demanat o, si no hi és, en el primer que hi hagi (ca, es, en, fr)."""
    per_idioma = per_idioma or {}
    for i in (idioma, "ca", "es", "en", "fr"):
        if per_idioma.get(i):
            return per_idioma[i]
    return ""


def noms_motius(con: sqlite3.Connection) -> dict[str, str]:
    """Nom en català (per al tauler i els informes) dels motius propis i dels estàndard redactats per la marca.

    Es busca a la configuració general i a la de cada botiga: un motiu propi d'una sola botiga també té nom.
    """
    out: dict[str, str] = {}
    files = con.execute("SELECT botiga_id, config_json FROM config_fitxa ORDER BY botiga_id = '*' ").fetchall()
    for f in files:
        cfg = json.loads(f["config_json"])
        for x in cfg.get("motius_propis", []):
            out[x["id"]] = text_idioma(x.get("text"), "ca") or x["id"]
    return out


# ---------------------------------------------------------------- Lectura i escriptura


def _llegeix(con: sqlite3.Connection, botiga_id: str) -> dict | None:
    fila = con.execute("SELECT config_json FROM config_fitxa WHERE botiga_id = ?", (botiga_id,)).fetchone()
    return json.loads(fila["config_json"]) if fila else None


def general(con: sqlite3.Connection) -> dict:
    return normalitza(fusiona(DEFECTE, _llegeix(con, GENERAL)))


def de_botiga(con: sqlite3.Connection, botiga_id: str | None) -> dict | None:
    """La configuració parcial d'una botiga, o None si no en té."""
    return _llegeix(con, botiga_id) if botiga_id and botiga_id != GENERAL else None


def efectiva(con: sqlite3.Connection, botiga_id: str | None) -> dict:
    """La configuració que aplica la fitxa: general + la de la botiga."""
    return normalitza(fusiona(general(con), de_botiga(con, botiga_id)))


def resposta(con: sqlite3.Connection, botiga_id: str | None) -> dict:
    """Forma de `GET /fitxa/config`."""
    return {"general": general(con), "botiga": de_botiga(con, botiga_id), "efectiva": efectiva(con, botiga_id)}


def desa(con: sqlite3.Connection, botiga_id: str | None, cfg: dict) -> None:
    """Desa la general (botiga None) sencera, o la parcial d'una botiga. Una botiga amb `{}` torna a la general."""
    if botiga_id in (None, GENERAL):
        net = normalitza(fusiona(general(con), valida_config(cfg)))
        clau = GENERAL
    else:
        net = valida_config(cfg, parcial=True)
        clau = botiga_id
        if not net:
            con.execute("DELETE FROM config_fitxa WHERE botiga_id = ?", (clau,))
            con.commit()
            return
    con.execute("""INSERT INTO config_fitxa (botiga_id, config_json, actualitzada) VALUES (?, ?, ?)
                   ON CONFLICT(botiga_id) DO UPDATE SET config_json = excluded.config_json,
                     actualitzada = excluded.actualitzada""",
                (clau, json.dumps(net, ensure_ascii=False), temps.ara()))
    con.commit()


# ---------------------------------------------------------------- Contingut per model


def valida_contingut(c) -> dict:
    """Valida un ContingutModel (tots els camps opcionals) i el retorna net."""
    c = _diccionari(c, "contingut")
    sobrants = set(c) - set(_CAMPS_CONTINGUT)
    if sobrants:
        raise ErrorConfig(f"Camps desconeguts: {', '.join(sorted(sobrants))}")
    net: dict = {}
    for k in ("nom", "descripcio", "ajust", "guia_talles"):
        if c.get(k) not in (None, ""):
            net[k] = _text(c[k], k, 200 if k == "nom" else 4000)
    if c.get("cura"):
        if not isinstance(c["cura"], list) or len(c["cura"]) > 20:
            raise ErrorConfig("«cura» ha de ser una llista de textos (màxim 20)")
        net["cura"] = [_text(x, "cura", 300) for x in c["cura"]]
    if c.get("faq"):
        if not isinstance(c["faq"], list) or len(c["faq"]) > 30:
            raise ErrorConfig("«faq» ha de ser una llista (màxim 30)")
        net["faq"] = []
        for x in c["faq"]:
            if not isinstance(x, dict) or set(x) != {"q", "a"}:
                raise ErrorConfig("Cada pregunta de «faq» ha de tenir «q» i «a»")
            net["faq"].append({"q": _text(x["q"], "faq.q", 500), "a": _text(x["a"], "faq.a", 2000)})
    if c.get("combina"):
        if not isinstance(c["combina"], list) or len(c["combina"]) > 6:
            raise ErrorConfig("«combina» ha de ser una llista de models (màxim 6)")
        net["combina"] = [_text(x, "combina", 64) for x in c["combina"]]
    return net


def contingut(con: sqlite3.Connection, model: str) -> dict[str, dict]:
    """{idioma: ContingutModel} d'un model."""
    return {f["idioma"]: json.loads(f["camps_json"]) for f in con.execute(
        "SELECT idioma, camps_json FROM contingut_model WHERE model = ? ORDER BY idioma", (model,))}


def desa_contingut(con: sqlite3.Connection, model: str, idioma: str, c: dict) -> None:
    """Desa el contingut d'un model en un idioma. Un contingut buit l'esborra (torna al fitxer d'origen)."""
    if idioma not in IDIOMES:
        raise ErrorConfig(f"Idioma desconegut: {idioma}")
    net = valida_contingut(c)
    if not net:
        con.execute("DELETE FROM contingut_model WHERE model = ? AND idioma = ?", (model, idioma))
    else:
        con.execute("""INSERT INTO contingut_model (model, idioma, camps_json, actualitzat) VALUES (?, ?, ?, ?)
                       ON CONFLICT(model, idioma) DO UPDATE SET camps_json = excluded.camps_json,
                         actualitzat = excluded.actualitzat""",
                    (model, idioma, json.dumps(net, ensure_ascii=False), temps.ara()))
    con.commit()
