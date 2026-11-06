"""Descodificació d'EPC SGTIN (estàndard GS1 TDS) a GTIN-14 i número de sèrie.

Accepta dues formes:
  * URN pura:  urn:epc:id:sgtin:8400000.012345.100001
  * Hex SGTIN-96, com el llegeix el lector: 3034257BF7194E4000000001

Si les etiquetes d'una marca no són SGTIN, cal una taula EPC -> GTIN
(taula `etiqueta`) i aquest mòdul no s'utilitza.
"""

from dataclasses import dataclass

# Partició SGTIN-96: (bits empresa, dígits empresa, bits referència, dígits referència)
_PARTICIONS = {
    0: (40, 12, 4, 1),
    1: (37, 11, 7, 2),
    2: (34, 10, 10, 3),
    3: (30, 9, 14, 4),
    4: (27, 8, 17, 5),
    5: (24, 7, 20, 6),
    6: (20, 6, 24, 7),
}


@dataclass(frozen=True)
class Sgtin:
    prefix_empresa: str
    referencia: str  # inclou el dígit indicador al davant
    serie: str

    @property
    def gtin(self) -> str:
        cos = self.referencia[0] + self.prefix_empresa + self.referencia[1:]
        return cos + digit_control(cos)

    @property
    def urn(self) -> str:
        return f"urn:epc:id:sgtin:{self.prefix_empresa}.{self.referencia}.{self.serie}"


def digit_control(cos13: str) -> str:
    """Dígit de control GS1 (mòdul 10) per a un GTIN de 13 dígits sense control."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(cos13)))
    return str((10 - total % 10) % 10)


def descodifica(epc: str) -> Sgtin:
    epc = epc.strip()
    if epc.lower().startswith("urn:epc:id:sgtin:"):
        empresa, referencia, serie = epc.split(":")[-1].split(".")
        return Sgtin(empresa, referencia, serie)
    return _descodifica_hex(epc)


def _descodifica_hex(hex_epc: str) -> Sgtin:
    valor = int(hex_epc, 16)
    if len(hex_epc) != 24 or (valor >> 88) != 0x30:
        raise ValueError(f"No és un SGTIN-96: {hex_epc}")
    particio = (valor >> 82) & 0b111
    if particio not in _PARTICIONS:
        raise ValueError(f"Partició SGTIN no vàlida: {particio}")
    bits_e, digits_e, bits_r, digits_r = _PARTICIONS[particio]
    serie = valor & ((1 << 38) - 1)
    referencia = (valor >> 38) & ((1 << bits_r) - 1)
    empresa = (valor >> (38 + bits_r)) & ((1 << bits_e) - 1)
    return Sgtin(str(empresa).zfill(digits_e), str(referencia).zfill(digits_r), str(serie))


def normalitza(epc: str) -> str:
    """Retorna l'EPC en forma URN; si no és SGTIN, el retorna tal qual en majúscules."""
    try:
        return descodifica(epc).urn
    except ValueError:
        return epc.strip().upper()
