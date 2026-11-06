"""v0.3 D-E: estoc parat amb suggeriments i CSV, tasques de botiga, informes programats i lliurats,
PDF (WeasyPrint) i correu (SMTP fals)."""

import csv
import importlib
import io
import json
import smtplib
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from hebra import alertes, analitica as A, auth, correu, grafics_svg, informes_programats as ip, tasques
from hebra.analitica import inventari
from hebra.config import Config

MADRID = ZoneInfo("Europe/Madrid")
LL = {"dies_estoc_parat": 21, "parat_min_proves_traspas": 3, "parat_min_vendes_traspas": 1,
      "parat_dies_retornar": 60, "parat_conversio_baixa": 0.15, "parat_min_proves_conversio": 5}
NOMS = {"GIR-01": "Girona", "TAR-01": "Tarragona"}


# ---------------------------------------------------------------- Suggeriments (funció pura)


def test_suggeriment_traspassar_a_la_botiga_que_mes_el_mou():
    s = inventari.suggereix(2, 30, {"GIR-01": [12, 0], "TAR-01": [2, 1]}, 4, 1, None, LL, NOMS)
    assert s["accio"] == "traspassar" and s["botiga_desti"] == "GIR-01"
    assert s["text"] == "Traspassar 2 unitats a Girona: allà s'ha provat 12 vegades en 21 dies."
    # una sola venda a una altra botiga també n'hi ha prou
    s = inventari.suggereix(1, 30, {"TAR-01": [0, 1]}, 0, 0, None, LL, NOMS)
    assert s["accio"] == "traspassar" and s["botiga_desti"] == "TAR-01" and "1 unitat a Tarragona" in s["text"]


def test_suggeriment_retornar_moure_revisar_promocio():
    # > 60 dies i quiet a tot arreu (una prova solta a Girona no compta com a «quiet»)
    assert inventari.suggereix(3, 61, {}, 5, 2, None, LL, NOMS)["accio"] == "retornar"
    assert inventari.suggereix(3, 61, {"GIR-01": [1, 0]}, 0, 0, None, LL, NOMS)["accio"] == "moure_a_sala"
    assert inventari.suggereix(3, 60, {}, 5, 2, None, LL, NOMS)["accio"] == "promocio"   # 60 no és > 60
    # mai provat aquí: no és visible
    assert inventari.suggereix(3, 30, {}, 0, 0, None, LL, NOMS)["accio"] == "moure_a_sala"
    # provat prou i conversió baixa: revisar (talla, tall...), si el motiu és el preu, promoció
    s = inventari.suggereix(3, 30, {}, 10, 1, "talla", LL, NOMS)
    assert s["accio"] == "revisar" and "«talla»" in s["text"] and s["botiga_desti"] is None
    assert inventari.suggereix(3, 30, {}, 10, 1, "preu", LL, NOMS)["accio"] == "promocio"
    # poques proves per jutjar-ho, o conversió correcta: promoció
    assert inventari.suggereix(3, 30, {}, 4, 0, None, LL, NOMS)["accio"] == "promocio"
    assert inventari.suggereix(3, 30, {}, 10, 4, None, LL, NOMS)["accio"] == "promocio"
    # els llindars es poden canviar
    assert inventari.suggereix(3, 30, {"GIR-01": [2, 0]}, 0, 0, None, LL | {"parat_min_proves_traspas": 2},
                               NOMS)["accio"] == "traspassar"


def _prova(con, cabina, gtin, inici):
    s = con.execute("INSERT INTO sessio (cabina_id, inici, fi) VALUES (?, ?, ?)", (cabina, inici, inici)).lastrowid
    con.execute("""INSERT INTO prova (sessio_id, epc, gtin, durada_s, n_lectures, rssi_mitja, confianca)
                   VALUES (?, 'e', ?, 120, 20, -50, 'alta')""", (s, gtin))


