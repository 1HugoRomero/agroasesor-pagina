"""Rangos de dosis de siembra con fuente institucional (INIA), leídos del catálogo único de ``backend_flask``.

Un solo catálogo para Django y la API: aquí no se copian ni inventan valores. Cada referencia indica si su dato
fue cotejado con la fuente (``cotejada_con_fuente``) o solo está citado (``citada_sin_cotejar``). Sin PyYAML o sin el
archivo, la calculadora sigue funcionando con la densidad del cultivo registrada en la base de datos.
"""
import unicodedata
from functools import lru_cache
from pathlib import Path

from django.conf import settings

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
