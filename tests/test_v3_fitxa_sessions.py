"""v0.3, seccions A-C: fitxa configurable, assistència, altres botigues, provadors en directe i sessions."""

import base64
import importlib
import sqlite3
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from hebra import alertes, analitica, auth, db, fitxa, fitxa_config, provadors, temps


@pytest.fixture
def entorn(tmp_path, monkeypatch):
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "v3.db"))
    monkeypatch.setenv("HEBRA_SECRET", "secret-de-prova")
    monkeypatch.setenv("HEBRA_CLAU_PASSARELLA", "clau")
    monkeypatch.setenv("HEBRA_FRONTEND_DIST", str(tmp_path / "no-hi-es"))
    monkeypatch.setattr(auth, "ITERACIONS", 1000)
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    from hebra import simulador
    con = app_mod.con
    simulador.prepara_botiga(con)
    con.execute("INSERT INTO botiga (id, nom) VALUES ('GIR-01', 'Girona')")
    con.execute("INSERT INTO cabina (id, botiga_id, nom) VALUES ('GIR-01-C1', 'GIR-01', 'Cabina 1')")
    simulador._peces_fisiques(con, per_sku=1)
    auth.crea_usuari(con, "marca@hebra.cat", "Marca", "marca", "contrasenya-marca")
    auth.crea_usuari(con, "bcn@hebra.cat", "BCN", "botiga", "contrasenya-bcn", "BCN-01")
    provadors._darrera_publicacio.clear()
    return app_mod, con


def _client(app_mod, correu=None):
    c = TestClient(app_mod.app)
    if correu:
        r = c.post("/api/v2/sessio", json={"correu": correu, "contrasenya": f"contrasenya-{correu.split('@')[0]}"})
        assert r.status_code == 200, r.text
    return c


def _peca(con, model="CL-24-NAT"):
    return con.execute("""SELECT e.nfc_token, e.epc, k.* FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                          WHERE k.model = ? ORDER BY k.rowid LIMIT 1""", (model,)).fetchone()


# ---------------------------------------------------------------- A.1 Configuració


def test_config_general_botiga_i_efectiva(entorn):
    app_mod, _ = entorn
    c = _client(app_mod, "marca@hebra.cat")
    r = c.get("/api/v2/fitxa/config").json()
    assert r["botiga"] is None and r["general"] == r["efectiva"]
    assert r["general"]["seccions"]["ordre"] == list(fitxa_config.SECCIONS)
    assert r["general"]["accions"]["mostra_estoc"] == "disponibilitat"

    r = c.put("/api/v2/fitxa/config", json={"aparença": {"color_principal": "#aa0000", "nom_marca": "Lli"},
                                            "idiomes": ["es", "ca"]}).json()
    assert r["general"]["aparença"] == {"color_principal": "#AA0000", "logo_data_url": None, "nom_marca": "Lli"}
    assert r["general"]["idiomes"] == ["es", "ca"]

    r = c.put("/api/v2/fitxa/config?botiga=BCN-01",
              json={"seccions": {"ordre": ["origen", "talles"], "visibles": {"faq": False}},
                    "accions": {"mostra_estoc": "unitats"}}).json()
    assert r["botiga"] == {"seccions": {"ordre": ["origen", "talles"], "visibles": {"faq": False}},
                           "accions": {"mostra_estoc": "unitats"}}
    ef = r["efectiva"]
    assert ef["seccions"]["ordre"][:2] == ["origen", "talles"] and len(ef["seccions"]["ordre"]) == 6
    assert ef["seccions"]["visibles"]["faq"] is False and ef["seccions"]["visibles"]["cura"] is True
    assert ef["accions"]["mostra_estoc"] == "unitats" and ef["accions"]["demana_talla"] is True
    assert ef["aparença"]["nom_marca"] == "Lli"  # ve de la general
    assert c.get("/api/v2/fitxa/config?botiga=GIR-01").json()["botiga"] is None
    # Un objecte buit torna la botiga a la general.
    assert c.put("/api/v2/fitxa/config?botiga=BCN-01", json={}).json()["botiga"] is None


