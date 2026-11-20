"""Lot de prova: es carrega en una botiga pròpia i s'esborra sense tocar cap dada real."""

import importlib
from datetime import date

import pytest
from fastapi.testclient import TestClient

from hebra import analitica, auth, db, lot_prova, simulador
from hebra.analitica import Filtre


def _foto(con) -> dict:
    """Totes les files de totes les taules (menys la del lot), per comparar abans i després."""
    taules = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                        "AND name NOT LIKE 'sqlite_%' AND name != 'lot_prova'")]
    return {t: sorted(map(tuple, con.execute(f'SELECT * FROM "{t}"').fetchall())) for t in taules}


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    """Una base de dades amb dades «reals» (BCN-01, 1 setmana) i una configuració pròpia."""
    c = db.connecta(str(tmp_path_factory.mktemp("lot") / "lot.db"))
    db.inicialitza(c)
    simulador.simula(c, date(2026, 11, 2), setmanes=1)
    c.execute("INSERT INTO parametre (botiga_id, clau, valor) VALUES ('*', 'quota_mensual', '420') "
              "ON CONFLICT(botiga_id, clau) DO UPDATE SET valor = excluded.valor")
    c.commit()
    yield c
    c.close()


def test_carrega_i_esborra_sense_tocar_dades_reals(con):
    abans = _foto(con)
    real = analitica.resum(con, Filtre("BCN-01", date(2026, 11, 2), date(2026, 11, 8)))

    e = lot_prova.carrega(con, avui=date(2026, 11, 20))
    assert e["carregat"] and e["botiga_id"] == "PROVA-01" and e["resum"]["sessions"] > 0
    assert e["des"] == "2026-11-09" and e["fins"] == "2026-11-19"
    # Les dades de prova són a la seva botiga, amb les seves antenes, i la botiga real no canvia.
    assert con.execute("SELECT COUNT(*) FROM venda_linia WHERE botiga_id = 'PROVA-01'").fetchone()[0] > 0
    assert con.execute("SELECT COUNT(*) FROM antena WHERE id LIKE 'PROVA-R700:%'").fetchone()[0] == 3
    assert analitica.resum(con, Filtre("BCN-01", date(2026, 11, 2), date(2026, 11, 8))) == real
    # Cap paràmetre general ni cap programació d'informes de tota la marca; cap destinatari.
    assert con.execute("SELECT valor FROM parametre WHERE botiga_id = '*' AND clau = 'quota_mensual'").fetchone()[0] == "420"
    progs = con.execute("SELECT botiga_id, destinataris FROM programacio_informe WHERE botiga_id = 'PROVA-01'").fetchall()
    assert progs and all(p["destinataris"] == "[]" for p in progs)
    assert _foto(con)["programacio_informe"] != abans["programacio_informe"]
    # No es pot carregar dues vegades.
    with pytest.raises(lot_prova.ErrorLot):
        lot_prova.carrega(con, avui=date(2026, 11, 20))

    r = lot_prova.esborra(con)
    assert r["esborrat"] and r["files"] > 1000
    assert _foto(con) == abans  # exactament igual que abans de carregar-lo
    assert lot_prova.estat(con)["carregat"] is False
    with pytest.raises(lot_prova.ErrorLot):
        lot_prova.esborra(con)


def test_no_trepitja_una_botiga_real_amb_el_mateix_id(tmp_path):
    c = db.connecta(str(tmp_path / "x.db"))
    db.inicialitza(c)
    c.execute("INSERT INTO botiga (id, nom) VALUES ('PROVA-01', 'Una botiga real')")
    c.commit()
    with pytest.raises(lot_prova.ErrorLot):
        lot_prova.carrega(c, avui=date(2026, 11, 20))
    assert c.execute("SELECT nom FROM botiga WHERE id = 'PROVA-01'").fetchone()[0] == "Una botiga real"


def test_api(tmp_path, monkeypatch):
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "api.db"))
    monkeypatch.setenv("HEBRA_SECRET", "secret-de-prova")
    monkeypatch.setenv("HEBRA_FRONTEND_DIST", str(tmp_path / "no-hi-es"))
    monkeypatch.setattr(auth, "ITERACIONS", 1000)
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    auth.crea_usuari(app_mod.con, "marca@hebra.cat", "Marca", "marca", "contrasenya-marca")
    app_mod.con.execute("INSERT INTO botiga (id, nom) VALUES ('BCN-01', 'Barcelona')")
    auth.crea_usuari(app_mod.con, "bcn@hebra.cat", "BCN", "botiga", "contrasenya-bcn", "BCN-01")
    c = TestClient(app_mod.app)
    assert c.get("/api/v2/lot-prova").status_code == 401
    b = TestClient(app_mod.app)
    b.post("/api/v2/sessio", json={"correu": "bcn@hebra.cat", "contrasenya": "contrasenya-bcn"})
    assert b.post("/api/v2/lot-prova").status_code == 403  # una botiga no pot carregar ni esborrar el lot
    assert c.post("/api/v2/sessio", json={"correu": "marca@hebra.cat", "contrasenya": "contrasenya-marca"}).status_code == 200
    assert c.get("/api/v2/lot-prova").json()["carregat"] is False
    r = c.post("/api/v2/lot-prova")
    assert r.status_code == 200 and r.json()["carregat"] is True
    assert any(x["id"] == "PROVA-01" for x in c.get("/api/v2/jo").json()["botigues"])
    assert c.post("/api/v2/lot-prova").status_code == 409
    r = c.delete("/api/v2/lot-prova")
    assert r.status_code == 200 and r.json()["esborrat"] is True
    assert c.delete("/api/v2/lot-prova").status_code == 409
    assert app_mod.con.execute("SELECT COUNT(*) FROM botiga").fetchone()[0] == 1
