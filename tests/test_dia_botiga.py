"""v0.7: el lot de prova es comporta com una botiga oberta (ritme del dia i clients nous cada pocs minuts)."""

from datetime import date, datetime, timedelta
from unittest import mock

from hebra import db, lot_prova, simulador
from hebra.simulador import ZONA, horari_cabina


def _sessions_per_hora(dies: list[date]) -> dict[int, int]:
    n: dict[int, int] = {}
    for d in dies:
        for ci in range(3):
            for t, _ in horari_cabina(d, ci):
                n[t.hour] = n.get(t.hour, 0) + 1
    return n


def test_ritme_del_dia():
    dilluns = [date(2026, 11, 2) + timedelta(weeks=w) for w in range(8)]
    dissabtes = [d + timedelta(days=5) for d in dilluns]
    assert sum(_sessions_per_hora(dissabtes).values()) > 1.4 * sum(_sessions_per_hora(dilluns).values())
    h = _sessions_per_hora(dilluns + dissabtes)
    assert h[13] > h[15] and h[19] > h[15] and h[19] > h[10]   # puntes de migdia i tarda, calma a l'hora de dinar
    assert min(h) >= 10 and max(h) <= 20                         # obert de 10 a 21
    assert horari_cabina(date(2026, 11, 8), 0) == []             # diumenge tancat
    assert horari_cabina(date(2026, 11, 7), 1) == horari_cabina(date(2026, 11, 7), 1)  # sempre el mateix


def test_carrega_fins_ara_i_es_posa_al_dia(tmp_path):
    con = db.connecta(str(tmp_path / "dia.db"))
    db.inicialitza(con)
    ara = datetime(2026, 11, 27, 12, 30, tzinfo=ZONA)   # divendres a migdia
    with mock.patch("hebra.temps.ara", return_value=ara.isoformat()):
        e = lot_prova.carrega(con)
    assert e["fins"] == "2026-11-27"

    def recompte():
        return (con.execute("SELECT COUNT(*), MAX(inici) FROM sessio WHERE cabina_id LIKE 'PROVA-01-%'").fetchone(),
                con.execute("SELECT COUNT(*), MAX(ts) FROM venda_linia WHERE botiga_id = 'PROVA-01'").fetchone())
    (n0, max0), (v0, vmax0) = recompte()
    assert n0 > 0 and max0[:10] == "2026-11-27" and max0 < ara.isoformat()   # el matí d'avui, res al futur
    assert vmax0 <= ara.isoformat()

    # Dues hores més tard: clients nous, cap al futur, i tornar-ho a fer a la mateixa hora no duplica res.
    despres = ara + timedelta(hours=2)
    n = lot_prova.posa_al_dia(con, despres)
    assert n > 0 and lot_prova.posa_al_dia(con, despres) == 0
    (n1, max1), (v1, vmax1) = recompte()
    assert n1 > n0 and max0 < max1 < despres.isoformat() and vmax1 <= despres.isoformat()
    assert lot_prova.estat(con)["resum"]["sessions"] >= e["resum"]["sessions"] + n
    # Les mateixes sessions que si s'hagués carregat d'una tirada: res repetit ni encavalcat.
    fins = con.execute("SELECT inici, fi FROM sessio WHERE cabina_id = 'PROVA-01-C1' ORDER BY inici").fetchall()
    assert all(a["fi"] <= b["inici"] for a, b in zip(fins, fins[1:]))

    # La plataforma aturada uns dies: només n'omple els últims MAX_DIES_AL_DIA, i el diumenge no hi ha ningú.
    lot_prova.posa_al_dia(con, datetime(2026, 11, 30, 11, 0, tzinfo=ZONA))
    assert not con.execute("SELECT 1 FROM sessio WHERE cabina_id LIKE 'PROVA-01-%' AND inici LIKE '2026-11-29%'").fetchone()
    assert lot_prova.esborra(con)["esborrat"]
    assert lot_prova.posa_al_dia(con) == 0
    con.close()


def test_sense_lot_no_fa_res(tmp_path):
    con = db.connecta(str(tmp_path / "buit.db"))
    db.inicialitza(con)
    assert lot_prova.posa_al_dia(con) == 0
    assert simulador.BOTIGA == "BCN-01"
