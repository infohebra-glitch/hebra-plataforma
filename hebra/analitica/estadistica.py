"""Estadística mínima per als experiments (insights 17 i 18), només amb la llibreria estàndard.

  * Prova z de dues proporcions (bilateral, amb la proporció conjunta), com
    `prop.test(correct = FALSE)` d'R.
  * Interval de confiança del 95 % de la diferència (Wald, sense conjunta).
  * Interval de Wilson per a una proporció.
  * Mida de mostra per grup per detectar p1 contra p2 amb alfa 0,05 i potència 0,8
    (fórmula de Fleiss sense correcció de continuïtat, com `power.prop.test`).
"""

import math
from statistics import NormalDist

_N = NormalDist()
Z95 = _N.inv_cdf(0.975)   # 1,959964...


def z_dues_proporcions(x1: int, n1: int, x2: int, n2: int) -> tuple[float, float]:
    """Retorna (z, p-valor bilateral) per a H0: p1 = p2. Sense variància (0 % o 100 % als dos), (0, 1)."""
    if not n1 or not n2:
        raise ValueError("cada grup ha de tenir com a mínim una prova")
    conjunta = (x1 + x2) / (n1 + n2)
    se = math.sqrt(conjunta * (1 - conjunta) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (x1 / n1 - x2 / n2) / se
    return z, math.erfc(abs(z) / math.sqrt(2))


def ic95_diferencia(x1: int, n1: int, x2: int, n2: int, z: float = Z95) -> tuple[float, float]:
    """Interval de confiança (Wald) de p1 - p2."""
    p1, p2 = x1 / n1, x2 / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    d = p1 - p2
    return d - z * se, d + z * se


def wilson(x: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """Interval de Wilson del 95 % per a una proporció x/n (millor que Wald amb mostres petites)."""
    if not n:
        return None
    p = x / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    marge = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - marge), min(1.0, centre + marge)


def mostra_necessaria(p1: float, p2: float, alfa: float = 0.05, potencia: float = 0.8) -> int | None:
    """Proves necessàries PER GRUP per detectar p1 contra p2. None si no hi ha diferència."""
    if p1 is None or p2 is None or p1 == p2:
        return None
    za = _N.inv_cdf(1 - alfa / 2)
    zb = _N.inv_cdf(potencia)
    pm = (p1 + p2) / 2
    num = za * math.sqrt(2 * pm * (1 - pm)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return math.ceil(num * num / (p1 - p2) ** 2)
