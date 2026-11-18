"""Proves de la revisió tècnica: recàlcul incremental, entrada idempotent, seguretat de la fitxa NFC,
configuració de producció, sessions revocables, protecció contra SSRF i vendes sense duplicar."""

import importlib
import json
import urllib.error
from datetime import date

import pytest
from fastapi.testclient import TestClient

from hebra import auth, config, fitxa, passarella, proves, simulador, vendes
from hebra.integracions import http


@pytest.fixture
def entorn(tmp_path, monkeypatch):
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "rt.db"))
    monkeypatch.setenv("HEBRA_SECRET", "secret-de-prova")
    monkeypatch.setenv("HEBRA_CLAU_PASSARELLA", "clau")
    monkeypatch.setenv("HEBRA_FRONTEND_DIST", str(tmp_path / "no-hi-es"))
    monkeypatch.setattr(auth, "ITERACIONS", 1000)
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    con = app_mod.con
    simulador.simula(con, date(2026, 11, 16), setmanes=1)
    auth.crea_usuari(con, "bcn@hebra.cat", "BCN", "botiga", "contrasenya-bcn", "BCN-01")
    return app_mod, con


def _proves(con):
    return [tuple(r) for r in con.execute(
        """SELECT s.cabina_id, s.inici, p.gtin, p.epc, p.confianca FROM prova p JOIN sessio s ON s.id = p.sessio_id
           ORDER BY s.cabina_id, s.inici, p.epc, p.gtin""")]


# ---------------------------------------------------------------- recàlcul incremental

def test_incremental_dona_el_mateix_que_el_complet(entorn):
    app_mod, con = entorn
    regla = app_mod.cfg.regla
    proves.processa_botiga(con, "BCN-01", regla, tot=True)
    complet = _proves(con)
    assert complet
    proves.processa_botiga(con, "BCN-01", regla)          # no hi ha res de nou
    assert _proves(con) == complet
    proves.processa_botiga(con, "BCN-01", regla, tot=True)
    assert _proves(con) == complet


# ---------------------------------------------------------------- entrada de lots

def _lot(con, ref):
    antena = con.execute("SELECT id FROM antena LIMIT 1").fetchone()[0]
    return {"lectures": [{"epc": "3034257BF4000000000000AA", "antena": antena, "inici": "2026-11-20T10:00:00+01:00",
                          "fi": "2026-11-20T10:00:09+01:00", "n": 5, "rssi_max": -50, "rssi_mitja": -55, "ref": ref}]}


def test_lot_repetit_no_es_compta_dues_vegades(entorn):
    _, con = entorn
    abans = con.execute("SELECT COUNT(*) FROM lectura_agregada").fetchone()[0]
    r1 = passarella.desa_lot(con, _lot(con, "g1-1"))
    r2 = passarella.desa_lot(con, _lot(con, "g1-1"))
    assert (r1.lectures, r2.lectures, r2.repetits) == (1, 0, 1)
    assert con.execute("SELECT COUNT(*) FROM lectura_agregada").fetchone()[0] == abans + 1


def test_lot_amb_errors_es_rebutja_sencer_o_es_informa(entorn):
    _, con = entorn
    lot = _lot(con, "g1-2")
    lot["lectures"][0]["n"] = 0
    res = passarella.desa_lot(con, lot)
    assert res.lectures == 0 and res.errors


def test_senyal_de_vida_i_estat(entorn):
    _, con = entorn
    passarella.desa_lot(con, {"lectures": [], "passarella": {"id": "pi-1", "pendents": 3, "versio": "0.4",
                                                              "ara": "2026-01-01T00:00:00+00:00"}})
    est = passarella.estat(con)
    assert est and est[0]["id"] == "pi-1"
    assert est[0].get("alerta")  # rellotge molt desfasat


def test_lot_massa_gran_a_la_api(entorn):
    app_mod, _ = entorn
    c = TestClient(app_mod.app)
    r = c.post("/api/v1/lots", headers={"X-Hebra-Clau": "clau"},
               json={"lectures": [], "sensors": [{"cabina": "x"}] * (passarella.MAXIM_ELEMENTS + 1)})
    assert r.status_code == 413


# ---------------------------------------------------------------- configuració de producció

def test_produccio_no_arrenca_amb_claus_d_exemple(monkeypatch):
    monkeypatch.setenv("HEBRA_ENTORN", "produccio")
    monkeypatch.setenv("HEBRA_SECRET", "canvia-aquesta-clau")
    with pytest.raises(RuntimeError, match="HEBRA_SECRET"):
        config.carrega()


