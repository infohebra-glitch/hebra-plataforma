"""Integracions amb sistemes de la marca: Shopify, Square i CSV per URL (ESPECIFICACIO-v3, F).

  base.py      interfície comuna (`Connector`) i funcions d'ajuda
  http.py      peticions HTTP amb urllib (temps d'espera, reintents amb Retry-After)
  xifratge.py  secrets xifrats amb Fernet (clau derivada de HEBRA_SECRET per HKDF)
  desa.py      desa catàleg, vendes i estoc a les taules de sempre
  shopify.py   connector de Shopify (i la sincronització antiga per variables d'entorn)
  square.py    connector de Square
  csv_url.py   connector de fitxers CSV per URL (TPV que exporten un fitxer)
  motor.py     taula `integracio`, registre, intervals i sincronització
"""

from .base import ABAST, Connector, ErrorIntegracio
from .csv_url import CsvUrl
from .shopify import Shopify
from .square import Square

PROVEIDORS: dict[str, type[Connector]] = {"shopify": Shopify, "square": Square, "csv_url": CsvUrl}


def connector(proveidor: str, config: dict, secret: str | None, botiga_id: str | None = None) -> Connector:
    if proveidor not in PROVEIDORS:
        raise ErrorIntegracio(f"Proveïdor desconegut: {proveidor!r} (shopify, square o csv_url)")
    return PROVEIDORS[proveidor](config, secret, botiga_id)


__all__ = ["ABAST", "PROVEIDORS", "Connector", "ErrorIntegracio", "connector"]
