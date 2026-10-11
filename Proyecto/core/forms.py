import json
import re
from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import ActividadAgricola, Agricultor, Predio, Potrero, Cultivo, Zona
from .geometry import polygon_area, coordinates_from_geojson

COMUNAS = ['Melipilla', 'San Pedro', 'Alhué', 'María Pinto', 'Curacaví', 'Talagante', 'Isla de Maipo', 'Paine']


class RegistroForm(forms.Form):
    name = forms.CharField(max_length=150, label='Nombre')
    email = forms.EmailField(max_length=150, label='Correo electrónico')
    rut = forms.CharField(max_length=12, label='RUT')
    phone = forms.CharField(max_length=20, label='Teléfono')
    comuna = forms.ChoiceField(choices=[(c,c) for c in COMUNAS])
    password = forms.CharField(widget=forms.PasswordInput, label='Contraseña')
    password2 = forms.CharField(widget=forms.PasswordInput, label='Confirmación')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        users = get_user_model().objects
        if users.filter(email__iexact=email).exists() or users.filter(username__iexact=email).exists():
            raise ValidationError('Este correo ya tiene una cuenta.')
        return email

    def clean_rut(self):
        rut = self.cleaned_data['rut'].replace('.', '').replace(' ', '').upper()
        if not re.fullmatch(r'\d{7,8}-[0-9K]', rut):
            raise ValidationError('Usa un RUT válido con dígito verificador.')
        body, digit = rut.split('-')
        result = 11 - sum(int(n)*(2+i%6) for i,n in enumerate(reversed(body))) % 11
        expected = '0' if result == 11 else 'K' if result == 10 else str(result)
        if digit != expected:
            raise ValidationError('El dígito verificador del RUT no es válido.')
        rut = f'{int(body)}-{digit}'
        if Agricultor.objects.filter(rut=rut).exists():
            raise ValidationError('Este RUT ya está registrado.')
        return rut

    def clean_phone(self):
        phone = re.sub(r'[\s()-]', '', self.cleaned_data['phone'])
        if not re.fullmatch(r'\+?\d{8,15}', phone):
            raise ValidationError('Ingresa un teléfono de 8 a 15 dígitos.')
        return phone

    def clean(self):
        data = super().clean()
        if data.get('password') != data.get('password2'):
            self.add_error('password2', 'Las contraseñas no coinciden.')
        if data.get('password'):
            user = get_user_model()(username=data.get('email',''), email=data.get('email',''), first_name=data.get('name','')[:150])
            try:
                password_validation.validate_password(data['password'], user)
            except ValidationError as exc:
                self.add_error('password', exc)
        return data

    @transaction.atomic
    def save(self):
        d = self.cleaned_data
        user = get_user_model().objects.create_user(username=d['email'], email=d['email'], password=d['password'], first_name=d['name'])
        Agricultor.objects.create(user=user, nombre=d['name'], rut=d['rut'], telefono=d['phone'], comuna=d['comuna'])
        return user


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


class ActividadAgricolaForm(forms.ModelForm):
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['potrero'].queryset = Potrero.objects.filter(
            predio__propietario=user
        ).select_related('predio', 'cultivo')
        self.fields['potrero'].empty_label = 'Selecciona un potrero'
        self.fields['tipo'].choices = [
            ('', 'Selecciona un tipo de actividad'),
            *self.fields['tipo'].choices,
        ]

    class Meta:
        model = ActividadAgricola
        fields = ['nombre', 'tipo', 'potrero', 'fecha_programada', 'estado', 'observaciones']
        labels = {
            'nombre': 'Actividad',
            'tipo': 'Tipo de actividad',
            'potrero': 'Potrero',
            'fecha_programada': 'Fecha programada',
            'estado': 'Estado',
            'observaciones': 'Observaciones (opcional)',
        }
        widgets = {
            'fecha_programada': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'rows': 4}),
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
        return data
