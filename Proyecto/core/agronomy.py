"""Referencias agronómicas: ventanas de siembra y cosecha, rangos de dosis con fuente y datos de la calculadora de semillas.

Nada se inventa: cada valor lleva su fuente y su estado. Lo que no tiene fuente verificada se muestra como
«sin dato verificado», y el cálculo sigue siendo posible como simulación con una dosis que escribe la persona.
"""
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.db import models

from .models import Cultivo, ReferenciaAgronomica


ESTADOS_EVALUACION = {
    'within': 'Dentro de ventana referencial',
    'near': 'Cercana al límite de la ventana',
    'outside': 'Fuera de ventana referencial',
    'insufficient': 'Información insuficiente',
}


def find_reference(crop_id, zone_id, variety, year=None):
    """Busca la referencia verificada más específica.

    Prioridad: variedad exacta antes que referencia general y, dentro de cada
    una, el año indicado antes que la ventana recurrente (sin año). Nunca usa
    una referencia de otro año específico.
    """
    references = ReferenciaAgronomica.objects.filter(
        cultivo_id=crop_id,
        zona_id=zone_id,
        estado=ReferenciaAgronomica.Estado.VERIFICADA,
    ).select_related('cultivo', 'zona')
    if year is not None:
        references = references.filter(
            models.Q(anio_referencia=year) | models.Q(anio_referencia__isnull=True)
        )
    else:
        references = references.filter(anio_referencia__isnull=True)
    ordered = references.order_by(models.F('anio_referencia').desc(nulls_last=True), 'pk')
    if variety:
        reference = ordered.filter(variedad__iexact=variety).first()
        if reference:
            return reference
    return ordered.filter(variedad='').first()


def classify_calendar_window(proposal, reference, prefix, margin_days):
    start_month = getattr(reference, f'{prefix}_inicio_mes')
    start_day = getattr(reference, f'{prefix}_inicio_dia')
    end_month = getattr(reference, f'{prefix}_fin_mes')
    end_day = getattr(reference, f'{prefix}_fin_dia')
    if not all((start_month, start_day, end_month, end_day)):
        return 'insufficient', None

    intervals = []
    for start_year in range(proposal.year - 2, proposal.year + 2):
        try:
            start = date(start_year, start_month, start_day)
            end_year = start_year + (
                (end_month, end_day) < (start_month, start_day)
            )
            end = date(end_year, end_month, end_day)
        except ValueError:
            continue
        intervals.append((start, end))

    if not intervals:
        return 'insufficient', None
    for start, end in intervals:
        if start <= proposal <= end:
            return 'within', 0

    distance = min(
        min(abs((proposal - start).days), abs((proposal - end).days))
        for start, end in intervals
    )
    if distance <= margin_days:
        return 'near', distance
    return 'outside', distance


def evaluate_sowing_date(proposal, reference, margin_days):
    if reference is None or not reference.tiene_fuente_verificada:
        return {
            'status': 'insufficient',
            'status_label': ESTADOS_EVALUACION['insufficient'],
            'explanation': 'No hay una referencia verificada para este cultivo, zona y variedad.',
        }

    status, distance = classify_calendar_window(
        proposal,
        reference,
        'siembra',
        margin_days,
    )
    explanations = {
        'within': 'La fecha está dentro de la ventana publicada por la fuente.',
        'near': (
            f'La fecha está a {distance} día(s) del límite de la ventana '
            'y dentro del margen de referencia.'
        ),
        'outside': 'La fecha está fuera de la ventana y del margen de referencia.',
        'insufficient': 'La fuente no registra una ventana completa de siembra.',
    }
    return {
        'status': status,
        'status_label': ESTADOS_EVALUACION[status],
        'explanation': explanations[status],
        'distance_days': distance,
    }


