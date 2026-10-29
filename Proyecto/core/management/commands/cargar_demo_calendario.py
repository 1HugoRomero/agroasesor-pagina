"""Carga datos de DEMOSTRACIÓN para ver el calendario mientras no hay catálogo real.

Uso:
    python manage.py cargar_demo_calendario            # crea zonas, cultivos y ventanas de ejemplo
    python manage.py cargar_demo_calendario --borrar   # elimina solo lo creado por este comando

Los registros quedan en estado «Borrador» y con el documento «DEMO», así que la página
los muestra marcados como «Demostración» y nunca como referencias verificadas. Los
cálculos y evaluadores que exigen fuente verificada no los usan.
"""
import calendar

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Cultivo, ReferenciaAgronomica, Zona

MARCA = 'DEMO'
DESCRIPCION = 'Dato de demostración. No es una referencia oficial.'

ZONAS = ['Metropolitana', 'O’Higgins', 'Maule', 'Valparaíso']

# cultivo: (descripción, ciclo en días, [(zona, variedad, siembra mes ini-fin, cosecha mes ini-fin, nota)])
CULTIVOS = {
    'Maíz': ('Grano y ensilaje en Zona Central.', 150, [
        ('Metropolitana', 'Híbrido demo', (9, 11), (2, 4), 'Siembra de primavera.'),
        ('Metropolitana', '', (9, 11), (2, 4), 'Siembra de primavera.'),
        ('O’Higgins', '', (10, 11), (3, 5), 'Siembra de primavera, algo más tardía.'),
        ('Maule', '', (10, 12), (3, 5), 'Siembra de primavera.'),
        ('Valparaíso', '', (9, 10), (2, 4), 'Siembra temprana en valle.'),
    ]),
    'Trigo': ('Cereal de siembra otoño-invierno.', 210, [
        ('Maule', 'Demo invierno', (5, 7), (12, 1), 'Siembra de otoño-invierno.'),
        ('Maule', '', (5, 7), (12, 1), 'Siembra de otoño-invierno.'),
        ('O’Higgins', '', (5, 7), (12, 1), 'Siembra de otoño-invierno.'),
        ('Metropolitana', '', (5, 6), (12, 1), 'Siembra de otoño-invierno.'),
    ]),
    'Papa': ('Tubérculo de primavera.', 130, [
        ('O’Higgins', '', (8, 10), (12, 2), 'Papa de primavera.'),
        ('Metropolitana', '', (8, 10), (12, 2), 'Papa de primavera.'),
        ('Maule', '', (9, 11), (1, 3), 'Papa de primavera, más tardía.'),
        ('Valparaíso', '', (8, 9), (12, 1), 'Papa temprana.'),
    ]),
    'Alfalfa': ('Forraje con varios cortes.', 365, [
        ('Maule', '', (3, 5), (9, 4), 'Establecimiento en otoño.'),
        ('O’Higgins', '', (3, 5), (9, 4), 'Establecimiento en otoño.'),
    ]),
    'Tomate': ('Industrial y fresco bajo riego.', 140, [
        ('Metropolitana', 'Industrial demo', (8, 10), (12, 3), 'Trasplante de primavera.'),
        ('Metropolitana', '', (8, 10), (12, 3), 'Trasplante de primavera.'),
        ('O’Higgins', '', (9, 10), (1, 3), 'Trasplante de primavera.'),
    ]),
    'Cebolla': ('Almácigo y trasplante.', 180, [
        ('O’Higgins', '', (6, 8), (1, 3), 'Almácigo de invierno.'),
        ('Metropolitana', '', (6, 8), (1, 3), 'Almácigo de invierno.'),
    ]),
}


def _ventana(meses):
    inicio, fin = meses
    return inicio, 1, fin, calendar.monthrange(2001, fin)[1]


class Command(BaseCommand):
    help = 'Carga (o con --borrar elimina) datos de demostración del calendario agronómico.'

    def add_arguments(self, parser):
        parser.add_argument('--borrar', action='store_true', help='Elimina los datos creados por este comando.')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['borrar']:
            return self._borrar()
        zonas = {}
        for nombre in ZONAS:
            zona, creada = Zona.objects.get_or_create(
                nombre=nombre, defaults={'descripcion': DESCRIPCION, 'activo': True},
            )
            zonas[nombre] = zona
        creadas = existentes = 0
        for nombre, (descripcion, ciclo, filas) in CULTIVOS.items():
            cultivo, _ = Cultivo.objects.get_or_create(
                nombre=nombre, defaults={'descripcion': f'{descripcion} {DESCRIPCION}', 'activo': True},
            )
            for zona_nombre, variedad, siembra, cosecha, nota in filas:
                zona = zonas[zona_nombre]
                if ReferenciaAgronomica.objects.filter(
                    cultivo=cultivo, zona=zona, anio_referencia=None, variedad__iexact=variedad,
                ).exists():
                    existentes += 1
                    continue
                si_m, si_d, sf_m, sf_d = _ventana(siembra)
                ci_m, ci_d, cf_m, cf_d = _ventana(cosecha)
                referencia = ReferenciaAgronomica(
                    cultivo=cultivo, zona=zona, variedad=variedad,
                    siembra_inicio_mes=si_m, siembra_inicio_dia=si_d,
                    siembra_fin_mes=sf_m, siembra_fin_dia=sf_d,
                    cosecha_inicio_mes=ci_m, cosecha_inicio_dia=ci_d,
                    cosecha_fin_mes=cf_m, cosecha_fin_dia=cf_d,
                    duracion_ciclo_dias=ciclo,
                    condicion_siembra=f'{nota} {DESCRIPCION}',
                    documento_fuente=MARCA,
                    estado=ReferenciaAgronomica.Estado.BORRADOR,
                )
                referencia.full_clean()
                referencia.save()
                creadas += 1
        self.stdout.write(self.style.SUCCESS(
            f'Demostración cargada: {creadas} ventanas nuevas, {existentes} ya existían. '
            'Quedan marcadas como «Demostración»; bórralas con --borrar cuando tengas datos reales.'
        ))

    def _borrar(self):
        refs = ReferenciaAgronomica.objects.filter(documento_fuente=MARCA)
        total = refs.count()
        refs.delete()
        cultivos = Cultivo.objects.filter(descripcion__contains=DESCRIPCION, referencias_agronomicas__isnull=True)
        zonas = Zona.objects.filter(descripcion=DESCRIPCION, referencias_agronomicas__isnull=True, predio__isnull=True)
        n_c, n_z = cultivos.count(), zonas.count()
        for cultivo in cultivos:
            try:
                cultivo.delete()
            except Exception:  # tiene potreros u otros registros asociados: se conserva
                n_c -= 1
        for zona in zonas:
            try:
                zona.delete()
            except Exception:
                n_z -= 1
        self.stdout.write(self.style.SUCCESS(
            f'Eliminadas {total} ventanas demo, {n_c} cultivos y {n_z} zonas creados por la demostración.'
        ))
