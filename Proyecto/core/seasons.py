"""Asignación de cultivos a potreros por temporada, con trazabilidad.

El potrero conserva en sus campos ``cultivo``, ``variedad``, ``fecha_siembra`` y
``fecha_cosecha`` una *instantánea* del cultivo vigente, porque varios módulos
(dashboard, calculadoras y calendario) la leen directamente. El historial real
queda en ``TemporadaCultivo``: cada cambio de cultivo crea una temporada nueva y
las anteriores nunca se borran ni se sobrescriben.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Cultivo, PredioHistorial, Potrero, TemporadaCultivo


def agricultural_season_for(day):
    """Temporada agrícola chilena referencial: julio-junio (p. ej. 2026-2027)."""
    if day is None:
        return ''
    start = day.year if day.month >= 7 else day.year - 1
    return f'{start}-{start + 1}'


def current_season(plot):
    """Temporada más reciente del potrero, aunque esté cerrada."""
    return TemporadaCultivo.objects.filter(potrero=plot).select_related('cultivo').order_by('-creado', '-pk').first()


def season_payload(season):
    return {
        'id': season.pk,
        'cropId': season.cultivo_id,
        'crop': season.cultivo.nombre,
        'variety': season.variedad,
        'season': season.temporada_agricola,
        'sowingDate': season.fecha_siembra.isoformat() if season.fecha_siembra else '',
        'harvestDate': season.fecha_cosecha.isoformat() if season.fecha_cosecha else '',
        'status': season.estado,
        'statusLabel': season.get_estado_display(),
        'notes': season.observaciones,
        'created': season.creado.isoformat() if season.creado else '',
    }


def _preserve_legacy_crop(plot, user):
    """Si el potrero tenía un cultivo sin temporada, lo guarda antes del cambio."""
    if not plot.cultivo_id or plot.temporadas.exists():
        return None
    legacy = TemporadaCultivo(
        potrero=plot,
        cultivo=plot.cultivo,
        variedad=plot.variedad,
        temporada_agricola=agricultural_season_for(plot.fecha_siembra),
        fecha_siembra=plot.fecha_siembra,
        fecha_cosecha=plot.fecha_cosecha,
        estado=(
            TemporadaCultivo.Estado.SEMBRADA
            if plot.fecha_siembra and plot.fecha_siembra <= date.today()
            else TemporadaCultivo.Estado.PLANIFICADA
        ),
        observaciones=(
            'Registro conservado automáticamente desde los datos del potrero ' 'antes de asignar otro cultivo.'
        ),
    )
    # Se omite la validación de cultivo activo: es un dato histórico existente.
    legacy.save()
    return legacy


@transaction.atomic
def assign_crop(
    plot,
    user,
    *,
    crop,
    variety='',
    season_label='',
    sowing_date=None,
    harvest_date=None,
    status=TemporadaCultivo.Estado.PLANIFICADA,
    notes='',
    close_previous=True,
):
    """Crea una temporada nueva para ``plot`` y actualiza la instantánea del potrero.

    Lanza ``ValidationError`` con mensajes en español cuando los datos no son
    válidos. Nunca modifica temporadas anteriores salvo para cerrarlas cuando
    ``close_previous`` es verdadero y el usuario cambia de temporada.
    """
    plot = Potrero.objects.select_for_update().select_related('predio', 'cultivo').get(pk=plot.pk)
    if plot.predio.propietario_id != user.pk:
        raise ValidationError('El potrero no pertenece a tu cuenta.')
    if not isinstance(crop, Cultivo) or not crop.activo:
        raise ValidationError({'cultivo': 'Selecciona un cultivo activo del catálogo.'})
    variety = (variety or '').strip()
    notes = (notes or '').strip()
    season_label = (season_label or '').strip() or agricultural_season_for(sowing_date)

    previous_crop = plot.cultivo.nombre if plot.cultivo_id else 'Sin cultivo'
    _preserve_legacy_crop(plot, user)
    previous_open = list(
        plot.temporadas.exclude(estado__in=[TemporadaCultivo.Estado.CERRADA, TemporadaCultivo.Estado.COSECHADA])
    )

    season = TemporadaCultivo(
        potrero=plot,
        cultivo=crop,
        variedad=variety,
        temporada_agricola=season_label,
        fecha_siembra=sowing_date,
        fecha_cosecha=harvest_date,
        estado=status,
        observaciones=notes,
    )
    season.full_clean()
    season.save()

    closed = []
    if close_previous:
        for old in previous_open:
            # Solo se cambia el estado; fechas, cultivo y observaciones se conservan.
            TemporadaCultivo.objects.filter(pk=old.pk).update(estado=TemporadaCultivo.Estado.CERRADA)
            closed.append(old)

    plot.cultivo = crop
    plot.variedad = variety
    plot.fecha_siembra = sowing_date
    plot.fecha_cosecha = harvest_date
    plot.full_clean()
    plot.save()

    detail = [f'Cultivo: {previous_crop} → {crop.nombre}']
    if variety:
        detail.append(f'Variedad: {variety}')
    if season_label:
        detail.append(f'Temporada: {season_label}')
    if sowing_date:
        detail.append(f'Siembra: {sowing_date:%d/%m/%Y}')
    if harvest_date:
        detail.append(f'Cosecha prevista: {harvest_date:%d/%m/%Y}')
    detail.append(f'Estado: {season.get_estado_display()}')
    if closed:
        detail.append(f'{len(closed)} temporada(s) anterior(es) cerrada(s) sin borrar sus datos')
    PredioHistorial.objects.create(
        predio=plot.predio,
        potrero=plot,
        usuario=user,
        accion=PredioHistorial.Accion.CULTIVO_ASIGNADO,
        resumen=f'Se asignó un cultivo al potrero «{plot.nombre}»: ' + '; '.join(detail) + '.',
        superficie_anterior_ha=plot.superficie_ha,
        superficie_nueva_ha=plot.superficie_ha,
    )
    return season


@transaction.atomic
def update_current_dates(plot, user, season, *, sowing_date, harvest_date, status=None):
    """Actualiza fechas reales de la temporada vigente sin crear otra.

    Se usa cuando el agricultor registra desde el calendario las fechas de la
    temporada que ya tiene asignada. El cambio queda en el historial del predio.
    """
    plot = Potrero.objects.select_for_update().select_related('predio').get(pk=plot.pk)
    if plot.predio.propietario_id != user.pk or season.potrero_id != plot.pk:
        raise ValidationError('La temporada no pertenece a tu cuenta.')
    before = (season.fecha_siembra, season.fecha_cosecha, season.get_estado_display())
    season.fecha_siembra = sowing_date
    season.fecha_cosecha = harvest_date
    if status:
        season.estado = status
    if not season.temporada_agricola:
        season.temporada_agricola = agricultural_season_for(sowing_date)
    season.full_clean()
    season.save()
    latest = current_season(plot)
    if latest and latest.pk == season.pk:
        plot.fecha_siembra = sowing_date
        plot.fecha_cosecha = harvest_date
        plot.full_clean()
        plot.save()

    def fmt(value):
        return value.strftime('%d/%m/%Y') if value else 'Sin dato'

    PredioHistorial.objects.create(
        predio=plot.predio,
        potrero=plot,
        usuario=user,
        accion=PredioHistorial.Accion.POTRERO_ACTUALIZADO,
        resumen=(
            f'Fechas de la temporada {season.temporada_agricola or "sin rótulo"} de '
            f'«{season.cultivo.nombre}» actualizadas: siembra {fmt(before[0])} → '
            f'{fmt(season.fecha_siembra)}; cosecha {fmt(before[1])} → '
            f'{fmt(season.fecha_cosecha)}; estado {before[2]} → {season.get_estado_display()}.'
        ),
    )
    return season


def record_form_crop_change(plot, previous):
    """Conserva trazabilidad cuando el cultivo se cambia desde el formulario del potrero.

    ``previous`` es un diccionario con ``cultivo_id``, ``cultivo``, ``variedad``,
    ``fecha_siembra`` y ``fecha_cosecha`` anteriores al guardado (o ``None`` para
    un potrero nuevo). Solo crea temporadas; nunca borra ni modifica las existentes.
    """
    previous = previous or {}
    if plot.cultivo_id == previous.get('cultivo_id') or not plot.cultivo_id:
        return None
    if previous.get('cultivo_id') and not plot.temporadas.exists():
        TemporadaCultivo(
            potrero=plot,
            cultivo=previous['cultivo'],
            variedad=previous.get('variedad', ''),
            temporada_agricola=agricultural_season_for(previous.get('fecha_siembra')),
            fecha_siembra=previous.get('fecha_siembra'),
            fecha_cosecha=previous.get('fecha_cosecha'),
            estado=TemporadaCultivo.Estado.CERRADA,
            observaciones='Registro conservado automáticamente al cambiar el cultivo desde el formulario del potrero.',
        ).save()
    season = TemporadaCultivo(
        potrero=plot,
        cultivo=plot.cultivo,
        variedad=plot.variedad,
        temporada_agricola=agricultural_season_for(plot.fecha_siembra),
        fecha_siembra=plot.fecha_siembra,
        fecha_cosecha=plot.fecha_cosecha,
        estado=TemporadaCultivo.Estado.PLANIFICADA,
        observaciones='Temporada creada desde el formulario del potrero.',
    )
    season.save()
    return season
