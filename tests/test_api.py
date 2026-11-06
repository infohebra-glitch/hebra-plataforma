"""API del tauler (/api/v2): sessió, rols, operació, importacions, flux SSE i seguretat."""

import importlib
import threading
import time

import pytest
from fastapi.testclient import TestClient

from hebra import alertes, auth, fitxa


@pytest.fixture
def entorn(tmp_path, monkeypatch):
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "api.db"))
    monkeypatch.setenv("HEBRA_SECRET", "secret-de-prova")
    monkeypatch.setenv("HEBRA_FRONTEND_DIST", str(tmp_path / "no-hi-es"))
    monkeypatch.setattr(auth, "ITERACIONS", 1000)  # proves ràpides
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    from hebra import simulador
    con = app_mod.con
    simulador.prepara_botiga(con)
    con.execute("INSERT INTO botiga (id, nom) VALUES ('GIR-01', 'Girona')")
    simulador._peces_fisiques(con, per_sku=1)
    auth.crea_usuari(con, "admin@hebra.cat", "Admin", "admin", "contrasenya-admin")
    auth.crea_usuari(con, "marca@hebra.cat", "Marca", "marca", "contrasenya-marca")
    auth.crea_usuari(con, "bcn@hebra.cat", "BCN", "botiga", "contrasenya-bcn", "BCN-01")
    return app_mod, con


def _client(app_mod, correu=None):
    c = TestClient(app_mod.app)
    if correu:
        r = c.post("/api/v2/sessio", json={"correu": correu, "contrasenya": f"contrasenya-{correu.split('@')[0]}"})
        assert r.status_code == 200, r.text
    return c


def _peticio(con, botiga="BCN-01"):
    fila = con.execute("""SELECT e.nfc_token, k.gtin, k.model FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                          ORDER BY k.gtin LIMIT 1""").fetchone()
    altra = con.execute("SELECT gtin FROM catalog_sku WHERE model = ? AND gtin != ? LIMIT 1",
                        (fila["model"], fila["gtin"])).fetchone()[0]
    return fitxa.demana_talla(con, "s1", botiga, fila["gtin"], altra, "ca", "C2")


# ---------------------------------------------------------------- Sessió i rols


def test_sessio_galeta_i_logout(entorn):
    app_mod, _ = entorn
    c = TestClient(app_mod.app)
    assert c.get("/api/v2/jo").status_code == 401
    assert c.post("/api/v2/sessio", json={"correu": "marca@hebra.cat", "contrasenya": "no"}).status_code == 401
    r = c.post("/api/v2/sessio", json={"correu": "MARCA@hebra.cat", "contrasenya": "contrasenya-marca"})
    assert r.status_code == 200 and r.json()["usuari"]["rol"] == "marca"
    galeta = r.headers["set-cookie"]
    assert "hebra_sessio=" in galeta and "HttpOnly" in galeta and "SameSite=lax" in galeta
    assert "Secure" not in galeta  # només amb HEBRA_COOKIE_SECURE=1
    jo = c.get("/api/v2/jo").json()
    assert jo["usuari"]["correu"] == "marca@hebra.cat" and {b["id"] for b in jo["botigues"]} == {"BCN-01", "GIR-01"}
    assert c.delete("/api/v2/sessio").json() == {"ok": True}
    assert c.get("/api/v2/jo").status_code == 401


def test_galeta_manipulada_o_caducada(entorn):
    app_mod, _ = entorn
    c = TestClient(app_mod.app)
    bona = auth.signa("secret-de-prova", 1)
    assert auth.verifica("secret-de-prova", bona) == 1
    assert auth.verifica("altre-secret", bona) is None
    assert auth.verifica("secret-de-prova", bona, ara=time.time() + 13 * 3600) is None
    cos, sig = bona.split(".")
    falsa = auth._b64(b'{"uid":2,"exp":9999999999}') + "." + sig
    c.cookies.set("hebra_sessio", falsa)
    assert c.get("/api/v2/jo").status_code == 401


