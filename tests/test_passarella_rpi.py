"""Proves de la passarel·la de la Raspberry contra un lector R700 fals (servidor HTTP local)."""

import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from hebra import passarella, proves
from hebra.config import ReglaProva
from hebra_passarella import lector
from hebra_passarella.agregador import Agregador
from hebra_passarella.cua import Cua, envia_lot


def test_interpreta_esdeveniment_documentat_per_impinj():
    # Exemple literal de la documentació d'Impinj (EPC en base64url).
    l = lector.interpreta('{"TagInventoryEvent":{"epc":"dHADJSAWhYUQABAJ","antennaPort":1,"peakRssiCdbm":-5700},'
                          ' "timestamp":"2018-10-24T17:17:50.324240614Z"}')
    assert l.epc_hex == "7470032520168585100010 09".replace(" ", "")
    assert l.port == 1 and l.rssi_dbm == -57.0
    assert l.ts == datetime(2018, 10, 24, 17, 17, 50, 324240, tzinfo=timezone.utc)
    assert lector.interpreta('{"EndOfCycleEvent":{}, "timestamp":"2018-10-24T17:17:50Z"}') is None
    assert lector.interpreta('{"tagInventoryEvent":{"epcHex":"3034abcd","antennaPort":2,"peakRssiCdbm":-4800}}').epc_hex == "3034ABCD"


def test_preset_compleix_esquema():
    p = lector.preset(lector.ConfigLector(url="https://x", ports=(1, 2)))
    a = p["antennaConfigs"][0]
    assert set(a) >= {"antennaPort", "transmitPowerCdbm", "inventorySession", "inventorySearchMode",
                      "estimatedTagPopulation", "rfMode"}
    assert a["transmitPowerCdbm"] % 25 == 0 and 1000 <= a["transmitPowerCdbm"] <= 3150


def test_agregador_finestres_i_filtre():
    t0 = datetime(2026, 11, 16, 11, 0, tzinfo=timezone.utc)
    ag = Agregador("R700-1", finestra_s=10, prefixos_epc=("30",))
    for s in range(15):
        ag.afegeix("30aa", 1, -50 - (s % 2), t0 + timedelta(seconds=s))
    ag.afegeix("E2ZZ", 1, -40, t0)  # un altre prefix: s'ignora
    tancades = ag.tanca(t0 + timedelta(seconds=15))
    assert len(tancades) == 1
    f = tancades[0]
    assert f["epc"] == "30AA" and f["antena"] == "R700-1:1" and f["n"] == 15
    assert f["rssi_max"] == -50 and f["rssi_mitja"] == -50.5


def test_cua_persisteix(tmp_path):
    ruta = str(tmp_path / "cua.db")
    Cua(ruta).afegeix("sensor", [{"cabina": "C1", "ts": "x", "tipus": "porta_tancada"}])
    ids, lot = Cua(ruta).lot()  # una altra instància: com si la Raspberry s'hagués reiniciat
    assert len(ids) == 1 and lot["sensors"][0]["cabina"] == "C1"


class _LectorFals(BaseHTTPRequestHandler):
    """Imita l'API del R700: accepta el preset i l'inici, i serveix un flux de lectures."""
    rebut: list = []
    linies: list[str] = []

    def log_message(self, *a):
        pass

    def do_PUT(self):
        cos = self.rfile.read(int(self.headers["Content-Length"]))
        self.rebut.append(("PUT", self.path, json.loads(cos)))
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        cos = self.rfile.read(n) if n else b""
        self.rebut.append(("POST", self.path, json.loads(cos) if cos else None))
        self.send_response(204 if "lots" not in self.path else 200)
        self.end_headers()
        if "lots" in self.path:
            self.wfile.write(b'{"errors": []}')

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        for l in self.linies:
            self.wfile.write(l.encode() + b"\n")


def _servidor():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _LectorFals)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_punta_a_punta_lector_fals_fins_a_prova(con):
    """Lector (fals) -> client -> agregador -> plataforma -> motor de proves."""
    t0 = datetime(2026, 11, 16, 11, 0, 5, tzinfo=timezone.utc)
    epc_hex = "3034257BF7194E4000001A85"
    _LectorFals.linies = [json.dumps({"TagInventoryEvent": {"epcHex": epc_hex, "antennaPort": 1, "peakRssiCdbm": -5000},
                                      "timestamp": (t0 + timedelta(seconds=s)).isoformat().replace("+00:00", "Z")})
                          for s in range(0, 120, 2)]
    _LectorFals.rebut = []
    srv, url = _servidor()
    try:
        client = lector.ClientLector(lector.ConfigLector(url=url, ports=(1,)))
        ag = Agregador("R700-1")
        finestres = []
        for i, l in enumerate(client.lectures()):
            ag.afegeix(l.epc_hex, l.port, l.rssi_dbm, l.ts)
            finestres += ag.tanca(l.ts)
            if i == len(_LectorFals.linies) - 1:
                break
        finestres += ag.tanca(t0, tot=True)
        metodes = [(m, p) for m, p, _ in _LectorFals.rebut]
        assert ("PUT", "/api/v1/profiles/inventory/presets/hebra") in metodes
        assert ("POST", "/api/v1/profiles/inventory/presets/hebra/start") in metodes

        # La plataforma
        con.execute("INSERT INTO botiga (id, nom) VALUES ('B', 'B')")
        con.execute("INSERT INTO cabina (id, botiga_id, nom) VALUES ('C1', 'B', '1')")
        con.execute("INSERT INTO antena (id, cabina_id, port) VALUES ('R700-1:1', 'C1', 1)")
        sensors = [{"cabina": "C1", "ts": (t0 + timedelta(seconds=s)).isoformat(), "tipus": t}
                   for s, t in [(0, "porta_tancada"), (1, "presencia_si"), (130, "porta_oberta"), (133, "presencia_no")]]
        lot = {"lectures": finestres, "sensors": sensors}
        res = passarella.desa_lot(con, json.loads(json.dumps(lot)))
        assert res.errors == [] and res.lectures == len(finestres) >= 5
        assert proves.processa_cabina(con, "C1", ReglaProva()) == 1
        p = con.execute("SELECT epc, confianca FROM prova").fetchone()
        assert p["epc"] == "urn:epc:id:sgtin:0614141.812345.6789" and p["confianca"] == "alta"

        # I la cua sap enviar el lot a la plataforma (aquí, el mateix servidor fals).
        envia_lot(url, "clau", lot)
        assert _LectorFals.rebut[-1][1] == "/api/v1/lots"
    finally:
        srv.shutdown()
