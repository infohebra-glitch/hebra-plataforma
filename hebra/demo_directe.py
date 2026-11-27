"""Demo en directe sense lector: fa veure que algú entra a una cabina amb unes peces.

Serveix per ensenyar la plataforma en una trucada (per exemple, a Mango) quan encara no hi ha
cap lector a la botiga. Envia a la plataforma, pel mateix camí que la passarel·la de veritat
(`POST /api/v1/lots` amb la clau de passarel·la), lots amb l'hora d'ara:

  1. porta tancada i presència a la cabina triada;
  2. cada 10 s, lectures fortes de les etiquetes de les peces triades a l'antena d'aquella cabina;
  3. al final, porta oberta i sense presència, i es processa la botiga perquè la prova compti.

Mentrestant, a «Provadors en directe» del tauler la cabina surt ocupada amb les peces dins,
i al Resum hi apareix la prova en acabar. Només es fa servir amb el lot de prova (PROVA-01) o
amb una botiga de demostració: les lectures són inventades.

També treu els enllaços NFC d'una peça de cada model, per gravar-los en un adhesiu NFC.

Ús (al servidor):
  sudo hebra-admin demo-enllacos --botiga PROVA-01 --url https://plataforma.hebraia.com
  sudo hebra-admin demo-directe --botiga PROVA-01 --cabina 1 --minuts 3
  sudo hebra-admin demo-directe --botiga PROVA-01 --cabina 1 --model CL-24-NAT --model TX-26-IND
"""

import json
import sqlite3
import time
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

INTERVAL_S = 10
RSSI = -47.0


class ErrorDemo(ValueError):
    pass


def enllacos(con: sqlite3.Connection, botiga_id: str, url: str) -> list[dict]:
    """Una peça (etiqueta) de cada model que té etiquetes, amb l'enllaç NFC que s'ha de gravar."""
    files = con.execute(
        """SELECT s.model, s.color, s.talla, e.epc, e.nfc_token FROM etiqueta e
           JOIN catalog_sku s ON s.gtin = e.gtin
           WHERE e.rowid IN (SELECT MIN(e2.rowid) FROM etiqueta e2 JOIN catalog_sku s2 ON s2.gtin = e2.gtin
                             GROUP BY s2.model)
           ORDER BY s.model""").fetchall()
    base = url.rstrip("/")
    return [{"model": f["model"], "color": f["color"], "talla": f["talla"], "epc": f["epc"],
             "url": f"{base}/p/{f['nfc_token']}?b={botiga_id}"} for f in files]


def _cabina_i_antena(con: sqlite3.Connection, botiga_id: str, cabina: str) -> tuple[str, str]:
    if not con.execute("SELECT 1 FROM botiga WHERE id = ?", (botiga_id,)).fetchone():
        raise ErrorDemo(f"No hi ha cap botiga «{botiga_id}». Carrega el lot de prova des del tauler.")
    cab_id = cabina if cabina.startswith(botiga_id) else f"{botiga_id}-C{cabina}"
    f = con.execute("SELECT a.id FROM antena a JOIN cabina c ON c.id = a.cabina_id "
                    "WHERE c.id = ? AND c.botiga_id = ? ORDER BY a.port LIMIT 1", (cab_id, botiga_id)).fetchone()
    if not f:
        raise ErrorDemo(f"La cabina «{cab_id}» no existeix o no té antena.")
    return cab_id, f["id"]


def _epcs(con: sqlite3.Connection, models: list[str]) -> list[tuple[str, str]]:
    """(epc, model) d'una etiqueta per model. Sense models: els dos primers models amb etiquetes."""
    if not models:
        models = [r[0] for r in con.execute(
            "SELECT DISTINCT s.model FROM etiqueta e JOIN catalog_sku s ON s.gtin = e.gtin ORDER BY s.model LIMIT 2")]
    out = []
    for m in models:
        f = con.execute("SELECT e.epc, s.model FROM etiqueta e JOIN catalog_sku s ON s.gtin = e.gtin "
                        "WHERE lower(s.model) = lower(?) ORDER BY e.rowid LIMIT 1", (m,)).fetchone()
        if not f:
            raise ErrorDemo(f"No hi ha cap etiqueta del model «{m}».")
        out.append((f["epc"], f["model"]))
    if not out:
        raise ErrorDemo("No hi ha cap etiqueta a la plataforma.")
    return out


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def envia_http(api: str, clau: str) -> Callable[[str, dict | None], dict]:
    """Envia a la plataforma pel camí de la passarel·la (`X-Hebra-Clau`)."""
    def envia(cami: str, cos: dict | None) -> dict:
        dades = None if cos is None else json.dumps(cos).encode()
        req = urllib.request.Request(api.rstrip("/") + cami, data=dades if dades is not None else b"",
                                     headers={"X-Hebra-Clau": clau, "Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read() or b"{}")
    return envia


def executa(con: sqlite3.Connection, botiga_id: str, cabina: str, models: list[str], minuts: float,
            envia: Callable[[str, dict | None], dict], zona: str = "Europe/Madrid",
            espera: Callable[[float], None] = time.sleep, ara: Callable[[], datetime] | None = None,
            diu: Callable[[str], None] = print) -> dict:
    """Simula una sessió de cabina en directe. Retorna un resum (lots enviats, peces, proves)."""
    cab_id, antena = _cabina_i_antena(con, botiga_id, cabina)
    peces = _epcs(con, models)
    tz = ZoneInfo(zona)
    ara = ara or (lambda: datetime.now(tz))
    passos = max(1, round(minuts * 60 / INTERVAL_S))
    ref = f"demo-{int(ara().timestamp())}"

    t0 = ara()
    envia("/api/v1/lots", {"lectures": [], "sensors": [
        {"cabina": cab_id, "ts": _iso(t0), "tipus": "porta_tancada", "ref": f"{ref}-pt"},
        {"cabina": cab_id, "ts": _iso(t0), "tipus": "presencia_si", "ref": f"{ref}-ps"}]})
    diu(f"Cabina {cab_id} ocupada amb: {', '.join(m for _, m in peces)}. Obre «Provadors en directe» al tauler.")
    lots = 1
    for i in range(passos):
        espera(INTERVAL_S)
        fi = ara()
        inici = fi - timedelta(seconds=INTERVAL_S)
        envia("/api/v1/lots", {"lectures": [
            {"epc": epc, "antena": antena, "inici": _iso(inici), "fi": _iso(fi), "n": 14,
             "rssi_max": RSSI + 2, "rssi_mitja": RSSI, "ref": f"{ref}-{i}-{j}"}
            for j, (epc, _) in enumerate(peces)], "sensors": []})
        lots += 1
        diu(f"  {int((fi - t0).total_seconds())} s dins la cabina")
    t1 = ara()
    envia("/api/v1/lots", {"lectures": [], "sensors": [
        {"cabina": cab_id, "ts": _iso(t1), "tipus": "porta_oberta", "ref": f"{ref}-po"},
        {"cabina": cab_id, "ts": _iso(t1 + timedelta(seconds=5)), "tipus": "presencia_no", "ref": f"{ref}-pn"}]})
    lots += 1
    res = envia(f"/api/v1/processa?botiga={botiga_id}", None)
    diu(f"Fet: la cabina torna a estar lliure. {res}")
    return {"cabina": cab_id, "antena": antena, "peces": [m for _, m in peces], "lots": lots, "processa": res}
