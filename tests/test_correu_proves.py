"""Mode de proves del correu (tot a una sola adreça) i ordres d'administració per al servidor."""

import pytest

from hebra import auth, correu, db
from hebra.admin import correu_prova
from hebra.config import Config

from test_v3_estoc_informes import smtp  # noqa: F401  (fixture)


def _cfg(**k):
    return Config(smtp_host="smtp.prova.cat", smtp_port=587, smtp_usuari="u@prova.cat", smtp_contrasenya="c",
                  smtp_remitent="Hebra <clientes@hebraia.com>", **k)


def test_mode_de_proves_ho_envia_tot_a_una_adreca(smtp):
    cfg = _cfg(correu_redirigeix="clientes@hebraia.com")
    assert correu.envia(cfg, ["direccio@marca.cat", "botiga@marca.cat"], "Informe setmanal", "Hola") == \
        ["direccio@marca.cat", "botiga@marca.cat"]
    (_, m), = smtp.enviats
    assert m["To"] == "clientes@hebraia.com"
    assert m["Subject"] == "[Proves, per a direccio@marca.cat, botiga@marca.cat] Informe setmanal"
    assert "direccio@marca.cat" in m.get_content() and m["From"] == "Hebra <clientes@hebraia.com>"


def test_sense_mode_de_proves_va_als_destinataris(smtp):
    correu.envia(_cfg(), ["direccio@marca.cat"], "Informe", "Hola")
    (_, m), = smtp.enviats
    assert m["To"] == "direccio@marca.cat" and m["Subject"] == "Informe"


def test_correu_de_prova(smtp, capsys):
    assert correu_prova(_cfg(correu_redirigeix="clientes@hebraia.com"), None) == 0
    assert smtp.enviats[0][1]["To"] == "clientes@hebraia.com"
    assert correu_prova(Config(smtp_host=""), None) == 1
    smtp.falla = True
    assert correu_prova(_cfg(), "a@marca.cat") == 1


def test_canvia_contrasenya_des_del_servidor(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "ITERACIONS", 1000)
    con = db.connecta(str(tmp_path / "u.db"))
    db.inicialitza(con)
    auth.crea_usuari(con, "jo@hebraia.com", "Jo", "admin", "contrasenya-antiga")
    versio = con.execute("SELECT versio_sessio FROM usuari").fetchone()[0]
    auth.canvia_contrasenya(con, " JO@hebraia.com ", "contrasenya-nova")
    assert auth.autentica(con, "jo@hebraia.com", "contrasenya-nova")
    assert not auth.autentica(con, "jo@hebraia.com", "contrasenya-antiga")
    assert con.execute("SELECT versio_sessio FROM usuari").fetchone()[0] == versio + 1  # sessions tancades
    with pytest.raises(ValueError):
        auth.canvia_contrasenya(con, "jo@hebraia.com", "curta")
    with pytest.raises(ValueError):
        auth.canvia_contrasenya(con, "ningu@hebraia.com", "contrasenya-nova")
