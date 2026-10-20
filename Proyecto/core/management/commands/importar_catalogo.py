"""Importación controlada del catálogo agronómico desde un archivo JSON.

Uso:
    python manage.py importar_catalogo --plantilla catalogo.json   # crea una plantilla vacía
    python manage.py importar_catalogo catalogo.json               # simulación (no guarda)
    python manage.py importar_catalogo catalogo.json --aplicar     # guarda si todo es válido

Reglas:
- Cada registro se valida con ``full_clean()`` del modelo: un registro marcado como
  verificado sin institución/fuente, URL y fecha es rechazado.
- La importación es atómica: si un registro falla, no se guarda ninguno.
- Los registros existentes (mismo nombre) no se modifican salvo con ``--actualizar``.
- Nunca se generan valores por defecto para dosis, densidades ni ventanas.
"""
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Cultivo, Insumo, ProblemaAgricola, ReferenciaAgronomica, TipoInsumo, Zona

TEMPLATE = {
    "_instrucciones": (
        "Completa solo con datos respaldados por fuentes oficiales (INIA, SAG, ODEPA, "
        "universidades, fichas técnicas del fabricante). Deja vacío lo que no esté "
        "documentado. Para marcar un registro como verificado registra fuente, URL y "
        "fecha de consulta. Elimina esta clave antes de importar si lo prefieres."
    ),
    "zonas": [{"nombre": "", "descripcion": ""}],
    "cultivos": [{
        "nombre": "", "descripcion": "",
        "densidad_siembra": None, "unidad_siembra": "kg",
        "densidad_fuente": "", "densidad_url": "", "densidad_verificada": None,
        "rendimiento_ton_ha": None, "rendimiento_fuente": "", "rendimiento_url": "", "rendimiento_verificado": None,
    }],
    "tipos_insumo": [{"nombre": "Semilla"}, {"nombre": "Fertilizante"}, {"nombre": "Herbicida"},
                     {"nombre": "Fungicida"}, {"nombre": "Insecticida"}],
    "problemas": [{
        "nombre": "", "tipo": "pest | disease | weed | nutrition | other",
        "descripcion": "", "sintomas": "", "fuente_nombre": "", "fuente_url": "", "cultivos": [""],
    }],
    "referencias": [{
        "cultivo": "", "zona": "", "variedad": "", "anio_referencia": None,
        "nombre_cientifico": "", "familia_botanica": "", "tipo_cultivo": "",
        "siembra_inicio_mes": None, "siembra_inicio_dia": None, "siembra_fin_mes": None, "siembra_fin_dia": None,
        "cosecha_inicio_mes": None, "cosecha_inicio_dia": None, "cosecha_fin_mes": None, "cosecha_fin_dia": None,
        "duracion_ciclo_dias": None, "rendimiento_ton_ha": None,
        "condicion_siembra": "", "requerimientos": "", "profundidad_siembra": "",
        "etapas_fenologicas": "", "condiciones_crecimiento": "", "manejo_general": "",
        "indicadores_madurez": "", "consideraciones_cosecha": "",
        "plagas": "", "enfermedades": "", "malezas": "", "manejo_integrado": "",
        "institucion_fuente": "", "documento_fuente": "", "url_fuente": "", "fecha_consulta_fuente": None,
        "estado": "draft",
    }],
    "insumos": [{
        "nombre": "", "tipo": "", "cultivo": "", "zona": "", "problemas": [],
        "descripcion": "", "fabricante": "", "estado_verificacion": "unverified",
        "fuente_nombre": "", "fuente_url": "", "fecha_verificacion": None,
        "dosis_hectarea": None, "unidad_dosis": "", "dosis_verificada": False, "dosis_fuente": "",
        "numero_autorizacion_sag": "", "etiqueta_url": "", "hoja_seguridad_url": "",
        "ingrediente_activo": "", "concentracion": "", "formulacion": "",
        "cultivos_autorizados": [], "objetivos_control": [], "modo_aplicacion": "", "restricciones": "",
        "periodo_carencia": "", "tiempo_reingreso": "", "composicion_nutricional": "",
        "nitrogeno_pct": None, "fosforo_p2o5_pct": None, "potasio_k2o_pct": None,
        "presentacion_cantidad": None, "presentacion_unidad": "",
        "variedad_semilla": "", "tipo_semilla": "", "plantas_objetivo_m2": None,
        "peso_mil_semillas_g": None, "germinacion_pct": None, "pureza_pct": None,
    }],
}

DATE_FIELDS = {
    'densidad_verificada', 'rendimiento_verificado', 'fecha_consulta_fuente', 'fecha_verificacion',
    'vigencia_desde', 'vigencia_hasta',
}
DECIMAL_FIELDS = {
    'densidad_siembra', 'rendimiento_ton_ha', 'dosis_hectarea', 'dosis_maxima_hectarea', 'nitrogeno_pct',
    'fosforo_p2o5_pct', 'potasio_k2o_pct', 'presentacion_cantidad', 'plantas_objetivo_m2',
    'peso_mil_semillas_g', 'germinacion_pct', 'pureza_pct',
}


def _clean_values(model, record, skip):
    names = {field.name for field in model._meta.get_fields() if getattr(field, 'concrete', False)}
    values = {}
    for key, value in record.items():
        if key.startswith('_') or key in skip:
            continue
        if key not in names:
            raise CommandError(f'{model.__name__}: el campo «{key}» no existe.')
        if value is None or value == '':
            field = model._meta.get_field(key)
            if field.null:
                values[key] = None
            elif value == '':
                values[key] = ''
            continue
        if key in DATE_FIELDS:
            try:
                value = date.fromisoformat(str(value))
            except ValueError:
                raise CommandError(f'{model.__name__}: «{key}» debe tener formato AAAA-MM-DD.')
        elif key in DECIMAL_FIELDS:
            try:
                value = Decimal(str(value))
            except InvalidOperation:
                raise CommandError(f'{model.__name__}: «{key}» debe ser numérico.')
        values[key] = value
    return values


