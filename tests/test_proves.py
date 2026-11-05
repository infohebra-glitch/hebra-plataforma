from datetime import datetime, timedelta

from hebra import proves
from hebra.config import ReglaProva

R = ReglaProva(durada_minima_s=60, lectures_minimes=5, marge_alta_db=6, marge_mitjana_db=3, tancament_sessio_s=10)
T0 = datetime.fromisoformat("2026-11-16T12:00:00+01:00")


def ev(seg, tipus):
    return (T0 + timedelta(seconds=seg), tipus)


def test_sessio_basica():
    s = proves.detecta_sessions([ev(0, "porta_tancada"), ev(2, "presencia_si"),
                                 ev(300, "porta_oberta"), ev(303, "presencia_no"), ev(400, "porta_tancada")], "C1", R)
    assert len(s) == 1
    # Comença quan es compleixen les dues condicions (porta tancada i presència).
    assert s[0].inici == T0 + timedelta(seconds=2) and s[0].fi == T0 + timedelta(seconds=303)


def test_porta_oberta_un_moment_no_talla_la_sessio():
    # El client obre la porta per demanar una talla i torna a tancar: segueix sent la mateixa sessió.
    s = proves.detecta_sessions([ev(0, "porta_tancada"), ev(1, "presencia_si"), ev(100, "porta_oberta"),
                                 ev(104, "porta_tancada"), ev(300, "porta_oberta"), ev(302, "presencia_no")], "C1", R)
    assert len(s) == 1


def test_sessio_sense_tancar_no_compta():
    assert proves.detecta_sessions([ev(0, "porta_tancada"), ev(1, "presencia_si")], "C1", R) == []


def test_confianca():
    assert proves.confianca(-50, None, R) == "alta"
    assert proves.confianca(-50, -57, R) == "alta"
    assert proves.confianca(-50, -54, R) == "mitjana"
    assert proves.confianca(-50, -51, R) == "ambigua"
    assert proves.confianca(-55, -50, R) is None


def _munta(con):
    con.execute("INSERT INTO botiga (id, nom) VALUES ('B', 'B')")
    con.execute("INSERT INTO cabina (id, botiga_id, nom, veines) VALUES ('C1', 'B', '1', 'C2'), ('C2', 'B', '2', 'C1')")
    con.execute("INSERT INTO antena (id, cabina_id, port, llindar_rssi) VALUES ('A1', 'C1', 1, -60), ('A2', 'C2', 2, -60)")
    for seg, t in [(0, "porta_tancada"), (1, "presencia_si"), (200, "porta_oberta"), (202, "presencia_no")]:
        con.execute("INSERT INTO sensor_event (cabina_id, ts, tipus) VALUES ('C1', ?, ?)",
                    ((T0 + timedelta(seconds=seg)).isoformat(), t))


def _llegeix(con, epc, antena, de, fins, rssi):
    for s in range(de, fins, 10):
        con.execute("""INSERT INTO lectura_agregada (epc, antena_id, inici, fi, n_lectures, rssi_max, rssi_mitja)
                       VALUES (?, ?, ?, ?, 8, ?, ?)""",
                    (epc, antena, (T0 + timedelta(seconds=s)).isoformat(),
                     (T0 + timedelta(seconds=s + 10)).isoformat(), rssi + 2, rssi))


def test_prova_pas_i_lectura_feble(con):
    _munta(con)
    _llegeix(con, "PROVADA", "A1", 10, 190, -50)   # 3 minuts: prova
    _llegeix(con, "PAS", "A1", 10, 40, -50)        # 30 s: només un pas
    _llegeix(con, "FORA", "A1", 10, 190, -70)      # massa feble: és fora la cabina
    assert proves.processa_cabina(con, "C1", R) == 1
    p = con.execute("SELECT * FROM prova").fetchone()
    assert p["epc"] == "PROVADA" and p["confianca"] == "alta"


def test_lectura_creuada_amb_la_veina(con):
    _munta(con)
    _llegeix(con, "X", "A1", 10, 190, -50)
    _llegeix(con, "X", "A2", 10, 190, -54)
    proves.processa_cabina(con, "C1", R)
    assert con.execute("SELECT confianca FROM prova").fetchone()[0] == "mitjana"


def test_es_idempotent(con):
    _munta(con)
    _llegeix(con, "X", "A1", 10, 190, -50)
    proves.processa_cabina(con, "C1", R)
    proves.processa_cabina(con, "C1", R)
    assert con.execute("SELECT COUNT(*) FROM prova").fetchone()[0] == 1
