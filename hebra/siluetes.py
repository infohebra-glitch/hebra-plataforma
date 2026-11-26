"""Siluetes de peça (SVG) per quan un model encara no té foto.

Una figura per família de peça (samarreta, camisa, jersei, jaqueta, pantaló, faldilla, vestit),
pintada amb el color del model, amb ombres suaus i costures: a la fitxa NFC i al tauler sempre es
veu una peça de roba, mai un requadre buit. La família surt de la categoria del catàleg i, si no
n'hi ha prou, del nom; el color, del nom del color (català, castellà, anglès o francès).

URL pública: `/imatges/silueta/<familia>.svg?c=<hex>` (sense dades de la marca).
"""

import re
import unicodedata

FAMILIES = ("samarreta", "camisa", "jersei", "jaqueta", "pantalo", "faldilla", "vestit", "peca")

# Paraules (sense accents, en minúscula) que porten a cada família. L'ordre importa: «sobrecamisa» és camisa.
_PARAULES = [
    ("vestit", ("vestit", "vestido", "dress", "robe", "mono", "jumpsuit")),
    ("faldilla", ("faldilla", "falda", "skirt", "jupe")),
    ("pantalo", ("pantal", "texan", "vaquer", "jean", "pant", "trouser", "short", "bermuda", "part de baix",
                 "parte de abajo", "bottom")),
    ("jaqueta", ("jaqueta", "chaqueta", "americana", "abric", "abrigo", "jacket", "coat", "blazer", "veste",
                 "manteau", "parka", "gavardina", "trench", "sobrecamisa", "overshirt")),
    ("jersei", ("jersei", "jersey", "punt", "sweater", "pull", "dessuadora", "sudadera", "hoodie",
                "cardigan", "rebeca", "knit")),
    ("camisa", ("camisa", "brusa", "blusa", "shirt", "blouse", "chemise", "part de dalt", "parte de arriba")),
    ("samarreta", ("samarreta", "camiseta", "t-shirt", "tshirt", "tee", "top", "polo", "tank")),
]

COLORS = [
    (("blau nit", "azul noche", "navy", "mari", "marino", "bleu nuit", "bleu marine"), "#1F2A44"),
    (("indi", "indigo", "denim", "vaquer", "tejano"), "#2E3D5C"),
    (("blau cel", "celeste", "sky"), "#9DB8D6"),
    (("blau", "azul", "blue", "bleu"), "#3A5F8F"),
    (("grafit", "grafito", "graphite", "antracita", "anthracite", "gris fosc", "gris oscuro"), "#45484D"),
    (("gris clar", "gris claro", "light grey", "perla", "pearl"), "#C9C7C4"),
    (("gris", "grey", "gray"), "#8E8E8E"),
    (("negre", "negro", "black", "noir"), "#1E1E21"),
    (("blanc trencat", "roto", "off-white", "ivori", "marfil", "ivory"), "#EFE9DC"),
    (("blanc", "blanco", "white"), "#F5F4F0"),
    (("natural", "cru", "crudo", "ecru", "ecru", "beix", "beige", "lli", "lino", "linen", "arena", "sand", "sable"), "#D8CCB4"),
    (("camel", "camell"), "#B5865A"),
    (("terra", "teja", "terracota", "terracotta", "rovell", "oxido", "rust"), "#A35F3E"),
    (("marro", "marron", "brown", "brun", "xocolata", "chocolate"), "#6A4A34"),
    (("caqui", "khaki", "kaki"), "#8B845A"),
    (("oliva", "olive"), "#6B6B3C"),
    (("verd", "verde", "green", "vert"), "#4E6B4B"),
    (("grana", "granate", "burgundy", "bordeus", "burdeos", "bordeaux", "vino", "wine"), "#8C304B"),
    (("vermell", "rojo", "red", "rouge"), "#A83A38"),
    (("rosa", "pink", "rose"), "#D8A2A9"),
    (("mostassa", "mostaza", "mustard", "moutarde"), "#C29A2E"),
    (("groc", "amarillo", "yellow", "jaune"), "#DDB94B"),
    (("taronja", "naranja", "orange"), "#D27A3A"),
    (("lila", "morat", "morado", "purple", "violeta", "violet", "malva"), "#7A5A8C"),
]
PER_DEFECTE = "#B7B3B2"

