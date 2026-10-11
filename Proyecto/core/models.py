from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Sum
from decimal import Decimal
import math
from .geometry import polygon_area, polygon_perimeter, polygon_geojson, coordinates_from_geojson, polygon_contains, polygons_overlap


class Zona(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Cultivo(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    descripcion = models.TextField(blank=True)
    rendimiento_ton_ha = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    densidad_siembra = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    unidad_siembra = models.CharField(max_length=20, default='kg')
    rendimiento_fuente = models.CharField(max_length=255, blank=True)
    rendimiento_url = models.URLField(blank=True)
    rendimiento_verificado = models.DateField(null=True, blank=True)
    densidad_fuente = models.CharField(max_length=255, blank=True)
    densidad_url = models.URLField(blank=True)
    densidad_verificada = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class TipoInsumo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre


class Insumo(models.Model):
    ESTADO_VERIFICACION = [
        ('unverified', 'Información no verificada'),
        ('verified', 'Verificado con fuente'),
        ('restricted', 'Restringido'),
        ('cancelled', 'Registro cancelado'),
    ]
    tipo = models.ForeignKey(TipoInsumo, on_delete=models.PROTECT, related_name='insumos')
    cultivo = models.ForeignKey(Cultivo, on_delete=models.SET_NULL, null=True, blank=True, related_name='insumos')
    zona = models.ForeignKey(Zona, on_delete=models.SET_NULL, null=True, blank=True, related_name='insumos')
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    dosis_hectarea = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    unidad_dosis = models.CharField(max_length=50, blank=True)
    vigente = models.BooleanField(default=True)
    fabricante = models.CharField(max_length=150, blank=True)
    estado_verificacion = models.CharField(max_length=12, choices=ESTADO_VERIFICACION, default='unverified')
    fuente_nombre = models.CharField(max_length=255, blank=True)
    fuente_url = models.URLField(blank=True)
    fecha_verificacion = models.DateField(null=True, blank=True)
    dosis_verificada = models.BooleanField(default=False)
    dosis_fuente = models.CharField(max_length=255, blank=True)
    etiqueta_url = models.URLField(blank=True)
    hoja_seguridad_url = models.URLField(blank=True)
    ingrediente_activo = models.CharField(max_length=255, blank=True)
    concentracion = models.CharField(max_length=100, blank=True)
    formulacion = models.CharField(max_length=100, blank=True)
    numero_autorizacion_sag = models.CharField(max_length=100, blank=True)
    cultivos_autorizados = models.JSONField(default=list, blank=True)
    objetivos_control = models.JSONField(default=list, blank=True)
    restricciones = models.TextField(blank=True)
    periodo_carencia = models.CharField(max_length=100, blank=True)
    tiempo_reingreso = models.CharField(max_length=100, blank=True)
    precauciones_ambientales = models.TextField(blank=True)
    advertencia_polinizadores = models.TextField(blank=True)
    presentacion_cantidad = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(Decimal('0.001'))])
    presentacion_unidad = models.CharField(max_length=50, blank=True)
    composicion_nutricional = models.CharField(max_length=255, blank=True)
    nitrogeno_pct = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    fosforo_p2o5_pct = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    potasio_k2o_pct = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    variedad_semilla = models.CharField(max_length=150, blank=True)
    tipo_semilla = models.CharField(max_length=100, blank=True)
    plantas_objetivo_m2 = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(Decimal('0.001'))])
    peso_mil_semillas_g = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(Decimal('0.001'))])
    germinacion_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100'))])
    pureza_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100'))])

    def clean(self):
        super().clean()
        errors = {}
        if self.estado_verificacion == 'verified':
            if not self.fuente_nombre or not self.fuente_url or not self.fecha_verificacion:
                errors['estado_verificacion'] = 'Registra una fuente y fecha de verificación antes de marcar el producto como verificado.'
            if self.es_fitosanitario and (
                not self.numero_autorizacion_sag
                or not self.etiqueta_url
                or not isinstance(self.cultivos_autorizados, list)
                or not self.cultivos_autorizados
                or not isinstance(self.objetivos_control, list)
                or not self.objetivos_control
            ):
                errors['estado_verificacion'] = 'Para verificar un plaguicida registra autorización, etiqueta, cultivo y objetivo de control.'
        if self.dosis_verificada:
            if not self.dosis_hectarea or self.dosis_hectarea <= 0 or not self.unidad_dosis:
                errors['dosis_verificada'] = 'Registra una dosis positiva y su unidad antes de verificarla.'
            if not self.dosis_fuente or not self.fuente_url or not self.fecha_verificacion:
                errors['dosis_verificada'] = 'Registra la fuente y fecha de verificación de la dosis.'
            if self.es_fitosanitario and self.unidad_dosis not in {'kg/ha', 'g/ha', 'L/ha', 'mL/ha'}:
                errors['unidad_dosis'] = 'La dosis fitosanitaria debe expresarse por hectárea en kg, g, L o mL.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.nombre

    @property
    def es_fitosanitario(self):
        return self.tipo.nombre.casefold() in {'herbicida', 'fungicida', 'insecticida', 'acaricida', 'plaguicida'}

    @property
    def dosis_con_fuente(self):
        return (
            self.vigente
            and self.estado_verificacion == 'verified'
            and self.dosis_verificada
            and self.dosis_hectarea is not None
            and self.dosis_hectarea > 0
            and bool(self.dosis_fuente)
            and bool(self.fuente_url)
            and bool(self.fecha_verificacion)
        )

    @property
    def uso_verificado(self):
        return (
            self.es_fitosanitario
            and self.dosis_con_fuente
            and bool(self.etiqueta_url)
            and bool(self.numero_autorizacion_sag)
            and bool(self.cultivo_id)
            and isinstance(self.cultivos_autorizados, list)
            and self.cultivo.nombre in self.cultivos_autorizados
            and isinstance(self.objetivos_control, list)
            and bool(self.objetivos_control)
            and self.unidad_dosis in {'kg/ha', 'g/ha', 'L/ha', 'mL/ha'}
        )


