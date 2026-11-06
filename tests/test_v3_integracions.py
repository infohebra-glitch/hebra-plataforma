"""v0.3 F: integracions (Shopify, Square, CSV per URL), xifratge dels secrets, motor i API.

Cap prova fa servir la xarxa: se substitueix `hebra.integracions.http._obre` per un servidor fals.
"""

import importlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from hebra import auth, estoc
from hebra.integracions import ErrorIntegracio, http, motor, xifratge
from hebra.integracions.csv_url import CsvUrl
from hebra.integracions.shopify import API_VERSIO, Shopify
from hebra.integracions.square import Square

SB = f"/admin/api/{API_VERSIO}"
CLAU = "secret-de-prova"


class Fals:
    """Servidor HTTP fals: rutes {(mètode, camí): funció(query, cos) -> (estat, cos, capçaleres)}."""

    def __init__(self):
        self.rutes, self.peticions, self.esperes = {}, [], []

    def ruta(self, metode, cami, resposta):
        self.rutes[(metode, cami)] = resposta if callable(resposta) else (lambda q, c, r=resposta: r)

    def __call__(self, req, temps_espera):
        u = urlsplit(req.full_url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        cos = json.loads(req.data) if req.data else None
        capcaleres = {k.lower(): v for k, v in req.header_items()}
        self.peticions.append({"metode": req.get_method(), "host": u.hostname, "cami": u.path, "q": q, "cos": cos,
                               "h": capcaleres, "temps": temps_espera})
        f = self.rutes.get((req.get_method(), u.path))
        if f is None:
            return http.Resposta(404, {}, b'{"errors": "Not Found"}')
        r = f(q, cos)
        estat, dades, h = (r + ({},))[:3] if len(r) == 2 else r
        cru = dades if isinstance(dades, bytes) else json.dumps(dades).encode()
        return http.Resposta(estat, {k.lower(): v for k, v in h.items()}, cru)

    def cridades(self, cami):
        return [p for p in self.peticions if p["cami"] == cami]


@pytest.fixture
def fals(monkeypatch):
    f = Fals()
    monkeypatch.setattr(http, "_obre", f)
    monkeypatch.setattr(http, "_dorm", f.esperes.append)
    return f


def _botiga(con, bid="B", zona="Europe/Madrid"):
    con.execute("INSERT INTO botiga (id, nom, zona_horaria) VALUES (?, ?, ?)", (bid, bid, zona))
    con.commit()


# ---------------------------------------------------------------- Xifratge


def test_xifratge_anada_i_tornada():
    x = xifratge.xifra(CLAU, "shpat_molt_secret")
    assert "shpat" not in x and x != xifratge.xifra(CLAU, "shpat_molt_secret")  # Fernet porta IV aleatori
    assert xifratge.desxifra(CLAU, x) == "shpat_molt_secret"
    with pytest.raises(xifratge.SecretIllegible):
        xifratge.desxifra("una-altra-clau", x)
    with pytest.raises(ValueError):
        xifratge.xifra("", "x")


# ---------------------------------------------------------------- HTTP


def test_http_429_espera_retry_after_i_torna_a_provar(fals):
    estats = iter([(429, {}, {"Retry-After": "3"}), (429, {}, {"Retry-After": "999"}), (200, {"ok": 1})])
    fals.ruta("GET", "/x", lambda q, c: next(estats))
    assert http.peticio("GET", "https://a.test/x").json() == {"ok": 1}
    assert fals.esperes == [3.0, http.ESPERA_MAXIMA_S]  # educat, però amb un màxim
    assert all(p["temps"] == http.TEMPS_ESPERA_S for p in fals.peticions)
    fals.ruta("GET", "/sempre", (429, {}, {"Retry-After": "1"}))
    with pytest.raises(http.ErrorHttp) as e:
        http.peticio("GET", "https://a.test/sempre")
    assert e.value.estat == 429 and len(fals.cridades("/sempre")) == http.INTENTS


# ---------------------------------------------------------------- Shopify


def _productes_shopify(fals, pagina2=True):
    p1 = {"products": [{
        "id": 7001, "title": "Camisa lli", "product_type": "camisa",
        "options": [{"name": "Color", "position": 1}, {"name": "Talla", "position": 2}],
        "variants": [
            {"id": 11, "barcode": "8400000000017", "sku": "CAM01-BLAU-M", "price": "69.00", "option1": "Blau",
             "option2": "M", "inventory_item_id": 101},
            {"id": 12, "barcode": "8400000000024", "sku": "CAM01-BLAU-L", "price": "69.00", "option1": "Blau",
             "option2": "L", "inventory_item_id": 102},
            {"id": 13, "barcode": "", "sku": "CAM01-BLAU-XL", "price": "69.00", "option1": "Blau", "option2": "XL"}]}]}
    p2 = {"products": [{
        "id": 7002, "title": "Mocador", "product_type": "", "options": [{"name": "Title", "position": 1}],
        "variants": [{"id": 21, "barcode": "8400000000031", "sku": "MOC9", "price": "15.5", "option1": "Default Title",
                      "inventory_item_id": 201}]}]}

    def productes(q, c):
        if "page_info" in q:
            return 200, p2
        enllac = f'<https://marca.myshopify.com{SB}/products.json?limit=250&page_info=abc>; rel="next"' if pagina2 else ""
        return 200, p1, {"Link": enllac, "X-Shopify-Shop-Api-Call-Limit": "39/40"}
    fals.ruta("GET", f"{SB}/products.json", productes)


def test_shopify_cataleg_paginat_i_mapat(con, fals):
    _botiga(con)
    _productes_shopify(fals)
    s = Shopify(Shopify.valida({"domini": "marca"}, None, ["cataleg"]), "shpat_x")
    v = {x["gtin"]: x for x in s.cataleg()}
    assert set(v) == {"08400000000017", "08400000000024", "08400000000031"}  # sense codi de barres: fora
    assert v["08400000000017"] == {"gtin": "08400000000017", "model": "7001", "color": "Blau", "talla": "M",
                                   "categoria": "camisa", "preu_eur": 69.0, "id_extern": "11"}
    assert v["08400000000031"]["talla"] == "Única" and v["08400000000031"]["categoria"] == "altres"
    assert len(fals.cridades(f"{SB}/products.json")) == 2  # dues pàgines (capçalera Link)
    assert fals.peticions[1]["q"] == {"limit": "250", "page_info": "abc"}
    assert fals.esperes == [1.0]  # el cubell de Shopify era gairebé ple (39/40): s'espera
    assert all(p["h"]["x-shopify-access-token"] == "shpat_x" and p["host"] == "marca.myshopify.com"
               for p in fals.peticions)

    # SKU base i noms d'opció configurables.
    v = {x["gtin"]: x for x in Shopify({"domini": "marca", "model": "sku_base"}, "t").cataleg()}
    assert v["08400000000017"]["model"] == "CAM01" and v["08400000000031"]["model"] == "MOC9"
    s = Shopify({"domini": "marca.myshopify.com", "opcio_talla": "Mida", "opcio_color": ["Color"]}, "t")
    v = {x["gtin"]: x for x in s.cataleg()}
    assert v["08400000000017"]["talla"] == "Única" and v["08400000000017"]["color"] == "Blau"  # «Talla» no és «Mida»

    # Desat: catalog_sku amb l'id de variant.
    r = Shopify({"domini": "marca"}, "t", None).aplica(con, ["cataleg"], None, None)
    assert r["cataleg"] == 3
    f = con.execute("SELECT * FROM catalog_sku WHERE gtin = '08400000000024'").fetchone()
    assert (f["model"], f["color"], f["talla"], f["preu_eur"], f["variant_shopify"]) == ("7001", "Blau", "L", 69.0, "12")


def _comandes_shopify(fals):
    comandes = {"orders": [
        {"id": 900, "created_at": "2026-11-02T10:00:00Z", "processed_at": "2026-11-02T10:00:00Z", "cancelled_at": None,
         "location_id": 55,
         "line_items": [{"id": 1, "variant_id": 11, "quantity": 2, "price": "69.00"},
                        {"id": 2, "variant_id": 21, "quantity": 1, "price": "15.50"}],
         "refunds": [{"id": 5001, "created_at": "2026-11-04T09:00:00Z", "processed_at": "2026-11-04T09:00:00Z",
                      "refund_line_items": [{"line_item_id": 1, "quantity": 1, "subtotal": "65.00", "location_id": 55,
                                             "line_item": {"variant_id": 11, "price": "69.00"}}]}]},
        {"id": 901, "created_at": "2026-11-03T10:00:00Z", "location_id": None,   # en línia
         "line_items": [{"variant_id": 12, "quantity": 1, "price": "69.00"}], "refunds": []},
        {"id": 902, "created_at": "2026-11-03T11:00:00Z", "location_id": 77,     # una altra ubicació
         "line_items": [{"variant_id": 12, "quantity": 1, "price": "69.00"}], "refunds": []},
        {"id": 903, "created_at": "2026-11-03T12:00:00Z", "location_id": 55, "cancelled_at": "2026-11-03T13:00:00Z",
         "line_items": [{"variant_id": 12, "quantity": 1, "price": "69.00"}],
         "refunds": [{"id": 5002, "created_at": "2026-11-03T13:00:00Z",
                      "refund_line_items": [{"quantity": 1, "line_item": {"variant_id": 12, "price": "69.00"}}]}]}]}
    fals.ruta("GET", f"{SB}/orders.json", (200, comandes))


def test_shopify_vendes_amb_devolucions_negatives(con, fals):
    _botiga(con)
    _productes_shopify(fals, pagina2=True)
    _comandes_shopify(fals)
    s = Shopify({"domini": "marca", "ubicacio": "55"}, "t", "B")
    des = datetime(2026, 11, 1, tzinfo=timezone.utc)
    r = s.aplica(con, ["vendes"], des, des + timedelta(days=5))
    assert (r["linies_venda"], r["devolucions"], r["comandes"]) == (2, 1, 1)
    q = fals.cridades(f"{SB}/orders.json")[0]["q"]
    assert q["updated_at_min"] == "2026-11-01T00:00:00+00:00" and q["status"] == "any" and "refunds" in q["fields"]
    files = con.execute("SELECT * FROM venda_linia ORDER BY id").fetchall()
    assert [(f["gtin"], f["quantitat"], f["import_eur"], f["devolucio"]) for f in files] == [
        ("08400000000017", 2, 138.0, 0), ("08400000000031", 1, 15.5, 0), ("08400000000017", -1, -65.0, 1)]
    assert files[2]["ts"] == "2026-11-04T10:00:00+01:00" and files[2]["tiquet_hash"] != files[0]["tiquet_hash"]

    # Tornar a demanar la mateixa finestra no duplica res.
    r = s.aplica(con, ["vendes"], des, None)
    assert (r["linies_venda"], r["devolucions"]) == (0, 0)

    # Amb en_linia, també la comanda sense ubicació; la cancel·lada mai (ni la seva devolució).
    s = Shopify({"domini": "marca", "ubicacio": "55", "en_linia": True}, "t", "B")
    r = s.aplica(con, ["vendes"], des, None)
    assert (r["linies_venda"], r["devolucions"]) == (1, 0)
    assert con.execute("SELECT COUNT(*) FROM venda_linia").fetchone()[0] == 4


def test_shopify_estoc_de_la_ubicacio(con, fals):
    _botiga(con)
    _productes_shopify(fals)
    fals.ruta("GET", f"{SB}/inventory_levels.json", (200, {"inventory_levels": [
        {"inventory_item_id": 101, "location_id": 55, "available": 4},
        {"inventory_item_id": 102, "location_id": 55, "available": -2},
        {"inventory_item_id": 999, "location_id": 55, "available": 9},
        {"inventory_item_id": 201, "location_id": 55, "available": None}]}))
    r = Shopify({"domini": "marca", "ubicacio": 55}, "t", "B").aplica(con, ["estoc"], None, None)
    assert r["estoc"] == 2
    assert fals.cridades(f"{SB}/inventory_levels.json")[0]["q"]["location_ids"] == "55"
    assert estoc.unitats(con, "B", "08400000000017") == 4 and estoc.unitats(con, "B", "08400000000024") == 0
    assert con.execute("SELECT font FROM estoc LIMIT 1").fetchone()[0] == "shopify"


def test_shopify_prova_i_errors_clars(fals):
    fals.ruta("GET", f"{SB}/shop.json", (200, {"shop": {"name": "Marca BCN", "myshopify_domain": "marca.myshopify.com",
                                                         "currency": "EUR"}}))
    fals.ruta("GET", f"{SB}/locations.json", (200, {"locations": [{"id": 55, "name": "Botiga Gràcia", "active": True}]}))
    escopes = ["read_products", "read_orders", "write_inventory", "read_locations"]
    fals.ruta("GET", "/admin/oauth/access_scopes.json",
              lambda q, c: (200, {"access_scopes": [{"handle": h} for h in escopes]}))
    s = Shopify({"domini": "marca"}, "t")
    assert s.prova() == {"botiga": "Marca BCN", "domini": "marca.myshopify.com", "moneda": "EUR",
                         "ubicacions": [{"id": "55", "nom": "Botiga Gràcia", "activa": True}]}
    escopes.remove("read_orders")
    with pytest.raises(ErrorIntegracio, match="falten permisos: read_orders"):
        s.prova()

    fals.ruta("GET", f"{SB}/shop.json", (401, {"errors": "[API] Invalid API key or access token"}))
    with pytest.raises(ErrorIntegracio, match="no accepta el testimoni"):
        s.prova()
    fals.ruta("GET", f"{SB}/shop.json", (403, {"errors": "[API] This action requires merchant approval for read_locations scope."}))
    with pytest.raises(ErrorIntegracio, match="falta el permís read_locations"):
        s.prova()
    fals.ruta("GET", f"{SB}/shop.json", (404, {"errors": "Not Found"}))
    with pytest.raises(ErrorIntegracio, match="No es troba la botiga Shopify marca.myshopify.com"):
        s.prova()

    def sense_dns(req, t):
        raise http.ErrorXarxa("Name or service not known", dns=True)
    http._obre = sense_dns  # (el monkeypatch del fixture ho restaura)
    with pytest.raises(ErrorIntegracio, match="No es troba el domini marca.myshopify.com"):
        s.prova()


def test_shopify_valida_config():
    with pytest.raises(ErrorIntegracio, match="myshopify.com"):
        Shopify.valida({"domini": "www.marca.cat"}, "B", [])
    with pytest.raises(ErrorIntegracio, match="HTTPS"):
        Shopify.valida({"domini": "http://marca.myshopify.com"}, "B", [])
    with pytest.raises(ErrorIntegracio, match="ubicació"):
        Shopify.valida({"domini": "marca"}, "B", ["vendes"])
    c = Shopify.valida({"domini": "https://Marca.myshopify.com/admin", "ubicacio": 55}, "B", ["vendes"])
    assert c["domini"] == "marca.myshopify.com" and c["ubicacio"] == "55" and c["opcio_talla"][:2] == ["Talla", "Size"]


# ---------------------------------------------------------------- Square

SQ = "/v2"


def _square(fals):
    cataleg_p1 = {"objects": [
        {"type": "CATEGORY", "id": "CAT1", "category_data": {"name": "Pantalons"}},
        {"type": "ITEM_OPTION", "id": "OPT_T", "item_option_data": {"name": "Talla", "values": [
            {"id": "V_M", "item_option_value_data": {"name": "M"}}, {"id": "V_L", "item_option_value_data": {"name": "L"}}]}},
        {"type": "ITEM", "id": "IT1", "item_data": {"name": "Pantaló", "category_id": "CAT1", "variations": [
            {"type": "ITEM_VARIATION", "id": "VAR1", "item_variation_data": {
                "item_id": "IT1", "name": "M", "upc": "8400000000048", "sku": "PAN-M",
                "price_money": {"amount": 8900, "currency": "EUR"},
                "item_option_values": [{"item_option_id": "OPT_T", "item_option_value_id": "V_M"}]}}]}}],
        "cursor": "c2"}
    cataleg_p2 = {"objects": [
        {"type": "ITEM_VARIATION", "id": "VAR2", "item_variation_data": {
            "item_id": "IT1", "name": "L, Negre", "sku": "8400000000055", "price_money": {"amount": 8900}}},
        {"type": "ITEM_VARIATION", "id": "VAR3", "item_variation_data": {"item_id": "IT1", "name": "XL", "sku": "PAN-XL"}},
        {"type": "ITEM_VARIATION", "id": "VAR9", "is_deleted": True, "item_variation_data": {"upc": "8400000000062"}}]}
    fals.ruta("GET", f"{SQ}/catalog/list", lambda q, c: (200, cataleg_p2 if q.get("cursor") == "c2" else cataleg_p1))
    comandes = [
        {"id": "ORD1", "location_id": "LOC1", "closed_at": "2026-11-03T17:00:00Z", "state": "COMPLETED",
         "line_items": [{"catalog_object_id": "VAR1", "quantity": "2", "gross_sales_money": {"amount": 17800}},
                        {"catalog_object_id": "ALTRE", "quantity": "1"}]},
        {"id": "RET1", "location_id": "LOC1", "closed_at": "2026-11-04T10:00:00Z", "state": "COMPLETED",
         "returns": [{"source_order_id": "ORD1", "return_line_items": [
             {"catalog_object_id": "VAR1", "quantity": "1", "gross_return_money": {"amount": 8900}}]}]}]
    fals.ruta("POST", f"{SQ}/orders/search",
              lambda q, c: (200, {"orders": comandes[1:]} if c.get("cursor") else {"orders": comandes[:1], "cursor": "o2"}))
    fals.ruta("POST", f"{SQ}/inventory/counts/batch-retrieve", (200, {"counts": [
        {"catalog_object_id": "VAR1", "location_id": "LOC1", "state": "IN_STOCK", "quantity": "5"},
        {"catalog_object_id": "VAR2", "location_id": "LOC1", "state": "IN_STOCK", "quantity": "0"}]}))
    fals.ruta("GET", f"{SQ}/merchants/me", (200, {"merchant": {"id": "M1", "business_name": "Marca SL", "currency": "EUR"}}))
    fals.ruta("GET", f"{SQ}/locations", (200, {"locations": [{"id": "LOC1", "name": "Girona", "status": "ACTIVE"}]}))


def test_square_cataleg_vendes_devolucions_i_estoc(con, fals):
    _botiga(con)
    _square(fals)
    s = Square(Square.valida({"ubicacio": "LOC1"}, "B", list(("cataleg", "vendes", "estoc"))), "EAAA_tok", "B")
    v = {x["gtin"]: x for x in s.cataleg()}
    assert set(v) == {"08400000000048", "08400000000055"}  # GTIN de l'upc o del sku numèric
    assert v["08400000000048"] == {"gtin": "08400000000048", "model": "IT1", "color": "", "talla": "M",
                                   "categoria": "Pantalons", "preu_eur": 89.0, "id_extern": "VAR1"}
    assert (v["08400000000055"]["talla"], v["08400000000055"]["color"]) == ("L", "Negre")

    des = datetime(2026, 11, 1, tzinfo=timezone.utc)
    r = s.aplica(con, ["cataleg", "vendes", "estoc"], des, des + timedelta(days=5))
    assert (r["cataleg"], r["linies_venda"], r["devolucions"], r["estoc"]) == (2, 1, 1, 2)
    cerca = fals.cridades(f"{SQ}/orders/search")
    assert len(cerca) == 2 and cerca[1]["cos"]["cursor"] == "o2"
    assert cerca[0]["cos"]["location_ids"] == ["LOC1"]
    assert cerca[0]["cos"]["query"]["filter"]["date_time_filter"]["closed_at"]["start_at"] == "2026-11-01T00:00:00+00:00"
    files = con.execute("SELECT gtin, quantitat, import_eur, devolucio FROM venda_linia ORDER BY id").fetchall()
    assert [tuple(f) for f in files] == [("08400000000048", 2, 178.0, 0), ("08400000000048", -1, -89.0, 1)]
    assert estoc.unitats(con, "B", "08400000000048") == 5 and estoc.unitats(con, "B", "08400000000055") == 0
    p = fals.peticions[0]
    assert p["host"] == "connect.squareup.com" and p["h"]["authorization"] == "Bearer EAAA_tok"
    assert "square-version" in p["h"]


def test_square_prova_i_errors(fals):
    _square(fals)
    s = Square({"entorn": "sandbox"}, "tok")
    assert s.prova() == {"botiga": "Marca SL", "comerc": "M1", "moneda": "EUR",
                         "ubicacions": [{"id": "LOC1", "nom": "Girona", "activa": True}]}
    assert fals.peticions[0]["host"] == "connect.squareupsandbox.com"
    fals.ruta("GET", f"{SQ}/merchants/me", (401, {"errors": [{"category": "AUTHENTICATION_ERROR", "code": "UNAUTHORIZED"}]}))
    with pytest.raises(ErrorIntegracio, match="Square no accepta el testimoni"):
        s.prova()
    fals.ruta("GET", f"{SQ}/merchants/me", (403, {"errors": [{"code": "INSUFFICIENT_SCOPES", "detail": "MERCHANT_PROFILE_READ"}]}))
    with pytest.raises(ErrorIntegracio, match="falten permisos"):
        s.prova()


# ---------------------------------------------------------------- CSV per URL


def test_csv_url_importa_sense_duplicar(con, fals):
    _botiga(con)
    _botiga(con, "ALTRA")
    vendes_csv = ("data_hora;gtin;quantitat;import;tiquet\n"
                  "2026-11-03T10:00:00+01:00;8400000000017;1;69,00;T1\n"
                  "2026-11-03T10:00:00+01:00;8400000000017;1;69,00;T1\n"   # dues unitats iguals al mateix tiquet
                  "2026-11-03T12:00:00+01:00;8400000000017;-1;-69,00;T2\n")
    fals.ruta("GET", "/vendes.csv", (200, vendes_csv.encode("cp1252")))
    fals.ruta("GET", "/estoc.csv", (200, b"botiga,gtin,unitats\nB,8400000000017,3\nALTRA,8400000000017,9\n"))
    fals.ruta("GET", "/cataleg.csv", (200, "gtin,model,color,talla,categoria,preu\n8400000000017,M1,Blau,M,camisa,69\n".encode()))
    config = CsvUrl.valida({"url_vendes": "https://tpv.test/vendes.csv", "url_estoc": "https://tpv.test/estoc.csv",
                            "url_cataleg": "https://tpv.test/cataleg.csv", "capcalera": "X-Api-Key"}, "B",
                           ["cataleg", "vendes", "estoc"])
    c = CsvUrl(config, "clau-tpv", "B")
    assert c.prova()["fitxers"]["vendes"]["files"] == 3
    r = c.aplica(con, ["cataleg", "vendes", "estoc"], None, None)
    assert (r["cataleg"], r["linies_venda"], r["devolucions"], r["estoc"], r["errors"]) == (1, 2, 1, 1, [])
    assert r["_botigues"] == ["B"]
    assert all(p["h"].get("x-api-key") == "clau-tpv" for p in fals.peticions)
    assert estoc.unitats(con, "B", "08400000000017") == 3 and estoc.unitats(con, "ALTRA", "08400000000017") is None
    # El TPV torna a exportar el mateix fitxer amb una línia nova: només entra la nova.
    fals.ruta("GET", "/vendes.csv", (200, (vendes_csv + "2026-11-04T10:00:00+01:00;8400000000017;1;69,00;T3\n").encode()))
    r = c.aplica(con, ["vendes"], None, None)
    assert (r["linies_venda"], r["devolucions"]) == (1, 0)
    assert con.execute("SELECT COUNT(*) FROM venda_linia").fetchone()[0] == 4

    with pytest.raises(ErrorIntegracio, match="https://"):
        CsvUrl.valida({"url_vendes": "http://tpv.test/v.csv"}, "B", ["vendes"])
    with pytest.raises(ErrorIntegracio, match="estoc cal la URL"):
        CsvUrl.valida({"url_vendes": "https://tpv.test/v.csv"}, "B", ["vendes", "estoc"])
    fals.ruta("GET", "/vendes.csv", (401, b"no"))
    with pytest.raises(ErrorIntegracio, match="no accepta l'autorització"):
        c.prova()


# ---------------------------------------------------------------- Motor: intervals, registre, bucle


def test_interval_i_finestra():
    ara = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
    assert motor.toca(60, None, ara)
    assert not motor.toca(60, "2026-11-06T11:30:00+00:00", ara)
    assert motor.toca(60, "2026-11-06T12:00:00+01:00", ara)       # = 11:00 UTC: fa una hora
    assert motor.toca(5, "2026-11-06T11:45:00+00:00", ara)         # mai més sovint que 15 min...
    assert not motor.toca(5, "2026-11-06T11:50:00+00:00", ara)     # ...encara que la fila digui 5
    assert motor.finestra("2026-11-06T10:00:00+00:00", ara) == datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)
    assert motor.finestra(None, ara) == ara - timedelta(days=30)