@pytest.mark.parametrize("cos", [
    {"aparença": {"color_principal": "verd"}},
    {"seccions": {"ordre": ["talles", "inventada"]}},
    {"seccions": {"ordre": ["talles", "talles"]}},
    {"motius": ["preu", "car"]},
    {"accions": {"mostra_estoc": "sempre"}},
    {"idiomes": []},
    {"idiomes": ["de"]},
    {"textos": {"benvinguda": {"xx": "hola"}}},
    {"aparença": {"logo_data_url": "https://exemple.cat/logo.png"}},
    {"aparença": {"logo_data_url": "data:image/png;base64," + base64.b64encode(b"x" * (101 * 1024)).decode()}},
    {"desconegut": 1},
])
def test_config_validacio(entorn, cos):
    app_mod, _ = entorn
    r = _client(app_mod, "marca@hebra.cat").put("/api/v2/fitxa/config", json=cos)
    assert r.status_code == 400 and r.json()["detail"]


def test_config_permisos_i_logo(entorn):
    app_mod, _ = entorn
    assert _client(app_mod, "bcn@hebra.cat").get("/api/v2/fitxa/config").status_code == 403
    assert TestClient(app_mod.app).get("/api/v2/fitxa/config").status_code == 401
    c = _client(app_mod, "marca@hebra.cat")
    assert c.get("/api/v2/fitxa/config?botiga=NO-HI-ES").status_code == 404
    logo = "data:image/png;base64," + base64.b64encode(b"\x89PNG petit").decode()
    r = c.put("/api/v2/fitxa/config", json={"aparença": {"logo_data_url": logo}})
    assert r.status_code == 200 and r.json()["efectiva"]["aparença"]["logo_data_url"] == logo


# ---------------------------------------------------------------- A.2 Contingut per model


def test_contingut_per_model(entorn):
    app_mod, _ = entorn
    c = _client(app_mod, "marca@hebra.cat")
    models = {m["model"]: m for m in c.get("/api/v2/fitxa/models").json()["models"]}
    assert models["CL-24-NAT"]["nom"] == "Camisa de lli" and models["CL-24-NAT"]["te_origen"] is True
    assert models["CL-24-NAT"]["idiomes_amb_contingut"] == []

    cos = {"nom": "Camisa Mar", "cura": ["Rentar a 30 °C"], "faq": [{"q": "Encongeix?", "a": "No."}],
           "guia_talles": "Si dubtes, agafa la petita.", "combina": ["TX-26-IND"]}
    assert c.put("/api/v2/fitxa/models/CL-24-NAT/ca", json=cos).json() == {"ok": True}
    d = c.get("/api/v2/fitxa/models/CL-24-NAT").json()
    assert d["contingut"]["ca"]["nom"] == "Camisa Mar" and d["origen"]["model"] == "CL-24-NAT"
    models = {m["model"]: m for m in c.get("/api/v2/fitxa/models").json()["models"]}
    assert models["CL-24-NAT"]["idiomes_amb_contingut"] == ["ca"] and models["CL-24-NAT"]["nom"] == "Camisa Mar"

    assert c.put("/api/v2/fitxa/models/CL-24-NAT/de", json=cos).status_code == 400
    assert c.put("/api/v2/fitxa/models/NO-HI-ES/ca", json=cos).status_code == 404
    assert c.get("/api/v2/fitxa/models/NO-HI-ES").status_code == 404
    assert c.put("/api/v2/fitxa/models/CL-24-NAT/ca", json={"faq": [{"q": "sense resposta"}]}).status_code == 400
    assert c.put("/api/v2/fitxa/models/CL-24-NAT/ca", json={"color": "x"}).status_code == 400
    assert c.put("/api/v2/fitxa/models/CL-24-NAT/ca", json={}).json() == {"ok": True}  # esborra
    assert c.get("/api/v2/fitxa/models/CL-24-NAT").json()["contingut"] == {}


# ---------------------------------------------------------------- Fitxa aplicant la configuració


