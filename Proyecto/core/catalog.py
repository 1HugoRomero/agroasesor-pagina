from .models import Cultivo, Insumo, TipoInsumo, Zona, ReferenciaAgronomica, ProblemaAgricola


def _num(value):
    if value is None:
        return None
    return float(value)


def _product_problems(insumo):
    names = []
    for problem in insumo.problemas.all():
        if not problem.activo:
            continue
        crop_ids = {crop.pk for crop in problem.cultivos.all()}
        if crop_ids and insumo.cultivo_id and insumo.cultivo_id not in crop_ids:
            continue
        names.append(problem.nombre)
    return names


CATEGORY_KEYS = {
    'semilla': 'seed', 'semillas': 'seed',
    'fertilizante': 'fertilizer', 'fertilizantes': 'fertilizer', 'fertilizer': 'fertilizer',
    'enmienda': 'fertilizer', 'bioestimulante': 'other',
    'herbicida': 'herbicide', 'herbicidas': 'herbicide',
    'fungicida': 'fungicide', 'fungicidas': 'fungicide',
    'insecticida': 'insecticide', 'insecticidas': 'insecticide',
    'acaricida': 'insecticide', 'plaguicida': 'insecticide',
}
CATEGORY_LABELS = {
    'seed': 'Semillas',
    'fertilizer': 'Fertilizantes',
    'herbicide': 'Herbicidas',
    'fungicide': 'Fungicidas',
    'insecticide': 'Insecticidas y acaricidas',
    'other': 'Otros insumos agrícolas',
}


def category_key(type_name):
    return CATEGORY_KEYS.get((type_name or '').strip().casefold(), 'other')


def crop_varieties():
    varieties = {}
    for crop_id, variety in ReferenciaAgronomica.objects.exclude(
        estado=ReferenciaAgronomica.Estado.RETIRADA,
    ).exclude(variedad='').values_list('cultivo_id', 'variedad'):
        varieties.setdefault(str(crop_id), set()).add(variety)
    for crop_id, variety in Insumo.objects.exclude(cultivo=None).exclude(
        variedad_semilla='',
    ).values_list('cultivo_id', 'variedad_semilla'):
        varieties.setdefault(str(crop_id), set()).add(variety)
    return {key: sorted(values, key=str.casefold) for key, values in varieties.items()}


