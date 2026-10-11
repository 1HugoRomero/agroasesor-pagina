from django.contrib import admin

from .models import ActividadAgricola, Cultivo, Insumo, TipoInsumo, Zona, Agricultor, Predio, PredioHistorial, Potrero


@admin.register(Zona)
class ZonaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    search_fields = ('nombre',)


@admin.register(Cultivo)
class CultivoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'rendimiento_ton_ha', 'densidad_siembra', 'unidad_siembra', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)
    fieldsets = (
        (None, {'fields': ('nombre', 'descripcion', 'activo')}),
        ('Parámetros de referencia (no son recomendaciones)', {'fields': (
            'rendimiento_ton_ha', 'rendimiento_fuente', 'rendimiento_url', 'rendimiento_verificado',
            'densidad_siembra', 'unidad_siembra', 'densidad_fuente', 'densidad_url', 'densidad_verificada',
        )}),
    )


@admin.register(TipoInsumo)
class TipoInsumoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'cultivo', 'estado_verificacion', 'fecha_verificacion', 'vigente')
    list_filter = ('tipo', 'estado_verificacion', 'vigente', 'dosis_verificada')
    search_fields = ('nombre', 'fabricante', 'numero_autorizacion_sag', 'ingrediente_activo')
    fieldsets = (
        (None, {'fields': ('nombre', 'tipo', 'cultivo', 'zona', 'descripcion', 'fabricante', 'vigente')}),
        ('Verificación y trazabilidad', {'fields': (
            'estado_verificacion', 'fuente_nombre', 'fuente_url', 'fecha_verificacion',
            'dosis_hectarea', 'unidad_dosis', 'dosis_verificada', 'dosis_fuente',
        )}),
        ('Documentación y plaguicidas', {'fields': (
            'numero_autorizacion_sag', 'ingrediente_activo', 'concentracion', 'formulacion',
            'cultivos_autorizados', 'objetivos_control', 'etiqueta_url', 'hoja_seguridad_url',
            'restricciones', 'periodo_carencia', 'tiempo_reingreso',
            'precauciones_ambientales', 'advertencia_polinizadores',
        )}),
        ('Composición y presentación de fertilizantes', {'fields': (
            'composicion_nutricional', 'nitrogeno_pct', 'fosforo_p2o5_pct', 'potasio_k2o_pct',
            'presentacion_cantidad', 'presentacion_unidad',
        )}),
        ('Datos documentados de semillas', {'fields': (
            'variedad_semilla', 'tipo_semilla', 'plantas_objetivo_m2', 'peso_mil_semillas_g',
            'germinacion_pct', 'pureza_pct',
        )}),
    )


@admin.register(Agricultor)
class AgricultorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'comuna', 'user')
    search_fields = ('nombre', 'rut', 'user__email')


@admin.register(Predio)
class PredioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'propietario', 'superficie_ha', 'zona')
    search_fields = ('nombre', 'ubicacion')


@admin.register(PredioHistorial)
class PredioHistorialAdmin(admin.ModelAdmin):
    list_display = ('predio', 'potrero', 'accion', 'usuario', 'creado')
    list_filter = ('accion', 'creado')
    search_fields = ('predio__nombre', 'resumen', 'usuario__email')
    readonly_fields = (
        'predio', 'potrero', 'usuario', 'accion', 'resumen', 'creado',
        'geometria_anterior', 'geometria_nueva',
        'superficie_anterior_ha', 'superficie_nueva_ha',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Potrero)
class PotreroAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'predio', 'cultivo', 'superficie_ha')
    list_filter = ('cultivo',)
    search_fields = ('nombre', 'predio__nombre')


@admin.register(ActividadAgricola)
class ActividadAgricolaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'potrero', 'usuario', 'fecha_programada', 'estado')
    list_filter = ('tipo', 'estado', 'fecha_programada')
    search_fields = ('nombre', 'potrero__nombre', 'potrero__predio__nombre', 'usuario__email')
