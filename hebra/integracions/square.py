"""Connector de Square (API REST v2, només lectura, testimoni d'accés).

  * catàleg: `GET /v2/catalog/list` (ITEM, ITEM_VARIATION, i ITEM_OPTION i CATEGORY per als noms).
    GTIN = `upc` de la variant o, si no en té, el `sku` si són xifres. Talla i color de les opcions
    de l'article (noms configurables com a Shopify) o, si no n'hi ha, del nom de la variant
    («M, Blau» o «M / Blau»: primer la talla). Model = id de l'article o SKU base (`config.model`).
  * vendes: `POST /v2/orders/search` per ubicació (comandes COMPLETED per data de tancament).
    Les devolucions (`returns[].return_line_items`) es desen com a línies negatives (`devolucio = 1`).
  * estoc: `POST /v2/inventory/counts/batch-retrieve` (estat IN_STOCK) de la ubicació.

Permisos que calen: MERCHANT_PROFILE_READ, ITEMS_READ, ORDERS_READ, INVENTORY_READ.
"""

import re
import urllib.parse
from datetime import datetime

from . import http
from .base import (OPCIONS_COLOR, OPCIONS_TALLA, TALLA_UNICA, Connector, ErrorIntegracio, gtin, noms_opcio,
                   sku_base)
from .shopify import _valida_ubicacions

SQUARE_VERSIO = "2025-10-16"  # capçalera Square-Version fixada; revisar-la cada any
BASES = {"produccio": "https://connect.squareup.com", "sandbox": "https://connect.squareupsandbox.com"}
MAX_PAGINES = 200
PERMISOS = "MERCHANT_PROFILE_READ, ITEMS_READ, ORDERS_READ i INVENTORY_READ"


class ErrorSquare(ErrorIntegracio):
    pass


def _diners(m) -> float | None:
    if not isinstance(m, dict) or m.get("amount") is None:
        return None
    return int(m["amount"]) / 100.0


def _quantitat(q) -> int:
    try:
        return int(round(float(q or 0)))
    except ValueError:
        return 0


