"""Peticions HTTP dels connectors (només llibreria estàndard: urllib).

Tots els connectors passen per `peticio`. Les proves substitueixen `_obre` (vegeu
tests/test_v3_integracions.py) i així no cal xarxa.

  * temps d'espera fix per petició (`TEMPS_ESPERA_S`);
  * 429 (massa peticions) i 503: espera el que diu `Retry-After` (màxim 30 s) i ho torna a provar
    fins a `INTENTS` vegades, per no carregar el servei de l'altra banda;
  * qualsevol altre estat >= 400 -> `ErrorHttp` amb l'estat i el cos (perquè el connector
    en tregui un missatge clar);
  * error de xarxa o de DNS -> `ErrorXarxa`;
  * només https, i només cap a adreces públiques (`comprova_desti`): una URL configurada des del
    panell no pot fer servir el servidor per arribar a la seva xarxa interna ni al mateix servidor,
    tampoc a través d'una redirecció;
  * la resposta es llegeix fins a `MIDA_MAXIMA_RESPOSTA`; si és més gran, `ErrorXarxa`.

Límit conegut: el nom es resol dues vegades (en comprovar i en connectar). Un DNS que canviï
entre les dues resolucions podria saltar-se la comprovació; per al pilot és acceptable.
"""

import ipaddress
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

TEMPS_ESPERA_S = 20
INTENTS = 4
ESPERA_MAXIMA_S = 30
AGENT = "Hebra/0.4"
MIDA_MAXIMA_RESPOSTA = 25 * 1024 * 1024
MAX_REDIRECCIONS = 3


class ErrorHttp(Exception):
    def __init__(self, estat: int, cos: str, url: str):
        super().__init__(f"HTTP {estat} a {urllib.parse.urlsplit(url).path}")
        self.estat, self.cos, self.url = estat, cos, url

    def json(self) -> dict:
        try:
            d = json.loads(self.cos)
            return d if isinstance(d, dict) else {}
        except ValueError:
            return {}


class ErrorXarxa(Exception):
    def __init__(self, motiu: str, dns: bool = False):
        super().__init__(motiu)
        self.motiu, self.dns = motiu, dns


@dataclass
class Resposta:
    estat: int
    capcaleres: dict = field(default_factory=dict)  # noms en minúscules
    cos: bytes = b""

    def json(self):
        return json.loads(self.cos.decode("utf-8")) if self.cos else {}

    def text(self) -> str:
        return self.cos.decode("utf-8-sig")


def _resol(host: str) -> list[str]:  # les proves la substitueixen
    return [i[4][0] for i in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)]


def comprova_desti(url: str) -> None:
    """Llança `ErrorXarxa` si la URL no és https o apunta a una adreça que no és pública."""
    parts = urllib.parse.urlsplit(url)
    if os.environ.get("HEBRA_PERMET_XARXA_INTERNA") == "1":  # només per a proves en local
        return
    if parts.scheme != "https" or not parts.hostname:
        raise ErrorXarxa("només s'admeten adreces https://")
    try:
        adreces = _resol(parts.hostname)
    except socket.gaierror as e:
        raise ErrorXarxa(str(e), dns=True) from e
    for a in adreces:
        ip = ipaddress.ip_address(a.split("%")[0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            raise ErrorXarxa("l'adreça apunta a una xarxa interna i no es pot fer servir")


class _Redireccions(urllib.request.HTTPRedirectHandler):
    """Segueix redireccions només cap a https i adreces públiques, i poques."""
    max_redirections = MAX_REDIRECCIONS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        comprova_desti(newurl)
        nova = super().redirect_request(req, fp, code, msg, headers, newurl)
        if nova is not None and urllib.parse.urlsplit(newurl).hostname != urllib.parse.urlsplit(req.full_url).hostname:
            # Les credencials no viatgen a un altre domini.
            for c in list(nova.headers):
                if c.lower() in ("authorization", "cookie") or c.lower().startswith("x-"):
                    del nova.headers[c]
        return nova


_obridor = urllib.request.build_opener(_Redireccions)


def _obre(req: urllib.request.Request, temps_espera: float) -> Resposta:
    """Fa la petició i torna la resposta, també si l'estat és d'error (no llança HTTPError)."""
    comprova_desti(req.full_url)
    try:
        with _obridor.open(req, timeout=temps_espera) as r:
            cos = r.read(MIDA_MAXIMA_RESPOSTA + 1)
            if len(cos) > MIDA_MAXIMA_RESPOSTA:
                raise ErrorXarxa("la resposta és massa gran")
            return Resposta(r.status, {k.lower(): v for k, v in r.headers.items()}, cos)
    except urllib.error.HTTPError as e:
        cos = e.read(1024 * 1024) if e.fp else b""
        return Resposta(e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, cos)
    except urllib.error.URLError as e:
        dns = isinstance(e.reason, socket.gaierror)
        raise ErrorXarxa(str(e.reason), dns=dns) from e
    except (TimeoutError, socket.timeout) as e:
        raise ErrorXarxa("temps d'espera esgotat") from e
    except OSError as e:
        raise ErrorXarxa(str(e)) from e


def _dorm(segons: float) -> None:  # les proves la substitueixen
    time.sleep(segons)


def _espera(capcaleres: dict, intent: int) -> float:
    valor = capcaleres.get("retry-after", "")
    try:
        s = float(valor)
    except ValueError:
        s = 2.0 ** intent
    return max(0.5, min(s, ESPERA_MAXIMA_S))


def peticio(metode: str, url: str, capcaleres: dict | None = None, cos: dict | bytes | None = None,
            temps_espera: float = TEMPS_ESPERA_S) -> Resposta:
    """Petició HTTP amb reintents educats. Torna la `Resposta` (estat < 400) o llança l'error."""
    h = {"User-Agent": AGENT, "Accept": "application/json"}
    h.update(capcaleres or {})
    dades = None
    if isinstance(cos, dict):
        dades = json.dumps(cos).encode("utf-8")
        h["Content-Type"] = "application/json"
    elif cos is not None:
        dades = cos
    for intent in range(INTENTS):
        req = urllib.request.Request(url, data=dades, headers=h, method=metode)
        r = _obre(req, temps_espera)
        if r.estat in (429, 503) and intent < INTENTS - 1:
            _dorm(_espera(r.capcaleres, intent))
            continue
        if r.estat >= 400:
            raise ErrorHttp(r.estat, r.cos.decode("utf-8", "replace")[:2000], url)
        return r
    raise AssertionError("inabastable")
