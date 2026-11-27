"""Demo amb una peça real: el model de prova passa a ser un polo i l'enllaç NFC gravat continua funcionant."""

import importlib
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hebra import demo_peca

POLO = json.loads((Path(__file__).resolve().parent.parent / "dades" / "demo-polo.json").read_text(encoding="utf-8"))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "app.db"))
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    from hebra import simulador
    simulador.simula(app_mod.con, date(2026, 11, 16), setmanes=1)
    return TestClient(app_mod.app), app_mod.con


def test_el_mateix_enllac_obre_el_polo(client):
    c, con = client
    token = con.execute("""SELECT e.nfc_token FROM etiqueta e JOIN catalog_sku s ON s.gtin = e.gtin
                           WHERE s.model = 'CL-24-NAT' AND s.talla = 'M' LIMIT 1""").fetchone()[0]
    assert con.execute("SELECT 1 FROM imatge_peca WHERE model = 'CL-24-NAT'").fetchone()

    r = demo_peca.canvia(con, "CL-24-NAT", "PH4012-166", POLO, fet_a="pe", foto=None, botiga_id="BCN-01")
    assert r["model"] == "PH4012-166" and r["color"] == "Blau marí" and r["variants"] >= 1

    assert not con.execute("SELECT 1 FROM catalog_sku WHERE model = 'CL-24-NAT'").fetchone()
    k = con.execute("SELECT * FROM catalog_sku WHERE model = 'PH4012-166' AND talla = 'M'").fetchone()
    assert k["categoria"] == "polo" and k["preu_eur"] == 110
    assert json.loads(k["origen_json"])["etapes"][-1] == {"etapa": "confeccio", "pais": "PE", "actor": "Lacoste"}
    # La foto de la camisa ja no surt.
    assert not con.execute("SELECT 1 FROM imatge_peca WHERE model IN ('CL-24-NAT', 'PH4012-166')").fetchone()
    # Els altres models proposen combinar amb el codi nou.
    combina = [json.loads(f[0]).get("combina") or [] for f in con.execute("SELECT origen_json FROM catalog_sku")]
    assert not any("CL-24-NAT" in x for x in combina)

    html = c.get(f"/p/{token}?b=BCN-01&lang=es").text
    assert "Polo de piqué" in html and "Azul marino" in html and "Camisa de lino" not in html
    html_ca = c.get(f"/p/{token}?b=BCN-01").text
    assert "Polo de piqué" in html_ca and "Camisa de lli" not in html_ca

    # Els textos de la botiga de prova ja no parlen de la camisa.
    textos = " ".join(f[0] + f[1] for f in con.execute("SELECT titol, detall FROM tasca WHERE botiga_id = 'BCN-01'"))
    assert "camisa de lli" not in textos


def test_amb_foto_i_errors(client):
    _, con = client
    png = (Path(__file__).resolve().parent.parent / "dades" / "fotos-prova" / "JM-24-GRF.jpg").read_bytes()
    demo_peca.canvia(con, "CL-24-NAT", "PH4012-166", POLO, foto=png, botiga_id="BCN-01")
    assert con.execute("SELECT 1 FROM imatge_peca WHERE model = 'PH4012-166'").fetchone()
    with pytest.raises(demo_peca.ErrorPeca, match="CL-24-NAT"):
        demo_peca.canvia(con, "CL-24-NAT", "X", POLO)
    with pytest.raises(demo_peca.ErrorPeca, match="Ja hi ha"):
        demo_peca.canvia(con, "PH4012-166", "TX-26-IND", POLO)