def test_motor_crea_sincronitza_registre_i_pendents(con, fals, monkeypatch):
    _botiga(con)
    _productes_shopify(fals)
    _comandes_shopify(fals)
    fals.ruta("GET", f"{SB}/inventory_levels.json", (200, {"inventory_levels": []}))
    with pytest.raises(ErrorIntegracio, match="mínim és de 15"):
        motor.crea(con, CLAU, {"proveidor": "shopify", "botiga_id": "B", "config": {"domini": "marca", "ubicacio": "55"},
                               "secret": "shpat_x", "interval_min": 10})
    with pytest.raises(ErrorIntegracio, match="secret"):
        motor.crea(con, CLAU, {"proveidor": "shopify", "botiga_id": "B", "config": {"domini": "marca", "token": "x"}})
    i = motor.crea(con, CLAU, {"proveidor": "shopify", "botiga_id": "B", "config": {"domini": "marca", "ubicacio": "55"},
                               "secret": "shpat_x"})
    assert i["interval_min"] == 60 and i["estat"] == "mai" and i["te_secret"] and i["abast"] == ["vendes", "estoc"]
    assert "shpat_x" not in json.dumps(dict(con.execute("SELECT * FROM integracio").fetchone()))

    ara = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
    assert motor.pendents(con, ara) == [i["id"]]
    fet = motor.sincronitza_pendents(con, CLAU, ara)
    # Per defecte no porta el catàleg (només enganxa l'id de variant a les que ja hi són).
    assert fet[i["id"]] == {"cataleg": 0, "linies_venda": 2, "devolucions": 1, "estoc": 0}
    f = motor.obte(con, i["id"])
    assert f["estat"] == "ok" and f["darrera_sync"] == ara.isoformat() and "2 línies de venda" in f["missatge"]
    assert motor.pendents(con, ara + timedelta(minutes=59)) == []
    assert motor.pendents(con, ara + timedelta(minutes=60)) == [i["id"]]
    # La segona sincronització demana des de la darrera menys 2 dies.
    fals.peticions.clear()
    motor.sincronitza(con, CLAU, i["id"], ara + timedelta(hours=1))
    assert fals.cridades(f"{SB}/orders.json")[0]["q"]["updated_at_min"] == "2026-11-04T12:00:00+00:00"

    # Un error queda al registre i a l'estat, i el bucle no torna a provar fins a l'interval.
    fals.ruta("GET", f"{SB}/products.json", (401, {"errors": "Invalid"}))
    t = ara + timedelta(hours=2)
    assert "no accepta el testimoni" in motor.sincronitza_pendents(con, CLAU, t)[i["id"]]["error"]
    reg = motor.registre(con, i["id"])
    assert [r["estat"] for r in reg] == ["error", "ok", "ok"] and reg[1]["resum"]["linies_venda"] == 0
    assert motor.obte(con, i["id"])["estat"] == "error"
    assert motor.pendents(con, t + timedelta(minutes=30)) == []

    # Desactivada: no toca mai.
    motor.actualitza(con, CLAU, i["id"], {"actiu": False})
    assert motor.pendents(con, t + timedelta(days=1)) == []


