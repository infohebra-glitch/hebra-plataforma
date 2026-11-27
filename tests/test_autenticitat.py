"""v0.8: peça original o imitació (xip NTAG 424 DNA, verificació SUN)."""

import importlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from hebra import auth, autenticitat


def test_vector_de_nxp_an12196():
    # Exemple de l'AN12196 (claus a zero): PICCData xifrat i SDMMAC d'un toc real.
    clau = bytes(16)
    uid, ctr = autenticitat.desxifra_picc(clau, "EF963FF7828658A599F3041510671E88")
    assert uid.hex().upper() == "04DE5F1EACC040" and ctr == 61
    assert autenticitat.signatura(clau, uid, ctr).hex().upper() == "94EED9EE65337086"
    assert autenticitat.desxifra_picc(clau, "00" * 16) is None  # no comença per C7
    assert autenticitat.desxifra_picc(clau, "no-hex") is None


@pytest.fixture
def entorn(tmp_path, monkeypatch):
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "aut.db"))
    monkeypatch.setenv("HEBRA_SECRET", "secret-de-prova")
    monkeypatch.setenv("HEBRA_CLAU_PASSARELLA", "clau")
    monkeypatch.setenv("HEBRA_FRONTEND_DIST", str(tmp_path / "no-hi-es"))
    monkeypatch.setattr(auth, "ITERACIONS", 1000)
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    from hebra import simulador
    con = app_mod.con
    simulador.prepara_botiga(con)
    simulador._peces_fisiques(con, per_sku=1)
    return app_mod, con, app_mod.cfg.secret


def _peca(con):
    return con.execute("""SELECT e.epc, e.nfc_token FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                          WHERE k.model = 'CL-24-NAT' ORDER BY e.rowid LIMIT 1""").fetchone()


def _toc(con, secret, epc):
    """El que enviaria el xip real: el mateix càlcul amb les claus que la plataforma ha donat per gravar-lo."""
    fila = con.execute("SELECT nfc_uid FROM etiqueta WHERE epc = ?", (epc,)).fetchone()
    m = autenticitat.clau_mestra(con, secret)
    uid = bytes.fromhex(fila["nfc_uid"])
    return lambda ctr: (autenticitat.xifra_picc(autenticitat.clau_meta(m), uid, ctr),
                        autenticitat.signatura(autenticitat.clau_fitxer(m, uid), uid, ctr).hex())


def test_xip_real_original_copia_i_adhesiu_copiat(entorn):
    app_mod, con, secret = entorn
    p = _peca(con)
    r = autenticitat.protegeix(con, secret, "04:A1:B2:C3:D4:E5:F6", epc=p["epc"])
    assert len(r["clau_meta"]) == 32 and len(r["clau_fitxer"]) == 32 and r["uid"] == "04A1B2C3D4E5F6"
    toc = _toc(con, secret, p["epc"])
    c = TestClient(app_mod.app)

    picc, cmac = toc(1)
    r1 = c.get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca&picc={picc}&cmac={cmac}", follow_redirects=False)
    assert r1.status_code == 303 and "picc" not in r1.headers["location"]  # l'enllaç net, sense la signatura
    html = c.get(r1.headers["location"]).text
    assert "Peça original verificada" in html
    # Canviar d'idioma dins la mateixa visita manté el resultat (no torna a gastar el comptador).
    assert "Prenda original verificada" in c.get(r1.headers["location"].replace("lang=ca", "lang=es")).text

    # Algú copia l'enllaç signat i el grava en un altre adhesiu: el comptador ja s'ha vist.
    html = c.get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca&picc={picc}&cmac={cmac}").text
    assert "No hem pogut verificar" in html and "original verificada" not in html
    # Adhesiu normal amb l'enllaç fix d'aquesta peça: no porta signatura.
    assert "No hem pogut verificar" in c.get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca").text
    # Signatura falsificada.
    picc2, _ = toc(2)
    assert "No hem pogut verificar" in c.get(f"/p/{p['nfc_token']}?b=BCN-01&picc={picc2}&cmac={'0' * 16}").text
    # El toc següent del xip real torna a ser bo.
    picc3, cmac3 = toc(3)
    assert "Peça original verificada" in c.get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca&picc={picc3}&cmac={cmac3}").text
    estats = [f["valor"] for f in con.execute("SELECT valor FROM esdeveniment_nfc WHERE tipus = 'verificacio' ORDER BY id")]
    assert estats == ["original", "repetit", "sense_signatura", "no_verificada", "original"]


