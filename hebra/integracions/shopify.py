"""Connector de Shopify (Admin REST API, només lectura).

App personalitzada de la botiga amb testimoni `shpat_...` i permisos de només lectura
`read_products`, `read_orders`, `read_inventory` i `read_locations` (docs/INSTAL-LACIO.md).

  * catàleg: productes i variants -> catalog_sku. GTIN = codi de barres; model = id del producte
    (`config.model = "producte"`, per defecte) o SKU base (`"sku_base"`: el SKU sense la talla
    i el color del final); talla i color de les opcions amb noms configurables
    (`opcio_talla`, `opcio_color`; per defecte «Talla»/«Size» i «Color»); categoria = product_type.
    L'id de variant es desa sempre a `catalog_sku.variant_shopify` per a les variants que ja hi són.
  * vendes: comandes de la ubicació (`config.ubicacio`, o `ubicacions` per a tota la marca) i,
    amb `en_linia`, també les comandes en línia (sense ubicació). Es demanen per data
    d'actualització, així les devolucions (refunds) d'una comanda antiga també arriben; cada
    devolució es desa com a línies negatives (`devolucio = 1`). Les comandes cancel·lades no compten.
  * estoc: nivells d'inventari (`available`) de la ubicació.

No escriu mai res a Shopify.
"""

import os
import re
import sqlite3
import urllib.parse
from datetime import datetime, timedelta

from .. import db, temps, vendes as vendes_mod
from . import http
from .base import (OPCIONS_COLOR, OPCIONS_TALLA, TALLA_UNICA, Connector, ErrorIntegracio, gtin, noms_opcio,
                   sku_base)

API_VERSIO = "2026-10"  # versió fixada de l'Admin API; revisar-la cada any (Shopify en retira les antigues)
TEMPS_ESPERA_S = 20
MAX_PAGINES = 200
PERMISOS = ("read_products", "read_orders", "read_inventory", "read_locations")
PERMIS_DEL_RECURS = {"products": "read_products", "orders": "read_orders", "inventory_levels": "read_inventory",
                     "locations": "read_locations"}


class ErrorShopify(ErrorIntegracio):
    pass


def nom_variable_token(botiga_id: str) -> str:
    return "HEBRA_SHOPIFY_TOKEN_" + re.sub(r"[^A-Z0-9]", "_", botiga_id.upper())


def _base(domini: str) -> str:
    domini = (domini or "").strip()
    if not domini:
        raise ErrorShopify("Falta el domini de la botiga Shopify (p. ex. marca.myshopify.com)")
    if domini.startswith(("http://", "https://")):
        parts = urllib.parse.urlsplit(domini)
        host = parts.hostname or ""
        if parts.scheme == "http" and host not in ("127.0.0.1", "localhost"):
            raise ErrorShopify("Shopify només per HTTPS")
        return f"{parts.scheme}://{parts.netloc}"
    host = domini.strip("/").split("/")[0].lower()
    if "." not in host:
        host += ".myshopify.com"
    return f"https://{host}"