class Agricultor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='agricultor')
    nombre = models.CharField(max_length=150)
    rut = models.CharField(max_length=12, unique=True)
    telefono = models.CharField(max_length=20)
    comuna = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class Predio(models.Model):
    propietario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='predios')
    nombre = models.CharField(max_length=150)
    ubicacion = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)
    superficie_ha = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(Decimal('0.0001'))])
    latitud = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-85), MaxValueValidator(85)])
    longitud = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    geojson = models.JSONField(null=True, blank=True)
    zona = models.ForeignKey(Zona, on_delete=models.PROTECT, null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre', 'pk']
        constraints = [models.CheckConstraint(condition=models.Q(superficie_ha__gt=0), name='predio_superficie_positiva')]

    def clean(self):
        super().clean()
        if (self.latitud is None) != (self.longitud is None):
            raise ValidationError({'latitud': 'Completa ambas coordenadas o deja las dos vacías.'})
        if self.geojson:
            try:
                polygon_area(coordinates_from_geojson(self.geojson))
            except ValidationError as exc:
                raise ValidationError({'geojson': exc.messages})
        if self.pk and self.superficie_ha is not None:
            total = self.potreros.aggregate(total=Sum('superficie_ha'))['total'] or 0
            if self.superficie_ha < total:
                raise ValidationError({'superficie_ha': 'No puede ser menor que la superficie total de sus potreros.'})

    @property
    def superficie_m2(self):
        if not self.geojson:
            return None
        return polygon_area(coordinates_from_geojson(self.geojson))

    @property
    def perimetro_m(self):
        if not self.geojson:
            return None
        return polygon_perimeter(coordinates_from_geojson(self.geojson))

    def __str__(self):
        return self.nombre


class PredioHistorialQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Los registros históricos no se pueden modificar.')

    def delete(self):
        raise ValidationError('Los registros históricos no se pueden eliminar.')


class PredioHistorial(models.Model):
    class Accion(models.TextChoices):
        CREADO = 'created', 'Predio creado'
        ACTUALIZADO = 'updated', 'Datos del predio modificados'
        PERIMETRO = 'perimeter_updated', 'Perímetro modificado'
        SUPERFICIE = 'area_updated', 'Superficie modificada'
        POTRERO_CREADO = 'plot_created', 'Potrero creado'
        POTRERO_ACTUALIZADO = 'plot_updated', 'Potrero modificado'

    predio = models.ForeignKey(
        Predio,
        on_delete=models.PROTECT,
        related_name='historial',
    )
    potrero = models.ForeignKey(
        'Potrero',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='historial',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_predios',
    )
    accion = models.CharField(max_length=32, choices=Accion.choices)
    resumen = models.TextField()
    creado = models.DateTimeField(auto_now_add=True)
    geometria_anterior = models.JSONField(null=True, blank=True)
    geometria_nueva = models.JSONField(null=True, blank=True)
    superficie_anterior_ha = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    superficie_nueva_ha = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    objects = PredioHistorialQuerySet.as_manager()

    class Meta:
        ordering = ['-creado', '-pk']
        indexes = [
            models.Index(fields=['predio', '-creado'], name='predio_historial_fecha'),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Los registros históricos no se pueden modificar.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Los registros históricos no se pueden eliminar.')

    def __str__(self):
        return f'{self.get_accion_display()} · {self.predio}'


class Potrero(models.Model):
    predio = models.ForeignKey(Predio, on_delete=models.PROTECT, related_name='potreros')
    nombre = models.CharField(max_length=150)
    cultivo = models.ForeignKey(Cultivo, on_delete=models.PROTECT, null=True, blank=True, related_name='potreros')
    variedad = models.CharField(max_length=150, blank=True)
    fecha_siembra = models.DateField(null=True, blank=True)
    fecha_cosecha = models.DateField(null=True, blank=True)
    superficie_ha = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(Decimal('0.0001'))])
    perimetro = models.JSONField(default=list, blank=True)
    geojson = models.JSONField(null=True, blank=True)
    latitud = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-85), MaxValueValidator(85)])
    longitud = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre', 'pk']
        constraints = [models.CheckConstraint(condition=models.Q(superficie_ha__gt=0), name='potrero_superficie_positiva')]

    def clean(self):
        super().clean()
        errors = {}
        if self.perimetro:
            try:
                self.superficie_ha = (polygon_area(self.perimetro) / Decimal('10000')).quantize(Decimal('0.0001'))
            except ValidationError as exc:
                errors['perimetro'] = exc.messages
        elif self.perimetro != []:
            errors['perimetro'] = 'Usa una lista vacía cuando no haya perímetro.'
        if (self.latitud is None) != (self.longitud is None):
            errors['latitud'] = 'Completa ambas coordenadas o deja las dos vacías.'
        if any(v is not None and not math.isfinite(v) for v in (self.latitud, self.longitud)):
            errors['latitud'] = 'Las coordenadas deben ser finitas.'
        if self.fecha_siembra and self.fecha_cosecha and self.fecha_cosecha < self.fecha_siembra:
            errors['fecha_cosecha'] = 'La cosecha no puede ser anterior a la siembra.'
        if self.cultivo_id and not self.cultivo.activo:
            errors['cultivo'] = 'Selecciona un cultivo activo.'
        if self.predio_id and self.superficie_ha is not None:
            total = self.predio.potreros.exclude(pk=self.pk).aggregate(total=Sum('superficie_ha'))['total'] or 0
            if self.superficie_ha + total > self.predio.superficie_ha:
                errors['superficie_ha'] = 'Los potreros no pueden superar la superficie del predio.'
        if self.perimetro and self.predio_id:
            predio = self.predio
            if predio.geojson:
                try:
                    boundary = coordinates_from_geojson(predio.geojson)
                    if not polygon_contains(boundary, self.perimetro):
                        errors['perimetro'] = 'El perímetro del potrero debe quedar dentro del predio.'
                except ValidationError as exc:
                    errors['perimetro'] = exc.messages
            if not errors.get('perimetro'):
                for sibling in Potrero.objects.filter(predio=predio).exclude(pk=self.pk).exclude(perimetro=[]):
                    if polygons_overlap(self.perimetro, sibling.perimetro):
                        errors['perimetro'] = 'El potrero se superpone con otro potrero de este predio.'
                        break
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.geojson = polygon_geojson(self.perimetro)
        super().save(*args, **kwargs)

    @property
    def perimetro_m(self):
        return polygon_perimeter(self.perimetro) if self.perimetro else None

    @property
    def superficie_m2(self):
        return self.superficie_ha * Decimal('10000')

    def __str__(self):
        return f'{self.predio} · {self.nombre}'


