"""Datos de la calculadora de semillas: cultivos, referencias con fuente e información técnica verificada.

Nada se inventa: cada valor lleva su fuente y su estado. Lo que no tiene fuente verificada se muestra como
«sin dato verificado», y el cálculo sigue siendo posible como simulación con una dosis que escribe la persona.
"""
from .models import Cultivo, ReferenciaAgronomica
from .referencias import referencias_siembra

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