def test_usuari_botiga_veu_nomes_la_seva(entorn):
    app_mod, _ = entorn
    c = _client(app_mod, "bcn@hebra.cat")
    jo = c.get("/api/v2/jo").json()
    assert [b["id"] for b in jo["botigues"]] == ["BCN-01"]
    assert c.get("/api/v2/peticions?botiga=GIR-01").status_code == 403
    assert c.get("/api/v2/decisions").status_code == 403
    assert c.get("/api/v2/usuaris").status_code == 403
    assert c.post("/api/v2/importa/cataleg", files={"fitxer": ("c.csv", b"gtin\n")}).status_code == 403
    assert c.put("/api/v2/parametres", json={"valors": {"marge_peca": 1}}).status_code == 403


def test_marca_no_administra(entorn):
    app_mod, _ = entorn
    c = _client(app_mod, "marca@hebra.cat")
    assert c.get("/api/v2/parametres").status_code == 200
    assert c.put("/api/v2/parametres", json={"valors": {"marge_peca": 1}}).status_code == 403
    assert c.get("/api/v2/usuaris").status_code == 403
    assert c.post("/api/v2/shopify/sincronitza?botiga=BCN-01").status_code == 403


def test_limit_intents_de_sessio(entorn):
    app_mod, _ = entorn
    c = TestClient(app_mod.app)
    for _ in range(10):
        assert c.post("/api/v2/sessio", json={"correu": "marca@hebra.cat", "contrasenya": "x"}).status_code == 401
    # Bloquejat, fins i tot amb la contrasenya bona.
    r = c.post("/api/v2/sessio", json={"correu": "marca@hebra.cat", "contrasenya": "contrasenya-marca"})
    assert r.status_code == 429
    # Un altre correu des de la mateixa IP no queda bloquejat.
    assert c.post("/api/v2/sessio", json={"correu": "bcn@hebra.cat", "contrasenya": "contrasenya-bcn"}).status_code == 200


def test_usuaris_admin(entorn):
    app_mod, _ = entorn
    c = _client(app_mod, "admin@hebra.cat")
    r = c.post("/api/v2/usuaris", json={"correu": "gir@hebra.cat", "nom": "Girona", "rol": "botiga",
                                        "contrasenya": "curta"})
    assert r.status_code == 400
    r = c.post("/api/v2/usuaris", json={"correu": "gir@hebra.cat", "nom": "Girona", "rol": "botiga",
                                        "botiga_id": "GIR-01", "contrasenya": "contrasenya-gir"})
    assert r.status_code == 200 and r.json()["usuari"]["botiga_id"] == "GIR-01"
    uid = r.json()["usuari"]["id"]
    assert len(c.get("/api/v2/usuaris").json()["usuaris"]) == 4
    assert c.patch(f"/api/v2/usuaris/{uid}", json={"actiu": False}).json()["usuari"]["actiu"] is False
    assert TestClient(app_mod.app).post("/api/v2/sessio", json={"correu": "gir@hebra.cat",
                                                                "contrasenya": "contrasenya-gir"}).status_code == 401


# ---------------------------------------------------------------- Analítica (funcions substituïdes)


