"""Peces comunes de l'analítica: paràmetres, consultes base i petites utilitats.

Criteris que comparteixen totes les funcions:
  * només compten les proves de confiança `alta` i `mitjana`;
  * `Filtre.botiga_id = None` vol dir totes les botigues;
  * les hores es desen en hora local ISO 8601 (hebra/temps.py), així que
    comparar-les com a text amb 'AAAA-MM-DD' filtra pel dia local de la botiga.

Les consultes fan servir paràmetres amb nom (:b, :des, :fins) perquè es llegeixin
millor: `:fins` és el dia SEGÜENT a `Filtre.fins` (exclusiu).
"""

import json
import math
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta

from . import Filtre

CONFIANCES_VALIDES = ("alta", "mitjana")

# Valors per defecte dels paràmetres coneguts (docs/API.md). La taula `parametre` mana.
DEFECTES = {
    "marge_peca": 40,
    "quota_mensual": 350,
    "n_molt_provat": 10,        # proves per setmana del període (insight 3)
    "dies_estoc_parat": 21,     # insight 14
    "setmanes_cobertura": 8,    # insight 15
    "minuts_abandonada": 30,    # insight 13
    "senyals_perdua": 0,        # insight 25: només si val 1
}

MOTIUS = {
    "talla": "Talla",
    "tall": "Tall o forma",
    "preu": "Preu",
    "color": "Color",
    "qualitat": "Qualitat o teixit",
    "altre": "Altre",
}

ROLS = ("CEO", "PROD", "BOT", "MKT", "SOST")

_LLETRES = ["XXS", "XS", "S", "M", "L", "XL", "XXL"]


# ---------------------------------------------------------------- Paràmetres


def parametre(con: sqlite3.Connection, botiga_id: str | None, clau: str, defecte):
    """Valor d'un paràmetre: primer el de la botiga, després el general ('*'), si no `defecte`.

    Si `defecte` és un nombre, el text de la taula es converteix a nombre
    (enter si no té decimals); si no es pot convertir, es torna `defecte`.
    """
    for b in ([botiga_id, "*"] if botiga_id and botiga_id != "*" else ["*"]):
        fila = con.execute("SELECT valor FROM parametre WHERE botiga_id = ? AND clau = ?", (b, clau)).fetchone()
        if fila is not None:
            return _converteix(fila[0], defecte)
    return defecte


def _converteix(valor: str, defecte):
    if isinstance(defecte, bool) or not isinstance(defecte, (int, float)):
        return valor
    try:
        x = float(str(valor).replace(",", "."))
    except ValueError:
        return defecte
    return int(x) if x.is_integer() else x


def par(con: sqlite3.Connection, f: Filtre, clau: str):
    """Paràmetre conegut (amb el defecte de DEFECTES) per a la botiga del filtre."""
    return parametre(con, f.botiga_id, clau, DEFECTES[clau])


# ---------------------------------------------------------------- Període


def params(f: Filtre) -> dict:
    return {"b": f.botiga_id, "des": f.inici_iso, "fins": f.fi_exclusiu_iso}


def dies(f: Filtre) -> int:
    return (f.fins - f.des).days + 1


def setmanes(f: Filtre) -> float:
    return dies(f) / 7


def periode(f: Filtre) -> dict:
    return {"des": f.inici_iso, "fins": f.fins.isoformat(), "dies": dies(f)}


def anterior(f: Filtre) -> Filtre:
    """El període de la mateixa durada just abans."""
    n = dies(f)
    return Filtre(f.botiga_id, f.des - timedelta(days=n), f.des - timedelta(days=1))


def amb_dates(f: Filtre, des: date, fins: date) -> Filtre:
    return Filtre(f.botiga_id, des, fins)


def dilluns(d: date) -> date:
    return d - timedelta(days=d.weekday())


def dt(text: str) -> datetime:
    return datetime.fromisoformat(text)


# ---------------------------------------------------------------- Nombres


def frac(n: float, d: float, decimals: int = 3) -> float | None:
    """Fracció 0-1 arrodonida, o None si no hi ha denominador."""
    return round(n / d, decimals) if d else None


def resta(a: float | None, b: float | None) -> float | None:
    return round(a - b, 3) if a is not None and b is not None else None


def arrodoneix_5_punts(x: float) -> float:
    """0,415 -> 0,40 (corba de talles, insight 5)."""
    return round(round(x * 20) / 20, 2)