def test_bucle_mante_les_botigues_antigues_per_variable_d_entorn(con, fals, monkeypatch):
    _botiga(con)
    con.execute("INSERT INTO parametre (botiga_id, clau, valor) VALUES ('B', 'shopify_domini', 'marca.myshopify.com'), "
                "('B', 'shopify_ubicacio', '55')")
    _productes_shopify(fals)
    _comandes_shopify(fals)
    fals.ruta("GET", f"{SB}/inventory_levels.json", (200, {"inventory_levels": []}))
    ara = datetime.now(timezone.utc)
    assert motor.sincronitza_pendents(con, CLAU, ara) == {}  # sense testimoni, res
    monkeypatch.setenv("HEBRA_SHOPIFY_TOKEN_B", "shpat_env")
    fet = motor.sincronitza_pendents(con, CLAU, ara)
    assert fet["shopify:B"]["linies"] == 2 and fals.peticions[0]["h"]["x-shopify-access-token"] == "shpat_env"
    assert motor.sincronitza_pendents(con, CLAU, ara) == {}  # fins d'aquí a una hora, res
    # Si la botiga té una integració Shopify activa, mana la integració.
    motor.crea(con, CLAU, {"proveidor": "shopify", "botiga_id": "B", "config": {"domini": "marca", "ubicacio": "55"},
                           "secret": "shpat_nou", "abast": ["vendes"]})
    assert motor.botigues_antigues(con) == []


