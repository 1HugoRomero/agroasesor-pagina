"""Conversión de superficies (1 ha = 10.000 m²) y formato numérico chileno.

Única fuente de la conversión ha ↔ m² para la API: los demás módulos (calculadora, potreros) la reutilizan.
"""

from decimal import Decimal, InvalidOperation

M2_POR_HA = Decimal("10000")


def a_decimal(valor, campo="valor"):
    if valor is None or isinstance(valor, bool):
        raise ValueError(f"{campo} no es un número válido.")
    try:
        numero = Decimal(str(valor).strip().replace(",", ".")) if isinstance(valor, str) else Decimal(str(valor))
    except InvalidOperation:
        raise ValueError(f"{campo} no es un número válido.")
    if not numero.is_finite():
        raise ValueError(f"{campo} no es un número válido.")
    return numero


def ha_a_m2(ha):
    return a_decimal(ha, "ha") * M2_POR_HA


def m2_a_ha(m2):
    return a_decimal(m2, "m2") / M2_POR_HA


def formato_es(numero, decimales=2):
    """1234.5 -> '1.234,5' (miles con punto, decimal con coma, sin ceros sobrantes)."""
    n = a_decimal(numero)
    texto = f"{n:,.{decimales}f}"
    entero, _, dec = texto.partition(".")
    entero = entero.replace(",", ".")
    dec = dec.rstrip("0")
    return f"{entero},{dec}" if dec else entero


def superficie_dual(ha):
    """Devuelve la superficie en ambas unidades, lista para mostrar."""
    ha = a_decimal(ha, "ha")
    m2 = ha_a_m2(ha)
    return {
        "hectareas": float(ha),
        "metros_cuadrados": float(m2),
        "texto": f"{formato_es(ha, 4)} ha ({formato_es(m2, 2)} m²)",
    }
