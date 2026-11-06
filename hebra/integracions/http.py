"""Peticions HTTP dels connectors (només llibreria estàndard: urllib).

Tots els connectors passen per `peticio`. Les proves substitueixen `_obre` (vegeu
tests/test_v3_integracions.py) i així no cal xarxa.

  * temps d'espera fix per petició (`TEMPS_ESPERA_S`);
  * 429 (massa peticions) i 503: espera el que diu `Retry-After` (màxim 30 s) i ho torna a provar
    fins a `INTENTS` vegades, per no carregar el servei de l'altra banda;
  * qualsevol altre estat >= 400 -> `ErrorHttp` amb l'estat i el cos (perquè el connector
    en tregui un missatge clar);
  * error de xarxa o de DNS -> `ErrorXarxa`.
"""

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

TEMPS_ESPERA_S = 20
INTENTS = 4
ESPERA_MAXIMA_S = 30
AGENT = "Hebra/0.3 (+https://hebra.cat)"


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


def _obre(req: urllib.request.Request, temps_espera: float) -> Resposta:
    """Fa la petició i torna la resposta, també si l'estat és d'error (no llança HTTPError)."""
    try:
        with urllib.request.urlopen(req, timeout=temps_espera) as r:
            return Resposta(r.status, {k.lower(): v for k, v in r.headers.items()}, r.read())
    except urllib.error.HTTPError as e:
        cos = e.read() if e.fp else b""
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
