"""Tasques de botiga (docs/ESPECIFICACIO-v3.md, D.1).

Una tasca és una cosa concreta que algú de la botiga ha de fer: traspassar unitats
a una altra botiga, treure una peça del magatzem a la sala, fer un recompte...
Moltes neixen d'un suggeriment de l'estoc parat (`analitica.inventari`).

Cada creació o canvi d'estat es publica al bus d'alertes (`alertes.notifica_tasca`)
perquè la web del dependent s'actualitzi sola.
"""

import sqlite3

from . import alertes, temps

TIPUS = ("traspassar", "moure_a_sala", "promocio", "retornar", "revisar", "recompte", "altre")
ESTATS = ("pendent", "feta", "descartada")
CAMPS = ("id", "botiga_id", "tipus", "titol", "detall", "gtin", "unitats", "botiga_desti", "estat", "creada", "feta")

_VERBS = {"traspassar": "Traspassar", "moure_a_sala": "Treure a la sala", "promocio": "Posar en promoció",
          "retornar": "Retornar al magatzem central", "revisar": "Revisar", "recompte": "Fer recompte de",
          "altre": "Revisar"}


def tasca_json(fila: sqlite3.Row | dict | None) -> dict | None:
    """Forma `Tasca` de l'especificació."""
    return {c: fila[c] for c in CAMPS} if fila else None


def tasca(con: sqlite3.Connection, tid: int) -> dict | None:
    return tasca_json(con.execute("SELECT * FROM tasca WHERE id = ?", (tid,)).fetchone())


def titol_per_defecte(con: sqlite3.Connection, tipus: str, gtin: str | None, unitats: int | None,
                      botiga_desti: str | None) -> str:
    """«Traspassar 2 u. de Faldilla de llana (S) a Girona»: per quan la tasca arriba sense títol."""
    peca = ""
    if gtin:
        k = con.execute("SELECT model, talla, origen_json FROM catalog_sku WHERE gtin = ?", (gtin,)).fetchone()
        if k:
            peca = f"{alertes._nom_model(k['origen_json'], k['model'])} ({k['talla']})"
        else:
            peca = gtin
    text = _VERBS[tipus]
    if peca:
        text += f" {unitats} u. de {peca}" if unitats and tipus in ("traspassar", "retornar") else f" {peca}"
    if botiga_desti:
        b = con.execute("SELECT nom FROM botiga WHERE id = ?", (botiga_desti,)).fetchone()
        text += f" a {b['nom'] if b else botiga_desti}"
    return text


def pendent_igual(con: sqlite3.Connection, botiga_id: str, tipus: str, gtin: str | None) -> dict | None:
    """Tasca pendent amb la mateixa botiga, tipus i GTIN (per no duplicar-ne en crear-les en bloc)."""
    if not gtin:
        return None
    return tasca_json(con.execute(
        """SELECT * FROM tasca WHERE botiga_id = ? AND tipus = ? AND gtin = ? AND estat = 'pendent'
           ORDER BY id DESC LIMIT 1""", (botiga_id, tipus, gtin)).fetchone())


def crea(con: sqlite3.Connection, botiga_id: str, tipus: str, titol: str | None = None, detall: str = "",
         gtin: str | None = None, unitats: int | None = None, botiga_desti: str | None = None,
         creada_per: int | None = None, ts: str | None = None, notifica: bool = True) -> tuple[dict, bool]:
    """Crea una tasca pendent. Retorna (Tasca, nova). Si ja n'hi ha una de pendent igual, la retorna (nova=False).

    Les validacions de dades (botigues i GTIN existents) les fa qui crida (l'API respon 400).
    """
    if tipus not in TIPUS:
        raise ValueError(f"Tipus de tasca desconegut: {tipus}")
    existent = pendent_igual(con, botiga_id, tipus, gtin)
    if existent:
        return existent, False
    titol = (titol or "").strip() or titol_per_defecte(con, tipus, gtin, unitats, botiga_desti)
    tid = con.execute(
        """INSERT INTO tasca (botiga_id, tipus, titol, detall, gtin, unitats, botiga_desti, estat, creada, creada_per)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pendent', ?, ?)""",
        (botiga_id, tipus, titol[:200], detall or "", gtin, unitats, botiga_desti, ts or temps.ara(),
         creada_per)).lastrowid
    con.commit()
    t = tasca(con, tid)
    if notifica:
        alertes.notifica_tasca(t, nova=True)
    return t, True


def canvia_estat(con: sqlite3.Connection, tid: int, estat: str, usuari_id: int | None = None,
                 ts: str | None = None, notifica: bool = True) -> dict | None:
    """Marca la tasca com a feta o descartada (o la torna a pendent). None si no existeix."""
    if estat not in ESTATS:
        raise ValueError(f"Estat de tasca desconegut: {estat}")
    actual = tasca(con, tid)
    if actual is None:
        return None
    if actual["estat"] == estat:
        return actual
    if estat == "pendent":
        con.execute("UPDATE tasca SET estat = 'pendent', feta = NULL, feta_per = NULL WHERE id = ?", (tid,))
    else:
        con.execute("UPDATE tasca SET estat = ?, feta = ?, feta_per = ? WHERE id = ?",
                    (estat, ts or temps.ara(), usuari_id, tid))
    con.commit()
    t = tasca(con, tid)
    if notifica:
        alertes.notifica_tasca(t, nova=False)
    return t


def llista(con: sqlite3.Connection, botiga_id: str | None = None, estat: str | None = None,
           limit: int = 500) -> list[dict]:
    """Pendents primer; dins de cada grup, les més noves primer."""
    files = con.execute(
        """SELECT * FROM tasca WHERE (:b IS NULL OR botiga_id = :b) AND (:e IS NULL OR estat = :e)
           ORDER BY estat = 'pendent' DESC, creada DESC, id DESC LIMIT :n""",
        {"b": botiga_id, "e": estat, "n": limit}).fetchall()
    return [tasca_json(f) for f in files]


def pendents_per_gtin(con: sqlite3.Connection, botiga_id: str | None) -> dict[tuple[str, str], dict]:
    """{(botiga_id, gtin): la tasca pendent més nova} per enllaçar-les amb l'estoc parat."""
    out: dict[tuple[str, str], dict] = {}
    for f in con.execute("""SELECT * FROM tasca WHERE estat = 'pendent' AND gtin IS NOT NULL
                            AND (:b IS NULL OR botiga_id = :b) ORDER BY id""", {"b": botiga_id}):
        out[(f["botiga_id"], f["gtin"])] = tasca_json(f)
    return out