_HEX = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def _net(text: str | None) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def familia(categoria: str | None, nom: str | None = None) -> str:
    """El nom de la peça mana («Jersei de merino» a la categoria «part de dalt» és un jersei)."""
    for text in (nom, categoria):
        t = _net(text)
        if not t:
            continue
        for fam, paraules in _PARAULES:
            if any(p in t for p in paraules):
                return fam
    return "peca"


def color_hex(color: str | None) -> str:
    if color and _HEX.match(color.strip()):
        return "#" + color.strip().lstrip("#").upper()
    t = _net(color)
    if t:
        for noms, hexa in COLORS:
            if any(re.search(r"\b" + re.escape(n), t) for n in noms):
                return hexa
    return PER_DEFECTE


def url(categoria: str | None, color: str | None, nom: str | None = None) -> str:
    return f"/imatges/silueta/{familia(categoria, nom)}.svg?c={color_hex(color).lstrip('#')}"


# ---------------------------------------------------------------- dibuix

def _rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _mescla(h: str, amb: str, t: float) -> str:
    a, b = _rgb(h), _rgb(amb)
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _lluminositat(h: str) -> float:
    r, g, b = _rgb(h)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


# Figures en una caixa de 400 × 500. `cos`: contorn; `detall`: costures i plecs (traç); `farcit`: peces
# interiors (coll, cintura...) que es pinten una mica més fosques.
_FIGURES = {
    "samarreta": {
        "cos": "M128 74 L170 58 Q200 84 230 58 L272 74 L346 124 L318 178 L284 158 L286 440 Q200 454 114 440 "
               "L116 158 L82 178 L54 124 Z",
        "farcit": ["M170 58 Q200 84 230 58 L224 56 Q200 74 176 56 Z"],
        "detall": ["M116 158 L128 74", "M284 158 L272 74", "M82 178 L54 124", "M114 428 Q200 442 286 428",
                   "M74 166 L96 150", "M326 166 L304 150", "M170 140 Q190 260 176 400"],
    },
    "camisa": {
        "cos": "M134 70 L172 56 L200 92 L228 56 L266 70 L300 92 L330 250 L346 420 L314 426 L294 274 L292 452 "
               "Q200 464 108 452 L106 274 L86 426 L54 420 L70 250 L100 92 Z",
        "farcit": ["M172 56 L200 92 L184 112 L160 70 Z", "M228 56 L200 92 L216 112 L240 70 Z"],
        "detall": ["M200 96 L200 458", "M300 92 L292 274", "M100 92 L108 274", "M60 398 L88 396",
                   "M340 398 L312 396", "M228 150 L270 150 L270 196 L228 196 Z"],
        "botons": [140, 192, 244, 296, 348, 400],
    },
    "jersei": {
        "cos": "M132 76 L170 60 Q200 88 230 60 L268 76 L302 96 L334 250 L348 410 L316 418 L294 268 L292 432 "
               "Q200 444 108 432 L106 268 L84 418 L52 410 L66 250 L98 96 Z",
        "farcit": ["M170 60 Q200 88 230 60 L222 58 Q200 76 178 58 Z", "M108 418 Q200 430 292 418 L292 432 "
                   "Q200 444 108 432 Z", "M52 396 L84 404 L84 418 L52 410 Z", "M348 396 L316 404 L316 418 L348 410 Z"],
        "detall": ["M302 96 L294 268", "M98 96 L106 268", "M130 422 L130 438", "M160 424 L160 440",
                   "M190 425 L190 441", "M220 425 L220 441", "M250 424 L250 440", "M280 422 L280 437"],
    },
    "jaqueta": {
        "cos": "M130 70 L174 54 L200 70 L226 54 L270 70 L304 92 L334 250 L350 420 L318 428 L298 272 L298 456 "
               "Q200 468 102 456 L102 272 L82 428 L50 420 L66 250 L96 92 Z",
        "farcit": ["M174 54 L200 70 L200 250 L162 150 L150 84 Z", "M226 54 L200 70 L200 250 L238 150 L250 84 Z"],
        "detall": ["M200 250 L196 460", "M304 92 L298 272", "M96 92 L102 272", "M120 330 L170 330",
                   "M230 330 L280 330", "M236 190 L272 186"],
        "botons": [292, 348],
    },
    "pantalo": {
        "cos": "M128 58 L272 58 L292 462 L218 462 L200 176 L182 462 L108 462 Z",
        "farcit": ["M128 58 L272 58 L273 82 L127 82 Z"],
        "detall": ["M200 82 L200 176", "M200 82 Q214 126 200 150", "M134 84 Q160 118 172 92",
                   "M266 84 Q240 118 228 92", "M150 82 L150 58", "M250 82 L250 58", "M147 200 L132 452",
                   "M253 200 L268 452"],
    },
    "faldilla": {
        "cos": "M142 74 L258 74 L326 444 Q200 466 74 444 Z",
        "farcit": ["M142 74 L258 74 L261 98 L139 98 Z"],
        "detall": ["M170 98 L150 450", "M200 98 L200 456", "M230 98 L250 450", "M80 430 Q200 452 320 430"],
    },
    "vestit": {
        "cos": "M154 52 L172 52 Q200 92 228 52 L246 52 L264 160 Q252 196 258 226 L326 452 Q200 474 74 452 "
               "L142 226 Q148 196 136 160 Z",
        "farcit": ["M140 214 Q200 230 260 214 L258 232 Q200 248 142 232 Z"],
        "detall": ["M172 52 Q200 92 228 52", "M170 248 L140 452", "M200 250 L200 462", "M230 248 L260 452",
                   "M84 440 Q200 460 316 440"],
    },
}


