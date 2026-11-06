"""Plataforma: bus d'alertes, peces abandonades, nivell Bàsic, estoc, Shopify (servidor fals) i retenció."""

import asyncio
import json
import threading
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from hebra import alertes, estoc, proves, retencio, shopify
from hebra.config import ReglaProva

R = ReglaProva(durada_minima_s=60, lectures_minimes=5, marge_alta_db=6, marge_mitjana_db=3, tancament_sessio_s=10)
T0 = datetime.fromisoformat("2026-11-16T12:00:00+01:00")


def _t(seg: float) -> str:
    return (T0 + timedelta(seconds=seg)).isoformat()


def _llegeix(con, epc, antena, de, fins, rssi=-50, pas=10):
    for s in range(de, fins, pas):
        con.execute("""INSERT INTO lectura_agregada (epc, antena_id, inici, fi, n_lectures, rssi_max, rssi_mitja)
                       VALUES (?, ?, ?, ?, 8, ?, ?)""", (epc, antena, _t(s), _t(s + 10), rssi + 2, rssi))


def _munta(con, nivell="cabina"):
    con.execute("INSERT INTO botiga (id, nom, nivell) VALUES ('B', 'B', ?)", (nivell,))
    con.execute("INSERT INTO cabina (id, botiga_id, nom) VALUES ('C1', 'B', '1')")
    con.execute("INSERT INTO antena (id, cabina_id, port, llindar_rssi) VALUES ('A1', 'C1', 1, -60)")
    con.execute("INSERT INTO catalog_sku (gtin, model, color, talla, categoria) VALUES ('00000000000111', 'M1', 'Blau', 'M', 'camisa')")
    con.execute("INSERT INTO etiqueta (epc, nfc_token, gtin) VALUES ('E1', 'tok1', '00000000000111')")


def _sessio(con, de, fins):
    for seg, t in [(de, "porta_tancada"), (de + 1, "presencia_si"), (fins, "porta_oberta"), (fins + 2, "presencia_no")]:
        con.execute("INSERT INTO sensor_event (cabina_id, ts, tipus) VALUES ('C1', ?, ?)", (_t(seg), t))


# ---------------------------------------------------------------- Bus


def test_bus_publica_entre_fils_i_filtra_per_botiga():
    async def prova():
        bus = alertes.Bus()
        de_b = bus.subscriu("B")
        totes = bus.subscriu(None)
        fil = threading.Thread(target=lambda: (bus.publica("peticio", {"id": 1}, "X"),
                                               bus.publica("alerta", {"id": 2}, "B")))
        fil.start()
        fil.join()
        ev = await asyncio.wait_for(de_b.cua.get(), 1)
        assert ev.tipus == "alerta" and ev.dades == {"id": 2}
        assert ev.sse() == 'event: alerta\ndata: {"id": 2}\n\n'
        assert [(await totes.cua.get()).dades["id"] for _ in range(2)] == [1, 2]
        assert de_b.cua.empty()
        bus.dessubscriu(de_b)
        bus.dessubscriu(totes)
        assert bus.subscriptors == 0 and len(bus.recents) == 2
    asyncio.run(prova())


# ---------------------------------------------------------------- Peces abandonades


def test_peca_abandonada(con):
    _munta(con)
    _sessio(con, 0, 300)
    _llegeix(con, "E1", "A1", 10, 300 + 40 * 60)       # provada i encara llegida 40 min després de la sessió
    _llegeix(con, "E2", "A1", 10, 300 + 10 * 60)       # només 10 min: algú l'ha recollit
    proves.processa_cabina(con, "C1", R)
    alertes.detecta_abandonades(con, "C1", ara=_t(10_000))  # més tard: ja no es llegeix
    a = con.execute("SELECT * FROM peca_abandonada").fetchall()
    assert [(x["epc"], x["detectada"]) for x in a] == [("E1", _t(302 + 30 * 60))]
    assert a[0]["resolta"] == _t(300 + 40 * 60)        # ja no es llegeix: resolta quan es va deixar de llegir

    # Idempotent: tornar a processar no la duplica.
    proves.processa_cabina(con, "C1", R)
    assert con.execute("SELECT COUNT(*) FROM peca_abandonada").fetchone()[0] == 1