def evaluate_harvest_date(sowing_date, harvest_date, reference, margin_days):
    elapsed_days = (harvest_date - sowing_date).days
    if reference is None or not reference.tiene_fuente_verificada:
        return {
            'status': 'insufficient',
            'status_label': ESTADOS_EVALUACION['insufficient'],
            'explanation': (
                'No hay una referencia verificada para este cultivo, zona y variedad. '
                'No es posible evaluar la fecha de forma confiable.'
            ),
            'elapsed_days': elapsed_days,
            'expected_cycle_days': None,
            'cycle_difference_days': None,
        }

    seasonal_status, distance = classify_calendar_window(
        harvest_date,
        reference,
        'cosecha',
        margin_days,
    )
    if reference.duracion_ciclo_dias is None:
        if seasonal_status == 'insufficient':
            return {
                'status': 'insufficient',
                'status_label': ESTADOS_EVALUACION['insufficient'],
                'explanation': (
                    'La fuente no registra ventana de cosecha ni duración del ciclo; '
                    'no es posible evaluar la fecha de forma confiable.'
                ),
                'elapsed_days': elapsed_days,
                'expected_cycle_days': None,
                'cycle_difference_days': None,
            }
        explanation = {
            'within': 'La fecha cae dentro de la ventana estacional de cosecha publicada.',
            'near': (
                f'La fecha está a {distance} día(s) del límite de la ventana estacional '
                'y dentro del margen de referencia.'
            ),
            'outside': 'La fecha está fuera de la ventana estacional de cosecha y del margen de referencia.',
        }[seasonal_status]
        return {
            'status': seasonal_status,
            'status_label': ESTADOS_EVALUACION[seasonal_status],
            'explanation': explanation + (
                ' La fuente no documenta la duración del ciclo, por lo que no se comparó '
                'con los días transcurridos.'
            ),
            'distance_days': distance,
            'elapsed_days': elapsed_days,
            'expected_cycle_days': None,
            'cycle_difference_days': None,
        }
    cycle_difference = elapsed_days - reference.duracion_ciclo_dias

    if seasonal_status == 'insufficient':
        status = 'insufficient'
        explanation = 'La fuente no registra una ventana completa de cosecha.'
    elif abs(cycle_difference) > margin_days:
        status = 'outside'
        explanation = (
            'La duración prevista difiere más que el margen configurable del ciclo '
            'documentado. La madurez real no puede determinarse solo por calendario.'
        )
    else:
        status = seasonal_status
        explanation = {
            'within': 'La fecha y la duración prevista concuerdan con las referencias disponibles.',
            'near': (
                f'La fecha está a {distance} día(s) del límite de la ventana '
                'y dentro del margen de referencia.'
            ),
            'outside': 'La fecha está fuera de la ventana y del margen de referencia.',
        }[seasonal_status]

    return {
        'status': status,
        'status_label': ESTADOS_EVALUACION[status],
        'explanation': explanation,
        'distance_days': distance,
        'elapsed_days': elapsed_days,
        'expected_cycle_days': reference.duracion_ciclo_dias,
        'cycle_difference_days': cycle_difference,
    }


# Rangos de dosis de siembra con fuente institucional (INIA), leídos del catálogo único de ``backend_flask``.
# Un solo catálogo para Django y la API: aquí no se copian ni inventan valores. Cada referencia indica si su dato
# fue cotejado con la fuente (``cotejada_con_fuente``) o solo está citado (``citada_sin_cotejar``). Sin PyYAML o sin
# el archivo, la calculadora sigue funcionando con la densidad del cultivo registrada en la base de datos.
ARCHIVO = Path(settings.BASE_DIR) / 'backend_flask' / 'data' / 'catalogo_agricola.yaml'
ETIQUETAS = {
    'cotejada_con_fuente': 'Cotejada con la fuente',
    'citada_sin_cotejar': 'Citada de la fuente, pendiente de cotejo',
}


def _norm(texto):
    sin = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode()
    return sin.casefold().strip()