def test_produccio_accepta_claus_fortes(monkeypatch):
    monkeypatch.setenv("HEBRA_ENTORN", "produccio")
    monkeypatch.setenv("HEBRA_SECRET", "a" * 40)
    monkeypatch.setenv("HEBRA_CLAU_PASSARELLA", "b" * 30)
    monkeypatch.setenv("HEBRA_COOKIE_SECURE", "1")
    monkeypatch.delenv("HEBRA_CONTRASENYA_BOTIGA", raising=False)
    assert config.carrega().produccio


# ---------------------------------------------------------------- sessions

def test_canvi_de_contrasenya_tanca_les_altres_sessions(entorn):
    app_mod, _ = entorn
    dades = {"correu": "bcn@hebra.cat", "contrasenya": "contrasenya-bcn"}
    a, b = TestClient(app_mod.app), TestClient(app_mod.app)
    assert a.post("/api/v2/sessio", json=dades).status_code == 200
    assert b.post("/api/v2/sessio", json=dades).status_code == 200
    r = a.post("/api/v2/jo/contrasenya", json={"actual": "contrasenya-bcn", "nova": "una-altra-contrasenya"})
    assert r.status_code in (200, 204), r.text
    assert a.get("/api/v2/jo").status_code == 200       # la que l'ha canviada continua
    assert b.get("/api/v2/jo").status_code == 401       # l'altra ja no val
    assert a.post("/api/v2/jo/contrasenya", json={"actual": "incorrecta", "nova": "x" * 12}).status_code in (400, 401, 403)


def test_origen_estrany_es_rebutja(entorn):
    app_mod, _ = entorn
    c = TestClient(app_mod.app)
    r = c.post("/api/v2/sessio", headers={"Origin": "https://web-malvada.example"},
               json={"correu": "bcn@hebra.cat", "contrasenya": "contrasenya-bcn"})
    assert r.status_code == 403


def test_cos_massa_gran_es_rebutja(entorn):
    app_mod, _ = entorn
    c = TestClient(app_mod.app)
    r = c.post("/api/v2/sessio", content=b"x" * (13 * 1024 * 1024), headers={"content-type": "application/json"})
    assert r.status_code == 413


# ---------------------------------------------------------------- fitxa NFC pública

def _token(con):
    return con.execute("SELECT nfc_token FROM etiqueta LIMIT 1").fetchone()[0]


def test_fitxa_no_es_pot_indexar_ni_desar_a_la_memoria_cau(entorn):
    app_mod, con = entorn
    r = TestClient(app_mod.app).get(f"/p/{_token(con)}?b=BCN-01")
    assert r.status_code == 200
    assert "noindex" in r.headers["x-robots-tag"] and "no-store" in r.headers["cache-control"]


def test_fitxa_rebutja_sessio_i_botiga_manipulades(entorn):
    app_mod, con = entorn
    c = TestClient(app_mod.app)
    t = _token(con)
    assert c.post(f"/p/{t}/assistencia", data={"b": "BCN-01", "s": "<script>"}).status_code == 400
    assert c.post(f"/p/{t}/assistencia", data={"b": "NO-EXISTEIX", "s": "sessio-valida-1"}).status_code == 400


def test_assistencia_no_es_pot_repetir_sense_fi(entorn):
    app_mod, con = entorn
    c = TestClient(app_mod.app)
    t = _token(con)
    abans = con.execute("SELECT COUNT(*) FROM peticio_talla").fetchone()[0]
    for _ in range(6):   # mateixa visita: doble toc i insistència
        c.post(f"/p/{t}/assistencia", data={"b": "BCN-01", "s": "sessio-valida-1"}, follow_redirects=False)
    assert con.execute("SELECT COUNT(*) FROM peticio_talla").fetchone()[0] == abans + 1


def test_limit_per_botiga(entorn, monkeypatch):
    app_mod, con = entorn
    monkeypatch.setattr(fitxa, "MAX_PER_BOTIGA", 3)
    c = TestClient(app_mod.app)
    t = _token(con)
    ok = []
    for i in range(5):  # cada una és una visita diferent
        r = c.post(f"/p/{t}/assistencia", data={"b": "BCN-01", "s": f"visita-numero-{i}"}, follow_redirects=False)
        ok.append("ok=limit" in r.headers["location"])
    assert ok == [False, False, False, True, True]


# ---------------------------------------------------------------- SSRF

@pytest.mark.parametrize("url", ["https://127.0.0.1/x", "https://10.0.0.5/x", "https://169.254.169.254/latest",
                                 "https://[::1]/x", "http://exemple.cat/x", "file:///etc/passwd"])
def test_no_es_pot_fer_peticions_a_la_xarxa_interna(url):
    with pytest.raises(http.ErrorXarxa):
        http.comprova_desti(url)


def test_adreces_publiques_si(monkeypatch):
    monkeypatch.setattr(http, "_resol", lambda host: ["93.184.216.34"])
    http.comprova_desti("https://exemple.cat/fitxer.csv")


