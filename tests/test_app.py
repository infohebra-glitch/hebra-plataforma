"""Prova de punta a punta: simulació + pàgines web."""

import importlib
from datetime import date

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "app.db"))
    monkeypatch.setenv("HEBRA_CLAU_PASSARELLA", "clau")
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    from hebra import simulador
    simulador.simula(app_mod.con, date(2026, 11, 16), setmanes=1)
    return TestClient(app_mod.app), app_mod.con


AUTH = ("botiga", "hebra")


def test_fitxa_nfc_sense_galetes(client):
    c, con = client
    token = con.execute("SELECT nfc_token FROM etiqueta LIMIT 1").fetchone()[0]
    for lang in ("ca", "es", "fr", "en"):
        r = c.get(f"/p/{token}?b=BCN-01&lang={lang}")
        assert r.status_code == 200
        assert "set-cookie" not in r.headers
    assert c.get("/p/no-existeix").status_code == 404


def test_flux_peticio_talla(client):
    c, con = client
    fila = con.execute("SELECT e.nfc_token, k.model, k.color, k.gtin FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin LIMIT 1").fetchone()
    altra = con.execute("SELECT gtin FROM catalog_sku WHERE model = ? AND gtin != ? LIMIT 1", (fila["model"], fila["gtin"])).fetchone()[0]
    abans = con.execute("SELECT COUNT(*) FROM peticio_talla").fetchone()[0]
    r = c.post(f"/p/{fila['nfc_token']}/talla", data={"gtin": altra, "b": "BCN-01", "lang": "ca", "s": "sessio1"},
               follow_redirects=False)
    assert r.status_code == 303
    assert con.execute("SELECT COUNT(*) FROM peticio_talla").fetchone()[0] == abans + 1
    assert c.get("/botiga/peticions").status_code == 401
    assert c.get("/botiga/peticions", auth=AUTH).status_code == 200


def test_motiu_no_valid(client):
    c, con = client
    token = con.execute("SELECT nfc_token FROM etiqueta LIMIT 1").fetchone()[0]
    r = c.post(f"/p/{token}/motiu", data={"motiu": "<script>", "s": "x", "b": "BCN-01"})
    assert r.status_code == 400


def test_informe(client):
    c, _ = client
    r = c.get("/botiga/informe?b=BCN-01&setmana=2026-11-16", auth=AUTH)
    assert r.status_code == 200 and "Provat, venut, convertit" in r.text


def test_api_passarella_demana_clau(client):
    c, _ = client
    assert c.post("/api/v1/lots", json={}).status_code == 401
    r = c.post("/api/v1/lots", headers={"X-Hebra-Clau": "clau"},
               json={"sensors": [{"cabina": "BCN-01-C1", "ts": "2026-11-23T10:00:00Z", "tipus": "porta_tancada"}]})
    assert r.json() == {"lectures": 0, "sensors": 1, "errors": []}
    assert c.post("/api/v1/processa?botiga=BCN-01", headers={"X-Hebra-Clau": "clau"}).status_code == 200
