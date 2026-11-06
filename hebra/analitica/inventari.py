"""Estoc: estoc parat, risc de rebaixa i precisió d'estoc de la zona (insights 14, 15, 23).

Estoc parat (14): GTIN amb unitats > 0 i cap prova (de cap confiança) ni cap
  venda en els `dies_estoc_parat` (21) dies que acaben a `Filtre.fins`.
  `dies_sense_activitat` = dies des de l'última prova o venda; si no n'hi ha
  hagut mai, dies des de la primera dada de la botiga (és un mínim).
  Una fila per botiga i GTIN (v0.3), amb `valor_eur` (unitats × PVP), l'última
  prova i venda, l'activitat del mateix GTIN a les ALTRES botigues dins de la
  mateixa finestra, el suggeriment i la tasca pendent (si n'hi ha).

Suggeriment (v0.3, `suggereix`), la primera regla que es compleixi. Llindars a
`parametre` (defectes a base.DEFECTES):
  1. `traspassar`: una altra botiga l'ha provat >= `parat_min_proves_traspas` (3)
     vegades o n'ha venut >= `parat_min_vendes_traspas` (1) u. a la finestra.
     Destí: la que més l'ha mogut (proves + 3 × vendes). Es proposa traspassar-hi
     totes les unitats parades.
  2. `retornar`: fa més de `parat_dies_retornar` (60) dies que està parat i no
     s'ha provat ni venut a cap botiga a la finestra.
  3. `moure_a_sala`: no s'ha provat mai en aquesta botiga (probablement no és visible).
  4. `revisar`: s'ha provat >= `parat_min_proves_conversio` (5) vegades a la
     botiga i la conversió històrica és < `parat_conversio_baixa` (15 %), i el
     motiu més citat no és el preu (talla, tall, qualitat...).
  5. `promocio`: la resta (s'havia provat i ara no es mou, o el motiu és el preu).

Risc de rebaixa (15): models amb cobertura > `setmanes_cobertura` (8) setmanes
  i conversió baixa (la mateixa regla que «molt provat, poc venut», vegeu
  models.py) o sense cap prova. Cobertura = unitats ÷ vendes setmanals del
  període; None si no s'ha venut res (cobertura infinita).

Precisió (23): recomptes manuals contra lectura RFID fins a `Filtre.fins`.
  error_mitja_pct = Σ|manual − rfid| ÷ Σ manual.
"""

import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta

from hebra import tasques

from . import Filtre, base, per_model as models_mod


def _darreres(con: sqlite3.Connection, f: Filtre) -> dict[tuple, dict]:
    """{(botiga, gtin): {"prova": hora, "venda": hora o data}} de l'última prova (de qualsevol confiança)
    i de l'última venda (sense devolucions) abans del final del filtre."""
    p = base.params(f)
    out: dict[tuple, dict] = defaultdict(lambda: {"prova": None, "venda": None})
    for r in con.execute(
            """SELECT c.botiga_id, p.gtin, MAX(s.inici) AS hora
               FROM prova p JOIN sessio s ON s.id = p.sessio_id JOIN cabina c ON c.id = s.cabina_id
               WHERE p.gtin IS NOT NULL AND s.inici < :fins AND (:b IS NULL OR c.botiga_id = :b)
               GROUP BY c.botiga_id, p.gtin""", p):
        out[(r["botiga_id"], r["gtin"])]["prova"] = r["hora"]
    for r in con.execute(
            """SELECT botiga_id, gtin, MAX(COALESCE(ts, data)) AS hora FROM venda_linia
               WHERE quantitat > 0 AND data < :fins AND (:b IS NULL OR botiga_id = :b)
               GROUP BY botiga_id, gtin""", p):
        out[(r["botiga_id"], r["gtin"])]["venda"] = r["hora"]
    return out


