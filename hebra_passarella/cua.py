"""Cua local persistent (SQLite): si cau la xarxa, no es perd res durant 7 dies.

Tot el que es llegeix es desa primer aquí. Un fil a part ho envia a la
plataforma en lots i ho esborra quan la plataforma ha contestat bé.
"""

import json
import logging
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)


class Cua:
    def __init__(self, ruta: str, retencio_dies: int = 7):
        self._con = sqlite3.connect(ruta, check_same_thread=False)
        self._lock = threading.Lock()
        self.retencio = timedelta(days=retencio_dies)
        with self._lock:
            self._con.execute("""CREATE TABLE IF NOT EXISTS pendent (
                id INTEGER PRIMARY KEY AUTOINCREMENT, creat TEXT NOT NULL,
                tipus TEXT NOT NULL CHECK (tipus IN ('lectura', 'sensor')), dades TEXT NOT NULL)""")
            self._con.commit()

    def afegeix(self, tipus: str, elements: list[dict]) -> None:
        if not elements:
            return
        ara = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._con.executemany("INSERT INTO pendent (creat, tipus, dades) VALUES (?, ?, ?)",
                                  [(ara, tipus, json.dumps(e)) for e in elements])
            self._con.commit()

    def lot(self, maxim: int = 2000) -> tuple[list[int], dict]:
        with self._lock:
            files = self._con.execute("SELECT id, tipus, dades FROM pendent ORDER BY id LIMIT ?", (maxim,)).fetchall()
        lot = {"lectures": [], "sensors": []}
        for _, tipus, dades in files:
            lot["lectures" if tipus == "lectura" else "sensors"].append(json.loads(dades))
        return [f[0] for f in files], lot

    def esborra(self, ids: list[int]) -> None:
        if not ids:
            return
        with self._lock:
            self._con.execute(f"DELETE FROM pendent WHERE id IN ({','.join('?' * len(ids))})", ids)
            self._con.commit()

    def purga(self) -> int:
        """Esborra el que fa més de 7 dies que no s'ha pogut enviar."""
        limit = (datetime.now(timezone.utc) - self.retencio).isoformat()
        with self._lock:
            n = self._con.execute("DELETE FROM pendent WHERE creat < ?", (limit,)).rowcount
            self._con.commit()
        if n:
            log.warning("S'han perdut %s elements de més de %s dies sense xarxa", n, self.retencio.days)
        return n

    def mida(self) -> int:
        with self._lock:
            return self._con.execute("SELECT COUNT(*) FROM pendent").fetchone()[0]


def envia_lot(url_plataforma: str, clau: str, lot: dict, timeout: float = 20) -> None:
    req = urllib.request.Request(
        url_plataforma.rstrip("/") + "/api/v1/lots", data=json.dumps(lot).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Hebra-Clau": clau})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resposta = json.loads(r.read() or b"{}")
    if resposta.get("errors"):
        # Errors d'element (p. ex. una antena que no existeix a la plataforma): no es reintenten.
        log.warning("La plataforma ha rebutjat %s elements: %s", len(resposta["errors"]), resposta["errors"][:3])


def bucle_enviament(cua: Cua, url_plataforma: str, clau: str, cada_s: float = 5, atura=None) -> None:
    espera = cada_s
    while not (atura and atura.is_set()):
        ids, lot = cua.lot()
        if ids:
            try:
                envia_lot(url_plataforma, clau, lot)
                cua.esborra(ids)
                espera = cada_s
                continue  # si n'hi ha més, envia'ls de seguida
            except urllib.error.HTTPError as e:
                log.error("La plataforma respon %s; reintent més tard (%s pendents)", e.code, cua.mida())
            except Exception as e:
                log.error("Sense connexió amb la plataforma (%s); %s pendents", e, cua.mida())
            espera = min(espera * 2, 300)
        else:
            espera = cada_s
        cua.purga()
        time.sleep(espera)
