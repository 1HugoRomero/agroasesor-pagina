from django.core.management.base import BaseCommand

from core.models import Cultivo, Insumo, TipoInsumo, Zona

ZONAS = [
    ('Metropolitana', 'Valle de Melipilla y alrededores.'),
    ('O’Higgins', 'Valle de Rancagua y secano interior.'),
    ('Maule', 'Valle del Maule, primavera un poco más tardía.'),
    ('Valparaíso', 'Valle de Aconcagua y litoral interior.'),
]

CULTIVOS = [
    ('Maíz', 'Grano y ensilaje en Zona Central.', '9.20', '25', 'kg'),
    ('Trigo', 'Siembra de otoño-invierno.', '5.50', '160', 'kg'),
    ('Papa', 'Tubérculo de media estación.', '30.00', '2500', 'kg'),
    ('Alfalfa', 'Forraje con varios cortes.', '12.00', '20', 'kg'),
    ('Tomate', 'Industrial y fresco bajo riego.', '70.00', '0.2', 'kg'),
    ('Cebolla', 'Almácigo y transplante.', '40.00', '4', 'kg'),
]

INSUMOS = [
    ('Insecticida', 'Maíz', 'Metropolitana', 'Insumo demostrativo A', '2', 'L', True),
    ('Fertilizante', 'Trigo', 'O’Higgins', 'Fertilizante demostrativo B', '250', 'kg', True),
    ('Fertilizante', 'Maíz', 'Maule', 'Urea demostrativa Maule', '200', 'kg', True),
    ('Semilla', 'Maíz', 'Metropolitana', 'Semilla demostrativa C', '25', 'kg', True),
]


class Command(BaseCommand):
    help = 'Carga cultivos, zonas e insumos de demostración para que la calculadora lea la base.'

    def handle(self, *args, **options):
        zonas = {}
        for nombre, descripcion in ZONAS:
            zona, _created = Zona.objects.update_or_create(
                nombre=nombre,
                defaults={'descripcion': descripcion, 'activo': True},
            )
            zonas[nombre] = zona

        cultivos = {}
        for nombre, descripcion, rendimiento, densidad, unidad in CULTIVOS:
            cultivo, _created = Cultivo.objects.update_or_create(
                nombre=nombre,
                defaults={
                    'descripcion': descripcion,
                    'rendimiento_ton_ha': rendimiento,
                    'densidad_siembra': densidad,
                    'unidad_siembra': unidad,
                    'activo': True,
                },
            )
            cultivos[nombre] = cultivo

        tipos = {}
        for nombre in ['Insecticida', 'Fertilizante', 'Semilla', 'Herbicida']:
            tipo, _created = TipoInsumo.objects.update_or_create(nombre=nombre)
            tipos[nombre] = tipo

        for tipo, cultivo, zona, nombre, dosis, unidad, vigente in INSUMOS:
            Insumo.objects.update_or_create(
                nombre=nombre,
                tipo=tipos[tipo],
                cultivo=cultivos[cultivo],
                zona=zonas[zona],
                defaults={
                    'dosis_hectarea': dosis,
                    'unidad_dosis': unidad,
                    'vigente': vigente,
                    'descripcion': 'Ficha de demostración. No es una receta SAG.',
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f'Catálogo listo: {Cultivo.objects.count()} cultivos, '
            f'{Zona.objects.count()} zonas, {Insumo.objects.count()} insumos.'
        ))