def test_fitxa_aplica_configuracio(entorn):
    app_mod, con = entorn
    p = _peca(con)
    fitxa_config.desa(con, None, {"aparença": {"color_principal": "#123456", "nom_marca": "Marca Mar"},
                                  "idiomes": ["es", "ca"], "motius": ["preu", "nomes_mirava"],
                                  "textos": {"benvinguda": {"es": "Hola, bienvenida"}, "peu": {"ca": "Peu propi"}}})
    fitxa_config.desa(con, "BCN-01", {"seccions": {"ordre": ["cura", "talles"], "visibles": {"faq": False}},
                                      "accions": {"mostra_estoc": "unitats", "demana_assistencia": False}})
    fitxa_config.desa_contingut(con, "CL-24-NAT", "es", {"nom": "Camisa Mar", "guia_talles": "Talla justa."})
    c = TestClient(app_mod.app)
    r = c.get(f"/p/{p['nfc_token']}?b=BCN-01", headers={"accept-language": "fr-FR"})
    assert r.status_code == 200 and "set-cookie" not in r.headers
    html = r.text
    assert '<html lang="es">' in html  # el francès no s'ofereix: el primer idioma de la marca
    assert "Camisa Mar" in html and "Talla justa." in html and "Hola, bienvenida" in html
    assert "Marca Mar" in html and "--accent: #123456" in html
    assert 'hreflang="fr"' not in html and 'hreflang="ca"' in html
    assert html.index('data-seccio="cura"') < html.index('data-seccio="talles"')
    assert 'data-seccio="preguntes"' not in html
    assert 'value="nomes_mirava"' in html and 'value="talla"' not in html and "Solo miraba" in html
    assert "/assistencia" not in html
    assert " unidades" in html  # mostra_estoc = unitats
    assert f"<script>{fitxa.SCRIPT_SECCIONS}</script>" in html  # el hash de la CSP continua quadrant
    assert fitxa.HASH_SCRIPT in r.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    # En català, el nom torna al fitxer d'origen; el peu propi de la marca, sí.
    r = c.get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca&s=x")
    assert "Camisa de lli" in r.text and "Peu propi" in r.text
    # L'acció desactivada tampoc s'accepta per formulari.
    r = c.post(f"/p/{p['nfc_token']}/assistencia", data={"b": "BCN-01", "s": "x", "lang": "ca"})
    assert r.status_code == 400


def test_origen_visible_i_grup_de_control(entorn):
    app_mod, con = entorn
    p = _peca(con)
    c = TestClient(app_mod.app)
    avui = datetime.now().astimezone().date().isoformat()
    assert fitxa.dades_fitxa(con, p, "BCN-01", "ca")["mostra_origen"] is True
    con.execute("INSERT INTO assignacio (botiga_id, experiment, data, grup) VALUES ('BCN-01', 'origen', ?, 'sense')",
                (avui,))
    con.commit()
    assert fitxa.dades_fitxa(con, p, "BCN-01", "ca")["mostra_origen"] is False  # el control mana
    assert "Mostra el recorregut" not in c.get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca").text
    assert "Mostra el recorregut" in c.get(f"/p/{p['nfc_token']}?b=GIR-01&lang=ca").text
    fitxa_config.desa(con, "GIR-01", {"seccions": {"visibles": {"origen": False}}})
    assert fitxa.dades_fitxa(con, p, "GIR-01", "ca")["mostra_origen"] is False  # la marca l'amaga
    assert "Mostra el recorregut" not in c.get(f"/p/{p['nfc_token']}?b=GIR-01&lang=ca").text


