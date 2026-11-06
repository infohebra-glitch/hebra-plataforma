"""Autenticació de l'equip de la marca i de les botigues (tauler /app i API /api/v2).

  * Contrasenyes: PBKDF2-SHA256 amb sal aleatòria i 310.000 iteracions
    (`pbkdf2_sha256$iteracions$sal$hash`, tot en hex). Mai en clar.
  * Sessió: galeta `hebra_sessio` amb un testimoni signat amb HMAC-SHA256
    (`base64url(json{"uid","exp"}).base64url(signatura)`) i caducitat de 12 h.
    No hi ha estat al servidor: tancar la sessió esborra la galeta.
  * Límits: intents d'inici de sessió per IP i correu, i un cubell de testimonis
    per IP per als formularis públics de la fitxa NFC.

Els clients finals (fitxa NFC) no tenen usuari ni galeta.
"""

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from collections import deque

from . import temps

NOM_GALETA = "hebra_sessio"
DURADA_SESSIO_S = 12 * 3600
ITERACIONS = 310_000
ROLS = ("admin", "marca", "botiga")


# ---------------------------------------------------------------- Contrasenyes


def hash_contrasenya(contrasenya: str, iteracions: int | None = None) -> str:
    iteracions = iteracions or ITERACIONS
    sal = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", contrasenya.encode(), sal, iteracions)
    return f"pbkdf2_sha256${iteracions}${sal.hex()}${h.hex()}"


def comprova_contrasenya(contrasenya: str, desat: str) -> bool:
    try:
        algorisme, iteracions, sal, h = desat.split("$")
        if algorisme != "pbkdf2_sha256":
            return False
        calculat = hashlib.pbkdf2_hmac("sha256", contrasenya.encode(), bytes.fromhex(sal), int(iteracions))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculat.hex(), h)


# Hash fix per comparar quan el correu no existeix (el temps de resposta no delata si l'usuari hi és).
_HASH_FALS = hash_contrasenya(secrets.token_hex(8))


# ---------------------------------------------------------------- Testimoni de sessió


def _b64(dades: bytes) -> str:
    return base64.urlsafe_b64encode(dades).rstrip(b"=").decode()


def _desb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def signa(secret: str, uid: int, ara: float | None = None, durada_s: int = DURADA_SESSIO_S) -> str:
    cos = _b64(json.dumps({"uid": uid, "exp": int((ara or time.time()) + durada_s)}, separators=(",", ":")).encode())
    sig = hmac.new(secret.encode(), cos.encode(), hashlib.sha256).digest()
    return f"{cos}.{_b64(sig)}"


def verifica(secret: str, testimoni: str, ara: float | None = None) -> int | None:
    """Retorna l'id d'usuari si el testimoni és vàlid i no ha caducat; si no, None."""
    try:
        cos, sig = testimoni.split(".")
        esperada = hmac.new(secret.encode(), cos.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(esperada, _desb64(sig)):
            return None
        dades = json.loads(_desb64(cos))
        if int(dades["exp"]) < (ara or time.time()):
            return None
        return int(dades["uid"])
    except (ValueError, KeyError, TypeError):
        return None


# ---------------------------------------------------------------- Usuaris


def usuari_json(fila: sqlite3.Row) -> dict:
    return {"id": fila["id"], "nom": fila["nom"], "correu": fila["correu"], "rol": fila["rol"],
            "botiga_id": fila["botiga_id"]}


def crea_usuari(con: sqlite3.Connection, correu: str, nom: str, rol: str, contrasenya: str,
                botiga_id: str | None = None) -> int:
    correu = correu.strip().lower()
    if rol not in ROLS:
        raise ValueError(f"Rol desconegut: {rol}")
    if "@" not in correu:
        raise ValueError("Correu no vàlid")
    if len(contrasenya) < 10:
        raise ValueError("La contrasenya ha de tenir 10 caràcters o més")
    if rol == "botiga":
        if not botiga_id:
            raise ValueError("Un usuari de botiga necessita una botiga")
        if not con.execute("SELECT 1 FROM botiga WHERE id = ?", (botiga_id,)).fetchone():
            raise ValueError(f"Botiga desconeguda: {botiga_id}")
    else:
        botiga_id = None
    if con.execute("SELECT 1 FROM usuari WHERE correu = ?", (correu,)).fetchone():
        raise ValueError("Ja hi ha un usuari amb aquest correu")
    cur = con.execute(
        "INSERT INTO usuari (correu, nom, hash_contrasenya, rol, botiga_id, creat) VALUES (?, ?, ?, ?, ?, ?)",
        (correu, nom.strip(), hash_contrasenya(contrasenya), rol, botiga_id, temps.ara()))
    con.commit()
    return cur.lastrowid


def autentica(con: sqlite3.Connection, correu: str, contrasenya: str) -> sqlite3.Row | None:
    fila = con.execute("SELECT * FROM usuari WHERE correu = ? AND actiu = 1",
                       (correu.strip().lower(),)).fetchone()
    if fila is None:
        comprova_contrasenya(contrasenya, _HASH_FALS)
        return None
    return fila if comprova_contrasenya(contrasenya, fila["hash_contrasenya"]) else None


def usuari_per_id(con: sqlite3.Connection, uid: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM usuari WHERE id = ? AND actiu = 1", (uid,)).fetchone()


# ---------------------------------------------------------------- Límits (en memòria, un sol procés)


class LimitIntents:
    """Finestra lliscant: com a màxim `maxim` intents fallits per clau en `finestra_s` segons."""

    def __init__(self, maxim: int = 10, finestra_s: float = 15 * 60):
        self.maxim, self.finestra_s = maxim, finestra_s
        self._intents: dict[str, deque] = {}
        self._pany = threading.Lock()

    def bloquejat(self, clau: str, ara: float | None = None) -> bool:
        ara = ara or time.monotonic()
        with self._pany:
            d = self._intents.get(clau)
            while d and d[0] <= ara - self.finestra_s:
                d.popleft()
            return bool(d) and len(d) >= self.maxim

    def falla(self, clau: str, ara: float | None = None) -> None:
        with self._pany:
            self._intents.setdefault(clau, deque()).append(ara or time.monotonic())
            if len(self._intents) > 10_000:  # no deixem créixer la memòria indefinidament
                self._intents.clear()

    def reinicia(self, clau: str | None = None) -> None:
        with self._pany:
            if clau is None:
                self._intents.clear()
            else:
                self._intents.pop(clau, None)


class CubellTestimonis:
    """Cubell de testimonis per clau (IP): `capacitat` peticions de cop i `ritme` per segon després."""

    def __init__(self, capacitat: float = 30, ritme: float = 0.5):
        self.capacitat, self.ritme = capacitat, ritme
        self._cubells: dict[str, tuple[float, float]] = {}
        self._pany = threading.Lock()

    def permet(self, clau: str, ara: float | None = None) -> bool:
        ara = ara or time.monotonic()
        with self._pany:
            testimonis, darrer = self._cubells.get(clau, (self.capacitat, ara))
            testimonis = min(self.capacitat, testimonis + (ara - darrer) * self.ritme)
            if len(self._cubells) > 10_000:
                self._cubells.clear()
            if testimonis < 1:
                self._cubells[clau] = (testimonis, ara)
                return False
            self._cubells[clau] = (testimonis - 1, ara)
            return True

    def reinicia(self) -> None:
        with self._pany:
            self._cubells.clear()