def _primera_dada(con: sqlite3.Connection, botiga_id: str) -> date | None:
    r = con.execute(
        """SELECT MIN(d) FROM (
             SELECT MIN(substr(s.inici, 1, 10)) AS d FROM sessio s JOIN cabina c ON c.id = s.cabina_id
             WHERE c.botiga_id = ?
             UNION ALL SELECT MIN(data) FROM venda_linia WHERE botiga_id = ?)""",
        (botiga_id, botiga_id)).fetchone()[0]
    return date.fromisoformat(r) if r else None


def _activitat_finestra(con: sqlite3.Connection, des: date, fins: date) -> dict[str, dict[str, list[int]]]:
    """{gtin: {botiga: [proves vàlides, unitats venudes]}} a TOTES les botigues dins de la finestra."""
    f = Filtre(None, des, fins)
    out: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for p in base.proves_valides(con, f):
        if p["gtin"]:
            out[p["gtin"]][p["botiga_id"]][0] += 1
    for v in base.vendes(con, f):
        out[v["gtin"]][v["botiga_id"]][1] += v["quantitat"]
    return out


def _historic_botiga(con: sqlite3.Connection, f: Filtre) -> dict[tuple, list[int]]:
    """{(botiga, gtin): [proves vàlides, compres atribuïdes]} de tot l'historial fins al final del filtre."""
    out: dict[tuple, list[int]] = {}
    for r in con.execute(
            """SELECT c.botiga_id, p.gtin, COUNT(*) AS n, COUNT(a.venda_id) AS c
               FROM prova p JOIN sessio s ON s.id = p.sessio_id JOIN cabina c ON c.id = s.cabina_id
               LEFT JOIN atribucio a ON a.prova_id = p.id
               WHERE p.gtin IS NOT NULL AND p.confianca IN ('alta', 'mitjana') AND s.inici < :fins
                 AND (:b IS NULL OR c.botiga_id = :b)
               GROUP BY c.botiga_id, p.gtin""", base.params(f)):
        out[(r["botiga_id"], r["gtin"])] = [r["n"], r["c"]]
    return out


def _motiu_principal(con: sqlite3.Connection, f: Filtre) -> dict[tuple, str]:
    """{(botiga, model): motiu de no compra més citat a la fitxa} de tot l'historial."""
    comptes: dict[tuple, Counter] = defaultdict(Counter)
    for r in con.execute(
            """SELECT e.botiga_id, k.model, e.valor FROM esdeveniment_nfc e JOIN catalog_sku k ON k.gtin = e.gtin
               WHERE e.tipus = 'motiu_no_compra' AND e.ts < :fins AND (:b IS NULL OR e.botiga_id = :b)""",
            base.params(f)):
        comptes[(r["botiga_id"], r["model"])][r["valor"]] += 1
    return {k: c.most_common(1)[0][0] for k, c in comptes.items() if c}


def llindars(con: sqlite3.Connection, f: Filtre) -> dict:
    """Llindars dels suggeriments (taula `parametre`, defectes a base.DEFECTES)."""
    return {c: base.par(con, f, c) for c in ("dies_estoc_parat", "parat_min_proves_traspas",
                                              "parat_min_vendes_traspas", "parat_dies_retornar",
                                              "parat_conversio_baixa", "parat_min_proves_conversio")}