def test_previsualitza_sense_esdeveniments(entorn):
    app_mod, con = entorn
    n = con.execute("SELECT COUNT(*) FROM esdeveniment_nfc").fetchone()[0]
    c = _client(app_mod, "marca@hebra.cat")
    r = c.get("/api/v2/fitxa/previsualitza?model=CL-24-NAT&botiga=BCN-01&idioma=es")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "Camisa de lino" in r.text and "Previsualització" in r.text
    assert "<script>" not in r.text and 'id="seccions"' not in r.text
    assert "/api/v2/fitxa/previsualitza?model=CL-24-NAT&botiga=BCN-01&idioma=ca" in r.text
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in r.headers["content-security-policy"]
    assert con.execute("SELECT COUNT(*) FROM esdeveniment_nfc").fetchone()[0] == n
    assert c.get("/api/v2/fitxa/previsualitza?model=NO-HI-ES").status_code == 404
    assert _client(app_mod, "bcn@hebra.cat").get("/api/v2/fitxa/previsualitza?model=CL-24-NAT").status_code == 403


# ---------------------------------------------------------------- A.4 Assistència i A.5 altres botigues


def test_migracio_tipus_idempotent(tmp_path):
    ruta = str(tmp_path / "antiga.db")
    con = sqlite3.connect(ruta)
    con.execute("""CREATE TABLE peticio_talla (id INTEGER PRIMARY KEY AUTOINCREMENT, sessio_nfc TEXT NOT NULL,
                   botiga_id TEXT NOT NULL, gtin_origen TEXT NOT NULL, gtin_demanat TEXT NOT NULL,
                   talla_demanada TEXT NOT NULL, cabina TEXT, estat TEXT NOT NULL DEFAULT 'pendent',
                   hora_peticio TEXT NOT NULL, hora_resolta TEXT, disponible INTEGER)""")
    con.execute("""INSERT INTO peticio_talla (sessio_nfc, botiga_id, gtin_origen, gtin_demanat, talla_demanada,
                   hora_peticio) VALUES ('s', 'B', '1', '2', 'M', '2026-11-01T10:00:00+01:00')""")
    con.commit()
    con.close()
    con = db.connecta(ruta)
    db.inicialitza(con)
    db.inicialitza(con)
    assert con.execute("SELECT tipus FROM peticio_talla").fetchone()[0] == "talla"
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("""INSERT INTO peticio_talla (sessio_nfc, botiga_id, gtin_origen, gtin_demanat, talla_demanada,
                       hora_peticio, tipus) VALUES ('s', 'B', '1', '1', '', 'x', 'altra')""")


def test_assistencia_des_de_la_fitxa(entorn):
    app_mod, con = entorn
    p = _peca(con)
    c = TestClient(app_mod.app)
    r = c.post(f"/p/{p['nfc_token']}/assistencia", data={"cabina": "Cabina 2", "b": "BCN-01", "lang": "ca", "s": "s1"},
               follow_redirects=False)
    assert r.status_code == 303 and "ok=assistencia" in r.headers["location"]
    assert "Ara ve algú a la cabina." in c.get(r.headers["location"]).text
    assert c.post(f"/p/{p['nfc_token']}/assistencia", data={"s": "s1"}).status_code == 400  # sense botiga
    fila = con.execute("SELECT * FROM peticio_talla WHERE tipus = 'assistencia'").fetchone()
    assert fila["gtin_demanat"] == fila["gtin_origen"] == p["gtin"] and fila["talla_demanada"] == ""
    ev = [e for e in alertes.bus.recents if e.tipus == "peticio"][-1]
    assert ev.dades["tipus"] == "assistencia" and ev.dades["id"] == fila["id"] and ev.dades["accio"] == "nova"

    cb = _client(app_mod, "bcn@hebra.cat")
    pet = cb.get("/api/v2/peticions").json()["peticions"]
    assert pet[0]["tipus"] == "assistencia" and pet[0]["talla"] == "" and pet[0]["altres_botigues"] == []
    assert cb.patch(f"/api/v2/peticions/{fila['id']}", json={"estat": "lliurada"}).json()["estat"] == "lliurada"
    # Una de talla per comparar: el servei compta les dues; la demanda perduda, només la de talla.
    altra = con.execute("SELECT gtin FROM catalog_sku WHERE model = ? AND gtin != ? LIMIT 1",
                        (p["model"], p["gtin"])).fetchone()[0]
    fitxa.demana_talla(con, "s2", "BCN-01", p["gtin"], altra, "ca", "C1")
    dia = date.fromisoformat(fila["hora_peticio"][:10])
    f = analitica.Filtre("BCN-01", dia, dia)
    s = analitica.servei(con, f)
    assert s["peticions"] == 2 and s["peticions_assistencia"] == 1
    assert len(analitica.base.peticions(con, f)) == 1
    assert analitica.resum(con, f)["kpi"]["peticions_talla"] == 1


