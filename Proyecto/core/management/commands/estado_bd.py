"""Muestra qué base de datos está usando la aplicación y qué contiene.

Uso (Docker):  docker exec agroasesor_hugo python manage.py estado_bd
"""

from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from core import dbutils


class Command(BaseCommand):
    help = 'Muestra la ruta, el tamaño y el contenido de la base de datos en uso, y si es la oficial.'

    def handle(self, *args, **options):
        ruta = dbutils.ruta_bd()
        self.stdout.write('')
        self.stdout.write('=== BASE DE DATOS EN USO ===')
        self.stdout.write(f'Archivo : {ruta}')
        if ruta.exists():
            info = ruta.stat()
            self.stdout.write(f'Tamaño  : {info.st_size / 1024:,.0f} KB')
            self.stdout.write(f'Última modificación: {datetime.fromtimestamp(info.st_mtime):%d/%m/%Y %H:%M}')
        if dbutils.es_base_oficial():
            self.stdout.write(self.style.SUCCESS('Estado  : BASE OFICIAL (volumen persistente de Docker)'))
        else:
            self.stdout.write(
                self.style.WARNING(
                    'Estado  : NO es la base oficial. Para trabajar con la oficial usa '
                    '«docker compose up -d» y entra por http://localhost:8000/.'
                )
            )
        try:
            pendientes = MigrationExecutor(connection).migration_plan(
                MigrationExecutor(connection).loader.graph.leaf_nodes()
            )
            if pendientes:
                self.stdout.write(self.style.WARNING(f'Migraciones pendientes: {len(pendientes)} (ejecuta migrate).'))
            else:
                self.stdout.write('Migraciones: al día')
        except Exception as exc:  # base nueva o dañada
            self.stdout.write(self.style.WARNING(f'No se pudo revisar las migraciones: {exc}'))
        self.stdout.write('')
        for etiqueta, cantidad in dbutils.resumen_conteos():
            valor = '—' if cantidad is None else cantidad
            self.stdout.write(f'  {etiqueta:<26}{valor}')
        self.stdout.write(f'\nCarpeta de respaldos: {dbutils.directorio_respaldos()}')
        self.stdout.write('')
