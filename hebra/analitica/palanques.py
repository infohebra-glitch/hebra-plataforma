"""Què hi guanya el client: palanques de valor en euros (docs/ESPECIFICACIO.md, «palanques»).

TOTS els euros són ESTIMACIONS (`es_estimacio` sempre true) amb els paràmetres de
la marca, no resultats. Cada palanca porta la fórmula i el detall amb els números.

  * pvp_mitja: import ÷ unitats venudes al període (si no hi ha imports, preu mitjà del catàleg).
  * llindar_peces_mes = quota_mensual ÷ marge_peca, arrodonit amunt: peces de més
    al mes que paguen Hebra.
  * Les palanques mensuals escalen el període a 30 dies.
  * «Més conversió» fa servir la diferència de l'experiment d'origen NOMÉS si és
    estadísticament demostrable (p < 0,05); si no, una hipòtesi de 2 punts
    (paràmetre `punts_conversio_hipotesi`) i el detall ho diu.

Paràmetres opcionals (amb defecte): pct_reposat_a_temps 0,5; pct_compra_reposada
(conversió observada o 0,4); descompte_rebaixa 0,4; descompte_final 0,1;
pct_liquidat 0,6; punts_conversio_hipotesi 0,02.
"""

import math
import sqlite3
from statistics import mean

from . import Filtre, base, inventari as estoc_mod, experimentacio as exp_mod, per_model as models_mod, per_talla as talles_mod


def _p(x: float) -> str:
    return base.pct_txt(x)


def _eur(x: float) -> str:
    return f"{base.num_txt(x, 0)} €"


def valor(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /valor`."""
    b = f.botiga_id
    marge = base.par(con, f, "marge_peca")
    quota = base.par(con, f, "quota_mensual")
    vendes = base.vendes(con, f)
    unitats = sum(v["quantitat"] for v in vendes if v["import_eur"] is not None)
    if unitats:
        pvp = sum(v["import_eur"] for v in vendes if v["import_eur"] is not None) / unitats
    else:
        preus = [r[0] for r in con.execute("SELECT preu_eur FROM catalog_sku WHERE preu_eur IS NOT NULL")]
        pvp = mean(preus) if preus else 0
    pvp = round(pvp)
    mes = 30 / base.dies(f)
    proves = base.proves_valides(con, f)
    conversio = base.frac(sum(p["venuda"] for p in proves), len(proves)) or 0.4
    palanques = []

    # Menys talles esgotades (insight 7), al mes
    perdudes = round(sum(1 for p in base.peticions(con, f) if base.es_perduda(p)) * mes)
    reposat = base.parametre(con, b, "pct_reposat_a_temps", 0.5)
    compra = base.parametre(con, b, "pct_compra_reposada", conversio)
    palanques.append({
        "palanca": "Menys talles esgotades", "insights": [7],
        "formula": "Peticions sense estoc × % reposat a temps × % que compra × marge per peça (al mes)",
        "valor_eur": round(perdudes * reposat * compra * marge, 2),
        "detall": f"{perdudes} × {_p(reposat)} × {_p(compra)} × {_eur(marge)}", "es_estimacio": True})

    # Menys rebaixes (insights 3, 14, 15), per temporada
    taula = models_mod.taula_models(con, f, proves)
    risc = estoc_mod.risc_rebaixa(con, f, taula)
    models_risc = {r["model"] for r in risc}
    detectades = sum(r["unitats"] for r in risc) + sum(
        p["unitats"] for p in estoc_mod.estoc_parat(con, f) if p["model"] not in models_risc)
    evitat = base.parametre(con, b, "descompte_rebaixa", 0.4)
    final = base.parametre(con, b, "descompte_final", 0.1)
    palanques.append({
        "palanca": "Menys rebaixes", "insights": [3, 14, 15],
        "formula": "Unitats detectades a temps × PVP × (descompte evitat − descompte final) (per temporada)",
        "valor_eur": round(detectades * pvp * max(evitat - final, 0), 2),
        "detall": f"{detectades} u. × {_eur(pvp)} × ({_p(evitat)} − {_p(final)})", "es_estimacio": True})

    # Millor recompra (insights 5, 6), per comanda
    estoc = base.estoc_per_gtin(con, b)
    info = base.info_models(con)
    sobrants = 0.0
    for c in talles_mod.talles(con, f)["corba"]:
        total = base.estoc_de(estoc, info.get(c["model"], {}).get("gtins", [])) or 0
        sobrants += sum(max(0.0, t["pct_estoc"] - t["proposta_pct"]) * total
                        for t in c["talles"] if t["pct_estoc"] is not None)
    sobrants = math.floor(sobrants)
    cost = max(pvp - marge, 0)
    liquidat = base.parametre(con, b, "pct_liquidat", 0.6)
    palanques.append({
        "palanca": "Millor recompra", "insights": [5, 6],
        "formula": "Unitats sobrants evitades per talla × cost unitari × % que s'hauria liquidat (per comanda)",
        "valor_eur": round(sobrants * cost * liquidat, 2),
        "detall": f"{sobrants} u. × {_eur(cost)} × {_p(liquidat)}", "es_estimacio": True})

    # Més conversió (insights 2, 17, 18), al mes
    e = exp_mod.efecte_origen(con, f)
    if e and e["p_valor"] is not None and e["p_valor"] < exp_mod.ALFA and e["diferencia"] > 0:
        punts, font = e["diferencia"], f"diferència mesurada a «{e['id']}»"
    else:
        punts = base.parametre(con, b, "punts_conversio_hipotesi", 0.02)
        font = "hipòtesi: cap experiment ho ha demostrat encara"
    proves_mes = round(len(proves) * mes)
    palanques.append({
        "palanca": "Més conversió", "insights": [2, 17, 18],
        "formula": "Punts de conversió guanyats × proves al mes × marge per peça",
        "valor_eur": round(punts * proves_mes * marge, 2),
        "detall": f"{base.num_txt(punts * 100, 1)} punts × {proves_mes} × {_eur(marge)} ({font})",
        "es_estimacio": True})

    palanques.append({
        "palanca": "Disseny", "insights": [8, 22],
        "formula": "Unitats no produïdes d'un tall que no funciona × cost", "valor_eur": None,
        "detall": "Difícil de posar en euros: vegeu el feedback de disseny de l'informe de temporada.",
        "es_estimacio": True})
    palanques.append({
        "palanca": "Compliment a França", "insights": [24],
        "formula": "Hores estalviades a la declaració Refashion × cost per hora", "valor_eur": None,
        "detall": "Preparem les dades (historial de la peça), no fem la declaració.", "es_estimacio": True})

    return {"parametres": {"marge_peca": marge, "quota_mensual": quota, "pvp_mitja": pvp},
            "llindar_peces_mes": math.ceil(quota / marge) if marge else None,
            "palanques": palanques}
