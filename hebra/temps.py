"""Hores: tot es desa en hora local de la botiga (ISO 8601 amb desplaçament).

Així el "dia" d'una prova o d'una venda és el dia de la botiga, que és el que
compta per a l'atribució i el grup de control. Les comparacions de text entre
dates ISO funcionen perquè totes porten el mateix format.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

ZONA_PER_DEFECTE = "Europe/Madrid"


def local(text: str, zona: str = ZONA_PER_DEFECTE) -> str:
    """Normalitza una hora ISO a hora local de la botiga. Sense zona, s'assumeix local."""
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    tz = ZoneInfo(zona)
    dt = dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)
    return dt.isoformat(timespec="seconds")


def ara(zona: str = ZONA_PER_DEFECTE) -> str:
    return datetime.now(ZoneInfo(zona)).isoformat(timespec="seconds")
