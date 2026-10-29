"""Estadísticas del panel de administración (RF-26), calculadas solo con datos que ya existen.

No hay tablas nuevas ni cifras inventadas: todo sale de lo que los agricultores registraron.

Importante: el sistema guarda los CÁLCULOS que el agricultor ejecuta con un potrero (dosis, cobertura,
semillas, nutrición, rendimiento). Las simples CONSULTAS (abrir una ficha, mirar el calendario o el
catálogo) no se guardan en ninguna parte, por eso aquí nunca se presentan como si fueran consultas.
"""
from collections import Counter

from django.contrib.auth import get_user_model

from .models import ActividadAgricola, CalculoAgricola, Cultivo, Insumo, Potrero, Predio, TemporadaCultivo


def _texto(valor):
    return valor.strip() if isinstance(valor, str) and valor.strip() else ''


def _ranking(contador, limite):
    total = sum(contador.values())
    filas = []
    for nombre, cantidad in contador.most_common(limite):
        filas.append({'nombre': nombre, 'cantidad': cantidad, 'porcentaje': round(cantidad * 100 / total) if total else 0})
    return filas


def resumen_administrador(limite=5):
    usuarios = get_user_model().objects
    cultivos_en_calculos = Counter()
    insumos_en_calculos = Counter()
    cantidad_por_operacion = Counter()
    calculos_sin_cultivo = calculos_sin_insumo = 0

    nombres_insumo = dict(Insumo.objects.values_list('pk', 'nombre'))
    for calculo in CalculoAgricola.objects.only('operacion', 'entrada', 'resultado').iterator():
        entrada = calculo.entrada if isinstance(calculo.entrada, dict) else {}
        resultado = calculo.resultado if isinstance(calculo.resultado, dict) else {}
        cantidad_por_operacion[calculo.operacion] += 1

        cultivo = _texto(resultado.get('crop')) or _texto(entrada.get('crop'))
        if cultivo:
            cultivos_en_calculos[cultivo] += 1
        else:
            calculos_sin_cultivo += 1

        insumo = _texto(resultado.get('product'))
        if not insumo:
            identificador = str(entrada.get('product_id') or '')
            insumo = nombres_insumo.get(int(identificador), '') if identificador.isdigit() else ''
        if insumo:
            insumos_en_calculos[insumo] += 1
        else:
            calculos_sin_insumo += 1

    etiquetas = dict(CalculoAgricola.Operacion.choices)
    por_operacion = [
        {'nombre': etiquetas.get(clave, clave), 'cantidad': cantidad}
        for clave, cantidad in cantidad_por_operacion.most_common()
    ]
    actividades = ActividadAgricola.objects
    por_estado = {estado: actividades.filter(estado=estado).count() for estado, _ in ActividadAgricola.Estado.choices}

    return {
        'agricultores': usuarios.filter(is_staff=False).count(),
        'administradores': usuarios.filter(is_staff=True).count(),
        'predios': Predio.objects.count(),
        'potreros': Potrero.objects.count(),
        'cultivos_catalogo': Cultivo.objects.filter(activo=True).count(),
        'potreros_con_cultivo': Potrero.objects.filter(cultivo__isnull=False).count(),
        'temporadas': TemporadaCultivo.objects.count(),
        'calculos': sum(cantidad_por_operacion.values()),
        'calculos_por_operacion': por_operacion,
        'cultivos_mas_usados': _ranking(cultivos_en_calculos, limite),
        'insumos_mas_usados': _ranking(insumos_en_calculos, limite),
        'calculos_sin_cultivo': calculos_sin_cultivo,
        'calculos_sin_insumo': calculos_sin_insumo,
        'actividades': actividades.count(),
        'actividades_pendientes': por_estado.get(ActividadAgricola.Estado.PENDIENTE, 0),
        'actividades_completadas': por_estado.get(ActividadAgricola.Estado.COMPLETADA, 0),
        'actividades_canceladas': por_estado.get(ActividadAgricola.Estado.CANCELADA, 0),
    }
