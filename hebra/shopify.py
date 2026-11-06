"""Shopify (només lectura): comandes i estoc d'una ubicació (botiga física) per l'Admin REST API.

Configuració per botiga:
  * paràmetre `shopify_domini`   p. ex. `marca.myshopify.com` (taula `parametre`);
  * paràmetre `shopify_ubicacio` id numèric de la ubicació (location) de la botiga;
  * variable d'entorn `HEBRA_SHOPIFY_TOKEN_<BOTIGA>` amb el testimoni d'accés d'una
    app personalitzada amb permisos `read_orders`, `read_products` i `read_inventory`.
    <BOTIGA> és l'id en majúscules amb els caràcters no alfanumèrics canviats per `_`
    (BCN-01 -> HEBRA_SHOPIFY_TOKEN_BCN_01).

Què fa `sincronitza`:
  1. Llegeix tots els productes i en treu, per variant, el codi de barres (= GTIN)
     i l'`inventory_item_id`. Desa l'id de variant a `catalog_sku.variant_shopify`.
  2. Comandes creades des de la darrera sincronització (paràmetre `shopify_darrera_sync`)
     de la ubicació de la botiga -> `venda_linia`. El tiquet es desa xifrat com a
     vendes.py (`shopify:<id de comanda>`); una comanda ja importada no es torna a importar.
     Les comandes cancel·lades no compten. Les devolucions (refunds) encara no s'importen.
  3. Nivells d'inventari de la ubicació -> taula `estoc` (font 'shopify').
  4. Recalcula les atribucions de la botiga.

No escriu mai res a Shopify.
"""

import json
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from . import db, estoc, temps, vendes

API_VERSIO = "2026-10"  # versió fixada de l'Admin API; revisar-la cada any (Shopify en retira les antigues)
TEMPS_ESPERA_S = 20
MAX_PAGINES = 200


class ErrorShopify(Exception):
    pass


def nom_variable_token(botiga_id: str) -> str:
    return "HEBRA_SHOPIFY_TOKEN_" + re.sub(r"[^A-Z0-9]", "_", botiga_id.upper())


