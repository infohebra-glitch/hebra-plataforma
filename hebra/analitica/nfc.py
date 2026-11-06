"""Fitxa NFC: motius de no compra, ús de la fitxa i idiomes (insights 8, 16, 21).

Motius (insight 8): sempre amb la taxa de resposta, perquè qui respon no és tothom.
  taxa_resposta = respostes ÷ sessions de fitxa (sessions NFC diferents que l'han oberta).

Ús de la fitxa (insight 16): tocs = esdeveniments `obre_fitxa`; per secció:
  origen        <- `veu_origen`
  talles, cura, preguntes <- `veu_seccio` amb aquest `valor`
  motiu         <- `motiu_no_compra`
  peticio_talla <- `demana_talla`
  El % de cada secció és sobre els tocs. Idioma (insight 21): idioma dels tocs.
"""

import sqlite3
from collections import Counter, defaultdict

from . import Filtre, base

SECCIONS = ("origen", "talles", "cura", "preguntes", "motiu", "peticio_talla")
_TIPUS_SECCIO = {"veu_origen": "origen", "motiu_no_compra": "motiu", "demana_talla": "peticio_talla"}


def motius(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /motius`: respostes per motiu i per model, amb la taxa de resposta."""
    info = base.info_models(con)
    respostes = base.nfc(con, f, "motiu_no_compra")
    sessions_fitxa = len({e["sessio_nfc"] for e in base.nfc(con, f, "obre_fitxa")})
    per_motiu = Counter(e["valor"] for e in respostes)
    per_model: dict[str, Counter] = defaultdict(Counter)
    for e in respostes:
        per_model[e["model"] or e["gtin"]][e["valor"]] += 1
    n = len(respostes)
    return {
        "respostes": n, "sessions_fitxa": sessions_fitxa, "taxa_resposta": base.frac(n, sessions_fitxa),
        "per_motiu": [{"motiu": m, "n": k, "pct": base.frac(k, n)} for m, k in per_motiu.most_common()],
        "per_model": [{"model": m, "nom": base.nom_model(info, m), "respostes": sum(c.values()), "motius": dict(c)}
                      for m, c in sorted(per_model.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))],
    }


def fitxa_nfc(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /fitxa-nfc`: tocs per sessió de cabina, seccions vistes i idiomes."""
    events = base.nfc(con, f)
    tocs = [e for e in events if e["tipus"] == "obre_fitxa"]
    n_sessions = len(base.sessions(con, f))
    seccions: Counter = Counter()
    for e in events:
        if e["tipus"] in _TIPUS_SECCIO:
            seccions[_TIPUS_SECCIO[e["tipus"]]] += 1
        elif e["tipus"] == "veu_seccio" and e["valor"] in SECCIONS:
            seccions[e["valor"]] += 1
    idiomes = Counter(e["idioma"] for e in tocs)
    n = len(tocs)
    return {
        "tocs": n, "sessions_cabina": n_sessions, "tocs_per_sessio": base.frac(n, n_sessions, 2),
        "seccions": [{"seccio": s, "n": seccions[s], "pct": base.frac(seccions[s], n)} for s in SECCIONS],
        "idiomes": [{"idioma": i, "n": k, "pct": base.frac(k, n)} for i, k in idiomes.most_common()],
    }
