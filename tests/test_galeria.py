"""v0.6: galeria de fotos a la fitxa NFC i color de fons de les fotos de producte."""

import base64
import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from hebra import fitxa, imatges, textos

from test_api import _client, entorn  # noqa: F401 — fixture compartida


def _foto(fons=(255, 255, 255), peca=(20, 30, 70), ple=False) -> bytes:
    im = Image.new("RGB", (800, 1000), peca if ple else fons)
    if not ple:
        ImageDraw.Draw(im).rectangle((150, 120, 650, 900), fill=peca)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=95)
    return out.getvalue()


def _data_url(b: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(b).decode()


def test_fons_nomes_per_a_fotos_de_producte():
    assert imatges.fons(_foto()) in ("#FFFFFF", "#FEFEFE", "#FFFEFF")
    assert imatges.fons(_foto(fons=(200, 200, 200))) == ""      # fons gris d'estudi: omple el marc
    assert imatges.fons(_foto(ple=True)) == ""                  # detall: la peça omple la foto
    assert imatges.fons(b"no") == ""


def test_galeria_api_i_fitxa(entorn):  # noqa: F811
    app_mod, con = entorn
    model = con.execute("SELECT model FROM catalog_sku ORDER BY rowid LIMIT 1").fetchone()["model"]
    c = _client(app_mod, "marca@hebra.cat")
    assert c.put(f"/api/v2/imatges/{model}", json={"data_url": _data_url(_foto())}).status_code == 200
    r1 = c.post(f"/api/v2/imatges/{model}/galeria", json={"data_url": _data_url(_foto(ple=True))})
    r2 = c.post(f"/api/v2/imatges/{model}/galeria", json={"data_url": _data_url(_foto(fons=(180, 170, 160)))})
    assert r1.status_code == r2.status_code == 200, r1.text
    assert _client(app_mod, "bcn@hebra.cat").post(f"/api/v2/imatges/{model}/galeria",
                                                  json={"data_url": _data_url(_foto())}).status_code == 403
    assert c.post("/api/v2/imatges/NO-EXISTEIX/galeria", json={"data_url": _data_url(_foto())}).status_code == 404
    fila = next(i for i in c.get("/api/v2/imatges").json()["imatges"] if i["model"] == model)
    assert [g["clau"] for g in fila["galeria"]] == [r1.json()["clau"], r2.json()["clau"]]
    publica = TestClient(app_mod.app)
    assert publica.get(r1.json()["url"]).headers["content-type"] == "image/jpeg"

    token = con.execute("""SELECT e.nfc_token FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                           WHERE k.model = ? LIMIT 1""", (model,)).fetchone()[0]
    html = publica.get(f"/p/{token}?b=BCN-01").text
    assert html.count('class="fx-foto') == 3 and "fx-sencera" in html and "1</span> / 3" in html
    assert r2.json()["url"].split("?")[0] in html
    assert f"<script>{fitxa.SCRIPT_SECCIONS}</script>" in html

    assert c.delete(f"/api/v2/imatges/{model}/galeria/{r1.json()['clau']}").json() == {"esborrada": True}
    assert publica.get(r1.json()["url"]).status_code == 404
    assert publica.get(f"/p/{token}?b=BCN-01").text.count('class="fx-foto') == 2


def test_maxim_de_fotos(entorn):  # noqa: F811
    _, con = entorn
    model = con.execute("SELECT model FROM catalog_sku ORDER BY rowid LIMIT 1").fetchone()["model"]
    for _ in range(imatges.MAX_GALERIA):
        imatges.afegeix_galeria(con, model, _foto())
    try:
        imatges.afegeix_galeria(con, model, _foto())
        raise AssertionError("n'hauria d'haver acceptat massa")
    except imatges.ErrorImatge as e:
        assert "com a màxim" in str(e)


def test_bandera():
    assert textos.bandera("fr") == "🇫🇷" and textos.bandera("F") == "" and textos.bandera(None) == ""
