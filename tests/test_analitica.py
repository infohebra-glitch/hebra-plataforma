"""Forma de les respostes de hebra.analitica (docs/API.md) sobre 2 setmanes simulades, i rendiment."""

import json
import time
from datetime import date

import pytest

from hebra import analitica as A, db, informes, simulador

F = A.Filtre("BCN-01", date(2026, 11, 23), date(2026, 11, 29))
TOTES = A.Filtre(None, date(2026, 11, 16), date(2026, 11, 29))


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    c = db.connecta(str(tmp_path_factory.mktemp("sim") / "sim.db"))
    db.inicialitza(c)
    simulador.simula(c, date(2026, 11, 16), setmanes=2)
    yield c
    c.close()


def claus(d: dict, *esperades: str) -> None:
    assert set(d) == set(esperades), set(d) ^ set(esperades)


ACCIO = ("text", "insight", "model", "responsable", "data_limit")
EXPERIMENT = ("id", "variable", "hipotesi", "unitat", "inici", "fi", "estat", "grups", "diferencia", "ic95",
              "p_valor", "proves_minimes", "mostra_suficient", "proves_necessaries", "setmanes_restants", "conclusio")


def test_resum(con):
    r = A.resum(con, F)
    claus(r, "periode", "kpi", "serie_diaria", "accio", "alertes_obertes")
    assert r["periode"] == {"des": "2026-11-23", "fins": "2026-11-29", "dies": 7}
    claus(r["kpi"], "proves", "compres_atribuides", "conversio", "conversio_periode_anterior", "variacio_conversio",
          "sessions", "peces_per_sessio", "unitats_venudes", "venut_sense_provar", "venut_sense_provar_pct",
          "peticions_talla", "temps_resposta_mediana_s", "pct_resposta_sota_90s", "peces_abandonades",
          "demanda_perduda", "respostes_motiu", "taxa_resposta_motiu", "proves_ambigues")
    k = r["kpi"]
    assert k["proves"] > 300 and 0 < k["conversio"] < 1 and k["peces_abandonades"] >= 1
    assert len(r["serie_diaria"]) == 7
    claus(r["serie_diaria"][0], "data", "proves", "compres", "conversio", "grup_origen")
    assert {d["grup_origen"] for d in r["serie_diaria"]} <= {"amb", "sense", None}
    claus(r["accio"], *ACCIO)
    assert r["alertes_obertes"] >= 3


def test_models_i_detall(con):
    ms = A.models(con, F)["models"]
    claus(ms[0], "model", "nom", "categoria", "preu", "proves", "compres", "conversio", "conversio_categoria",
          "quartil_categoria", "molt_provat_poc_venut", "venut_sense_provar", "estoc", "motiu_principal",
          "demanda_perduda")
    marcats = [m["model"] for m in ms if m["molt_provat_poc_venut"]]
    assert marcats == ["VV-26-VRD"]  # el vestit "es prova i no es ven"
    d = A.model_detall(con, F, "CL-24-NAT")
    claus(d, "model", "nom", "categoria", "color", "preu", "kpi", "talles", "motius", "serie_setmanal",
          "provat_amb", "origen", "efecte_origen", "dubte_talla")
    claus(d["kpi"], "proves", "compres", "conversio", "venut_sense_provar", "respostes_motiu", "taxa_resposta_motiu")
    claus(d["talles"][0], "talla", "gtin", "proves", "compres", "conversio", "pct_proves", "pct_compres", "estoc",
          "demanda_perduda", "canvis_de_talla")
    assert [t["talla"] for t in d["talles"]] == ["S", "M", "L", "XL"]
    claus(d["origen"], "etapes", "composicio")
    claus(d["efecte_origen"], *EXPERIMENT)
    assert A.model_detall(con, F, "NO-EXISTEIX") is None


def test_talles_demanda_motius(con):
    t = A.talles(con, F)
    claus(t, "taula", "no_quadra", "corba")
    claus(t["taula"][0], "categoria", "talla", "proves", "compres", "conversio")
    claus(t["corba"][0], "model", "nom", "talles")
    claus(t["corba"][0]["talles"][0], "talla", "pct_proves", "pct_compres", "pct_estoc", "proposta_pct")
    for nq in t["no_quadra"]:
        claus(nq, "model", "nom", "talla", "conversio", "conversio_resta_talles", "text")
    d = A.demanda_perduda(con, F)
    claus(d, "total", "per_variant", "text")
    assert d["total"] >= 3
    claus(d["per_variant"][0], "model", "nom", "color", "talla", "n", "estoc")
    m = A.motius(con, F)
    claus(m, "respostes", "sessions_fitxa", "taxa_resposta", "per_motiu", "per_model")
    assert set(p["motiu"] for p in m["per_motiu"]) <= {"talla", "tall", "preu", "color", "qualitat", "altre"}


