"""Informe setmanal «provat, venut, convertit» (Proposta MVP, secció 5.2 C) per a la plantilla HTML.

Des de la v0.2 els càlculs són a `hebra.analitica` (els mateixos que fa servir el
tauler); aquí només es reorganitzen amb la forma que espera informe.html.
Regles que l'informe declara sempre:
  * només compten les proves de confiança alta i mitjana;
  * l'efecte de l'origen només es dona com a resultat si cada grup té una mostra
    mínima; si no, es diu "mostra insuficient" (no prometem percentatges);
  * "venut sense provar" són unitats venudes que no s'han aparellat amb cap prova.
"""

import sqlite3
from datetime import date, timedelta

from .analitica import Filtre, base
from .analitica import experimentacio, nfc, per_model, per_talla, tauler

PROVES_MINIMES_PER_GRUP = experimentacio.PROVES_MINIMES
MOTIUS = base.MOTIUS


def setmanal(con: sqlite3.Connection, botiga_id: str, dilluns: date) -> dict:
    f = Filtre(botiga_id, dilluns, dilluns + timedelta(days=6))
    proves = base.proves_valides(con, f)
    k = tauler.kpi(con, f, proves)

    models = [{"model": m["model"], "nom": m["nom"], "proves": m["proves"], "compres": m["compres"],
               "conversio": m["conversio"], "alerta": m["molt_provat_poc_venut"]}
              for m in per_model.taula_models(con, f, proves) if m["proves"]]

    # Efecte de l'origen NOMÉS d'aquesta setmana (el tauler el dona acumulat).
    e = experimentacio.experiment_origen(con, botiga_id)
    grups = (experimentacio.grups(con, e, f.des, f.fins) if e else
             {g: {"proves": 0, "compres": 0, "conversio": None} for g in ("amb", "sense")})
    minim = (e or {}).get("proves_minimes") or PROVES_MINIMES_PER_GRUP
    hi_ha_mostra = all(grups[g]["proves"] >= minim for g in grups)
    diferencia = base.resta(grups["amb"]["conversio"], grups["sense"]["conversio"]) if hi_ha_mostra else None

    perduda = per_talla.demanda_perduda(con, f)["per_variant"]
    motius = nfc.motius(con, f)["per_motiu"]
    peticions = base.peticions(con, f)
    segons = [s for s in (base.segons_resposta(p) for p in peticions) if s is not None]
    accio = tauler.accio_principal(con, f)

    return {
        "botiga_id": botiga_id,
        "inici": f.inici_iso,
        "fi": f.fins.isoformat(),
        "totals": {
            "proves": k["proves"],
            "ambigues": k["proves_ambigues"],
            "compres_atribuides": k["compres_atribuides"],
            "conversio": k["conversio"],
            "unitats_venudes": k["unitats_venudes"],
            "venut_sense_provar": k["venut_sense_provar"],
        },
        "per_categoria_talla": per_talla.taula_categoria_talla(proves),
        "models": models,
        "origen": {"grups": grups, "hi_ha_mostra": hi_ha_mostra, "diferencia": diferencia, "minim": minim},
        "demanda_perduda": [{"model": v["model"], "color": v["color"], "talla_demanada": v["talla"], "n": v["n"]}
                            for v in perduda],
        "motius": [{"motiu": MOTIUS.get(m["motiu"], m["motiu"]), "n": m["n"]} for m in motius],
        "peticions": {"n": len(peticions), "segons_mitjans": round(sum(segons) / len(segons)) if segons else None},
        "accio": accio["text"] if accio else None,
    }