class Client:
    def __init__(self, domini: str, token: str, versio: str = API_VERSIO):
        self.arrel = _base(domini)
        self.host = urllib.parse.urlsplit(self.arrel).netloc
        self.base = f"{self.arrel}/admin/api/{versio}"
        self.token = token

    def _error(self, e: Exception, recurs: str) -> ErrorShopify:
        if isinstance(e, http.ErrorXarxa):
            if e.dns:
                return ErrorShopify(f"No es troba el domini {self.host}: revisa que estigui ben escrit "
                                    "(ha de ser el de Shopify, p. ex. marca.myshopify.com)")
            return ErrorShopify(f"No es pot connectar amb Shopify ({e.motiu}). Revisa la connexió a internet del servidor")
        assert isinstance(e, http.ErrorHttp)
        if e.estat == 401:
            return ErrorShopify("Shopify no accepta el testimoni d'accés: revisa que sigui el de l'app personalitzada "
                                "d'aquesta botiga (comença per shpat_) i que l'app estigui instal·lada")
        if e.estat == 403:
            m = re.search(r"\b(read_[a-z_]+)\b", e.cos)
            permis = m.group(1) if m else PERMIS_DEL_RECURS.get(recurs, "de lectura")
            return ErrorShopify(f"Al testimoni li falta el permís {permis}. A Shopify, a l'app personalitzada, "
                                f"marca {permis} a la configuració de l'Admin API i torna-la a instal·lar")
        if e.estat == 404:
            return ErrorShopify(f"No es troba la botiga Shopify {self.host} (o el recurs {recurs}): revisa el domini, "
                                "p. ex. marca.myshopify.com")
        if e.estat == 402:
            return ErrorShopify(f"La botiga Shopify {self.host} no està activa (pla pendent de pagament)")
        if e.estat == 423:
            return ErrorShopify(f"La botiga Shopify {self.host} està bloquejada")
        if e.estat == 429:
            return ErrorShopify("Shopify ha limitat les peticions (massa en poc temps). Es tornarà a provar a la "
                                "propera sincronització")
        if e.estat >= 500:
            return ErrorShopify(f"Shopify no respon bé ara mateix (error {e.estat}). Torna-ho a provar d'aquí a una estona")
        return ErrorShopify(f"Shopify ha respost {e.estat} a {urllib.parse.urlsplit(e.url).path}")

    def _get(self, url: str, recurs: str = "") -> tuple[dict, str | None]:
        try:
            r = http.peticio("GET", url, {"X-Shopify-Access-Token": self.token}, temps_espera=TEMPS_ESPERA_S)
        except (http.ErrorHttp, http.ErrorXarxa) as e:
            raise self._error(e, recurs) from e
        try:
            dades = r.json()
        except ValueError as e:
            raise ErrorShopify("Shopify ha tornat una resposta que no s'entén (és el domini de Shopify?)") from e
        _frena(r.capcaleres.get("x-shopify-shop-api-call-limit", ""))
        return dades, _pagina_seguent(r.capcaleres.get("link", ""))

    def un(self, recurs: str, **params) -> dict:
        q = f"?{urllib.parse.urlencode(params)}" if params else ""
        return self._get(f"{self.base}/{recurs}.json{q}", recurs)[0]

    def llista(self, recurs: str, clau: str, **params) -> list[dict]:
        """GET paginat (capçalera Link, rel="next")."""
        url: str | None = f"{self.base}/{recurs}.json?{urllib.parse.urlencode(dict(params, limit=250))}"
        resultat = []
        for _ in range(MAX_PAGINES):
            if not url:
                break
            dades, url = self._get(url, recurs)
            resultat.extend(dades.get(clau, []))
        return resultat

    def permisos(self) -> set[str] | None:
        """Permisos del testimoni (oauth/access_scopes, sense versió). None si no es poden saber."""
        try:
            r = http.peticio("GET", f"{self.arrel}/admin/oauth/access_scopes.json",
                             {"X-Shopify-Access-Token": self.token}, temps_espera=TEMPS_ESPERA_S)
            return {s.get("handle") for s in r.json().get("access_scopes", [])}
        except (http.ErrorHttp, http.ErrorXarxa, ValueError, AttributeError):
            return None


def _frena(limit: str) -> None:
    """Si el cubell de peticions de Shopify (p. ex. "32/40") és gairebé ple, espera una mica."""
    try:
        fet, total = (int(x) for x in limit.split("/"))
    except ValueError:
        return
    if total and fet / total >= 0.8:
        http._dorm(1.0)


def _pagina_seguent(link: str) -> str | None:
    for part in link.split(","):
        m = re.search(r'<([^>]+)>\s*;\s*rel="?next"?', part)
        if m:
            return m.group(1)
    return None


_gtin = gtin  # compatibilitat


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


