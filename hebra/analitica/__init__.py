"""Analítica de Hebra: els 25 insights i els 7 informes (vegeu docs/ESPECIFICACIO.md i docs/API.md).

Cada funció pública rep una connexió i un `Filtre` i retorna un diccionari
JSON-serialitzable amb EXACTAMENT la forma descrita a docs/API.md. L'API
(hebra/api/) només les crida; el tauler (frontend/) només les pinta.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Filtre:
    botiga_id: str | None   # None = totes les botigues que l'usuari pot veure
    des: date               # inclòs
    fins: date              # inclòs

    @property
    def inici_iso(self) -> str:
        return self.des.isoformat()

    @property
    def fi_exclusiu_iso(self) -> str:
        from datetime import timedelta
        return (self.fins + timedelta(days=1)).isoformat()