def suggereix(unitats: int, dies_parat: int, altres: dict[str, list[int]], proves_hist: int, compres_hist: int,
              motiu: str | None, ll: dict, noms: dict[str, str]) -> dict:
    """Suggeriment per a una variant parada en una botiga (funció pura; regles a l'inici del mòdul).

    `altres` = {botiga: [proves, unitats venudes]} de les ALTRES botigues dins de la finestra.
    """
    finestra = ll["dies_estoc_parat"]
    millor = max(altres.items(), key=lambda kv: (kv[1][0] + 3 * kv[1][1], kv[1][0], kv[0]), default=None)
    if millor and (millor[1][0] >= ll["parat_min_proves_traspas"] or millor[1][1] >= ll["parat_min_vendes_traspas"]):
        desti, (n, v) = millor
        motius = [f"s'ha provat {base.plural(n, 'vegada', 'vegades')}" if n else None,
                  f"se n'han venut {v} u." if v else None]
        return {"accio": "traspassar", "botiga_desti": desti,
                "text": f"Traspassar {base.plural(unitats, 'unitat', 'unitats')} a {noms.get(desti, desti)}: allà "
                        + " i ".join(m for m in motius if m) + f" en {finestra} dies."}
    quiet_enlloc = not any(n or v for n, v in altres.values())
    if dies_parat > ll["parat_dies_retornar"] and quiet_enlloc:
        return {"accio": "retornar", "botiga_desti": None,
                "text": f"Retornar les {unitats} u. al magatzem: fa {dies_parat} dies que no es mou i cap botiga "
                        f"no l'ha provada ni venuda en {finestra} dies."}
    if proves_hist == 0:
        return {"accio": "moure_a_sala", "botiga_desti": None,
                "text": f"Treure-la a la sala: n'hi ha {unitats} u. i no s'ha provat mai en aquesta botiga; "
                        "probablement no és visible."}
    conv = compres_hist / proves_hist
    motiu_txt = base.MOTIUS.get(motiu, motiu).lower() if motiu else None
    if proves_hist >= ll["parat_min_proves_conversio"] and conv < ll["parat_conversio_baixa"] and motiu != "preu":
        return {"accio": "revisar", "botiga_desti": None,
                "text": f"Revisar la peça: s'ha provat {proves_hist} vegades i només s'ha comprat "
                        f"{compres_hist} ({base.pct_txt(conv)})"
                        + (f"; el motiu més citat és «{motiu_txt}»." if motiu_txt else ". Mireu talla i tall.")}
    return {"accio": "promocio", "botiga_desti": None,
            "text": f"Posar-la en promoció o en un lloc més visible: fa {dies_parat} dies que no es mou"
                    + (" i el motiu més citat és el preu." if motiu == "preu"
                       else f" (s'havia provat {proves_hist} vegades).")}


def estoc_parat(con: sqlite3.Connection, f: Filtre) -> list[dict]:
    """Una fila per botiga i GTIN parat, amb el context de les altres botigues, el suggeriment i la tasca."""
    ll = llindars(con, f)
    dies = ll["dies_estoc_parat"]
    inici = f.fins - timedelta(days=dies - 1)
    inici_finestra = inici.isoformat()
    darreres = _darreres(con, f)
    info = base.info_models(con)
    activitat = _activitat_finestra(con, inici, f.fins)
    historic = _historic_botiga(con, f)
    motius = _motiu_principal(con, f)
    noms = {r["id"]: r["nom"] for r in con.execute("SELECT id, nom FROM botiga")}
    pendents = tasques.pendents_per_gtin(con, f.botiga_id)
    primeres: dict[str, date | None] = {}
    out = []
    for e in con.execute(
            """SELECT e.botiga_id, e.gtin, e.unitats, k.model, k.talla, k.color, k.categoria, k.preu_eur
               FROM estoc e LEFT JOIN catalog_sku k ON k.gtin = e.gtin
               WHERE e.unitats > 0 AND (:b IS NULL OR e.botiga_id = :b)
               ORDER BY e.gtin, e.botiga_id""", {"b": f.botiga_id}):
        clau = (e["botiga_id"], e["gtin"])
        d = darreres.get(clau, {"prova": None, "venda": None})
        ultim = max((x[:10] for x in (d["prova"], d["venda"]) if x), default=None)
        if ultim and ultim >= inici_finestra:
            continue
        if ultim:
            sense = (f.fins - date.fromisoformat(ultim)).days
        else:
            if e["botiga_id"] not in primeres:
                primeres[e["botiga_id"]] = _primera_dada(con, e["botiga_id"])
            primera = primeres[e["botiga_id"]]
            sense = (f.fins - primera).days + 1 if primera else dies
        altres = {b: v for b, v in activitat.get(e["gtin"], {}).items() if b != e["botiga_id"]}
        n_hist, c_hist = historic.get(clau, [0, 0])
        out.append({
            "gtin": e["gtin"], "model": e["model"], "nom": base.nom_model(info, e["model"]), "color": e["color"],
            "talla": e["talla"], "categoria": e["categoria"], "botiga_id": e["botiga_id"], "unitats": e["unitats"],
            "valor_eur": round(e["unitats"] * e["preu_eur"], 2) if e["preu_eur"] is not None else None,
            "dies_parat": sense, "dies_sense_activitat": sense,
            "darrera_prova": d["prova"], "darrera_venda": d["venda"],
            "proves_altres_botigues": sum(n for n, _ in altres.values()),
            "vendes_altres_botigues": sum(v for _, v in altres.values()),
            "suggeriment": suggereix(e["unitats"], sense, altres, n_hist, c_hist,
                                     motius.get((e["botiga_id"], e["model"])), ll, noms),
            "tasca": pendents.get(clau),
        })
    return sorted(out, key=lambda r: (-r["dies_parat"], -r["unitats"], r["gtin"], r["botiga_id"]))


