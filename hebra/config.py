"""Configuració per variables d'entorn (vegeu .env.example).

Tot té un valor per defecte pensat per a desenvolupament local.
En producció (HEBRA_ENTORN=produccio) la plataforma no arrenca amb valors
d'exemple: calen HEBRA_SECRET i HEBRA_CLAU_PASSARELLA aleatoris i HEBRA_COOKIE_SECURE=1
(vegeu `problemes_produccio`). Les pàgines antigues /botiga/* queden desactivades
si no se'ls posa una contrasenya pròpia.
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
    # Correu per enviar els informes a l'equip de la marca (hebra/correu.py). Sense host, no s'envia res.
    smtp_host: str = field(default_factory=lambda: os.environ.get("HEBRA_SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: _int("HEBRA_SMTP_PORT", 587))
    smtp_usuari: str = field(default_factory=lambda: os.environ.get("HEBRA_SMTP_USUARI", ""))
    smtp_contrasenya: str = field(default_factory=lambda: os.environ.get("HEBRA_SMTP_CONTRASENYA", ""))
    smtp_remitent: str = field(default_factory=lambda: os.environ.get("HEBRA_SMTP_REMITENT", ""))
    # Mode de proves: si té una adreça, TOTS els correus van només aquí (l'assumpte diu a qui anaven).
    # Per enviar als destinataris de veritat, deixeu-la buida (desplegament/configura-correu.sh).
    correu_redirigeix: str = field(default_factory=lambda: os.environ.get("HEBRA_CORREU_REDIRIGEIX", "").strip())

    @property
    def produccio(self) -> bool:
        return self.entorn == "produccio"

    @property
    def botiga_antiga_activa(self) -> bool:
        """Les pàgines antigues /botiga/* (usuari bàsic compartit): en producció, només amb contrasenya pròpia."""
        return not self.produccio or self.contrasenya_botiga not in CONTRASENYES_BOTIGA_DEV


SECRET_DEV = "hebra-dev-secret-no-el-facis-servir-en-produccio"
CLAU_PASSARELLA_DEV = "canvia-aquesta-clau"
CONTRASENYES_BOTIGA_DEV = ("hebra", "canvia-aquesta-contrasenya", "")


def problemes_produccio(cfg: Config) -> list[str]:
    """Què impedeix arrencar en producció: valors d'exemple o massa febles."""
    p = []
    if len(cfg.secret) < 32 or cfg.secret.startswith("canvia") or cfg.secret == SECRET_DEV:
        p.append("HEBRA_SECRET ha de ser una clau aleatòria de 32 caràcters o més")
    if len(cfg.clau_passarella) < 24 or cfg.clau_passarella.startswith("canvia"):
        p.append("HEBRA_CLAU_PASSARELLA ha de ser una clau aleatòria de 24 caràcters o més")
    # Les pàgines antigues /botiga/* només s'activen si se'ls posa una contrasenya pròpia.
    if cfg.contrasenya_botiga not in CONTRASENYES_BOTIGA_DEV and len(cfg.contrasenya_botiga) < 12:
        p.append("HEBRA_CONTRASENYA_BOTIGA ha de tenir 12 caràcters o més (o deixa-la buida per desactivar /botiga)")
    if not cfg.galeta_segura:
        p.append("HEBRA_COOKIE_SECURE ha de ser 1 (la plataforma només s'ha de servir per HTTPS)")
    return p


def carrega() -> Config:
    cfg = Config()
    if cfg.entorn == "produccio":
        problemes = problemes_produccio(cfg)
        if problemes:
            raise RuntimeError("Configuració no segura per a producció (HEBRA_ENTORN=produccio):\n  - "
                               + "\n  - ".join(problemes)
                               + "\nGenera claus amb: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")
    if not cfg.secret:
        logging.getLogger("hebra").warning(
            "HEBRA_SECRET no és definit: fem servir una clau de desenvolupament. No ho facis en producció.")
        cfg = Config(secret=SECRET_DEV)
    return cfg