def test_rutes_analitica_reben_el_filtre(entorn, monkeypatch):
    app_mod, con = entorn
    from hebra import analitica
    rebuts = []

    def stub(nom):
        def f(con, filtre, *args):
            rebuts.append((nom, filtre, args))
            return {"funcio": nom}
        return f

    for nom in ("resum", "models", "talles", "demanda_perduda", "motius", "servei", "estoc", "fitxa_nfc",
                "experiments", "alertes", "valor", "perdues", "model_detall", "informe"):
        monkeypatch.setattr(analitica, nom, stub(nom), raising=False)
    monkeypatch.setattr(analitica, "historial_peca", lambda con, epc: {"epc": epc}, raising=False)

    c = _client(app_mod, "marca@hebra.cat")
    for ruta, nom in [("resum", "resum"), ("models", "models"), ("talles", "talles"),
                      ("demanda-perduda", "demanda_perduda"), ("motius", "motius"), ("servei", "servei"),
                      ("estoc", "estoc"), ("fitxa-nfc", "fitxa_nfc"), ("experiments", "experiments"),
                      ("alertes", "alertes"), ("valor", "valor"), ("perdues", "perdues"),
                      ("models/CL-24-NAT", "model_detall"), ("informes/setmanal", "informe")]:
        r = c.get(f"/api/v2/{ruta}?des=2026-11-16&fins=2026-11-22")
        assert r.status_code == 200 and r.json() == {"funcio": nom}, ruta
    nom, f, args = rebuts[-1]
    assert f.botiga_id is None and f.des.isoformat() == "2026-11-16" and f.fins.isoformat() == "2026-11-22"
    assert args == ("setmanal",)
    assert c.get("/api/v2/informes/inventat").status_code == 404
    assert c.get("/api/v2/resum?des=ahir").status_code == 400
    assert c.get("/api/v2/resum?des=2026-11-20&fins=2026-11-10").status_code == 400
    assert c.get("/api/v2/resum?botiga=NO-HI-ES").status_code == 404
    assert c.get("/api/v2/peces/urn:x/historial").json() == {"epc": "urn:x"}

    # Per defecte: els darrers 7 dies amb dades.
    con.execute("INSERT INTO sessio (cabina_id, inici, fi) VALUES ('BCN-01-C1', '2026-11-20T10:00:00+01:00', '2026-11-20T10:05:00+01:00')")
    c.get("/api/v2/resum")
    f = rebuts[-1][1]
    assert (f.des.isoformat(), f.fins.isoformat()) == ("2026-11-14", "2026-11-20")

    # Un usuari de botiga queda limitat a la seva.
    cb = _client(app_mod, "bcn@hebra.cat")
    cb.get("/api/v2/models")
    assert rebuts[-1][1].botiga_id == "BCN-01"
    assert cb.get("/api/v2/models?botiga=GIR-01").status_code == 403
    assert TestClient(app_mod.app).get("/api/v2/resum").status_code == 401


# ---------------------------------------------------------------- Peticions i flux


def test_peticio_maquina_d_estats_i_bus(entorn):
    app_mod, con = entorn
    alertes.bus.recents.clear()
    pid = _peticio(con)
    ev = alertes.bus.recents[-1]
    assert ev.tipus == "peticio" and ev.dades["id"] == pid and ev.dades["accio"] == "nova"
    assert ev.botiga_id == "BCN-01"

    c = _client(app_mod, "bcn@hebra.cat")
    p = c.get("/api/v2/peticions?estat=pendent").json()["peticions"]
    assert [x["id"] for x in p] == [pid] and p[0]["talla"] and p[0]["segons_espera"] >= 0
    assert c.patch(f"/api/v2/peticions/{pid}", json={"estat": "pendent"}).status_code == 400
    r = c.patch(f"/api/v2/peticions/{pid}", json={"estat": "en_cami"})
    assert r.status_code == 200 and r.json()["estat"] == "en_cami" and r.json()["hora_resolta"] is None
    assert alertes.bus.recents[-1].dades["estat"] == "en_cami"
    r = c.patch(f"/api/v2/peticions/{pid}", json={"estat": "lliurada"})
    assert r.json()["estat"] == "lliurada" and r.json()["hora_resolta"]
    # Un estat final no es pot canviar.
    assert c.patch(f"/api/v2/peticions/{pid}", json={"estat": "no_disponible"}).status_code == 400
    assert c.patch("/api/v2/peticions/9999", json={"estat": "lliurada"}).status_code == 404

    # Una petició d'una altra botiga: 403.
    altra = _peticio(con, "GIR-01")
    assert c.patch(f"/api/v2/peticions/{altra}", json={"estat": "en_cami"}).status_code == 403


