"""PDF dels informes (docs/ESPECIFICACIO-v3.md, E.3): plantilla HTML + WeasyPrint.

La plantilla és `hebra/templates/informe_pdf.html` (A4; capçalera amb la marca i el
període; peu «Dades de Hebra · pàgina X de Y»). Els gràfics són SVG fets al servidor
(hebra/grafics_svg.py), sense JavaScript. WeasyPrint necessita Pango al sistema
(vegeu docs/INSTAL-LACIO.md); s'importa només quan cal, perquè la resta de la
plataforma funcioni encara que no hi sigui.
"""

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import db, grafics_svg

PLANTILLES = Path(__file__).with_name("templates")


def _data(text: str | None) -> str:
    if not text:
        return "—"
    d = date.fromisoformat(text[:10])
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


_entorn = Environment(loader=FileSystemLoader(PLANTILLES), autoescape=select_autoescape(["html"]))
_entorn.filters["valor"] = lambda v, unitat="enter": grafics_svg.format_valor(v, unitat)
_entorn.filters["variacio"] = lambda v, unitat="enter": grafics_svg.format_variacio(v, unitat)
_entorn.filters["data"] = _data


def nom_marca(con: sqlite3.Connection, botiga_id: str | None) -> str:
    """Paràmetre `nom_marca`; si no, el de la configuració de la fitxa (v0.3, A.1); si no, «Hebra»."""
    nom = db.parametre(con, botiga_id, "nom_marca")
    if nom:
        return nom
    try:
        fila = con.execute("SELECT config_json FROM config_fitxa WHERE botiga_id = '*'").fetchone()
    except sqlite3.OperationalError:   # la taula encara no existeix
        fila = None
    if fila:
        try:
            nom = (json.loads(fila[0]).get("aparença") or {}).get("nom_marca")
        except (ValueError, AttributeError):
            nom = None
    return nom or "Hebra"


def html(con: sqlite3.Connection, inf: dict, botiga_id: str | None, generat: str | None = None) -> str:
    """HTML de l'informe tal com el pinta el PDF."""
    botiga = None
    if botiga_id:
        fila = con.execute("SELECT nom FROM botiga WHERE id = ?", (botiga_id,)).fetchone()
        botiga = fila["nom"] if fila else botiga_id
    p = inf.get("periode") or {}
    periode_txt = _data(p.get("des")) if p.get("des") == p.get("fins") else f"{_data(p.get('des'))} – {_data(p.get('fins'))}"
    generat_dt = datetime.fromisoformat(generat) if generat else datetime.now()
    grafics = [dict(g, svg=Markup(grafics_svg.svg(g))) for g in inf.get("grafics") or []]
    return _entorn.get_template("informe_pdf.html").render(
        inf=inf, grafics=grafics, marca=nom_marca(con, botiga_id), botiga=botiga, periode_txt=periode_txt,
        generat_txt=f"{_data(generat_dt.date().isoformat())} a les {generat_dt:%H:%M}")


def pdf(con: sqlite3.Connection, inf: dict, botiga_id: str | None, generat: str | None = None) -> bytes:
    """PDF (bytes) de l'informe."""
    from weasyprint import HTML  # import tardà: carrega Pango i triga una mica
    return HTML(string=html(con, inf, botiga_id, generat), base_url=str(PLANTILLES)).write_pdf()


def nom_fitxer(inf: dict, botiga_id: str | None) -> str:
    p = inf.get("periode") or {}
    return f"hebra-{inf.get('tipus', 'informe')}-{botiga_id or 'totes'}-{p.get('fins', '')}.pdf"
