"""Imatges de les peces (v0.5): la foto de cada model i color que veu el client a la fitxa NFC
i la marca al tauler.

D'on surten:
  * pujada des del tauler (Fitxa NFC → Imatges de les peces);
  * una URL (columna `imatge_url` del catàleg CSV o el camp URL del tauler): la plataforma la
    descarrega una vegada i la serveix ella mateixa;
  * Shopify: la imatge del producte (o de la variant) es descarrega en sincronitzar el catàleg.

La plataforma sempre serveix la imatge des del seu propi domini: el mòbil del client no fa cap
petició a tercers (cap CDN, cap rastreig), i la CSP pot continuar sent `img-src 'self' data:`.
En desar-la es redimensiona (1.200 px com a molt), es passa a JPEG o PNG i es treuen les
metadades (EXIF amb la ubicació GPS, càmera...).

Si un model no té imatge, es mostra una silueta de la seva categoria pintada amb el seu color
(`hebra/siluetes.py`): la fitxa i el tauler sempre ensenyen una peça de roba.
"""

import hashlib
import io
import secrets
import sqlite3

from . import siluetes, temps

MAX_BYTES = 6 * 1024 * 1024       # el que acceptem d'entrada
COSTAT_MAX = 1200                 # px del costat llarg després de redimensionar
MIMES = {"image/jpeg", "image/png", "image/webp"}
MAX_GALERIA = 8                   # fotos de més per model (a part de la principal)


class ErrorImatge(ValueError):
    pass