class Client:
    def __init__(self, domini: str, token: str, versio: str = API_VERSIO):
        if domini.startswith(("http://", "https://")):
            base = domini.rstrip("/")
            host = urllib.parse.urlsplit(base).hostname or ""
            if base.startswith("http://") and host not in ("127.0.0.1", "localhost"):
                raise ErrorShopify("Shopify només per HTTPS")
        else:
            base = f"https://{domini.strip('/')}"
        self.base = f"{base}/admin/api/{versio}"
        self.token = token

    def _get(self, url: str) -> tuple[dict, str | None]:
        req = urllib.request.Request(url, headers={"X-Shopify-Access-Token": self.token, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TEMPS_ESPERA_S) as r:
                dades = json.loads(r.read().decode("utf-8"))
                return dades, _pagina_seguent(r.headers.get("Link", ""))
        except urllib.error.HTTPError as e:
            raise ErrorShopify(f"Shopify ha respost {e.code} a {urllib.parse.urlsplit(url).path}") from e
        except urllib.error.URLError as e:
            raise ErrorShopify(f"No es pot connectar amb Shopify: {e.reason}") from e

    def llista(self, recurs: str, clau: str, **params) -> list[dict]:
        """GET paginat (capçalera Link, rel="next")."""
        url: str | None = f"{self.base}/{recurs}.json?{urllib.parse.urlencode(dict(params, limit=250))}"
        resultat = []
        for _ in range(MAX_PAGINES):
            if not url:
                break
            dades, url = self._get(url)
            resultat.extend(dades.get(clau, []))
        return resultat


def _pagina_seguent(link: str) -> str | None:
    for part in link.split(","):
        m = re.search(r'<([^>]+)>\s*;\s*rel="?next"?', part)
        if m:
            return m.group(1)
    return None


def _gtin(codi: str | None) -> str | None:
    codi = (codi or "").strip()
    return codi.zfill(14) if codi.isdigit() and len(codi) <= 14 else None


def sincronitza(con: sqlite3.Connection, botiga_id: str, client: Client | None = None) -> dict:
    """Sincronitza comandes i estoc d'una botiga. Retorna {"comandes", "linies", "estoc"}."""
    botiga = con.execute("SELECT * FROM botiga WHERE id = ?", (botiga_id,)).fetchone()
    if botiga is None:
        raise ErrorShopify(f"Botiga desconeguda: {botiga_id}")
    ubicacio = db.parametre(con, botiga_id, "shopify_ubicacio")
    if client is None:
        domini = db.parametre(con, botiga_id, "shopify_domini")
        token = os.environ.get(nom_variable_token(botiga_id), "")
        if not domini or not ubicacio or not token:
            raise ErrorShopify(f"Falta configurar Shopify per a {botiga_id}: paràmetres shopify_domini i "
                               f"shopify_ubicacio i variable {nom_variable_token(botiga_id)}")
        client = Client(domini, token)
    if not ubicacio:
        raise ErrorShopify(f"Falta el paràmetre shopify_ubicacio per a {botiga_id}")
    zona = botiga["zona_horaria"]

    # 1. Variants: codi de barres (GTIN) i article d'inventari.
    gtin_variant, gtin_article = {}, {}
    for prod in client.llista("products", "products", fields="id,variants"):
        for v in prod.get("variants", []):
            g = _gtin(v.get("barcode"))
            if not g:
                continue
            gtin_variant[str(v["id"])] = g
            if v.get("inventory_item_id"):
                gtin_article[str(v["inventory_item_id"])] = g
            con.execute("UPDATE catalog_sku SET variant_shopify = ? WHERE gtin = ?", (str(v["id"]), g))

    # 2. Comandes de la ubicació des de la darrera sincronització.
    ara = temps.ara(zona)
    des = db.parametre(con, botiga_id, "shopify_darrera_sync")
    params = {"status": "any", "fields": "id,created_at,processed_at,cancelled_at,location_id,line_items"}
    if des:
        # Un dia de marge per si alguna comanda s'ha processat tard; les ja importades se salten.
        params["created_at_min"] = (datetime.fromisoformat(des) - timedelta(days=1)).isoformat()
    n_comandes = n_linies = 0
    for comanda in client.llista("orders", "orders", **params):
        if str(comanda.get("location_id")) != str(ubicacio) or comanda.get("cancelled_at"):
            continue
        tiquet = vendes._hash_tiquet(f"shopify:{comanda['id']}")
        if con.execute("SELECT 1 FROM venda_linia WHERE botiga_id = ? AND tiquet_hash = ? LIMIT 1",
                       (botiga_id, tiquet)).fetchone():
            continue  # ja importada
        ts = temps.local(comanda.get("processed_at") or comanda["created_at"], zona)
        afegides = 0
        for linia in comanda.get("line_items", []):
            g = gtin_variant.get(str(linia.get("variant_id")))
            quantitat = int(linia.get("quantity") or 0)
            if not g or quantitat == 0:
                continue
            preu = float(linia.get("price") or 0) * quantitat
            con.execute(
                """INSERT INTO venda_linia (botiga_id, ts, data, gtin, quantitat, import_eur, tiquet_hash, devolucio)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)""", (botiga_id, ts, ts[:10], g, quantitat, round(preu, 2), tiquet))
            afegides += 1
        n_linies += afegides
        n_comandes += 1 if afegides else 0

    # 3. Estoc de la ubicació.
    n_estoc = 0
    for nivell in client.llista("inventory_levels", "inventory_levels", location_ids=ubicacio):
        g = gtin_article.get(str(nivell.get("inventory_item_id")))
        if g is None or nivell.get("available") is None:
            continue
        estoc.desa(con, botiga_id, g, max(0, int(nivell["available"])), font="shopify", ts=ara)
        n_estoc += 1
    con.commit()
    db.desa_parametre(con, botiga_id, "shopify_darrera_sync", ara)
    vendes.atribueix(con, botiga_id)
    return {"comandes": n_comandes, "linies": n_linies, "estoc": n_estoc}
