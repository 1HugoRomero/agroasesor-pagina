import json
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.db import IntegrityError, transaction
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from .catalog import catalog_payload
from .forms import ActividadAgricolaForm, COMUNAS, RegistroForm, PredioForm, PotreroForm
from .models import ActividadAgricola, Predio, PredioHistorial, Potrero, Agricultor, Cultivo, Insumo, Zona

NAV_GROUPS = [
    ('El campo', [('dashboard', 'Hoy', 'layout-dashboard'), ('predios', 'Mis predios y potreros', 'map'), ('calendario', 'Siembra', 'calendar-days')]),
    ('La decisión', [('decisiones', 'Centro de decisiones', 'sprout')]),
    ('Cierre', [('busqueda', 'Buscar', 'search'), ('reportes', 'Reporte', 'file-text'), ('admin_panel', 'Administración', 'shield-check')]),
]

def map_config():
    return {'tile_url':settings.MAP_TILE_URL, 'attribution':settings.MAP_TILE_ATTRIBUTION}


def farm_payload(user):
    predios = list(
        Predio.objects.filter(propietario=user)
        .annotate(potreros_count=Count('potreros'))
    )
    plots = list(
        Potrero.objects.filter(predio__propietario=user)
        .select_related('predio', 'cultivo')
    )
    assigned_by_farm = {}
    for plot in plots:
        assigned_by_farm[plot.predio_id] = (
            assigned_by_farm.get(plot.predio_id, Decimal('0')) + plot.superficie_ha
        )
    total_farm_area = sum(
        (predio.superficie_ha for predio in predios),
        Decimal('0'),
    )
    assigned_area = sum(
        (plot.superficie_ha for plot in plots),
        Decimal('0'),
    )
    unassigned_area = sum(
        (
            max(Decimal('0'), predio.superficie_ha - assigned_by_farm.get(predio.pk, Decimal('0')))
            for predio in predios
        ),
        Decimal('0'),
    )
    crop_count = Potrero.objects.filter(
        predio__propietario=user,
        cultivo__activo=True,
    ).values('cultivo_id').distinct().count()
    distribution_pct = (
        assigned_area / total_farm_area * 100
        if total_farm_area
        else Decimal('0')
    )
    return {
        'predios': [{'id':str(p.pk), 'name':p.nombre, 'location':p.ubicacion, 'area':float(p.superficie_ha),
                     'plotCount':p.potreros_count,
                     'updated':timezone.localtime(p.actualizado).strftime('%d/%m/%Y'),
                     'lat':p.latitud, 'lng':p.longitud, 'geojson':p.geojson,
                     'perimeterM':float(p.perimetro_m) if p.perimetro_m is not None else None,
                     'detailUrl':reverse('predio_detail', kwargs={'pk':p.pk}),
                     'editUrl':reverse('predio_edit', kwargs={'pk':p.pk}),
                     'potreroCreateUrl':reverse('potrero_create', kwargs={'predio_pk':p.pk})} for p in predios],
        'plots': [{'id':str(p.pk), 'predio':str(p.predio_id), 'farmName':p.predio.nombre,
                   'name':p.nombre, 'crop':p.cultivo.nombre if p.cultivo else '',
                   'variety':p.variedad, 'sowing':p.fecha_siembra.isoformat() if p.fecha_siembra else '',
                   'harvest':p.fecha_cosecha.isoformat() if p.fecha_cosecha else '', 'areaHa':float(p.superficie_ha),
                   'areaM2':float(p.superficie_ha * Decimal('10000')),
                   'perimeterM':float(p.perimetro_m) if p.perimetro_m is not None else None,
                   'coordinates':p.perimetro, 'geojson':p.geojson, 'lat':p.latitud, 'lng':p.longitud,
                   'created':timezone.localtime(p.creado).strftime('%d/%m/%Y'),
                   'updated':timezone.localtime(p.actualizado).strftime('%d/%m/%Y'),
                   'status':(
                       'Planificado' if p.cultivo_id and p.cultivo.activo
                       else 'Sin cultivo activo' if p.cultivo_id
                       else 'Sin cultivo'
                   ),
                   'editUrl':reverse('potrero_edit', kwargs={'predio_pk':p.predio_id, 'pk':p.pk}),
                   'detailUrl':(
                       reverse('predio_detail', kwargs={'pk':p.predio_id})
                       + f'?potrero={p.pk}#predio-history'
                   )} for p in plots],
        'stats': {
            'predios':len(predios),
            'potreros':len(plots),
            'superficie_predios':float(total_farm_area),
            'superficie':float(assigned_area),
            'superficie_sin_asignar':float(unassigned_area),
            'distribucion_pct':float(distribution_pct),
            'distribucion_bar_pct':float(min(Decimal('100'), max(Decimal('0'), distribution_pct))),
            'sobreasignada':assigned_area > total_farm_area,
            'cultivos':crop_count,
        },
    }


