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
import sqlite3

from . import siluetes, temps

MAX_BYTES = 6 * 1024 * 1024       # el que acceptem d'entrada
COSTAT_MAX = 1200                 # px del costat llarg després de redimensionar
MIMES = {"image/jpeg", "image/png", "image/webp"}


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
        """INSERT INTO imatge_peca (clau, model, color, mime, dades, font, url_origen, versio, actualitzada)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(model, color) DO UPDATE SET mime=excluded.mime, dades=excluded.dades, font=excluded.font,
             url_origen=excluded.url_origen, versio=excluded.versio, actualitzada=excluded.actualitzada""",
        (clau(model, color or ""), model, color or "", mime, neta, font, url_origen, versio, ara))
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
    return con.execute("SELECT mime, dades, versio FROM imatge_peca WHERE clau = ?", (c,)).fetchone()


def _index(con: sqlite3.Connection) -> dict[tuple[str, str], str]:
    return {(r["model"], r["color"]): f"/imatges/peca/{r['clau']}?v={r['versio']}"
            for r in con.execute("SELECT model, color, clau, versio FROM imatge_peca")}


class Resolutor:
    """Resol la imatge de molts models d'un cop (una sola consulta): foto del color, foto del model
    o silueta de la categoria amb el color de la peça."""

    def __init__(self, con: sqlite3.Connection):
        from .analitica import base
        self.index = _index(con)
        self.noms = {m: i["nom"] for m, i in base.info_models(con).items()}

    def de(self, model: str, color: str | None, categoria: str | None, nom: str | None = None) -> dict:
        url = self.index.get((model, color or "")) or self.index.get((model, ""))
        if url:
            return {"url": url, "silueta": False}
        return {"url": siluetes.url(categoria, color, nom or self.noms.get(model)), "silueta": True}


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
    for f in con.execute("SELECT DISTINCT model, color, categoria FROM catalog_sku ORDER BY model, color"):
        im = res.de(f["model"], f["color"], f["categoria"])
        font = fonts.get((f["model"], f["color"])) or fonts.get((f["model"], ""))
        out.append({"model": f["model"], "nom": base.nom_model(info, f["model"]), "color": f["color"],
                    "categoria": f["categoria"], "imatge": im["url"], "silueta": im["silueta"],
                    "font": font[0] if font else None, "actualitzada": font[1] if font else None})
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