def test_talla_esgotada_a_la_tercera_peticio(entorn):
    _, con = entorn
    fila = con.execute("""SELECT k.gtin, k.model FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                          ORDER BY k.gtin LIMIT 1""").fetchone()
    altra = con.execute("SELECT gtin FROM catalog_sku WHERE model = ? AND gtin != ? LIMIT 1",
                        (fila["model"], fila["gtin"])).fetchone()[0]
    con.execute("INSERT INTO estoc (botiga_id, gtin, unitats, actualitzat) VALUES ('BCN-01', ?, 0, 'x')", (altra,))
    alertes.bus.recents.clear()
    for i in range(4):
        fitxa.demana_talla(con, f"s{i}", "BCN-01", fila["gtin"], altra, "ca", ts=f"2026-11-16T12:0{i}:00+01:00")
    avisos = [e for e in alertes.bus.recents if e.tipus == "alerta"]
    assert len(avisos) == 1 and avisos[0].dades["tipus"] == "talla_esgotada"
    assert con.execute("SELECT COUNT(*) FROM peticio_talla WHERE disponible = 0").fetchone()[0] == 4


def test_flux_sse(entorn, monkeypatch):
    app_mod, con = entorn
    from hebra.api import flux
    monkeypatch.setattr(flux, "DURADA_MAXIMA_S", 3.0)
    c = _client(app_mod, "bcn@hebra.cat")

    def publica_quan_hi_hagi_subscriptor():
        for _ in range(200):
            if alertes.bus.subscriptors:
                alertes.bus.publica("peticio", {"id": 1, "botiga_id": "GIR-01"}, "GIR-01")  # no és seva
                alertes.bus.publica("peticio", {"id": 2, "botiga_id": "BCN-01"}, "BCN-01")
                return
            time.sleep(0.01)

    threading.Thread(target=publica_quan_hi_hagi_subscriptor).start()
    r = c.get("/api/v2/flux")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    blocs = [b for b in r.text.split("\n\n") if b.startswith("event:")]
    assert blocs[0] == 'event: peticio\ndata: {"id": 2, "botiga_id": "BCN-01"}'
    assert len(blocs) == 1
    assert alertes.bus.subscriptors == 0
    assert TestClient(app_mod.app).get("/api/v2/flux").status_code == 401


# ---------------------------------------------------------------- Abandonades, decisions, experiments


def test_abandonades(entorn):
    app_mod, con = entorn
    epc = con.execute("SELECT epc FROM etiqueta LIMIT 1").fetchone()[0]
    con.execute("INSERT INTO peca_abandonada (epc, cabina_id, detectada) VALUES (?, 'BCN-01-C1', '2026-11-16T12:30:00+01:00')", (epc,))
    con.commit()
    c = _client(app_mod, "bcn@hebra.cat")
    a = c.get("/api/v2/abandonades?obertes=1").json()["abandonades"]
    assert len(a) == 1 and a[0]["epc"] == epc and a[0]["cabina"] == "BCN-01-C1" and a[0]["resolta"] is None
    assert c.patch(f"/api/v2/abandonades/{a[0]['id']}", json={"resolta": True}).json()["resolta"]
    assert c.get("/api/v2/abandonades?obertes=1").json()["abandonades"] == []
    assert len(c.get("/api/v2/abandonades").json()["abandonades"]) == 1


def test_decisions_crud(entorn):
    app_mod, _ = entorn
    c = _client(app_mod, "marca@hebra.cat")
    r = c.post("/api/v2/decisions", json={"titol": "Revisar el patró de la 38", "botiga_id": "BCN-01",
                                          "insight": "talla_no_quadra", "model": "TX-26-IND", "responsable": "PROD",
                                          "data_limit": "2026-12-01"})
    assert r.status_code == 200
    d = r.json()
    assert d["estat"] == "proposada" and d["creada"] and set(d) == {
        "id", "botiga_id", "creada", "titol", "descripcio", "insight", "model", "responsable", "data_limit",
        "estat", "experiment_id", "resultat"}
    assert c.post("/api/v2/decisions", json={"titol": ""}).status_code == 400
    assert c.post("/api/v2/decisions", json={"titol": "x", "estat": "inventat"}).status_code == 400
    assert c.post("/api/v2/decisions", json={"titol": "x", "experiment_id": "no-hi-es"}).status_code == 400
    r = c.patch(f"/api/v2/decisions/{d['id']}", json={"estat": "feta", "resultat": "Conversió +5 punts"})
    assert r.json()["estat"] == "feta" and r.json()["resultat"] == "Conversió +5 punts" and r.json()["titol"] == d["titol"]
    assert c.patch("/api/v2/decisions/999", json={"estat": "feta"}).status_code == 404
    assert [x["id"] for x in c.get("/api/v2/decisions?botiga=BCN-01").json()["decisions"]] == [d["id"]]


