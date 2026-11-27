"""Còpies de seguretat (hebra/copies.py)."""

import gzip
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from hebra import copies, db
from hebra.analitica import Filtre, estat_sistema


@pytest.fixture
def bd(tmp_path):
    ruta = tmp_path / "hebra.db"
    c = db.connecta(str(ruta))
    db.inicialitza(c)
    c.execute("INSERT INTO botiga (id, nom, nivell, zona_horaria) VALUES ('BCN-01', 'Barcelona', 'cabina', 'Europe/Madrid')")
    c.commit()
    yield ruta, c
    c.close()


def _cc(tmp_path, **kw):
    return copies.ConfigCopies(carpeta=str(tmp_path / "copies"), diaries=kw.get("diaries", 14),
                               setmanals=kw.get("setmanals", 8), desti=kw.get("desti", ""), remot_dies=60)


def test_copia_en_calent_es_valida_i_conte_les_dades(tmp_path, bd):
    ruta, c = bd
    # Hi ha una escriptura sense tancar al WAL mentre es copia: la còpia ha de ser coherent igualment.
    c.execute("INSERT INTO botiga (id, nom, nivell, zona_horaria) VALUES ('GIR-01', 'Girona', 'cabina', 'Europe/Madrid')")
    c.commit()
    e = copies.fes_copia(str(ruta), _cc(tmp_path))
    fitxer = tmp_path / "copies" / e["fitxer"]
    assert fitxer.is_file() and (tmp_path / "copies" / (e["fitxer"] + ".sha256")).is_file()
    assert oct(fitxer.stat().st_mode)[-3:] == "600"
    cru = tmp_path / "comprova.db"
    cru.write_bytes(gzip.decompress(fitxer.read_bytes()))
    k = sqlite3.connect(cru)
    assert {r[0] for r in k.execute("SELECT id FROM botiga")} == {"BCN-01", "GIR-01"}
    k.close()
    assert e["remot"] is None and e["error_remot"] is None


def test_rotacio_guarda_diaries_i_setmanals(tmp_path, bd):
    ruta, _ = bd
    cc = _cc(tmp_path, diaries=3, setmanals=2)
    inici = datetime(2026, 9, 1, 3, 30, tzinfo=timezone.utc)
    for i in range(40):
        copies.fes_copia(str(ruta), cc, ara=inici + timedelta(days=i))
    restants = copies.llista(tmp_path / "copies")
    dates = [copies._data_del_nom(p).date() for p in restants]
    assert len(restants) == 5
    assert dates[:3] == [(inici + timedelta(days=i)).date() for i in (39, 38, 37)]
    # Les dues setmanals són de setmanes diferents i anteriors a les diàries
    assert len({d.isocalendar()[:2] for d in dates[3:]}) == 2
    assert not list((tmp_path / "copies").glob("tmp*"))


def test_restaura_substitueix_i_guarda_lanterior(tmp_path, bd):
    ruta, c = bd
    e = copies.fes_copia(str(ruta), _cc(tmp_path))
    c.execute("DELETE FROM botiga")
    c.commit()
    c.close()
    anterior = copies.restaura(str(tmp_path / "copies" / e["fitxer"]), str(ruta))
    assert anterior and anterior.is_file()
    k = sqlite3.connect(ruta)
    assert k.execute("SELECT COUNT(*) FROM botiga").fetchone()[0] == 1
    k.close()


def test_restaura_rebutja_una_copia_malmesa(tmp_path, bd):
    ruta, _ = bd
    e = copies.fes_copia(str(ruta), _cc(tmp_path))
    f = tmp_path / "copies" / e["fitxer"]
    f.write_bytes(f.read_bytes()[:-20] + b"x" * 20)
    with pytest.raises(copies.ErrorCopia, match="SHA-256"):
        copies.restaura(str(f), str(ruta))
    brossa = tmp_path / "brossa.db"
    brossa.write_bytes(b"no soc una base de dades" * 100)
    with pytest.raises(copies.ErrorCopia):
        copies.restaura(str(brossa), str(ruta))
    assert sqlite3.connect(ruta).execute("SELECT COUNT(*) FROM botiga").fetchone()[0] == 1


def test_error_remot_no_perd_la_copia_local_i_surt_a_lestat(tmp_path, bd, monkeypatch):
    ruta, c = bd
    monkeypatch.setattr(copies.shutil, "which", lambda _: None)  # sense rclone
    e = copies.fes_copia(str(ruta), _cc(tmp_path, desti="copies:hebra"))
    assert (tmp_path / "copies" / e["fitxer"]).is_file()
    assert "rclone" in e["error_remot"]
    st = copies.estat(c)
    assert st["alerta"] is True and st["error_remot"]


def test_envia_amb_rclone(tmp_path, bd, monkeypatch):
    ruta, c = bd
    crides = []
    monkeypatch.setattr(copies.shutil, "which", lambda _: "/usr/bin/rclone")

    class R:
        returncode, stderr = 0, ""

    monkeypatch.setattr(copies.subprocess, "run", lambda args, **kw: crides.append(args) or R())
    e = copies.fes_copia(str(ruta), _cc(tmp_path, desti="copies:hebra/"))
    assert crides[0][:2] == ["rclone", "copyto"] and crides[0][3] == f"copies:hebra/{e['fitxer']}"
    assert crides[1][:4] == ["rclone", "delete", "--min-age", "60d"]
    assert e["remot"] == "copies:hebra/"
    assert copies.estat(c)["alerta"] is False


def test_estat_sistema_avisa_sense_copies(tmp_path, bd):
    ruta, c = bd
    from datetime import date
    f = Filtre(botiga_id=None, des=date(2026, 11, 10), fins=date(2026, 11, 16))
    st = estat_sistema(c, f)["copia_seguretat"]
    assert st["darrera"] is None and st["alerta"] is True
    vella = datetime.now(timezone.utc) - timedelta(hours=48)
    copies.fes_copia(str(ruta), _cc(tmp_path), ara=vella)
    st = estat_sistema(c, f)["copia_seguretat"]
    assert st["alerta"] is True and st["hores"] >= 47
    copies.fes_copia(str(ruta), _cc(tmp_path, desti=""))
    assert estat_sistema(c, f)["copia_seguretat"]["alerta"] is False