def test_xip_d_una_altra_peca_no_val(entorn):
    app_mod, con, secret = entorn
    a, b = con.execute("SELECT epc, nfc_token FROM etiqueta ORDER BY rowid LIMIT 2").fetchall()
    autenticitat.protegeix(con, secret, "04000000000001", epc=a["epc"])
    autenticitat.protegeix(con, secret, "04000000000002", epc=b["epc"])
    picc, cmac = _toc(con, secret, a["epc"])(1)
    html = TestClient(app_mod.app).get(f"/p/{b['nfc_token']}?b=BCN-01&lang=ca&picc={picc}&cmac={cmac}").text
    assert "No hem pogut verificar" in html
    with pytest.raises(autenticitat.ErrorXip):
        autenticitat.protegeix(con, secret, "04000000000001", epc=b["epc"])  # un xip, una peça
    with pytest.raises(autenticitat.ErrorXip):
        autenticitat.protegeix(con, secret, "04AA", epc=b["epc"])


def test_peca_sense_xip_no_diu_res(entorn):
    app_mod, con, _ = entorn
    p = _peca(con)
    html = TestClient(app_mod.app).get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca").text
    assert "original verificada" not in html and "No hem pogut verificar" not in html


def test_toc_simulat_per_a_la_demo(entorn):
    app_mod, con, secret = entorn
    p = _peca(con)
    c = TestClient(app_mod.app)
    t1 = autenticitat.toc_simulat(con, secret, epc=p["epc"])
    t2 = autenticitat.toc_simulat(con, secret, epc=p["epc"])  # dos enllaços seguits: comptadors diferents
    assert t2["comptador"] == t1["comptador"] + 1
    # L'adhesiu normal de la demo continua sense avís: el xip és simulat.
    assert "No hem pogut verificar" not in c.get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca").text
    url = f"/p/{p['nfc_token']}?b=BCN-01&lang=ca&picc={t2['picc']}&cmac={t2['cmac']}"
    assert "Peça original verificada" in c.get(url).text
    assert "No hem pogut verificar" in c.get(url).text  # el mateix enllaç dues vegades
    # El primer enllaç (comptador més baix) ja no val després del segon.
    assert "No hem pogut verificar" in c.get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca&picc={t1['picc']}&cmac={t1['cmac']}").text


def test_clau_mestra_xifrada_i_estable(entorn):
    _, con, secret = entorn
    m = autenticitat.clau_mestra(con, secret)
    assert autenticitat.clau_mestra(con, secret) == m
    desada = con.execute("SELECT valor FROM parametre WHERE clau = 'nfc_clau_mestra'").fetchone()["valor"]
    assert m.hex() not in desada.lower()


def test_robots_no_gasten_el_comptador(entorn):
    app_mod, con, secret = entorn
    p = _peca(con)
    autenticitat.protegeix(con, secret, "04A1B2C3D4E5F6", epc=p["epc"])
    picc, cmac = _toc(con, secret, p["epc"])(1)
    url = f"/p/{p['nfc_token']}?b=BCN-01&lang=ca&picc={picc}&cmac={cmac}"
    TestClient(app_mod.app).get(url, headers={"user-agent": "WhatsApp/2.23"})
    assert "Peça original verificada" in TestClient(app_mod.app).get(url).text