def test_experiment_amb_sorteig(entorn):
    app_mod, con = entorn
    c = _client(app_mod, "marca@hebra.cat")
    cos = {"id": "origen-2027-01", "botiga_id": "BCN-01", "variable": "origen", "hipotesi": "L'origen fa vendre",
           "unitat": "dia", "inici": "2027-01-04", "setmanes": 6, "proves_minimes": 30}
    r = c.post("/api/v2/experiments", json=cos)
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["fi"] == "2027-02-14" and e["estat"] == "previst" and e["assignacio"] == {"amb": 21, "sense": 21}
    assert con.execute("SELECT COUNT(*) FROM assignacio WHERE experiment = 'origen-2027-01'").fetchone()[0] == 42
    # La fitxa NFC llegeix el grup amb experiment = 'origen'.
    assert con.execute("SELECT COUNT(*) FROM assignacio WHERE experiment = 'origen' AND data >= '2027-01-04'").fetchone()[0] == 42
    assert c.post("/api/v2/experiments", json=cos).status_code == 400  # id repetit
    r = c.post("/api/v2/experiments", json=dict(cos, id="preu-models", variable="preu", unitat="model"))
    assert sum(r.json()["assignacio"].values()) == con.execute("SELECT COUNT(DISTINCT model) FROM catalog_sku").fetchone()[0]
    assert _client(app_mod, "bcn@hebra.cat").post("/api/v2/experiments", json=dict(cos, id="x-1")).status_code == 403


def test_parametres_i_recomptes(entorn):
    app_mod, con = entorn
    c = _client(app_mod, "admin@hebra.cat")
    r = c.put("/api/v2/parametres", json={"botiga_id": "BCN-01", "valors": {"marge_peca": 42, "minuts_abandonada": "20"}})
    assert r.json() == {"botiga_id": "BCN-01", "valors": {"marge_peca": "42", "minuts_abandonada": "20"}}
    assert c.put("/api/v2/parametres", json={"valors": {"Mal Nom": 1}}).status_code == 400
    from hebra import db
    assert db.parametre(con, "BCN-01", "minuts_abandonada") == "20"
    assert db.parametre(con, "GIR-01", "minuts_abandonada", "30") == "30"

    cb = _client(app_mod, "bcn@hebra.cat")
    r = cb.post("/api/v2/recomptes", json={"botiga_id": "BCN-01", "data": "2026-11-16", "gtin": "8400000123457",
                                           "manual": 10, "rfid": 9})
    assert r.status_code == 200 and r.json()["gtin"] == "08400000123457"
    assert cb.post("/api/v2/recomptes", json={"botiga_id": "GIR-01", "data": "2026-11-16", "gtin": "1",
                                              "manual": 1, "rfid": 1}).status_code == 403


# ---------------------------------------------------------------- Importacions


