"""v0.5: imatges de les peces (pujada, URL, silueta) i la fitxa NFC amb la peça i «Combina amb»."""

import base64
import io

from fastapi.testclient import TestClient
from PIL import Image

from hebra import fitxa, imatges, siluetes
from hebra.integracions import http

from test_api import _client, entorn  # noqa: F401 — fixture compartida


def _jpeg(w=1600, h=2000, color=(200, 180, 150), exif=True) -> bytes:
    im = Image.new("RGB", (w, h), color)
    out = io.BytesIO()
    kw = {}
    if exif:
        e = Image.Exif()
        e[0x010F] = "Camera de prova"  # Make
        kw["exif"] = e.tobytes()
    im.save(out, "JPEG", **kw)
    return out.getvalue()


def test_siluetes_familia_i_color():
    assert siluetes.familia("part de dalt", "Jersei de merino") == "jersei"
    assert siluetes.familia("part de baix", None) == "pantalo"
    assert siluetes.familia("vestit") == "vestit"
    assert siluetes.familia("???") == "peca"
    assert siluetes.color_hex("Blau nit") == "#1F2A44"
    assert siluetes.color_hex("amarillo") == "#DDB94B"   # no és «marí»
    assert siluetes.color_hex("#a1b2c3") == "#A1B2C3"
    assert siluetes.color_hex(None) == siluetes.PER_DEFECTE
    assert siluetes.svg("camisa", "Terra").startswith("<svg")


def test_normalitza_redimensiona_i_treu_exif():
    dades, mime = imatges.normalitza(_jpeg())
    im = Image.open(io.BytesIO(dades))
    assert mime == "image/jpeg" and max(im.size) == imatges.COSTAT_MAX
    assert not im.getexif()
    # PNG amb transparència es queda PNG
    png = io.BytesIO()
    Image.new("RGBA", (40, 50), (0, 0, 0, 0)).save(png, "PNG")
    assert imatges.normalitza(png.getvalue())[1] == "image/png"


def test_rebutja_no_imatges():
    for dolent in (b"", b"<svg></svg>", b"GIF89a....", b"\xff\xd8\xffnoesjpeg"):
        try:
            imatges.normalitza(dolent)
        except imatges.ErrorImatge:
            continue
        raise AssertionError(dolent)