@pytest.fixture
def dues_botigues(con):
    con.executemany("INSERT INTO botiga (id, nom) VALUES (?, ?)", [("BCN-01", "Barcelona"), ("GIR-01", "Girona")])
    con.executemany("INSERT INTO cabina (id, botiga_id, nom) VALUES (?, ?, 'C1')",
                    [("BCN-01-C1", "BCN-01"), ("GIR-01-C1", "GIR-01")])
    con.executemany("""INSERT INTO catalog_sku (gtin, model, color, talla, categoria, preu_eur)
                       VALUES (?, ?, 'Blau', 'M', ?, ?)""",
                    [("00000000000001", "JA", "jaqueta", 100.0), ("00000000000002", "PA", "pantalo", 40.0)])
    con.executemany("INSERT INTO estoc (botiga_id, gtin, unitats, actualitzat) VALUES (?, ?, ?, '2026-11-29')",
                    [("BCN-01", "00000000000001", 2), ("BCN-01", "00000000000002", 5), ("GIR-01", "00000000000001", 1)])
    # La jaqueta es prova molt a Girona; a Barcelona no s'ha provat mai cap de les dues.
    for i in range(4):
        _prova(con, "GIR-01-C1", "00000000000001", f"2026-11-2{i}T10:00:00+01:00")
    # una dada antiga a Barcelona perquè els dies parats tinguin un inici
    con.execute("""INSERT INTO venda_linia (botiga_id, ts, data, gtin, quantitat) VALUES
                   ('BCN-01', '2026-10-01T12:00:00+02:00', '2026-10-01', '00000000000002', 1)""")
    con.commit()
    return con


def test_estoc_parat_amb_suggeriment_resum_i_tasca(dues_botigues):
    con = dues_botigues
    f = A.Filtre("BCN-01", date(2026, 11, 23), date(2026, 11, 29))
    e = A.estoc(con, f)
    parat = {p["gtin"]: p for p in e["parat"]}
    ja, pa = parat["00000000000001"], parat["00000000000002"]
    assert ja["botiga_id"] == "BCN-01" and ja["valor_eur"] == 200.0 and ja["categoria"] == "jaqueta"
    assert ja["proves_altres_botigues"] == 4 and ja["vendes_altres_botigues"] == 0
    assert ja["suggeriment"] == {"accio": "traspassar", "botiga_desti": "GIR-01",
                                 "text": "Traspassar 2 unitats a Girona: allà s'ha provat 4 vegades en 21 dies."}
    assert pa["darrera_venda"] == "2026-10-01T12:00:00+02:00" and pa["darrera_prova"] is None
    assert pa["dies_parat"] == 59 and pa["dies_sense_activitat"] == 59
    assert pa["suggeriment"]["accio"] == "moure_a_sala" and ja["tasca"] is None
    assert e["resum_parat"] == {"unitats": 7, "valor_eur": 400.0, "per_categoria": [
        {"categoria": "jaqueta", "unitats": 2, "valor_eur": 200.0},     # empat de valor: per nom
        {"categoria": "pantalo", "unitats": 5, "valor_eur": 200.0}]}
    # Llindar a `parametre`: més dies per retornar
    con.execute("INSERT INTO parametre VALUES ('*', 'parat_dies_retornar', '30')")
    assert {p["gtin"]: p for p in A.estoc(con, f)["parat"]}["00000000000002"]["suggeriment"]["accio"] == "retornar"
    # La tasca pendent apareix a la fila
    t, nova = tasques.crea(con, "BCN-01", "traspassar", None, "", "00000000000001", 2, "GIR-01", notifica=False)
    assert nova and t["titol"] == "Traspassar 2 u. de JA (M) a Girona"
    assert {p["gtin"]: p for p in A.estoc(con, f)["parat"]}["00000000000001"]["tasca"] == t
    # Amb totes les botigues: una fila per botiga i GTIN (la de Girona no està parada)
    tots = A.estoc(con, A.Filtre(None, date(2026, 11, 23), date(2026, 11, 29)))["parat"]
    assert sorted((p["botiga_id"], p["gtin"]) for p in tots) == [("BCN-01", "00000000000001"),
                                                                 ("BCN-01", "00000000000002")]


# ---------------------------------------------------------------- Calendari dels informes (funcions pures)


def _prog(tipus, **kw):
    return {"tipus": tipus, "actiu": 1, "hora": "08:00", "dia_setmana": None, "dia_mes": None, "data": None,
            "creada": "2026-01-01T00:00:00+01:00", "darrera_execucio": None} | kw