def test_peca_abandonada_oberta_publica_alerta_i_venda_l_exclou(con):
    _munta(con)
    _sessio(con, 0, 300)
    _llegeix(con, "E1", "A1", 10, 300 + 40 * 60)
    alertes.bus.recents.clear()
    proves.processa_cabina(con, "C1", R)
    con.execute("DELETE FROM peca_abandonada")
    # Encara es llegeix "ara": oberta i publicada.
    assert alertes.detecta_abandonades(con, "C1", ara=_t(300 + 40 * 60 + 30)) == 1
    assert con.execute("SELECT resolta FROM peca_abandonada").fetchone()[0] is None
    ev = alertes.bus.recents[-1]
    assert ev.tipus == "abandonada" and ev.dades["epc"] == "E1" and ev.botiga_id == "B"

    # Si s'ha venut el mateix GTIN, no és abandonada (és la de l'emprovador però se n'han endut una).
    con.execute("DELETE FROM peca_abandonada")
    con.execute("INSERT INTO venda_linia (botiga_id, ts, data, gtin, quantitat) VALUES ('B', ?, '2026-11-16', '00000000000111', 1)",
                (_t(600),))
    assert alertes.detecta_abandonades(con, "C1", ara=_t(300 + 40 * 60 + 30)) == 0


def test_minuts_abandonada_es_parametre(con):
    _munta(con)
    con.execute("INSERT INTO parametre (botiga_id, clau, valor) VALUES ('B', 'minuts_abandonada', '60')")
    _sessio(con, 0, 300)
    _llegeix(con, "E1", "A1", 10, 300 + 40 * 60)
    proves.processa_cabina(con, "C1", R)
    assert con.execute("SELECT COUNT(*) FROM peca_abandonada").fetchone()[0] == 0


# ---------------------------------------------------------------- Nivell Bàsic


def test_estades_i_entrades_a_zona():
    t = lambda s: T0 + timedelta(seconds=s)  # noqa: E731
    lectures = [("A", t(0), t(10), 5, -50, -60), ("A", t(50), t(60), 5, -50, -60),   # buit de 40 s: la mateixa estada
                ("A", t(200), t(210), 5, -50, -60),                                    # buit de 140 s: una altra
                ("B", t(5), t(15), 5, -70, -60)]                                       # massa feble
    estades = proves.estades_zona(lectures)
    assert [(e.epc, e.inici, e.fi, e.n_lectures) for e in estades] == [("A", t(0), t(60), 10), ("A", t(200), t(210), 5)]
    assert len(proves.entrades_zona(estades)) == 2
    assert proves.etiqueta_sessions("basic") == "entrades a zona"


def test_nivell_basic_sense_sensors(con):
    _munta(con, nivell="basic")
    _llegeix(con, "E1", "A1", 0, 180)          # 3 min a la zona: prova
    _llegeix(con, "E2", "A1", 60, 100)         # 40 s, la mateixa entrada: només un pas
    _llegeix(con, "E1", "A1", 1000, 1300, pas=50)  # buits de 40 s (lectures de 10 s cada 50 s): una altra prova
    _llegeix(con, "E3", "A1", 5000, 5100, pas=70)  # buits de 60 s: estades separades i curtes, cap prova
    assert proves.processa_cabina(con, "C1", R) == 2
    sessions = con.execute("SELECT inici, fi FROM sessio ORDER BY inici").fetchall()
    assert [(s["inici"], s["fi"]) for s in sessions[:2]] == [(_t(0), _t(180)), (_t(1000), _t(1260))]
    assert len(sessions) == 4  # dues entrades amb prova + dues de l'E3
    p = con.execute("SELECT epc, gtin, durada_s, confianca FROM prova ORDER BY id").fetchall()
    assert [(x["epc"], x["gtin"], x["durada_s"]) for x in p] == [("E1", "00000000000111", 180), ("E1", "00000000000111", 260)]
    assert proves.processa_cabina(con, "C1", R) == 2  # idempotent
    assert con.execute("SELECT COUNT(*) FROM sessio").fetchone()[0] == 4