def catalog_payload():
    cultivos = list(Cultivo.objects.order_by('nombre'))
    insumos = list(
        Insumo.objects.select_related('tipo', 'cultivo', 'zona')
        .prefetch_related('problemas__cultivos')
        .order_by('nombre')
    )
    zonas = list(Zona.objects.order_by('nombre'))
    problems = list(ProblemaAgricola.objects.filter(activo=True).prefetch_related('cultivos'))
    regional_yields = [
        reference
        for reference in ReferenciaAgronomica.objects.filter(
            estado=ReferenciaAgronomica.Estado.VERIFICADA,
            cultivo__activo=True,
            zona__activo=True,
        ).select_related('cultivo', 'zona').order_by(
            'cultivo__nombre', 'zona__nombre', 'variedad',
        )
        if reference.tiene_fuente_verificada and reference.rendimiento_ton_ha is not None
    ]

    categories = [category_key(insumo.tipo.nombre) for insumo in insumos]
    return {
        'fromDb': True,
        'stats': {
            'crops': sum(1 for cultivo in cultivos if cultivo.activo),
            'zones': sum(1 for zona in zonas if zona.activo),
            'seeds': categories.count('seed'),
            'cropsWithDensity': sum(1 for cultivo in cultivos if cultivo.activo and cultivo.densidad_siembra is not None),
            'fertilizers': categories.count('fertilizer'),
            'otherInputs': len(categories) - categories.count('seed') - categories.count('fertilizer'),
            'products': len(insumos),
            'problems': len(problems),
            'inventoryTracked': False,
        },
        'categoryLabels': CATEGORY_LABELS,
        'varieties': crop_varieties(),
        'zonas': [
            {'id': str(zona.pk), 'name': zona.nombre, 'description': zona.descripcion, 'active': zona.activo}
            for zona in zonas
        ],
        'cultivos': [
            {
                'id': str(cultivo.pk),
                'name': cultivo.nombre,
                'description': cultivo.descripcion,
                'yield': _num(cultivo.rendimiento_ton_ha),
                'density': _num(cultivo.densidad_siembra),
                'unit': cultivo.unidad_siembra or 'kg',
                'densitySource': cultivo.densidad_fuente,
                'densityUrl': cultivo.densidad_url,
                'densityVerifiedAt': cultivo.densidad_verificada.isoformat() if cultivo.densidad_verificada else '',
                'yieldSource': cultivo.rendimiento_fuente,
                'yieldUrl': cultivo.rendimiento_url,
                'yieldVerifiedAt': cultivo.rendimiento_verificado.isoformat() if cultivo.rendimiento_verificado else '',
                'active': cultivo.activo,
            }
            for cultivo in cultivos
        ],
        'insumos': [
            {
                'id': str(insumo.pk),
                'name': insumo.nombre,
                'active': insumo.vigente_en,
                'usable': insumo.vigente_en and insumo.estado_verificacion not in {'restricted', 'cancelled'},
                'category': category_key(insumo.tipo.nombre),
                'categoryLabel': CATEGORY_LABELS[category_key(insumo.tipo.nombre)],
                'cropId': str(insumo.cultivo_id) if insumo.cultivo_id else '',
                'zoneId': str(insumo.zona_id) if insumo.zona_id else '',
                'problemIds': [str(problem.pk) for problem in insumo.problemas.all() if problem.activo],
                'applicationMode': insumo.modo_aplicacion,
                'crop': insumo.cultivo.nombre if insumo.cultivo else '',
                'type': insumo.tipo.nombre,
                'dose': _num(insumo.dosis_hectarea),
                'unit': insumo.unidad_dosis,
                'maxDose': _num(insumo.dosis_maxima_hectarea),
                'maxDoseUnit': insumo.unidad_dosis_maxima,
                'validFrom': insumo.vigencia_desde.isoformat() if insumo.vigencia_desde else '',
                'validUntil': insumo.vigencia_hasta.isoformat() if insumo.vigencia_hasta else '',
                'problems':_product_problems(insumo),
                'problem':next(iter(_product_problems(insumo)), ''),
                'zone': insumo.zona.nombre if insumo.zona else '',
                'description': insumo.descripcion,
                'manufacturer': insumo.fabricante,
                'verificationStatus': insumo.estado_verificacion,
                'verified': insumo.estado_verificacion == 'verified',
                'sourceName': insumo.fuente_nombre,
                'sourceUrl': insumo.fuente_url,
                'verifiedAt': insumo.fecha_verificacion.isoformat() if insumo.fecha_verificacion else '',
                'doseVerified': insumo.dosis_con_fuente,
                'doseSource': insumo.dosis_fuente,
                'labelUrl': insumo.etiqueta_url,
                'safetySheetUrl': insumo.hoja_seguridad_url,
                'activeIngredient': insumo.ingrediente_activo,
                'concentration': insumo.concentracion,
                'formulation': insumo.formulacion,
                'sagRegistration': insumo.numero_autorizacion_sag,
                'authorizedCrops': insumo.cultivos_autorizados,
                'controlTargets': insumo.objetivos_control,
                'restrictions': insumo.restricciones,
                'preharvestInterval': insumo.periodo_carencia,
                'reentryInterval': insumo.tiempo_reingreso,
                'environmentalPrecautions': insumo.precauciones_ambientales,
                'pollinatorWarning': insumo.advertencia_polinizadores,
                'packageAmount': _num(insumo.presentacion_cantidad),
                'packageUnit': insumo.presentacion_unidad,
                'nutrientComposition': insumo.composicion_nutricional,
                'nitrogenPct': _num(insumo.nitrogeno_pct),
                'phosphorusP2o5Pct': _num(insumo.fosforo_p2o5_pct),
                'potassiumK2oPct': _num(insumo.potasio_k2o_pct),
                'seedVariety': insumo.variedad_semilla,
                'seedType': insumo.tipo_semilla,
                'targetPlantsM2': _num(insumo.plantas_objetivo_m2),
                'thousandSeedWeightG': _num(insumo.peso_mil_semillas_g),
                'germinationPct': _num(insumo.germinacion_pct),
                'purityPct': _num(insumo.pureza_pct),
                'verifiedUse': insumo.uso_verificado,
            }
            for insumo in insumos
        ],
        'semillas': [
            {
                'id': str(cultivo.pk),
                'name': cultivo.nombre,
                'crop': cultivo.nombre,
                'density': _num(cultivo.densidad_siembra),
                'unit': cultivo.unidad_siembra or 'kg',
                'densitySource': cultivo.densidad_fuente,
                'densityUrl': cultivo.densidad_url,
                'densityVerifiedAt': cultivo.densidad_verificada.isoformat() if cultivo.densidad_verificada else '',
            }
            for cultivo in cultivos
            if cultivo.activo and cultivo.densidad_siembra is not None
        ],
        'yields': {
            cultivo.nombre: _num(cultivo.rendimiento_ton_ha)
            for cultivo in cultivos
            if cultivo.rendimiento_ton_ha is not None
        },
        'yieldReferences': {
            cultivo.nombre: {
                'rate':_num(cultivo.rendimiento_ton_ha),
                'source':cultivo.rendimiento_fuente,
                'url':cultivo.rendimiento_url,
                'verifiedAt':cultivo.rendimiento_verificado.isoformat() if cultivo.rendimiento_verificado else '',
            }
            for cultivo in cultivos
            if cultivo.rendimiento_ton_ha is not None
        },
        'regionalYieldReferences': [
            {
                'cropId':str(reference.cultivo_id),
                'crop':reference.cultivo.nombre,
                'zoneId':str(reference.zona_id),
                'zone':reference.zona.nombre,
                'variety':reference.variedad,
                'rate':_num(reference.rendimiento_ton_ha),
                'source':reference.institucion_fuente,
                'document':reference.documento_fuente,
                'url':reference.url_fuente,
                'verifiedAt':reference.fecha_consulta_fuente.isoformat(),
            }
            for reference in regional_yields
        ],
        'problemas':[
            {
                'id':str(problem.pk),
                'name':problem.nombre,
                'type':problem.tipo,
                'typeLabel':problem.get_tipo_display(),
                'symptoms':problem.sintomas,
                'sourceName':problem.fuente_nombre,
                'sourceUrl':problem.fuente_url,
                'description':problem.descripcion,
                'cropIds':[str(crop.pk) for crop in problem.cultivos.all()],
            }
            for problem in problems
        ],
    }
