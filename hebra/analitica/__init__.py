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


# Les funcions públiques (una per ruta de docs/API.md). S'importen després de
# definir `Filtre` perquè els submòduls el fan servir.
from .temps_real import alertes  # noqa: E402
from .base import parametre  # noqa: E402
from .inventari import estoc  # noqa: E402
from .experimentacio import experiments  # noqa: E402
from .informes import informe  # noqa: E402
from .per_model import model_detall, models  # noqa: E402
from .nfc import fitxa_nfc, motius  # noqa: E402
from .peces import historial_peca, perdues  # noqa: E402
from .tauler import resum  # noqa: E402
from .cabina import servei  # noqa: E402
from .per_talla import demanda_perduda, talles  # noqa: E402
from .palanques import valor  # noqa: E402
from .sistema import estat_sistema  # noqa: E402
from .sessions import sessions  # noqa: E402  (v0.3, C)

__all__ = [
    "Filtre", "parametre",
    "resum", "models", "model_detall", "talles", "demanda_perduda", "motius", "servei", "estoc",
    "fitxa_nfc", "experiments", "alertes", "valor", "informe", "historial_peca", "perdues", "estat_sistema",
    "sessions",
]