def test_servei_estoc_fitxa(con):
    s = A.servei(con, F)
    claus(s, "peticions", "peticions_assistencia", "peticions_per_sessio", "mediana_s", "pct_sota_90s", "per_estat", "ocupacio",
          "peces_per_sessio")
    claus(s["per_estat"], "pendent", "en_cami", "lliurada", "no_disponible")
    assert s["per_estat"]["en_cami"] + s["per_estat"]["pendent"] >= 1
    claus(s["ocupacio"], "durada_mitjana_s", "pct_temps_totes_plenes", "mapa")
    claus(s["ocupacio"]["mapa"][0], "dia_setmana", "hora", "sessions", "pct_totes_plenes")
    claus(s["peces_per_sessio"][0], "peces", "sessions", "pct_amb_compra")
    e = A.estoc(con, F)
    claus(e, "parat", "resum_parat", "risc_rebaixa", "precisio")
    assert {p["model"] for p in e["parat"]} == {"FL-25-GRS"}
    claus(e["parat"][0], "gtin", "model", "nom", "color", "talla", "categoria", "botiga_id", "unitats", "valor_eur",
          "dies_parat", "dies_sense_activitat", "darrera_prova", "darrera_venda", "proves_altres_botigues",
          "vendes_altres_botigues", "suggeriment", "tasca")
    assert all(p["dies_sense_activitat"] >= 21 for p in e["parat"])
    claus(e["risc_rebaixa"][0], "model", "nom", "unitats", "cobertura_setmanes", "conversio", "quartil_categoria")
    claus(e["precisio"], "recomptes", "error_mitja_pct")
    n = A.fitxa_nfc(con, F)
    claus(n, "tocs", "sessions_cabina", "tocs_per_sessio", "seccions", "idiomes")
    seccions = {x["seccio"]: x["n"] for x in n["seccions"]}
    assert set(seccions) == {"origen", "talles", "cura", "preguntes", "motiu", "peticio_talla"}
    assert seccions["talles"] > 0 and seccions["origen"] > 0


def test_experiments_alertes_valor(con):
    exps = A.experiments(con, F)["experiments"]
    assert [x["id"] for x in exps] == ["origen-2026-11"]  # l'experiment de la taula, no un de sintètic
    claus(exps[0], *EXPERIMENT)
    claus(exps[0]["grups"]["amb"], "proves", "compres", "conversio")
    assert exps[0]["proves_minimes"] == 30 and exps[0]["mostra_suficient"]
    al = A.alertes(con, F)["alertes"]
    tipus = {a["tipus"] for a in al}
    assert {"peticio_talla", "talla_esgotada", "peca_abandonada", "molt_provat_poc_venut"} <= tipus
    claus(al[0], "id", "tipus", "text", "botiga_id", "cabina", "creada", "estat", "ref")
    v = A.valor(con, F)
    claus(v, "parametres", "llindar_peces_mes", "palanques")
    assert v["parametres"]["marge_peca"] == 40 and v["parametres"]["quota_mensual"] == 350
    assert v["llindar_peces_mes"] == 9
    for p in v["palanques"]:
        claus(p, "palanca", "insights", "formula", "valor_eur", "detall", "es_estimacio")
        assert p["es_estimacio"] is True


@pytest.mark.parametrize("tipus", ["diari", "setmanal", "mensual", "temporada", "pilot", "mango"])
def test_informes(con, tipus):
    r = A.informe(con, F, tipus)
    claus(r, "tipus", "titol", "periode", "blocs", "accio", "avisos", "xifres", "grafics")
    assert r["tipus"] == tipus and r["blocs"] and r["xifres"] and r["grafics"]
    for g in r["grafics"]:
        claus(g, "id", "titol", "tipus", "unitat", "eix_x", "series", "nota")
        assert g["tipus"] in ("linia", "barres", "barres_apilades", "donut")
        assert all(len(s["valors"]) == len(g["eix_x"]) for s in g["series"])
    for x in r["xifres"]:
        assert {"etiqueta", "valor", "unitat", "variacio", "vs"} <= set(x)
    for b in r["blocs"]:
        claus(b, "id", "titol", "text", "dades")
    claus(r["accio"], *ACCIO)
    assert r["accio"]["responsable"] in ("CEO", "PROD", "BOT", "MKT", "SOST")
    assert any(a.startswith("Dades simulades") for a in r["avisos"])
    json.dumps(r)  # serialitzable


def test_informe_desconegut(con):
    with pytest.raises(ValueError):
        A.informe(con, F, "anual")


def test_informe_pilot_criteris(con):
    r = A.informe(con, F, "pilot")
    criteris = next(b for b in r["blocs"] if b["id"] == "criteris")["dades"]
    assert len(criteris) == 4 and all(c["compleix"] is not None for c in criteris)


def test_totes_les_botigues(con):
    assert A.resum(con, TOTES)["kpi"]["proves"] == A.resum(con, A.Filtre("BCN-01", TOTES.des, TOTES.fins))["kpi"]["proves"]
    assert A.informe(con, TOTES, "setmanal")["blocs"]


def test_historial_i_perdues(con):
    epc = con.execute("SELECT epc FROM prova LIMIT 1").fetchone()[0]
    h = A.historial_peca(con, epc)
    claus(h, "epc", "gtin", "model", "nom", "talla", "esdeveniments")
    assert {e["tipus"] for e in h["esdeveniments"]} <= {"prova", "venda", "abandonada", "nfc"}
    claus(h["esdeveniments"][0], "ts", "tipus", "detall")
    assert A.historial_peca(con, "urn:no:existeix") is None
    assert A.perdues(con, F) == {"actiu": False, "per_zona_hora": [], "total": 0}


def test_informe_html_antic_coherent(con):
    r = informes.setmanal(con, "BCN-01", date(2026, 11, 23))
    k = A.resum(con, F)["kpi"]
    assert r["totals"]["proves"] == k["proves"] and r["totals"]["conversio"] == k["conversio"]
    assert any(m["alerta"] for m in r["models"] if m["model"] == "VV-26-VRD")


def test_rendiment(con):
    for fn in (A.resum, A.models, A.talles, A.servei, A.estoc, A.experiments, A.alertes, A.valor):
        t = time.perf_counter()
        fn(con, F)
        assert time.perf_counter() - t < 0.5, fn.__name__
