"""Compatibilitat (v0.2): el connector de Shopify ara és a `hebra/integracions/shopify.py`.

Continua funcionant la configuració antiga per botiga:
  * paràmetre `shopify_domini`   p. ex. `marca.myshopify.com` (taula `parametre`);
  * paràmetre `shopify_ubicacio` id numèric de la ubicació (location) de la botiga;
  * variable d'entorn `HEBRA_SHOPIFY_TOKEN_<BOTIGA>` (BCN-01 -> HEBRA_SHOPIFY_TOKEN_BCN_01).

`python -m hebra.admin shopify --botiga BCN-01` i `POST /api/v2/shopify/sincronitza` la fan servir.
La manera nova és una integració desada des del tauler (Connexions i dades), amb el testimoni xifrat.
"""

from .integracions.shopify import (API_VERSIO, Client, ErrorShopify, Shopify, _gtin, _pagina_seguent,
                                   nom_variable_token, sincronitza)

__all__ = ["API_VERSIO", "Client", "ErrorShopify", "Shopify", "_gtin", "_pagina_seguent", "nom_variable_token",
           "sincronitza"]