def test_api_puja_serveix_i_esborra(entorn):  # noqa: F811
    app_mod, con = entorn
    model = con.execute("SELECT model, color FROM catalog_sku ORDER BY rowid LIMIT 1").fetchone()
    c = _client(app_mod, "marca@hebra.cat")
    assert _client(app_mod, "bcn@hebra.cat").get("/api/v2/imatges").status_code == 403
    llista = c.get("/api/v2/imatges").json()["imatges"]
    # El simulador desa la foto de prova de cada model de prova
    assert any(not i["silueta"] and i["font"] == "prova" for i in llista)
    con.execute("DELETE FROM imatge_peca")
    con.commit()
    llista = c.get("/api/v2/imatges").json()["imatges"]
    assert all(i["silueta"] for i in llista) and llista[0]["imatge"].startswith("/imatges/silueta/")
    r = c.get(llista[0]["imatge"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")

    data_url = "data:image/jpeg;base64," + base64.b64encode(_jpeg()).decode()
    r = c.put(f"/api/v2/imatges/{model['model']}", json={"data_url": data_url})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    img = TestClient(app_mod.app).get(url)  # pública, sense sessió (la fa servir la fitxa)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert "immutable" in img.headers["cache-control"]
    # La fitxa NFC ensenya la foto
    token = con.execute("""SELECT e.nfc_token FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                           WHERE k.model = ? LIMIT 1""", (model["model"],)).fetchone()[0]
    assert url.split("?")[0] in TestClient(app_mod.app).get(f"/p/{token}?b=BCN-01").text

    assert c.put("/api/v2/imatges/NO-EXISTEIX", json={"data_url": data_url}).status_code == 404
    assert c.put(f"/api/v2/imatges/{model['model']}", json={"data_url": "data:image/png;base64,AAAA"}).status_code == 400
    assert c.delete(f"/api/v2/imatges/{model['model']}").json() == {"esborrada": True}
    assert TestClient(app_mod.app).get(url).status_code == 404
    assert TestClient(app_mod.app).get("/imatges/silueta/res.svg").status_code == 404
    assert TestClient(app_mod.app).get("/imatges/silueta/camisa.svg?c=zz").status_code == 404


def test_imatge_des_de_url_amb_proteccio(entorn, monkeypatch):  # noqa: F811
    app_mod, con = entorn
    model = con.execute("SELECT model FROM catalog_sku LIMIT 1").fetchone()[0]
    try:
        imatges.des_de_url(con, model, "", "http://127.0.0.1/foto.jpg")
        raise AssertionError("ha d'aturar les adreces internes")
    except imatges.ErrorImatge:
        pass
    monkeypatch.setattr(http, "comprova_desti", lambda url: None)
    monkeypatch.setattr(http, "peticio", lambda *a, **k: http.Resposta(200, {}, _jpeg(300, 400)))
    r = imatges.des_de_url(con, model, "", "https://botiga.example/foto.jpg")
    assert r["font"] == "url"
    assert con.execute("SELECT url_origen FROM imatge_peca WHERE model = ?", (model,)).fetchone()[0].startswith("https://")


def test_combina_automatic_des_del_provador(entorn):  # noqa: F811
    app_mod, con = entorn
    from datetime import date

    from hebra import simulador
    simulador.simula(con, date.fromisoformat(fitxa.temps.ara()[:10]), setmanes=2)
    # Sense «combina» de la marca: la fitxa proposa el que més es prova junt a la cabina
    con.execute("UPDATE catalog_sku SET origen_json = json_remove(origen_json, '$.combina')")
    con.execute("DELETE FROM contingut_model")
    con.commit()
    model = "CL-24-NAT"  # camisa de lli del fitxer de prova
    auto = fitxa.provat_amb(con, model)
    assert auto and model not in auto
    peca = con.execute("""SELECT e.epc, e.nfc_token, k.* FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                          WHERE k.model = ? LIMIT 1""", (model,)).fetchone()
    d = fitxa.dades_fitxa(con, peca, "BCN-01", "es")
    assert [c["model"] for c in d["combina"]] == auto
    assert d["nota_combina"] == fitxa.NOTA_COMBINA_PROVADOR["es"]
    assert not d["imatge"]["silueta"] and d["imatge"]["url"].startswith("/imatges/peca/")  # foto de prova
    assert all(c["imatge"]["url"].startswith("/imatges/") for c in d["combina"])


def test_panorama():
    import tempfile
    from datetime import date

    from hebra import analitica, db, simulador
    c = db.connecta(tempfile.mktemp())
    db.inicialitza(c)
    simulador.simula(c, date(2026, 11, 16), setmanes=2)
    f = analitica.Filtre(None, date(2026, 11, 3), date(2026, 11, 16))
    p = analitica.panorama(c, f)
    assert [e["clau"] for e in p["embut"]] == ["tocs", "proves", "peticions", "compres"]
    proves = p["embut"][1]["n"]
    assert proves > 0 and p["embut"][3]["n"] <= proves
    assert sum(map(sum, p["mapa_calor"]["proves"])) <= proves and len(p["mapa_calor"]["proves"]) == 7
    assert sum(r["proves"] for r in p["per_categoria"]) == proves
    assert sum(t["sessions"] for t in p["temps_cabina"]["trams"]) == sum(s["sessions"] for s in p["peces_per_sessio"])
    peca = p["peces"][0]
    assert peca["imatge"].startswith("/imatges/") and len(peca["serie"]) == len(p["dies"]) == 14
    assert sum(peca["serie"]) == peca["proves"]


def test_fotos_prova_per_a_dades_antigues(entorn):  # noqa: F811
    """Dades de prova d'abans de la v0.5 (sense fotos): en arrencar es desen les fotos reals de les peces."""
    _app, con = entorn
    from hebra import imatges, simulador
    con.execute("DELETE FROM imatge_peca")
    con.commit()
    assert simulador.fotos_prova(con) >= 4
    assert simulador.fotos_prova(con) == 0  # no les torna a desar
    res = imatges.Resolutor(con)
    for m in ("CL-24-NAT", "JM-24-GRF", "VV-26-VRD", "TX-26-IND"):
        assert not res.de(m, None, None)["silueta"]
    # la marca hi ha posat la seva: no es toca
    con.execute("DELETE FROM imatge_peca WHERE model = 'CL-24-NAT'")
    imatges.desa(con, "CL-24-NAT", "Natural", _jpeg(), font="pujada")
    assert simulador.fotos_prova(con) == 0
