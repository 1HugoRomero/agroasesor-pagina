from decimal import Decimal

from app.services.unidades import formato_es, ha_a_m2, m2_a_ha, superficie_dual


def test_conversion_ida_y_vuelta(client=None):
    assert ha_a_m2("1.5") == Decimal("15000")
    assert m2_a_ha(2500) == Decimal("0.25")
    assert m2_a_ha(ha_a_m2("3.7")) == Decimal("3.7")


def test_coma_decimal_aceptada(client=None):
    assert ha_a_m2("1,5") == Decimal("15000")


def test_formato_chileno(client=None):
    assert formato_es(15000, 2) == "15.000"
    assert formato_es("1234.5", 2) == "1.234,5"
    assert superficie_dual("0.25")["texto"] == "0,25 ha (2.500 m²)"


def test_valores_invalidos(client=None):
    for malo in ("abc", None, True, "NaN", "Infinity"):
        try:
            ha_a_m2(malo)
        except ValueError:
            continue
        raise AssertionError(f"{malo!r} debió rechazarse")
