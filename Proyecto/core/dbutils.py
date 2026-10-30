"""Utilidades para trabajar con LA base de datos oficial de AgroAsesor.

Regla del proyecto: existe una sola base de datos oficial, el archivo SQLite que vive en el
volumen persistente de Docker (/data/db.sqlite3). Todo lo demás (db.sqlite3 sueltos, respaldos
viejos) es solo archivo o copia de seguridad.
"""

import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connection

RUTA_OFICIAL_DOCKER = '/data/db.sqlite3'

# Tablas que cuentan «lo que el agricultor registró» (sirven para ver de un vistazo qué hay en la base).
TABLAS_RESUMEN = [
    ('auth_user', 'Usuarios'),
    ('core_predio', 'Predios'),
    ('core_potrero', 'Potreros'),
    ('core_temporadacultivo', 'Temporadas de cultivo'),
    ('core_actividadagricola', 'Actividades'),
    ('core_calculoagricola', 'Cálculos guardados'),
    ('core_cultivo', 'Cultivos (catálogo)'),
    ('core_insumo', 'Insumos (catálogo)'),
    ('core_zona', 'Zonas (catálogo)'),
]


def ruta_bd():
    """Ruta absoluta del archivo SQLite que está usando Django en este momento."""
    return Path(str(settings.DATABASES['default']['NAME'])).resolve()


def es_base_oficial():
    return str(ruta_bd()).replace('\\', '/') == RUTA_OFICIAL_DOCKER


def directorio_respaldos():
    """Carpeta de respaldos: DJANGO_BACKUP_DIR, o /backups en Docker, o ./backups en local."""
    configurado = os.getenv('DJANGO_BACKUP_DIR')
    if configurado:
        return Path(configurado)
    if Path('/backups').is_dir():
        return Path('/backups')
    return Path(settings.BASE_DIR) / 'backups'


def _sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, 'rb') as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b''):
            h.update(bloque)
    return h.hexdigest()


def verificar_respaldo(ruta):
    """Abre el respaldo en solo lectura y comprueba que sea una base sana.

    Devuelve un diccionario con integridad, cantidad de tablas, filas de auth_user y la suma sha256.
    """
    con = sqlite3.connect(f'file:{ruta}?mode=ro', uri=True)
    try:
        integridad = con.execute('PRAGMA integrity_check').fetchone()[0]
        tablas = con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        try:
            usuarios = con.execute('SELECT COUNT(*) FROM auth_user').fetchone()[0]
        except sqlite3.Error:
            usuarios = None
    finally:
        con.close()
    return {
        'integridad': integridad,
        'tablas': tablas,
        'usuarios': usuarios,
        'sha256': _sha256(ruta),
        'ok': integridad == 'ok',
    }


def respaldar(prefijo='db', mantener=20, directorio=None):
    """Copia consistente de la base (API de respaldo de SQLite, segura aunque la app esté encendida).

    El respaldo se verifica (integridad y suma sha256, que queda en un archivo .sha256 al lado). Devuelve la
    ruta del respaldo, o None si la base aún no existe. Si la verificación falla se borra la copia y se
    lanza RuntimeError. Conserva solo los últimos ``mantener`` respaldos con ese prefijo (otros prefijos
    nunca se borran).
    """
    origen = ruta_bd()
    if not origen.exists() or origen.stat().st_size == 0:
        return None
    carpeta = Path(directorio) if directorio else directorio_respaldos()
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f'{prefijo}-{datetime.now():%Y%m%d-%H%M%S}.sqlite3'
    con_origen = sqlite3.connect(str(origen))
    con_destino = sqlite3.connect(str(destino))
    try:
        con_origen.backup(con_destino)
    finally:
        con_destino.close()
        con_origen.close()
    resultado = verificar_respaldo(destino)
    if not resultado['ok']:
        destino.unlink(missing_ok=True)
        raise RuntimeError(f'El respaldo no pasó la verificación de integridad ({resultado["integridad"]}).')
    (destino.parent / f'{destino.name}.sha256').write_text(f'{resultado["sha256"]}  {destino.name}\n', encoding='utf-8')
    _ULTIMA_VERIFICACION[str(destino)] = resultado
    if mantener and mantener > 0:
        viejos = sorted(carpeta.glob(f'{prefijo}-*.sqlite3'), key=lambda p: p.stat().st_mtime, reverse=True)
        for viejo in viejos[mantener:]:
            for archivo in (viejo, viejo.parent / f'{viejo.name}.sha256'):
                try:
                    archivo.unlink()
                except OSError:
                    pass
    return destino


_ULTIMA_VERIFICACION = {}


def verificacion_de(ruta):
    """Resultado de la verificación hecha al crear ese respaldo (o None si no se hizo en este proceso)."""
    return _ULTIMA_VERIFICACION.get(str(ruta))


def resumen_conteos():
    """[(etiqueta, cantidad)] de las tablas principales; None si la tabla aún no existe."""
    resultado = []
    with connection.cursor() as cur:
        for tabla, etiqueta in TABLAS_RESUMEN:
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{tabla}"')
                resultado.append((etiqueta, cur.fetchone()[0]))
            except Exception:
                resultado.append((etiqueta, None))
    return resultado
