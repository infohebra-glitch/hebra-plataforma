"""Sensors de cabina per cable, llegits pels pins GPIO de la Raspberry Pi.

Per cada cabina:
  * Contacte de porta (reed magnètic) entre un pin i GND. Porta tancada = contacte tancat.
  * Radar de presència HLK-LD2410C: la seva sortida OUT (3,3 V) a un pin. Alt = hi ha algú.
    El radar només diu "hi ha algú": sense imatge ni posició. Es configura per cable,
    sense fer servir el seu Bluetooth.

Cada canvi genera un esdeveniment {"cabina", "ts", "tipus"} per a la plataforma.
Fa servir `gpiozero` (ve amb Raspberry Pi OS). Fora d'una Raspberry no s'importa.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

log = logging.getLogger(__name__)


@dataclass
class ConfigCabina:
    cabina: str          # id a la plataforma, p. ex. "BCN-01-C1"
    pin_porta: int       # numeració BCM
    pin_presencia: int
    rebot_s: float = 0.3  # filtre de rebots del contacte


def engega(cabines: list[ConfigCabina], envia: Callable[[dict], None]) -> list:
    """Configura els pins i crida `envia(esdeveniment)` a cada canvi. Retorna els objectes gpiozero."""
    from gpiozero import Button, DigitalInputDevice  # només a la Raspberry

    def emet(cabina: str, tipus: str) -> None:
        envia({"cabina": cabina, "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"), "tipus": tipus})

    objectes = []
    for c in cabines:
        porta = Button(c.pin_porta, pull_up=True, bounce_time=c.rebot_s)
        presencia = DigitalInputDevice(c.pin_presencia, pull_up=False)
        porta.when_pressed = lambda c=c: emet(c.cabina, "porta_tancada")
        porta.when_released = lambda c=c: emet(c.cabina, "porta_oberta")
        presencia.when_activated = lambda c=c: emet(c.cabina, "presencia_si")
        presencia.when_deactivated = lambda c=c: emet(c.cabina, "presencia_no")
        # Estat inicial, perquè la plataforma sàpiga d'on partim.
        emet(c.cabina, "porta_tancada" if porta.is_pressed else "porta_oberta")
        emet(c.cabina, "presencia_si" if presencia.is_active else "presencia_no")
        objectes += [porta, presencia]
        log.info("Cabina %s: porta al GPIO%s, presència al GPIO%s", c.cabina, c.pin_porta, c.pin_presencia)
    return objectes
