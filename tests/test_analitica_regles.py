"""Regles de negoci de hebra.analitica amb dades fetes a mà (sense simulador)."""

from datetime import date, datetime, timedelta

import pytest

from hebra import analitica as A
from hebra.analitica import estadistica

B = "T-01"
CAB = "T-01-C1"
DILLUNS = date(2026, 11, 16)
F = A.Filtre(B, DILLUNS, DILLUNS + timedelta(days=6))


@pytest.fixture
def t(con):
    con.execute("INSERT INTO botiga (id, nom) VALUES (?, 'Prova')", (B,))
    con.execute("INSERT INTO cabina (id, botiga_id, nom) VALUES (?, ?, 'Cabina 1')", (CAB, B))
    return Constructor(con)


class Constructor:
    def __init__(self, con):
        self.con = con
        self.n = 0

    def sku(self, gtin, model, talla, categoria="texans", preu=50.0):
        self.con.execute("""INSERT INTO catalog_sku (gtin, model, color, talla, categoria, preu_eur)
                            VALUES (?, ?, 'Blau', ?, ?, ?)""", (gtin, model, talla, categoria, preu))

    def proves(self, gtin, n, venudes, dia=DILLUNS, grup=None, confianca="alta"):
        """`n` proves del GTIN, cada una a la seva sessió; les `venudes` primeres amb venda atribuïda."""
        for i in range(n):
            self.n += 1
            inici = datetime(dia.year, dia.month, dia.day, 10, tzinfo=None) + timedelta(minutes=self.n)
            ts = inici.isoformat() + "+01:00"
            fi = (inici + timedelta(seconds=200)).isoformat() + "+01:00"
            s = self.con.execute("INSERT INTO sessio (cabina_id, inici, fi, grup) VALUES (?, ?, ?, ?)",
                                 (CAB, ts, fi, grup)).lastrowid
            p = self.con.execute("""INSERT INTO prova (sessio_id, epc, gtin, durada_s, n_lectures, rssi_mitja, confianca)
                                    VALUES (?, ?, ?, 120, 20, -50, ?)""", (s, f"epc-{gtin}-{self.n}", gtin, confianca)).lastrowid
            if i < venudes:
                v = self.con.execute("""INSERT INTO venda_linia (botiga_id, ts, data, gtin, quantitat, import_eur)
                                        VALUES (?, ?, ?, ?, 1, 50)""", (B, fi, dia.isoformat(), gtin)).lastrowid
                self.con.execute("INSERT INTO atribucio (prova_id, venda_id, regla) VALUES (?, ?, 'mateix_gtin_hora')",
                                 (p, v))

    def peticio(self, gtin, hora, disponible=0, estat="pendent"):
        self.con.execute("""INSERT INTO peticio_talla (sessio_nfc, botiga_id, gtin_origen, gtin_demanat, talla_demanada,
                                                      cabina, estat, hora_peticio, disponible)
                            VALUES ('s', ?, ?, ?, 'L', ?, ?, ?, ?)""", (B, gtin, gtin, CAB, estat, hora, disponible))


def test_parametre_botiga_general_i_defecte(con, t):
    assert A.parametre(con, B, "marge_peca", 40) == 40
    con.execute("INSERT INTO parametre VALUES ('*', 'marge_peca', '35')")
    assert A.parametre(con, B, "marge_peca", 40) == 35
    con.execute("INSERT INTO parametre VALUES (?, 'marge_peca', '32.5')", (B,))
    assert A.parametre(con, B, "marge_peca", 40) == 32.5
    assert A.parametre(con, None, "marge_peca", 40) == 35
    assert A.parametre(con, B, "shopify_domini", None) is None


def test_molt_provat_poc_venut(con, t):
    for m, cat in (("A", "texans"), ("B", "camisa"), ("C", "jersei"), ("D", "vestit"), ("E", "faldilla")):
        t.sku(f"g{m}", m, "M", cat)
    t.proves("gA", 40, 4)     # 10 %: molt per sota
    t.proves("gB", 40, 16)
    t.proves("gC", 40, 14)
    t.proves("gD", 40, 15)
    t.proves("gE", 5, 0)      # poc provat: no compta encara que no es vengui
    t.proves("gB", 3, 0, confianca="ambigua")  # no compten
    files = {m["model"]: m for m in A.models(con, F)["models"]}
    assert files["A"]["molt_provat_poc_venut"] and files["A"]["quartil_categoria"] == 1
    assert not files["B"]["molt_provat_poc_venut"] and not files["E"]["molt_provat_poc_venut"]
    assert files["B"]["proves"] == 40 and files["A"]["conversio"] == 0.1
    assert A.resum(con, F)["kpi"]["proves_ambigues"] == 3
    accio = A.resum(con, F)["accio"]
    assert accio["insight"] == "molt_provat_poc_venut" and accio["model"] == "A" and accio["responsable"] == "PROD"
    assert any(a["tipus"] == "molt_provat_poc_venut" and a["ref"] == "A" for a in A.alertes(con, F)["alertes"])


