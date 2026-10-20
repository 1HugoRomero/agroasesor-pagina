import os
import json
import re
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings, Client
from django.utils import timezone
from .geometry import polygon_area, polygon_perimeter
from .models import AceptacionPoliticas, ActividadAgricola, CalculoAgricola, ConfiguracionAgronomica, Cultivo, Insumo, Predio, PredioHistorial, Potrero, ReferenciaAgronomica, TemporadaCultivo, TipoInsumo, Zona, ProblemaAgricola

User = get_user_model()
PASSWORD = 'Campo-Seguro-2026!'
POLYGON = [[-71.215,-33.686],[-71.214,-33.686],[-71.214,-33.685],[-71.215,-33.685]]


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('farmer@example.com', email='farmer@example.com', password=PASSWORD)

    def registration_data(self, **values):
        return {
            'mode':'register',
            'first_name':'María',
            'last_name':'Soto',
            'username':'maria.soto',
            'email':'maria@example.com',
            'password1':PASSWORD,
            'password2':PASSWORD,
            'acepta_politicas':'on',
            **values,
        }

    def test_registration_persists_hashed_password_logs_in_and_records_policy_acceptance(self):
        response = self.client.post('/login/', self.registration_data())
        self.assertRedirects(response, '/')
        user = User.objects.get(email='maria@example.com')
        self.assertEqual(user.username, 'maria.soto')
        self.assertEqual(user.first_name, 'María')
        self.assertEqual(user.last_name, 'Soto')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertFalse(user.is_staff)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        acceptance = user.aceptaciones_politicas.get()
        self.assertEqual(acceptance.version, AceptacionPoliticas.VERSION_ACTUAL)
        self.assertIsNotNone(acceptance.aceptada_en)
        self.assertFalse(self.user.aceptaciones_politicas.exists())

    def test_registration_requires_policy_acceptance(self):
        data = self.registration_data()
        del data['acepta_politicas']
        response = self.client.post('/login/', data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Debes leer y aceptar la Política de privacidad, seguridad y cookies')
        self.assertFalse(User.objects.filter(email='maria@example.com').exists())
        self.assertFalse(AceptacionPoliticas.objects.exists())

    def test_policy_page_explains_cookies_and_browser_storage(self):
        response = self.client.get('/politicas/privacidad-y-cookies/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cookies necesarias')
        self.assertContains(response, 'almacenamiento local del navegador')
        self.assertContains(response, AceptacionPoliticas.VERSION_ACTUAL)

    def test_registration_rejects_weak_or_mismatched_passwords(self):
        weak_password = self.client.post(
            '/login/',
            self.registration_data(password1='123456', password2='123456'),
        )
        self.assertEqual(weak_password.status_code, 200)
        mismatch = self.client.post(
            '/login/',
            self.registration_data(password1=PASSWORD, password2='diferente'),
        )
        self.assertContains(mismatch, 'Las contraseñas no coinciden.')
        self.assertFalse(User.objects.filter(email='maria@example.com').exists())

    def test_registration_rejects_duplicate_username_and_email_case_insensitively(self):
        duplicate_username = self.registration_data(
            username='FARMER@example.com',
            email='new@example.com',
        )
        self.assertContains(
            self.client.post('/login/', duplicate_username),
            'Este nombre de usuario ya está registrado.',
        )
        duplicate_email = self.registration_data(
            username='another',
            email='FARMER@example.com',
        )
        self.assertContains(
            self.client.post('/login/', duplicate_email),
            'Este correo electrónico ya está registrado.',
        )
        self.assertEqual(User.objects.count(), 1)

    def test_login_logout_and_invalid_credentials(self):
        self.assertEqual(self.client.get('/').status_code, 302)
        self.assertContains(self.client.post('/login/', {'email':self.user.email,'password':'wrong'}), 'incorrectos')
        self.assertContains(
            self.client.post('/login/', {'username':'cuenta-inexistente','password':PASSWORD}),
            'incorrectos',
        )
        self.assertRedirects(self.client.post('/login/', {'username':'farmer@example.com','password':PASSWORD}), '/')
        self.assertEqual(self.client.get('/logout/').status_code, 405)
        self.assertRedirects(self.client.post('/logout/'), '/login/')
        self.assertEqual(self.client.get('/predios/').status_code, 302)

    def test_registered_user_can_log_out_and_sign_back_in_with_username_or_email(self):
        self.client.post('/login/', self.registration_data())
        self.assertRedirects(self.client.post('/logout/'), '/login/')
        self.assertRedirects(
            self.client.post('/login/', {'username':'maria.soto','password':PASSWORD}),
            '/',
        )
        self.assertRedirects(self.client.post('/logout/'), '/login/')
        self.assertRedirects(
            self.client.post('/login/', {'username':'MARIA@example.com','password':PASSWORD}),
            '/',
        )

    def test_registration_and_predio_data_are_isolated_and_persist_after_login(self):
        existing_farm = Predio.objects.create(
            propietario=self.user,
            nombre='Campo privado existente',
            ubicacion='Melipilla',
            superficie_ha=5,
        )
        self.client.post('/login/', self.registration_data())
        registered_user = User.objects.get(username='maria.soto')
        empty_farms = self.client.get('/predios/')
        self.assertEqual(empty_farms.status_code, 200)
        self.assertEqual(empty_farms.context['predios_list'].count(), 0)
        self.assertNotContains(empty_farms, existing_farm.nombre)

        boundary = [[-71.215,-33.686],[-71.214,-33.686],[-71.214,-33.685],[-71.215,-33.685]]
        feature = {
            'type':'Feature',
            'properties':{},
            'geometry':{'type':'Polygon','coordinates':[boundary + [boundary[0]]]},
        }
        response = self.client.post('/predios/nuevo/', {
            'nombre':'Campo de María',
            'ubicacion':'Melipilla',
            'superficie_ha':'',
            'geojson':json.dumps(feature),
            'perimetro_aceptado':'on',
        })
        farm = Predio.objects.get(nombre='Campo de María')
        self.assertRedirects(response, f'/predios/{farm.pk}/')
        self.assertEqual(farm.propietario, registered_user)

        self.assertRedirects(self.client.post('/logout/'), '/login/')
        self.assertRedirects(
            self.client.post('/login/', {'username':'maria.soto','password':PASSWORD}),
            '/',
        )
        owned_farms = self.client.get('/predios/')
        self.assertContains(owned_farms, farm.nombre)
        self.assertNotContains(owned_farms, existing_farm.nombre)
        self.assertEqual(list(registered_user.predios.values_list('pk', flat=True)), [farm.pk])
        self.assertEqual(self.client.get(f'/predios/{existing_farm.pk}/').status_code, 404)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        self.client.post('/login/', {'email':self.user.email, 'password':PASSWORD})
        self.assertEqual(self.client.get('/').status_code, 302)

    def test_admin_shortcut_cannot_escalate_privileges(self):
        self.assertEqual(self.client.post('/entrar-admin/').status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/entrar-admin/').status_code, 403)
        self.assertEqual(self.client.get('/panel-admin/').status_code, 403)
        self.assertNotContains(self.client.get('/'), 'Ingresar como administrador')

    def test_admin_real_counts(self):
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.get('/panel-admin/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['metrics']['Predios'], 0)
        self.assertContains(response, '/admin/')

    def test_csrf_required_for_login_registration_and_logout(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/login/', self.registration_data()).status_code, 403)
        client.force_login(self.user)
        self.assertEqual(client.post('/logout/').status_code, 403)

    @override_settings(MAILERS={'default':{'BACKEND':'django.core.mail.backends.locmem.EmailBackend'}})
    def test_reset_requires_verified_single_use_token(self):
        self.assertRedirects(self.client.post('/cuenta/recuperar/', {'email':self.user.email}), '/cuenta/enviado/')
        self.assertEqual(len(mail.outbox), 1)
        url = re.search(r'http://testserver(/cuenta/restablecer/\S+)', mail.outbox[0].body).group(1)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        password = 'Nueva-Clave-Segura-2026!'
        self.assertRedirects(self.client.post(response.url, {'new_password1':password,'new_password2':password}), '/cuenta/restablecida/')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(password))
        another = Client()
        self.assertContains(another.get(url), 'inválido')

    def test_old_reset_flow_cannot_change_password(self):
        self.client.post('/login/', {'mode':'reset','email':self.user.email,'password':'hacked','password2':'hacked'})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))


class TerrainTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('a',email='a@example.com',password=PASSWORD)
        self.other = User.objects.create_user('b',email='b@example.com',password=PASSWORD)
        self.crop = Cultivo.objects.create(nombre='Cultivo de prueba')
        self.predio = Predio.objects.create(propietario=self.user,nombre='Mi campo',ubicacion='Melipilla',superficie_ha=10)
        self.client.force_login(self.user)
        self.url = f'/predios/{self.predio.pk}/potreros/nuevo/'

    def plot_data(self, **values):
        return {'nombre':'Potrero norte','cultivo':self.crop.pk,'variedad':'','superficie_ha':'2',
                'fecha_siembra':'2026-10-02','fecha_cosecha':'2027-03-01','latitud':'','longitud':'','perimetro':'[]', **values}

    def test_create_and_edit_predio(self):
        boundary = [[-71.216,-33.687],[-71.213,-33.687],[-71.213,-33.684],[-71.216,-33.684]]
        feature = {'type':'Feature','properties':{},'geometry':{'type':'Polygon','coordinates':[boundary + [boundary[0]]]}}
        response = self.client.post('/predios/nuevo/', {
            'nombre':'Campo nuevo','ubicacion':'Paine','superficie_ha':'5',
            'geojson':json.dumps(feature),'perimetro_aceptado':'on',
            'propietario':self.other.pk,
        })
        self.assertEqual(response.status_code, 302)
        p = Predio.objects.get(nombre='Campo nuevo')
        self.assertRedirects(response, f'/predios/{p.pk}/')
        self.assertEqual(p.propietario,self.user)
        self.assertRedirects(self.client.post(f'/predios/{p.pk}/editar/',{'nombre':'Actualizado','ubicacion':'Paine','superficie_ha':'6'}), f'/predios/{p.pk}/')
        p.refresh_from_db()
        self.assertEqual(p.nombre,'Actualizado')
        self.assertEqual(p.geojson, feature)
        self.assertEqual(p.historial.count(), 2)

    def test_predio_drawn_geojson_is_closed_and_server_recalculates_area(self):
        boundary = [[-71.216,-33.687],[-71.213,-33.687],[-71.213,-33.684],[-71.216,-33.684]]
        feature = {
            'type':'Feature',
            'properties':{},
            'geometry':{'type':'Polygon','coordinates':[boundary + [boundary[0]]]},
        }
        response = self.client.post('/predios/nuevo/', {
            'nombre':'Campo delimitado',
            'ubicacion':'Melipilla',
            'superficie_ha':'999',
            'geojson':json.dumps(feature),
            'perimetro_aceptado':'on',
            'latitud':'',
            'longitud':'',
            'zona':'',
        })
        self.assertEqual(response.status_code, 302)
        farm = Predio.objects.get(nombre='Campo delimitado')
        self.assertRedirects(response, f'/predios/{farm.pk}/')
        self.assertEqual(farm.geojson, feature)
        self.assertEqual(
            farm.superficie_ha,
            (polygon_area(boundary) / Decimal('10000')).quantize(Decimal('0.0001')),
        )
        self.assertEqual(self.client.get(f'/predios/{farm.pk}/').status_code, 200)
        edit_response = self.client.get(f'/predios/{farm.pk}/editar/')
        self.assertContains(edit_response, 'id="map-form-summary"')
        self.assertContains(edit_response, 'id="map-summary-area"')
        self.assertContains(edit_response, 'name="geojson"')

    def test_new_predio_requires_an_explicit_accepted_closed_polygon(self):
        form_data = {
            'nombre':'Sin aceptación', 'ubicacion':'Melipilla', 'superficie_ha':'',
            'geojson':json.dumps({
                'type':'Feature','properties':{},
                'geometry':{'type':'Polygon','coordinates':[POLYGON + [POLYGON[0]]]},
            }),
        }
        response = self.client.post('/predios/nuevo/', form_data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Predio.objects.filter(nombre='Sin aceptación').exists())
        form_data['perimetro_aceptado'] = 'on'
        response = self.client.post('/predios/nuevo/', form_data)
        self.assertEqual(response.status_code, 302)
        farm = Predio.objects.get(nombre='Sin aceptación')
        self.assertEqual(farm.historial.get().accion, PredioHistorial.Accion.CREADO)

        invalid_data = {
            'nombre':'Anillo abierto', 'ubicacion':'Melipilla', 'superficie_ha':'',
            'geojson':json.dumps({
                'type':'Feature','properties':{},
                'geometry':{'type':'Polygon','coordinates':[POLYGON]},
            }),
            'perimetro_aceptado':'on',
        }
        self.assertEqual(self.client.post('/predios/nuevo/', invalid_data).status_code, 200)
        self.assertFalse(Predio.objects.filter(nombre='Anillo abierto').exists())

    def test_perimeter_edits_recalculate_surface_and_keep_immutable_history_snapshots(self):
        old_points = POLYGON
        old_feature = {
            'type':'Feature','properties':{},
            'geometry':{'type':'Polygon','coordinates':[old_points + [old_points[0]]]},
        }
        create_response = self.client.post('/predios/nuevo/', {
            'nombre':'Trazable','ubicacion':'Melipilla','superficie_ha':'',
            'geojson':json.dumps(old_feature),'perimetro_aceptado':'on',
        })
        self.assertEqual(create_response.status_code, 302)
        farm = Predio.objects.get(nombre='Trazable')
        old_area = farm.superficie_ha
        new_points = [[-71.215,-33.686],[-71.2135,-33.686],[-71.2135,-33.6845],[-71.215,-33.6845]]
        new_feature = {
            'type':'Feature','properties':{},
            'geometry':{'type':'Polygon','coordinates':[new_points + [new_points[0]]]},
        }
        response = self.client.post(f'/predios/{farm.pk}/editar/', {
            'nombre':farm.nombre,'ubicacion':farm.ubicacion,'superficie_ha':str(old_area),
            'descripcion':'Actualizada','observaciones':'Revisión anual',
            'geojson':json.dumps(new_feature),'perimetro_aceptado':'on',
        })
        self.assertRedirects(response, f'/predios/{farm.pk}/')
        farm.refresh_from_db()
        self.assertEqual(
            farm.superficie_ha,
            (polygon_area(new_points) / Decimal('10000')).quantize(Decimal('0.0001')),
        )
        self.assertNotEqual(farm.superficie_ha, old_area)
        perimeter_event = farm.historial.get(accion=PredioHistorial.Accion.PERIMETRO)
        self.assertEqual(perimeter_event.geometria_anterior, old_feature)
        self.assertEqual(perimeter_event.geometria_nueva, new_feature)
        self.assertEqual(perimeter_event.superficie_anterior_ha, old_area)
        self.assertEqual(perimeter_event.superficie_nueva_ha, farm.superficie_ha)
        with self.assertRaises(ValidationError):
            perimeter_event.resumen = 'Alterado'
            perimeter_event.save()
        with self.assertRaises(ValidationError):
            perimeter_event.delete()
        with self.assertRaises(ValidationError):
            PredioHistorial.objects.filter(pk=perimeter_event.pk).update(resumen='Alterado')
        with self.assertRaises(ValidationError):
            PredioHistorial.objects.filter(pk=perimeter_event.pk).delete()
        self.client.logout()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/predios/{farm.pk}/').status_code, 404)
        self.assertEqual(self.client.post(f'/predios/{farm.pk}/editar/', {}).status_code, 404)

    def test_predio_ficha_shows_persistent_history_and_agricultural_totals(self):
        self.predio.geojson = {
            'type':'Feature',
            'properties':{},
            'geometry':{'type':'Polygon','coordinates':[POLYGON + [POLYGON[0]]]},
        }
        self.predio.save()
        history = PredioHistorial.objects.create(
            predio=self.predio,
            usuario=self.user,
            accion=PredioHistorial.Accion.CREADO,
            resumen='Predio importado antes de activar el historial.',
            superficie_nueva_ha=self.predio.superficie_ha,
        )
        self.client.post(self.url, self.plot_data())
        response = self.client.get(f'/predios/{self.predio.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Historial del terreno')
        self.assertContains(response, 'Potrero creado')
        self.assertContains(response, 'Superficie utilizada')
        self.assertContains(response, 'Planificación de siembra')
        self.assertContains(response, 'data-map-layer="normal"')
        self.assertContains(response, 'data-map-layer="satellite"')
        self.assertContains(response, 'predio-map-status')
        self.assertEqual(response.context['historial'].first().accion, PredioHistorial.Accion.POTRERO_CREADO)
        self.assertTrue(PredioHistorial.objects.filter(pk=history.pk).exists())

    def test_create_plot_and_associate_crop_persist_across_sessions(self):
        self.assertRedirects(self.client.post(self.url,self.plot_data()), f'/predios/{self.predio.pk}/')
        plot = Potrero.objects.get()
        self.assertEqual(plot.cultivo,self.crop)
        self.client.logout()
        self.client.force_login(self.user)
        response = self.client.get('/predios/')
        self.assertContains(response,'Potrero norte')
        self.assertEqual(response.context['farm_data']['plots'][0]['id'],str(plot.pk))
        event = self.predio.historial.get(accion=PredioHistorial.Accion.POTRERO_CREADO)
        self.assertEqual(event.superficie_nueva_ha, plot.superficie_ha)
        self.assertEqual(event.potrero, plot)
        self.assertContains(response, 'MIS PREDIOS REGISTRADOS')
        self.assertContains(response, 'POTREROS DE ESTE PREDIO')
        self.assertContains(response, 'HISTORIAL DE POTREROS')
        self.assertContains(response, f'data-select-plot="{plot.pk}"')
        selected_response = self.client.get('/predios/', {'predio':str(self.predio.pk)})
        self.assertContains(selected_response, f'data-initial-farm="{self.predio.pk}"')

    def test_predios_page_lists_all_owned_farms_and_filters_potrero_history(self):
        other_farm = Predio.objects.create(
            propietario=self.user,
            nombre='Campo sur',
            ubicacion='Paine',
            superficie_ha=5,
        )
        more_farms = [
            Predio.objects.create(
                propietario=self.user,
                nombre=f'Campo {number}',
                ubicacion='Zona rural',
                superficie_ha=1,
            )
            for number in range(3, 11)
        ]
        foreign_farm = Predio.objects.create(
            propietario=self.other,
            nombre='Campo privado',
            ubicacion='Otra comuna',
            superficie_ha=8,
        )
        first_plot = Potrero.objects.create(
            predio=self.predio,
            nombre='Ladera norte',
            cultivo=self.crop,
            superficie_ha=Decimal('2'),
        )
        second_plot = Potrero.objects.create(
            predio=other_farm,
            nombre='Bajo sur',
            superficie_ha=Decimal('1'),
        )
        Potrero.objects.create(
            predio=foreign_farm,
            nombre='Potrero ajeno',
            superficie_ha=Decimal('1'),
        )

        response = self.client.get('/predios/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['predios_list'].count(), 10)
        self.assertContains(response, 'Mi campo')
        self.assertContains(response, 'Campo sur')
        for farm in more_farms:
            self.assertContains(response, farm.nombre)
        self.assertNotContains(response, 'Campo privado')
        self.assertContains(response, 'Ladera norte')
        self.assertContains(response, 'Bajo sur')
        self.assertNotContains(response, 'Potrero ajeno')
        self.assertEqual(response.context['potrero_history_page'].paginator.count, 2)

        selected = self.client.get('/predios/', {'predio':str(self.predio.pk)})
        self.assertEqual(selected.context['selected_predio'], self.predio)
        self.assertContains(selected, f'data-farm-plots="{self.predio.pk}"')
        self.assertContains(selected, f'?potrero={first_plot.pk}#predio-history')
        self.assertContains(selected, 'data-select-plot="' + str(first_plot.pk) + '"')

        filtered = self.client.get('/predios/', {
            'q':'norte',
            'filtro_predio':str(self.predio.pk),
            'cultivo':str(self.crop.pk),
            'orden':'nombre',
        })
        self.assertEqual(filtered.context['potrero_history_page'].paginator.count, 1)
        self.assertEqual(filtered.context['potrero_history_page'].object_list[0], first_plot)

    def test_potrero_history_list_paginates_and_keeps_filters(self):
        for number in range(26):
            Potrero.objects.create(
                predio=self.predio,
                nombre=f'Potrero {number:02}',
                superficie_ha=Decimal('0.1'),
            )
        response = self.client.get('/predios/', {
            'q':'Potrero',
            'filtro_predio':str(self.predio.pk),
            'orden':'nombre',
        })
        page = response.context['potrero_history_page']
        self.assertEqual(page.paginator.count, 26)
        self.assertEqual(page.paginator.num_pages, 2)
        self.assertEqual(len(page.object_list), 25)
        self.assertContains(response, 'Página 1 de 2')
        self.assertContains(
            response,
            f'?q=Potrero&filtro_predio={self.predio.pk}&cultivo=&orden=nombre&pagina=2',
        )

    def test_predios_empty_state_distinguishes_no_farms_and_farm_without_plots(self):
        response = self.client.get('/predios/')
        self.assertContains(response, 'Selecciona un predio para registrar y administrar sus potreros.')
        self.assertContains(response, 'Este predio todavía no tiene potreros registrados.')
        self.assertContains(response, 'Registrar primer potrero')

        new_user = User.objects.create_user('empty', email='empty@example.com', password=PASSWORD)
        self.client.force_login(new_user)
        empty_response = self.client.get('/predios/')
        self.assertContains(empty_response, 'No tienes predios registrados.')
        self.assertContains(empty_response, 'Registrar predio')
        self.assertNotContains(empty_response, 'Aún no hay potreros ubicados en el mapa.')

    def test_polygon_area_is_calculated_on_server(self):
        self.assertRedirects(self.client.post(self.url,self.plot_data(perimetro=json.dumps(POLYGON),superficie_ha='9')), f'/predios/{self.predio.pk}/')
        plot = Potrero.objects.get()
        self.assertEqual(plot.perimetro,POLYGON)
        self.assertEqual(plot.superficie_ha,(polygon_area(POLYGON)/10000).quantize(Decimal('0.0001')))
        self.assertNotEqual(plot.superficie_ha,Decimal('9'))

    def test_polygon_does_not_need_manual_area(self):
        self.assertRedirects(self.client.post(self.url,self.plot_data(perimetro=json.dumps(POLYGON),superficie_ha='')), f'/predios/{self.predio.pk}/')

    def test_edit_plot_crop_and_coordinates(self):
        self.client.post(self.url,self.plot_data())
        plot = Potrero.objects.get()
        url=f'/predios/{self.predio.pk}/potreros/{plot.pk}/editar/'
        self.assertRedirects(self.client.post(url,self.plot_data(nombre='Sur',cultivo='',latitud='-33.5',longitud='-71.2')), f'/predios/{self.predio.pk}/')
        plot.refresh_from_db()
        self.assertIsNone(plot.cultivo)
        self.assertEqual(plot.latitud,-33.5)
        self.assertEqual(plot.nombre,'Sur')
        event = self.predio.historial.get(accion=PredioHistorial.Accion.POTRERO_ACTUALIZADO)
        self.assertEqual(event.superficie_anterior_ha, Decimal('2'))
        self.assertEqual(event.superficie_nueva_ha, Decimal('2'))
        self.assertEqual(event.potrero, plot)
        self.assertIn('Nombre: Potrero norte → Sur', event.resumen)
        filtered_history = self.client.get(f'/predios/{self.predio.pk}/', {'potrero':plot.pk})
        self.assertContains(filtered_history, 'Historial de Sur')
        self.assertContains(filtered_history, 'Se modificó el potrero')
        self.assertNotContains(filtered_history, 'Predio creado')

    def test_owners_cannot_see_or_modify_other_terrain(self):
        self.client.post(self.url,self.plot_data())
        plot=Potrero.objects.get()
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get('/predios/'),'Mi campo')
        self.assertEqual(self.client.get('/').context['farm_data']['plots'],[])
        for url in [f'/predios/{self.predio.pk}/editar/',self.url,f'/predios/{self.predio.pk}/potreros/{plot.pk}/editar/']:
            self.assertEqual(self.client.get(url).status_code,404)
            self.assertEqual(self.client.post(url,self.plot_data()).status_code,404)

    def test_reject_invalid_dates_areas_and_coordinates(self):
        for data in [self.plot_data(superficie_ha='-1'),self.plot_data(superficie_ha='0'),self.plot_data(superficie_ha='11'),
                     self.plot_data(fecha_cosecha='2026-01-01'),self.plot_data(latitud='91',longitud='1'),
                     self.plot_data(latitud='-33'),self.plot_data(latitud='nan',longitud='1'),self.plot_data(perimetro='not-json')]:
            with self.subTest(data=data):
                self.assertEqual(self.client.post(self.url,data).status_code,200)
        self.assertEqual(Potrero.objects.count(),0)

    def test_total_plot_area_and_predio_reduction(self):
        self.client.post(self.url,self.plot_data(superficie_ha='8'))
        response=self.client.post(self.url,self.plot_data(superficie_ha='3'))
        self.assertContains(response,'superar')
        self.assertEqual(Potrero.objects.count(),1)
        response=self.client.post(f'/predios/{self.predio.pk}/editar/',{'nombre':'Mi campo','ubicacion':'Melipilla','superficie_ha':'7'})
        self.assertContains(response,'menor')

    def test_inactive_or_unknown_crop_rejected(self):
        self.crop.activo=False
        self.crop.save()
        self.assertEqual(self.client.post(self.url,self.plot_data()).status_code,200)
        self.assertEqual(self.client.post(self.url,self.plot_data(cultivo='9999')).status_code,200)
        self.assertEqual(Potrero.objects.count(),0)

    def test_empty_catalog_stays_empty(self):
        Cultivo.objects.all().delete()
        response=self.client.get('/')
        self.assertEqual(response.context['catalog']['cultivos'],[])
        self.assertEqual(response.context['catalog']['semillas'],[])

    @override_settings(MAP_TILE_URL='https://tiles.example/test-</script><script>bad()</script>/{z}/{x}/{y}.png')
    def test_map_configuration_is_safely_serialized(self):
        response=self.client.get('/predios/')
        self.assertNotContains(response,'test-</script>')
        self.assertContains(response,'\\u003C/script\\u003E')

    def test_map_uses_leaflet_and_keeps_manual_registration(self):
        response = self.client.get(self.url)
        self.assertContains(response,'leaflet-geoman')
        self.assertContains(response,'Dibujar campo')
        self.assertContains(response,'Medir línea')
        self.assertRedirects(self.client.post(self.url,self.plot_data()),f'/predios/{self.predio.pk}/')
        predio_form = self.client.get('/predios/nuevo/')
        self.assertContains(predio_form, 'id="map-form-summary"')
        self.assertContains(predio_form, 'id="map-summary-area"')
        self.assertContains(predio_form, 'id="map-summary-perimeter"')
        self.assertContains(predio_form, 'id="map-summary-location"')
        self.assertContains(predio_form, 'id="accept-perimeter"')
        self.assertContains(predio_form, 'id="confirm-and-continue"')
        self.assertContains(predio_form, 'id="terrain-form" hidden')

    def test_potrero_geojson_is_saved_and_recovered(self):
        self.client.post(self.url,self.plot_data(perimetro=json.dumps(POLYGON)))
        plot = Potrero.objects.get()
        self.assertEqual(plot.geojson['type'], 'Feature')
        self.assertEqual(plot.geojson['geometry']['type'], 'Polygon')
        self.assertEqual(plot.geojson['geometry']['coordinates'][0][0], plot.geojson['geometry']['coordinates'][0][-1])
        self.assertEqual(self.client.get('/predios/').context['farm_data']['plots'][0]['geojson'], plot.geojson)

    def test_polygon_perimeter_is_closed_and_included_in_map_data(self):
        self.client.post(self.url, self.plot_data(perimetro=json.dumps(POLYGON)))
        plot = Potrero.objects.get()
        perimeter = polygon_perimeter(POLYGON)
        self.assertGreater(perimeter, Decimal('350'))
        self.assertLess(perimeter, Decimal('450'))
        self.assertEqual(perimeter, polygon_perimeter(list(reversed(POLYGON))))
        map_plot = self.client.get('/predios/').context['farm_data']['plots'][0]
        self.assertEqual(map_plot['perimeterM'], float(perimeter))

    def test_map_initializes_without_turf_and_offers_boundary_drawing(self):
        listing = self.client.get('/predios/')
        form = self.client.get(self.url)
        self.assertContains(listing, 'predios-map.js')
        self.assertContains(listing, 'Información seleccionada')
        self.assertContains(listing, 'selected-terrain-details')
        self.assertNotContains(listing, 'turf.min.js')
        self.assertContains(form, 'Cancelar trazo')
        self.assertContains(form, 'finish-line')
        self.assertContains(form, 'clear-measurement')
        self.assertContains(form, 'live-perimeter')
        self.assertContains(form, 'live-area')
        self.assertNotContains(form, 'turf.min.js')

    def test_potrero_must_stay_inside_predio_boundary(self):
        boundary = [[-71.216,-33.687],[-71.213,-33.687],[-71.213,-33.684],[-71.216,-33.684]]
        self.predio.geojson = {
            'type':'Feature', 'properties':{},
            'geometry':{'type':'Polygon','coordinates':[boundary + [boundary[0]]]},
        }
        self.predio.save()
        outside = [[-71.219,-33.686],[-71.218,-33.686],[-71.218,-33.685],[-71.219,-33.685]]
        response = self.client.post(self.url, self.plot_data(perimetro=json.dumps(outside)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'debe quedar dentro del predio')
        self.assertFalse(Potrero.objects.exists())

    def test_potrero_form_shows_remaining_area_and_focuses_parent_boundary(self):
        boundary = [[-71.216,-33.687],[-71.213,-33.687],[-71.213,-33.684],[-71.216,-33.684]]
        self.predio.geojson = {
            'type':'Feature', 'properties':{},
            'geometry':{'type':'Polygon','coordinates':[boundary + [boundary[0]]]},
        }
        self.predio.save()
        Potrero.objects.create(
            predio=self.predio,
            nombre='Existente',
            superficie_ha=Decimal('2'),
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['potrero_superficie_disponible'], Decimal('8'))
        self.assertEqual(response.context['form'].fields['superficie_ha'].widget.attrs['max'], '8.0000')
        self.assertContains(response, 'Enfocar predio')
        self.assertContains(response, 'límite verde punteado')
        self.assertContains(response, 'Dibuja el potrero completamente dentro de ese límite')

    def test_potrero_overlap_with_same_farm_is_rejected(self):
        first = [[-71.215,-33.686],[-71.214,-33.686],[-71.214,-33.685],[-71.215,-33.685]]
        self.client.post(self.url,self.plot_data(perimetro=json.dumps(first)))
        second = [[-71.2145,-33.686],[-71.2135,-33.686],[-71.2135,-33.685],[-71.2145,-33.685]]
        response = self.client.post(self.url,self.plot_data(nombre='Potrero sur',perimetro=json.dumps(second)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'se superpone')
        self.assertEqual(Potrero.objects.count(), 1)

    def test_all_existing_module_routes_render(self):
        urls = [
            '/', '/predios/', '/predios/nuevo/', f'/predios/{self.predio.pk}/',
            f'/predios/{self.predio.pk}/editar/', '/decisiones/', '/productos/',
            '/calendario/', '/actividades/', '/actividades/nueva/', '/reportes/', '/busqueda/',
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="sidebar-quick-links"')
                quick_links = response.content.decode().split(
                    'id="sidebar-quick-links"', 1
                )[1].split('</nav>', 1)[0]
                self.assertEqual(quick_links.count('<a '), 7)
                for href in (
                    '/predios/nuevo/', '/predios/', '/actividades/nueva/',
                    '/decisiones/', '/decisiones/?herramienta=llevar&amp;tipo=insumos', '/productos/',
                    '/reportes/',
                ):
                    self.assertIn(f'href="{href}"', quick_links)

    def test_decision_center_tools_and_single_sidebar_link(self):
        response = self.client.get('/decisiones/')
        self.assertContains(response, 'Centro de decisiones')
        self.assertContains(response, 'Calcula, planifica y optimiza los recursos de tu terreno')
        for text in ('Cuánto llevar', 'Si alcanza', 'Cosecha', 'Ficha de insumo'):
            self.assertContains(response, text)
        decision_group = next(items for label, items in response.context['nav_groups'] if label == 'La decisión')
        self.assertEqual([(name, title) for name, title, _icon in decision_group], [('decisiones', 'Centro de decisiones')])

    def test_legacy_calculator_routes_redirect_to_integrated_tools(self):
        expected = {
            '/calculadora/?modo=insumos&plot=3': '/decisiones/?herramienta=llevar&tipo=insumos&plot=3',
            '/calculadora/': '/decisiones/?herramienta=llevar&tipo=semillas',
            '/cobertura/': '/decisiones/?herramienta=alcanza',
            '/predictor/': '/decisiones/?herramienta=cosecha',
            '/asesor/?crop=2': '/decisiones/?herramienta=ficha&crop=2',
        }
        for url, target in expected.items():
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), target, fetch_redirect_response=False)

    def test_csrf_required_to_save_terrain(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url,self.plot_data()).status_code,403)
        self.assertEqual(client.post('/predios/nuevo/', {}).status_code,403)


class GeometryTests(TestCase):
    def test_area_reference_and_orientation(self):
        # Approximately a 111 m x 93 m rectangle at latitude 33.686° S.
        area=polygon_area(POLYGON)
        self.assertGreater(area,Decimal('10200'))
        self.assertLess(area,Decimal('10500'))
        self.assertEqual(area,polygon_area(list(reversed(POLYGON))))

    def test_invalid_polygons(self):
        examples=[[],POLYGON[:2],[POLYGON[0]]*3,[POLYGON[0],POLYGON[2],POLYGON[1],POLYGON[3]],
                  [[0,0],[1,1],[2,2]],[[0,0],[1,float('nan')],[2,1]],[[True,0],[1,0],[1,1]],
                  [[181,0],[1,0],[1,1]],[[0,0],[1,0],[1,1]]*100,{'coordinates':POLYGON}]
        for points in examples:
            with self.subTest(points=points),self.assertRaises(ValidationError):
                polygon_area(points)


class CatalogSliceTests(TestCase):
    def test_existing_seed_command_and_catalog_contract(self):
        # Legacy demonstration data is used only in this isolated test database.
        call_command('seed_catalog',verbosity=0)
        user=User.objects.create_user('catalog',password=PASSWORD)
        self.client.force_login(user)
        response=self.client.get('/decisiones/')
        self.assertTrue(response.context['catalog']['fromDb'])
        seeds={item['crop']:item['density'] for item in response.context['catalog']['semillas']}
        self.assertEqual(seeds['Maíz'],25.0)
        self.assertEqual(seeds['Trigo'],160.0)
        maize_seed = next(item for item in response.context['catalog']['semillas'] if item['crop'] == 'Maíz')
        self.assertEqual(maize_seed['densitySource'], Cultivo.objects.get(nombre='Maíz').densidad_fuente)

    def test_catalog_does_not_invent_missing_seed_density(self):
        Cultivo.objects.create(nombre='Cultivo sin dosis')
        user=User.objects.create_user('catalog-empty',email='catalog-empty@example.com',password=PASSWORD)
        self.client.force_login(user)
        response=self.client.get('/decisiones/')
        self.assertEqual(response.context['catalog']['semillas'],[])


class ServerCalculationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('calculator', email='calculator@example.com', password=PASSWORD)
        self.other = User.objects.create_user('other', email='other@example.com', password=PASSWORD)
        self.crop = Cultivo.objects.create(nombre='Maíz')
        self.farm = Predio.objects.create(
            propietario=self.user, nombre='Campo de cálculo', ubicacion='Melipilla', superficie_ha=10
        )
        self.plot = Potrero.objects.create(
            predio=self.farm, nombre='Lote 1', cultivo=self.crop, superficie_ha=4
        )
        self.client.force_login(self.user)

    def calculate(self, **payload):
        return self.client.post(
            '/calculos/ejecutar/',
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_yield_calculation_uses_server_area_and_validates_values(self):
        response = self.calculate(
            operation='yield',
            plot_id=self.plot.pk,
            crop=self.crop.nombre,
            area='2.5',
            rate='6',
            source='Fuente técnica ingresada',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['production'], 15)
        self.assertFalse(response.json()['source_verified'])
        self.assertEqual(
            self.calculate(
                operation='yield',
                plot_id=self.plot.pk,
                crop=self.crop.nombre,
                area='-1',
                rate='6',
                source='Fuente técnica',
            ).status_code,
            400,
        )
        self.assertEqual(
            self.calculate(
                operation='yield',
                plot_id=self.plot.pk,
                crop=self.crop.nombre,
                area='2',
                rate='6',
            ).status_code,
            400,
        )

    def test_yield_prefers_verified_crop_zone_and_variety_reference(self):
        zone = Zona.objects.create(nombre='Zona rendimiento')
        self.farm.zona = zone
        self.farm.save(update_fields=['zona'])
        reference = ReferenciaAgronomica.objects.create(
            cultivo=self.crop,
            zona=zone,
            variedad='Híbrido A',
            rendimiento_ton_ha=Decimal('8.50'),
            institucion_fuente='Centro técnico',
            documento_fuente='Ensayo regional',
            url_fuente='https://example.org/yield',
            fecha_consulta_fuente='2026-10-01',
            estado=ReferenciaAgronomica.Estado.VERIFICADA,
        )
        self.plot.variedad = reference.variedad
        self.plot.save(update_fields=['variedad'])
        response = self.calculate(
            operation='yield',
            calculation_type='rendimiento',
            plot_id=self.plot.pk,
            crop=self.crop.nombre,
            area='2.5',
            rate='6',
            source='Fuente enviada por cliente',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rate'], 8.5)
        self.assertEqual(response.json()['production'], 21.25)
        self.assertTrue(response.json()['source_verified'])
        self.assertEqual(response.json()['source'], 'Centro técnico · Ensayo regional')
        self.assertEqual(response.json()['source_url'], 'https://example.org/yield')

    def test_standard_dose_calculation_keeps_area_times_dose_formula(self):
        response = self.calculate(
            operation='dose', plot_id=self.plot.pk, crop=self.crop.nombre,
            area='2.5', dose='12', unit='kg',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['amount'], 30)
        self.assertEqual(response.json()['unit'], 'kg')

    def test_seed_population_uses_explicit_parameters_and_source(self):
        response = self.calculate(
            operation='seed_population', plot_id=self.plot.pk, area='1',
            plants_m2='100', thousand_seed_weight_g='300',
            germination_pct='90', purity_pct='95', source='Ficha de semilla',
        )
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.json()['rate'], 100 * 300 / (100 * 0.9 * 0.95))
        self.assertEqual(
            self.calculate(
                operation='seed_population', plot_id=self.plot.pk, area='1',
                plants_m2='100', thousand_seed_weight_g='300',
                germination_pct='101', purity_pct='95', source='Ficha de semilla',
            ).status_code,
            400,
        )

    def test_coverage_preserves_unregistered_units_and_computes_availability(self):
        kind = TipoInsumo.objects.create(nombre='Fertilizante')
        product = Insumo.objects.create(tipo=kind, nombre='Producto sin unidad')
        response = self.calculate(
            operation='coverage', plot_id=self.plot.pk, crop=self.crop.nombre,
            product_id=product.pk, area='2', dose='3', stock='3',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['needed'], 6)
        self.assertEqual(response.json()['coveredHa'], 1)
        self.assertEqual(response.json()['unit'], '')

    def test_calculation_rejects_another_users_plot(self):
        other_farm = Predio.objects.create(
            propietario=self.other, nombre='Otro campo', ubicacion='Paine', superficie_ha=2
        )
        other_plot = Potrero.objects.create(predio=other_farm, nombre='Privado', superficie_ha=1)
        response = self.calculate(
            operation='yield', plot_id=other_plot.pk, crop=self.crop.nombre, area='1', rate='4'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('no pertenece', response.json()['error'])
        self.assertFalse(CalculoAgricola.objects.exists())

    def test_calculations_are_saved_and_report_history_is_user_scoped(self):
        response = self.calculate(
            operation='dose',
            calculation_type='semillas',
            plot_id=self.plot.pk,
            crop=self.crop.nombre,
            area='2',
            dose='15',
            unit='kg',
        )
        self.assertEqual(response.status_code, 200)
        calculation = CalculoAgricola.objects.get(pk=response.json()['calculation_id'])
        self.assertEqual(calculation.usuario, self.user)
        self.assertEqual(calculation.potrero, self.plot)
        self.assertEqual(calculation.operacion, CalculoAgricola.Operacion.DOSIS)
        self.assertEqual(calculation.entrada['area_ha'], '2')
        self.assertEqual(calculation.entrada['calculation_type'], 'semillas')
        self.assertEqual(calculation.resultado['amount'], 30)

        other_farm = Predio.objects.create(
            propietario=self.other,
            nombre='Campo ajeno',
            ubicacion='Paine',
            superficie_ha=2,
        )
        other_plot = Potrero.objects.create(
            predio=other_farm,
            nombre='Lote ajeno',
            superficie_ha=1,
        )
        private_calculation = CalculoAgricola.objects.create(
            usuario=self.other,
            potrero=other_plot,
            operacion=CalculoAgricola.Operacion.RENDIMIENTO,
            entrada={'calculation_type':'rendimiento'},
            resultado={'production':10},
        )
        report = self.client.get('/reportes/')
        self.assertEqual(
            [item['id'] for item in report.context['report_records']],
            [calculation.pk],
        )
        self.assertNotContains(report, 'Campo ajeno')
        self.assertContains(report, 'Cálculo guardado')

    def test_calculation_history_cannot_be_deleted(self):
        calculation = CalculoAgricola.objects.create(
            usuario=self.user,
            potrero=self.plot,
            operacion=CalculoAgricola.Operacion.DOSIS,
            entrada={},
            resultado={},
        )
        with self.assertRaises(ValidationError):
            calculation.delete()
        with self.assertRaises(ValidationError):
            CalculoAgricola.objects.filter(pk=calculation.pk).delete()

    def test_phytosanitary_coverage_requires_verified_authorized_target(self):
        kind = TipoInsumo.objects.create(nombre='Herbicida')
        product = Insumo.objects.create(
            tipo=kind, cultivo=self.crop, nombre='Producto autorizado',
            dosis_hectarea=Decimal('1.5'), unidad_dosis='L/ha',
            estado_verificacion='verified', fuente_nombre='Etiqueta',
            fuente_url='https://example.com/source', fecha_verificacion='2026-01-01',
            dosis_verificada=True, dosis_fuente='Etiqueta',
            etiqueta_url='https://example.com/label', numero_autorizacion_sag='REG-1',
            cultivos_autorizados=[self.crop.nombre], objetivos_control=['Maleza A'],
        )
        payload = {
            'operation':'coverage', 'plot_id':self.plot.pk, 'crop':self.crop.nombre,
            'product_id':product.pk, 'area':'2', 'dose':'99', 'stock':'3',
        }
        invalid = self.calculate(**payload)
        self.assertEqual(invalid.status_code, 400)
        valid = self.calculate(**payload, target='Maleza A')
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()['dose'], 1.5)
        self.assertEqual(valid.json()['coveredHa'], 2)

    def test_verified_maximum_dose_is_enforced_and_expired_products_are_rejected(self):
        kind = TipoInsumo.objects.create(nombre='Fertilizante')
        product = Insumo.objects.create(
            tipo=kind,
            cultivo=self.crop,
            nombre='Fertilizante con máximo',
            dosis_hectarea=Decimal('1'),
            unidad_dosis='kg/ha',
            dosis_maxima_hectarea=Decimal('1.5'),
            unidad_dosis_maxima='kg/ha',
            estado_verificacion='verified',
            fuente_nombre='Etiqueta técnica',
            fuente_url='https://example.com/max-dose',
            fecha_verificacion=timezone.localdate(),
            dosis_verificada=True,
            dosis_fuente='Etiqueta técnica',
        )
        excessive = self.calculate(
            operation='dose',
            plot_id=self.plot.pk,
            crop=self.crop.nombre,
            product_id=product.pk,
            area='1',
            dose='1.6',
            unit='kg',
        )
        self.assertEqual(excessive.status_code, 400)
        self.assertIn('supera el máximo', excessive.json()['error'])

        product.vigencia_hasta = timezone.localdate() - timedelta(days=1)
        product.save(update_fields=['vigencia_hasta'])
        expired = self.calculate(
            operation='dose',
            plot_id=self.plot.pk,
            crop=self.crop.nombre,
            product_id=product.pk,
            area='1',
            dose='1',
            unit='kg',
        )
        self.assertEqual(expired.status_code, 400)
        self.assertIn('no existe o no está vigente', expired.json()['error'])

    def test_fertilizer_nutrition_requires_verified_composition_and_need_source(self):
        kind = TipoInsumo.objects.create(nombre='Fertilizante')
        product = Insumo.objects.create(
            tipo=kind, nombre='Fertilizante N', unidad_dosis='kg/ha',
            estado_verificacion='verified', fuente_nombre='Ficha técnica',
            fuente_url='https://example.com/fertilizer', fecha_verificacion='2026-01-01',
            composicion_nutricional='10% N', nitrogeno_pct=Decimal('10'),
        )
        response = self.calculate(
            operation='fertilizer_nutrition', plot_id=self.plot.pk, area='2',
            product_id=product.pk, nutrient='N', need_per_ha='5',
            need_source='Análisis de suelo',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['amount'], 100)
        self.assertEqual(
            self.calculate(
                operation='fertilizer_nutrition', plot_id=self.plot.pk, area='2',
                product_id=product.pk, nutrient='N', need_per_ha='5',
            ).status_code,
            400,
        )

    def test_calculation_endpoint_enforces_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            '/calculos/ejecutar/',
            data=json.dumps({'operation':'yield', 'plot_id':self.plot.pk, 'area':'1', 'rate':'4', 'crop':'Maíz'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)


class ActividadAgricolaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'activity-owner@example.com',
            email='activity-owner@example.com',
            password=PASSWORD,
        )
        self.other = User.objects.create_user(
            'activity-other@example.com',
            email='activity-other@example.com',
            password=PASSWORD,
        )
        self.predio = Predio.objects.create(
            propietario=self.user,
            nombre='Campo de actividades',
            ubicacion='Melipilla',
            superficie_ha=Decimal('8'),
        )
        self.potrero = Potrero.objects.create(
            predio=self.predio,
            nombre='Lote norte',
            superficie_ha=Decimal('2'),
        )
        other_farm = Predio.objects.create(
            propietario=self.other,
            nombre='Campo ajeno',
            ubicacion='Paine',
            superficie_ha=Decimal('4'),
        )
        self.other_plot = Potrero.objects.create(
            predio=other_farm,
            nombre='Lote ajeno',
            superficie_ha=Decimal('1'),
        )
        self.client.force_login(self.user)
        self.create_url = '/actividades/nueva/'

    def activity_data(self, **values):
        return {
            'nombre':'Aplicar riego',
            'tipo':'riego',
            'potrero':self.potrero.pk,
            'fecha_programada':'2026-11-05',
            'estado':'pendiente',
            'observaciones':'Revisar humedad del suelo.',
            **values,
        }

    def test_create_activity_persists_across_a_new_authenticated_session(self):
        response = self.client.post(self.create_url, self.activity_data())
        activity = ActividadAgricola.objects.get()
        self.assertRedirects(response, f'/actividades/{activity.pk}/')
        self.assertEqual(activity.usuario, self.user)
        self.assertEqual(activity.potrero, self.potrero)
        self.assertEqual(activity.estado, ActividadAgricola.Estado.PENDIENTE)

        self.client.logout()
        another_session = Client()
        another_session.force_login(self.user)
        self.assertContains(another_session.get('/actividades/'), 'Aplicar riego')
        self.assertContains(another_session.get('/'), 'Aplicar riego')
        self.assertContains(another_session.get('/calendario/'), 'Aplicar riego')

    def test_dashboard_counters_use_owned_farm_data(self):
        crop = Cultivo.objects.create(nombre='Cultivo del potrero')
        self.potrero.cultivo = crop
        self.potrero.save(update_fields=['cultivo'])
        response = self.client.get('/')
        stats = response.context['farm_data']['stats']
        self.assertEqual(stats['predios'], 1)
        self.assertEqual(stats['potreros'], 1)
        self.assertEqual(stats['superficie_predios'], 8.0)
        self.assertEqual(stats['superficie'], 2.0)
        self.assertEqual(stats['superficie_sin_asignar'], 6.0)
        self.assertEqual(stats['distribucion_pct'], 25.0)
        self.assertEqual(stats['cultivos'], 1)
        self.assertEqual(response.context['pending_activity_count'], 0)
        self.assertContains(response, '8,00')
        self.assertContains(response, '2,00')
        self.assertContains(response, 'Mis predios')
        self.assertContains(response, 'Potreros activos')
        self.assertContains(response, 'Distribución de superficie')
        self.assertContains(response, 'sidebar-quick-links')
        self.assertContains(response, 'Calcular insumos')
        self.assertNotContains(response, '<nav class="card quick-links"')
        self.assertContains(response, f'/predios/{self.predio.pk}/')
        self.assertContains(response, f'/predios/{self.predio.pk}/potreros/{self.potrero.pk}/editar/')

    def test_dashboard_surfaces_and_counts_are_isolated_and_refresh_after_registration(self):
        response = self.client.get('/')
        stats = response.context['farm_data']['stats']
        self.assertEqual(stats['predios'], 1)
        self.assertEqual(stats['potreros'], 1)
        self.assertEqual(stats['superficie_predios'], 8.0)
        self.assertEqual(stats['superficie'], 2.0)
        self.assertEqual(stats['cultivos'], 0)
        self.assertNotContains(response, 'Campo ajeno')

        boundary = [[-71.216,-33.687],[-71.213,-33.687],[-71.213,-33.684],[-71.216,-33.684]]
        feature = {
            'type':'Feature','properties':{},
            'geometry':{'type':'Polygon','coordinates':[boundary + [boundary[0]]]},
        }
        create_response = self.client.post('/predios/nuevo/', {
            'nombre':'Nuevo dashboard','ubicacion':'Paine','superficie_ha':'',
            'geojson':json.dumps(feature),'perimetro_aceptado':'on',
        })
        self.assertEqual(create_response.status_code, 302)
        dashboard = self.client.get('/')
        self.assertEqual(dashboard.context['farm_data']['stats']['predios'], 2)
        self.assertAlmostEqual(dashboard.context['farm_data']['stats']['superficie_predios'], 8 + float(polygon_area(boundary) / 10000), places=3)
        self.assertContains(dashboard, 'Nuevo dashboard')

    def test_dashboard_refreshes_assigned_area_and_active_crop_after_registering_plot(self):
        crop = Cultivo.objects.create(nombre='Trigo de dashboard')
        response = self.client.post(
            f'/predios/{self.predio.pk}/potreros/nuevo/',
            {
                'nombre':'Lote nuevo',
                'cultivo':crop.pk,
                'variedad':'',
                'fecha_siembra':'',
                'fecha_cosecha':'',
                'superficie_ha':'1.5',
                'latitud':'',
                'longitud':'',
                'perimetro':'[]',
            },
        )
        self.assertEqual(response.status_code, 302)
        dashboard = self.client.get('/')
        stats = dashboard.context['farm_data']['stats']
        self.assertEqual(stats['potreros'], 2)
        self.assertEqual(stats['superficie'], 3.5)
        self.assertEqual(stats['superficie_sin_asignar'], 4.5)
        self.assertEqual(stats['cultivos'], 1)
        self.assertContains(dashboard, 'Lote nuevo')
        self.assertContains(dashboard, 'Trigo de dashboard')

    def test_dashboard_empty_states_and_calculation_history_do_not_use_fictional_data(self):
        self.client.force_login(self.other)
        response = self.client.get('/')
        stats = response.context['farm_data']['stats']
        self.assertEqual(stats['predios'], 1)
        self.assertEqual(stats['potreros'], 1)
        self.assertContains(response, 'No hay actividades pendientes guardadas')
        self.assertContains(response, 'Aún no hay historial persistente de cálculos')
        self.assertContains(response, 'Centro de decisiones')

        self.client.force_login(User.objects.create_user(
            'dashboard-empty@example.com',
            email='dashboard-empty@example.com',
            password=PASSWORD,
        ))
        empty_response = self.client.get('/')
        self.assertEqual(empty_response.context['farm_data']['stats']['predios'], 0)
        self.assertEqual(empty_response.context['farm_data']['stats']['potreros'], 0)
        self.assertContains(empty_response, 'Registrar predio')
        self.assertContains(empty_response, 'Registra un predio para consultar la distribución')
        self.assertContains(empty_response, 'Registrar un predio')

    def test_edit_and_status_updates_are_persistent_and_dashboard_count_is_real(self):
        activity = ActividadAgricola.objects.create(
            usuario=self.user,
            potrero=self.potrero,
            nombre='Preparar suelo',
            tipo=ActividadAgricola.Tipo.PREPARACION,
            fecha_programada='2026-10-30',
        )
        self.assertContains(
            self.client.get(f'/actividades/{activity.pk}/editar/'),
            'value="2026-10-30"',
        )
        response = self.client.post(
            f'/actividades/{activity.pk}/editar/',
            self.activity_data(nombre='Riego actualizado', tipo='riego'),
        )
        self.assertRedirects(response, f'/actividades/{activity.pk}/')
        activity.refresh_from_db()
        self.assertEqual(activity.nombre, 'Riego actualizado')
        self.assertEqual(activity.tipo, ActividadAgricola.Tipo.RIEGO)

        dashboard = self.client.get('/')
        self.assertEqual(dashboard.context['pending_activity_count'], 1)
        self.assertContains(dashboard, 'Actividades pendientes')
        self.assertContains(dashboard, 'Riego actualizado')
        self.assertContains(dashboard, 'Pendiente')
        response = self.client.post(
            f'/actividades/{activity.pk}/estado/',
            {'estado':'completada', 'next':'dashboard'},
        )
        self.assertRedirects(response, '/')
        activity.refresh_from_db()
        self.assertEqual(activity.estado, ActividadAgricola.Estado.COMPLETADA)
        self.assertEqual(self.client.get('/').context['pending_activity_count'], 0)
        self.assertContains(self.client.get('/calendario/'), 'Riego actualizado')

    def test_invalid_activity_fields_and_foreign_potrero_are_rejected(self):
        invalid_values = [
            self.activity_data(nombre=''),
            self.activity_data(tipo='fumigación'),
            self.activity_data(fecha_programada='no-es-fecha'),
            self.activity_data(potrero=self.other_plot.pk),
        ]
        for data in invalid_values:
            with self.subTest(data=data):
                response = self.client.post(self.create_url, data)
                self.assertEqual(response.status_code, 200)
        self.assertFalse(ActividadAgricola.objects.exists())

    def test_user_cannot_read_edit_change_or_delete_another_users_activity(self):
        activity = ActividadAgricola.objects.create(
            usuario=self.other,
            potrero=self.other_plot,
            nombre='Actividad privada',
            tipo=ActividadAgricola.Tipo.SIEMBRA,
            fecha_programada='2026-11-01',
        )
        detail_url = f'/actividades/{activity.pk}/'
        for url in [detail_url, f'/actividades/{activity.pk}/editar/', f'/actividades/{activity.pk}/eliminar/']:
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(
            self.client.post(f'/actividades/{activity.pk}/estado/', {'estado':'completada'}).status_code,
            404,
        )
        self.assertNotContains(self.client.get('/actividades/'), 'Actividad privada')
        self.assertNotContains(self.client.get('/'), 'Actividad privada')
        self.assertNotContains(self.client.get('/calendario/'), 'Actividad privada')
        activity.refresh_from_db()
        self.assertEqual(activity.estado, ActividadAgricola.Estado.PENDIENTE)

    def test_delete_requires_confirmation_and_post(self):
        activity = ActividadAgricola.objects.create(
            usuario=self.user,
            potrero=self.potrero,
            nombre='Actividad a eliminar',
            tipo=ActividadAgricola.Tipo.MONITOREO,
            fecha_programada='2026-11-10',
        )
        delete_url = f'/actividades/{activity.pk}/eliminar/'
        self.assertContains(self.client.get(delete_url), 'Esta acción no se puede deshacer')
        self.assertTrue(ActividadAgricola.objects.filter(pk=activity.pk).exists())
        response = self.client.post(delete_url)
        self.assertRedirects(response, '/actividades/')
        self.assertFalse(ActividadAgricola.objects.filter(pk=activity.pk).exists())

    def test_invalid_status_is_rejected_and_activity_routes_require_authentication(self):
        activity = ActividadAgricola.objects.create(
            usuario=self.user,
            potrero=self.potrero,
            nombre='Regar',
            tipo=ActividadAgricola.Tipo.RIEGO,
            fecha_programada='2026-11-10',
        )
        response = self.client.post(
            f'/actividades/{activity.pk}/estado/',
            {'estado':'inventado'},
        )
        self.assertRedirects(response, f'/actividades/{activity.pk}/')
        activity.refresh_from_db()
        self.assertEqual(activity.estado, ActividadAgricola.Estado.PENDIENTE)

        self.client.logout()
        for url in [
            '/actividades/',
            '/actividades/nueva/',
            f'/actividades/{activity.pk}/',
            f'/actividades/{activity.pk}/editar/',
            f'/actividades/{activity.pk}/eliminar/',
        ]:
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_status_endpoint_enforces_csrf(self):
        activity = ActividadAgricola.objects.create(
            usuario=self.user,
            potrero=self.potrero,
            nombre='Revisar cultivo',
            tipo=ActividadAgricola.Tipo.MONITOREO,
            fecha_programada='2026-11-10',
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            f'/actividades/{activity.pk}/estado/',
            {'estado':'completada'},
        )
        self.assertEqual(response.status_code, 403)


class AgronomicCalendarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='calendar-user',
            email='calendar@example.com',
            password=PASSWORD,
        )
        self.client.force_login(self.user)
        self.crop = Cultivo.objects.create(nombre='Trigo de prueba')
        self.zone = Zona.objects.create(nombre='Zona de prueba')

    def create_reference(self, **values):
        data = {
            'cultivo':self.crop,
            'zona':self.zone,
            'siembra_inicio_mes':2,
            'siembra_inicio_dia':1,
            'siembra_fin_mes':2,
            'siembra_fin_dia':10,
            'cosecha_inicio_mes':7,
            'cosecha_inicio_dia':1,
            'cosecha_fin_mes':8,
            'cosecha_fin_dia':31,
            'duracion_ciclo_dias':120,
            'institucion_fuente':'Institución técnica',
            'documento_fuente':'Manual agronómico',
            'url_fuente':'https://example.org/manual',
            'fecha_consulta_fuente':'2026-10-01',
            'estado':ReferenciaAgronomica.Estado.VERIFICADA,
        }
        data.update(values)
        return ReferenciaAgronomica.objects.create(**data)

    def evaluate(self, **values):
        return self.client.post(
            '/calendario/evaluar/',
            data=json.dumps({
                'evaluation':'sowing',
                'crop_id':self.crop.pk,
                'zone_id':self.zone.pk,
                'proposed_date':'2026-02-05',
                **values,
            }),
            content_type='application/json',
        )

    def test_calendar_displays_only_documented_verified_references(self):
        verified = self.create_reference()
        self.create_reference(
            variedad='Sin fuente',
            estado=ReferenciaAgronomica.Estado.BORRADOR,
            institucion_fuente='',
            documento_fuente='',
            url_fuente='',
            fecha_consulta_fuente=None,
        )
        response = self.client.get('/calendario/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ventana de siembra')
        self.assertContains(response, 'calendar-references')
        self.assertEqual(
            [reference['id'] for reference in response.context['calendar_references']],
            [verified.pk, verified.pk + 1],
        )
        self.assertNotContains(response, 'Referencia general para la Zona Central')

    def test_missing_verified_reference_returns_insufficient_information(self):
        response = self.evaluate()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'insufficient')
        self.assertIsNone(response.json()['source'])

    def test_sowing_window_classifies_inside_near_and_outside_using_configuration(self):
        self.create_reference()
        ConfiguracionAgronomica.objects.create(margen_ventana_dias=15)
        cases = [
            ('2026-02-05', 'within'),
            ('2026-01-17', 'near'),
            ('2026-01-16', 'outside'),
        ]
        for proposed_date, expected_status in cases:
            with self.subTest(proposed_date=proposed_date):
                response = self.evaluate(proposed_date=proposed_date)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['status'], expected_status)
                self.assertEqual(response.json()['margin_days'], 15)
                self.assertEqual(response.json()['source']['institution'], 'Institución técnica')

    def test_sowing_window_crossing_calendar_year_is_classified_correctly(self):
        self.create_reference(
            siembra_inicio_mes=11,
            siembra_inicio_dia=20,
            siembra_fin_mes=2,
            siembra_fin_dia=10,
        )
        response = self.evaluate(proposed_date='2027-01-15')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'within')

    def test_variety_specific_reference_is_preferred_over_general_reference(self):
        self.create_reference(institucion_fuente='Fuente general')
        self.create_reference(
            variedad='Línea A',
            institucion_fuente='Fuente de variedad',
            siembra_inicio_mes=3,
            siembra_inicio_dia=1,
            siembra_fin_mes=3,
            siembra_fin_dia=10,
        )
        response = self.evaluate(
            variety='Línea A',
            proposed_date='2026-03-05',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'within')
        self.assertEqual(response.json()['source']['institution'], 'Fuente de variedad')

    def test_harvest_compares_window_and_documented_cycle(self):
        reference = self.create_reference()
        response = self.client.post(
            '/calendario/evaluar/',
            data=json.dumps({
                'evaluation':'harvest',
                'crop_id':self.crop.pk,
                'zone_id':self.zone.pk,
                'sowing_date':'2026-03-01',
                'proposed_date':'2026-07-01',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'within')
        self.assertEqual(response.json()['expected_cycle_days'], reference.duracion_ciclo_dias)
        self.assertEqual(response.json()['elapsed_days'], 122)
        self.assertIn('madurez real', response.json()['disclaimer'])

    def test_harvest_reports_near_and_cycle_outside_states(self):
        self.create_reference()
        base_payload = {
            'evaluation':'harvest',
            'crop_id':self.crop.pk,
            'zone_id':self.zone.pk,
            'sowing_date':'2026-03-01',
        }
        near = self.client.post(
            '/calendario/evaluar/',
            data=json.dumps({**base_payload, 'proposed_date':'2026-06-16'}),
            content_type='application/json',
        )
        self.assertEqual(near.status_code, 200)
        self.assertEqual(near.json()['status'], 'near')
        outside_cycle = self.client.post(
            '/calendario/evaluar/',
            data=json.dumps({**base_payload, 'proposed_date':'2026-08-31'}),
            content_type='application/json',
        )
        self.assertEqual(outside_cycle.status_code, 200)
        self.assertEqual(outside_cycle.json()['status'], 'outside')

    def test_harvest_rejects_invalid_order_and_endpoint_requires_login_and_post(self):
        self.create_reference()
        invalid_order = self.client.post(
            '/calendario/evaluar/',
            data=json.dumps({
                'evaluation':'harvest',
                'crop_id':self.crop.pk,
                'zone_id':self.zone.pk,
                'sowing_date':'2026-07-01',
                'proposed_date':'2026-03-01',
            }),
            content_type='application/json',
        )
        self.assertEqual(invalid_order.status_code, 400)
        self.assertContains(invalid_order, 'no puede ser anterior', status_code=400)

        self.assertEqual(self.client.get('/calendario/evaluar/').status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post('/calendario/evaluar/').status_code, 302)

    def test_reference_requires_complete_valid_windows_and_source_when_verified(self):
        reference = ReferenciaAgronomica(
            cultivo=self.crop,
            zona=self.zone,
            siembra_inicio_mes=2,
            siembra_inicio_dia=30,
        )
        with self.assertRaises(ValidationError):
            reference.full_clean()

        incomplete_source = ReferenciaAgronomica(
            cultivo=self.crop,
            zona=self.zone,
            estado=ReferenciaAgronomica.Estado.VERIFICADA,
        )
        with self.assertRaises(ValidationError):
            incomplete_source.full_clean()

    def test_evaluator_rejects_non_json_and_invalid_catalog_ids(self):
        self.assertEqual(
            self.client.post('/calendario/evaluar/', {'evaluation':'sowing'}).status_code,
            415,
        )
        response = self.client.post(
            '/calendario/evaluar/',
            data=json.dumps({
                'evaluation':'sowing',
                'crop_id':99999,
                'zone_id':self.zone.pk,
                'proposed_date':'2026-02-05',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_evaluation_endpoint_enforces_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            '/calendario/evaluar/',
            data=json.dumps({
                'evaluation':'sowing',
                'crop_id':self.crop.pk,
                'zone_id':self.zone.pk,
                'proposed_date':'2026-02-05',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)


class TemporadaCultivoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='season-user',
            email='season@example.com',
            password=PASSWORD,
        )
        self.other = User.objects.create_user(
            username='other-season-user',
            email='other-season@example.com',
            password=PASSWORD,
        )
        self.crop = Cultivo.objects.create(nombre='Cultivo legado')
        self.new_crop = Cultivo.objects.create(nombre='Cultivo nuevo')
        self.predio = Predio.objects.create(
            propietario=self.user,
            nombre='Predio temporadas',
            ubicacion='Melipilla',
            superficie_ha=5,
        )
        self.potrero = Potrero.objects.create(
            predio=self.predio,
            nombre='Potrero rotación',
            cultivo=self.crop,
            variedad='Variedad antigua',
            fecha_siembra='2025-09-01',
            fecha_cosecha='2026-02-01',
            superficie_ha=2,
        )
        self.client.force_login(self.user)
        self.create_url = (
            f'/predios/{self.predio.pk}/potreros/{self.potrero.pk}/temporadas/nueva/'
        )

    def season_data(self, **values):
        return {
            'cultivo':self.new_crop.pk,
            'variedad':'Variedad nueva',
            'fecha_siembra':'2026-09-15',
            'fecha_cosecha':'2027-02-10',
            'estado':TemporadaCultivo.Estado.PLANIFICADA,
            'observaciones':'Rotación de este ciclo.',
            **values,
        }

    def test_each_new_season_persists_without_overwriting_legacy_potrero_data(self):
        first_response = self.client.post(self.create_url, self.season_data())
        self.assertRedirects(first_response, f'/predios/{self.predio.pk}/')
        first = TemporadaCultivo.objects.get()
        self.assertEqual(first.potrero, self.potrero)
        self.assertEqual(first.cultivo, self.new_crop)
        self.assertEqual(first.variedad, 'Variedad nueva')
        self.assertEqual(first.observaciones, 'Rotación de este ciclo.')

        second_response = self.client.post(
            self.create_url,
            self.season_data(
                cultivo=self.crop.pk,
                variedad='Otra temporada',
                fecha_siembra='2027-09-15',
                fecha_cosecha='2028-02-10',
            ),
        )
        self.assertRedirects(second_response, f'/predios/{self.predio.pk}/')
        self.potrero.refresh_from_db()
        self.assertEqual(self.potrero.cultivo, self.crop)
        self.assertEqual(self.potrero.variedad, 'Variedad antigua')
        self.assertEqual(self.potrero.fecha_siembra.isoformat(), '2025-09-01')
        self.assertEqual(self.potrero.fecha_cosecha.isoformat(), '2026-02-01')
        self.assertEqual(self.potrero.temporadas.count(), 2)
        self.assertContains(self.client.get(f'/predios/{self.predio.pk}/'), 'Variedad nueva')
        self.assertContains(self.client.get(f'/predios/{self.predio.pk}/'), 'Otra temporada')

        self.client.logout()
        self.assertRedirects(
            self.client.post(
                '/login/',
                {'username':'season-user', 'password':PASSWORD},
            ),
            '/',
        )
        self.assertEqual(
            list(self.potrero.temporadas.values_list('cultivo__nombre', flat=True)),
            ['Cultivo legado', 'Cultivo nuevo'],
        )

    def test_season_validation_and_non_deletion(self):
        response = self.client.post(
            self.create_url,
            self.season_data(
                fecha_siembra='2027-03-01',
                fecha_cosecha='2027-02-28',
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La cosecha no puede ser anterior a la siembra.')
        self.assertFalse(TemporadaCultivo.objects.exists())

        response = self.client.post(
            self.create_url,
            self.season_data(
                fecha_siembra='',
                fecha_cosecha='',
                estado=TemporadaCultivo.Estado.SEMBRADA,
            ),
        )
        self.assertContains(response, 'Registra la fecha de siembra')
        self.assertFalse(TemporadaCultivo.objects.exists())

        season = TemporadaCultivo.objects.create(
            potrero=self.potrero,
            cultivo=self.new_crop,
            fecha_siembra='2026-09-15',
        )
        with self.assertRaises(ValidationError):
            season.delete()
        with self.assertRaises(ValidationError):
            TemporadaCultivo.objects.filter(pk=season.pk).delete()

    def test_user_cannot_create_or_edit_seasons_for_another_users_plot(self):
        other_farm = Predio.objects.create(
            propietario=self.other,
            nombre='Predio privado',
            ubicacion='Paine',
            superficie_ha=4,
        )
        other_plot = Potrero.objects.create(
            predio=other_farm,
            nombre='Potrero privado',
            superficie_ha=1,
        )
        other_season = TemporadaCultivo.objects.create(
            potrero=other_plot,
            cultivo=self.new_crop,
            fecha_siembra='2026-09-15',
        )
        create_other_url = (
            f'/predios/{other_farm.pk}/potreros/{other_plot.pk}/temporadas/nueva/'
        )
        edit_other_url = (
            f'/predios/{other_farm.pk}/potreros/{other_plot.pk}/'
            f'temporadas/{other_season.pk}/editar/'
        )
        self.assertEqual(self.client.get(create_other_url).status_code, 404)
        self.assertEqual(self.client.post(create_other_url, self.season_data()).status_code, 404)
        self.assertEqual(self.client.get(edit_other_url).status_code, 404)
        self.assertNotContains(self.client.get(f'/predios/{self.predio.pk}/'), 'Potrero privado')

    def test_calendar_only_offers_the_current_users_plots_and_seasons(self):
        own_season = TemporadaCultivo.objects.create(
            potrero=self.potrero,
            cultivo=self.new_crop,
            fecha_siembra='2026-09-15',
        )
        other_farm = Predio.objects.create(
            propietario=self.other,
            nombre='Predio privado',
            ubicacion='Paine',
            superficie_ha=4,
        )
        other_plot = Potrero.objects.create(
            predio=other_farm,
            nombre='Potrero privado',
            superficie_ha=1,
        )
        TemporadaCultivo.objects.create(
            potrero=other_plot,
            cultivo=self.crop,
            fecha_siembra='2026-09-15',
        )
        response = self.client.get('/calendario/')
        self.assertEqual(
            [plot['id'] for plot in response.context['calendar_plots']],
            [self.potrero.pk],
        )
        self.assertEqual(
            [season['id'] for season in response.context['calendar_plots'][0]['seasons']],
            [own_season.pk],
        )


# ---------------------------------------------------------------------------
# Integración de calendario, temporadas, centro de decisiones y catálogo.
# Todos los datos de estas pruebas son ficticios y viven solo en la base de pruebas.
# ---------------------------------------------------------------------------
from datetime import date as _date


def _verified_source():
    return dict(
        institucion_fuente='Institución de prueba', documento_fuente='Documento de prueba',
        url_fuente='https://example.org/prueba', fecha_consulta_fuente=_date(2026, 10, 1),
        estado=ReferenciaAgronomica.Estado.VERIFICADA,
    )


class IntegrationBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('owner', email='owner@example.com', password=PASSWORD)
        self.other = User.objects.create_user('intruder', email='intruder@example.com', password=PASSWORD)
        self.zone = Zona.objects.create(nombre='Zona prueba')
        self.zone2 = Zona.objects.create(nombre='Zona prueba 2')
        self.maize = Cultivo.objects.create(nombre='Maíz prueba')
        self.wheat = Cultivo.objects.create(nombre='Trigo prueba')
        self.farm = Predio.objects.create(propietario=self.user, nombre='Campo', ubicacion='X', superficie_ha=10, zona=self.zone)
        self.plot = Potrero.objects.create(predio=self.farm, nombre='Lote A', superficie_ha=4)
        self.other_farm = Predio.objects.create(propietario=self.other, nombre='Ajeno', ubicacion='Y', superficie_ha=5)
        self.other_plot = Potrero.objects.create(predio=self.other_farm, nombre='Lote ajeno', superficie_ha=1)
        self.client.force_login(self.user)

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')


class CropAssignmentTests(IntegrationBase):
    def url(self, plot=None):
        return f'/api/potreros/{(plot or self.plot).pk}/cultivo/'

    def test_assign_creates_season_updates_snapshot_and_history(self):
        response = self.post_json(self.url(), {
            'crop_id': self.maize.pk, 'variety': 'H1', 'season': '2026-2027',
            'sowing_date': '2026-10-10', 'harvest_date': '2027-03-30', 'status': 'sown', 'notes': 'Nota',
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.cultivo, self.maize)
        self.assertEqual(self.plot.variedad, 'H1')
        self.assertEqual(self.plot.fecha_siembra, _date(2026, 10, 10))
        season = self.plot.temporadas.get()
        self.assertEqual(season.temporada_agricola, '2026-2027')
        self.assertEqual(season.estado, 'sown')
        self.assertTrue(PredioHistorial.objects.filter(potrero=self.plot, accion='crop_assigned').exists())
        data = response.json()['plot']
        self.assertEqual(data['crop'], 'Maíz prueba')
        self.assertEqual(len(data['seasons']), 1)

    def test_changing_crop_keeps_previous_season_and_legacy_crop(self):
        self.plot.cultivo = self.wheat
        self.plot.fecha_siembra = _date(2026, 5, 1)
        self.plot.save()
        response = self.post_json(self.url(), {'crop_id': self.maize.pk, 'sowing_date': '2026-10-01'})
        self.assertEqual(response.status_code, 200, response.content)
        seasons = list(self.plot.temporadas.order_by('creado', 'pk'))
        self.assertEqual([s.cultivo for s in seasons], [self.wheat, self.maize])
        self.assertEqual(seasons[0].fecha_siembra, _date(2026, 5, 1))
        self.assertEqual(seasons[0].estado, 'closed')
        response = self.post_json(self.url(), {'crop_id': self.wheat.pk, 'close_previous': False})
        self.assertEqual(self.plot.temporadas.count(), 3)
        self.assertEqual(self.plot.temporadas.get(cultivo=self.maize).estado, 'planned')

    def test_update_dates_mode_keeps_crop_and_requires_same_crop(self):
        self.post_json(self.url(), {'crop_id': self.maize.pk})
        season = self.plot.temporadas.get()
        response = self.post_json(self.url(), {
            'mode': 'update_dates', 'season_id': season.pk, 'crop_id': self.maize.pk,
            'sowing_date': '2026-10-05', 'harvest_date': '2027-03-01', 'status': 'planned',
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.plot.temporadas.count(), 1)
        season.refresh_from_db()
        self.assertEqual(season.fecha_siembra, _date(2026, 10, 5))
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.fecha_cosecha, _date(2027, 3, 1))
        response = self.post_json(self.url(), {'mode': 'update_dates', 'season_id': season.pk, 'crop_id': self.wheat.pk})
        self.assertEqual(response.status_code, 400)

    def test_validation_and_isolation(self):
        self.assertEqual(self.post_json(self.url(self.other_plot), {'crop_id': self.maize.pk}).status_code, 404)
        self.assertEqual(self.other_plot.temporadas.count(), 0)
        bad_dates = self.post_json(self.url(), {'crop_id': self.maize.pk, 'sowing_date': '2026-10-10', 'harvest_date': '2026-01-01'})
        self.assertEqual(bad_dates.status_code, 400)
        self.assertIn('cosecha', bad_dates.json()['error'])
        self.maize.activo = False
        self.maize.save()
        self.assertEqual(self.post_json(self.url(), {'crop_id': self.maize.pk}).status_code, 400)
        self.assertEqual(self.post_json(self.url(), {'crop_id': self.wheat.pk, 'season': '2026-2030'}).status_code, 400)
        self.assertEqual(self.plot.temporadas.count(), 0)
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(self.url(), data=json.dumps({'crop_id': self.maize.pk}), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_potrero_form_crop_change_preserves_traceability(self):
        url = f'/predios/{self.farm.pk}/potreros/{self.plot.pk}/editar/'
        base = {'nombre': 'Lote A', 'superficie_ha': '4', 'perimetro': '[]', 'variedad': '', 'fecha_siembra': '', 'fecha_cosecha': '', 'latitud': '', 'longitud': ''}
        self.client.post(url, {**base, 'cultivo': self.wheat.pk})
        self.client.post(url, {**base, 'cultivo': self.maize.pk})
        self.assertEqual([s.cultivo for s in self.plot.temporadas.order_by('creado', 'pk')], [self.wheat, self.maize])

    def test_predios_page_selects_plot_and_isolates_other_users(self):
        response = self.client.get(f'/predios/?potrero={self.plot.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-initial-plot="%s"' % self.plot.pk)
        self.assertContains(response, 'id="crop-dialog"')
        self.assertEqual(self.client.get(f'/predios/?potrero={self.other_plot.pk}').status_code, 404)
        self.assertEqual(self.client.get(f'/api/potreros/{self.other_plot.pk}/').status_code, 404)


class CalendarIntegrationTests(IntegrationBase):
    def setUp(self):
        super().setUp()
        self.ref = ReferenciaAgronomica.objects.create(
            cultivo=self.maize, zona=self.zone, siembra_inicio_mes=9, siembra_inicio_dia=15,
            siembra_fin_mes=11, siembra_fin_dia=30, cosecha_inicio_mes=3, cosecha_inicio_dia=1,
            cosecha_fin_mes=5, cosecha_fin_dia=15, duracion_ciclo_dias=170, **_verified_source(),
        )
        ReferenciaAgronomica.objects.create(cultivo=self.wheat, zona=self.zone2, variedad='Invernal', siembra_inicio_mes=5,
            siembra_inicio_dia=1, siembra_fin_mes=7, siembra_fin_dia=15, **_verified_source())

    def evaluate(self, **payload):
        return self.post_json('/calendario/evaluar/', payload)

    def test_calendar_sends_all_zones_and_variety_index(self):
        response = self.client.get('/calendario/')
        self.assertEqual(response.status_code, 200)
        crops = {item['crop'] for item in response.context['calendar_references']}
        self.assertEqual(crops, {'Maíz prueba', 'Trigo prueba'})
        self.assertIn({'cropId': self.wheat.pk, 'zoneId': self.zone2.pk, 'variety': 'Invernal'}, response.context['calendar_variety_index'])
        self.assertContains(response, 'Fuera de ventanas documentadas')
        self.assertContains(response, 'id="calendar-save"')

    def test_year_specific_reference_has_priority(self):
        ReferenciaAgronomica.objects.create(cultivo=self.maize, zona=self.zone, anio_referencia=2027,
            siembra_inicio_mes=10, siembra_inicio_dia=20, siembra_fin_mes=10, siembra_fin_dia=31, **_verified_source())
        within_recurring = self.evaluate(evaluation='sowing', crop_id=self.maize.pk, zone_id=self.zone.pk, proposed_date='2026-10-01')
        self.assertEqual(within_recurring.json()['status'], 'within')
        specific = self.evaluate(evaluation='sowing', crop_id=self.maize.pk, zone_id=self.zone.pk, proposed_date='2027-10-10')
        self.assertEqual(specific.json()['status'], 'near')
        self.assertEqual(specific.json()['reference_context']['year'], 2027)

    def test_harvest_across_years_and_leap_year(self):
        normal = self.evaluate(evaluation='harvest', crop_id=self.maize.pk, zone_id=self.zone.pk,
                               sowing_date='2026-10-01', proposed_date='2027-03-20').json()
        leap = self.evaluate(evaluation='harvest', crop_id=self.maize.pk, zone_id=self.zone.pk,
                             sowing_date='2027-10-01', proposed_date='2028-03-19').json()
        self.assertEqual(normal['elapsed_days'], 170)
        self.assertEqual(leap['elapsed_days'], 170)
        self.assertEqual(normal['status'], 'within')
        self.assertEqual(normal['sowing_date'], '2026-10-01')

    def test_harvest_without_documented_cycle_uses_window_only_and_insufficient_without_data(self):
        self.ref.duracion_ciclo_dias = None
        self.ref.save()
        result = self.evaluate(evaluation='harvest', crop_id=self.maize.pk, zone_id=self.zone.pk,
                               sowing_date='2026-10-01', proposed_date='2027-04-01').json()
        self.assertEqual(result['status'], 'within')
        self.assertIsNone(result['expected_cycle_days'])
        self.assertIn('no documenta la duración', result['explanation'])
        none = self.evaluate(evaluation='harvest', crop_id=self.wheat.pk, zone_id=self.zone.pk,
                             sowing_date='2026-05-01', proposed_date='2026-12-01').json()
        self.assertEqual(none['status'], 'insufficient')
        self.assertNotIn('100', none['explanation'])


class DecisionCenterIntegrationTests(IntegrationBase):
    def setUp(self):
        super().setUp()
        self.plot.cultivo = self.maize
        self.plot.save()
        self.seed_type = TipoInsumo.objects.create(nombre='Semilla')
        self.fert_type = TipoInsumo.objects.create(nombre='Fertilizante')
        verified = dict(estado_verificacion='verified', fuente_nombre='Fuente', fuente_url='https://example.org/f',
                        fecha_verificacion=_date(2026, 10, 1))
        self.seed = Insumo.objects.create(nombre='Semilla P', tipo=self.seed_type, cultivo=self.maize, dosis_hectarea=Decimal('22'),
            unidad_dosis='kg/ha', dosis_verificada=True, dosis_fuente='Ficha', presentacion_cantidad=Decimal('20'),
            presentacion_unidad='kg', variedad_semilla='V1', **verified)
        self.fert = Insumo.objects.create(nombre='Fert P', tipo=self.fert_type, cultivo=self.maize)
        self.wheat_fert = Insumo.objects.create(nombre='Fert trigo', tipo=self.fert_type, cultivo=self.wheat)

    def calc(self, **payload):
        return self.post_json('/calculos/ejecutar/', {'plot_id': self.plot.pk, 'crop': 'Maíz prueba', **payload})

    def test_seed_dose_marks_documented_source_and_packages(self):
        data = self.calc(operation='dose', calculation_type='semillas', area='3', dose='22', unit='kg/ha', product_id=self.seed.pk).json()
        self.assertEqual(data['amount'], 66)
        self.assertTrue(data['verified'])
        self.assertFalse(data['simulation'])
        self.assertEqual(data['package']['count'], 4)
        self.assertEqual(data['source'], 'Ficha')

    def test_modified_or_undocumented_dose_is_simulation(self):
        data = self.calc(operation='dose', calculation_type='semillas', area='3', dose='30', unit='kg/ha', product_id=self.seed.pk).json()
        self.assertTrue(data['simulation'])
        manual = self.calc(operation='dose', calculation_type='insumos', area='1', dose='100', unit='kg/ha', product_id=self.fert.pk).json()
        self.assertTrue(manual['simulation'])

    def test_category_and_crop_mismatches_are_rejected(self):
        self.assertEqual(self.calc(operation='dose', calculation_type='semillas', area='1', dose='5', unit='kg/ha', product_id=self.fert.pk).status_code, 400)
        self.assertEqual(self.calc(operation='dose', calculation_type='insumos', area='1', dose='5', unit='kg/ha', product_id=self.seed.pk).status_code, 400)
        self.assertEqual(self.calc(operation='dose', calculation_type='insumos', area='1', dose='5', unit='kg/ha', product_id=self.wheat_fert.pk).status_code, 400)
        self.fert.estado_verificacion = 'restricted'
        self.fert.save()
        self.assertEqual(self.calc(operation='dose', calculation_type='insumos', area='1', dose='5', unit='kg/ha', product_id=self.fert.pk).status_code, 400)

    def test_coverage_is_simulation_without_inventory(self):
        data = self.calc(operation='coverage', calculation_type='coverage', area='4', dose='22', unit='kg/ha', stock='44', product_id=self.seed.pk).json()
        self.assertEqual(data['coveredHa'], 2)
        self.assertEqual(data['missingQty'], 44)
        self.assertEqual(data['inventory'], 'simulation')

    def test_catalog_payload_stats_categories_and_varieties(self):
        response = self.client.get('/decisiones/')
        catalog = response.context['catalog']
        self.assertEqual(catalog['stats']['seeds'], 1)
        self.assertEqual(catalog['stats']['fertilizers'], 2)
        self.assertFalse(catalog['stats']['inventoryTracked'])
        self.assertEqual({item['category'] for item in catalog['insumos']}, {'seed', 'fertilizer'})
        self.assertEqual(catalog['varieties'][str(self.maize.pk)], ['V1'])
        for tool in ('data-tool="llevar"', 'data-tool="alcanza"', 'data-tool="cosecha"', 'data-tool="ficha"', 'Cálculo avanzado'):
            self.assertContains(response, tool)

    def test_empty_catalog_is_reported_without_fake_options(self):
        Insumo.objects.all().delete()
        response = self.client.get('/decisiones/')
        self.assertContains(response, 'El catálogo no tiene insumos registrados')
        self.assertNotContains(response, '<option value="1">')


class CatalogImportCommandTests(TestCase):
    def write(self, data):
        import tempfile
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(data, handle)
        handle.close()
        return handle.name

    def test_dry_run_then_apply(self):
        path = self.write({'zonas': [{'nombre': 'Zona import'}], 'cultivos': [{'nombre': 'Cultivo import'}]})
        call_command('importar_catalogo', path, verbosity=0, stdout=open(os.devnull, 'w'))
        self.assertFalse(Cultivo.objects.filter(nombre='Cultivo import').exists())
        call_command('importar_catalogo', path, '--aplicar', stdout=open(os.devnull, 'w'))
        self.assertTrue(Cultivo.objects.filter(nombre='Cultivo import').exists())

    def test_verified_reference_without_source_rolls_back_everything(self):
        from django.core.management.base import CommandError
        path = self.write({
            'zonas': [{'nombre': 'Z'}], 'cultivos': [{'nombre': 'C'}],
            'referencias': [{'cultivo': 'C', 'zona': 'Z', 'estado': 'verified'}],
        })
        with self.assertRaises(CommandError):
            call_command('importar_catalogo', path, '--aplicar', stdout=open(os.devnull, 'w'))
        self.assertFalse(Zona.objects.filter(nombre='Z').exists())

    def test_template_has_no_agronomic_values(self):
        import tempfile
        path = tempfile.mktemp(suffix='.json')
        call_command('importar_catalogo', '--plantilla', path, stdout=open(os.devnull, 'w'))
        data = json.load(open(path, encoding='utf-8'))
        self.assertIsNone(data['cultivos'][0]['densidad_siembra'])
        self.assertIsNone(data['insumos'][0]['dosis_hectarea'])


class ProfessionalModulesTests(IntegrationBase):
    def setUp(self):
        super().setUp()
        self.plot.cultivo = self.maize
        self.plot.fecha_siembra = _date(2026, 10, 1)
        self.plot.fecha_cosecha = _date(2026, 10, 20)
        self.plot.save()
        self.insect_type = TipoInsumo.objects.create(nombre='Insecticida')
        self.fert_type = TipoInsumo.objects.create(nombre='Fertilizante')
        self.insecticide = Insumo.objects.create(
            nombre='Insecticida X', tipo=self.insect_type, cultivo=self.maize, periodo_carencia='21 días',
            dosis_hectarea=Decimal('0.5'), unidad_dosis='L/ha',
        )
        self.fert = Insumo.objects.create(nombre='Fert trigo', tipo=self.fert_type, cultivo=self.wheat)

    def activity(self, **values):
        data = {'nombre': 'Aplicación', 'tipo': 'control_fitosanitario', 'potrero': self.plot.pk,
                'fecha_programada': '2026-10-05', 'estado': 'pendiente', 'prioridad': 'alta'}
        data.update(values)
        return self.client.post('/actividades/nueva/', data)

    def test_field_log_record_with_product_dose_total_and_withholding_alert(self):
        response = self.activity(insumo=self.insecticide.pk, dosis='0.5', unidad_dosis='L/ha', superficie_ha='2',
                                 estado='completada', fecha_realizada='2026-10-05', responsable='Juan')
        self.assertEqual(response.status_code, 302, response.content.decode()[:3000])
        item = ActividadAgricola.objects.get()
        self.assertEqual(item.cantidad_total, Decimal('1.000'))
        self.assertEqual(item.fecha_fin_carencia, _date(2026, 10, 26))
        self.assertTrue(item.conflicto_carencia)
        detail = self.client.get(f'/actividades/{item.pk}/')
        self.assertContains(detail, 'anterior al fin del período de carencia')

    def test_activity_validations(self):
        self.assertEqual(self.activity(estado='completada').status_code, 200)  # sin fecha ni producto
        self.assertEqual(self.activity(insumo=self.fert.pk, tipo='fertilizacion').status_code, 200)  # otro cultivo
        self.assertEqual(self.activity(superficie_ha='99', tipo='riego').status_code, 200)
        self.assertEqual(self.activity(dosis='2', tipo='fertilizacion').status_code, 200)  # dosis sin unidad
        self.assertEqual(ActividadAgricola.objects.count(), 0)
        self.assertEqual(self.activity(tipo='riego', dosis='5', unidad_dosis='kg/ha').status_code, 302)
        self.assertIsNone(ActividadAgricola.objects.get().dosis)

    def test_list_filters_calendar_and_prefill(self):
        self.activity(tipo='riego', nombre='Riego norte')
        response = self.client.get('/actividades/?vista=calendario&mes=2026-10')
        self.assertContains(response, 'Riego norte')
        self.assertEqual(response.context['activity_stats']['pendientes'], 1)
        self.assertEqual(list(self.client.get('/actividades/?tipo=siembra').context['activities']), [])
        form = self.client.get(f'/actividades/nueva/?potrero={self.plot.pk}&tipo=control_fitosanitario&insumo={self.insecticide.pk}&dosis=0.5&unidad=L/ha')
        self.assertEqual(form.context['form'].initial['insumo'], self.insecticide.pk)
        self.assertEqual(form.context['form'].initial['unidad_dosis'], 'L/ha')

    def test_season_plan_uses_registered_dates_without_duplicates(self):
        payload = {'potrero': self.plot.pk, 'incluir_preparacion': '1', 'dias_preparacion': '10',
                   'incluir_siembra': '1', 'incluir_monitoreo': '1', 'frecuencia_monitoreo': '7', 'incluir_cosecha': '1'}
        self.client.post('/actividades/plan/', payload)
        types = sorted(ActividadAgricola.objects.values_list('tipo', flat=True))
        self.assertEqual(types, ['cosecha', 'monitoreo', 'monitoreo', 'preparacion', 'siembra'])
        self.assertEqual(ActividadAgricola.objects.get(tipo='preparacion').fecha_programada, _date(2026, 9, 21))
        self.client.post('/actividades/plan/', payload)
        self.assertEqual(ActividadAgricola.objects.count(), 5)
        self.assertEqual(self.client.post('/actividades/plan/', {**payload, 'potrero': self.other_plot.pk}).status_code, 404)

    def test_product_catalog_filters_and_sheet(self):
        names = lambda url: [item.nombre for item in self.client.get(url).context['products_page']]
        self.assertEqual(names('/productos/?categoria=insecticide'), ['Insecticida X'])
        self.assertEqual(names('/productos/?q=trigo'), ['Fert trigo'])
        self.assertEqual(names(f'/productos/?cultivo={self.maize.pk}'), ['Insecticida X'])
        self.assertEqual(self.client.get('/productos/?solo_calculables=1').context['product_count'], 0)
        sheet = self.client.get(f'/productos/{self.insecticide.pk}/')
        self.assertContains(sheet, 'número de autorización SAG')
        self.assertContains(sheet, '21 días')
        self.assertNotContains(sheet, 'Calcular cantidad</a>')

    def test_reports_types_csv_and_isolation(self):
        self.activity(insumo=self.insecticide.pk, dosis='0.5', unidad_dosis='L/ha', superficie_ha='2',
                      estado='completada', fecha_realizada='2026-10-05', responsable='Juan')
        ActividadAgricola.objects.create(usuario=self.other, potrero=self.other_plot, nombre='Ajena', tipo='riego',
                                         fecha_programada=_date(2026, 10, 1), estado='completada', fecha_realizada=_date(2026, 10, 1))
        for kind in ('resumen', 'cuaderno', 'cultivos', 'calculos'):
            with self.subTest(kind=kind):
                response = self.client.get(f'/reportes/?tipo={kind}')
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'Ajena')
                self.assertNotContains(response, 'Lote ajeno')
        log = self.client.get('/reportes/?tipo=cuaderno')
        self.assertContains(log, 'Insecticida X')
        self.assertEqual(len(log.context['field_log']), 1)
        csv_response = self.client.get('/reportes/?tipo=cuaderno&formato=csv')
        self.assertEqual(csv_response['Content-Type'], 'text/csv; charset=utf-8')
        content = csv_response.content.decode('utf-8-sig')
        self.assertIn('Insecticida X', content)
        self.assertIn('26/10/2026', content)
        self.assertNotIn('Ajena', content)
