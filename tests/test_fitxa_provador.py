"""v0.8: la fitxa NFC té un mode dins del provador i un altre fora.

Dins (el lector té la peça ara mateix dins d'una cabina): demanar talla, avisar el dependent amb la cabina
ja posada i dir per què no te l'emportes. Fora (botiga, carrer o casa): només informació.
Una botiga sense lectors de cabina ho ensenya tot, com abans.
"""

import importlib
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from hebra import auth, fitxa, temps


@pytest.fixture
def entorn(tmp_path, monkeypatch):
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "v8.db"))
    monkeypatch.setenv("HEBRA_SECRET", "secret-de-prova")
    monkeypatch.setenv("HEBRA_CLAU_PASSARELLA", "clau")
    monkeypatch.setenv("HEBRA_FRONTEND_DIST", str(tmp_path / "no-hi-es"))
    monkeypatch.setattr(auth, "ITERACIONS", 1000)
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    from hebra import simulador
    con = app_mod.con
    simulador.prepara_botiga(con)
    con.execute("INSERT INTO botiga (id, nom) VALUES ('GIR-01', 'Girona')")  # sense lectors de cabina
    simulador._peces_fisiques(con, per_sku=1)
    auth.crea_usuari(con, "marca@hebra.cat", "Marca", "marca", "contrasenya-marca")
    return app_mod, con


def _peca(con):
    return con.execute("""SELECT e.nfc_token, e.epc, k.* FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                          WHERE k.model = 'CL-24-NAT' ORDER BY k.rowid LIMIT 1""").fetchone()


def _ara():
    return datetime.fromisoformat(temps.ara())


def _lectura(con, epc, fa_s=10, cabina="BCN-01-C2", rssi=-45):
    antena = con.execute("SELECT id, llindar_rssi FROM antena WHERE cabina_id = ? ORDER BY id LIMIT 1",
                         (cabina,)).fetchone()["id"]
    fi = _ara() - timedelta(seconds=fa_s)
    con.execute("INSERT INTO lectura_agregada (epc, antena_id, inici, fi, n_lectures, rssi_max, rssi_mitja) "
                "VALUES (?, ?, ?, ?, 10, ?, ?)",
                (epc, antena, (fi - timedelta(seconds=10)).isoformat(timespec="seconds"),
                 fi.isoformat(timespec="seconds"), rssi + 3, rssi))
    con.commit()


def _darrer_toc(con):
    return con.execute("SELECT valor FROM esdeveniment_nfc WHERE tipus = 'obre_fitxa' ORDER BY id DESC LIMIT 1"
                       ).fetchone()["valor"]


def test_fora_del_provador_nomes_informacio(entorn):
    app_mod, con = entorn
    p = _peca(con)
    assert fitxa.on_es_peca(con, p["epc"], "BCN-01") == {"mode": "fora", "cabina": None}
    html = TestClient(app_mod.app).get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca").text
    assert "Composició" in html
    assert f'action="/p/{p["nfc_token"]}/talla"' not in html
    assert f'action="/p/{p["nfc_token"]}/assistencia"' not in html
    assert f'action="/p/{p["nfc_token"]}/motiu"' not in html
    assert "<nav class=\"fx-accions" not in html and "Ets al provador" not in html
    assert _darrer_toc(con) == "fora"


def test_dins_del_provador_amb_la_cabina_posada(entorn):
    app_mod, con = entorn
    p = _peca(con)
    _lectura(con, p["epc"])
    assert fitxa.on_es_peca(con, p["epc"], "BCN-01") == {"mode": "dins", "cabina": "Cabina 2"}
    c = TestClient(app_mod.app)
    html = c.get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca").text
    assert "Ets al provador (Cabina 2)" in html
    assert f'action="/p/{p["nfc_token"]}/talla"' in html and f'action="/p/{p["nfc_token"]}/motiu"' in html
    assert '<input type="hidden" name="cabina" value="Cabina 2">' in html
    assert 'placeholder="Cabina (opcional)"' not in html
    assert _darrer_toc(con) == "dins"
    # L'avís arriba al dependent amb la cabina, sense que el client l'escrigui.
    r = c.post(f"/p/{p['nfc_token']}/assistencia", data={"cabina": "Cabina 2", "b": "BCN-01", "lang": "ca",
                                                         "s": "sessio-prova-1"}, follow_redirects=False)
    assert r.status_code == 303
    assert con.execute("SELECT cabina FROM peticio_talla ORDER BY id DESC LIMIT 1").fetchone()["cabina"] == "Cabina 2"


def test_surt_del_provador(entorn):
    _, con = entorn
    p = _peca(con)
    _lectura(con, p["epc"], fa_s=30)
    assert fitxa.on_es_peca(con, p["epc"], "BCN-01")["mode"] == "dins"
    # El sensor diu que la cabina s'ha buidat després de l'última lectura: la peça ja és fora.
    con.execute("INSERT INTO sensor_event (cabina_id, ts, tipus) VALUES ('BCN-01-C2', ?, 'presencia_no')",
                ((_ara() - timedelta(seconds=5)).isoformat(timespec="seconds"),))
    con.commit()
    assert fitxa.on_es_peca(con, p["epc"], "BCN-01")["mode"] == "fora"


def test_lectura_antiga_o_feble_no_compta(entorn):
    _, con = entorn
    p = _peca(con)
    _lectura(con, p["epc"], fa_s=fitxa.FINESTRA_DINS_S + 30)
    assert fitxa.on_es_peca(con, p["epc"], "BCN-01")["mode"] == "fora"
    _lectura(con, p["epc"], fa_s=5, rssi=-80)  # per sota del llindar: la peça és al passadís, no a la cabina
    assert fitxa.on_es_peca(con, p["epc"], "BCN-01")["mode"] == "fora"
    # Una altra botiga no compta.
    _lectura(con, p["epc"], fa_s=5)
    assert fitxa.on_es_peca(con, p["epc"], "GIR-01")["mode"] == "sempre"
    assert fitxa.on_es_peca(con, p["epc"], None)["mode"] == "fora"


def test_botiga_sense_lectors_de_cabina_ho_ensenya_tot(entorn):
    app_mod, con = entorn
    p = _peca(con)
    html = TestClient(app_mod.app).get(f"/p/{p['nfc_token']}?b=GIR-01&lang=ca").text
    assert f'action="/p/{p["nfc_token"]}/talla"' in html and 'placeholder="Cabina (opcional)"' in html
    assert "Ets al provador" not in html


def test_previsualitza_els_dos_modes(entorn):
    app_mod, con = entorn
    c = TestClient(app_mod.app)
    assert c.post("/api/v2/sessio", json={"correu": "marca@hebra.cat", "contrasenya": "contrasenya-marca"}).status_code == 200
    dins = c.get("/api/v2/fitxa/previsualitza?model=CL-24-NAT&botiga=BCN-01&idioma=ca&mode=dins").text
    fora = c.get("/api/v2/fitxa/previsualitza?model=CL-24-NAT&botiga=BCN-01&idioma=ca&mode=fora").text
    assert "Ets al provador (Cabina 2)" in dins and "Previsualització dins del provador" in dins
    assert "Ets al provador" not in fora and "/talla" not in fora and "Previsualització fora del provador" in fora
    assert "&amp;mode=fora" in fora or "&mode=fora" in fora  # els idiomes mantenen el mode
    assert c.get("/api/v2/fitxa/previsualitza?model=CL-24-NAT&mode=casa").status_code == 400