def test_molt_provat_quartil_dins_la_categoria(con, t):
    # 4 models de la mateixa categoria: mana el quartil inferior, no el 60 %.
    for i, venudes in enumerate((8, 9, 10, 11)):
        t.sku(f"g{i}", f"M{i}", "M", "texans")
        t.proves(f"g{i}", 20, venudes)
    files = {m["model"]: m for m in A.models(con, F)["models"]}
    assert [m for m in files if files[m]["molt_provat_poc_venut"]] == ["M0"]
    assert files["M0"]["conversio_categoria"] == round(38 / 80, 3)


def test_talla_que_no_quadra_i_corba(con, t):
    for talla, g in (("38", "t38"), ("40", "t40"), ("42", "t42")):
        t.sku(g, "TX", talla)
    t.proves("t38", 20, 2)
    t.proves("t40", 20, 8)
    t.proves("t42", 20, 6)
    nq = A.talles(con, F)["no_quadra"]
    assert [(x["model"], x["talla"]) for x in nq] == [("TX", "38")]
    assert nq[0]["conversio"] == 0.1 and nq[0]["conversio_resta_talles"] == 0.35
    assert "1 de cada 10" in nq[0]["text"] and "patró de la 38" in nq[0]["text"]

    con.executemany("INSERT INTO estoc (botiga_id, gtin, unitats, actualitzat) VALUES (?, ?, ?, '2026-11-22')",
                    [(B, "t38", 6), (B, "t40", 2), (B, "t42", 2)])
    corba = {x["talla"]: x for x in A.talles(con, F)["corba"][0]["talles"]}
    # 38: 0,7 × 2/16 + 0,3 × 1/3 = 0,1875 -> 0,20 ; 40: 0,7 × 0,5 + 0,1 = 0,45
    assert corba["38"]["proposta_pct"] == 0.2 and corba["40"]["proposta_pct"] == 0.45
    assert corba["38"]["pct_estoc"] == 0.6 and corba["40"]["pct_compres"] == 0.5


def test_estoc_parat_i_risc(con, t):
    t.sku("vell", "V", "M")
    t.sku("viu", "W", "M")
    t.sku("zero", "Z", "M")
    t.proves("vell", 1, 0, dia=DILLUNS - timedelta(days=30))   # última activitat fa 36 dies
    t.proves("viu", 12, 1, dia=DILLUNS + timedelta(days=2))
    con.executemany("INSERT INTO estoc (botiga_id, gtin, unitats, actualitzat) VALUES (?, ?, ?, '2026-11-22')",
                    [(B, "vell", 5), (B, "viu", 40), (B, "zero", 0)])
    e = A.estoc(con, F)
    assert [(p["gtin"], p["unitats"], p["dies_sense_activitat"]) for p in e["parat"]] == [("vell", 5, 36)]
    assert {r["model"] for r in e["risc_rebaixa"]} == {"V"}  # sense proves i sense vendes
    assert e["precisio"] is None
    con.execute("INSERT INTO recompte_estoc (botiga_id, data, gtin, manual, rfid) VALUES (?, '2026-11-16', 'viu', 40, 38)",
                (B,))
    assert A.estoc(con, F)["precisio"] == {"recomptes": 1, "error_mitja_pct": 0.05}


def test_alerta_talla_esgotada(con, t):
    t.sku("gL", "CL", "L", "camisa")
    t.sku("gS", "CL", "S", "camisa")
    for h in ("10:00", "12:00", "17:00"):
        t.peticio("gL", f"2026-11-18T{h}:00+01:00", disponible=0, estat="no_disponible")
    t.peticio("gL", "2026-11-19T10:00:00+01:00", disponible=0, estat="no_disponible")  # un altre dia
    for h in ("10:00", "11:00"):
        t.peticio("gS", f"2026-11-18T{h}:00+01:00", disponible=0, estat="no_disponible")
    t.peticio("gS", "2026-11-18T12:00:00+01:00", disponible=1)  # hi havia estoc
    al = [a for a in A.alertes(con, F)["alertes"] if a["tipus"] == "talla_esgotada"]
    assert [(a["ref"], a["creada"][:10]) for a in al] == [("gL", "2026-11-18")]
    pendents = [a for a in A.alertes(con, F)["alertes"] if a["tipus"] == "peticio_talla"]
    assert len(pendents) == 1
    d = A.demanda_perduda(con, F)
    assert d["total"] == 6 and d["per_variant"][0]["n"] == 4


