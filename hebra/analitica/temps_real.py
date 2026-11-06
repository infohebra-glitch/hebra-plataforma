"""Alertes per a la web del dependent i el tauler (informe A).

Tipus:
  * `peticio_talla`: peticions del període encara obertes (estat pendent o en_cami).
  * `talla_esgotada`: >= 3 peticions del mateix GTIN el mateix dia sense estoc
    (estat no_disponible o disponible = 0). Una alerta per GTIN i dia.
  * `peca_abandonada`: peces abandonades del període encara no resoltes (insight 13).
  * `molt_provat_poc_venut`: models marcats per l'insight 3 al període.
Totes les que es llisten estan obertes; `estat` és el de la petició o 'oberta'.
"""

import sqlite3
from collections import defaultdict

from . import Filtre, base, per_model as models_mod

PETICIONS_TALLA_ESGOTADA = 3


def _cabina(p) -> str:
    return p["cabina_nom"] or (f"Cabina {p['cabina']}" if p["cabina"] else "Un client")


def alertes(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /alertes`: alertes obertes del període, de la més nova a la més antiga."""
    info = base.info_models(con)
    out = []
    peticions = base.peticions(con, f)
    for p in peticions:
        if p["estat"] in ("pendent", "en_cami"):
            out.append({"id": f"pt-{p['id']}", "tipus": "peticio_talla",
                        "text": f"{_cabina(p)} demana «{base.nom_model(info, p['model'])}» en {p['talla_demanada']}.",
                        "botiga_id": p["botiga_id"], "cabina": p["cabina"], "creada": p["hora_peticio"],
                        "estat": p["estat"], "ref": p["id"]})

    esgotades: dict[tuple, list] = defaultdict(list)
    for p in peticions:
        if base.es_perduda(p):
            esgotades[(p["botiga_id"], p["gtin_demanat"], p["hora_peticio"][:10])].append(p)
    for (botiga, gtin, dia), ps in esgotades.items():
        if len(ps) >= PETICIONS_TALLA_ESGOTADA:
            p = ps[-1]
            out.append({"id": f"te-{botiga}-{gtin}-{dia}", "tipus": "talla_esgotada",
                        "text": (f"«{base.nom_model(info, p['model'])}» en {p['talla_demanada']}: {len(ps)} peticions "
                                 f"el {dia} i no n'hi ha. Cal reposar-la."),
                        "botiga_id": botiga, "cabina": None, "creada": p["hora_peticio"], "estat": "oberta",
                        "ref": gtin})

    minuts = base.par(con, f, "minuts_abandonada")
    for a in base.abandonades(con, f):
        if a["resolta"] is None:
            peca = f"«{base.nom_model(info, a['model'])}» en {a['talla']}" if a["model"] else a["epc"]
            out.append({"id": f"pa-{a['id']}", "tipus": "peca_abandonada",
                        "text": f"{a['cabina_nom']}: {peca} fa més de {minuts} min que no torna a la sala.",
                        "botiga_id": a["botiga_id"], "cabina": a["cabina_id"], "creada": a["detectada"],
                        "estat": "oberta", "ref": a["id"]})

    for m in models_mod.taula_models(con, f):
        if m["molt_provat_poc_venut"]:
            out.append({"id": f"mp-{m['model']}", "tipus": "molt_provat_poc_venut",
                        "text": (f"«{m['nom']}»: {m['proves']} proves i {m['compres']} compres "
                                 f"({base.pct_txt(m['conversio'])} de conversió). Revisar preu, exposició o tall."),
                        "botiga_id": f.botiga_id, "cabina": None, "creada": f.fins.isoformat(),
                        "estat": "oberta", "ref": m["model"]})
    out.sort(key=lambda a: a["creada"], reverse=True)
    return {"alertes": out}
