"""Interfície comuna dels connectors i funcions d'ajuda.

Cada connector rep `config` (dict, sense secrets), `secret` (testimoni o capçalera, ja desxifrat)
i `botiga_id` (None = tota la marca) i implementa:

  * `prova() -> dict`             comprova la connexió; torna {"botiga": nom, "ubicacions": [{"id","nom"}], ...}
  * `cataleg() -> [Variant]`      {"gtin","model","color","talla","categoria","preu_eur","id_extern"}
  * `vendes(des, fins) -> [Linia]` {"tiquet","ubicacio","ts","gtin","quantitat","import_eur","devolucio"}
                                  (devolucions amb quantitat i import negatius i devolucio = 1)
  * `estoc() -> [Nivell]`         {"ubicacio","gtin","unitats"}

`aplica` les desa amb les funcions de `desa.py`, que fan servir les taules de sempre
(`catalog_sku`, `venda_linia`, `estoc`): la resta de la plataforma no canvia.

Ubicacions: una integració d'una botiga fa servir `config.ubicacio` (id de la ubicació del
proveïdor); una de tota la marca (botiga_id NULL) pot fer servir `config.ubicacions`
= {"<id d'ubicació>": "<botiga>"} per repartir vendes i estoc entre botigues.
"""

import re
import sqlite3
from datetime import datetime

from . import desa

ABAST = ("cataleg", "vendes", "estoc")
OPCIONS_TALLA = ["Talla", "Size", "Taille", "Tamaño", "Talle"]
OPCIONS_COLOR = ["Color", "Colour", "Couleur", "Colore"]
TALLA_UNICA = "Única"


class ErrorIntegracio(Exception):
    """Error amb un missatge en català que es pot ensenyar tal qual a la persona."""


def gtin(codi) -> str | None:
    """Codi de barres -> GTIN-14 (només xifres, fins a 14); si no ho és, None."""
    codi = str(codi or "").strip()
    return codi.zfill(14) if codi.isdigit() and len(codi) <= 14 else None


def noms_opcio(valor, defecte: list[str]) -> list[str]:
    """Noms d'opció configurables: llista o text separat per comes."""
    if not valor:
        return defecte
    if isinstance(valor, str):
        valor = valor.split(",")
    return [str(v).strip() for v in valor if str(v).strip()]


def sku_base(sku: str, valors: list[str], longitud: int | None = None) -> str:
    """SKU del model: treu del final els trossos que són la talla o el color (CAM01-M-BLAU -> CAM01)."""
    sku = (sku or "").strip()
    if longitud:
        return sku[:longitud] or sku
    base = sku
    canvia = True
    while canvia:
        canvia = False
        for v in valors:
            if not v:
                continue
            m = re.search(r"[-_/. ]+" + re.escape(v) + r"$", base, re.IGNORECASE)
            if m and m.start() > 0:
                base, canvia = base[:m.start()], True
    return base or sku


def mapa_ubicacions(config: dict, botiga_id: str | None) -> dict:
    """{id d'ubicació (text) o None (en línia): botiga}."""
    mapa: dict = {}
    if botiga_id:
        if config.get("ubicacio") not in (None, ""):
            mapa[str(config["ubicacio"])] = botiga_id
        if config.get("en_linia"):
            mapa[None] = botiga_id
    for ub, b in (config.get("ubicacions") or {}).items():
        mapa[str(ub)] = b
    return mapa


class Connector:
    proveidor = ""
    enllaca_variants = False  # Shopify: desa sempre l'id de variant a catalog_sku encara que no s'importi el catàleg

    def __init__(self, config: dict, secret: str | None, botiga_id: str | None = None):
        self.config = config or {}
        self.secret = secret or ""
        self.botiga_id = botiga_id
        self.mapa = mapa_ubicacions(self.config, botiga_id)

    @property
    def ubicacions(self) -> list[str]:
        return [u for u in self.mapa if u is not None]

    @classmethod
    def valida(cls, config: dict, botiga_id: str | None, abast: list[str]) -> dict:
        """Comprova i normalitza la configuració abans de desar-la (ErrorIntegracio si no és bona)."""
        return dict(config or {})

    def prova(self) -> dict:
        raise NotImplementedError

    def cataleg(self) -> list[dict]:
        raise NotImplementedError

    def vendes(self, des: datetime, fins: datetime) -> list[dict]:
        raise NotImplementedError

    def estoc(self) -> list[dict]:
        raise NotImplementedError

    def aplica(self, con: sqlite3.Connection, abast: list[str], des: datetime, fins: datetime) -> dict:
        """Sincronitza el que diu `abast`. Torna el resum (vegeu ESPECIFICACIO-v3 F.3)."""
        r = {"cataleg": 0, "linies_venda": 0, "devolucions": 0, "estoc": 0, "comandes": 0}
        if "cataleg" in abast or self.enllaca_variants:
            r["cataleg"] = desa.cataleg(con, self.cataleg(), crea="cataleg" in abast,
                                        camp_extern="variant_shopify" if self.proveidor == "shopify" else None)
        if "vendes" in abast:
            v = desa.vendes(con, self.vendes(des, fins), self.mapa)
            r.update(linies_venda=v["linies"], devolucions=v["devolucions"], comandes=v["tiquets"])
            r["_botigues"] = v["botigues"]
        if "estoc" in abast:
            r["estoc"] = desa.estoc(con, self.estoc(), self.mapa, font=self.proveidor)
        return r
