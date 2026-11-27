"""Seccions i motius «per què no» propis de la marca, escrits a mà al tauler."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from hebra import analitica, fitxa, fitxa_config
from hebra.analitica import Filtre

from test_v3_fitxa_sessions import _client, _peca, entorn  # noqa: F401  (fixture)

SECCIO = {"id": "p-arreglos", "titol": {"ca": "Arranjaments", "es": "Arreglos"},
          "text": {"ca": "Fem la vora gratis.\nEn 48 hores.", "es": "Cogemos el bajo gratis."}, "plegable": False}
MOTIU = {"id": "p-massa-llarg", "text": {"ca": "És massa llarg", "es": "Es demasiado largo"}}


def test_desa_seccions_i_motius_propis(entorn):
    app_mod, _ = entorn
    c = _client(app_mod, "marca@hebra.cat")
    r = c.put("/api/v2/fitxa/config", json={
        "seccions_propies": [SECCIO], "motius_propis": [MOTIU],
        "motius": ["preu", "p-massa-llarg"],
        "textos_motius": {"preu": {"ca": "Ara no m'ho puc permetre"}},
    })
    assert r.status_code == 200, r.text
    ef = r.json()["efectiva"]
    assert ef["seccions"]["ordre"][-1] == "p-arreglos"  # una secció nova va al final
    assert ef["motius"] == ["preu", "p-massa-llarg"]
    # Esborrar la secció la treu també de l'ordre; esborrar el motiu el treu de la llista.
    r = c.put("/api/v2/fitxa/config", json={"seccions_propies": [], "motius_propis": []}).json()["efectiva"]
    assert "p-arreglos" not in r["seccions"]["ordre"] and r["motius"] == ["preu"]


@pytest.mark.parametrize("cos", [
    {"seccions_propies": [{"id": "arreglos", "titol": {"ca": "x"}, "text": {"ca": "y"}}]},     # sense «p-»
    {"seccions_propies": [{"id": "p-a", "titol": {}, "text": {"ca": "y"}}]},                  # sense títol
    {"seccions_propies": [SECCIO, SECCIO]},                                                  # repetida
    {"seccions_propies": [{**SECCIO, "html": "<b>"}]},                                       # camp desconegut
    {"seccions_propies": [{**SECCIO, "titol": {"xx": "x"}}]},                                # idioma desconegut
    {"motius_propis": [{"id": "p-x", "text": {"ca": "x" * 81}}]},                            # massa llarg
    {"motius_propis": [{"id": f"p-{i}", "text": {"ca": "x"}} for i in range(11)]},          # massa motius
    {"textos_motius": {"inventat": {"ca": "x"}}},
    {"motius": ["P-MAJUSCULES"]},
])
def test_validacio(entorn, cos):
    app_mod, _ = entorn
    r = _client(app_mod, "marca@hebra.cat").put("/api/v2/fitxa/config", json=cos)
    assert r.status_code == 400 and r.json()["detail"]


def test_la_fitxa_ensenya_seccio_i_motius_propis(entorn):
    app_mod, con = entorn
    p = _peca(con)
    fitxa_config.desa(con, None, {"seccions_propies": [SECCIO, {**SECCIO, "id": "p-plegada", "plegable": True}],
                                  "motius_propis": [MOTIU], "motius": ["preu", "p-massa-llarg"],
                                  "textos_motius": {"preu": {"ca": "Ara no m'ho puc permetre"}}})
    _dins_del_provador(con, p["epc"])
    c = TestClient(app_mod.app)
    html = c.get(f"/p/{p['nfc_token']}?b=BCN-01&lang=ca&s=sessio-prova-1").text
    assert "Arranjaments" in html and "<p>Fem la vora gratis.</p>" in html and "<p>En 48 hores.</p>" in html
    assert 'data-seccio="p-plegada"' in html  # la plegable registra quan s'obre
    assert 'value="p-massa-llarg" >És massa llarg<' in html
    assert "Ara no m&#39;ho puc permetre" in html
    html_es = c.get(f"/p/{p['nfc_token']}?b=BCN-01&lang=es&s=sessio-prova-1").text
    assert "Arreglos" in html_es and "Es demasiado largo" in html_es

    # El client tria el motiu propi; el tauler en mostra el text de la marca.
    r = c.post(f"/p/{p['nfc_token']}/motiu", data={"motiu": "p-massa-llarg", "b": "BCN-01", "s": "sessio-prova-1",
                                                   "lang": "ca"}, follow_redirects=False)
    assert r.status_code == 303
    m = analitica.motius(con, Filtre("BCN-01", date(2000, 1, 1), date(2100, 1, 1)))
    assert m["per_motiu"][0]["motiu"] == "p-massa-llarg" and m["etiquetes"]["p-massa-llarg"] == "És massa llarg"
    # Un motiu propi que no és a la configuració no s'accepta.
    r = c.post(f"/p/{p['nfc_token']}/motiu", data={"motiu": "p-inventat", "b": "BCN-01", "s": "sessio-prova-2",
                                                   "lang": "ca"}, follow_redirects=False)
    assert r.status_code == 400
    # Obrir la secció plegable queda registrat; una secció pròpia inexistent, no.
    assert c.post(f"/p/{p['nfc_token']}/seccio", data={"seccio": "p-plegada", "b": "BCN-01", "s": "sessio-prova-1",
                                                       "lang": "ca"}).status_code == 204
    assert c.post(f"/p/{p['nfc_token']}/seccio", data={"seccio": "p-no-hi-es", "b": "BCN-01", "s": "sessio-prova-1",
                                                       "lang": "ca"}).status_code == 400


def test_motius_pagina_respecta_ordre(entorn):
    cfg = fitxa_config.normalitza(fitxa_config.fusiona(fitxa_config.DEFECTE, {
        "motius_propis": [MOTIU], "motius": ["p-massa-llarg", "talla"]}))
    assert [k for k, _ in fitxa.motius_pagina(cfg, "ca")] == ["p-massa-llarg", "talla"]


def _dins_del_provador(con, epc, botiga="BCN-01"):
    """v0.8: la fitxa ensenya talla, assistència i motius només si el lector té la peça ara dins d'una cabina."""
    from datetime import datetime, timedelta
    from hebra import temps
    ara = datetime.fromisoformat(temps.ara())
    antena = con.execute("SELECT a.id FROM antena a JOIN cabina c ON c.id = a.cabina_id WHERE c.botiga_id = ? "
                         "ORDER BY a.id LIMIT 1", (botiga,)).fetchone()["id"]
    con.execute("INSERT INTO lectura_agregada (epc, antena_id, inici, fi, n_lectures, rssi_max, rssi_mitja) "
                "VALUES (?, ?, ?, ?, 10, -40, -45)",
                (epc, antena, (ara - timedelta(seconds=20)).isoformat(timespec="seconds"), ara.isoformat(timespec="seconds")))
    con.commit()
