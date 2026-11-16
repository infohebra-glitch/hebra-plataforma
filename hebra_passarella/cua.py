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
import uuid
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
            self._con.execute("CREATE TABLE IF NOT EXISTS meta (clau TEXT PRIMARY KEY, valor TEXT NOT NULL)")
            fila = self._con.execute("SELECT valor FROM meta WHERE clau = 'instal·lacio'").fetchone()
            if fila is None:
                fila = (uuid.uuid4().hex[:12],)
                self._con.execute("INSERT INTO meta VALUES ('instal·lacio', ?)", (fila[0],))
            self._con.commit()
        # Identifica aquesta passarel·la i dona un `ref` únic a cada element: si un lot s'envia dues
        # vegades (la resposta es perd), la plataforma no el compta dues cops.
        self.id = fila[0]

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
        for id_, tipus, dades in files:
            e = json.loads(dades)
            e["ref"] = f"{self.id}-{id_}"
            lot["lectures" if tipus == "lectura" else "sensors"].append(e)
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


VERSIO = "0.4"


def senyal(cua: Cua) -> dict:
    """El que la plataforma necessita per saber que la passarel·la viu i va al dia."""
    return {"id": cua.id, "pendents": cua.mida(), "versio": VERSIO,
            "ara": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def envia_lot(url_plataforma: str, clau: str, lot: dict, timeout: float = 20) -> None:
    req = urllib.request.Request(
        url_plataforma.rstrip("/") + "/api/v1/lots", data=json.dumps(lot).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Hebra-Clau": clau})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resposta = json.loads(r.read() or b"{}")
    if resposta.get("errors"):
        # Errors d'element (p. ex. una antena que no existeix a la plataforma): no es reintenten.
        log.warning("La plataforma ha rebutjat %s elements: %s", len(resposta["errors"]), resposta["errors"][:3])


def _envia_amb_senyal(cua: Cua, url: str, clau: str, ids: list[int], lot: dict) -> None:
    lot["passarella"] = senyal(cua)
    envia_lot(url, clau, lot)
    cua.esborra(ids)


def bucle_enviament(cua: Cua, url_plataforma: str, clau: str, cada_s: float = 5, atura=None,
                    senyal_cada_s: float = 60) -> None:
    """Envia la cua en lots. Cada `senyal_cada_s` s'envia també un lot buit: així la plataforma
    sap que la passarel·la és viva encara que a la botiga no passi res."""
    espera, maxim, darrer_senyal = cada_s, 2000, 0.0
    while not (atura and atura.is_set()):
        ids, lot = cua.lot(maxim)
        if ids or time.monotonic() - darrer_senyal >= senyal_cada_s:
            try:
                _envia_amb_senyal(cua, url_plataforma, clau, ids, lot)
                darrer_senyal = time.monotonic()
                espera, maxim = cada_s, 2000
                if ids:
                    continue  # si n'hi ha més, envia'ls de seguida
            except urllib.error.HTTPError as e:
                if e.code in (400, 413, 422):
                    # La plataforma no accepta aquest lot i ho tornaria a dir sempre: un sol element
                    # dolent no ha de bloquejar la resta. Es parteix el lot i, si és un de sol, es descarta.
                    if len(ids) > 1:
                        maxim = max(1, len(ids) // 2)
                        log.warning("La plataforma respon %s; es prova amb lots de %s", e.code, maxim)
                        continue
                    if ids:
                        log.error("Element descartat: la plataforma el rebutja (%s): %s", e.code, lot)
                        cua.esborra(ids)
                        maxim = 2000
                        continue
                log.error("La plataforma respon %s; reintent més tard (%s pendents)", e.code, cua.mida())
                espera = min(espera * 2, 300)
            except Exception as e:
                log.error("Sense connexió amb la plataforma (%s); %s pendents", e, cua.mida())
                espera = min(espera * 2, 300)
        else:
            espera = cada_s
        cua.purga()
        time.sleep(espera)