def svg(fam: str, color: str | None) -> str:
    """SVG de 400 × 500 amb la peça de la família `fam` pintada del color `color` (nom o hex)."""
    fig = _FIGURES.get(fam) or _FIGURES["samarreta"]
    base = color_hex(color)
    fosc = _lluminositat(base) < 0.35
    clar = _mescla(base, "#FFFFFF", 0.22)
    ombra = _mescla(base, "#000000", 0.28)
    tra = _mescla(base, "#FFFFFF", 0.35) if fosc else _mescla(base, "#000000", 0.32)
    interior = _mescla(base, "#000000", 0.14)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 500" role="img" aria-label="Peça">',
        "<defs>",
        f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{clar}"/>'
        f'<stop offset=".55" stop-color="{base}"/><stop offset="1" stop-color="{ombra}"/></linearGradient>',
        '<radialGradient id="f" cx=".5" cy=".42" r=".75"><stop offset="0" stop-color="#FBFAF8"/>'
        '<stop offset="1" stop-color="#ECEAE6"/></radialGradient>',
        '<filter id="s" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="9"/></filter>',
        "</defs>",
        '<rect width="400" height="500" fill="url(#f)"/>',
        '<ellipse cx="200" cy="474" rx="132" ry="11" fill="#000" opacity=".10" filter="url(#s)"/>',
    ]
    if fam == "peca":  # penja-robes amb una samarreta
        parts.append('<path d="M200 40 q-14 0 -14 13 q0 9 9 13 l5 3" fill="none" stroke="#8E8A86" '
                     'stroke-width="5" stroke-linecap="round"/>')
    parts.append(f'<path d="{fig["cos"]}" fill="url(#g)" stroke="{tra}" stroke-width="2" stroke-linejoin="round"/>')
    for p in fig.get("farcit", []):
        parts.append(f'<path d="{p}" fill="{interior}" stroke="{tra}" stroke-width="1.6" stroke-linejoin="round"/>')
    for p in fig.get("detall", []):
        parts.append(f'<path d="{p}" fill="none" stroke="{tra}" stroke-width="1.4" stroke-dasharray="5 4" '
                     'stroke-linecap="round" opacity=".7"/>')
    for y in fig.get("botons", []):
        parts.append(f'<circle cx="{206 if fam == "jaqueta" else 200}" cy="{y}" r="5" fill="{clar}" stroke="{tra}" '
                     'stroke-width="1.4"/>')
    parts.append("</svg>")
    return "".join(parts)
