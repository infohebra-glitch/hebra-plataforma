"""Connector «CSV per URL»: per a TPV que exporten un fitxer (Ágora, Revo, Lightspeed...).

Configuració: `url_vendes`, `url_estoc`, `url_cataleg` (HTTPS, cada una opcional) i, si el
servidor ho demana, una capçalera d'autorització: el valor és el secret de la integració
(p. ex. «Bearer abc...» o «Basic ...») i el nom, `config.capcalera` (per defecte Authorization).

Descarrega cada fitxer i l'importa amb els importadors de sempre (formats a docs/API.md i
hebra/vendes.py, hebra/estoc.py, hebra/admin.py). Si la integració és d'una botiga i el fitxer
no porta la columna `botiga`, s'hi afegeix; si la porta, només s'importen les files d'aquesta botiga.
Com que el TPV sol tornar a exportar els mateixos dies, les línies de venda que ja hi són
(mateixa botiga, hora, GTIN, quantitat, import i tiquet) no es tornen a importar.
"""

import csv
import io
import sqlite3
import urllib.parse
from collections import Counter
from datetime import datetime

from .. import estoc as estoc_mod
from .. import temps, vendes as vendes_mod
from . import http
from .base import Connector, ErrorIntegracio

TIPUS = {"vendes": "url_vendes", "estoc": "url_estoc", "cataleg": "url_cataleg"}
NOM = {"vendes": "vendes", "estoc": "estoc", "cataleg": "catàleg"}
MIDA_MAXIMA = 20 * 1024 * 1024
COLUMNES = {"vendes": {"data_hora", "botiga", "gtin", "quantitat"}, "estoc": {"botiga", "gtin", "unitats"},
            "cataleg": {"gtin", "model", "color", "talla"}}


def _separador(text: str) -> str:
    mostra = text[:2048]
    return ";" if mostra.count(";") > mostra.count(",") else ","


def _columnes(text: str, alies: dict) -> list[str]:
    files = list(csv.reader(io.StringIO(text[:8192]), delimiter=_separador(text)))
    return [alies.get(c.strip().lower(), c.strip().lower()) for c in files[0]] if files else []


def amb_botiga(text: str, botiga_id: str | None) -> str:
    """Afegeix la columna `botiga` si falta, o deixa només les files de la botiga."""
    if not botiga_id:
        return text
    sep = _separador(text)
    files = list(csv.reader(io.StringIO(text), delimiter=sep))
    if not files:
        return text
    cap = [c.strip().lower() for c in files[0]]
    idx = next((i for i, c in enumerate(cap) if c in ("botiga", "botiga_id")), None)
    if idx is None:
        files = [files[0] + ["botiga"]] + [f + [botiga_id] for f in files[1:] if any(x.strip() for x in f)]
    else:
        files = [files[0]] + [f for f in files[1:] if len(f) > idx and f[idx].strip() == botiga_id]
    sortida = io.StringIO()
    csv.writer(sortida, delimiter=sep, lineterminator="\n").writerows(files)
    return sortida.getvalue()


def _clau_venda(f: dict) -> tuple | None:
    try:
        moment = f["data_hora"].strip()
        if len(moment) == 10:
            ts, data = None, datetime.fromisoformat(moment).date().isoformat()
        else:
            ts = temps.local(moment)
            data = ts[:10]
        imp = (f.get("import") or "").strip().replace(",", ".")
        return (f["botiga"].strip(), ts, data, f["gtin"].strip().zfill(14), int(f["quantitat"]),
                round(float(imp), 2) if imp else None, vendes_mod._hash_tiquet((f.get("tiquet") or "").strip()))
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


def sense_repetides(con: sqlite3.Connection, text: str) -> tuple[str, int]:
    """Treu les línies de venda que ja són a la base de dades. Torna (text, quantes s'han tret)."""
    sep = _separador(text)
    lector = csv.DictReader(io.StringIO(text), delimiter=sep)
    if lector.fieldnames is None:
        return text, 0
    originals = list(lector.fieldnames)
    lector.fieldnames = [vendes_mod.ALIES.get(c.strip().lower(), c.strip().lower()) for c in originals]
    files = list(lector)
    claus = [_clau_venda(f) for f in files]
    dies = {(k[0], k[2]) for k in claus if k}
    existents: Counter = Counter()
    for botiga, dia in dies:
        for r in con.execute("""SELECT botiga_id, ts, data, gtin, quantitat, import_eur, tiquet_hash FROM venda_linia
                                WHERE botiga_id = ? AND data = ?""", (botiga, dia)):
            existents[(r[0], r[1], r[2], r[3], r[4], None if r[5] is None else round(r[5], 2), r[6])] += 1
    sortida = io.StringIO()
    w = csv.writer(sortida, delimiter=sep, lineterminator="\n")
    w.writerow(originals)
    trets = 0
    for f, k in zip(files, claus):
        if k and existents[k] > 0:
            existents[k] -= 1
            trets += 1
            continue
        w.writerow([f.get(c, "") for c in lector.fieldnames])
    return sortida.getvalue(), trets