def test_altres_botigues(entorn):
    app_mod, con = entorn
    p = _peca(con)
    altra = con.execute("SELECT gtin FROM catalog_sku WHERE model = ? AND gtin != ? LIMIT 1",
                        (p["model"], p["gtin"])).fetchone()[0]
    con.execute("INSERT INTO estoc VALUES ('BCN-01', ?, 0, 'x', 'csv')", (altra,))
    con.execute("INSERT INTO estoc VALUES ('GIR-01', ?, 3, 'x', 'csv')", (altra,))
    con.commit()
    pid = fitxa.demana_talla(con, "s", "BCN-01", p["gtin"], altra, "ca")
    pet = alertes.peticio(con, pid)
    assert pet["tipus"] == "talla" and pet["disponible"] is False
    assert pet["altres_botigues"] == [{"botiga_id": "GIR-01", "nom": "Girona", "unitats": 3}]
    con.execute("UPDATE estoc SET unitats = 2 WHERE botiga_id = 'BCN-01'")
    con.commit()
    pid2 = fitxa.demana_talla(con, "s", "BCN-01", p["gtin"], altra, "ca")
    assert alertes.peticio(con, pid2)["altres_botigues"] == []  # n'hi ha a la botiga


# ---------------------------------------------------------------- B. Provadors en directe


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def test_provadors_directe_i_flux(entorn):
    app_mod, con = entorn
    ara = datetime.fromisoformat(temps.ara())
    p = _peca(con)
    lot = {"sensors": [{"cabina": "BCN-01-C1", "ts": _iso(ara - timedelta(seconds=90)), "tipus": "porta_tancada"},
                       {"cabina": "BCN-01-C1", "ts": _iso(ara - timedelta(seconds=88)), "tipus": "presencia_si"},
                       {"cabina": "BCN-01-C2", "ts": _iso(ara - timedelta(seconds=300)), "tipus": "presencia_si"},
                       {"cabina": "BCN-01-C2", "ts": _iso(ara - timedelta(seconds=200)), "tipus": "porta_oberta"}],
           "lectures": [{"epc": p["epc"], "antena": "R700-1:1", "inici": _iso(ara - timedelta(seconds=s + 10)),
                         "fi": _iso(ara - timedelta(seconds=s)), "n": 8, "rssi_max": -45, "rssi_mitja": -50}
                        for s in (80, 40, 5)]
           # La veïna (C2) també la llegeix, més fluix: és de la C1.
           + [{"epc": p["epc"], "antena": "R700-1:2", "inici": _iso(ara - timedelta(seconds=15)),
               "fi": _iso(ara - timedelta(seconds=5)), "n": 5, "rssi_max": -55, "rssi_mitja": -57}]}
    fitxa.demana_assistencia(con, "s", "BCN-01", p["gtin"], "ca", "1")
    alertes.bus.recents.clear()
    r = TestClient(app_mod.app).post("/api/v1/lots", json=lot, headers={"X-Hebra-Clau": "clau"})
    assert r.status_code == 200 and not r.json()["errors"]
    evs = {e.dades["cabina_id"]: e for e in alertes.bus.recents if e.tipus == "cabina"}
    assert set(evs) == {"BCN-01-C1", "BCN-01-C2"} and evs["BCN-01-C1"].botiga_id == "BCN-01"

    d = _client(app_mod, "bcn@hebra.cat").get("/api/v2/provadors/directe").json()
    cab = {x["cabina_id"]: x for x in d["cabines"]}
    assert set(cab) == {"BCN-01-C1", "BCN-01-C2", "BCN-01-C3"}  # només la seva botiga
    c1 = cab["BCN-01-C1"]
    assert c1["estat"] == "ocupada" and c1["des_de"] == _iso(ara - timedelta(seconds=88))
    assert [x["epc"] for x in c1["peces"]] == [p["epc"]] and c1["peces"][0]["model"] == "CL-24-NAT"
    assert c1["peces"][0]["des_de"] == _iso(ara - timedelta(seconds=90))  # presència contínua
    assert c1["peticions_obertes"] == 1  # «1» ↔ «Cabina 1»
    assert cab["BCN-01-C2"]["estat"] == "porta_oberta" and cab["BCN-01-C2"]["peces"] == []
    assert cab["BCN-01-C3"]["estat"] == "sense_dades"
    assert set(c1["avui"]) == {"sessions", "proves", "durada_mitjana_s"}
    assert d["resum"]["ocupades"] == 2 and d["resum"]["lliures"] == 0
    assert evs["BCN-01-C1"].dades == c1 | {"avui": evs["BCN-01-C1"].dades["avui"]}

    # Com a molt un cop cada 5 s per cabina.
    alertes.bus.recents.clear()
    TestClient(app_mod.app).post("/api/v1/lots", json={"sensors": lot["sensors"][:1]}, headers={"X-Hebra-Clau": "clau"})
    assert not [e for e in alertes.bus.recents if e.tipus == "cabina"]

    cb = _client(app_mod, "bcn@hebra.cat")
    assert cb.get("/api/v2/provadors/directe?botiga=GIR-01").status_code == 403
    cm = _client(app_mod, "marca@hebra.cat")
    assert {x["botiga_id"] for x in cm.get("/api/v2/provadors/directe").json()["cabines"]} == {"BCN-01", "GIR-01"}
    assert TestClient(app_mod.app).get("/api/v2/provadors/directe").status_code == 401


