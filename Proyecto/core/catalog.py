from .models import Cultivo, Insumo, TipoInsumo, Zona


def _num(value):
    if value is None:
        return None
    return float(value)


def catalog_payload():
    cultivos = list(Cultivo.objects.order_by('nombre'))
    insumos = list(Insumo.objects.select_related('tipo', 'cultivo', 'zona').order_by('nombre'))
    zonas = list(Zona.objects.order_by('nombre'))

    return {
        'fromDb': True,
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
                'active': insumo.vigente,
                'crop': insumo.cultivo.nombre if insumo.cultivo else '',
                'type': insumo.tipo.nombre,
                'dose': _num(insumo.dosis_hectarea),
                'unit': insumo.unidad_dosis,
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
    }