def _utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def test_diari_toca_un_cop_a_les_vuit_hora_local():
    p = _prog("diari")
    assert ip.toca(p, _utc(2026, 11, 16, 6, 59), "Europe/Madrid").isoformat() == "2026-11-15T08:00:00+01:00"
    o = ip.toca(p, _utc(2026, 11, 16, 7, 0), "Europe/Madrid")      # 08:00 a Madrid (hivern, +01:00)
    assert o.isoformat() == "2026-11-16T08:00:00+01:00"
    p["darrera_execucio"] = o.isoformat()
    assert ip.toca(p, _utc(2026, 11, 16, 7, 1), "Europe/Madrid") is None   # ja fet
    assert ip.toca(p, _utc(2026, 11, 17, 6, 59), "Europe/Madrid") is None
    assert ip.periode("diari", o.date()) == (date(2026, 11, 15), date(2026, 11, 15))
    # creada després de l'hora d'avui: fins demà no toca
    p2 = _prog("diari", creada="2026-11-16T09:30:00+01:00")
    assert ip.toca(p2, _utc(2026, 11, 16, 9, 0), "Europe/Madrid") is None
    assert ip.propera(p2, _utc(2026, 11, 16, 9, 0), "Europe/Madrid").isoformat() == "2026-11-17T08:00:00+01:00"
    assert ip.toca(_prog("diari", actiu=0), _utc(2026, 11, 16, 9, 0), "Europe/Madrid") is None


def test_canvi_d_hora_estiu_i_hivern():
    p = _prog("diari")
    # Estiu (+02:00): les 08:00 locals són les 06:00 UTC
    assert ip.toca(p, _utc(2026, 7, 1, 5, 59), "Europe/Madrid").date() == date(2026, 6, 30)
    assert ip.toca(p, _utc(2026, 7, 1, 6, 0), "Europe/Madrid").isoformat() == "2026-07-01T08:00:00+02:00"
    # El dia del canvi (29-03-2026, a les 2 h passen a ser les 3 h) les 08:00 ja són d'estiu
    assert ip.toca(p, _utc(2026, 3, 29, 6, 0), "Europe/Madrid").isoformat() == "2026-03-29T08:00:00+02:00"
    assert ip.toca(p, _utc(2026, 3, 29, 5, 59), "Europe/Madrid").date() == date(2026, 3, 28)
    # 02:30 no existeix el 29-03: es fa a les 03:30 d'estiu (01:30 UTC), un sol cop
    p230 = _prog("diari", hora="02:30")
    assert ip.toca(p230, _utc(2026, 3, 29, 1, 29), "Europe/Madrid").date() == date(2026, 3, 28)
    o = ip.toca(p230, _utc(2026, 3, 29, 1, 30), "Europe/Madrid")
    assert o.isoformat() == "2026-03-29T03:30:00+02:00"
    # 02:30 existeix dues vegades el 25-10: es fa la primera (00:30 UTC) i no es repeteix
    o = ip.toca(p230, _utc(2026, 10, 25, 0, 30), "Europe/Madrid")
    assert o.isoformat() == "2026-10-25T02:30:00+02:00"
    p230["darrera_execucio"] = o.isoformat()
    assert ip.toca(p230, _utc(2026, 10, 25, 1, 45), "Europe/Madrid") is None
    # Una altra zona: Canàries (una hora menys)
    assert ip.toca(p, _utc(2026, 11, 16, 8, 0), "Atlantic/Canary").isoformat() == "2026-11-16T08:00:00+00:00"