def test_bucle_botigues_antigues_compta_l_intent_encara_que_falli(con, fals, monkeypatch):
    """Revisió: si la sincronització antiga falla, no s'ha de tornar a provar cada minut sinó cada hora."""
    _botiga(con)
    con.execute("INSERT INTO parametre (botiga_id, clau, valor) VALUES ('B', 'shopify_domini', 'marca.myshopify.com'), "
                "('B', 'shopify_ubicacio', '55')")
    monkeypatch.setenv("HEBRA_SHOPIFY_TOKEN_B", "shpat_env")
    fals.ruta("GET", f"{SB}/products.json", (401, {"errors": "Invalid"}))
    ara = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
    assert "error" in motor.sincronitza_pendents(con, CLAU, ara)["shopify:B"]
    n = len(fals.peticions)
    assert motor.sincronitza_pendents(con, CLAU, ara + timedelta(minutes=1)) == {}
    assert motor.sincronitza_pendents(con, CLAU, ara + timedelta(minutes=59)) == {}
    assert len(fals.peticions) == n
    assert "error" in motor.sincronitza_pendents(con, CLAU, ara + timedelta(minutes=60))["shopify:B"]


def test_cataleg_no_trepitja_model_color_talla_ni_categoria(con, fals):
    """Revisió: el catàleg del proveïdor crea els GTIN nous i només n'actualitza el preu als que ja hi són."""
    _botiga(con)
    con.execute("""INSERT INTO catalog_sku (gtin, model, color, talla, categoria, preu_eur, origen_json)
                   VALUES ('08400000000017', 'CL-24-NAT', 'Natural', 'S', 'camisa', 59.0, '{"x": 1}')""")
    con.commit()
    _productes_shopify(fals)
    r = Shopify({"domini": "marca"}, "t", None).aplica(con, ["cataleg"], None, None)
    assert r["cataleg"] == 3
    f = con.execute("SELECT * FROM catalog_sku WHERE gtin = '08400000000017'").fetchone()
    assert (f["model"], f["color"], f["talla"], f["categoria"], f["origen_json"]) == \
        ("CL-24-NAT", "Natural", "S", "camisa", '{"x": 1}')
    assert f["preu_eur"] == 69.0 and f["variant_shopify"] == "11"   # el preu i l'id extern sí
    nova = con.execute("SELECT * FROM catalog_sku WHERE gtin = '08400000000024'").fetchone()
    assert (nova["model"], nova["talla"]) == ("7001", "L")          # la nova, sencera
    # Per defecte, una integració nova de Shopify o Square no porta el catàleg.
    i = motor.crea(con, CLAU, {"proveidor": "square", "botiga_id": "B", "config": {"ubicacio": "L1"}, "secret": "EAAA"})
    assert i["abast"] == ["vendes", "estoc"]