class CsvUrl(Connector):
    proveidor = "csv_url"

    @classmethod
    def valida(cls, config: dict, botiga_id: str | None, abast: list[str]) -> dict:
        c = {k: v for k, v in (config or {}).items() if v not in (None, "")}
        if not any(c.get(k) for k in TIPUS.values()):
            raise ErrorIntegracio("Cal com a mínim una URL (vendes, estoc o catàleg)")
        for tipus, clau in TIPUS.items():
            if c.get(clau):
                parts = urllib.parse.urlsplit(str(c[clau]).strip())
                if parts.scheme != "https" or not parts.hostname:
                    raise ErrorIntegracio(f"La URL de {NOM[tipus]} ha de començar per https://")
                c[clau] = str(c[clau]).strip()
            elif tipus in abast:
                raise ErrorIntegracio(f"Per sincronitzar {NOM[tipus]} cal la URL del fitxer")
        if c.get("capcalera") and not str(c["capcalera"]).replace("-", "").isalnum():
            raise ErrorIntegracio("El nom de la capçalera no és vàlid")
        return c

    def _descarrega(self, tipus: str) -> str:
        url = self.config[TIPUS[tipus]]
        h = {"Accept": "text/csv, text/plain, */*"}
        if self.secret:
            h[self.config.get("capcalera") or "Authorization"] = self.secret
        try:
            r = http.peticio("GET", url, h, temps_espera=60)
        except http.ErrorXarxa as e:
            host = urllib.parse.urlsplit(url).hostname
            if e.dns:
                raise ErrorIntegracio(f"No es troba el domini {host} (URL de {NOM[tipus]})") from e
            raise ErrorIntegracio(f"No es pot descarregar el fitxer de {NOM[tipus]} ({e.motiu})") from e
        except http.ErrorHttp as e:
            if e.estat in (401, 403):
                raise ErrorIntegracio(f"El servidor del fitxer de {NOM[tipus]} no accepta l'autorització "
                                      f"(error {e.estat}): revisa la capçalera") from e
            if e.estat == 404:
                raise ErrorIntegracio(f"No es troba el fitxer de {NOM[tipus]} (error 404): revisa la URL") from e
            raise ErrorIntegracio(f"El servidor del fitxer de {NOM[tipus]} ha respost {e.estat}") from e
        if len(r.cos) > MIDA_MAXIMA:
            raise ErrorIntegracio(f"El fitxer de {NOM[tipus]} és massa gran (màxim 20 MB)")
        try:
            return r.cos.decode("utf-8-sig")
        except UnicodeDecodeError:
            return r.cos.decode("cp1252", "replace")  # molts TPV exporten en Windows-1252

    def _comprova(self, tipus: str, text: str) -> dict:
        alies = {"vendes": vendes_mod.ALIES, "estoc": estoc_mod.ALIES}.get(tipus, {})
        cols = _columnes(text, alies)
        if not cols:
            raise ErrorIntegracio(f"El fitxer de {NOM[tipus]} és buit")
        cal = COLUMNES[tipus] - ({"botiga"} if self.botiga_id else set())
        falten = cal - set(cols) - ({"botiga"} if "botiga_id" in cols else set())
        if falten:
            raise ErrorIntegracio(f"Al fitxer de {NOM[tipus]} li falten columnes: {', '.join(sorted(falten))}")
        return {"files": max(0, len([x for x in text.splitlines() if x.strip()]) - 1), "columnes": cols}

    def prova(self) -> dict:
        fitxers = {}
        for tipus, clau in TIPUS.items():
            if self.config.get(clau):
                fitxers[tipus] = self._comprova(tipus, self._descarrega(tipus))
        return {"botiga": None, "ubicacions": [], "fitxers": fitxers}

    def aplica(self, con: sqlite3.Connection, abast: list[str], des, fins) -> dict:
        from .. import admin  # aquí: admin importa hebra.shopify, que importa aquest paquet

        r = {"cataleg": 0, "linies_venda": 0, "devolucions": 0, "estoc": 0, "errors": [], "_botigues": []}
        if "cataleg" in abast:
            n, errors = admin.importa_cataleg(con, self._descarrega("cataleg"))
            r["cataleg"] = n
            r["errors"] += [f"Catàleg: {e}" for e in errors]
        if "vendes" in abast:
            text = amb_botiga(self._descarrega("vendes"), self.botiga_id)
            self._comprova("vendes", text)
            text, _ = sense_repetides(con, text)
            abans = con.execute("SELECT COALESCE(MAX(id), 0) FROM venda_linia").fetchone()[0]
            _, errors = vendes_mod.importa_csv(con, text)
            for f in con.execute("""SELECT botiga_id, SUM(devolucio = 0), SUM(devolucio = 1) FROM venda_linia
                                    WHERE id > ? GROUP BY botiga_id""", (abans,)):
                r["linies_venda"] += f[1] or 0
                r["devolucions"] += f[2] or 0
                r["_botigues"].append(f[0])
            r["errors"] += [f"Vendes: {e}" for e in errors]
        if "estoc" in abast:
            text = amb_botiga(self._descarrega("estoc"), self.botiga_id)
            n, errors = estoc_mod.importa_csv(con, text)
            r["estoc"] = n
            r["errors"] += [f"Estoc: {e}" for e in errors]
        r["errors"] = r["errors"][:50]
        return r
