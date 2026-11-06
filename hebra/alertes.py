"""Alertes en directe per al dependent (informe A) i detecció de peces abandonades (insight 13).

Bus d'esdeveniments
-------------------
Publicació/subscripció dins del procés: la fitxa NFC, la web del dependent i el
càlcul periòdic de proves corren al mateix procés que `GET /api/v2/flux`
(Server-Sent Events), que reenvia cada esdeveniment als dependents connectats.
Amb diversos processos (uvicorn --workers > 1) caldria un bus extern (p. ex.
Redis o LISTEN/NOTIFY de PostgreSQL); al pilot n'hi ha un.

Tipus d'esdeveniment (nom SSE): `peticio` (nova o canvi d'estat), `abandonada`
(peça abandonada nova), `alerta` (`talla_esgotada`) i `tasca` (tasca de botiga
nova o canviada, v0.3). També `cabina` (estat en directe d'una cabina, v0.3,
hebra/provadors.py). Les peticions poden ser de talla o d'assistència (camp `tipus`).

Peces abandonades
-----------------
Regla (simple i revisable): una peça provada en una sessió de cabina que es
continua llegint a la mateixa cabina `minuts_abandonada` minuts (paràmetre,
30 per defecte) després que la sessió s'hagi acabat, sense cap altra sessió
entremig i sense cap venda del mateix GTIN a la botiga, és una peça abandonada.
La presència és contínua si entre dues lectures hi ha menys de
`BUIT_MAXIM_S` segons. Es marca com a resolta quan deixa de llegir-se (algú
l'ha recollida). Al nivell Bàsic no hi ha sessions de cabina reals i no s'aplica.
"""

import asyncio
import json
import sqlite3
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import db, estoc, temps

BUIT_MAXIM_S = 120
DIES_FINESTRA = 7  # el càlcul periòdic només mira les sessions dels darrers dies amb dades de la cabina
PETICIONS_TALLA_ESGOTADA = 3


# ---------------------------------------------------------------- Bus


@dataclass
class Esdeveniment:
    tipus: str                 # nom de l'esdeveniment SSE: 'peticio' | 'abandonada' | 'alerta'
    dades: dict
    botiga_id: str | None

    def sse(self) -> str:
        return f"event: {self.tipus}\ndata: {json.dumps(self.dades, ensure_ascii=False)}\n\n"


@dataclass(eq=False)
class Subscripcio:
    botiga_id: str | None      # None = totes les botigues
    bucle: asyncio.AbstractEventLoop
    cua: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=500))

    def vol(self, ev: Esdeveniment) -> bool:
        return self.botiga_id is None or ev.botiga_id == self.botiga_id


class Bus:
    def __init__(self, recents: int = 200):
        self._subs: set[Subscripcio] = set()
        self._pany = threading.Lock()
        self.recents: deque[Esdeveniment] = deque(maxlen=recents)

    def subscriu(self, botiga_id: str | None = None) -> Subscripcio:
        """S'ha de cridar des del bucle asyncio que llegirà la cua."""
        s = Subscripcio(botiga_id, asyncio.get_running_loop())
        with self._pany:
            self._subs.add(s)
        return s

    def dessubscriu(self, s: Subscripcio) -> None:
        with self._pany:
            self._subs.discard(s)

    def publica(self, tipus: str, dades: dict, botiga_id: str | None) -> Esdeveniment:
        """Es pot cridar des de qualsevol fil (les rutes síncrones corren en un grup de fils)."""
        ev = Esdeveniment(tipus, dades, botiga_id)
        with self._pany:
            self.recents.append(ev)
            subs = [s for s in self._subs if s.vol(ev)]
        for s in subs:
            try:
                s.bucle.call_soon_threadsafe(_posa, s.cua, ev)
            except RuntimeError:  # el bucle ja s'ha tancat
                self.dessubscriu(s)
        return ev

    @property
    def subscriptors(self) -> int:
        return len(self._subs)


def _posa(cua: asyncio.Queue, ev: Esdeveniment) -> None:
    try:
        cua.put_nowait(ev)
    except asyncio.QueueFull:
        pass  # client massa lent: perd l'esdeveniment, però la llista es pot tornar a demanar


bus = Bus()


# ---------------------------------------------------------------- Peticions de talla


def _nom_model(origen_json: str | None, defecte: str) -> str:
    nom = json.loads(origen_json or "{}").get("nom", defecte)
    if isinstance(nom, dict):
        return nom.get("ca") or nom.get("es") or next(iter(nom.values()), defecte)
    return nom


def _segons(des: str, fins: str) -> int:
    return max(0, int((datetime.fromisoformat(fins) - datetime.fromisoformat(des)).total_seconds()))


