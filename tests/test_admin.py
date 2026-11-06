from pathlib import Path

from hebra import admin, cataleg

ARREL = Path(__file__).resolve().parent.parent


def test_alta_botiga_cataleg_i_etiquetes(con, tmp_path):
    assert "3 cabines" in admin.botiga(con, str(ARREL / "desplegament" / "botiga.example.json"))
    (tmp_path / "cat.csv").write_text("gtin;model;color;talla;categoria;preu\n"
                                      "08400000123457;CL-24-NAT;Natural;M;camisa;69\n"
                                      "08400000124454;CL-24-NAT;Natural;L;camisa;69\n"
                                      "08400000123458;MAL;X;S;camisa;1\n", encoding="utf-8")
    r = admin.cataleg_csv(con, str(tmp_path / "cat.csv"))
    assert r.startswith("2 variants") and "GTIN no vàlid" in r

    # L'origen s'enganxa a les variants reals del model, sense inventar-ne de noves.
    assert cataleg.importa_origen(con, ARREL / "dades" / "origen-prova.json") >= 2
    assert con.execute("SELECT COUNT(*) FROM catalog_sku WHERE model = 'CL-24-NAT' AND origen_json IS NOT NULL").fetchone()[0] == 2

    (tmp_path / "et.csv").write_text("epc\n303600B2000C0E4000000001\n", encoding="utf-8")
    sortida = tmp_path / "nfc.csv"
    # L'EPC hex és de l'empresa 8400000 i la referència 012345 -> GTIN 08400000123457
    r = admin.etiquetes(con, str(tmp_path / "et.csv"), "BCN-01", "https://h.example", str(sortida))
    assert r.startswith("1 etiquetes"), r
    url = sortida.read_text().splitlines()[1].split(",")[2]
    assert url.startswith("https://h.example/p/") and url.endswith("?b=BCN-01")
    token = url.split("/p/")[1].split("?")[0]
    assert len(token) >= 12  # aleatori, no endevinable
    # Tornar-ho a executar manté el mateix token (l'etiqueta ja gravada continua funcionant).
    admin.etiquetes(con, str(tmp_path / "et.csv"), "BCN-01", "https://h.example", str(sortida))
    assert token in sortida.read_text()