def test_setmanal_mensual_i_una_vegada():
    s = _prog("setmanal", dia_setmana=0)
    o = ip.toca(s, _utc(2026, 11, 18, 12, 0), "Europe/Madrid")   # dimecres: el darrer dilluns
    assert o.isoformat() == "2026-11-16T08:00:00+01:00"
    assert ip.periode("setmanal", o.date()) == (date(2026, 11, 9), date(2026, 11, 15))
    assert ip.periode("setmanal", date(2026, 11, 18)) == (date(2026, 11, 9), date(2026, 11, 15))
    assert ip.propera(s, _utc(2026, 11, 18, 12, 0), "Europe/Madrid").isoformat() == "2026-11-23T08:00:00+01:00"
    m = _prog("mensual", dia_mes=1)
    o = ip.toca(m, _utc(2026, 12, 1, 7, 0), "Europe/Madrid")
    assert o.isoformat() == "2026-12-01T08:00:00+01:00"
    assert ip.periode("mensual", o.date()) == (date(2026, 11, 1), date(2026, 11, 30))
    assert ip.periode("mensual", date(2027, 1, 1)) == (date(2026, 12, 1), date(2026, 12, 31))
    assert ip.propera(m, _utc(2026, 12, 31, 12, 0), "Europe/Madrid").isoformat() == "2027-01-01T08:00:00+01:00"
    t = _prog("temporada", data="2027-01-10")
    assert ip.toca(t, _utc(2027, 1, 10, 6, 59), "Europe/Madrid") is None
    o = ip.toca(t, _utc(2027, 1, 12, 9, 0), "Europe/Madrid")      # el servidor estava aturat: es fa en tornar
    assert o.isoformat() == "2027-01-10T08:00:00+01:00"
    t["darrera_execucio"] = o.isoformat()
    assert ip.toca(t, _utc(2027, 2, 1, 9, 0), "Europe/Madrid") is None and ip.propera(t, _utc(2027, 2, 1), "Europe/Madrid") is None
    assert ip.periode("temporada", date(2027, 1, 10)) == (date(2026, 7, 12), date(2027, 1, 9))
    assert ip.periode("pilot", date(2027, 1, 10), date(2026, 11, 9)) == (date(2026, 11, 9), date(2027, 1, 9))
    assert ip.periode("pilot", date(2027, 1, 10)) == (date(2026, 11, 29), date(2027, 1, 9))


# ---------------------------------------------------------------- Gràfics SVG i format català


def test_format_catala_i_svg():
    assert grafics_svg.format_valor(1234.4, "eur") == "1.234 €" and grafics_svg.format_valor(9.5, "eur") == "9,50 €"
    assert grafics_svg.format_valor(12345, "enter") == "12.345"
    assert grafics_svg.format_valor(0.347, "pct") == "35 %" and grafics_svg.format_valor(0.045, "pct") == "4,5 %"
    assert grafics_svg.format_valor(2450.0, "eur") == "2.450 €"
    assert grafics_svg.format_valor(92, "segons") == "92 s"
    assert grafics_svg.format_valor(None, "pct") == "—"
    assert grafics_svg.format_variacio(0.031, "pct") == "+3,1 punts"
    assert grafics_svg.format_variacio(-0.04, "enter") == "−4 %"
    base = {"titol": "T", "unitat": "pct", "eix_x": ["S45", "S46", "S47"],
            "series": [{"nom": "Amb", "valors": [0.31, None, 0.29]}, {"nom": "Sense", "valors": [0.2, 0.25, 0.22]}]}
    for tipus in ("linia", "barres", "barres_apilades", "donut"):
        svg = grafics_svg.svg(dict(base, tipus=tipus))
        assert svg.startswith("<svg") and svg.endswith("</svg>") and "<script" not in svg
    assert "Sense" in grafics_svg.svg(dict(base, tipus="linia"))           # llegenda amb 2 sèries
    assert "Sense dades" in grafics_svg.svg(dict(base, tipus="barres", series=[]))
    with pytest.raises(ValueError):
        grafics_svg.svg(dict(base, tipus="radar"))


# ---------------------------------------------------------------- API