def test_un_nom_que_resol_a_una_adreca_interna_es_rebutja(monkeypatch):
    monkeypatch.setattr(http, "_resol", lambda host: ["192.168.1.10"])
    with pytest.raises(http.ErrorXarxa):
        http.comprova_desti("https://sembla-public.example/x.csv")


# ---------------------------------------------------------------- vendes

def test_pujar_dues_vegades_el_mateix_csv_no_duplica(entorn):
    _, con = entorn
    gtin = con.execute("SELECT gtin FROM catalog_sku LIMIT 1").fetchone()[0]
    csv = f"data_hora,botiga,gtin,quantitat,import,tiquet\n2026-11-30T12:00:00+01:00,BCN-01,{gtin},1,69.00,T-1\n"
    abans = con.execute("SELECT COUNT(*) FROM venda_linia").fetchone()[0]
    assert vendes.importa_csv_sense_repetir(con, csv)[0] == 1
    n, errors, repetides = vendes.importa_csv_sense_repetir(con, csv)
    assert (n, repetides) == (0, 1) and not errors
    assert con.execute("SELECT COUNT(*) FROM venda_linia").fetchone()[0] == abans + 1


# ---------------------------------------------------------------- passarel·la (Raspberry)

def test_cua_dona_ref_estable_i_el_lot_conte_el_senyal(tmp_path):
    from hebra_passarella.cua import Cua, senyal
    cua = Cua(str(tmp_path / "c.db"))
    cua.afegeix("lectura", [{"epc": "A"}, {"epc": "B"}])
    ids, lot = cua.lot()
    refs = [e["ref"] for e in lot["lectures"]]
    assert len(set(refs)) == 2 and all(r.startswith(cua.id + "-") for r in refs)
    assert Cua(str(tmp_path / "c.db")).id == cua.id        # la identitat sobreviu als reinicis
    assert senyal(cua)["pendents"] == 2


def test_un_element_dolent_no_bloqueja_la_cua(tmp_path, monkeypatch):
    import threading
    from hebra_passarella import cua as cua_mod
    cua = cua_mod.Cua(str(tmp_path / "c.db"))
    cua.afegeix("lectura", [{"epc": "BO-1"}, {"epc": "DOLENT"}, {"epc": "BO-2"}])
    rebuts = []
    atura = threading.Event()

    def falsa(url, clau, lot, timeout=20):
        epcs = [e["epc"] for e in lot["lectures"]]
        if "DOLENT" in epcs:
            raise urllib.error.HTTPError(url, 400, "dolent", {}, None)
        rebuts.extend(epcs)
        if cua.mida() == len(epcs):
            atura.set()
    monkeypatch.setattr(cua_mod, "envia_lot", falsa)
    monkeypatch.setattr(cua_mod.time, "sleep", lambda s: None)
    cua_mod.bucle_enviament(cua, "http://x", "k", atura=atura)
    assert sorted(rebuts) == ["BO-1", "BO-2"] and cua.mida() == 0


# ---------------------------------------------------------------- posada en producció

def test_claus_generades_passen_la_comprovacio(monkeypatch, tmp_path):
    from hebra import admin
    for linia in admin.claus().splitlines():
        if linia and not linia.startswith("#"):
            k, v = linia.split("=", 1)
            monkeypatch.setenv(k, v)
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "hebra.db"))
    errors, _ = admin.comprova_configuracio()
    assert errors == []


def test_comprova_detecta_la_configuracio_d_exemple(monkeypatch, tmp_path):
    from hebra import admin
    for k in ("HEBRA_ENTORN", "HEBRA_SECRET", "HEBRA_CLAU_PASSARELLA", "HEBRA_SAL_TIQUET", "HEBRA_COOKIE_SECURE"):
        monkeypatch.delenv(k, raising=False)
    errors, _ = admin.comprova_configuracio()
    assert len(errors) >= 4


def test_copia_de_seguretat_es_valida_i_es_roten(tmp_path):
    import sqlite3
    from hebra import admin
    bd = tmp_path / "hebra.db"
    c = sqlite3.connect(bd)
    c.execute("CREATE TABLE t (x)")
    c.execute("INSERT INTO t VALUES (42)")
    c.commit()
    c.close()
    carpeta = tmp_path / "copies"
    carpeta.mkdir()
    for i in range(3):
        (carpeta / f"hebra-2026-01-0{i + 1}_0300.db").write_bytes(b"vella")
    admin.copia(str(bd), str(carpeta), dies=2)
    fitxers = sorted(carpeta.glob("hebra-*.db"))
    assert len(fitxers) == 2
    assert sqlite3.connect(fitxers[-1]).execute("SELECT x FROM t").fetchone()[0] == 42