def test_prova_no_envia_el_secret_desat_a_un_desti_nou(con, fals):
    """Revisió: `prova` (i `actualitza`) amb `id` no fa servir el secret desat si la config apunta a un altre lloc."""
    _botiga(con)
    fals.ruta("GET", f"{SB}/shop.json", (200, {"shop": {"name": "Marca"}}))
    fals.ruta("GET", f"{SB}/locations.json", (200, {"locations": []}))
    fals.ruta("GET", "/v.csv", (200, b"data_hora;gtin;quantitat\n"))
    i = motor.crea(con, CLAU, {"proveidor": "shopify", "botiga_id": "B", "config": {"domini": "marca", "ubicacio": "55"},
                               "secret": "shpat_desat"})
    # Mateix domini (amb una altra opció canviada): fa servir el desat.
    assert motor.prova(con, CLAU, None, {"domini": "marca.myshopify.com", "en_linia": True}, None, i["id"])["botiga"] == "Marca"
    assert fals.peticions[-1]["h"]["x-shopify-access-token"] == "shpat_desat"
    fals.peticions.clear()
    with pytest.raises(ErrorIntegracio, match="torna a escriure el testimoni"):
        motor.prova(con, CLAU, None, {"domini": "dolenta"}, None, i["id"])
    assert fals.peticions == []
    # Amb el secret a la petició, sí (és el que acaba d'escriure la persona).
    motor.prova(con, CLAU, None, {"domini": "altra"}, "shpat_nou", i["id"])
    assert fals.peticions[-1]["host"] == "altra.myshopify.com"
    assert fals.peticions[-1]["h"]["x-shopify-access-token"] == "shpat_nou"
    with pytest.raises(ErrorIntegracio, match="torna a escriure"):
        motor.actualitza(con, CLAU, i["id"], {"config": {"domini": "dolenta", "ubicacio": "55"}})
    assert motor.actualitza(con, CLAU, i["id"], {"config": {"domini": "dolenta", "ubicacio": "55"},
                                                 "secret": "shpat_x"})["config"]["domini"] == "dolenta.myshopify.com"

    # CSV: un altre servidor necessita la capçalera de nou; el mateix servidor amb un altre fitxer, no.
    c = motor.crea(con, CLAU, {"proveidor": "csv_url", "botiga_id": "B", "secret": "Bearer desat",
                               "config": {"url_vendes": "https://tpv.test/v.csv"}})
    fals.peticions.clear()
    motor.prova(con, CLAU, None, {"url_vendes": "https://tpv.test/v.csv?x=1"}, None, c["id"])
    assert fals.peticions[-1]["h"]["authorization"] == "Bearer desat"
    fals.peticions.clear()
    with pytest.raises(ErrorIntegracio, match="adreces dels fitxers"):
        motor.prova(con, CLAU, None, {"url_vendes": "https://dolent.test/v.csv"}, None, c["id"])
    with pytest.raises(ErrorIntegracio, match="torna a escriure"):
        motor.prova(con, CLAU, None, {"url_vendes": "https://tpv.test/v.csv",
                                      "url_estoc": "https://dolent.test/e.csv"}, None, c["id"])
    assert fals.peticions == []
    # Square: canviar d'entorn també.
    q = motor.crea(con, CLAU, {"proveidor": "square", "botiga_id": "B", "config": {"ubicacio": "L1"}, "secret": "EAAA"})
    with pytest.raises(ErrorIntegracio, match="entorn de Square"):
        motor.prova(con, CLAU, None, {"ubicacio": "L1", "entorn": "sandbox"}, None, q["id"])