class ActividadAgricola(models.Model):
    class Tipo(models.TextChoices):
        PREPARACION = 'preparacion', 'Preparación'
        SIEMBRA = 'siembra', 'Siembra'
        FERTILIZACION = 'fertilizacion', 'Fertilización'
        RIEGO = 'riego', 'Riego'
        MONITOREO = 'monitoreo', 'Monitoreo'
        CONTROL_FITOSANITARIO = 'control_fitosanitario', 'Control fitosanitario'
        COSECHA = 'cosecha', 'Cosecha'
        OTRA = 'otra', 'Otra'

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        COMPLETADA = 'completada', 'Completada'
        CANCELADA = 'cancelada', 'Cancelada'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='actividades_agricolas',
    )
    potrero = models.ForeignKey(
        Potrero,
        on_delete=models.CASCADE,
        related_name='actividades',
    )
    nombre = models.CharField(max_length=180)
    tipo = models.CharField(max_length=32, choices=Tipo.choices)
    fecha_programada = models.DateField()
    estado = models.CharField(
        max_length=12,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    observaciones = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fecha_programada', 'pk']
        indexes = [
            models.Index(
                fields=['usuario', 'estado', 'fecha_programada'],
                name='actividad_usuario_estado_fecha',
            ),
        ]

    def clean(self):
        super().clean()
        if self.usuario_id and self.potrero_id:
            if self.potrero.predio.propietario_id != self.usuario_id:
                raise ValidationError({
                    'potrero': 'Selecciona un potrero de tu cuenta.',
                })

    def __str__(self):
        return f'{self.nombre} · {self.potrero}'
