"""Estadística dels experiments contra valors coneguts (R: prop.test, power.prop.test, binom Wilson)."""

import math

import pytest

from hebra.analitica import estadistica as e


def test_z_dues_proporcions_com_prop_test():
    # prop.test(c(45, 30), c(100, 100), correct = FALSE): X-squared = 4.8, p-value = 0.02846
    z, p = e.z_dues_proporcions(45, 100, 30, 100)
    assert z == pytest.approx(math.sqrt(4.8), abs=1e-4)
    assert p == pytest.approx(0.02846, abs=1e-5)


def test_z_sense_variancia():
    assert e.z_dues_proporcions(0, 10, 0, 20) == (0.0, 1.0)


def test_ic95_diferencia_wald():
    lo, hi = e.ic95_diferencia(45, 100, 30, 100)
    se = math.sqrt(0.45 * 0.55 / 100 + 0.3 * 0.7 / 100)
    assert lo == pytest.approx(0.15 - 1.959964 * se, abs=1e-6)
    assert hi == pytest.approx(0.15 + 1.959964 * se, abs=1e-6)
    assert lo > 0  # coherent amb p < 0,05


def test_wilson():
    lo, hi = e.wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4) and hi == pytest.approx(0.7634, abs=1e-4)
    assert e.wilson(0, 0) is None
    assert e.wilson(0, 10)[0] == pytest.approx(0.0, abs=1e-12)


def test_mostra_necessaria():
    # power.prop.test(p1 = .3, p2 = .4, power = .8): n = 355.9 per grup
    assert e.mostra_necessaria(0.3, 0.4) == 356
    assert e.mostra_necessaria(0.4, 0.3) == 356
    assert e.mostra_necessaria(0.3, 0.3) is None