# ---------------------------------------------------------------- API


@pytest.fixture
def entorn(tmp_path, monkeypatch):
    monkeypatch.setenv("HEBRA_BD", str(tmp_path / "api.db"))
    monkeypatch.setenv("HEBRA_SECRET", CLAU)
    monkeypatch.setenv("HEBRA_FRONTEND_DIST", str(tmp_path / "no-hi-es"))
    monkeypatch.setattr(auth, "ITERACIONS", 1000)
    from hebra import app as app_mod
    app_mod = importlib.reload(app_mod)
    con = app_mod.con
    con.execute("INSERT INTO botiga (id, nom) VALUES ('BCN-01', 'Barcelona')")
    con.commit()
    auth.crea_usuari(con, "marca@hebra.cat", "Marca", "marca", "contrasenya-marca")
    auth.crea_usuari(con, "bcn@hebra.cat", "BCN", "botiga", "contrasenya-bcn", "BCN-01")
    return app_mod, con


def _client(app_mod, correu):
    c = TestClient(app_mod.app)
    r = c.post("/api/v2/sessio", json={"correu": correu, "contrasenya": f"contrasenya-{correu.split('@')[0]}"})
    assert r.status_code == 200, r.text
    return c


def test_api_integracions_rols_i_secret_mai_surt(entorn, fals):
    app_mod, con = entorn
    _productes_shopify(fals)
    _comandes_shopify(fals)
    fals.ruta("GET", f"{SB}/inventory_levels.json", (200, {"inventory_levels": []}))
    fals.ruta("GET", f"{SB}/shop.json", (200, {"shop": {"name": "Marca BCN"}}))
    fals.ruta("GET", f"{SB}/locations.json", (200, {"locations": [{"id": 55, "name": "Gràcia"}]}))

    botiga = _client(app_mod, "bcn@hebra.cat")
    assert botiga.get("/api/v2/integracions").status_code == 403
    assert botiga.post("/api/v2/integracions/prova", json={"proveidor": "shopify"}).status_code == 403
    assert TestClient(app_mod.app).get("/api/v2/integracions").status_code == 401

    c = _client(app_mod, "marca@hebra.cat")
    TOKEN = "shpat_aixo_no_ha_de_sortir_mai"
    r = c.post("/api/v2/integracions/prova", json={"proveidor": "shopify", "config": {"domini": "marca"}, "secret": TOKEN})
    assert r.status_code == 200 and r.json() == {"ok": True, "detall": {
        "botiga": "Marca BCN", "domini": "marca.myshopify.com", "moneda": None,
        "ubicacions": [{"id": "55", "nom": "Gràcia", "activa": True}]}}
    r = c.post("/api/v2/integracions/prova", json={"proveidor": "shopify", "config": {"domini": "marca.cat"}, "secret": "x"})
    assert r.status_code == 400 and "myshopify.com" in r.json()["detail"]

    r = c.post("/api/v2/integracions", json={"botiga_id": "BCN-01", "proveidor": "shopify", "secret": TOKEN,
                                             "config": {"domini": "marca", "ubicacio": "55"}, "interval_min": 30})
    assert r.status_code == 200, r.text
    i = r.json()
    assert set(i) == {"id", "botiga_id", "proveidor", "config", "te_secret", "actiu", "abast", "interval_min",
                      "darrera_sync", "estat", "missatge"}
    assert i["te_secret"] is True and i["interval_min"] == 30 and i["estat"] == "mai"
    assert c.post("/api/v2/integracions", json={"proveidor": "shopify", "botiga_id": "NO", "secret": "x",
                                                "config": {"domini": "marca"}}).status_code == 400
    assert c.post("/api/v2/integracions", json={"proveidor": "res"}).status_code == 400

    # Prova d'una integració desada sense tornar a enviar el testimoni.
    assert c.post("/api/v2/integracions/prova", json={"id": i["id"]}).json()["ok"] is True
    assert fals.peticions[-1]["h"]["x-shopify-access-token"] == TOKEN

    r = c.post(f"/api/v2/integracions/{i['id']}/sincronitza")
    assert r.status_code == 200 and r.json() == {"resum": {"cataleg": 0, "linies_venda": 2, "devolucions": 1, "estoc": 0}}
    reg = c.get(f"/api/v2/integracions/{i['id']}/registre").json()["registre"]
    assert len(reg) == 1 and reg[0]["estat"] == "ok" and reg[0]["resum"]["devolucions"] == 1 and reg[0]["fi"]

    r = c.patch(f"/api/v2/integracions/{i['id']}", json={"actiu": False, "secret": "shpat_nou_" + TOKEN})
    assert r.status_code == 200 and r.json()["actiu"] is False and r.json()["te_secret"] is True
    assert c.patch(f"/api/v2/integracions/{i['id']}", json={"interval_min": 5}).status_code == 400
    assert c.patch("/api/v2/integracions/999", json={"actiu": True}).status_code == 404

    # El testimoni no surt mai: ni a les respostes ni en clar a la base de dades.
    tot = json.dumps([c.get("/api/v2/integracions").json(), r.json(), reg])
    assert TOKEN not in tot and "shpat" not in tot and "secret_xifrat" not in tot
    assert TOKEN not in json.dumps([dict(f) for f in con.execute("SELECT * FROM integracio")])

    fals.ruta("GET", f"{SB}/products.json", (401, {}))
    r = c.post(f"/api/v2/integracions/{i['id']}/sincronitza")
    assert r.status_code == 400 and "testimoni" in r.json()["detail"] and TOKEN not in r.text
    assert c.get("/api/v2/integracions").json()["integracions"][0]["estat"] == "error"

    assert c.delete(f"/api/v2/integracions/{i['id']}").json() == {"ok": True}
    assert c.get("/api/v2/integracions").json() == {"integracions": []}
    assert c.get(f"/api/v2/integracions/{i['id']}/registre").status_code == 404
