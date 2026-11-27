"""v0.9: devolucions online importades i comparades amb el motiu de no compra del provador."""

import importlib
from datetime import date

import pytest

from hebra import analitica as A, db, devolucions as dev, fitxa, lot_prova, simulador
from hebra.analitica import informes_grafics as ig

F = A.Filtre(None, date(2026, 11, 16), date(2026, 11, 29))


@pytest.fixture
def con(tmp_path):
    c = db.connecta(str(tmp_path / "dev.db"))
    db.inicialitza(c)
    simulador.simula(c, date(2026, 11, 16), setmanes=2)
    yield c
    c.close()


def _gtins(c, model="CL-24-NAT"):
    return {r["talla"]: r["gtin"] for r in c.execute("SELECT gtin, talla FROM catalog_sku WHERE model = ?", (model,))}


@pytest.mark.parametrize("text,esperat", [
    ("TALLA PEQUEÑA", ("talla", "petita")), ("Too big", ("talla", "gran")), ("No em queda bé", ("talla", None)),
    ("No es como en la foto", ("diferent_foto", None)), ("Llegó tarde", ("enviament", None)),
    ("Defectuoso", ("defecte", None)), ("Calidad del tejido", ("qualitat", None)), ("COLOR DIFERENTE", ("color", None)),
    ("No me favorece", ("tall", None)), ("Ya no lo quiero", ("canvi_opinio", None)), ("Precio", ("preu", None)),
    ("xyz", (None, None)), ("", (None, None)), ("Talla equivocada", ("talla", None)), ("granate", (None, None)),
])
def test_classifica(text, esperat):
    assert dev.classifica(text) == esperat


def test_importa_sense_dades_personals_ni_duplicats(con):
    g = _gtins(con)
    csv = ("Fecha;EAN;Cantidad;Motivo;Comentario;Pedido;Email cliente;Nombre\n"
           f"2026-11-20;{g['M']};1;TALLA PEQUEÑA;;PED-1;anna@exemple.com;Anna\n"
           f"21/11/2026;{g['L']};2;OTRO;me queda enorme, llamadme al 600 123 456;PED-2;joan@exemple.com;Joan\n"
           f"2026-11-22;00000000000000;1;PRECIO;;PED-3;x@y.z;X\n")
    r = dev.importa_csv(con, csv)
    assert r["importades"] == 2 and len(r["errors"]) == 1 and "catàleg" in r["errors"][0]
    assert any("Email cliente" in a and "Nombre" in a for a in r["avisos"])
    # Res personal a la base de dades: ni correus, ni noms, ni el comentari, ni el telèfon, ni la comanda en clar.
    bolcat = "\n".join(con.iterdump())
    for prohibit in ("anna@", "Anna", "Joan", "600 123", "llamadme", "PED-1", "enorme"):
        assert prohibit not in bolcat, prohibit
    # El comentari s'ha fet servir per classificar l'«OTRO» (i després s'ha llençat).
    fil = {x["talla"]: x for x in dev.files(con, "2026-11-01", "2026-12-01")}
    assert (fil["M"]["motiu"], fil["M"]["sentit"]) == ("talla", "petita")
    assert (fil["L"]["motiu"], fil["L"]["sentit"], fil["L"]["quantitat"]) == ("talla", "gran", 2)
    # Tornar a pujar el mateix fitxer no duplica res.
    r2 = dev.importa_csv(con, csv)
    assert r2["importades"] == 0 and r2["repetides"] == 2


def test_columnes_obligatories(con):
    assert "Falten columnes" in dev.importa_csv(con, "data,motiu\n2026-11-20,talla\n")["errors"][0]
    assert "motiu" in dev.importa_csv(con, "data,gtin\n2026-11-20,1\n")["errors"][0]


def test_mapa_manual_canvia_la_comparativa(con):
    g = _gtins(con)
    dev.importa_csv(con, "data,gtin,motiu\n" + "".join(f"2026-11-2{i},{g['M']},R07\n" for i in range(6)))
    m = {x["codi"]: x for x in dev.llista_mapa(con)["codis"]}
    assert m["r07"]["motiu"] == "altre" and m["r07"]["unitats"] == 6 and not m["r07"]["manual"]
    dev.desa_mapa(con, "r07", "talla", "gran")
    r = A.provador_online(con, F, "CL-24-NAT")
    assert r["devolucions_online"] == 6 and r["talla_sentit"]["online"]["gran"] == 6
    with pytest.raises(ValueError):
        dev.desa_mapa(con, "r07", "inventat", None)
    with pytest.raises(ValueError):
        dev.desa_mapa(con, "r07", "preu", "gran")
    with pytest.raises(KeyError):
        dev.desa_mapa(con, "no-hi-es", "preu", None)


def test_coincidencia():
    from collections import Counter

    from hebra.analitica.devolucions import coincidencia
    cats = {"talla", "preu", "color"}
    assert coincidencia(Counter(talla=5, preu=5), Counter(talla=10, preu=10), cats) == 1.0
    assert coincidencia(Counter(talla=10), Counter(preu=10), cats) == 0.0
    assert coincidencia(Counter(talla=4), Counter(talla=10), cats) is None  # poques respostes