@pytest.fixture
def entorn(tmp_path, monkeypatch):
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "api.db"))
    monkeypatch.setenv("HEBRA_SECRET", "secret-de-prova")
    monkeypatch.setenv("HEBRA_FRONTEND_DIST", str(tmp_path / "no-hi-es"))
    for v in ("HEBRA_SMTP_HOST", "HEBRA_SMTP_USUARI", "HEBRA_SMTP_REMITENT"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(auth, "ITERACIONS", 1000)
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    con = app_mod.con
    from hebra import simulador
    simulador.simula(con, date(2026, 11, 16), setmanes=1)
    con.execute("INSERT INTO botiga (id, nom) VALUES ('GIR-01', 'Girona')")
    con.commit()
    auth.crea_usuari(con, "marca@hebra.cat", "Marca", "marca", "contrasenya-marca")
    auth.crea_usuari(con, "bcn@hebra.cat", "BCN", "botiga", "contrasenya-bcn", "BCN-01")
    auth.crea_usuari(con, "gir@hebra.cat", "GIR", "botiga", "contrasenya-gir", "GIR-01")
    return app_mod, con


def _client(app_mod, correu_=None):
    c = TestClient(app_mod.app)
    if correu_:
        r = c.post("/api/v2/sessio", json={"correu": correu_, "contrasenya": f"contrasenya-{correu_.split('@')[0]}"})
        assert r.status_code == 200, r.text
    return c


F_SIM = "botiga=BCN-01&des=2026-11-16&fins=2026-11-22"


def test_estoc_api_i_csv(entorn):
    app_mod, _ = entorn
    c = _client(app_mod, "bcn@hebra.cat")
    e = c.get(f"/api/v2/estoc?{F_SIM}").json()
    assert e["parat"] and e["resum_parat"]["unitats"] == sum(p["unitats"] for p in e["parat"])
    assert {p["suggeriment"]["accio"] for p in e["parat"]} <= {"traspassar", "moure_a_sala", "promocio", "retornar", "revisar"}
    r = c.get(f"/api/v2/estoc/parat.csv?{F_SIM}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    files = list(csv.reader(io.StringIO(r.text.lstrip("﻿")), delimiter=";"))
    assert files[0][:3] == ["botiga_id", "gtin", "model"] and len(files) == len(e["parat"]) + 1
    assert files[1][1] == e["parat"][0]["gtin"] and files[1][14] == e["parat"][0]["suggeriment"]["accio"]
    assert c.get(f"/api/v2/estoc/parat.csv?{F_SIM}&categoria=no-n-hi-ha").text.count("\n") == 1
    assert c.get("/api/v2/estoc/parat.csv?botiga=GIR-01").status_code == 403   # botiga: només la seva


def test_tasques_permisos_i_bus(entorn):
    app_mod, con = entorn
    gtin = con.execute("SELECT gtin FROM catalog_sku ORDER BY gtin LIMIT 1").fetchone()[0]
    bcn, gir, marca = _client(app_mod, "bcn@hebra.cat"), _client(app_mod, "gir@hebra.cat"), _client(app_mod, "marca@hebra.cat")
    r = bcn.post("/api/v2/tasques", json={"tipus": "traspassar", "gtin": gtin, "unitats": 2, "botiga_desti": "GIR-01"})
    assert r.status_code == 200, r.text
    t = r.json()
    assert set(t) == {"id", "botiga_id", "tipus", "titol", "detall", "gtin", "unitats", "botiga_desti", "estat",
                      "creada", "feta"}
    assert t["botiga_id"] == "BCN-01" and t["estat"] == "pendent" and "a Girona" in t["titol"]
    ev = alertes.bus.recents[-1]
    assert ev.tipus == "tasca" and ev.botiga_id == "BCN-01"
    assert ev.dades["accio"] == "nova" and ev.dades["id"] == t["id"]
    # la mateixa tasca pendent no es duplica
    assert bcn.post("/api/v2/tasques", json={"tipus": "traspassar", "gtin": gtin, "unitats": 2,
                                             "botiga_desti": "GIR-01"}).json()["id"] == t["id"]
    # validacions
    assert bcn.post("/api/v2/tasques", json={"tipus": "traspassar", "gtin": gtin}).status_code == 400
    assert bcn.post("/api/v2/tasques", json={"tipus": "moure_a_sala", "gtin": "99999"}).status_code == 400
    assert bcn.post("/api/v2/tasques", json={"tipus": "volar", "titol": "x"}).status_code == 400
    assert marca.post("/api/v2/tasques", json={"tipus": "altre", "titol": "x"}).status_code == 400  # sense botiga
    # rols: una botiga no crea ni veu ni toca tasques d'una altra
    assert gir.post("/api/v2/tasques", json={"botiga_id": "BCN-01", "tipus": "recompte"}).status_code == 403
    assert gir.get("/api/v2/tasques?botiga=BCN-01").status_code == 403
    assert gir.get("/api/v2/tasques").json() == {"tasques": []}
    assert gir.patch(f"/api/v2/tasques/{t['id']}", json={"estat": "feta"}).status_code == 403
    m = marca.post("/api/v2/tasques", json={"botiga_id": "GIR-01", "tipus": "recompte", "titol": "Recompte"}).json()
    assert [x["id"] for x in gir.get("/api/v2/tasques").json()["tasques"]] == [m["id"]]
    assert t["id"] in [x["id"] for x in marca.get("/api/v2/tasques?botiga=BCN-01").json()["tasques"]]
    # feta
    assert bcn.patch(f"/api/v2/tasques/{t['id']}", json={"estat": "regalada"}).status_code == 400
    f = bcn.patch(f"/api/v2/tasques/{t['id']}", json={"estat": "feta"}).json()
    assert f["estat"] == "feta" and f["feta"]
    assert alertes.bus.recents[-1].dades["accio"] == "canvi"
    assert con.execute("SELECT feta_per FROM tasca WHERE id = ?", (t["id"],)).fetchone()[0] is not None
    assert t["id"] not in [x["id"] for x in bcn.get("/api/v2/tasques?estat=pendent").json()["tasques"]]
    assert bcn.get("/api/v2/tasques?estat=x").status_code == 400
    assert bcn.patch("/api/v2/tasques/99999", json={"estat": "feta"}).status_code == 404
    assert TestClient(app_mod.app).get("/api/v2/tasques").status_code == 401


def test_informes_rutes_no_es_trepitgen(entorn):
    app_mod, _ = entorn
    c = _client(app_mod, "marca@hebra.cat")
    inf = c.get(f"/api/v2/informes/setmanal?{F_SIM}").json()
    for clau in ("tipus", "titol", "periode", "blocs", "accio", "avisos", "xifres", "grafics"):
        assert clau in inf
    g = inf["grafics"][0]
    assert set(g) == {"id", "titol", "tipus", "unitat", "eix_x", "series", "nota"}
    assert set(inf["xifres"][0]) == {"etiqueta", "valor", "unitat", "variacio", "vs"}
    assert c.get("/api/v2/informes/anual").status_code == 404
    assert "lliurats" in c.get("/api/v2/informes/lliurats").json()
    assert "programacions" in c.get("/api/v2/informes/programacio").json()
    assert c.get("/api/v2/informes/lliurats/999999").status_code == 404


def test_pdf_al_moment_i_de_lliurat(entorn):
    app_mod, _ = entorn
    c = _client(app_mod, "marca@hebra.cat")
    r = c.get(f"/api/v2/informes/setmanal.pdf?{F_SIM}")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert c.get(f"/api/v2/informes/anual.pdf?{F_SIM}").status_code == 404
    lliurats = c.get("/api/v2/informes/lliurats?tipus=diari").json()["lliurats"]
    assert lliurats and all(x["tipus"] == "diari" for x in lliurats)
    r = c.get(f"/api/v2/informes/lliurats/{lliurats[0]['id']}.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_lliurats_genera_ara_i_permisos(entorn):
    app_mod, _ = entorn
    marca, bcn, gir = (_client(app_mod, x) for x in ("marca@hebra.cat", "bcn@hebra.cat", "gir@hebra.cat"))
    r = marca.post("/api/v2/informes/lliurats", json={"tipus": "mensual", "botiga": None,
                                                       "des": "2026-11-16", "fins": "2026-11-22"})
    assert r.status_code == 200, r.text
    nou = r.json()
    assert {"id", "tipus", "botiga_id", "des", "fins", "generat", "estat_enviament", "enviat_a"} <= set(nou)
    assert nou["estat_enviament"] == "no_enviat" and nou["botiga_id"] is None
    llista = marca.get("/api/v2/informes/lliurats").json()["lliurats"]
    assert nou["id"] in [x["id"] for x in llista]
    assert [x["generat"] for x in llista] == sorted((x["generat"] for x in llista), reverse=True)  # nous primer
    dades = marca.get(f"/api/v2/informes/lliurats/{nou['id']}").json()
    assert dades["tipus"] == "mensual" and dades["grafics"] and dades["periode"]["des"] == "2026-11-16"
    # la botiga no veu els de totes les botigues ni els d'altres botigues
    assert bcn.get(f"/api/v2/informes/lliurats/{nou['id']}").status_code == 404
    assert all(x["botiga_id"] == "BCN-01" for x in bcn.get("/api/v2/informes/lliurats").json()["lliurats"])
    assert gir.get("/api/v2/informes/lliurats").json()["lliurats"] == []
    assert bcn.post("/api/v2/informes/lliurats", json={"tipus": "diari", "des": "2026-11-16",
                                                       "fins": "2026-11-16"}).status_code == 403
    assert marca.post("/api/v2/informes/lliurats", json={"tipus": "diari", "des": "2026-11-20",
                                                         "fins": "2026-11-16"}).status_code == 400


def test_programacio_crud_i_validacions(entorn):
    app_mod, _ = entorn
    marca, bcn = _client(app_mod, "marca@hebra.cat"), _client(app_mod, "bcn@hebra.cat")
    r = marca.post("/api/v2/informes/programacio", json={"botiga_id": "GIR-01", "tipus": "setmanal", "dia_setmana": 0,
                                                          "hora": "08:00", "destinataris": ["a@marca.cat"]})
    assert r.status_code == 200, r.text
    p = r.json()
    assert set(p) >= {"id", "botiga_id", "tipus", "actiu", "dia_setmana", "dia_mes", "data", "hora", "destinataris",
                      "propera"}
    assert p["actiu"] is True and p["destinataris"] == ["a@marca.cat"] and p["propera"].endswith("T08:00:00+01:00")
    assert datetime.fromisoformat(p["propera"]).weekday() == 0
    for dolent in ({"tipus": "setmanal"}, {"tipus": "mensual", "dia_mes": 31}, {"tipus": "temporada"},
                   {"tipus": "diari", "hora": "25:00"}, {"tipus": "diari", "destinataris": ["no-es-un-correu"]},
                   {"tipus": "diari", "botiga_id": "XXX"}):
        assert marca.post("/api/v2/informes/programacio", json=dolent).status_code == 400, dolent
    assert bcn.post("/api/v2/informes/programacio", json={"tipus": "diari"}).status_code == 403
    q = marca.patch(f"/api/v2/informes/programacio/{p['id']}", json={"actiu": False, "hora": "09:15"}).json()
    assert q["actiu"] is False and q["hora"] == "09:15" and q["propera"] is None and q["dia_setmana"] == 0
    q = marca.patch(f"/api/v2/informes/programacio/{p['id']}", json={"tipus": "temporada", "data": "2027-01-10",
                                                                     "actiu": True}).json()
    assert q["dia_setmana"] is None and q["data"] == "2027-01-10"
    # la botiga veu només les seves, sense poder-les canviar
    assert {x["botiga_id"] for x in bcn.get("/api/v2/informes/programacio").json()["programacions"]} == {"BCN-01"}
    assert bcn.patch(f"/api/v2/informes/programacio/{p['id']}", json={"actiu": True}).status_code == 403
    assert bcn.delete(f"/api/v2/informes/programacio/{p['id']}").status_code == 403
    assert marca.delete(f"/api/v2/informes/programacio/{p['id']}").json() == {"ok": True}
    assert marca.delete(f"/api/v2/informes/programacio/{p['id']}").status_code == 404


# ---------------------------------------------------------------- Correu (SMTP fals)


class SMTPFals:
    enviats: list = []
    falla = False

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.tls, self.login_ = host, port, False, None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        pass

    def starttls(self, context=None):
        self.tls = True

    def login(self, u, c):
        self.login_ = (u, c)

    def send_message(self, m):
        if SMTPFals.falla:
            raise smtplib.SMTPRecipientsRefused({})
        SMTPFals.enviats.append((self, m))


@pytest.fixture
def smtp(monkeypatch):
    SMTPFals.enviats, SMTPFals.falla = [], False
    monkeypatch.setattr(smtplib, "SMTP", SMTPFals)
    return SMTPFals


def test_correu_modul(smtp):
    cfg = Config(smtp_host="smtp.prova.cat", smtp_port=587, smtp_usuari="u", smtp_contrasenya="c",
                 smtp_remitent="Hebra <informes@marca.cat>")
    assert correu.envia(cfg, [" a@marca.cat", "A@marca.cat", "b@marca.cat"], "Assumpte", "Text",
                        [("x.pdf", b"%PDF-1.7", "application/pdf")]) == ["a@marca.cat", "b@marca.cat"]
    s, m = smtp.enviats[0]
    assert s.tls and s.login_ == ("u", "c") and (s.host, s.port) == ("smtp.prova.cat", 587)
    assert m["To"] == "a@marca.cat, b@marca.cat" and m["Subject"] == "Assumpte"
    adj = [p for p in m.iter_attachments()]
    assert adj[0].get_filename() == "x.pdf" and adj[0].get_content_type() == "application/pdf"
    with pytest.raises(correu.ErrorCorreu, match="no està configurat"):
        correu.envia(Config(), ["a@marca.cat"], "A", "T")
    with pytest.raises(correu.ErrorCorreu, match="no vàlid"):
        correu.envia(cfg, ["a@marca"], "A", "T")
    smtp.falla = True
    with pytest.raises(correu.ErrorCorreu, match="No s'ha pogut enviar"):
        correu.envia(cfg, ["a@marca.cat"], "A", "T")


def test_envia_per_api(entorn, smtp):
    app_mod, con = entorn
    c = _client(app_mod, "marca@hebra.cat")
    lid = c.get("/api/v2/informes/lliurats?tipus=setmanal").json()["lliurats"][0]["id"]
    # sense SMTP: 400 amb el motiu
    r = c.post(f"/api/v2/informes/lliurats/{lid}/envia", json={"destinataris": ["a@marca.cat"]})
    assert r.status_code == 400 and r.json()["detail"] == "El correu no està configurat"
    assert c.post(f"/api/v2/informes/setmanal/envia?{F_SIM}",
                  json={"destinataris": ["a@marca.cat"]}).json()["detail"] == "El correu no està configurat"
    app_mod.app.state.cfg = Config(secret="secret-de-prova", smtp_host="smtp.prova.cat", smtp_remitent="i@marca.cat")
    try:
        r = c.post(f"/api/v2/informes/lliurats/{lid}/envia", json={"destinataris": ["no-valid"]})
        assert r.status_code == 400 and "no vàlid" in r.json()["detail"]
        r = c.post(f"/api/v2/informes/lliurats/{lid}/envia", json={"destinataris": ["a@marca.cat"]})
        assert r.status_code == 200 and r.json() == {"ok": True}
        _, m = smtp.enviats[-1]
        pdf = next(m.iter_attachments())
        assert pdf.get_content_type() == "application/pdf" and pdf.get_content().startswith(b"%PDF")
        fila = c.get("/api/v2/informes/lliurats?tipus=setmanal").json()["lliurats"][0]
        assert fila["estat_enviament"] == "enviat" and fila["enviat_a"] == ["a@marca.cat"]
        r = c.post(f"/api/v2/informes/diari/envia?{F_SIM}", json={"destinataris": ["b@marca.cat"]})
        assert r.status_code == 200 and len(smtp.enviats) == 2
        assert "Resum diari" in smtp.enviats[-1][1]["Subject"]
    finally:
        app_mod.app.state.cfg = app_mod.cfg


def test_bucle_genera_i_envia_el_que_toca(entorn, smtp):
    app_mod, con = entorn
    con.execute("DELETE FROM programacio_informe")
    con.execute("""INSERT INTO programacio_informe (botiga_id, tipus, actiu, hora, destinataris, creada)
                   VALUES ('BCN-01', 'diari', 1, '08:00', '["a@marca.cat"]', '2026-11-01T00:00:00+01:00')""")
    con.commit()
    cfg = Config(smtp_host="smtp.prova.cat", smtp_remitent="i@marca.cat")
    ara = datetime(2026, 11, 20, 8, 0, 30, tzinfo=MADRID)
    fets = ip.executa_pendents(con, cfg, ara)
    assert len(fets) == 1 and ip.executa_pendents(con, cfg, ara + timedelta(minutes=1)) == []
    f = ip.lliurat(con, fets[0])
    assert (f["des"], f["fins"], f["estat_enviament"]) == ("2026-11-19", "2026-11-19", "enviat")
    assert json.loads(f["dades_json"])["tipus"] == "diari" and len(smtp.enviats) == 1
    # sense SMTP es genera igual però no s'envia
    assert len(ip.executa_pendents(con, Config(), ara + timedelta(days=1))) == 1
    assert ip.lliurat(con, max(r[0] for r in con.execute("SELECT id FROM informe_lliurat")))["estat_enviament"] == "no_enviat"


def test_simulador_programacions_lliurats_i_tasques(entorn):
    _, con = entorn
    tipus = {r[0] for r in con.execute("SELECT tipus FROM programacio_informe")}
    assert tipus == {"diari", "setmanal", "mensual", "temporada"}
    assert con.execute("SELECT hora FROM programacio_informe WHERE tipus = 'setmanal'").fetchone()[0] == "08:00"
    n = dict(con.execute("SELECT tipus, COUNT(*) FROM informe_lliurat GROUP BY tipus").fetchall())
    assert n["diari"] == 7 and n["setmanal"] == 1     # una setmana simulada
    estats = {r[0] for r in con.execute("SELECT estat FROM tasca")}
    assert {"pendent", "feta"} <= estats
