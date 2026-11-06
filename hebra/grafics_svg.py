"""Gràfics SVG fets al servidor per al PDF dels informes (sense JavaScript).

Dibuixa la forma `grafics` de l'informe (docs/ESPECIFICACIO-v3.md, E.2):

    {"id", "titol", "tipus": "linia" | "barres" | "barres_apilades" | "donut",
     "unitat": "pct" | "enter" | "eur" | "segons", "eix_x": [...],
     "series": [{"nom", "valors": [...]}], "nota"}

Criteris de disseny (llegible en A4 i en blanc i negre):
  * colors neutres (no de marca), en ordre fix per sèrie; el text sempre en gris fosc,
    mai del color de la sèrie;
  * línies de 2 px amb punts, barres primes amb 2 px de separació, quadrícula suau;
  * llegenda sempre que hi ha 2 sèries o més; valors escrits a les barres i al final
    de cada línia (en paper no hi ha «hover»);
  * números en format català: 1.234,5 · 34 % · 1.234 € · 92 s.
Un valor `None` és «sense dada»: no es dibuixa.
"""

import math
from html import escape

COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
TEXT = "#1f1f1e"
TEXT_SECUNDARI = "#52514e"
QUADRICULA = "#e4e3df"
EIX = "#b9b8b2"
FONS = "#ffffff"
FONT = "font-family=\"'DejaVu Sans', 'Liberation Sans', Arial, sans-serif\""


# ---------------------------------------------------------------- Nombres en català


def _milers(n: float, decimals: int) -> str:
    text = f"{abs(n):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return ("−" if n < 0 else "") + text


def format_valor(valor, unitat: str = "enter", compacte: bool = False) -> str:
    """Format català d'un valor segons la unitat. `None` → «—»."""
    if valor is None:
        return "—"
    if unitat == "pct":
        x = valor * 100
        return f"{_milers(x, 0 if compacte or abs(x) >= 10 or float(x).is_integer() else 1)} %"
    if unitat == "eur":
        return f"{_milers(valor, 0 if compacte or abs(valor) >= 100 or float(valor).is_integer() else 2)} €"
    if unitat == "segons":
        if abs(valor) >= 120:
            return f"{_milers(valor / 60, 0 if compacte else 1)} min"
        return f"{_milers(valor, 0)} s"
    return _milers(valor, 0 if float(valor).is_integer() or compacte else 1)


def format_variacio(variacio: float | None, unitat: str) -> str:
    """Variació d'una xifra: relativa (+4 %) o, si la xifra és un percentatge, en punts (+3,1 punts)."""
    if variacio is None:
        return ""
    if unitat == "pct":
        return f"{'+' if variacio >= 0 else '−'}{_milers(abs(variacio) * 100, 1)} punts"
    return f"{'+' if variacio >= 0 else '−'}{_milers(abs(variacio) * 100, 0)} %"


# ---------------------------------------------------------------- Peces comunes


def _escala(maxim: float, unitat: str) -> tuple[float, list[float]]:
    """Màxim «rodó» de l'eix i les marques (de 0 al màxim, 4 intervals)."""
    if maxim <= 0:
        maxim = 1 if unitat != "pct" else 0.1
    brut = maxim / 4
    ordre = 10 ** math.floor(math.log10(brut))
    pas = next(m * ordre for m in (1, 2, 2.5, 5, 10) if m * ordre >= brut)
    if unitat == "enter":
        pas = max(1, math.ceil(pas))
    sostre = pas * math.ceil(maxim / pas - 1e-9)
    n = round(sostre / pas)
    return sostre, [round(pas * i, 10) for i in range(n + 1)]


def _text(x: float, y: float, contingut: str, mida: int = 10, color: str = TEXT_SECUNDARI,
          ancora: str = "start", pes: str = "normal") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{mida}" fill="{color}" text-anchor="{ancora}" '
            f'font-weight="{pes}">{escape(str(contingut))}</text>')


def _retalla(text: str, maxim: int) -> str:
    text = str(text)
    return text if len(text) <= maxim else text[: maxim - 1] + "…"


def _llegenda(series: list[dict], x: float, y: float, amplada: float) -> tuple[str, float]:
    """Llegenda en una o més files. Retorna (svg, alçada ocupada)."""
    if len(series) < 2:
        return "", 0
    parts, cx, cy = [], x, y
    for i, s in enumerate(series):
        nom = _retalla(s["nom"], 28)
        w = 18 + len(nom) * 6.2 + 14
        if cx + w > x + amplada and cx > x:
            cx, cy = x, cy + 16
        parts.append(f'<rect x="{cx:.1f}" y="{cy - 8:.1f}" width="10" height="10" rx="2" fill="{COLORS[i % 8]}"/>')
        parts.append(_text(cx + 15, cy + 1, nom, 10, TEXT))
        cx += w
    return "".join(parts), cy - y + 18


