"""Demo amb una peça real: converteix un model de prova en una peça que es pot tocar (p. ex. un polo).

Les etiquetes i els enllaços NFC del model no canvien: l'adhesiu ja gravat obre la fitxa nova.
Canvia el codi de model (a totes les taules on surt), el color, la categoria, el preu i la fitxa
d'origen (nom, descripció, composició, ajust, cura, preguntes, amb què combina), esborra la foto i el
contingut propi del model antic, i adapta els textos de les tasques i decisions de la botiga de prova.

Ús (al servidor):
  sudo hebra-admin demo-peca --model CL-24-NAT --nou-model PH4012-166 \\
       --fitxer /opt/hebra-plataforma/dades/demo-polo.json --fet-a PE

Si es torna a carregar el lot de prova, el model torna a ser el de prova.
"""

import json
import sqlite3

from . import imatges

# Textos de la botiga de prova (tasques i decisions) que parlen del model antic: (antic, nou).
TEXTOS_PROVA = {"CL-24-NAT": [("la camisa de lli", "el {nom}"), ("l'han demanada", "l'han demanat")]}


class ErrorPeca(ValueError):
    pass


def _tr(v, idioma: str = "ca") -> str:
    return v.get(idioma) or next(iter(v.values()), "") if isinstance(v, dict) else (v or "")


def canvia(con: sqlite3.Connection, model: str, nou_model: str, peca: dict, fet_a: str | None = None,
           foto: bytes | list[bytes] | None = None, botiga_id: str = "PROVA-01") -> dict:
    """Aplica `peca` (format de peça de hebra-origen) al model `model` i el reanomena `nou_model`."""
    nou_model = (nou_model or model).strip()
    files = con.execute("SELECT gtin, talla, origen_json FROM catalog_sku WHERE model = ?", (model,)).fetchall()
    if not files:
        raise ErrorPeca(f"No hi ha cap model «{model}» al catàleg.")
    if nou_model != model and con.execute("SELECT 1 FROM catalog_sku WHERE model = ?", (nou_model,)).fetchone():
        raise ErrorPeca(f"Ja hi ha un model «{nou_model}» al catàleg.")
    for clau in ("nom", "color"):
        if not peca.get(clau):
            raise ErrorPeca(f"Al fitxer hi falta «{clau}».")

    anterior = json.loads(files[0]["origen_json"] or "{}")
    origen = dict(peca, model=nou_model,
                  faq_general=anterior.get("faq_general", []),
                  estoc={t["talla"]: t.get("estoc") for t in peca.get("talles", [])})
    if fet_a:
        origen["etapes"] = [e for e in origen.get("etapes", []) if e.get("etapa") != "confeccio"] + [
            {"etapa": "confeccio", "pais": fet_a.strip().upper()[:2], "actor": peca.get("marca", "")}]
    color = _tr(peca["color"])
    categoria = peca.get("forma") or "altres"
    con.execute("""UPDATE catalog_sku SET model = ?, color = ?, categoria = ?, preu_eur = COALESCE(?, preu_eur),
                   origen_json = ? WHERE model = ?""",
                (nou_model, color, categoria, peca.get("preu_eur"), json.dumps(origen, ensure_ascii=False), model))

    # El model antic deixa d'existir: la seva foto i el seu contingut propi ja no valen.
    if nou_model != model:
        imatges.esborra_model(con, model)
    con.execute("DELETE FROM contingut_model WHERE model = ?", (model,))
    if nou_model != model:
        con.execute("DELETE FROM contingut_model WHERE model = ?", (nou_model,))
        for taula in ("decisio", "assignacio_model"):
            con.execute(f"UPDATE {taula} SET model = ? WHERE model = ?", (nou_model, model))
        # Els altres models que proposaven combinar-lo amb el model antic.
        for f in con.execute("SELECT gtin, origen_json FROM catalog_sku WHERE origen_json LIKE ?",
                             (f'%"{model}"%',)).fetchall():
            o = json.loads(f["origen_json"])
            if model in (o.get("combina") or []):
                o["combina"] = [nou_model if m == model else m for m in o["combina"]]
                con.execute("UPDATE catalog_sku SET origen_json = ? WHERE gtin = ?",
                            (json.dumps(o, ensure_ascii=False), f["gtin"]))

    # Textos de la botiga de prova que parlen de la peça antiga.
    for antic, nou in TEXTOS_PROVA.get(model, []):
        nou = nou.format(nom=_tr(peca["nom"]).lower())
        for taula, camps in (("tasca", ("titol", "detall")), ("decisio", ("titol", "descripcio"))):
            for camp in camps:
                con.execute(f"UPDATE {taula} SET {camp} = replace({camp}, ?, ?) WHERE botiga_id = ?",
                            (antic, nou, botiga_id))
    fotos = [foto] if isinstance(foto, bytes) else list(foto or [])
    if fotos:  # la primera és la principal; les altres, a la galeria
        imatges.esborra_model(con, nou_model)
        imatges.desa(con, nou_model, "", fotos[0], font="pujada")
        for f in fotos[1:]:
            imatges.afegeix_galeria(con, nou_model, f)
    con.commit()
    return {"model": nou_model, "nom": _tr(peca["nom"]), "color": color, "variants": len(files),
            "foto": bool(fotos), "fotos": len(fotos)}