def test_comparativa_per_model(con):
    g = _gtins(con)
    for i in range(6):
        fitxa.registra(con, f"s{i}", "BCN-01", g["M"], "motiu_no_compra", "ca", "preu", ts=f"2026-11-2{i}T12:00:00+01:00")
    dev.importa_csv(con, "data,gtin,motiu\n" + "".join(f"2026-11-2{i},{g['M']},No es como en la foto\n" for i in range(4))
                    + "".join(f"2026-11-2{i},{g['M']},Precio\n" for i in range(3)))
    r = A.provador_online(con, F)
    fila = next(m for m in r["models"] if m["model"] == "CL-24-NAT")
    assert fila["devolucions_online"] == 7 and fila["nomes_online"] == 4 and fila["motiu_online"] == "diferent_foto"
    assert r["pct_nomes_online"] is not None and r["nomes_online_detall"][0]["motiu"] == "diferent_foto"
    assert "nomes_mirava" not in {c["motiu"] for c in r["categories"]}
    assert r["text"]
    d = A.model_detall(con, F, "CL-24-NAT")["provador_online"]
    assert d["devolucions_online"] == 7 and d["lectura"]


def test_sense_devolucions_res_a_la_fitxa_ni_a_l_informe(con):
    assert A.model_detall(con, F, "CL-24-NAT")["provador_online"] is None
    assert "provador_online" not in {g["id"] for g in A.informe(con, F, "mensual")["grafics"]}
    assert A.provador_online(con, F)["devolucions_online"] == 0


def test_grafic_a_l_informe(con):
    dev.simula(con, F.des, F.fins, [r[0] for r in con.execute("SELECT gtin FROM catalog_sku")])
    inf = A.informe(con, F, "mensual")
    g = next(x for x in inf["grafics"] if x["id"] == "provador_online")
    assert [s["nom"] for s in g["series"]] == ["Provador", "Online"] and g["lectura"]
    assert "provador_online" not in {x["id"] for x in A.informe(con, F, "setmanal")["grafics"]}
    from hebra import grafics_svg
    assert "<svg" in grafics_svg.svg(g)
    assert ig.llegeix(g)


def test_lot_de_prova_les_porta_i_les_esborra(tmp_path):
    c = db.connecta(str(tmp_path / "lot.db"))
    db.inicialitza(c)
    dev_real = None
    simulador.prepara_botiga(c)
    gtin_real = c.execute("SELECT gtin FROM catalog_sku LIMIT 1").fetchone()[0]
    dev_real = dev.importa_csv(c, f"data,gtin,motiu\n2026-11-20,{gtin_real},Precio\n")
    assert dev_real["importades"] == 1
    lot_prova.carrega(c, avui=date(2026, 11, 27))
    assert c.execute("SELECT COUNT(*) FROM devolucio_online WHERE lot_prova = 1").fetchone()[0] > 0
    lot_prova.esborra(c)
    assert c.execute("SELECT COUNT(*) FROM devolucio_online WHERE lot_prova = 1").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM devolucio_online").fetchone()[0] == 1  # les reals no es toquen
    c.close()


def test_api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from hebra import auth
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "api.db"))
    monkeypatch.setenv("HEBRA_SECRET", "secret-de-prova")
    monkeypatch.setenv("HEBRA_FRONTEND_DIST", str(tmp_path / "no-hi-es"))
    monkeypatch.setattr(auth, "ITERACIONS", 1000)
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    c = app_mod.con
    simulador.simula(c, date(2026, 11, 16), setmanes=1)
    auth.crea_usuari(c, "marca@hebra.cat", "Marca", "marca", "contrasenya-marca")
    auth.crea_usuari(c, "bcn@hebra.cat", "BCN", "botiga", "contrasenya-bcn", "BCN-01")
    g = _gtins(c)

    def client(correu):
        cl = TestClient(app_mod.app)
        assert cl.post("/api/v2/sessio", json={"correu": correu, "contrasenya": f"contrasenya-{correu.split('@')[0]}"}).status_code == 200
        return cl

    fitxer = {"fitxer": ("dev.csv", f"data,gtin,motiu\n2026-11-20,{g['M']},Talla pequeña\n".encode(), "text/csv")}
    botiga = client("bcn@hebra.cat")
    assert botiga.post("/api/v2/importa/devolucions", files=fitxer).status_code == 403
    assert botiga.get("/api/v2/provador-online").status_code == 403
    marca = client("marca@hebra.cat")
    r = marca.post("/api/v2/importa/devolucions", files=fitxer)
    assert r.status_code == 200 and r.json()["importades"] == 1
    r = marca.get("/api/v2/provador-online", params={"des": "2026-11-16", "fins": "2026-11-22"})
    assert r.status_code == 200 and r.json()["devolucions_online"] == 1
    mapa = marca.get("/api/v2/devolucions/mapa").json()
    assert mapa["codis"][0]["codi"] == "talla pequeña" and mapa["importat"]["linies"] == 1
    assert marca.put("/api/v2/devolucions/mapa", json={"codi": "talla pequeña", "motiu": "tall"}).status_code == 200
    assert marca.put("/api/v2/devolucions/mapa", json={"codi": "talla pequeña", "motiu": "res"}).status_code == 422
    assert marca.delete("/api/v2/devolucions").json()["esborrades"] == 1