def _page(request, template, current, extra=None):
    if not request.user.is_authenticated:
        return redirect('login')
    if current == 'admin_panel' and not request.user.is_staff:
        raise PermissionDenied
    extra = extra or {}
    name = request.user.get_full_name() or request.user.username
    context = {
        'user': {'name':name, 'email':request.user.email, 'role':'Administrador' if request.user.is_staff else 'Agricultor'},
        'first_name':name.split()[0], 'initials':''.join(p[0] for p in name.split()[:2]).upper(),
        'nav_groups':NAV_GROUPS, 'current':current, 'query':request.GET.get('q',''),
        'catalog':catalog_payload(),
        'farm_data':extra.get('farm_data') or farm_payload(request.user),
        'pending_activities':ActividadAgricola.objects.filter(
            usuario=request.user,
            estado=ActividadAgricola.Estado.PENDIENTE,
        ).select_related('potrero', 'potrero__predio').order_by('fecha_programada', 'pk')[:5],
        'phase_a':current in {'dashboard','predios','calendario','admin_panel'},
    }
    context.update(extra)
    response = render(request, template, context)
    add_never_cache_headers(response)
    return response


def index(request):
    return render(request, 'index.html')


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    mode = request.POST.get('mode') or request.GET.get('mode') or 'login'
    if mode in {'recover', 'reset'}:
        return redirect('password_reset')
    mode = 'register' if mode == 'register' else 'login'
    error = ''
    data = {key:(request.POST.get(key) or '').strip() for key in ['email','name','rut','phone','comuna']}
    data['comuna'] = data['comuna'] or 'Melipilla'
    registration = RegistroForm(request.POST or None)
    if request.method == 'POST':
        if mode == 'register':
            if registration.is_valid():
                try:
                    user = registration.save()
                except IntegrityError:
                    error = 'El correo o RUT ya está registrado.'
                else:
                    login(request, user, backend='core.auth.EmailBackend')
                    return redirect('dashboard')
            else:
                error = ' '.join(f'{registration.fields[field].label or field}: {msg}' if field in registration.fields else str(msg) for field, errors in registration.errors.items() for msg in errors)
        else:
            user = authenticate(request, username=data['email'].lower(), password=request.POST.get('password',''))
            if user is None:
                error = 'Correo o contraseña incorrectos.'
            else:
                login(request, user)
                return redirect('dashboard')
    return render(request, 'login.html', {
        'mode':mode, 'error':error, 'form':data, 'comunas':COMUNAS,
        'headline':'Administra los datos reales de tu campo.' if mode == 'login' else 'Registra tu cuenta de agricultor.',
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
@require_POST
def enter_as_admin(request):
    if not request.user.is_staff:
        raise PermissionDenied
    return redirect('admin_panel')


@login_required
def dashboard(request):
    farm_data = farm_payload(request.user)
    pending = ActividadAgricola.objects.filter(
        usuario=request.user,
        potrero__predio__propietario=request.user,
        estado=ActividadAgricola.Estado.PENDIENTE,
    ).select_related('potrero', 'potrero__predio').order_by('fecha_programada', 'pk')
    return _page(request, 'dashboard.html', 'dashboard', {
        'farm_data':farm_data,
        'dashboard_predios':farm_data['predios'],
        'dashboard_plots':farm_data['plots'],
        'dashboard_activities':pending[:5],
        'pending_activity_count':pending.count(),
    })


def _activities_for_user(user):
    return ActividadAgricola.objects.filter(
        usuario=user,
    ).select_related('potrero', 'potrero__predio', 'potrero__cultivo')


@login_required
def activity_list(request):
    return _page(
        request,
        'activity_list.html',
        'calendario',
        {'activities':_activities_for_user(request.user)},
    )


@login_required
def activity_create(request):
    form = ActividadAgricolaForm(
        request.POST or None,
        user=request.user,
        instance=ActividadAgricola(usuario=request.user),
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'La actividad quedó guardada y aparecerá en Hoy y Siembra.')
        return redirect('calendario')
    return _page(request, 'activity_form.html', 'calendario', {
        'form':form,
        'heading':'Registrar actividad agrícola',
    })


@login_required
def activity_detail(request, pk):
    activity = get_object_or_404(
        _activities_for_user(request.user),
        pk=pk,
    )
    return _page(request, 'activity_detail.html', 'calendario', {
        'activity':activity,
    })


@login_required
def activity_edit(request, pk):
    activity = get_object_or_404(
        _activities_for_user(request.user),
        pk=pk,
    )
    form = ActividadAgricolaForm(
        request.POST or None,
        user=request.user,
        instance=activity,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'La actividad fue actualizada.')
        return redirect('actividad_detail', pk=activity.pk)
    return _page(request, 'activity_form.html', 'calendario', {
        'form':form,
        'heading':'Editar actividad agrícola',
        'activity':activity,
    })


@login_required
@require_POST
def activity_change_status(request, pk):
    activity = get_object_or_404(
        _activities_for_user(request.user),
        pk=pk,
    )
    new_status = request.POST.get('estado', '')
    if new_status not in ActividadAgricola.Estado.values:
        messages.error(request, 'Selecciona un estado válido para la actividad.')
        return redirect('actividad_detail', pk=activity.pk)
    activity.estado = new_status
    activity.save(update_fields=['estado', 'actualizado'])
    messages.success(request, 'El estado de la actividad fue actualizado.')
    destination = request.POST.get('next')
    if destination == 'dashboard':
        return redirect('dashboard')
    if destination == 'calendario':
        return redirect('calendario')
    return redirect('actividad_detail', pk=activity.pk)


@login_required
def activity_delete(request, pk):
    activity = get_object_or_404(
        _activities_for_user(request.user),
        pk=pk,
    )
    if request.method == 'POST':
        activity.delete()
        messages.success(request, 'La actividad fue eliminada.')
        return redirect('calendario')
    return _page(request, 'activity_confirm_delete.html', 'calendario', {
        'activity':activity,
    })


@login_required
def predios(request):
    predios_list = Predio.objects.filter(propietario=request.user).annotate(
        potreros_count=Count('potreros'),
    ).prefetch_related('potreros__cultivo')
    selected_predio_id = request.GET.get('predio', '')
    if selected_predio_id:
        selected_predio = get_object_or_404(
            Predio,
            pk=selected_predio_id,
            propietario=request.user,
        )
    else:
        selected_predio = None

    potrero_queryset = Potrero.objects.filter(
        predio__propietario=request.user,
    ).select_related('predio', 'cultivo')
    search_term = request.GET.get('q', '').strip()
    filter_predio = request.GET.get('filtro_predio', '').strip()
    filter_cultivo = request.GET.get('cultivo', '').strip()
    sort_by = request.GET.get('orden', '-creado')
    if search_term:
        potrero_queryset = potrero_queryset.filter(nombre__icontains=search_term)
    if filter_predio:
        potrero_queryset = potrero_queryset.filter(predio_id=filter_predio)
    if filter_cultivo:
        potrero_queryset = potrero_queryset.filter(cultivo_id=filter_cultivo)
    ordering = {
        'creado': 'creado',
        '-creado': '-creado',
        'actualizado': 'actualizado',
        '-actualizado': '-actualizado',
        'nombre': 'nombre',
        '-nombre': '-nombre',
    }
    potrero_queryset = potrero_queryset.order_by(ordering.get(sort_by, '-creado'), 'pk')
    history_page = Paginator(potrero_queryset, 25).get_page(request.GET.get('pagina'))
    crop_options = Cultivo.objects.filter(
        potreros__predio__propietario=request.user,
    ).distinct().order_by('nombre')
    return _page(request, 'predios.html', 'predios', {
        'predios_list':predios_list,
        'selected_predio':selected_predio,
        'selected_predio_id':str(selected_predio.pk) if selected_predio else '',
        'potrero_history_page':history_page,
        'crop_options':crop_options,
        'terrain_filters':{
            'q':search_term,
            'predio':filter_predio,
            'cultivo':filter_cultivo,
            'orden':sort_by,
        },
        'maps_config':map_config(),
    })


@login_required
def predio_detail(request, pk):
    predio = get_object_or_404(
        Predio.objects.prefetch_related('potreros__cultivo', 'historial__usuario'),
        pk=pk,
        propietario=request.user,
    )
    potreros = predio.potreros.all()
    selected_potrero_id = request.GET.get('potrero', '').strip()
    selected_potrero = None
    historial = predio.historial.select_related('usuario', 'potrero')
    if selected_potrero_id:
        selected_potrero = get_object_or_404(
            potreros,
            pk=selected_potrero_id,
        )
        historial = historial.filter(potrero=selected_potrero)
    superficie_utilizada = potreros.aggregate(total=Sum('superficie_ha'))['total'] or Decimal('0')
    return _page(request, 'predio_detail.html', 'predios', {
        'predio':predio,
        'potreros':potreros,
        'historial':historial,
        'selected_potrero':selected_potrero,
        'superficie_utilizada':superficie_utilizada,
        'superficie_restante':max(Decimal('0'), predio.superficie_ha - superficie_utilizada),
        'cultivos':Cultivo.objects.filter(potreros__predio=predio).distinct(),
        'maps_config':map_config(),
    })


@login_required
@transaction.atomic
def predio_form(request, pk=None):
    instance = get_object_or_404(Predio, pk=pk, propietario=request.user) if pk else Predio(propietario=request.user)
    original = None
    if instance.pk:
        original = {
            'nombre':instance.nombre,
            'descripcion':instance.descripcion,
            'ubicacion':instance.ubicacion,
            'observaciones':instance.observaciones,
            'zona_id':instance.zona_id,
            'zona':instance.zona.nombre if instance.zona_id else 'Sin zona',
            'superficie_ha':instance.superficie_ha,
            'geojson':instance.geojson,
        }
    form = PredioForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        geometry = form.cleaned_data.get('geojson')
        if not original and not geometry:
            form.add_error('geojson', 'Dibuja y acepta el perímetro para registrar el predio.')
        elif not original and not form.cleaned_data.get('perimetro_aceptado'):
            form.add_error('perimetro_aceptado', 'Acepta el perímetro antes de registrar el predio.')
        elif original and geometry != original['geojson'] and not form.cleaned_data.get('perimetro_aceptado'):
            form.add_error('perimetro_aceptado', 'Acepta el nuevo perímetro antes de guardar.')
        if form.errors:
            pass
        else:
            predio = form.save(commit=False)
            predio.propietario = request.user
            predio.save()
            if original is None:
                PredioHistorial.objects.create(
                    predio=predio,
                    usuario=request.user,
                    accion=PredioHistorial.Accion.CREADO,
                    resumen=f'Predio creado con una superficie de {predio.superficie_ha} ha.',
                    geometria_nueva=predio.geojson,
                    superficie_nueva_ha=predio.superficie_ha,
                )
            else:
                geometry_changed = predio.geojson != original['geojson']
                area_changed = predio.superficie_ha != original['superficie_ha']
                metadata_changed = any(
                    getattr(predio, field) != original[field]
                    for field in ('nombre', 'descripcion', 'ubicacion', 'observaciones', 'zona_id')
                )
                metadata_labels = {
                    'nombre': 'Nombre',
                    'descripcion': 'Descripción',
                    'ubicacion': 'Ubicación',
                    'observaciones': 'Observaciones',
                    'zona_id': 'Zona',
                }
                metadata_changes = [
                    f'{metadata_labels[field]}: '
                    f'{original["zona"] if field == "zona_id" else (original[field] or "Sin dato")} → '
                    f'{(predio.zona.nombre if predio.zona_id else "Sin zona") if field == "zona_id" else (getattr(predio, field) or "Sin dato")}'
                    for field in metadata_labels
                    if getattr(predio, field) != original[field]
                ]
                if geometry_changed:
                    PredioHistorial.objects.create(
                        predio=predio,
                        usuario=request.user,
                        accion=PredioHistorial.Accion.PERIMETRO,
                        resumen=(
                            f'Perímetro actualizado; superficie: {original["superficie_ha"]} ha '
                            f'→ {predio.superficie_ha} ha.'
                        ),
                        geometria_anterior=original['geojson'],
                        geometria_nueva=predio.geojson,
                        superficie_anterior_ha=original['superficie_ha'],
                        superficie_nueva_ha=predio.superficie_ha,
                    )
                elif area_changed:
                    PredioHistorial.objects.create(
                        predio=predio,
                        usuario=request.user,
                        accion=PredioHistorial.Accion.SUPERFICIE,
                        resumen=(
                            f'Superficie actualizada de {original["superficie_ha"]} ha '
                            f'a {predio.superficie_ha} ha.'
                        ),
                        superficie_anterior_ha=original['superficie_ha'],
                        superficie_nueva_ha=predio.superficie_ha,
                    )
                if metadata_changed:
                    PredioHistorial.objects.create(
                        predio=predio,
                        usuario=request.user,
                        accion=PredioHistorial.Accion.ACTUALIZADO,
                        resumen='Se actualizaron los datos del predio: ' + '; '.join(metadata_changes) + '.',
                        geometria_anterior=original['geojson'] if geometry_changed else None,
                        geometria_nueva=predio.geojson if geometry_changed else None,
                        superficie_anterior_ha=original['superficie_ha'] if area_changed else None,
                        superficie_nueva_ha=predio.superficie_ha if area_changed else None,
                    )
            messages.success(request, 'El predio quedó guardado correctamente.')
            return redirect('predio_detail', pk=predio.pk)
    return _page(request, 'terreno_form.html', 'predios', {
        'form':form, 'heading':'Editar predio' if pk else 'Registrar predio',
        'is_predio':True, 'maps_config':map_config(),
        'registration_open':bool(request.method == 'POST' and form.errors),
    })


@login_required
@transaction.atomic
def potrero_form(request, predio_pk, pk=None):
    predio = get_object_or_404(Predio.objects.select_for_update(), pk=predio_pk, propietario=request.user)
    instance = get_object_or_404(Potrero, pk=pk, predio=predio) if pk else Potrero(predio=predio)
    used_area_query = predio.potreros.all()
    if instance.pk:
        used_area_query = used_area_query.exclude(pk=instance.pk)
    used_area = used_area_query.aggregate(total=Sum('superficie_ha'))['total'] or Decimal('0')
    available_area = max(Decimal('0'), predio.superficie_ha - used_area)
    original = None
    if instance.pk:
        original = {
            'nombre':instance.nombre,
            'superficie_ha':instance.superficie_ha,
            'geojson':instance.geojson,
            'cultivo':instance.cultivo.nombre if instance.cultivo_id else 'Sin cultivo',
            'variedad':instance.variedad,
            'fecha_siembra':instance.fecha_siembra,
            'fecha_cosecha':instance.fecha_cosecha,
            'latitud':instance.latitud,
            'longitud':instance.longitud,
        }
    form = PotreroForm(request.POST or None, instance=instance)
    form.fields['superficie_ha'].widget.attrs['max'] = format(available_area, 'f')
    form.fields['superficie_ha'].help_text = (
        f'Superficie disponible en este predio: {available_area} ha. '
        'Si dibujas el perímetro, la superficie se calculará automáticamente.'
    )
    if request.method == 'POST' and form.is_valid():
        potrero = form.save()
        if original is None:
            PredioHistorial.objects.create(
                predio=predio,
                potrero=potrero,
                usuario=request.user,
                accion=PredioHistorial.Accion.POTRERO_CREADO,
                resumen=f'Se creó el potrero «{potrero.nombre}» con {potrero.superficie_ha} ha.',
                geometria_nueva=potrero.geojson,
                superficie_nueva_ha=potrero.superficie_ha,
            )
        else:
            current = {
                'nombre':potrero.nombre,
                'superficie_ha':potrero.superficie_ha,
                'geojson':potrero.geojson,
                'cultivo':potrero.cultivo.nombre if potrero.cultivo_id else 'Sin cultivo',
                'variedad':potrero.variedad,
                'fecha_siembra':potrero.fecha_siembra,
                'fecha_cosecha':potrero.fecha_cosecha,
                'latitud':potrero.latitud,
                'longitud':potrero.longitud,
            }
            labels = {
                'nombre':'Nombre',
                'superficie_ha':'Superficie (ha)',
                'cultivo':'Cultivo',
                'variedad':'Variedad',
                'fecha_siembra':'Fecha de siembra',
                'fecha_cosecha':'Fecha de cosecha',
                'latitud':'Latitud',
                'longitud':'Longitud',
            }
            changes = [
                f'{labels[field]}: {original[field] or "Sin dato"} → {current[field] or "Sin dato"}'
                for field in labels
                if original[field] != current[field]
            ]
            geometry_changed = original['geojson'] != current['geojson']
            if geometry_changed:
                changes.append('Perímetro actualizado')
            if changes:
                PredioHistorial.objects.create(
                    predio=predio,
                    potrero=potrero,
                    usuario=request.user,
                    accion=PredioHistorial.Accion.POTRERO_ACTUALIZADO,
                    resumen=f'Se modificó el potrero «{original["nombre"]}»: ' + '; '.join(changes) + '.',
                    geometria_anterior=original['geojson'] if geometry_changed else None,
                    geometria_nueva=current['geojson'] if geometry_changed else None,
                    superficie_anterior_ha=original['superficie_ha'],
                    superficie_nueva_ha=current['superficie_ha'],
                )
        messages.success(request, 'Potrero, cultivo y ubicación guardados en la base de datos.')
        return redirect('predio_detail', pk=predio.pk)
    return _page(request, 'terreno_form.html', 'predios', {
        'form':form, 'heading':'Editar potrero' if pk else 'Registrar potrero', 'predio':predio,
        'is_potrero':True, 'maps_config':map_config(),
        'potrero_superficie_disponible':available_area,
    })


def asesor(request):
    return _page(request, 'asesor.html', 'decisiones')


def calculadora(request):
    return _page(request, 'calculadora.html', 'decisiones')


def cobertura(request):
    return _page(request, 'cobertura.html', 'decisiones')


def predictor(request):
    return _page(request, 'predictor.html', 'decisiones')


def _decimal_input(value, label, allow_zero=False):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{label} debe ser un número válido.')
    if not number.is_finite() or number > Decimal('1e18') or number < 0 or (not allow_zero and number == 0):
        condition = '0 o mayor' if allow_zero else 'mayor a 0'
        raise ValueError(f'{label} debe ser {condition}.')
    return number


@login_required
@require_POST
def calculate(request):
    if request.content_type != 'application/json':
        return JsonResponse({'error':'Envía los datos como JSON.'}, status=415)
    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict):
            raise ValueError('Los datos del cálculo deben ser un objeto JSON.')
        operation = payload.get('operation')
        area = _decimal_input(payload.get('area'), 'La superficie')
        plot_id = payload.get('plot_id')
        if not str(plot_id or '').isdigit():
            raise ValueError('Selecciona un potrero registrado.')
        plot = Potrero.objects.select_related('cultivo').filter(
            predio__propietario=request.user, pk=plot_id
        ).first()
        if plot is None:
            raise ValueError('El potrero no existe o no pertenece a tu cuenta.')
        if area > plot.superficie_ha:
            raise ValueError(f'La superficie no puede superar {plot.superficie_ha} ha registradas.')
        result = {}
        if operation in {'dose', 'coverage'}:
            crop_name = str(payload.get('crop') or '').strip()
            if not crop_name and plot.cultivo_id:
                crop_name = plot.cultivo.nombre
            crop = Cultivo.objects.filter(nombre=crop_name, activo=True).first() if crop_name else None
            if crop_name and crop is None:
                raise ValueError('Selecciona un cultivo activo del catálogo.')
            product = None
            if payload.get('product_id'):
                if not str(payload['product_id']).isdigit():
                    raise ValueError('Selecciona un producto del catálogo.')
                product = Insumo.objects.select_related('tipo', 'cultivo').filter(
                    vigente=True, pk=payload['product_id']
                ).first()
                if product is None:
                    raise ValueError('El producto no existe o no está vigente.')
                if product.cultivo_id and (crop is None or product.cultivo.nombre != crop.nombre):
                    raise ValueError('El producto del catálogo no corresponde al cultivo seleccionado.')
            if product and product.es_fitosanitario:
                target = payload.get('target')
                if (
                    not product.uso_verificado
                    or crop is None
                    or crop_name != product.cultivo.nombre
                    or crop_name not in product.cultivos_autorizados
                    or target not in product.objetivos_control
                ):
                    raise ValueError('El producto fitosanitario no tiene un uso verificado para ese cultivo y objetivo.')
                dose = product.dosis_hectarea
                unit = product.unidad_dosis
            else:
                dose = _decimal_input(payload.get('dose'), 'La dosis')
                unit = str(payload.get('unit') or '').strip()
            if product and product.es_fitosanitario and not unit:
                raise ValueError('El producto fitosanitario no tiene una unidad de dosis verificada.')
            if operation == 'dose':
                amount = area * dose
                result = {'amount':float(amount), 'unit':unit.replace('/ha', ''), 'dose':float(dose), 'dose_unit':unit}
            else:
                stock = _decimal_input(payload.get('stock'), 'La cantidad disponible', allow_zero=True)
                needed = area * dose
                covered_area = min(area, stock / dose)
                result = {
                    'dose':float(dose),
                    'dose_unit':unit,
                    'needed':float(needed),
                    'coveredHa':float(covered_area),
                    'percent':float(covered_area / area * 100),
                    'missingHa':float(max(Decimal('0'), area - covered_area)),
                    'missingQty':float(max(Decimal('0'), needed - stock)),
                    'surplus':float(max(Decimal('0'), stock - needed)),
                    'unit':unit.replace('/ha', ''),
                }
        elif operation == 'seed_population':
            plants = _decimal_input(payload.get('plants_m2'), 'Las plantas objetivo por m²')
            weight = _decimal_input(payload.get('thousand_seed_weight_g'), 'El peso de mil semillas')
            germination = _decimal_input(payload.get('germination_pct'), 'La germinación')
            purity = _decimal_input(payload.get('purity_pct'), 'La pureza')
            if germination > 100 or purity > 100:
                raise ValueError('Germinación y pureza deben ser porcentajes de hasta 100.')
            source = str(payload.get('source') or '').strip()
            if not source:
                raise ValueError('Indica la fuente de los parámetros de semilla.')
            kg_per_ha = plants * weight / (Decimal('100') * (germination / 100) * (purity / 100))
            result = {
                'rate':float(kg_per_ha),
                'amount':float(kg_per_ha * area),
                'unit':'kg',
                'dose_unit':'kg/ha',
                'source':source,
            }
        elif operation == 'fertilizer_nutrition':
            product_id = payload.get('product_id')
            if not str(product_id or '').isdigit():
                raise ValueError('Selecciona un fertilizante del catálogo.')
            product = Insumo.objects.select_related('tipo', 'cultivo').filter(pk=product_id, vigente=True).first()
            if (
                product is None
                or product.tipo.nombre.casefold() not in {'fertilizante', 'fertilizer'}
                or product.estado_verificacion != 'verified'
                or not product.fuente_nombre
                or not product.fuente_url
                or not product.fecha_verificacion
                or not product.composicion_nutricional
                or product.unidad_dosis != 'kg/ha'
            ):
                raise ValueError('La composición o unidad del fertilizante no está verificada con una fuente.')
            if product.cultivo_id and payload.get('crop') != product.cultivo.nombre:
                raise ValueError('El fertilizante no corresponde al cultivo seleccionado.')
            nutrient_fields = {
                'N':product.nitrogeno_pct,
                'P2O5':product.fosforo_p2o5_pct,
                'K2O':product.potasio_k2o_pct,
            }
            nutrient = payload.get('nutrient')
            percentage = nutrient_fields.get(nutrient)
            if percentage is None or percentage <= 0:
                raise ValueError('El fertilizante no tiene composición verificada para este nutriente.')
            need_per_ha = _decimal_input(payload.get('need_per_ha'), 'La necesidad nutricional')
            need_source = str(payload.get('need_source') or '').strip()
            if not need_source:
                raise ValueError('Indica la fuente documentada de la necesidad nutricional.')
            product_per_ha = need_per_ha / (percentage / 100)
            amount = area * product_per_ha
            nutrient_applied = amount * (percentage / 100)
            result = {
                'amount':float(amount),
                'unit':product.unidad_dosis.replace('/ha', '') or 'kg',
                'dose':float(product_per_ha),
                'dose_unit':'kg de producto/ha',
                'nutrient':nutrient,
                'nutrientNeedPerHa':float(need_per_ha),
                'nutrientPct':float(percentage),
                'nutrientApplied':float(nutrient_applied),
                'nutrientSource':need_source,
                'product':product.nombre,
                'productSource':product.fuente_nombre,
            }
        elif operation == 'yield':
            crop = Cultivo.objects.filter(nombre=payload.get('crop'), activo=True).first()
            if crop is None:
                raise ValueError('Selecciona un cultivo activo del catálogo.')
            rate = _decimal_input(payload.get('rate'), 'El rendimiento')
            result = {'rate':float(rate), 'production':float(area * rate), 'unit':'ton'}
            result['source'] = str(payload.get('source') or '').strip()
        else:
            raise ValueError('El tipo de cálculo no está disponible.')
    except json.JSONDecodeError:
        return JsonResponse({'error':'El cuerpo JSON no se pudo interpretar.'}, status=400)
    except ValueError as exc:
        return JsonResponse({'error':str(exc)}, status=400)
    return JsonResponse({'ok':True, **result})


def decisiones(request):
    return _page(request, 'decisiones.html', 'decisiones')


@login_required
def calendario(request):
    return _page(request, 'calendario.html', 'calendario', {
        'activities':_activities_for_user(request.user),
        'referential_calendar':True,
    })


def busqueda(request):
    return _page(request, 'busqueda.html', 'busqueda')


def reportes(request):
    return _page(request, 'reportes.html', 'reportes')


@login_required
def admin_panel(request):
    if not request.user.is_staff:
        raise PermissionDenied
    return _page(request, 'admin.html', 'admin_panel', {'metrics':{
        'Agricultores':Agricultor.objects.count(), 'Predios':Predio.objects.count(),
        'Potreros':Potrero.objects.count(), 'Cultivos':Cultivo.objects.count(),
        'Insumos vigentes':Insumo.objects.filter(vigente=True).count(), 'Zonas':Zona.objects.count(),
    }})