def _embolcall(amplada: int, alcada: int, cos: str, titol: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {amplada} {alcada}" width="{amplada}" '
            f'height="{alcada}" role="img" aria-label="{escape(titol)}" {FONT}>'
            f'<rect width="{amplada}" height="{alcada}" fill="{FONS}"/>{cos}</svg>')


def _sense_dades(amplada: int, alcada: int, titol: str) -> str:
    return _embolcall(amplada, alcada, _text(amplada / 2, alcada / 2, "Sense dades al període", 11,
                                             TEXT_SECUNDARI, "middle"), titol)


def _valors(g: dict) -> list[float]:
    return [v for s in g.get("series", []) for v in s.get("valors", []) if v is not None]


def _eix_y(x0: float, y0: float, y1: float, amplada: float, marques: list[float], sostre: float,
           unitat: str) -> str:
    out = []
    for m in marques:
        y = y1 - (m / sostre) * (y1 - y0)
        out.append(f'<line x1="{x0:.1f}" x2="{x0 + amplada:.1f}" y1="{y:.1f}" y2="{y:.1f}" '
                   f'stroke="{QUADRICULA if m else EIX}" stroke-width="1"/>')
        out.append(_text(x0 - 6, y + 3.5, format_valor(m, unitat, compacte=True), 9, TEXT_SECUNDARI, "end"))
    return "".join(out)


def _etiquetes_x(eix: list, xs: list[float], y: float, espai: float) -> str:
    """Etiquetes de l'eix X; si no hi caben, se'n salten (sempre la primera i l'última)."""
    maxim = max(4, int(espai / 6.2))
    pas = 1
    while pas < len(eix) and espai * pas < min(len(str(e)) for e in eix) * 5.5:
        pas += 1
    out = []
    for i, (e, x) in enumerate(zip(eix, xs)):
        if i % pas and i != len(eix) - 1:
            continue
        out.append(_text(x, y, _retalla(e, maxim * pas), 9, TEXT_SECUNDARI, "middle"))
    return "".join(out)


# ---------------------------------------------------------------- Tipus de gràfic


def linia(g: dict, amplada: int = 640, alcada: int = 230) -> str:
    valors = _valors(g)
    if not valors or not g.get("eix_x"):
        return _sense_dades(amplada, alcada, g.get("titol", ""))
    unitat = g.get("unitat", "enter")
    llegenda, h_ll = _llegenda(g["series"], 52, 14, amplada - 60)
    x0, y0, x1, y1 = 52, 14 + h_ll, amplada - 56, alcada - 26
    sostre, marques = _escala(max(valors), unitat)
    n = len(g["eix_x"])
    xs = [x0 + (x1 - x0) * (i / (n - 1) if n > 1 else 0.5) for i in range(n)]
    cos = [llegenda, _eix_y(x0, y0, y1, x1 - x0, marques, sostre, unitat)]
    for si, s in enumerate(g["series"]):
        color = COLORS[si % 8]
        punts = [(xs[i], y1 - (v / sostre) * (y1 - y0)) for i, v in enumerate(s["valors"][:n]) if v is not None]
        trams, actual = [], []
        for i, v in enumerate(s["valors"][:n]):   # un buit (None) talla la línia
            if v is None:
                if actual:
                    trams.append(actual)
                actual = []
            else:
                actual.append((xs[i], y1 - (v / sostre) * (y1 - y0)))
        if actual:
            trams.append(actual)
        for t in trams:
            if len(t) > 1:
                cos.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" '
                           f'stroke-linecap="round" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in t)}"/>')
        for x, y in punts:
            cos.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}" stroke="{FONS}" stroke-width="1.5"/>')
        if punts:
            darrer = [v for v in s["valors"][:n] if v is not None][-1]
            x, y = punts[-1]
            cos.append(_text(x + 7, y + 3.5, format_valor(darrer, unitat), 9, TEXT, "start", "bold"))
    cos.append(_etiquetes_x(g["eix_x"], xs, alcada - 10, (x1 - x0) / max(n - 1, 1)))
    return _embolcall(amplada, alcada, "".join(cos), g.get("titol", ""))


def _horitzontal(g: dict) -> bool:
    eix = g.get("eix_x") or []
    return len(eix) <= 12 and any(len(str(e)) > 9 for e in eix)