def test_experiment_sintetic_origen_i_z(con, t):
    t.sku("g1", "M", "M")
    con.executemany("INSERT INTO assignacio (botiga_id, experiment, data, grup) VALUES (?, 'origen', ?, ?)",
                    [(B, "2026-11-16", "amb"), (B, "2026-11-17", "sense")])
    t.proves("g1", 100, 45, dia=date(2026, 11, 16))
    t.proves("g1", 100, 30, dia=date(2026, 11, 17))
    exps = A.experiments(con, F)["experiments"]
    assert len(exps) == 1
    e = exps[0]
    assert e["id"] == f"origen-{B}" and e["variable"] == "origen" and e["unitat"] == "dia"
    assert e["grups"]["amb"] == {"proves": 100, "compres": 45, "conversio": 0.45}
    assert e["diferencia"] == 0.15
    assert e["p_valor"] == round(estadistica.z_dues_proporcions(45, 100, 30, 100)[1], 3) == 0.028
    assert e["ic95"][0] > 0 and e["mostra_suficient"]
    assert e["proves_necessaries"] == estadistica.mostra_necessaria(0.45, 0.30)
    assert e["conclusio"].startswith("Diferència demostrable")


def test_experiment_per_models(con, t):
    t.sku("ga", "MA", "M")
    t.sku("gb", "MB", "M")
    con.execute("""INSERT INTO experiment (id, botiga_id, variable, hipotesi, unitat, inici, fi, proves_minimes)
                   VALUES ('preu-1', ?, 'preu', 'Baixar el preu', 'model', '2026-11-16', '2026-12-13', 30)""", (B,))
    con.executemany("INSERT INTO assignacio_model VALUES ('preu-1', ?, ?)", [("MA", "amb"), ("MB", "sense")])
    t.proves("ga", 10, 5)
    t.proves("gb", 10, 2)
    e = A.experiments(con, F)["experiments"][0]
    assert e["grups"]["amb"]["proves"] == 10 and e["grups"]["sense"]["compres"] == 2
    assert not e["mostra_suficient"] and e["conclusio"].startswith("Mostra insuficient")
    assert e["setmanes_restants"] == 3


def test_abandonades_seccions_i_perdues(con, t):
    t.sku("g1", "M", "M")
    con.execute("INSERT INTO etiqueta (epc, nfc_token, gtin) VALUES ('epc-x', 'tok', 'g1')")
    t.proves("g1", 2, 0)
    con.execute("INSERT INTO peca_abandonada (epc, cabina_id, detectada) VALUES ('epc-x', ?, '2026-11-16T12:00:00+01:00')",
                (CAB,))
    con.execute("""INSERT INTO esdeveniment_nfc (sessio_nfc, ts, botiga_id, gtin, tipus, valor, idioma)
                   VALUES ('s1', '2026-11-16T11:00:00+01:00', ?, 'g1', 'obre_fitxa', NULL, 'fr'),
                          ('s1', '2026-11-16T11:01:00+01:00', ?, 'g1', 'veu_seccio', 'cura', 'fr')""", (B, B))
    assert A.resum(con, F)["kpi"]["peces_abandonades"] == 1
    assert any(a["tipus"] == "peca_abandonada" for a in A.alertes(con, F)["alertes"])
    n = A.fitxa_nfc(con, F)
    assert {s["seccio"]: s["pct"] for s in n["seccions"]}["cura"] == 1.0
    assert n["idiomes"] == [{"idioma": "fr", "n": 1, "pct": 1.0}]
    assert [e["tipus"] for e in A.historial_peca(con, "epc-x")["esdeveniments"]] == ["abandonada"]

    assert A.perdues(con, F)["actiu"] is False
    con.execute("INSERT INTO parametre VALUES ('*', 'senyals_perdua', '1')")
    t.proves("g1", 1, 0, dia=DILLUNS + timedelta(days=3))  # dada posterior: les dues primeres no han tornat
    p = A.perdues(con, F)
    assert p["actiu"] and p["total"] == 2 and p["per_zona_hora"] == [{"cabina": CAB, "hora": 10, "n": 2}]


def test_sense_dades(con, t):
    r = A.resum(con, F)
    assert r["kpi"]["proves"] == 0 and r["kpi"]["conversio"] is None
    assert r["accio"]["insight"] == "qualitat_dada"
    for tipus in ("diari", "setmanal", "mensual", "temporada", "pilot", "mango"):
        inf = A.informe(con, F, tipus)
        assert inf["accio"] is not None and any(a.startswith("Mostra petita") for a in inf["avisos"])
    assert A.valor(con, F)["palanques"][0]["es_estimacio"] is True