class Shopify(Connector):
    proveidor = "shopify"
    enllaca_variants = True

    def __init__(self, config: dict, secret: str | None, botiga_id: str | None = None, client: Client | None = None):
        super().__init__(config, secret, botiga_id)
        self.client = client or Client(self.config.get("domini", ""), self.secret)
        self._variants: list[dict] | None = None
        self._gtin_variant: dict[str, str] = {}
        self._gtin_article: dict[str, str] = {}

    @classmethod
    def valida(cls, config: dict, botiga_id: str | None, abast: list[str]) -> dict:
        c = dict(config or {})
        base = _base(c.get("domini", ""))
        host = urllib.parse.urlsplit(base).hostname or ""
        if not (host.endswith(".myshopify.com") or host in ("127.0.0.1", "localhost")):
            raise ErrorShopify("Fes servir el domini intern de Shopify, acabat en .myshopify.com (el trobaràs a "
                               "Configuració > Dominis)")
        c["domini"] = host if base.startswith("https://") else base
        if c.get("model", "producte") not in ("producte", "sku_base"):
            raise ErrorShopify("«model» ha de ser «producte» o «sku_base»")
        c["opcio_talla"] = noms_opcio(c.get("opcio_talla"), OPCIONS_TALLA)
        c["opcio_color"] = noms_opcio(c.get("opcio_color"), OPCIONS_COLOR)
        c["en_linia"] = bool(c.get("en_linia", False))
        _valida_ubicacions(c, botiga_id, abast, "Shopify")
        return c

    # ------------------------------------------------------------ prova
    def prova(self) -> dict:
        shop = self.client.un("shop").get("shop", {})
        ubicacions = self.client.llista("locations", "locations")
        permisos = self.client.permisos()
        if permisos is not None:
            falten = [p for p in PERMISOS if p not in permisos and p.replace("read_", "write_") not in permisos]
            if falten:
                raise ErrorShopify(f"Al testimoni li falten permisos: {', '.join(falten)}. A Shopify, a l'app "
                                   "personalitzada, marca'ls a la configuració de l'Admin API i torna-la a instal·lar")
        return {"botiga": shop.get("name"), "domini": shop.get("myshopify_domain") or self.client.host,
                "moneda": shop.get("currency"),
                "ubicacions": [{"id": str(u["id"]), "nom": u.get("name") or str(u["id"]), "activa": bool(u.get("active", True))}
                               for u in ubicacions]}

    # ------------------------------------------------------------ catàleg
    def cataleg(self) -> list[dict]:
        if self._variants is not None:
            return self._variants
        noms_talla = [n.casefold() for n in noms_opcio(self.config.get("opcio_talla"), OPCIONS_TALLA)]
        noms_color = [n.casefold() for n in noms_opcio(self.config.get("opcio_color"), OPCIONS_COLOR)]
        per_sku = self.config.get("model") == "sku_base"
        longitud = self.config.get("sku_base_longitud")
        resultat = []
        productes = self.client.llista("products", "products",
                                       fields="id,title,product_type,options,variants")
        for p in productes:
            posicions = {(o.get("name") or "").strip().casefold(): o.get("position") for o in p.get("options") or []}
            pos_talla = next((posicions[n] for n in noms_talla if n in posicions), None)
            pos_color = next((posicions[n] for n in noms_color if n in posicions), None)
            for v in p.get("variants", []):
                g = gtin(v.get("barcode"))
                if not g:
                    continue
                self._gtin_variant[str(v["id"])] = g
                if v.get("inventory_item_id"):
                    self._gtin_article[str(v["inventory_item_id"])] = g
                talla = (v.get(f"option{pos_talla}") if pos_talla else None) or TALLA_UNICA
                color = (v.get(f"option{pos_color}") if pos_color else None) or ""
                model = str(p.get("id"))
                if per_sku and v.get("sku"):
                    model = sku_base(v["sku"], [talla, color], int(longitud) if longitud else None)
                try:
                    preu = float(v["price"]) if v.get("price") not in (None, "") else None
                except ValueError:
                    preu = None
                resultat.append({"gtin": g, "model": model, "color": color, "talla": talla,
                                 "categoria": (p.get("product_type") or "").strip() or "altres",
                                 "preu_eur": preu, "id_extern": str(v["id"])})
        self._variants = resultat
        return resultat

    # ------------------------------------------------------------ vendes
    def vendes(self, des: datetime | None, fins: datetime | None) -> list[dict]:
        self.cataleg()
        params = {"status": "any",
                  "fields": "id,created_at,processed_at,cancelled_at,location_id,line_items,refunds"}
        if des:
            params["updated_at_min"] = _iso(des)
        if fins:
            params["updated_at_max"] = _iso(fins)
        linies = []
        for c in self.client.llista("orders", "orders", **params):
            ub = None if c.get("location_id") in (None, "") else str(c["location_id"])
            de_la_botiga = ub in self.mapa
            tiquet = f"shopify:{c['id']}"
            cancel = bool(c.get("cancelled_at"))
            if de_la_botiga and not cancel:
                ts = c.get("processed_at") or c["created_at"]
                for li in c.get("line_items", []):
                    g = self._gtin_variant.get(str(li.get("variant_id")))
                    q = int(li.get("quantity") or 0)
                    if g and q > 0:
                        linies.append({"tiquet": tiquet, "ubicacio": ub, "ts": ts, "gtin": g, "quantitat": q,
                                       "import_eur": float(li.get("price") or 0) * q, "devolucio": 0})
            for r in c.get("refunds") or []:
                ts_r = r.get("processed_at") or r.get("created_at") or c["created_at"]
                for rli in r.get("refund_line_items") or []:
                    li = rli.get("line_item") or {}
                    g = self._gtin_variant.get(str(li.get("variant_id")))
                    q = int(rli.get("quantity") or 0)
                    ub_r = ub if de_la_botiga else (None if rli.get("location_id") is None else str(rli["location_id"]))
                    if not g or q <= 0 or ub_r not in self.mapa:
                        continue
                    subtotal = rli.get("subtotal")
                    imp = float(subtotal) if subtotal not in (None, "") else float(li.get("price") or 0) * q
                    linies.append({"tiquet": f"{tiquet}:devolucio:{r.get('id')}", "ubicacio": ub_r, "ts": ts_r,
                                   "gtin": g, "quantitat": -q, "import_eur": -abs(imp), "devolucio": 1,
                                   # d'una comanda cancel·lada només si la venda ja s'havia importat
                                   "requereix": tiquet if cancel else None})
        return linies

    # ------------------------------------------------------------ estoc
    def estoc(self) -> list[dict]:
        self.cataleg()
        if not self.ubicacions:
            return []
        nivells = []
        for n in self.client.llista("inventory_levels", "inventory_levels", location_ids=",".join(self.ubicacions)):
            g = self._gtin_article.get(str(n.get("inventory_item_id")))
            if g is None or n.get("available") is None:
                continue
            nivells.append({"ubicacio": str(n.get("location_id") or self.ubicacions[0]), "gtin": g,
                            "unitats": int(n["available"])})
        return nivells


