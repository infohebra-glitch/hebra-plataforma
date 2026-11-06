"""Retenció de dades: esborra les dades crues passats N dies (HEBRA_RETENCIO_DIES, 90 per defecte).

Només s'esborren `lectura_agregada` (lectures UHF agregades) i `sensor_event`
(porta i presència). Les sessions, proves, atribucions i peces abandonades que
se n'han calculat es mantenen: el motor de proves només recalcula a partir del
primer esdeveniment que encara es conserva (vegeu hebra/proves.py).

L'aplicació l'executa un cop al dia (hebra/app.py).
"""

import sqlite3
from datetime import date, timedelta

from . import temps


def neteja(con: sqlite3.Connection, dies: int, avui: date | None = None) -> dict[str, int]:
    """Esborra les files de dies anteriors a avui − `dies`. Retorna quantes n'ha esborrat per taula."""
    if dies <= 0:
        return {"lectura_agregada": 0, "sensor_event": 0}
    avui = avui or date.fromisoformat(temps.ara()[:10])
    limit = (avui - timedelta(days=dies)).isoformat()
    # Comparem el dia (els 10 primers caràcters) perquè les hores poden tenir desplaçaments diferents (hivern/estiu).
    n_lectures = con.execute("DELETE FROM lectura_agregada WHERE substr(fi, 1, 10) < ?", (limit,)).rowcount
    n_sensors = con.execute("DELETE FROM sensor_event WHERE substr(ts, 1, 10) < ?", (limit,)).rowcount
    con.commit()
    return {"lectura_agregada": n_lectures, "sensor_event": n_sensors}
