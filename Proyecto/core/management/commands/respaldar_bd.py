"""Hace una copia de seguridad consistente de la base de datos oficial.

Uso (Docker):  docker exec agroasesor_hugo python manage.py respaldar_bd
Los respaldos quedan en la carpeta «backups» junto al docker-compose.yml.
"""

from django.core.management.base import BaseCommand

from core import dbutils


class Command(BaseCommand):
    help = 'Crea un respaldo fechado de la base de datos (seguro con la aplicación encendida).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mantener', type=int, default=20, help='Cuántos respaldos automáticos conservar (por defecto 20).'
        )
        parser.add_argument('--prefijo', default='db', help='Prefijo del archivo (por defecto «db»).')

    def handle(self, *args, **options):
        destino = dbutils.respaldar(prefijo=options['prefijo'], mantener=options['mantener'])
        if destino is None:
            self.stdout.write('Aún no hay base de datos que respaldar (se creará al migrar).')
            return
        self.stdout.write(self.style.SUCCESS(f'Respaldo creado: {destino}'))
        info = dbutils.verificacion_de(destino)
        if info:
            self.stdout.write(
                f'Verificado: integridad {info["integridad"]} · {info["tablas"]} tablas · '
                f'{info["usuarios"]} usuarios · sha256 {info["sha256"][:16]}…'
            )
