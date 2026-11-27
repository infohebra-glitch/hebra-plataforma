"""v0.7: proves i compres per dia comparades (període anterior, any, col·lecció), franja i condicions del dia;
i la tria de gràfics de cada informe per part de la marca."""

from datetime import date

import pytest

from hebra import analitica as A, db, simulador
from hebra.analitica import informes_grafics as ig

F = A.Filtre("BCN-01", date(2026, 11, 23), date(2026, 11, 29))


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    c = db.connecta(str(tmp_path_factory.mktemp("cmp") / "cmp.db"))
    db.inicialitza(c)
    simulador.simula(c, date(2026, 11, 16), setmanes=2)
    yield c
    c.close()


def test_sense_comparar(con):
    r = A.comparativa(con, F)
    assert len(r["dies"]) == 7 and r["comparacio"] is None
    assert r["total"]["proves"] == sum(d["proves"] for d in r["dies"]) > 0
    assert "pluja" in r["condicions_disponibles"]


def test_periode_anterior_i_franja(con):
    r = A.comparativa(con, F, compara="anterior")
    c = r["comparacio"]
    assert (c["des"], c["fins"]) == ("2026-11-16", "2026-11-22") and len(c["dies"]) == 7
    assert c["total"]["proves"] > 0
    mati = A.comparativa(con, F, franja="mati")
    assert 0 < mati["total"]["proves"] < r["total"]["proves"]
    with pytest.raises(ValueError):
        A.comparativa(con, F, franja="nit")
    with pytest.raises(ValueError):
        A.comparativa(con, F, compara="res")


def test_condicions_del_dia(con):
    con.execute("INSERT INTO condicio_dia (botiga_id, data, condicio) VALUES ('BCN-01', '2026-11-24', 'pluja')")
    con.execute("INSERT INTO condicio_dia (botiga_id, data, condicio) VALUES ('BCN-01', '2026-11-26', 'pluja')")
    pluja = A.comparativa(con, F, condicio="pluja")
    assert pluja["total"]["dies"] == 2
    assert [d["data"] for d in pluja["dies"] if d["proves"] is not None] == ["2026-11-24", "2026-11-26"]
    sense = A.comparativa(con, F, condicio="!pluja")
    assert sense["total"]["dies"] == 5
    assert pluja["total"]["proves"] + sense["total"]["proves"] == A.comparativa(con, F)["total"]["proves"]


def test_colleccio(con):
    cid = con.execute("INSERT INTO colleccio (nom, des, fins) VALUES ('Tardor', '2026-11-16', '2026-11-20')").lastrowid
    r = A.comparativa(con, F, compara="colleccio", colleccio=cid)
    assert r["comparacio"]["etiqueta"] == "Tardor" and len(r["comparacio"]["dies"]) == 5
    assert A.colleccions(con)[0]["nom"] == "Tardor"
    with pytest.raises(ValueError):
        A.comparativa(con, F, compara="colleccio", colleccio=999)


def test_la_marca_tria_els_grafics(con):
    tots = A.informe(con, F, "setmanal")
    ids = [g["id"] for g in tots["grafics_disponibles"]]
    assert tots["grafics_triats"] is None and [g["id"] for g in tots["grafics"]] == ids
    ig.desa_grafics_triats(con, "setmanal", [ids[2], ids[0]])
    r = A.informe(con, F, "setmanal")
    assert [g["id"] for g in r["grafics"]] == [ids[2], ids[0]]
    assert len(r["grafics_disponibles"]) == len(ids)       # el catàleg sencer, per poder tornar-los a posar
    assert [g["id"] for g in A.informe(con, F, "mensual")["grafics"]]  # els altres tipus no canvien
    ig.desa_grafics_triats(con, "setmanal", None)
    assert len(A.informe(con, F, "setmanal")["grafics"]) == len(ids)


def test_api(tmp_path, monkeypatch):
    import importlib

    from fastapi.testclient import TestClient

    from hebra import auth
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "api.db"))
    monkeypatch.setenv("HEBRA_SECRET", "secret-de-prova")
    monkeypatch.setenv("HEBRA_FRONTEND_DIST", str(tmp_path / "no-hi-es"))
    monkeypatch.setattr(auth, "ITERACIONS", 1000)
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    con = app_mod.con
    simulador.simula(con, date(2026, 11, 16), setmanes=2)
    auth.crea_usuari(con, "marca@hebra.cat", "Marca", "marca", "contrasenya-marca")
    auth.crea_usuari(con, "bcn@hebra.cat", "BCN", "botiga", "contrasenya-bcn", "BCN-01")

    def client(correu):
        c = TestClient(app_mod.app)
        assert c.post("/api/v2/sessio", json={"correu": correu,
                                              "contrasenya": f"contrasenya-{correu.split('@')[0]}"}).status_code == 200
        return c

    m, b = client("marca@hebra.cat"), client("bcn@hebra.cat")
    q = "botiga=BCN-01&des=2026-11-23&fins=2026-11-29"
    r = m.get(f"/api/v2/comparativa?{q}&compara=anterior&franja=tarda")
    assert r.status_code == 200 and r.json()["comparacio"]["etiqueta"] == "Període anterior"
    assert m.get(f"/api/v2/comparativa?{q}&franja=nit").status_code == 422
    # Condicions: la botiga marca la seva; la marca pot marcar-les totes.
    assert b.post("/api/v2/condicions", json={"data": "2026-11-24", "condicio": "Pluja"}).json()["botigues"] == 1
    assert m.get(f"/api/v2/comparativa?{q}&condicio=pluja").json()["total"]["dies"] == 1
    assert b.delete("/api/v2/condicions?data=2026-11-24&condicio=pluja").json()["esborrades"] == 1
    # Col·leccions: només la marca.
    assert b.post("/api/v2/colleccions", json={"nom": "X", "des": "2026-01-01", "fins": "2026-02-01"}).status_code == 403
    assert m.post("/api/v2/colleccions", json={"nom": "X", "des": "2026-03-01", "fins": "2026-02-01"}).status_code == 422
    cid = m.post("/api/v2/colleccions", json={"nom": "Tardor", "des": "2026-11-16", "fins": "2026-11-22"}).json()["id"]
    assert m.get(f"/api/v2/comparativa?{q}&compara=colleccio&colleccio={cid}").json()["comparacio"]["etiqueta"] == "Tardor"
    # Tria de gràfics de l'informe: només la marca, i només ids que existeixen.
    ids = [g["id"] for g in m.get(f"/api/v2/informes/setmanal?{q}").json()["grafics_disponibles"]]
    assert b.put(f"/api/v2/informes/setmanal/grafics?{q}", json={"grafics": ids[:2]}).status_code == 403
    assert m.put(f"/api/v2/informes/setmanal/grafics?{q}", json={"grafics": ["no-existeix"]}).status_code == 400
    assert m.put(f"/api/v2/informes/setmanal/grafics?{q}", json={"grafics": ids[:2]}).json()["grafics_triats"] == ids[:2]
    assert [g["id"] for g in b.get(f"/api/v2/informes/setmanal?{q}").json()["grafics"]] == ids[:2]
    assert m.put(f"/api/v2/informes/setmanal/grafics?{q}", json={"grafics": None}).json()["grafics_triats"] is None