def mediana(valors: list[float]) -> float | None:
    if not valors:
        return None
    v = sorted(valors)
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def quartils(valors: dict) -> dict:
    """{clau: valor} -> {clau: quartil 1-4}, on 1 és el quartil inferior. Empats: el mateix quartil."""
    ordenats = sorted(valors.values())
    n = len(ordenats)
    return {k: ordenats.index(v) * 4 // n + 1 for k, v in valors.items()} if n else {}


# ---------------------------------------------------------------- Text en català


def pct_txt(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.0f} %"


def num_txt(x: float | None, decimals: int = 2) -> str:
    if x is None:
        return "—"
    text = f"{x:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return text.replace(" ", ".")


def punts_txt(d: float | None) -> str:
    """Diferència de conversió en punts: 0,069 -> '+6,9 punts'."""
    return "—" if d is None else f"{d * 100:+.1f} punts".replace(".", ",")


def un_de_cada(conv: float | None) -> str:
    if not conv:
        return "cap"
    return f"1 de cada {max(1, round(1 / conv))}"


def p_txt(p: float | None) -> str:
    if p is None:
        return "—"
    return "< 0,001" if p < 0.001 else num_txt(p, 2 if p >= 0.01 else 3)


def plural(n: int, singular: str, plural_: str) -> str:
    return f"{n} {singular if n == 1 else plural_}"


def ordre_talla(t: str | None) -> tuple:
    """Lletres de petita a gran, després números de menor a major, després la resta."""
    t = t or ""
    if t in _LLETRES:
        return (0, _LLETRES.index(t), "")
    try:
        return (1, float(t.replace(",", ".")), "")
    except ValueError:
        return (2, 0, t)


# ---------------------------------------------------------------- Catàleg


def info_models(con: sqlite3.Connection) -> dict[str, dict]:
    """{model: {nom, categoria, color, preu, origen, gtins}} a partir de catalog_sku."""
    out: dict[str, dict] = {}
    for k in con.execute("SELECT * FROM catalog_sku ORDER BY rowid"):
        m = out.get(k["model"])
        if m is None:
            origen = json.loads(k["origen_json"]) if k["origen_json"] else None
            nom = (origen or {}).get("nom", k["model"])
            if isinstance(nom, dict):
                nom = nom.get("ca") or next(iter(nom.values()), k["model"])
            m = out[k["model"]] = {"nom": nom, "categoria": k["categoria"], "color": k["color"],
                                   "preu": k["preu_eur"], "origen": origen, "gtins": []}
        m["gtins"].append(k["gtin"])
    return out


def nom_model(info: dict, model: str | None) -> str:
    return info.get(model, {}).get("nom", model or "sense catàleg")


# ---------------------------------------------------------------- Consultes base


def proves_valides(con: sqlite3.Connection, f: Filtre) -> list[sqlite3.Row]:
    """Proves de confiança alta o mitjana del període, amb el SKU i si s'han venut (atribució)."""
    return con.execute(
        """SELECT p.id, p.epc, p.gtin, p.sessio_id, s.inici, s.fi, s.grup, s.cabina_id, c.botiga_id,
                  k.model, k.color, k.talla, k.categoria,
                  (a.venda_id IS NOT NULL) AS venuda
           FROM prova p
           JOIN sessio s ON s.id = p.sessio_id
           JOIN cabina c ON c.id = s.cabina_id
           LEFT JOIN catalog_sku k ON k.gtin = p.gtin
           LEFT JOIN atribucio a ON a.prova_id = p.id
           WHERE p.confianca IN ('alta', 'mitjana')
             AND s.inici >= :des AND s.inici < :fins AND (:b IS NULL OR c.botiga_id = :b)""",
        params(f)).fetchall()


def n_ambigues(con: sqlite3.Connection, f: Filtre) -> int:
    return con.execute(
        """SELECT COUNT(*) FROM prova p JOIN sessio s ON s.id = p.sessio_id JOIN cabina c ON c.id = s.cabina_id
           WHERE p.confianca = 'ambigua' AND s.inici >= :des AND s.inici < :fins
             AND (:b IS NULL OR c.botiga_id = :b)""", params(f)).fetchone()[0]


def sessions(con: sqlite3.Connection, f: Filtre) -> list[sqlite3.Row]:
    """Sessions de cabina del període (amb o sense proves)."""
    return con.execute(
        """SELECT s.id, s.cabina_id, c.botiga_id, s.inici, s.fi FROM sessio s JOIN cabina c ON c.id = s.cabina_id
           WHERE s.inici >= :des AND s.inici < :fins AND (:b IS NULL OR c.botiga_id = :b)""",
        params(f)).fetchall()


def vendes(con: sqlite3.Connection, f: Filtre) -> list[sqlite3.Row]:
    """Línies de venda (no devolucions) del període, amb el SKU."""
    return con.execute(
        """SELECT v.id, v.botiga_id, v.data, v.ts, v.gtin, v.quantitat, v.import_eur,
                  k.model, k.color, k.talla, k.categoria
           FROM venda_linia v LEFT JOIN catalog_sku k ON k.gtin = v.gtin
           WHERE v.quantitat > 0 AND v.data >= :des AND v.data < :fins
             AND (:b IS NULL OR v.botiga_id = :b)""", params(f)).fetchall()


def peticions(con: sqlite3.Connection, f: Filtre) -> list[sqlite3.Row]:
    """Peticions de talla del període, amb el SKU demanat i el nom de la cabina."""
    return con.execute(
        """SELECT pt.*, k.model, k.color, cab.nom AS cabina_nom
           FROM peticio_talla pt
           LEFT JOIN catalog_sku k ON k.gtin = pt.gtin_demanat
           LEFT JOIN cabina cab ON cab.id = pt.cabina
           WHERE pt.hora_peticio >= :des AND pt.hora_peticio < :fins
             AND (:b IS NULL OR pt.botiga_id = :b)
           ORDER BY pt.hora_peticio, pt.id""", params(f)).fetchall()


def es_perduda(p: sqlite3.Row) -> bool:
    """Demanda perduda (insight 7): la talla demanada no hi era."""
    return p["estat"] == "no_disponible" or p["disponible"] == 0


def segons_resposta(p: sqlite3.Row) -> float | None:
    """Segons entre la petició i el lliurament (insight 10); None si no s'ha lliurat."""
    if p["estat"] != "lliurada" or not p["hora_resolta"]:
        return None
    return (dt(p["hora_resolta"]) - dt(p["hora_peticio"])).total_seconds()


def nfc(con: sqlite3.Connection, f: Filtre, *tipus: str) -> list[sqlite3.Row]:
    """Esdeveniments de la fitxa NFC del període (opcionalment, només d'uns tipus)."""
    filtre_tipus = f"AND e.tipus IN ({','.join('?' * len(tipus))})" if tipus else ""
    return con.execute(
        f"""SELECT e.*, k.model FROM esdeveniment_nfc e LEFT JOIN catalog_sku k ON k.gtin = e.gtin
            WHERE e.ts >= ? AND e.ts < ? AND (? IS NULL OR e.botiga_id = ?) {filtre_tipus}""",
        (f.inici_iso, f.fi_exclusiu_iso, f.botiga_id, f.botiga_id, *tipus)).fetchall()


def abandonades(con: sqlite3.Connection, f: Filtre) -> list[sqlite3.Row]:
    return con.execute(
        """SELECT pa.*, c.botiga_id, c.nom AS cabina_nom, e.gtin, k.model, k.talla
           FROM peca_abandonada pa JOIN cabina c ON c.id = pa.cabina_id
           LEFT JOIN etiqueta e ON e.epc = pa.epc
           LEFT JOIN catalog_sku k ON k.gtin = e.gtin
           WHERE pa.detectada >= :des AND pa.detectada < :fins AND (:b IS NULL OR c.botiga_id = :b)
           ORDER BY pa.detectada""", params(f)).fetchall()


def estoc_per_gtin(con: sqlite3.Connection, botiga_id: str | None) -> dict[str, int]:
    """Unitats en estoc per GTIN (sumades si són totes les botigues). Sense fila = desconegut."""
    out: dict[str, int] = defaultdict(int)
    for r in con.execute("SELECT gtin, unitats FROM estoc WHERE (:b IS NULL OR botiga_id = :b)", {"b": botiga_id}):
        out[r["gtin"]] += r["unitats"]
    return dict(out)


def estoc_de(estoc: dict[str, int], gtins: list[str]) -> int | None:
    """Unitats d'un grup de GTIN, o None si cap no té dada d'estoc."""
    coneguts = [estoc[g] for g in gtins if g in estoc]
    return sum(coneguts) if coneguts else None


def dades_simulades(con: sqlite3.Connection, botiga_id: str | None) -> bool:
    """El simulador marca les seves dades amb el paràmetre `dades_simulades` = 1."""
    return parametre(con, botiga_id, "dades_simulades", 0) == 1


# ---------------------------------------------------------------- Acció


def accio(text: str, insight: str, model: str | None, responsable: str, data_limit: date) -> dict:
    """Una acció concreta (forma `Accio` de docs/API.md). `insight` és la clau, com a `decisio.insight`."""
    assert responsable in ROLS, responsable
    return {"text": text, "insight": insight, "model": model, "responsable": responsable,
            "data_limit": data_limit.isoformat()}


def ceil_div(a: float, b: float) -> int:
    return math.ceil(a / b)
