"""Experiments amb grup de control: efecte de l'origen i de qualsevol canvi (insights 17 i 18).

D'on surten els grups:
  * Experiments per dies (`unitat = 'dia'`): cada prova pren el grup del seu dia
    a `assignacio`, buscant primer `assignacio.experiment = experiment.id`. Si no
    hi ha cap fila i l'experiment és de la variable 'origen', es fa servir
    `assignacio.experiment = 'origen'`, que és el que escriuen el motor de proves
    (sessio.grup) i la fitxa NFC (control.mostra_origen).
  * Experiments per models (`unitat = 'model'`): cada prova pren el grup del seu
    model a `assignacio_model`.
  * Compatibilitat: si una botiga té files a `assignacio` amb experiment
    'origen' però cap experiment 'origen' a la taula `experiment`, se'n crea un
    de sintètic («origen-<botiga>») que va del primer al darrer dia assignat.

Càlcul: proves des de l'inici de l'experiment fins a min(fi, Filtre.fins) (el
resultat és acumulat, no només del període del filtre). Prova z de dues
proporcions i IC del 95 % de la diferència (estadistica.py).
`proves_necessaries` és PER GRUP, per detectar la diferència observada amb
potència 0,8 i alfa 0,05. `setmanes_restants` són setmanes de calendari fins a `fi`.
Sense mostra mínima a cada grup, la conclusió ho diu i no en treu res.
"""

import math
import sqlite3
from datetime import date

from . import Filtre, base, estadistica

HIPOTESI_ORIGEN = "Ensenyar l'origen a la fitxa NFC fa que es compri més després de provar."
PROVES_MINIMES = 30
ALFA = 0.05


def definits(con: sqlite3.Connection, botiga_id: str | None) -> list[dict]:
    """Experiments de la taula, més els d'origen sintètics per compatibilitat."""
    exps = [dict(r) for r in con.execute(
        "SELECT * FROM experiment WHERE (:b IS NULL OR botiga_id = :b) ORDER BY inici, id", {"b": botiga_id})]
    amb_origen = {e["botiga_id"] for e in exps if e["variable"] == "origen"}
    for r in con.execute(
            """SELECT botiga_id, MIN(data) AS inici, MAX(data) AS fi FROM assignacio
               WHERE experiment = 'origen' AND (:b IS NULL OR botiga_id = :b)
               GROUP BY botiga_id ORDER BY botiga_id""", {"b": botiga_id}):
        if r["botiga_id"] not in amb_origen:
            exps.append({"id": f"origen-{r['botiga_id']}", "botiga_id": r["botiga_id"], "variable": "origen",
                         "hipotesi": HIPOTESI_ORIGEN, "unitat": "dia", "inici": r["inici"], "fi": r["fi"],
                         "proves_minimes": PROVES_MINIMES, "estat": None})
    return exps


def _grup_de(con: sqlite3.Connection, e: dict):
    """Funció prova -> 'amb' | 'sense' | None per a aquest experiment."""
    if e["unitat"] == "model":
        mapa = dict(con.execute("SELECT model, grup FROM assignacio_model WHERE experiment = ?", (e["id"],)).fetchall())
        return lambda p: mapa.get(p["model"])
    files = con.execute("SELECT data, grup FROM assignacio WHERE botiga_id = ? AND experiment = ?",
                        (e["botiga_id"], e["id"])).fetchall()
    if not files and e["variable"] == "origen":
        files = con.execute("SELECT data, grup FROM assignacio WHERE botiga_id = ? AND experiment = 'origen'",
                            (e["botiga_id"],)).fetchall()
    mapa = {r["data"]: r["grup"] for r in files}
    return lambda p: mapa.get(p["inici"][:10])


def grups(con: sqlite3.Connection, e: dict, des: date, fins: date, model: str | None = None) -> dict:
    """{'amb': {proves, compres, conversio}, 'sense': {...}} entre `des` i `fins` (inclosos)."""
    comptes = {"amb": [0, 0], "sense": [0, 0]}
    if fins >= des:
        grup_de = _grup_de(con, e)
        for p in base.proves_valides(con, Filtre(e["botiga_id"], des, fins)):
            if model and p["model"] != model:
                continue
            g = grup_de(p)
            if g in comptes:
                comptes[g][0] += 1
                comptes[g][1] += p["venuda"]
    return {g: {"proves": n, "compres": c, "conversio": base.frac(c, n)} for g, (n, c) in comptes.items()}