def _altres_botigues(fila: sqlite3.Row) -> list[dict]:
    """v0.3 (A.5): si la talla demanada no hi és, on n'hi ha (taula `estoc`), de més a menys unitats."""
    if fila["tipus"] != "talla" or not (fila["disponible"] == 0 or fila["estat"] == "no_disponible"):
        return []
    altres = json.loads(fila["altres_json"] or "[]")
    return sorted(altres, key=lambda a: (-a["unitats"], a["botiga_id"]))


def peticio_json(fila: sqlite3.Row, ara: str | None = None) -> dict:
    """Forma de `GET /api/v2/peticions` (docs/API.md). `fila` ve de `SQL_PETICIONS`.

    `tipus`: 'talla' | 'assistencia' (v0.3, A.4). Una d'assistència té `talla` = ''.
    """
    fins = fila["hora_resolta"] or ara or temps.ara()
    return {"id": fila["id"], "tipus": fila["tipus"], "botiga_id": fila["botiga_id"], "model": fila["model"],
            "nom": _nom_model(fila["origen_json"], fila["model"]), "color": fila["color"],
            "talla": fila["talla_demanada"], "cabina": fila["cabina"], "hora_peticio": fila["hora_peticio"],
            "hora_resolta": fila["hora_resolta"], "estat": fila["estat"],
            "disponible": None if fila["disponible"] is None else bool(fila["disponible"]),
            "segons_espera": _segons(fila["hora_peticio"], fins),
            "altres_botigues": _altres_botigues(fila)}


SQL_PETICIONS = """SELECT pt.*, k.model, k.color, k.origen_json,
                          (SELECT json_group_array(json_object('botiga_id', e.botiga_id, 'nom', b.nom,
                                                               'unitats', e.unitats))
                           FROM estoc e JOIN botiga b ON b.id = e.botiga_id
                           WHERE e.gtin = pt.gtin_demanat AND e.botiga_id != pt.botiga_id AND e.unitats > 0
                          ) AS altres_json
                   FROM peticio_talla pt
                   JOIN catalog_sku k ON k.gtin = pt.gtin_demanat"""


def peticio(con: sqlite3.Connection, peticio_id: int) -> dict | None:
    fila = con.execute(SQL_PETICIONS + " WHERE pt.id = ?", (peticio_id,)).fetchone()
    return peticio_json(fila) if fila else None


def notifica_peticio(con: sqlite3.Connection, peticio_id: int, nova: bool) -> None:
    """Publica la petició (nova o canviada) i, si cal, l'alerta de talla esgotada."""
    p = peticio(con, peticio_id)
    if p is None:
        return
    bus.publica("peticio", dict(p, accio="nova" if nova else "canvi"), p["botiga_id"])
    if nova and p["disponible"] is False:
        _potser_talla_esgotada(con, peticio_id)


def _potser_talla_esgotada(con: sqlite3.Connection, peticio_id: int) -> None:
    """Alerta quan un GTIN sense estoc arriba a 3 peticions el mateix dia (només un cop, en arribar-hi)."""
    pt = con.execute(SQL_PETICIONS + " WHERE pt.id = ?", (peticio_id,)).fetchone()
    dia = pt["hora_peticio"][:10]
    n = con.execute(
        """SELECT COUNT(*) FROM peticio_talla WHERE botiga_id = ? AND gtin_demanat = ? AND disponible = 0
           AND substr(hora_peticio, 1, 10) = ?""", (pt["botiga_id"], pt["gtin_demanat"], dia)).fetchone()[0]
    if n != PETICIONS_TALLA_ESGOTADA:
        return
    nom = _nom_model(pt["origen_json"], pt["model"])
    bus.publica("alerta", {
        "id": f"te-{pt['botiga_id']}-{pt['gtin_demanat']}-{dia}", "tipus": "talla_esgotada",
        "text": f"{n} peticions avui de {nom} en {pt['talla_demanada']} i no n'hi ha estoc.",
        "botiga_id": pt["botiga_id"], "cabina": pt["cabina"], "creada": pt["hora_peticio"],
        "estat": "pendent", "ref": pt["gtin_demanat"]}, pt["botiga_id"])


def notifica_tasca(tasca: dict, nova: bool) -> None:
    """Publica una tasca de botiga (v0.3, D.1) nova o canviada: esdeveniment SSE `tasca`."""
    bus.publica("tasca", dict(tasca, accio="nova" if nova else "canvi"), tasca["botiga_id"])


def disponible(con: sqlite3.Connection, botiga_id: str | None, gtin: str, estoc_origen: int | None) -> int | None:
    """1/0 segons l'estoc conegut (taula `estoc` si hi és; si no, el del fitxer d'origen), o None."""
    u = estoc.unitats(con, botiga_id, gtin)
    if u is None:
        u = estoc_origen
    return None if u is None else int(u > 0)


# ---------------------------------------------------------------- Peces abandonades