def test_importa_vendes_estoc_i_cataleg(entorn):
    app_mod, con = entorn
    gtin = con.execute("SELECT gtin FROM catalog_sku ORDER BY gtin LIMIT 1").fetchone()[0]
    cb = _client(app_mod, "bcn@hebra.cat")
    vendes = f"data_hora,botiga,gtin,quantitat,import,tiquet\n2026-11-16T12:00:00+01:00,BCN-01,{gtin},1,69,T1\n"
    r = cb.post("/api/v2/importa/vendes", files={"fitxer": ("v.csv", vendes.encode())})
    assert r.json() == {"importades": 1, "errors": []}
    alienes = vendes + f"2026-11-16,GIR-01,{gtin},1,69,T2\n"
    assert cb.post("/api/v2/importa/vendes", files={"fitxer": ("v.csv", alienes.encode())}).status_code == 403

    r = cb.post("/api/v2/importa/estoc", files={"fitxer": ("e.csv", f"botiga;gtin;unitats\nBCN-01;{gtin};3\nBCN-01;abc;1\n".encode())})
    assert r.json()["importades"] == 1 and "GTIN no vàlid" in r.json()["errors"][0]
    assert con.execute("SELECT unitats FROM estoc WHERE gtin = ?", (gtin,)).fetchone()[0] == 3

    ca = _client(app_mod, "admin@hebra.cat")
    cat = "gtin,model,color,talla,categoria,preu\n08400000123457,CL-24-NAT,Natural,M,camisa,69\n"
    assert ca.post("/api/v2/importa/cataleg", files={"fitxer": ("c.csv", cat.encode())}).json() == {"importades": 1, "errors": []}
    assert ca.post("/api/v2/importa/cataleg", files={"fitxer": ("c.csv", b"\xff\xfe")}).status_code == 400


# ---------------------------------------------------------------- Fitxa NFC, seguretat i tauler


def test_fitxa_seccio_balisa_i_csp(entorn):
    app_mod, con = entorn
    c = TestClient(app_mod.app)
    token = con.execute("SELECT nfc_token FROM etiqueta LIMIT 1").fetchone()[0]
    r = c.get(f"/p/{token}?b=BCN-01")
    assert r.status_code == 200 and "set-cookie" not in r.headers
    csp = r.headers["content-security-policy"]
    assert fitxa.HASH_SCRIPT in csp and "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    assert f"<script>{fitxa.SCRIPT_SECCIONS}</script>" in r.text  # el text exacte que té el hash
    assert 'data-seccio="talles"' in r.text and 'id="seccions"' in r.text
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["referrer-policy"] == "no-referrer"

    r = c.post(f"/p/{token}/seccio", data={"seccio": "cura", "s": "sess", "b": "BCN-01", "lang": "es"})
    assert r.status_code == 204 and "set-cookie" not in r.headers
    fila = con.execute("SELECT * FROM esdeveniment_nfc WHERE tipus = 'veu_seccio'").fetchone()
    assert fila["valor"] == "cura" and fila["idioma"] == "es" and fila["botiga_id"] == "BCN-01"
    assert c.post(f"/p/{token}/seccio", data={"seccio": "<x>", "s": "sess"}).status_code == 400


def test_fitxa_estoc_real_i_combina(entorn):
    app_mod, con = entorn
    import json
    fila = con.execute("""SELECT e.nfc_token, k.gtin, k.model FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                          ORDER BY k.gtin LIMIT 1""").fetchone()
    altres = con.execute("SELECT DISTINCT model FROM catalog_sku WHERE model != ?", (fila["model"],)).fetchall()
    origen = json.loads(con.execute("SELECT origen_json FROM catalog_sku WHERE gtin = ?", (fila["gtin"],)).fetchone()[0])
    origen["combina"] = [altres[0][0], "MODEL-INEXISTENT"]
    con.execute("UPDATE catalog_sku SET origen_json = ? WHERE model = ?", (json.dumps(origen), fila["model"]))
    for v in con.execute("SELECT gtin FROM catalog_sku WHERE model = ?", (fila["model"],)).fetchall():
        con.execute("INSERT INTO estoc (botiga_id, gtin, unitats, actualitzat) VALUES ('BCN-01', ?, 0, 'x')", (v[0],))
    con.commit()
    peca = fitxa.peca_per_token(con, fila["nfc_token"])
    d = fitxa.dades_fitxa(con, peca, "BCN-01", "ca")
    assert all(t["estoc"] == 0 for t in d["talles"])
    assert d["combina"][1] == "MODEL-INEXISTENT" and d["combina"][0] != altres[0][0]  # nom, no codi
    # Sense botiga (o sense files d'estoc), l'estoc del fitxer d'origen.
    d2 = fitxa.dades_fitxa(con, peca, None, "ca")
    assert [t["estoc"] for t in d2["talles"]] == [origen["estoc"].get(t["talla"]) for t in d2["talles"]]
    r = TestClient(app_mod.app).get(f"/p/{fila['nfc_token']}?b=BCN-01")
    assert "Combina amb" in r.text and "MODEL-INEXISTENT" in r.text