def barres(g: dict, amplada: int = 640, alcada: int = 230, apilades: bool = False) -> str:
    valors = _valors(g)
    eix = g.get("eix_x") or []
    if not valors or not eix:
        return _sense_dades(amplada, alcada, g.get("titol", ""))
    unitat = g.get("unitat", "enter")
    series = g["series"]
    n = len(eix)
    if apilades:
        totals = [sum((s["valors"][i] or 0) for s in series if i < len(s["valors"])) for i in range(n)]
        maxim = max(totals)
    else:
        maxim = max(valors)
    sostre, marques = _escala(maxim, unitat)
    if _horitzontal(g) and not apilades:
        # Percentatges en horitzontal: sempre sobre el 100 %, perquè dos gràfics veïns es puguin comparar.
        return _barres_horitzontals(g, amplada, 1.0 if unitat == "pct" and maxim <= 1 else sostre, unitat)
    llegenda, h_ll = _llegenda(series, 52, 14, amplada - 60)
    x0, y0, x1, y1 = 52, 14 + h_ll + 6, amplada - 12, alcada - 26
    banda = (x1 - x0) / n
    grups = 1 if apilades else len(series)
    gruix = min(34.0, banda * 0.72 / grups)
    etiquetar = n * grups <= 14
    cos = [llegenda, _eix_y(x0, y0, y1, x1 - x0, marques, sostre, unitat)]
    centres = []
    for i in range(n):
        centre = x0 + banda * (i + 0.5)
        centres.append(centre)
        base_y = y1
        for si, s in enumerate(series):
            v = s["valors"][i] if i < len(s["valors"]) else None
            if v is None or v <= 0:
                continue
            h = (v / sostre) * (y1 - y0)
            if apilades:
                x = centre - gruix / 2
                y = base_y - h
                # 2 px de separació entre segments (vora del color del fons)
                cos.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{gruix:.1f}" height="{max(h - 1, 0.5):.1f}" '
                           f'fill="{COLORS[si % 8]}" stroke="{FONS}" stroke-width="1"/>')
                if etiquetar and h > 13:
                    cos.append(_text(centre, y + h / 2 + 3.5, format_valor(v, unitat, True), 9, FONS, "middle"))
                base_y = y
            else:
                x = centre - gruix * grups / 2 + si * gruix
                cos.append(f'<path d="{_barra_vertical(x + 1, y1, gruix - 2, h)}" fill="{COLORS[si % 8]}"/>')
                if etiquetar:
                    cos.append(_text(x + gruix / 2, y1 - h - 4, format_valor(v, unitat, True), 9, TEXT, "middle"))
        if apilades and etiquetar:
            total = sum((s["valors"][i] or 0) for s in series if i < len(s["valors"]))
            cos.append(_text(centre, base_y - 4, format_valor(total, unitat, True), 9, TEXT, "middle", "bold"))
    cos.append(_etiquetes_x(eix, centres, alcada - 10, banda))
    return _embolcall(amplada, alcada, "".join(cos), g.get("titol", ""))


def _barra_vertical(x: float, y_base: float, w: float, h: float, r: float = 3) -> str:
    """Barra amb l'extrem de dades arrodonit i la base recta (ancorada a l'eix)."""
    r = min(r, w / 2, h)
    return (f"M{x:.1f},{y_base:.1f} V{y_base - h + r:.1f} Q{x:.1f},{y_base - h:.1f} {x + r:.1f},{y_base - h:.1f} "
            f"H{x + w - r:.1f} Q{x + w:.1f},{y_base - h:.1f} {x + w:.1f},{y_base - h + r:.1f} V{y_base:.1f} Z")


