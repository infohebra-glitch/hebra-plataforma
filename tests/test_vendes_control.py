from datetime import date

from hebra import control, vendes


def _prova(con, gtin, inici):
    sid = con.execute("INSERT INTO sessio (cabina_id, inici, fi) VALUES ('C1', ?, ?)", (inici, inici)).lastrowid
    return con.execute("""INSERT INTO prova (sessio_id, epc, gtin, durada_s, n_lectures, rssi_mitja, confianca)
                          VALUES (?, 'E', ?, 120, 10, -50, 'alta')""", (sid, gtin)).lastrowid


def _munta(con):
    con.execute("INSERT INTO botiga (id, nom) VALUES ('B', 'B')")
    con.execute("INSERT INTO cabina (id, botiga_id, nom) VALUES ('C1', 'B', '1')")


CSV = """data_hora;botiga;sku;quantitat;import;tiquet
2026-11-16T11:00:00+01:00;B;111;1;10,00;T1
2026-11-16T13:00:00+01:00;B;111;1;10,00;T2
2026-11-16T13:30:00+01:00;B;111;1;10,00;T3
2026-11-17;B;222;1;20;T4
2026-11-17T10:00:00+01:00;X;222;1;20;T5
"""


def test_importa_i_atribueix(con):
    _munta(con)
    p1 = _prova(con, "00000000000111", "2026-11-16T12:00:00+01:00")
    p2 = _prova(con, "00000000000222", "2026-11-17T18:00:00+01:00")
    n, errors = vendes.importa_csv(con, CSV)
    assert n == 4 and len(errors) == 1 and "botiga desconeguda" in errors[0]
    assert con.execute("SELECT COUNT(*) FROM venda_linia WHERE tiquet_hash LIKE 'T%'").fetchone()[0] == 0

    assert vendes.atribueix(con, "B") == 2
    regles = dict(con.execute("SELECT prova_id, regla FROM atribucio").fetchall())
    # La venda de les 11 h és anterior a la prova: no compta. La de les 13 h sí; la de les 13.30 ja no (1 prova, 1 venda).
    assert regles == {p1: "mateix_gtin_hora", p2: "mateix_gtin_dia"}


def test_sorteig_equilibrat_per_dia_de_la_setmana():
    a = control.sorteja("B", "origen", date(2026, 11, 16), setmanes=6)
    assert len(a) == 42
    for dia in range(7):
        grups = [g for d, g in a.items() if date.fromisoformat(d).weekday() == dia]
        assert grups.count("amb") == grups.count("sense") == 3
    assert a == control.sorteja("B", "origen", date(2026, 11, 16), setmanes=6)  # reproduïble