def test_limit_formularis_fitxa(entorn):
    app_mod, con = entorn
    app_mod.app.state.limit_fitxa = auth.CubellTestimonis(capacitat=3, ritme=0.001)
    c = TestClient(app_mod.app)
    token = con.execute("SELECT nfc_token FROM etiqueta LIMIT 1").fetchone()[0]
    codis = [c.post(f"/p/{token}/seccio", data={"seccio": "cura", "s": "x"}).status_code for _ in range(5)]
    assert codis == [204, 204, 204, 429, 429]


def test_tauler_spa(entorn, tmp_path, monkeypatch):
    app_mod, _ = entorn
    c = TestClient(app_mod.app)
    assert c.get("/app/").status_code == 404
    assert c.get("/", follow_redirects=False).status_code == 200  # sense dist: la pàgina d'inici de sempre

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=app></div>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("no")
    monkeypatch.setattr(app_mod, "cfg", app_mod.cfg.__class__(frontend_dist=str(dist), secret="s"))
    assert c.get("/", follow_redirects=False).headers["location"] == "/app/"
    assert c.get("/app", follow_redirects=False).headers["location"] == "/app/"
    assert "id=app" in c.get("/app/").text
    assert "id=app" in c.get("/app/dependent/peticions").text  # ruta del client: index.html
    r = c.get("/app/assets/app.js")
    assert r.text == "console.log(1)" and "immutable" in r.headers["cache-control"]
    assert "id=app" in c.get("/app/..%2Fsecret.txt").text  # no surt de dist


def test_pagina_antiga_del_dependent_en_cami(entorn):
    app_mod, con = entorn
    pid = _peticio(con)
    c = TestClient(app_mod.app)
    aut = ("botiga", "hebra")
    assert "En camí" in c.get("/botiga/peticions", auth=aut).text
    c.post(f"/botiga/peticions/{pid}", data={"estat": "en_cami"}, auth=aut, follow_redirects=False)
    assert con.execute("SELECT estat FROM peticio_talla WHERE id = ?", (pid,)).fetchone()[0] == "en_cami"
    c.post(f"/botiga/peticions/{pid}", data={"estat": "lliurada"}, auth=aut, follow_redirects=False)
    fila = con.execute("SELECT estat, hora_resolta FROM peticio_talla WHERE id = ?", (pid,)).fetchone()
    assert fila["estat"] == "lliurada" and fila["hora_resolta"]


def test_cli_usuari(tmp_path, monkeypatch, capsys):
    import sys
    from hebra import admin, db
    ruta = str(tmp_path / "cli.db")
    monkeypatch.setenv("HEBRA_BD", ruta)
    monkeypatch.setattr(auth, "ITERACIONS", 1000)
    monkeypatch.setattr(sys, "argv", ["hebra.admin", "usuari", "--correu", "Anna@Marca.cat", "--nom", "Anna",
                                      "--rol", "marca", "--contrasenya", "una-contrasenya-llarga"])
    admin.main()
    assert "Usuari 1 creat" in capsys.readouterr().out
    con = db.connecta(ruta)
    assert auth.autentica(con, "anna@marca.cat", "una-contrasenya-llarga")["rol"] == "marca"
    monkeypatch.setattr(sys, "argv", ["hebra.admin", "usuari", "--correu", "b@m.cat", "--nom", "B",
                                      "--rol", "botiga", "--contrasenya", "una-contrasenya-llarga"])
    with pytest.raises(SystemExit, match="necessita una botiga"):
        admin.main()
