"""Configuració per variables d'entorn (vegeu .env.example).

Tot té un valor per defecte pensat per a desenvolupament local.
En producció (HEBRA_ENTORN=produccio) cal definir HEBRA_SECRET, i canviar com a
mínim HEBRA_CLAU_PASSARELLA i HEBRA_CONTRASENYA_BOTIGA.
"""

import logging
import os
from dataclasses import dataclass, field


def _int(nom: str, defecte: int) -> int:
    return int(os.environ.get(nom, defecte))


def _float(nom: str, defecte: float) -> float:
    return float(os.environ.get(nom, defecte))


@dataclass(frozen=True)
class ReglaProva:
    """Regla que converteix lectures de cabina en una "prova" (Proposta MVP, 3.3).

    Tots els valors són una proposta inicial: es calibren amb 1-2 dies
    d'observació manual a la setmana 0 del pilot.
    """

    durada_minima_s: float = field(default_factory=lambda: _float("HEBRA_PROVA_DURADA_S", 60))
    lectures_minimes: int = field(default_factory=lambda: _int("HEBRA_PROVA_LECTURES", 5))
    # Marge (dB) entre la cabina guanyadora i la veïna per decidir la confiança.
    marge_alta_db: float = field(default_factory=lambda: _float("HEBRA_MARGE_ALTA_DB", 6))
    marge_mitjana_db: float = field(default_factory=lambda: _float("HEBRA_MARGE_MITJANA_DB", 3))
    # Segons sense presència amb la porta oberta que tanquen la sessió.
    tancament_sessio_s: float = field(default_factory=lambda: _float("HEBRA_TANCAMENT_SESSIO_S", 10))


@dataclass(frozen=True)
class Config:
    ruta_bd: str = field(default_factory=lambda: os.environ.get("HEBRA_BD", "hebra.db"))
    clau_passarella: str = field(default_factory=lambda: os.environ.get("HEBRA_CLAU_PASSARELLA", "canvia-aquesta-clau"))
    usuari_botiga: str = field(default_factory=lambda: os.environ.get("HEBRA_USUARI_BOTIGA", "botiga"))
    contrasenya_botiga: str = field(default_factory=lambda: os.environ.get("HEBRA_CONTRASENYA_BOTIGA", "hebra"))
    regla: ReglaProva = field(default_factory=ReglaProva)
    # Cada quants minuts es recalculen proves i atribucions (0 = mai; llavors cal cridar /api/v1/processa).
    processa_cada_min: float = field(default_factory=lambda: _float("HEBRA_PROCESSA_CADA_MIN", 5))
    # 'dev' (per defecte) o 'produccio'. En producció HEBRA_SECRET és obligatori.
    entorn: str = field(default_factory=lambda: os.environ.get("HEBRA_ENTORN", "dev"))
    # Clau per signar la galeta de sessió del tauler (HMAC-SHA256).
    secret: str = field(default_factory=lambda: os.environ.get("HEBRA_SECRET", ""))
    # Galeta només per HTTPS (posa-ho a 1 darrere del proxy amb HTTPS).
    galeta_segura: bool = field(default_factory=lambda: os.environ.get("HEBRA_COOKIE_SECURE", "0") == "1")
    # Dies que es guarden les lectures crues agregades i els esdeveniments de sensors.
    retencio_dies: int = field(default_factory=lambda: _int("HEBRA_RETENCIO_DIES", 90))
    # Carpeta del tauler compilat (frontend/dist). Si no existeix, no se serveix /app.
    frontend_dist: str = field(default_factory=lambda: os.environ.get(
        "HEBRA_FRONTEND_DIST", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")))


SECRET_DEV = "hebra-dev-secret-no-el-facis-servir-en-produccio"


def carrega() -> Config:
    cfg = Config()
    if not cfg.secret:
        if cfg.entorn == "produccio":
            raise RuntimeError("Cal definir HEBRA_SECRET en producció (HEBRA_ENTORN=produccio)")
        logging.getLogger("hebra").warning(
            "HEBRA_SECRET no és definit: fem servir una clau de desenvolupament. No ho facis en producció.")
        cfg = Config(secret=SECRET_DEV)
    return cfg