def abandonada_json(fila: sqlite3.Row) -> dict:
    return {"id": fila["id"], "epc": fila["epc"], "model": fila["model"],
            "nom": _nom_model(fila["origen_json"], fila["model"] or fila["epc"]), "talla": fila["talla"],
            "cabina": fila["cabina_id"], "botiga_id": fila["botiga_id"], "detectada": fila["detectada"],
            "resolta": fila["resolta"]}


SQL_ABANDONADES = """SELECT a.*, c.botiga_id, k.model, k.talla, k.origen_json FROM peca_abandonada a
                     JOIN cabina c ON c.id = a.cabina_id
                     LEFT JOIN etiqueta e ON e.epc = a.epc LEFT JOIN catalog_sku k ON k.gtin = e.gtin"""


def _presencia_continua(lectures: list[tuple[datetime, datetime]], des: datetime) -> datetime | None:
    """Fi de la cadena de lectures que continua des de `des` (buits < BUIT_MAXIM_S), o None si no n'hi ha."""
    fi = None
    for inici, final in lectures:
        if final < des:
            continue
        referencia = fi or des
        if (inici - referencia).total_seconds() >= BUIT_MAXIM_S:
            break
        fi = max(fi or final, final)
    return fi


def detecta_abandonades(con: sqlite3.Connection, cabina_id: str, ara: str | None = None,
                        tot: bool = False) -> int:
    """Aplica la regla de peces abandonades a una cabina. Retorna quantes n'ha trobat de noves.

    Per defecte només mira les sessions dels darrers `DIES_FINESTRA` dies amb dades de la
    cabina (el càlcul corre cada pocs minuts); amb `tot=True`, tot l'historial.
    Idempotent: `detectada` és determinista (fi de la sessió + minuts) i la taula té UNIQUE.
    """
    cabina = con.execute("SELECT * FROM cabina WHERE id = ?", (cabina_id,)).fetchone()
    botiga_id = cabina["botiga_id"]
    minuts = float(db.parametre(con, botiga_id, "minuts_abandonada", "30"))
    ara_dt = datetime.fromisoformat(ara or temps.ara())
    sessions = con.execute("SELECT id, inici, fi FROM sessio WHERE cabina_id = ? ORDER BY inici",
                           (cabina_id,)).fetchall()
    if sessions and not tot:
        des = (datetime.fromisoformat(sessions[-1]["fi"]) - timedelta(days=DIES_FINESTRA)).isoformat()
        sessions = [s for s in sessions if s["fi"] >= des]
    noves = 0
    for i, s in enumerate(sessions):
        fi_sessio = datetime.fromisoformat(s["fi"])
        seguent = datetime.fromisoformat(sessions[i + 1]["inici"]) if i + 1 < len(sessions) else None
        limit = fi_sessio + timedelta(minutes=minuts)
        for p in con.execute("SELECT epc, gtin FROM prova WHERE sessio_id = ?", (s["id"],)).fetchall():
            lectures = [(datetime.fromisoformat(f["inici"]), datetime.fromisoformat(f["fi"])) for f in con.execute(
                """SELECT l.inici, l.fi FROM lectura_agregada l JOIN antena a ON a.id = l.antena_id
                   WHERE a.cabina_id = ? AND l.epc = ? AND l.fi >= ? ORDER BY l.inici""",
                (cabina_id, p["epc"], s["fi"]))]
            fi = _presencia_continua(lectures, fi_sessio)
            if fi is None or fi < limit or (seguent and seguent <= limit):
                continue
            if p["gtin"] and con.execute(
                    """SELECT 1 FROM venda_linia WHERE botiga_id = ? AND gtin = ? AND quantitat > 0
                       AND ((ts IS NOT NULL AND ts >= ? AND ts <= ?) OR (ts IS NULL AND data = ?))""",
                    (botiga_id, p["gtin"], s["inici"], limit.isoformat(), s["inici"][:10])).fetchone():
                continue  # se l'han endut: no és abandonada
            detectada = limit.isoformat()
            cur = con.execute("INSERT OR IGNORE INTO peca_abandonada (epc, cabina_id, detectada) VALUES (?, ?, ?)",
                              (p["epc"], cabina_id, detectada))
            ja_no_hi_es = (ara_dt - fi).total_seconds() > BUIT_MAXIM_S
            if ja_no_hi_es:
                con.execute("""UPDATE peca_abandonada SET resolta = ? WHERE epc = ? AND cabina_id = ?
                               AND detectada = ? AND resolta IS NULL""",
                            (fi.isoformat(timespec="seconds"), p["epc"], cabina_id, detectada))
            if cur.rowcount:
                noves += 1
                if not ja_no_hi_es:
                    fila = con.execute(SQL_ABANDONADES + " WHERE a.id = ?", (cur.lastrowid,)).fetchone()
                    bus.publica("abandonada", abandonada_json(fila), botiga_id)
    con.commit()
    return noves
