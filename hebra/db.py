"""Accés a la base de dades.

Fem servir sqlite3 de la llibreria estàndard i SQL escrit a mà: és el més fàcil
de llegir i revisar. Totes les consultes fan servir paràmetres (?) per evitar
injecció SQL. Per passar a PostgreSQL caldria canviar aquest mòdul (connexió i
marcador de paràmetres) i el tipus AUTOINCREMENT de schema.sql.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ESQUEMA = Path(__file__).with_name("schema.sql")


def connecta(ruta: str) -> sqlite3.Connection:
    con = sqlite3.connect(ruta, check_same_thread=False, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    # WAL: la web pot llegir mentre el càlcul periòdic de proves escriu.
    con.execute("PRAGMA journal_mode = WAL")
    return con


def inicialitza(con: sqlite3.Connection) -> None:
    """Crea les taules si no existeixen (idempotent)."""
    con.executescript(ESQUEMA.read_text(encoding="utf-8"))
    con.commit()


@contextmanager
def transaccio(con: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