class Square(Connector):
    proveidor = "square"

    def __init__(self, config: dict, secret: str | None, botiga_id: str | None = None):
        super().__init__(config, secret, botiga_id)
        self.base = BASES.get(self.config.get("entorn") or "produccio", BASES["produccio"]) + "/v2"
        self._variants: list[dict] | None = None
        self._gtin_variacio: dict[str, str] = {}

    @classmethod
    def valida(cls, config: dict, botiga_id: str | None, abast: list[str]) -> dict:
        c = dict(config or {})
        c["entorn"] = c.get("entorn") or "produccio"
        if c["entorn"] not in BASES:
            raise ErrorSquare("«entorn» ha de ser «produccio» o «sandbox»")
        if c.get("model", "producte") not in ("producte", "sku_base"):
            raise ErrorSquare("«model» ha de ser «producte» o «sku_base»")
        c["opcio_talla"] = noms_opcio(c.get("opcio_talla"), OPCIONS_TALLA)
        c["opcio_color"] = noms_opcio(c.get("opcio_color"), OPCIONS_COLOR)
        c.pop("en_linia", None)
        _valida_ubicacions(c, botiga_id, abast, "Square")
        return c

    # ------------------------------------------------------------ HTTP
    def _crida(self, metode: str, cami: str, cos: dict | None = None, **params) -> dict:
        url = f"{self.base}/{cami}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        h = {"Authorization": f"Bearer {self.secret}", "Square-Version": SQUARE_VERSIO}
        try:
            return http.peticio(metode, url, h, cos).json()
        except http.ErrorXarxa as e:
            raise ErrorSquare(f"No es pot connectar amb Square ({e.motiu}). Revisa la connexió a internet del servidor") from e
        except http.ErrorHttp as e:
            errors = e.json().get("errors") or [{}]
            codi, detall = errors[0].get("code", ""), errors[0].get("detail", "")
            if e.estat == 401:
                raise ErrorSquare("Square no accepta el testimoni d'accés: revisa'l (i que sigui de l'entorn triat, "
                                  "producció o sandbox)") from e
            if e.estat == 403 or codi == "INSUFFICIENT_SCOPES":
                raise ErrorSquare(f"Al testimoni de Square li falten permisos (cal {PERMISOS})"
                                  + (f": {detall}" if detall else "")) from e
            if e.estat == 404:
                raise ErrorSquare(f"Square no troba {cami}" + (f": {detall}" if detall else " (revisa la ubicació)")) from e
            if e.estat == 429:
                raise ErrorSquare("Square ha limitat les peticions (massa en poc temps). Es tornarà a provar a la "
                                  "propera sincronització") from e
            if e.estat >= 500:
                raise ErrorSquare(f"Square no respon bé ara mateix (error {e.estat}). Torna-ho a provar d'aquí a una estona") from e
            raise ErrorSquare(f"Square ha respost {e.estat}" + (f": {detall}" if detall else "")) from e
        except ValueError as e:
            raise ErrorSquare("Square ha tornat una resposta que no s'entén") from e

    def _pagines(self, metode: str, cami: str, clau: str, cos: dict | None = None, **params) -> list[dict]:
        resultat, cursor = [], None
        for _ in range(MAX_PAGINES):
            if metode == "GET":
                d = self._crida("GET", cami, **(dict(params, cursor=cursor) if cursor else params))
            else:
                d = self._crida("POST", cami, dict(cos or {}, **({"cursor": cursor} if cursor else {})))
            resultat.extend(d.get(clau) or [])
            cursor = d.get("cursor")
            if not cursor:
                break
        return resultat

    # ------------------------------------------------------------ prova
    def prova(self) -> dict:
        m = self._crida("GET", "merchants/me").get("merchant") or {}
        ubicacions = self._crida("GET", "locations").get("locations") or []
        return {"botiga": m.get("business_name") or m.get("id"), "comerc": m.get("id"), "moneda": m.get("currency"),
                "ubicacions": [{"id": u["id"], "nom": u.get("name") or u["id"], "activa": u.get("status", "ACTIVE") == "ACTIVE"}
                               for u in ubicacions]}

    # ------------------------------------------------------------ catàleg
    def cataleg(self) -> list[dict]:
        if self._variants is not None:
            return self._variants
        objectes = [o for o in self._pagines("GET", "catalog/list", "objects",
                                             types="ITEM,ITEM_VARIATION,ITEM_OPTION,CATEGORY")
                    if not o.get("is_deleted")]
        items, categories, valors, variacions = {}, {}, {}, {}
        for o in objectes:
            t = o.get("type")
            if t == "ITEM":
                items[o["id"]] = o
                for v in (o.get("item_data") or {}).get("variations") or []:
                    variacions.setdefault(v["id"], v)
            elif t == "ITEM_VARIATION":
                variacions[o["id"]] = o
            elif t == "CATEGORY":
                categories[o["id"]] = (o.get("category_data") or {}).get("name")
            elif t == "ITEM_OPTION":
                d = o.get("item_option_data") or {}
                for val in d.get("values") or []:
                    valors[val["id"]] = (d.get("name") or "", (val.get("item_option_value_data") or {}).get("name") or "")
        noms_talla = [n.casefold() for n in noms_opcio(self.config.get("opcio_talla"), OPCIONS_TALLA)]
        noms_color = [n.casefold() for n in noms_opcio(self.config.get("opcio_color"), OPCIONS_COLOR)]
        per_sku = self.config.get("model") == "sku_base"
        longitud = self.config.get("sku_base_longitud")
        resultat = []
        for vid, v in variacions.items():
            d = v.get("item_variation_data") or {}
            g = gtin(d.get("upc")) or gtin(d.get("sku"))
            if not g:
                continue
            self._gtin_variacio[vid] = g
            talla = color = None
            for ov in d.get("item_option_values") or []:
                nom, valor = valors.get(ov.get("item_option_value_id"), ("", ""))
                if nom.strip().casefold() in noms_talla:
                    talla = valor
                elif nom.strip().casefold() in noms_color:
                    color = valor
            if talla is None and color is None:
                parts = [x.strip() for x in re.split(r"\s*[,/]\s*", d.get("name") or "") if x.strip()]
                if parts and parts[0].casefold() != "regular":
                    talla = parts[0]
                    color = parts[1] if len(parts) > 1 else None
            talla, color = talla or TALLA_UNICA, color or ""
            item = items.get(d.get("item_id")) or {}
            idata = item.get("item_data") or {}
            cat_id = (idata.get("category_id") or (idata.get("reporting_category") or {}).get("id")
                      or next((c.get("id") for c in idata.get("categories") or []), None))
            model = d.get("item_id") or vid
            if per_sku and d.get("sku"):
                model = sku_base(d["sku"], [talla, color], int(longitud) if longitud else None)
            resultat.append({"gtin": g, "model": model, "color": color, "talla": talla,
                             "categoria": categories.get(cat_id) or "altres", "preu_eur": _diners(d.get("price_money")),
                             "id_extern": vid})
        self._variants = resultat
        return resultat

    # ------------------------------------------------------------ vendes
    def vendes(self, des: datetime | None, fins: datetime | None) -> list[dict]:
        self.cataleg()
        linies = []
        filtre_data = {}
        if des:
            filtre_data["start_at"] = des.isoformat(timespec="seconds")
        if fins:
            filtre_data["end_at"] = fins.isoformat(timespec="seconds")
        for i in range(0, len(self.ubicacions), 10):  # màxim 10 ubicacions per consulta
            cos = {"location_ids": self.ubicacions[i:i + 10], "limit": 500,
                   "query": {"filter": {"state_filter": {"states": ["COMPLETED"]},
                                        **({"date_time_filter": {"closed_at": filtre_data}} if filtre_data else {})},
                             "sort": {"sort_field": "CLOSED_AT", "sort_order": "ASC"}}}
            for c in self._pagines("POST", "orders/search", "orders", cos):
                tiquet, ub = f"square:{c['id']}", c.get("location_id")
                ts = c.get("closed_at") or c.get("created_at")
                for li in c.get("line_items") or []:
                    g = self._gtin_variacio.get(li.get("catalog_object_id"))
                    q = _quantitat(li.get("quantity"))
                    if g and q > 0:
                        imp = _diners(li.get("gross_sales_money"))
                        if imp is None:
                            imp = (_diners(li.get("base_price_money")) or 0) * q
                        linies.append({"tiquet": tiquet, "ubicacio": ub, "ts": ts, "gtin": g, "quantitat": q,
                                       "import_eur": imp, "devolucio": 0})
                for ret in c.get("returns") or []:
                    for rli in ret.get("return_line_items") or []:
                        g = self._gtin_variacio.get(rli.get("catalog_object_id"))
                        q = _quantitat(rli.get("quantity"))
                        if g and q > 0:
                            imp = _diners(rli.get("gross_return_money"))
                            if imp is None:
                                imp = (_diners(rli.get("base_price_money")) or 0) * q
                            linies.append({"tiquet": tiquet, "ubicacio": ub, "ts": ts, "gtin": g, "quantitat": -q,
                                           "import_eur": -abs(imp), "devolucio": 1})
        return linies

    # ------------------------------------------------------------ estoc
    def estoc(self) -> list[dict]:
        self.cataleg()
        if not self.ubicacions:
            return []
        nivells = []
        for n in self._pagines("POST", "inventory/counts/batch-retrieve", "counts",
                               {"location_ids": self.ubicacions, "states": ["IN_STOCK"]}):
            g = self._gtin_variacio.get(n.get("catalog_object_id"))
            if g and n.get("state", "IN_STOCK") == "IN_STOCK":
                nivells.append({"ubicacio": n.get("location_id"), "gtin": g, "unitats": _quantitat(n.get("quantity"))})
        return nivells