def _tipus(dades: bytes) -> str | None:
    if dades[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if dades[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if dades[:4] == b"RIFF" and dades[8:12] == b"WEBP":
        return "image/webp"
    return None


def normalitza(dades: bytes) -> tuple[bytes, str]:
    """Valida i neteja una imatge: (bytes, mime). JPEG si és opaca, PNG si té transparència."""
    if not dades:
        raise ErrorImatge("La imatge és buida")
    if len(dades) > MAX_BYTES:
        raise ErrorImatge(f"La imatge fa més de {MAX_BYTES // (1024 * 1024)} MB")
    if _tipus(dades) is None:
        raise ErrorImatge("Només s'accepten imatges JPEG, PNG o WebP")
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(dades))
        if im.width * im.height > 40_000_000:
            raise ErrorImatge("La imatge és massa gran")
        im = ImageOps.exif_transpose(im)  # gira segons l'EXIF abans de treure'l
        im.thumbnail((COSTAT_MAX, COSTAT_MAX))
        rgba = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P", "PA") else None
        sortida = io.BytesIO()
        if rgba is not None and rgba.getextrema()[3][0] < 255:
            rgba.save(sortida, "PNG", optimize=True)
            return sortida.getvalue(), "image/png"
        im.convert("RGB").save(sortida, "JPEG", quality=86, optimize=True, progressive=True)
        return sortida.getvalue(), "image/jpeg"
    except ErrorImatge:
        raise
    except Exception as e:  # noqa: BLE001 — qualsevol fitxer que Pillow no entengui
        raise ErrorImatge("No s'ha pogut llegir la imatge") from e


def fons(dades: bytes) -> str:
    """Color del fons ('#RRGGBB') si és una foto de producte sobre fons clar i llis (les quatre cantonades
    iguals i quasi blanques): la fitxa la mostra sencera sobre aquest color, sense retallar-la.
    '' si és una foto ambientada o un detall que omple tota la foto (llavors omple el marc)."""
    try:
        from PIL import Image, ImageStat
        im = Image.open(io.BytesIO(dades)).convert("RGB")
        im.thumbnail((240, 240))
        w, h = im.size
        c = max(3, min(w, h) * 6 // 100)
        cantons = [ImageStat.Stat(im.crop(r)) for r in
                   ((0, 0, c, c), (w - c, 0, w, c), (0, h - c, c, h), (w - c, h - c, w, h))]
        mitjana = [sum(st.mean[i] for st in cantons) / 4 for i in range(3)]
        if max(max(st.stddev) for st in cantons) > 10:
            return ""
        if max(abs(st.mean[i] - mitjana[i]) for st in cantons for i in range(3)) > 14:
            return ""
        if sum(mitjana) / 3 < 236:  # només fons quasi blancs (foto de producte); un fons gris d'estudi o
            return ""               # fosc vol dir foto ambientada o detall: omple el marc
        return "#" + "".join(f"{round(x):02X}" for x in mitjana)
    except Exception:  # noqa: BLE001 — si no es pot llegir, es mostra omplint el marc
        return ""


def clau(model: str, color: str = "") -> str:
    """Identificador públic estable d'una imatge (no revela el codi intern del model)."""
    return hashlib.sha256(f"{model}\x1f{color}".encode()).hexdigest()[:20]


def desa(con: sqlite3.Connection, model: str, color: str, dades: bytes, font: str = "pujada",
         url_origen: str | None = None) -> dict:
    """Desa (o substitueix) la imatge d'un model i color. `color=''` = imatge per a tots els colors."""
    if not model or len(model) > 80 or len(color or "") > 80:
        raise ErrorImatge("Model o color no vàlid")
    neta, mime = normalitza(dades)
    ara = temps.ara()
    versio = hashlib.sha256(neta).hexdigest()[:10]
    con.execute(
        """INSERT INTO imatge_peca (clau, model, color, mime, dades, font, url_origen, versio, actualitzada, fons)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(model, color) DO UPDATE SET mime=excluded.mime, dades=excluded.dades, font=excluded.font,
             url_origen=excluded.url_origen, versio=excluded.versio, actualitzada=excluded.actualitzada,
             fons=excluded.fons""",
        (clau(model, color or ""), model, color or "", mime, neta, font, url_origen, versio, ara, fons(neta)))
    con.commit()
    return {"model": model, "color": color or "", "url": f"/imatges/peca/{clau(model, color or '')}?v={versio}",
            "bytes": len(neta), "font": font}


def des_de_url(con: sqlite3.Connection, model: str, color: str, url: str, font: str = "url") -> dict:
    """Descarrega una imatge (només http/https públics: la mateixa protecció SSRF que les integracions)."""
    from .integracions import http
    if not url or not url.lower().startswith(("http://", "https://")) or len(url) > 2000:
        raise ErrorImatge("La URL ha de començar per http:// o https://")
    try:
        http.comprova_desti(url)
        r = http.peticio("GET", url, {"Accept": "image/*"}, temps_espera=15)
    except (http.ErrorHttp, http.ErrorXarxa, ValueError) as e:
        raise ErrorImatge(f"No s'ha pogut descarregar la imatge: {e}") from e
    return desa(con, model, color, r.cos, font=font, url_origen=url)


def esborra(con: sqlite3.Connection, model: str, color: str = "") -> bool:
    n = con.execute("DELETE FROM imatge_peca WHERE model = ? AND color = ?", (model, color or "")).rowcount
    con.commit()
    return bool(n)


def per_clau(con: sqlite3.Connection, c: str) -> sqlite3.Row | None:
    return (con.execute("SELECT mime, dades, versio FROM imatge_peca WHERE clau = ?", (c,)).fetchone()
            or con.execute("SELECT mime, dades, versio FROM imatge_galeria WHERE clau = ?", (c,)).fetchone())


def omple_fons(con: sqlite3.Connection) -> int:
    """Calcula el color de fons de les fotos desades abans de la v0.6 (es crida en arrencar)."""
    n = 0
    for f in con.execute("SELECT clau, dades FROM imatge_peca WHERE fons IS NULL").fetchall():
        con.execute("UPDATE imatge_peca SET fons = ? WHERE clau = ?", (fons(f["dades"]), f["clau"]))
        n += 1
    con.commit()
    return n


# ── Galeria: més fotos del mateix model ────────────────────────────────────

def afegeix_galeria(con: sqlite3.Connection, model: str, dades: bytes) -> dict:
    """Afegeix una foto a la galeria del model (després de la principal)."""
    if not model or len(model) > 80:
        raise ErrorImatge("Model no vàlid")
    n, ordre = con.execute("SELECT COUNT(*), COALESCE(MAX(ordre), 0) FROM imatge_galeria WHERE model = ?",
                           (model,)).fetchone()
    if n >= MAX_GALERIA:
        raise ErrorImatge(f"Cada peça pot tenir {MAX_GALERIA} fotos de més, com a màxim. Treu-ne alguna abans.")
    neta, mime = normalitza(dades)
    c = secrets.token_hex(10)
    versio = hashlib.sha256(neta).hexdigest()[:10]
    con.execute("""INSERT INTO imatge_galeria (clau, model, ordre, mime, dades, fons, versio, actualitzada)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (c, model, ordre + 1, mime, neta, fons(neta), versio, temps.ara()))
    con.commit()
    return {"model": model, "clau": c, "url": f"/imatges/peca/{c}?v={versio}", "bytes": len(neta)}


def esborra_galeria(con: sqlite3.Connection, model: str, c: str) -> bool:
    n = con.execute("DELETE FROM imatge_galeria WHERE model = ? AND clau = ?", (model, c)).rowcount
    con.commit()
    return bool(n)


def esborra_model(con: sqlite3.Connection, model: str) -> None:
    """Totes les fotos d'un model (principal i galeria)."""
    con.execute("DELETE FROM imatge_peca WHERE model = ?", (model,))
    con.execute("DELETE FROM imatge_galeria WHERE model = ?", (model,))
    con.commit()


def _galeries(con: sqlite3.Connection, model: str | None = None) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    q = "SELECT model, clau, versio, fons FROM imatge_galeria" + (" WHERE model = ?" if model else "") + " ORDER BY ordre"
    for r in con.execute(q, (model,) if model else ()):
        out.setdefault(r["model"], []).append(
            {"clau": r["clau"], "url": f"/imatges/peca/{r['clau']}?v={r['versio']}", "fons": r["fons"] or ""})
    return out


def _index(con: sqlite3.Connection) -> dict[tuple[str, str], dict]:
    return {(r["model"], r["color"]): {"url": f"/imatges/peca/{r['clau']}?v={r['versio']}", "fons": r["fons"] or ""}
            for r in con.execute("SELECT model, color, clau, versio, fons FROM imatge_peca")}


class Resolutor:
    """Resol la imatge de molts models d'un cop (una sola consulta): foto del color, foto del model
    o silueta de la categoria amb el color de la peça."""

    def __init__(self, con: sqlite3.Connection):
        from .analitica import base
        self.index = _index(con)
        self.noms = {m: i["nom"] for m, i in base.info_models(con).items()}

    def de(self, model: str, color: str | None, categoria: str | None, nom: str | None = None) -> dict:
        im = self.index.get((model, color or "")) or self.index.get((model, ""))
        if im:
            return {"url": im["url"], "fons": im["fons"], "silueta": False}
        return {"url": siluetes.url(categoria, color, nom or self.noms.get(model)), "fons": "", "silueta": True}


def fotos(con: sqlite3.Connection, model: str, color: str | None, categoria: str | None, nom: str | None = None) -> list[dict]:
    """Totes les fotos d'una peça per a la galeria de la fitxa: la principal i després les de més."""
    principal = Resolutor(con).de(model, color, categoria, nom)
    extres = _galeries(con, model).get(model, [])
    if principal["silueta"] and extres:
        return [dict(e, silueta=False) for e in extres]
    return [principal] + [dict(e, silueta=False) for e in extres]


def imatge(con: sqlite3.Connection, model: str, color: str | None, categoria: str | None) -> dict:
    return Resolutor(con).de(model, color, categoria)


def llista(con: sqlite3.Connection) -> list[dict]:
    """Cada model i color del catàleg amb la seva imatge (per a la pantalla d'imatges del tauler)."""
    from .analitica import base
    info = base.info_models(con)
    res = Resolutor(con)
    fonts = {(r["model"], r["color"]): (r["font"], r["actualitzada"])
             for r in con.execute("SELECT model, color, font, actualitzada FROM imatge_peca")}
    out = []
    galeries = _galeries(con)
    for f in con.execute("SELECT DISTINCT model, color, categoria FROM catalog_sku ORDER BY model, color"):
        im = res.de(f["model"], f["color"], f["categoria"])
        font = fonts.get((f["model"], f["color"])) or fonts.get((f["model"], ""))
        out.append({"model": f["model"], "nom": base.nom_model(info, f["model"]), "color": f["color"],
                    "categoria": f["categoria"], "imatge": im["url"], "silueta": im["silueta"],
                    "font": font[0] if font else None, "actualitzada": font[1] if font else None,
                    "galeria": [{"clau": g["clau"], "url": g["url"]} for g in galeries.get(f["model"], [])]})
    return out


def importa_urls(con: sqlite3.Connection, peticions: list[tuple[str, str, str]], font: str,
                 maxim: int = 300) -> tuple[int, list[str]]:
    """Descarrega les imatges [(model, color, url)] que encara no tenim (o que han canviat d'URL).
    No para per una imatge dolenta: torna (descarregades, errors)."""
    ja = {(r["model"], r["color"]): r["url_origen"] for r in con.execute("SELECT model, color, url_origen FROM imatge_peca")}
    n, errors, vistes = 0, [], set()
    for model, color, url in peticions:
        clau_ = (model, color or "")
        if not url or clau_ in vistes or ja.get(clau_) == url:
            continue
        vistes.add(clau_)
        if n + len(errors) >= maxim:
            errors.append(f"S'han deixat imatges per a la propera sincronització (màxim {maxim} cada vegada)")
            break
        try:
            des_de_url(con, model, color or "", url, font=font)
            n += 1
        except ErrorImatge as e:
            errors.append(f"{model} {color}: {e}")
    return n, errors