def avalua(con: sqlite3.Connection, e: dict, fins_filtre: date, model: str | None = None) -> dict:
    """Forma `Experiment` de docs/API.md."""
    inici, fi = date.fromisoformat(e["inici"]), date.fromisoformat(e["fi"])
    g = grups(con, e, inici, min(fi, fins_filtre), model)
    a, s = g["amb"], g["sense"]
    diferencia = ic = p = necessaries = None
    if a["proves"] and s["proves"]:
        pa, ps = a["compres"] / a["proves"], s["compres"] / s["proves"]
        diferencia = round(pa - ps, 3)
        ic = [round(x, 3) for x in estadistica.ic95_diferencia(a["compres"], a["proves"], s["compres"], s["proves"])]
        p = round(estadistica.z_dues_proporcions(a["compres"], a["proves"], s["compres"], s["proves"])[1], 3)
        necessaries = estadistica.mostra_necessaria(pa, ps)
    minimes = e["proves_minimes"] or PROVES_MINIMES
    suficient = a["proves"] >= minimes and s["proves"] >= minimes
    estat = e["estat"] or ("tancat" if fi < fins_filtre else "actiu")
    restants = 0 if estat == "tancat" else max(0, math.ceil((fi - fins_filtre).days / 7))
    return {
        "id": e["id"], "variable": e["variable"], "hipotesi": e["hipotesi"], "unitat": e["unitat"],
        "inici": e["inici"], "fi": e["fi"], "estat": estat,
        "grups": g, "diferencia": diferencia, "ic95": ic, "p_valor": p,
        "proves_minimes": minimes, "mostra_suficient": suficient, "proves_necessaries": necessaries,
        "setmanes_restants": restants,
        "conclusio": conclusio(a["proves"], s["proves"], minimes, diferencia, ic, p, restants),
    }


def conclusio(n_amb: int, n_sense: int, minimes: int, diferencia, ic, p, restants: int) -> str:
    falten = (f" {'Falta' if restants == 1 else 'Falten'} {base.plural(restants, 'setmana', 'setmanes')}."
              if restants else "")
    if n_amb < minimes or n_sense < minimes:
        return (f"Mostra insuficient: cal un mínim de {minimes} proves per grup (ara n'hi ha {n_amb} amb "
                f"i {n_sense} sense). Encara no en traiem cap conclusió.{falten}")
    if p is not None and p < ALFA:
        sentit = "més" if diferencia > 0 else "menys"
        return (f"Diferència demostrable: amb el canvi es compra {sentit} després de provar "
                f"({base.punts_txt(diferencia)}; IC del 95 %: {base.punts_txt(ic[0])} a {base.punts_txt(ic[1])}; "
                f"p = {base.p_txt(p)}).")
    if restants:
        return f"Encara no hi ha diferència demostrable (p = {base.p_txt(p)}).{falten}"
    return f"La prova ha acabat sense una diferència demostrable (p = {base.p_txt(p)})."


def experiments(con: sqlite3.Connection, f: Filtre) -> dict:
    """`GET /experiments`: tots els experiments de la botiga (o de totes), avaluats fins a `Filtre.fins`."""
    return {"experiments": [avalua(con, e, f.fins) for e in definits(con, f.botiga_id)]}


def experiment_origen(con: sqlite3.Connection, botiga_id: str | None) -> dict | None:
    """L'experiment d'origen per dies més recent (actiu abans que tancat)."""
    origen = [e for e in definits(con, botiga_id) if e["variable"] == "origen" and e["unitat"] == "dia"]
    if not origen:
        return None
    return sorted(origen, key=lambda e: (e["estat"] == "actiu", e["inici"]))[-1]


def efecte_origen(con: sqlite3.Connection, f: Filtre, model: str | None = None) -> dict | None:
    """Experiment de l'origen avaluat (opcionalment només per a un model), o None si no n'hi ha."""
    e = experiment_origen(con, f.botiga_id)
    return avalua(con, e, f.fins, model) if e else None


def grup_origen_per_dia(con: sqlite3.Connection, f: Filtre) -> dict[str, str | None]:
    """{dia: 'amb' | 'sense'} de l'experiment d'origen; None si les botigues no coincideixen."""
    out: dict[str, str | None] = {}
    for e in definits(con, f.botiga_id):
        if e["variable"] != "origen" or e["unitat"] != "dia":
            continue
        files = con.execute("SELECT data, grup FROM assignacio WHERE botiga_id = ? AND experiment = ?",
                            (e["botiga_id"], e["id"])).fetchall() or con.execute(
            "SELECT data, grup FROM assignacio WHERE botiga_id = ? AND experiment = 'origen'",
            (e["botiga_id"],)).fetchall()
        for r in files:
            if f.inici_iso <= r["data"] < f.fi_exclusiu_iso:
                out[r["data"]] = r["grup"] if out.get(r["data"], r["grup"]) == r["grup"] else None
    return out
