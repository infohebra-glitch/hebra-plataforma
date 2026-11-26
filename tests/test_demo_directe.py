"""Demo en directe: una sessió de cabina enviada pel camí de la passarel·la, sense lector."""

import importlib
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from hebra import demo_directe, provadors


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "app.db"))
    monkeypatch.setenv("HEBRA_CLAU_PASSARELLA", "clau")
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    from hebra import simulador
    simulador.simula(app_mod.con, date(2026, 11, 16), setmanes=1)
    return TestClient(app_mod.app), app_mod.con


def test_enllacos_un_per_model(client):
    _, con = client
    e = demo_directe.enllacos(con, "BCN-01", "https://plataforma.exemple/")
    models = [x["model"] for x in e]
    assert models and len(models) == len(set(models))
    assert all(x["url"].startswith("https://plataforma.exemple/p/") and x["url"].endswith("?b=BCN-01") for x in e)


def test_sessio_en_directe_ocupa_la_cabina_i_crea_una_prova(client):
    c, con = client
    rellotge = [datetime(2026, 11, 26, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))]

    def espera(s):
        rellotge[0] += timedelta(seconds=s)

    def envia(cami, cos):
        r = c.post(cami, json=cos, headers={"X-Hebra-Clau": "clau"}) if cos is not None else \
            c.post(cami, headers={"X-Hebra-Clau": "clau"})
        assert r.status_code == 200, r.text
        return r.json()

    estats = []

    def diu(text):
        if "dins la cabina" in text:
            d = provadors.directe(con, "BCN-01", ara=rellotge[0].isoformat())
            c1 = next(x for x in d["cabines"] if x["cabina_id"] == "BCN-01-C1")
            estats.append(c1)

    proves_abans = con.execute("SELECT COUNT(*) FROM prova").fetchone()[0]
    res = demo_directe.executa(con, "BCN-01", "1", [], 2, envia, espera=espera, ara=lambda: rellotge[0], diu=diu)

    assert res["cabina"] == "BCN-01-C1" and len(res["peces"]) == 2 and res["lots"] == 12 + 2
    assert estats and estats[-1]["estat"] == "ocupada"
    assert len(estats[-1]["peces"]) == 2
    # En acabar, la sessió ja és una prova de cada peça.
    assert con.execute("SELECT COUNT(*) FROM prova").fetchone()[0] >= proves_abans + 2
    d = provadors.directe(con, "BCN-01", ara=(rellotge[0] + timedelta(seconds=30)).isoformat())
    assert next(x for x in d["cabines"] if x["cabina_id"] == "BCN-01-C1")["estat"] == "lliure"


def test_errors_clars(client):
    _, con = client
    with pytest.raises(demo_directe.ErrorDemo, match="botiga"):
        demo_directe.executa(con, "NO-01", "1", [], 1, lambda *_: {}, espera=lambda s: None)
    with pytest.raises(demo_directe.ErrorDemo, match="cabina"):
        demo_directe.executa(con, "BCN-01", "9", [], 1, lambda *_: {}, espera=lambda s: None)
    with pytest.raises(demo_directe.ErrorDemo, match="model"):
        demo_directe.executa(con, "BCN-01", "1", ["No existeix"], 1, lambda *_: {}, espera=lambda s: None)
