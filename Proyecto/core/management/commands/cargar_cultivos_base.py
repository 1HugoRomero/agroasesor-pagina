"""Carga los cultivos base (solo nombres) y la zona «Melipilla» para poder trabajar desde el primer día.

Uso:
    python manage.py cargar_cultivos_base

Es seguro repetirlo: solo crea los que faltan y nunca modifica ni borra los existentes. No carga
rendimientos, densidades, dosis ni ventanas de siembra; esos datos deben registrarse con su fuente
desde el administrador.
"""
from django.core.management.base import BaseCommand

from core.catalog import ensure_base_crops, ensure_default_zone


class Command(BaseCommand):
    help = 'Carga los cultivos base de la zona central y la zona Melipilla (solo nombres, sin datos agronómicos).'

    def handle(self, *args, **options):
        created = ensure_base_crops()
        if created:
            self.stdout.write(self.style.SUCCESS(f'Se cargaron {created} cultivos base.'))
        else:
            self.stdout.write('Los cultivos base ya estaban cargados.')
        zone, zone_created = ensure_default_zone()
        if zone_created:
            self.stdout.write(self.style.SUCCESS(f'Se creó la zona por defecto: {zone.nombre}.'))