# ---------------------------------------------------------------- Estoc


def test_importa_estoc(con):
    _munta(con)
    n, errors = estoc.importa_csv(con, "botiga;sku;unitats\nB;111;4\nB;111;2\nX;111;1\nB;222;-1\nB;333;no\n")
    assert n == 2 and len(errors) == 3
    assert estoc.unitats(con, "B", "00000000000111") == 2  # la darrera fila mana
    assert estoc.unitats(con, "B", "00000000000999") is None
    assert estoc.importa_csv(con, "botiga,gtin\nB,1\n")[1] == ["Falten columnes: unitats"]
    assert alertes.disponible(con, "B", "00000000000111", 0) == 1      # la taula mana sobre l'origen
    assert alertes.disponible(con, "B", "00000000000999", 0) == 0      # sense dada: l'origen
    assert alertes.disponible(con, "B", "00000000000999", None) is None


# ---------------------------------------------------------------- Shopify (servidor fals)


class _ShopifyFals(BaseHTTPRequestHandler):
    peticions: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        url = urlsplit(self.path)
        q = parse_qs(url.query)
        self.peticions.append((url.path, q, self.headers.get("X-Shopify-Access-Token")))
        base = f"/admin/api/{shopify.API_VERSIO}"
        enllac = None
        if url.path == f"{base}/products.json":
            if "page_info" not in q:
                cos = {"products": [{"id": 1, "variants": [{"id": 11, "barcode": "111", "inventory_item_id": 101}]}]}
                enllac = f'<http://{self.headers["Host"]}{base}/products.json?limit=250&page_info=p2>; rel="next"'
            else:
                cos = {"products": [{"id": 2, "variants": [{"id": 22, "barcode": "00000000000222", "inventory_item_id": 202},
                                                           {"id": 33, "barcode": "", "inventory_item_id": 303}]}]}
        elif url.path == f"{base}/orders.json":
            cos = {"orders": [
                {"id": 900, "created_at": "2026-11-16T11:00:00Z", "processed_at": "2026-11-16T11:00:00Z",
                 "cancelled_at": None, "location_id": 55,
                 "line_items": [{"variant_id": 11, "quantity": 2, "price": "69.00"},
                                {"variant_id": 22, "quantity": 1, "price": "20.00"},
                                {"variant_id": 99, "quantity": 1, "price": "1.00"}]},
                {"id": 901, "created_at": "2026-11-16T12:00:00Z", "location_id": 77,   # una altra botiga
                 "line_items": [{"variant_id": 11, "quantity": 1, "price": "69.00"}]},
                {"id": 902, "created_at": "2026-11-16T13:00:00Z", "location_id": 55, "cancelled_at": "2026-11-16T14:00:00Z",
                 "line_items": [{"variant_id": 11, "quantity": 1, "price": "69.00"}]}]}
        elif url.path == f"{base}/inventory_levels.json":
            cos = {"inventory_levels": [{"inventory_item_id": 101, "location_id": 55, "available": 3},
                                        {"inventory_item_id": 202, "location_id": 55, "available": -1},
                                        {"inventory_item_id": 999, "location_id": 55, "available": 9}]}
        else:
            self.send_response(404)
            self.end_headers()
            return
        dades = json.dumps(cos).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        if enllac:
            self.send_header("Link", enllac)
        self.end_headers()
        self.wfile.write(dades)