def _barres_horitzontals(g: dict, amplada: int, sostre: float, unitat: str) -> str:
    series, eix = g["series"], g["eix_x"]
    llegenda, h_ll = _llegenda(series, 12, 14, amplada - 20)
    fila = 12 * len(series) + 10
    alcada = int(20 + h_ll + fila * len(eix) + 8)
    etiqueta_w = min(220, max(len(str(e)) for e in eix) * 6 + 10)
    x0, x1, y0 = 12 + etiqueta_w, amplada - 60, 14 + h_ll
    cos = [llegenda]
    for i, e in enumerate(eix):
        y = y0 + i * fila
        cos.append(_text(x0 - 8, y + fila / 2 + 3, _retalla(e, int(etiqueta_w / 6)), 10, TEXT, "end"))
        for si, s in enumerate(series):
            v = s["valors"][i] if i < len(s["valors"]) else None
            yb = y + 5 + si * 12
            if v is None:
                cos.append(_text(x0 + 2, yb + 8, "—", 9))
                continue
            w = max((v / sostre) * (x1 - x0), 0)
            r = min(3, w / 2)
            cos.append(f'<path d="M{x0:.1f},{yb:.1f} H{x0 + w - r:.1f} Q{x0 + w:.1f},{yb:.1f} {x0 + w:.1f},{yb + r:.1f} '
                       f'V{yb + 10 - r:.1f} Q{x0 + w:.1f},{yb + 10:.1f} {x0 + w - r:.1f},{yb + 10:.1f} H{x0:.1f} Z" '
                       f'fill="{COLORS[si % 8]}"/>')
            cos.append(_text(x0 + w + 5, yb + 8.5, format_valor(v, unitat), 9, TEXT))
    cos.append(f'<line x1="{x0}" x2="{x0}" y1="{y0}" y2="{y0 + fila * len(eix)}" stroke="{EIX}"/>')
    return _embolcall(amplada, alcada, "".join(cos), g.get("titol", ""))


def donut(g: dict, amplada: int = 640, alcada: int = 210) -> str:
    """Donut d'una sola sèrie (parts d'un total). Les etiquetes de l'eix X són les parts."""
    eix = g.get("eix_x") or []
    valors = (g.get("series") or [{"valors": []}])[0]["valors"]
    parts = [(e, v) for e, v in zip(eix, valors) if v]
    total = sum(v for _, v in parts)
    if not parts or total <= 0:
        return _sense_dades(amplada, alcada, g.get("titol", ""))
    if len(parts) > 8:   # més de 8 colors no es distingeixen: la resta va a «Altres»
        parts = parts[:7] + [("Altres", sum(v for _, v in parts[7:]))]
    unitat = g.get("unitat", "enter")
    cx, cy, r, gruix = 110, alcada / 2, min(80, alcada / 2 - 14), 26
    cos, angle = [], -math.pi / 2
    for i, (_, v) in enumerate(parts):
        a = 2 * math.pi * v / total
        cos.append(_arc(cx, cy, r, r - gruix, angle, angle + a, COLORS[i % 8], sola=len(parts) == 1))
        angle += a
    cos.append(_text(cx, cy + 2, format_valor(total, unitat, True), 15, TEXT, "middle", "bold"))
    cos.append(_text(cx, cy + 17, "total", 9, TEXT_SECUNDARI, "middle"))
    lx, ly = 230, cy - (len(parts) * 20) / 2 + 12
    for i, (e, v) in enumerate(parts):
        y = ly + i * 20
        cos.append(f'<rect x="{lx}" y="{y - 9:.1f}" width="11" height="11" rx="2" fill="{COLORS[i % 8]}"/>')
        cos.append(_text(lx + 18, y, _retalla(e, 36), 10, TEXT))
        cos.append(_text(amplada - 12, y, f"{format_valor(v, unitat)} · {format_valor(v / total, 'pct')}", 10,
                         TEXT_SECUNDARI, "end"))
    return _embolcall(amplada, alcada, "".join(cos), g.get("titol", ""))


def _arc(cx, cy, r_ext, r_int, a0, a1, color, sola=False) -> str:
    if sola:   # un sol sector: dos cercles (un arc de 360° no es pot dibuixar amb un sol camí)
        return (f'<circle cx="{cx}" cy="{cy}" r="{(r_ext + r_int) / 2}" fill="none" stroke="{color}" '
                f'stroke-width="{r_ext - r_int}"/>')
    gran = 1 if a1 - a0 > math.pi else 0

    def p(r, a):
        return f"{cx + r * math.cos(a):.2f},{cy + r * math.sin(a):.2f}"
    return (f'<path d="M{p(r_ext, a0)} A{r_ext},{r_ext} 0 {gran} 1 {p(r_ext, a1)} L{p(r_int, a1)} '
            f'A{r_int},{r_int} 0 {gran} 0 {p(r_int, a0)} Z" fill="{color}" stroke="{FONS}" stroke-width="2"/>')


def svg(g: dict, amplada: int = 640) -> str:
    """SVG d'un gràfic de l'informe segons el seu `tipus`."""
    tipus = g.get("tipus")
    if tipus == "linia":
        return linia(g, amplada)
    if tipus == "barres":
        return barres(g, amplada)
    if tipus == "barres_apilades":
        return barres(g, amplada, apilades=True)
    if tipus == "donut":
        return donut(g, amplada)
    raise ValueError(f"Tipus de gràfic desconegut: {tipus}")