def _valida_ubicacions(c: dict, botiga_id: str | None, abast: list[str], nom: str) -> None:
    if c.get("ubicacions") is not None and not isinstance(c["ubicacions"], dict):
        raise ErrorIntegracio("«ubicacions» ha de ser {\"<id d'ubicació>\": \"<botiga>\"}")
    if c.get("ubicacio") not in (None, ""):
        c["ubicacio"] = str(c["ubicacio"])
        if not botiga_id:
            raise ErrorIntegracio("Amb una sola ubicació cal dir de quina botiga és (botiga_id), o fes servir «ubicacions»")
    if {"vendes", "estoc"} & set(abast) and not c.get("ubicacio") and not c.get("ubicacions"):
        raise ErrorIntegracio(f"Tria la ubicació de {nom} de la botiga (fes «Prova la connexió» per veure-les)")


# ---------------------------------------------------------------- compatibilitat (v0.2)


def sincronitza(con: sqlite3.Connection, botiga_id: str, client: Client | None = None) -> dict:
    """Sincronització amb la configuració antiga: paràmetres `shopify_domini` i `shopify_ubicacio`
    i variable d'entorn HEBRA_SHOPIFY_TOKEN_<BOTIGA>. Torna {"comandes", "linies", "estoc"}."""
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
    ara = temps.ara(botiga["zona_horaria"])
    darrera = db.parametre(con, botiga_id, "shopify_darrera_sync")
    des = datetime.fromisoformat(darrera) - timedelta(days=2) if darrera else None
    conn = Shopify({"ubicacio": ubicacio}, client.token, botiga_id, client=client)
    r = conn.aplica(con, ["vendes", "estoc"], des, None)
    db.desa_parametre(con, botiga_id, "shopify_darrera_sync", ara)
    vendes_mod.atribueix(con, botiga_id)
    return {"comandes": r["comandes"], "linies": r["linies_venda"], "estoc": r["estoc"]}