@pytest.fixture
def shopify_fals():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _ShopifyFals)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _ShopifyFals.peticions = []
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_shopify_sincronitza(con, shopify_fals, monkeypatch):
    _munta(con)
    con.execute("INSERT INTO catalog_sku (gtin, model, color, talla, categoria) VALUES ('00000000000222', 'M1', 'Blau', 'L', 'camisa')")
    con.execute("INSERT INTO parametre (botiga_id, clau, valor) VALUES ('B', 'shopify_domini', ?), ('B', 'shopify_ubicacio', '55')",
                (shopify_fals,))
    with pytest.raises(shopify.ErrorShopify, match="HEBRA_SHOPIFY_TOKEN_B"):
        shopify.sincronitza(con, "B")
    monkeypatch.setenv("HEBRA_SHOPIFY_TOKEN_B", "shpat_prova")

    assert shopify.sincronitza(con, "B") == {"comandes": 1, "linies": 2, "estoc": 2}
    linies = con.execute("SELECT * FROM venda_linia ORDER BY gtin").fetchall()
    assert [(x["gtin"], x["quantitat"], x["import_eur"]) for x in linies] == [
        ("00000000000111", 2, 138.0), ("00000000000222", 1, 20.0)]
    assert linies[0]["ts"] == "2026-11-16T12:00:00+01:00" and linies[0]["data"] == "2026-11-16"
    assert linies[0]["tiquet_hash"] and "900" not in linies[0]["tiquet_hash"]
    assert estoc.unitats(con, "B", "00000000000111") == 3 and estoc.unitats(con, "B", "00000000000222") == 0
    assert con.execute("SELECT variant_shopify FROM catalog_sku WHERE gtin = '00000000000111'").fetchone()[0] == "11"
    assert all(t == "shpat_prova" for _, _, t in _ShopifyFals.peticions)
    assert {p for p, _, _ in _ShopifyFals.peticions} == {f"/admin/api/{shopify.API_VERSIO}/{r}.json"
                                                         for r in ("products", "orders", "inventory_levels")}

    # La segona vegada no duplica les comandes i demana només des de la darrera sincronització.
    _ShopifyFals.peticions = []
    assert shopify.sincronitza(con, "B")["linies"] == 0
    q = next(q for p, q, _ in _ShopifyFals.peticions if p.endswith("orders.json"))
    assert "created_at_min" in q
    assert con.execute("SELECT COUNT(*) FROM venda_linia").fetchone()[0] == 2


def test_shopify_nomes_https():
    with pytest.raises(shopify.ErrorShopify):
        shopify.Client("http://marca.myshopify.com", "t")
    assert shopify.Client("marca.myshopify.com", "t").base == f"https://marca.myshopify.com/admin/api/{shopify.API_VERSIO}"
    assert shopify.nom_variable_token("BCN-01") == "HEBRA_SHOPIFY_TOKEN_BCN_01"


# ---------------------------------------------------------------- Retenció


def test_retencio_esborra_dades_crues_i_mante_les_proves(con):
    _munta(con)
    _sessio(con, 0, 300)
    _llegeix(con, "E1", "A1", 10, 190)
    assert proves.processa_cabina(con, "C1", R) == 1
    # Una sessió nova, 100 dies després.
    for seg, t in [(0, "porta_tancada"), (1, "presencia_si"), (300, "porta_oberta"), (302, "presencia_no")]:
        con.execute("INSERT INTO sensor_event (cabina_id, ts, tipus) VALUES ('C1', ?, ?)",
                    ((T0 + timedelta(days=100, seconds=seg)).isoformat(), t))
    con.execute("INSERT INTO lectura_agregada (epc, antena_id, inici, fi, n_lectures, rssi_max, rssi_mitja) VALUES ('E9', 'A1', ?, ?, 50, -48, -50)",
                ((T0 + timedelta(days=100, seconds=10)).isoformat(), (T0 + timedelta(days=100, seconds=200)).isoformat()))

    n = retencio.neteja(con, 90, avui=date(2027, 2, 24))
    assert n == {"lectura_agregada": 18, "sensor_event": 4}
    assert con.execute("SELECT COUNT(*) FROM lectura_agregada").fetchone()[0] == 1
    # Recalcular no esborra la prova antiga (ja no en queden les dades crues).
    assert proves.processa_cabina(con, "C1", R) == 1
    assert [r[0] for r in con.execute("SELECT epc FROM prova ORDER BY id")] == ["E1", "E9"]
    assert retencio.neteja(con, 0) == {"lectura_agregada": 0, "sensor_event": 0}
