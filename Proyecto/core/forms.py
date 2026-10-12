import json
from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import ActividadAgricola, Predio, Potrero, Cultivo, Zona, TemporadaCultivo, Insumo
from django.db import models
from .geometry import polygon_area, coordinates_from_geojson


class RegistroForm(UserCreationForm):
    error_messages = {
        **UserCreationForm.error_messages,
        'password_mismatch': 'Las contraseñas no coinciden.',
    }

    first_name = forms.CharField(
        max_length=150,
        label='Nombre',
        widget=forms.TextInput(attrs={'autocomplete': 'given-name', 'placeholder': 'Tu nombre'}),
    )
    last_name = forms.CharField(
        max_length=150,
        label='Apellido (opcional)',
        required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'family-name', 'placeholder': 'Tu apellido'}),
    )
    email = forms.EmailField(
        max_length=254,
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'tu@correo.com'}),
    )
    acepta_politicas = forms.BooleanField(
        required=True,
        error_messages={
            'required': 'Debes leer y aceptar la Política de privacidad, seguridad y cookies para crear tu cuenta.',
        },
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('first_name', 'last_name', 'username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Nombre de usuario'
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'username',
            'placeholder': 'Elige un nombre de usuario',
        })
        self.fields['password1'].label = 'Contraseña'
        self.fields['password1'].widget.attrs.update({'autocomplete': 'new-password'})
        self.fields['password2'].label = 'Confirmar contraseña'
        self.fields['password2'].widget.attrs.update({'autocomplete': 'new-password'})
        self.fields['password1'].help_text = (
            'Usa al menos 8 caracteres; evita las contraseñas comunes, solo numéricas '
            'o que contengan tus datos personales.'
        )

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        users = get_user_model().objects
        if (
            users.filter(username__iexact=username).exists()
            or users.filter(email__iexact=username).exists()
        ):
            raise ValidationError('Este nombre de usuario ya está registrado.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        users = get_user_model().objects
        if (
            users.filter(email__iexact=email).exists()
            or users.filter(username__iexact=email).exists()
        ):
            raise ValidationError('Este correo electrónico ya está registrado.')
        return email


class PredioForm(forms.ModelForm):
    geojson = forms.JSONField(required=False, widget=forms.HiddenInput())
    perimetro_aceptado = forms.BooleanField(required=False, widget=forms.HiddenInput())
    fecha_creacion = forms.CharField(
        label='Fecha de creación',
        required=False,
        disabled=True,
        initial='Se asignará automáticamente al guardar',
    )

    class Meta:
        model = Predio
        fields = [
            'nombre', 'descripcion', 'ubicacion', 'observaciones',
            'superficie_ha', 'zona', 'latitud', 'longitud', 'geojson',
        ]
        labels = {
            'superficie_ha': 'Superficie total (ha)',
            'ubicacion': 'Referencia de ubicación',
            'descripcion': 'Descripción (opcional)',
            'observaciones': 'Observaciones (opcional)',
        }
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
            'superficie_ha': forms.NumberInput(attrs={'min':'0.0001','step':'0.0001','readonly':'readonly'}),
            'latitud': forms.NumberInput(attrs={'min':-85,'max':85,'step':'any'}),
            'longitud': forms.NumberInput(attrs={'min':-180,'max':180,'step':'any'}),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance and instance.pk:
            bound_data = args[0] if args else kwargs.get('data')
            if bound_data is not None and 'geojson' not in bound_data:
                bound_data = bound_data.copy()
                bound_data['geojson'] = json.dumps(instance.geojson) if instance.geojson else ''
                if args:
                    args = (bound_data, *args[1:])
                else:
                    kwargs['data'] = bound_data
        super().__init__(*args, **kwargs)
        self.fields['superficie_ha'].required = False
        self.fields['zona'].queryset = Zona.objects.filter(activo=True)
        if instance and instance.pk:
            self.fields['fecha_creacion'].initial = timezone.localtime(instance.creado).strftime('%d/%m/%Y %H:%M')

    def clean(self):
        data = super().clean()
        geometry = data.get('geojson')
        if geometry:
            try:
                coordinates = coordinates_from_geojson(geometry)
                data['superficie_ha'] = (polygon_area(coordinates) / 10000).quantize(Decimal('0.0001'))
            except ValidationError as exc:
                self.add_error('geojson', exc)
        elif data.get('superficie_ha') is None:
            self.add_error('superficie_ha', 'Ingresa la superficie o dibuja el perímetro.')
        return data


class PotreroForm(forms.ModelForm):
    class Meta:
        model = Potrero
        fields = ['nombre', 'cultivo', 'variedad', 'fecha_siembra', 'fecha_cosecha', 'superficie_ha', 'latitud', 'longitud', 'perimetro']
        labels = {'superficie_ha':'Superficie (ha)', 'perimetro':'Perímetro', 'latitud':'Latitud', 'longitud':'Longitud'}
        widgets = {
            'perimetro': forms.HiddenInput(),
            'fecha_siembra': forms.DateInput(format='%Y-%m-%d', attrs={'type':'date'}),
            'fecha_cosecha': forms.DateInput(format='%Y-%m-%d', attrs={'type':'date'}),
            'superficie_ha': forms.NumberInput(attrs={'min':'0.0001','step':'0.0001'}),
            'latitud': forms.NumberInput(attrs={'min':-85,'max':85,'step':'any'}),
            'longitud': forms.NumberInput(attrs={'min':-180,'max':180,'step':'any'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cultivo'].queryset = Cultivo.objects.filter(activo=True)
        self.fields['superficie_ha'].required = False

    def clean(self):
        data = super().clean()
        perimeter = data.get('perimetro') or []
        data['perimetro'] = perimeter
        if perimeter:
            try:
                data['superficie_ha'] = (polygon_area(perimeter) / 10000).quantize(Decimal('0.0001'))
            except ValidationError as exc:
                self.add_error('perimetro', exc)
        elif data.get('superficie_ha') is None:
            self.add_error('superficie_ha', 'Ingresa la superficie o dibuja el perímetro.')
        return data


class TemporadaCultivoForm(forms.ModelForm):
    class Meta:
        model = TemporadaCultivo
        fields = [
            'cultivo', 'variedad', 'temporada_agricola', 'fecha_siembra', 'fecha_cosecha',
            'estado', 'observaciones',
        ]
        labels = {
            'cultivo':'Cultivo',
            'variedad':'Variedad',
            'temporada_agricola':'Temporada agrícola',
            'fecha_siembra':'Fecha de siembra',
            'fecha_cosecha':'Fecha de cosecha',
            'estado':'Estado de la temporada',
            'observaciones':'Observaciones',
        }
        widgets = {
            'fecha_siembra':forms.DateInput(format='%Y-%m-%d', attrs={'type':'date'}),
            'fecha_cosecha':forms.DateInput(format='%Y-%m-%d', attrs={'type':'date'}),
            'observaciones':forms.Textarea(attrs={'rows':4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cultivo'].queryset = Cultivo.objects.filter(activo=True).order_by('nombre')
        self.fields['cultivo'].empty_label = 'Selecciona un cultivo'
        self.fields['temporada_agricola'].widget.attrs.update({'placeholder':'2026-2027', 'pattern':'[0-9]{4}-[0-9]{4}'})
        self.fields['fecha_siembra'].required = False
        self.fields['fecha_cosecha'].required = False


UNIDADES_DOSIS = [
    ('', 'Unidad'), ('kg/ha', 'kg/ha'), ('g/ha', 'g/ha'), ('L/ha', 'L/ha'),
    ('mL/ha', 'mL/ha'), ('unidades/ha', 'unidades/ha'),
]


class ActividadAgricolaForm(forms.ModelForm):
    unidad_dosis = forms.ChoiceField(choices=UNIDADES_DOSIS, required=False, label='Unidad')

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['potrero'].queryset = Potrero.objects.filter(
            predio__propietario=user
        ).select_related('predio', 'cultivo').order_by('predio__nombre', 'nombre')
        self.fields['potrero'].empty_label = 'Selecciona un potrero'
        self.fields['potrero'].label_from_instance = lambda plot: f'{plot.predio.nombre} · {plot.nombre}'
        self.fields['temporada'].queryset = TemporadaCultivo.objects.filter(
            potrero__predio__propietario=user
        ).select_related('cultivo', 'potrero')
        self.fields['temporada'].empty_label = 'Sin temporada asociada'
        self.fields['temporada'].label_from_instance = lambda season: (
            f'{season.temporada_agricola + " · " if season.temporada_agricola else ""}'
            f'{season.cultivo.nombre}{" · " + season.variedad if season.variedad else ""} · {season.get_estado_display()}'
        )
        today = timezone.localdate()
        self.fields['insumo'].queryset = Insumo.objects.filter(vigente=True).exclude(
            estado_verificacion__in=['restricted', 'cancelled'],
        ).filter(
            models.Q(vigencia_desde__isnull=True) | models.Q(vigencia_desde__lte=today),
            models.Q(vigencia_hasta__isnull=True) | models.Q(vigencia_hasta__gte=today),
        ).select_related('tipo', 'cultivo').order_by('tipo__nombre', 'nombre')
        self.fields['insumo'].empty_label = 'Sin producto del catálogo'
        self.fields['insumo'].label_from_instance = lambda item: f'{item.tipo.nombre} · {item.nombre}'
        self.fields['prioridad'].required = False
        self.fields['tipo'].choices = [
            ('', 'Selecciona un tipo de actividad'),
            *[choice for choice in self.fields['tipo'].choices if choice[0]],
        ]

    class Meta:
        model = ActividadAgricola
        fields = [
            'tipo', 'nombre', 'potrero', 'temporada', 'prioridad', 'fecha_programada', 'estado',
            'fecha_realizada', 'responsable', 'insumo', 'insumo_otro', 'objetivo', 'dosis',
            'unidad_dosis', 'superficie_ha', 'condiciones_clima', 'observaciones',
        ]
        labels = {
            'nombre': 'Nombre de la actividad',
            'tipo': 'Tipo de labor',
            'potrero': 'Potrero',
            'temporada': 'Temporada de cultivo',
            'prioridad': 'Prioridad',
            'fecha_programada': 'Fecha programada',
            'estado': 'Estado',
            'fecha_realizada': 'Fecha en que se realizó',
            'responsable': 'Responsable / aplicador',
            'insumo': 'Producto del catálogo',
            'insumo_otro': 'Otro producto (no catalogado)',
            'objetivo': 'Objetivo (plaga, maleza, nutriente…)',
            'dosis': 'Dosis',
            'superficie_ha': 'Superficie tratada (ha)',
            'condiciones_clima': 'Condiciones al momento de la labor',
            'observaciones': 'Observaciones (opcional)',
        }
        widgets = {
            'fecha_programada': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'fecha_realizada': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'rows': 4}),
            'dosis': forms.NumberInput(attrs={'min': '0.001', 'step': 'any'}),
            'superficie_ha': forms.NumberInput(attrs={'min': '0.0001', 'step': 'any'}),
            'condiciones_clima': forms.TextInput(attrs={'placeholder': 'Ej.: despejado, viento suave, suelo húmedo'}),
            'responsable': forms.TextInput(attrs={'placeholder': 'Nombre de quien ejecuta la labor'}),
        }

    def clean_potrero(self):
        potrero = self.cleaned_data['potrero']
        if potrero.predio.propietario_id != self.user.pk:
            raise ValidationError('Selecciona un potrero de tu cuenta.')
        return potrero

    def clean(self):
        data = super().clean()
        if self.instance.pk and self.instance.usuario_id != self.user.pk:
            raise ValidationError('No puedes modificar actividades de otra cuenta.')
        plot = data.get('potrero')
        season = data.get('temporada')
        product = data.get('insumo')
        crop = season.cultivo if season else (plot.cultivo if plot else None)
        if product and product.cultivo_id and crop and product.cultivo_id != crop.pk:
            self.add_error('insumo', f'El producto está asociado a {product.cultivo.nombre}, no a {crop.nombre}.')
        if product and data.get('unidad_dosis') and product.unidad_dosis and data['unidad_dosis'] != product.unidad_dosis:
            self.add_error('unidad_dosis', f'La unidad registrada del producto es {product.unidad_dosis}.')
        if (
            product and product.dosis_maxima_hectarea is not None and data.get('dosis')
            and data['dosis'] > product.dosis_maxima_hectarea
        ):
            self.add_error('dosis', f'Supera la dosis máxima registrada ({product.dosis_maxima_hectarea} {product.unidad_dosis_maxima}).')
        if not data.get('prioridad'):
            data['prioridad'] = ActividadAgricola.Prioridad.MEDIA
        if data.get('tipo') not in ActividadAgricola.TIPOS_CON_INSUMO:
            for field in ('insumo', 'insumo_otro', 'dosis', 'unidad_dosis'):
                if data.get(field):
                    data[field] = None if field in ('insumo', 'dosis') else ''
        return data