@lru_cache(maxsize=1)
def _catalogo():
    try:
        import yaml
        datos = yaml.safe_load(ARCHIVO.read_text(encoding='utf-8'))
        fuentes = {f['id']: f for f in datos['fuentes']}
        referencias = []
        for ref in datos['referencias_siembra']:
            fuente = fuentes[ref['fuente_id']]
            referencias.append({
                'id': ref['id'], 'cultivo': ref['cultivo'], 'sistema': ref['sistema'],
                'min': float(ref['dosis_min_kg_ha']), 'max': float(ref['dosis_max_kg_ha']),
                'unidad': 'kg/ha', 'nota': ref.get('nota', ''),
                'estado': ref.get('estado_verificacion', 'citada_sin_cotejar'),
                'estado_etiqueta': ETIQUETAS.get(ref.get('estado_verificacion'), ETIQUETAS['citada_sin_cotejar']),
                'fecha_consulta': str(ref.get('fecha_consulta') or ''),
                'fuente': {'organismo': fuente['organismo'], 'titulo': fuente['titulo'], 'url': fuente['url']},
            })
        return tuple(referencias)
    except Exception:  # sin PyYAML, sin archivo o catálogo inválido: se omite y se usa solo la base de datos
        return ()


def referencias_siembra(cultivo=None):
    todas = _catalogo()
    if cultivo is None:
        return list(todas)
    buscado = _norm(cultivo)
    return [r for r in todas if _norm(r['cultivo']) == buscado]


# Calculadora de semillas: cultivos, referencias con fuente e información técnica verificada.
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre']


def _ventana(ref):
    if None in (ref.siembra_inicio_mes, ref.siembra_fin_mes):
        return ''
    inicio, fin = MESES[ref.siembra_inicio_mes - 1].capitalize(), MESES[ref.siembra_fin_mes - 1].capitalize()
    return inicio if inicio == fin else f'{inicio} – {fin}'


def _ficha(ref):
    return {
        'zone': ref.zona.nombre, 'variety': ref.variedad, 'sowingWindow': _ventana(ref),
        'depth': ref.profundidad_siembra, 'management': ref.manejo_general, 'soil': ref.requerimientos,
        'yield': float(ref.rendimiento_ton_ha) if ref.rendimiento_ton_ha is not None else None,
        'source': {'institution': ref.institucion_fuente, 'document': ref.documento_fuente,
                   'url': ref.url_fuente,
                   'consulted': ref.fecha_consulta_fuente.isoformat() if ref.fecha_consulta_fuente else ''},
    }


def semillas_payload():
    fichas = {}
    for ref in ReferenciaAgronomica.objects.filter(
        estado=ReferenciaAgronomica.Estado.VERIFICADA, cultivo__activo=True,
    ).select_related('cultivo', 'zona'):
        if ref.tiene_fuente_verificada:
            fichas.setdefault(ref.cultivo_id, []).append(_ficha(ref))
    cultivos = []
    for cultivo in Cultivo.objects.filter(activo=True).order_by('nombre'):
        respaldado = bool(cultivo.densidad_fuente and cultivo.densidad_url and cultivo.densidad_verificada)
        cultivos.append({
            'id': cultivo.pk, 'name': cultivo.nombre,
            'density': float(cultivo.densidad_siembra) if cultivo.densidad_siembra is not None else None,
            'unit': (cultivo.unidad_siembra or 'kg') + '/ha',
            'densityBacked': respaldado, 'densitySource': cultivo.densidad_fuente,
            'densityUrl': cultivo.densidad_url,
            'densityVerified': cultivo.densidad_verificada.isoformat() if cultivo.densidad_verificada else '',
            'yield': float(cultivo.rendimiento_ton_ha) if cultivo.rendimiento_ton_ha is not None else None,
            'references': referencias_siembra(cultivo.nombre),
            'sheets': fichas.get(cultivo.pk, []),
        })
    return {'crops': cultivos}