# ---------------------------------------------------------------- C. Sessions


def _sessio(con, cabina, inici: datetime, minuts: int, peces: list[tuple[str, bool]]) -> None:
    """Una sessió amb proves de confiança alta; (gtin, comprada)."""
    sid = con.execute("INSERT INTO sessio (cabina_id, inici, fi) VALUES (?, ?, ?)",
                      (cabina, _iso(inici), _iso(inici + timedelta(minutes=minuts)))).lastrowid
    for i, (gtin, comprada) in enumerate(peces):
        pid = con.execute("""INSERT INTO prova (sessio_id, epc, gtin, durada_s, n_lectures, rssi_mitja, confianca)
                             VALUES (?, ?, ?, 120, 10, -50, 'alta')""", (sid, f"epc-{sid}-{i}", gtin)).lastrowid
        if comprada:
            vid = con.execute("""INSERT INTO venda_linia (botiga_id, ts, data, gtin, quantitat)
                                 VALUES ('BCN-01', ?, ?, ?, 1)""",
                              (_iso(inici + timedelta(minutes=minuts + 2)), inici.date().isoformat(), gtin)).lastrowid
            con.execute("INSERT INTO atribucio (prova_id, venda_id, regla) VALUES (?, ?, 'mateix_gtin_hora')", (pid, vid))