class Command(BaseCommand):
    help = 'Importa el catálogo agronómico desde JSON con validación completa (simulación por defecto).'

    def add_arguments(self, parser):
        parser.add_argument('archivo', nargs='?')
        parser.add_argument('--aplicar', action='store_true', help='Guarda los cambios. Sin esta opción solo valida.')
        parser.add_argument('--actualizar', action='store_true', help='Permite modificar registros existentes con el mismo nombre.')
        parser.add_argument('--plantilla', metavar='RUTA', help='Escribe una plantilla JSON vacía y termina.')

    def handle(self, *args, **options):
        if options['plantilla']:
            with open(options['plantilla'], 'w', encoding='utf-8') as handle:
                json.dump(TEMPLATE, handle, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f'Plantilla creada en {options["plantilla"]}. No contiene datos agronómicos.'))
            return
        if not options['archivo']:
            raise CommandError('Indica el archivo JSON a importar o usa --plantilla.')
        try:
            with open(options['archivo'], encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f'No se pudo leer el archivo: {exc}')
        if not isinstance(data, dict):
            raise CommandError('El archivo debe contener un objeto JSON.')

        self.update = options['actualizar']
        self.summary = {}
        try:
            with transaction.atomic():
                self._import(data)
                if not options['aplicar']:
                    transaction.set_rollback(True)
        except ValidationError as exc:
            raise CommandError(f'Validación rechazada: {exc}')
        for section, (created, updated, skipped) in self.summary.items():
            self.stdout.write(f'{section}: {created} nuevos, {updated} actualizados, {skipped} sin cambios')
        if options['aplicar']:
            self.stdout.write(self.style.SUCCESS('Catálogo importado.'))
        else:
            self.stdout.write(self.style.WARNING('Simulación: no se guardó nada. Usa --aplicar para importar.'))

    def _save(self, section, model, lookup, values, m2m=None):
        created = updated = skipped = 0
        instance = model.objects.filter(**lookup).first()
        if instance and not self.update:
            skipped = 1
        else:
            instance = instance or model(**lookup)
            for key, value in values.items():
                setattr(instance, key, value)
            instance.full_clean()
            is_new = instance.pk is None
            instance.save()
            for key, items in (m2m or {}).items():
                getattr(instance, key).set(items)
            created, updated = (1, 0) if is_new else (0, 1)
        total = self.summary.get(section, (0, 0, 0))
        self.summary[section] = (total[0] + created, total[1] + updated, total[2] + skipped)
        return instance

    def _get(self, model, name, label):
        if not name:
            return None
        instance = model.objects.filter(nombre=name).first()
        if instance is None:
            raise CommandError(f'{label} «{name}» no existe en el catálogo ni en el archivo.')
        return instance

    def _import(self, data):
        for record in data.get('zonas', []):
            if not record.get('nombre'):
                continue
            values = _clean_values(Zona, record, {'nombre'})
            self._save('Zonas', Zona, {'nombre': record['nombre']}, values)
        for record in data.get('cultivos', []):
            if not record.get('nombre'):
                continue
            values = _clean_values(Cultivo, record, {'nombre'})
            self._save('Cultivos', Cultivo, {'nombre': record['nombre']}, values)
        for record in data.get('tipos_insumo', []):
            if record.get('nombre'):
                self._save('Tipos de insumo', TipoInsumo, {'nombre': record['nombre']}, {})
        for record in data.get('problemas', []):
            if not record.get('nombre'):
                continue
            values = _clean_values(ProblemaAgricola, record, {'nombre', 'cultivos'})
            crops = [self._get(Cultivo, name, 'El cultivo') for name in record.get('cultivos', []) if name]
            self._save('Problemas', ProblemaAgricola, {'nombre': record['nombre']}, values, {'cultivos': crops})
        for record in data.get('referencias', []):
            if not record.get('cultivo') or not record.get('zona'):
                continue
            values = _clean_values(ReferenciaAgronomica, record, {'cultivo', 'zona', 'variedad', 'anio_referencia'})
            lookup = {
                'cultivo': self._get(Cultivo, record['cultivo'], 'El cultivo'),
                'zona': self._get(Zona, record['zona'], 'La zona'),
                'variedad': (record.get('variedad') or '').strip(),
                'anio_referencia': record.get('anio_referencia'),
            }
            self._save('Referencias agronómicas', ReferenciaAgronomica, lookup, values)
        for record in data.get('insumos', []):
            if not record.get('nombre'):
                continue
            values = _clean_values(Insumo, record, {'nombre', 'tipo', 'cultivo', 'zona', 'problemas'})
            values['cultivo'] = self._get(Cultivo, record.get('cultivo'), 'El cultivo')
            values['zona'] = self._get(Zona, record.get('zona'), 'La zona')
            tipo = self._get(TipoInsumo, record.get('tipo'), 'El tipo de insumo')
            if tipo is None:
                raise CommandError(f'El insumo «{record["nombre"]}» requiere un tipo.')
            problems = [self._get(ProblemaAgricola, name, 'El problema') for name in record.get('problemas', []) if name]
            self._save('Insumos', Insumo, {'nombre': record['nombre'], 'tipo': tipo}, values, {'problemas': problems})
