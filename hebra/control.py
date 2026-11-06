"""Grup de control (Proposta MVP, secció 3.5).

Amb l'NFC, la funció que provem (al MVP: ensenyar l'origen a la fitxa) s'encén
o s'apaga per a TOTA la botiga un dia sencer. Cada dia es sorteja si és 'amb'
o 'sense', equilibrant per dia de la setmana: per a cada dia de la setmana, la
meitat de les setmanes és 'amb' i l'altra meitat 'sense'.

El sorteig és reproduïble (llavor fixa) perquè es pugui auditar a l'informe final.
"""

import random
import sqlite3
from datetime import date, timedelta

GRUPS = ("amb", "sense")


def sorteja(botiga_id: str, experiment: str, inici: date, setmanes: int, llavor: int = 2026) -> dict[str, str]:
    """Retorna {data ISO: grup} per a `setmanes` setmanes a partir d'`inici`.

    Per a cada dia de la setmana (dl, dt...) es fa una llista amb tants 'amb'
    com 'sense' (si el nombre de setmanes és senar, n'hi ha un de més a l'atzar)
    i es barreja.
    """
    rng = random.Random(f"{llavor}:{botiga_id}:{experiment}:{inici.isoformat()}")
    per_dia_setmana: dict[int, list[str]] = {}
    for dia in range(7):
        llista = ["amb", "sense"] * (setmanes // 2)
        if setmanes % 2:
            llista.append(rng.choice(GRUPS))
        rng.shuffle(llista)
        per_dia_setmana[dia] = llista

    resultat = {}
    for i in range(setmanes * 7):
        d = inici + timedelta(days=i)
        resultat[d.isoformat()] = per_dia_setmana[d.weekday()][i // 7]
    return resultat


def desa_assignacio(con: sqlite3.Connection, botiga_id: str, experiment: str, assignacio: dict[str, str]) -> None:
    con.executemany(
        """INSERT INTO assignacio (botiga_id, experiment, data, grup) VALUES (?, ?, ?, ?)
           ON CONFLICT(botiga_id, experiment, data) DO UPDATE SET grup = excluded.grup""",
        [(botiga_id, experiment, d, g) for d, g in assignacio.items()],
    )
    con.commit()


def grup_del_dia(con: sqlite3.Connection, botiga_id: str, experiment: str, dia: str) -> str | None:
    """Grup del dia, o None si l'experiment no està actiu aquell dia (mesura base)."""
    fila = con.execute(
        "SELECT grup FROM assignacio WHERE botiga_id = ? AND experiment = ? AND data = ?",
        (botiga_id, experiment, dia),
    ).fetchone()
    return fila["grup"] if fila else None


def mostra_origen(con: sqlite3.Connection, botiga_id: str | None, dia: str) -> bool:
    """La fitxa NFC ensenya l'origen? Sense experiment actiu, sí (comportament normal)."""
    if not botiga_id:
        return True
    return grup_del_dia(con, botiga_id, "origen", dia) != "sense"
