"""Validaciones y normalización de datos personales chilenos (nombre, teléfono, comuna y RUT).

Se usan en el registro y en el perfil del agricultor. Todas lanzan ``ValidationError`` con mensajes
pensados para el agricultor, y devuelven el valor ya normalizado para guardarlo en la base.
"""
import re

from django.core.exceptions import ValidationError

_LETRAS_NOMBRE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]*$")
_PARTICULAS = {'de', 'del', 'la', 'las', 'los', 'el', 'y', 'e'}


def _embellecer(texto):
    """«juan de la cruz» → «Juan de la Cruz» (respeta las partículas habituales)."""
    palabras = []
    for i, palabra in enumerate(texto.split()):
        bajo = palabra.lower()
        if i > 0 and bajo in _PARTICULAS:
            palabras.append(bajo)
        else:
            palabras.append('-'.join(parte[:1].upper() + parte[1:].lower() for parte in palabra.split('-')))
    return ' '.join(palabras)


def normalizar_nombre_completo(valor):
    """Nombre y apellido: solo letras, espacios, guion, punto y apóstrofo; al menos dos palabras."""
    texto = ' '.join((valor or '').split())
    if not texto:
        raise ValidationError('Escribe tu nombre completo.')
    if len(texto) > 150:
        raise ValidationError('El nombre es demasiado largo (máximo 150 caracteres).')
    if not _LETRAS_NOMBRE.match(texto):
        raise ValidationError('El nombre solo puede tener letras, espacios, guion, punto y apóstrofo.')
    if len(texto.split()) < 2:
        raise ValidationError('Escribe tu nombre y tu apellido.')
    return _embellecer(texto)


def partir_nombre(nombre_completo):
    """(nombre, apellidos) para los campos first_name / last_name de Django."""
    partes = nombre_completo.split()
    if len(partes) <= 2:
        return partes[0], ' '.join(partes[1:])
    mitad = 2 if len(partes) >= 4 else 1
    return ' '.join(partes[:mitad]), ' '.join(partes[mitad:])


def normalizar_comuna(valor):
    texto = ' '.join((valor or '').split())
    if not texto:
        raise ValidationError('Indica tu comuna.')
    if len(texto) > 100:
        raise ValidationError('El nombre de la comuna es demasiado largo.')
    if not _LETRAS_NOMBRE.match(texto) or len(texto) < 3:
        raise ValidationError('La comuna solo puede tener letras y espacios (por ejemplo: Melipilla).')
    return _embellecer(texto)


def normalizar_telefono(valor):
    """Teléfono chileno de 9 dígitos (móvil 9XXXXXXXX o fijo con código de área). Se guarda como +56XXXXXXXXX."""
    texto = (valor or '').strip()
    if not texto:
        raise ValidationError('Indica un teléfono de contacto.')
    if not re.fullmatch(r'\+?[0-9 ()\-]+', texto):
        raise ValidationError('El teléfono solo puede tener números, espacios, guion, paréntesis y un «+» al inicio.')
    digitos = re.sub(r'\D', '', texto)
    if texto.startswith('+') or digitos.startswith('56') and len(digitos) == 11:
        if not digitos.startswith('56'):
            raise ValidationError('Por ahora solo se aceptan teléfonos de Chile (+56).')
        digitos = digitos[2:]
    if len(digitos) == 10 and digitos.startswith('0'):
        digitos = digitos[1:]
    if len(digitos) != 9 or digitos[0] not in '23456789':
        raise ValidationError('Escribe un teléfono chileno de 9 dígitos, por ejemplo +56 9 1234 5678.')
    return f'+56{digitos}'


def formatear_telefono(valor):
    """+56912345678 → «+56 9 1234 5678» (solo para mostrar)."""
    if valor and re.fullmatch(r'\+56\d{9}', valor):
        return f'+56 {valor[3]} {valor[4:8]} {valor[8:]}'
    return valor or ''


def digito_verificador(cuerpo):
    suma, factor = 0, 2
    for cifra in reversed(str(cuerpo)):
        suma += int(cifra) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return '0' if resto == 11 else 'K' if resto == 10 else str(resto)


def normalizar_rut(valor):
    """RUT con dígito verificador (módulo 11). Devuelve «12345678-5» sin puntos; acepta «12.345.678-5»."""
    texto = (valor or '').strip()
    if not texto:
        return None
    if not re.fullmatch(r'[0-9.\-kK ]+', texto):
        raise ValidationError('El RUT solo puede tener números, puntos, guion y la letra K.')
    limpio = re.sub(r'[.\s]', '', texto).upper()
    coincide = re.fullmatch(r'(\d{7,8})-?([0-9K])', limpio)
    if not coincide:
        raise ValidationError('Escribe el RUT completo con su dígito verificador, por ejemplo 12.345.678-5.')
    cuerpo, dv = coincide.groups()
    if digito_verificador(cuerpo) != dv:
        raise ValidationError('El RUT no es válido: revisa el dígito verificador.')
    return f'{cuerpo}-{dv}'


def formatear_rut(valor):
    """12345678-5 → «12.345.678-5» (solo para mostrar)."""
    if not valor or '-' not in valor:
        return valor or ''
    cuerpo, dv = valor.split('-')
    return f'{int(cuerpo):,}'.replace(',', '.') + f'-{dv}'