def resum_parat(parat: list[dict]) -> dict:
    """Totals de l'estoc parat i repartiment per categoria (de més a menys valor)."""
    per: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
    for p in parat:
        c = per[p["categoria"] or "sense catàleg"]
        c[0] += p["unitats"]
        c[1] += p["valor_eur"] or 0
    return {"unitats": sum(p["unitats"] for p in parat),
            "valor_eur": round(sum(p["valor_eur"] or 0 for p in parat), 2),
            "per_categoria": [{"categoria": c, "unitats": u, "valor_eur": round(v, 2)}
                              for c, (u, v) in sorted(per.items(), key=lambda kv: (-kv[1][1], kv[0]))]}


def risc_rebaixa(con: sqlite3.Connection, f: Filtre, taula: list[dict] | None = None) -> list[dict]:
    taula = models_mod.taula_models(con, f) if taula is None else taula
    limit = base.par(con, f, "setmanes_cobertura")
    info = base.info_models(con)
    estoc = base.estoc_per_gtin(con, f.botiga_id)
    venudes: dict[str, int] = defaultdict(int)
    for v in base.vendes(con, f):
        if v["model"]:
            venudes[v["model"]] += v["quantitat"]
    per_model = {r["model"]: r for r in taula}
    out = []
    for model, i in info.items():
        unitats = base.estoc_de(estoc, i["gtins"])
        if not unitats or unitats <= 0:
            continue
        r = per_model.get(model, {"proves": 0, "conversio": None, "quartil_categoria": None, "conversio_baixa": False})
        setmanals = venudes[model] / base.setmanes(f)
        cobertura = round(unitats / setmanals, 1) if setmanals else None
        if (cobertura is None or cobertura > limit) and (r["conversio_baixa"] or r["proves"] == 0):
            out.append({"model": model, "nom": i["nom"], "unitats": unitats, "cobertura_setmanes": cobertura,
                        "conversio": r["conversio"], "quartil_categoria": r["quartil_categoria"]})
    return sorted(out, key=lambda r: -r["unitats"])


def precisio(con: sqlite3.Connection, f: Filtre) -> dict | None:
    files = con.execute(
        "SELECT manual, rfid FROM recompte_estoc WHERE data < :fins AND (:b IS NULL OR botiga_id = :b)",
        base.params(f)).fetchall()
    if not files:
        return None
    manual = sum(r["manual"] for r in files)
    return {"recomptes": len(files),
            "error_mitja_pct": base.frac(sum(abs(r["manual"] - r["rfid"]) for r in files), manual)}


def estoc(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /estoc`."""
    parat = estoc_parat(con, f)
    return {"parat": parat, "resum_parat": resum_parat(parat), "risc_rebaixa": risc_rebaixa(con, f),
            "precisio": precisio(con, f)}
