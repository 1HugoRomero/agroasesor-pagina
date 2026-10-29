"""Revisa que la base oficial esté sana y que sus datos estén bien relacionados.

Uso (Docker):  docker exec agroasesor_hugo python manage.py verificar_bd

Comprueba: integridad de SQLite, claves foráneas (sin registros huérfanos), duplicados evidentes
(mismo predio dos veces para un mismo dueño, mismo potrero dos veces en un predio), usuarios que comparten
correo (se informan, nunca se fusionan) y muestra los totales finales. Termina con error si hay problemas graves.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from core import dbutils


class Command(BaseCommand):
    help = 'Verifica integridad, relaciones y duplicados de la base oficial y muestra los totales.'

    def _filas(self, sql):
        with connection.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def handle(self, *args, **options):
        graves = []
        self.stdout.write('')
        self.stdout.write(f'Base revisada: {dbutils.ruta_bd()}')
        self.stdout.write(self.style.SUCCESS('Es la base OFICIAL.') if dbutils.es_base_oficial() else self.style.WARNING('OJO: no es la base oficial (/data/db.sqlite3).'))

        integridad = self._filas('PRAGMA integrity_check')[0][0]
        self.stdout.write(f'Integridad de SQLite : {integridad}')
        if integridad != 'ok':
            graves.append(f'integrity_check devolvió «{integridad}»')

        huerfanos = self._filas('PRAGMA foreign_key_check')
        self.stdout.write(f'Registros sin relación (claves foráneas rotas): {len(huerfanos)}')
        for tabla, fila, destino, _ in huerfanos[:20]:
            self.stdout.write(self.style.ERROR(f'  - {tabla} fila {fila} apunta a «{destino}» que no existe'))
        if huerfanos:
            graves.append(f'{len(huerfanos)} claves foráneas rotas')

        duplicados = {
            'Predios repetidos (mismo dueño y nombre)': 'SELECT propietario_id, nombre, COUNT(*) FROM core_predio GROUP BY propietario_id, nombre HAVING COUNT(*) > 1',
            'Potreros repetidos (mismo predio y nombre)': 'SELECT predio_id, nombre, COUNT(*) FROM core_potrero GROUP BY predio_id, nombre HAVING COUNT(*) > 1',
            'Usuarios repetidos (mismo nombre sin distinguir mayúsculas)': 'SELECT lower(username), COUNT(*) FROM auth_user GROUP BY lower(username) HAVING COUNT(*) > 1',
            'Agricultores con el mismo RUT': 'SELECT rut, COUNT(*) FROM core_agricultor WHERE rut IS NOT NULL AND rut <> \'\' GROUP BY rut HAVING COUNT(*) > 1',
        }
        for etiqueta, sql in duplicados.items():
            filas = self._filas(sql)
            self.stdout.write(f'{etiqueta}: {len(filas)}')
            for fila in filas[:10]:
                self.stdout.write(self.style.ERROR(f'  - {fila}'))
            if filas:
                graves.append(f'{etiqueta}: {len(filas)}')

        compartidos = self._filas(
            "SELECT lower(email), group_concat(username, ', '), COUNT(*) FROM auth_user "
            "WHERE email <> '' GROUP BY lower(email) HAVING COUNT(*) > 1"
        )
        self.stdout.write(f'Correos compartidos por varias cuentas (se conservan separadas; solo informativo): {len(compartidos)}')
        for correo, usuarios, cuantos in compartidos:
            self.stdout.write(self.style.WARNING(f'  · {correo} → {cuantos} cuentas: {usuarios}'))

        sin_perfil = self._filas(
            'SELECT username FROM auth_user WHERE is_staff = 0 AND id NOT IN (SELECT user_id FROM core_agricultor)'
        )
        self.stdout.write(f'Cuentas de agricultor sin perfil completo (nombre/teléfono/comuna): {len(sin_perfil)} (informativo; verán el aviso en «Mi perfil»)')
        admins = self._filas("SELECT username FROM auth_user WHERE is_staff = 1")
        self.stdout.write(f'Cuentas con acceso de administrador: {len(admins)} → ' + (', '.join(a[0] for a in admins) or 'ninguna'))
        sin_potrero = self._filas('SELECT COUNT(*) FROM core_predio WHERE id NOT IN (SELECT predio_id FROM core_potrero)')[0][0]
        self.stdout.write(f'Predios todavía sin potreros (normal; el agricultor puede no haberlos creado aún): {sin_potrero}')

        self.stdout.write('\nTotales de la base oficial:')
        for etiqueta, cantidad in dbutils.resumen_conteos():
            self.stdout.write(f'  {etiqueta:<26}{"—" if cantidad is None else cantidad}')
        if graves:
            raise CommandError('Verificación con problemas: ' + '; '.join(graves))
        self.stdout.write(self.style.SUCCESS('\nVerificación correcta: sin registros huérfanos ni duplicados.'))