def test_recarregar_el_lot_no_perd_el_polo(tmp_path):
    """v0.9: esborrar i tornar a carregar el lot de prova torna a posar el polo, amb les fotos i el mateix enllaç NFC."""
    from hebra import autenticitat, db, lot_prova
    con = db.connecta(str(tmp_path / "lot.db"))
    db.inicialitza(con)
    lot_prova.carrega(con, avui=date(2026, 11, 27))
    foto = (Path(__file__).resolve().parent.parent / "dades" / "fotos-prova" / "camisa.jpg")
    foto = foto if foto.exists() else next((Path(__file__).resolve().parent.parent / "dades" / "fotos-prova").glob("*.jpg"))
    demo_peca.canvia(con, "CL-24-NAT", "PH4012-166", POLO, fet_a="PE", foto=[foto.read_bytes()] * 2)
    abans = {r["talla"]: r["nfc_token"] for r in con.execute(
        "SELECT k.talla, e.nfc_token FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin WHERE k.model = 'PH4012-166'")}
    autenticitat.protegeix(con, "secret", "04A1B2C3D4E5F6", model="PH4012-166")
    uid_epc_talla = con.execute("""SELECT k.talla FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                                   WHERE e.nfc_uid IS NOT NULL""").fetchone()["talla"]

    lot_prova.esborra(con)
    assert not con.execute("SELECT 1 FROM catalog_sku WHERE model = 'PH4012-166'").fetchone()
    lot_prova.carrega(con, avui=date(2026, 11, 27))

    k = con.execute("SELECT * FROM catalog_sku WHERE model = 'PH4012-166' LIMIT 1").fetchone()
    assert k and k["categoria"] == "polo" and json.loads(k["origen_json"])["etapes"][-1]["pais"] == "PE"
    assert not con.execute("SELECT 1 FROM catalog_sku WHERE model = 'CL-24-NAT'").fetchone()
    despres = {r["talla"]: r["nfc_token"] for r in con.execute(
        "SELECT k.talla, e.nfc_token FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin WHERE k.model = 'PH4012-166'")}
    assert set(abans.items()) <= set(despres.items()) or abans == despres  # el mateix enllaç per talla
    assert con.execute("SELECT 1 FROM imatge_peca WHERE model = 'PH4012-166'").fetchone()
    assert con.execute("SELECT COUNT(*) FROM imatge_galeria WHERE model = 'PH4012-166'").fetchone()[0] == 1
    assert con.execute("""SELECT k.talla FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                          WHERE e.nfc_uid = '04A1B2C3D4E5F6'""").fetchone()["talla"] == uid_epc_talla

    assert demo_peca.oblida(con, "PH4012-166")
    lot_prova.esborra(con)
    lot_prova.carrega(con, avui=date(2026, 11, 27))
    assert con.execute("SELECT 1 FROM catalog_sku WHERE model = 'CL-24-NAT'").fetchone()
    con.close()


def test_peca_ja_convertida_es_pot_recordar(tmp_path):
    """Si el polo ja es va fer abans de v0.9, tornar a executar demo-peca només el recorda (no falla ni toca fotos)."""
    from hebra import db, imatges, lot_prova
    con = db.connecta(str(tmp_path / "lot.db"))
    db.inicialitza(con)
    lot_prova.carrega(con, avui=date(2026, 11, 27))
    demo_peca.canvia(con, "CL-24-NAT", "PH4012-166", POLO, fet_a="PE", desa=False)
    foto = next((Path(__file__).resolve().parent.parent / "dades" / "fotos-prova").glob("*.jpg")).read_bytes()
    imatges.desa(con, "PH4012-166", "", foto, font="pujada")
    con.commit()
    tokens = {r[0] for r in con.execute(
        "SELECT e.nfc_token FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin WHERE k.model = 'PH4012-166'")}
    r = demo_peca.canvia(con, "CL-24-NAT", "PH4012-166", POLO, fet_a="PE")
    assert r["ja_fet"]
    lot_prova.esborra(con)
    lot_prova.carrega(con, avui=date(2026, 11, 27))
    assert tokens == {r[0] for r in con.execute(
        "SELECT e.nfc_token FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin WHERE k.model = 'PH4012-166'")}
    assert con.execute("SELECT 1 FROM imatge_peca WHERE model = 'PH4012-166'").fetchone()