def test_sessions(entorn):
    app_mod, con = entorn
    g = {(k["model"], k["talla"]): k["gtin"] for k in con.execute("SELECT * FROM catalog_sku")}
    cam_s, cam_m = g[("CL-24-NAT", "S")], g[("CL-24-NAT", "M")]
    tx = next(v for (m, _), v in g.items() if m == "TX-26-IND")
    t0 = datetime.fromisoformat("2026-11-16T11:00:00+01:00")
    # 3 sessions camisa en S i M (+ texans); en dues es compra la M.
    for i, compra in enumerate([True, True, False]):
        _sessio(con, "BCN-01-C1", t0 + timedelta(hours=i), 4, [(cam_s, False), (cam_m, compra), (tx, False)])
    _sessio(con, "BCN-01-C2", t0, 1, [(cam_m, False)])                     # 1 peça, < 2 min
    _sessio(con, "BCN-01-C2", t0 + timedelta(hours=2), 12, [(tx, True)])   # > 10 min, amb compra
    con.execute("INSERT INTO sessio (cabina_id, inici, fi) VALUES ('BCN-01-C3', ?, ?)",
                ("2026-11-16T12:00:00+01:00", "2026-11-16T12:05:00+01:00"))  # sense proves: no compta
    con.commit()
    f = analitica.Filtre("BCN-01", date(2026, 11, 16), date(2026, 11, 16))
    s = analitica.sessions(con, f)
    assert s["kpi"] == {"sessions": 5, "peces_per_sessio_mitjana": 2.2, "peces_per_sessio_mediana": 3,
                        "durada_mitjana_s": round((3 * 240 + 60 + 720) / 5), "pct_sessions_amb_compra": 0.6,
                        "mostra_petita": True}
    trams = {r["peces"]: r for r in s["per_nombre_peces"]}
    assert list(trams) == ["1", "2", "3", "4", "5+"]
    assert trams["1"]["sessions"] == 2 and trams["1"]["amb_compra"] == 1 and trams["1"]["conversio_sessio"] == 0.5
    assert trams["3"] == {"peces": "3", "sessions": 3, "amb_compra": 2, "conversio_sessio": 0.667,
                          "unitats_comprades": 2, "mostra_petita": True}
    assert trams["5+"]["sessions"] == 0 and trams["5+"]["conversio_sessio"] is None

    [parell] = s["provades_juntes"]
    assert (parell["model_a"], parell["model_b"], parell["sessions"]) == ("CL-24-NAT", "TX-26-IND", 3)
    assert parell["lift"] == round(3 * 5 / (4 * 4), 2) and parell["conversio_conjunta"] == 0.0
    assert parell["conversio_alguna"] == 0.667 and parell["nom_a"] == "Camisa de lli"

    dubte = s["mateix_model_diferent_talla"]
    assert dubte["sessions"] == 3 and dubte["pct_sessions"] == 0.6
    assert dubte["parells_talla"] == [{"model": "CL-24-NAT", "nom": "Camisa de lli", "color": "Natural",
                                       "talles": "S+M", "sessions": 3, "comprada": {"S": 0, "M": 2, "cap": 1},
                                       "mostra_petita": True}]
    assert dubte["per_model"] == [{"model": "CL-24-NAT", "nom": "Camisa de lli", "sessions_dubte": 3,
                                   "pct_sessions_model": 0.75, "talla_mes_comprada": "M", "mostra_petita": True}]
    durada = {r["tram"]: r["sessions"] for r in s["per_durada"]}
    assert durada == {"<2 min": 1, "2-5 min": 3, "5-10 min": 0, ">10 min": 1}
    assert [r["hora"] for r in s["per_hora"]] == [11, 12, 13]

    det = analitica.model_detall(con, f, "CL-24-NAT")["dubte_talla"]
    assert det["sessions"] == 3 and det["sessions_model"] == 4 and det["talla_mes_comprada"] == "M"
    assert det["parells_talla"][0]["talles"] == "S+M" and "model" not in det["parells_talla"][0]
    assert analitica.model_detall(con, f, "JM-24-GRF")["dubte_talla"] is None  # no s'ha provat

    r = _client(app_mod, "bcn@hebra.cat").get("/api/v2/sessions?des=2026-11-16&fins=2026-11-16")
    assert r.status_code == 200 and r.json()["kpi"]["sessions"] == 5


def test_simulador_genera_novetats(tmp_path):
    from hebra import simulador
    con = db.connecta(str(tmp_path / "sim.db"))
    db.inicialitza(con)
    simulador.simula(con, date(2026, 11, 16), setmanes=1)
    f = analitica.Filtre(None, date(2026, 11, 16), date(2026, 11, 22))
    s = analitica.sessions(con, f)
    assert s["kpi"]["sessions"] > 100
    assert s["mateix_model_diferent_talla"]["sessions"] > 10
    assert {r["peces"]: r["sessions"] for r in s["per_nombre_peces"]}["4"] > 0
    assert analitica.servei(con, f)["peticions_assistencia"] > 0
