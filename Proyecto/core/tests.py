import json
import re
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings, Client
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .forms import RegistroForm
from .geometry import polygon_area, polygon_perimeter
from .models import ActividadAgricola, Agricultor, Cultivo, Insumo, Predio, PredioHistorial, Potrero, TipoInsumo, Zona

User = get_user_model()
PASSWORD = 'Campo-Seguro-2026!'
POLYGON = [[-71.215,-33.686],[-71.214,-33.686],[-71.214,-33.685],[-71.215,-33.685]]


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('farmer@example.com', email='farmer@example.com', password=PASSWORD)

    def registration_data(self, **values):
        return {'mode':'register', 'name':'María Soto', 'email':'maria@example.com', 'rut':'12.345.678-5',
                'phone':'+56 9 1234 5678', 'comuna':'Melipilla', 'password':PASSWORD, 'password2':PASSWORD, **values}

    def test_registration_persists_hashed_password_and_profile(self):
        response = self.client.post('/login/', self.registration_data())
        self.assertRedirects(response, '/')
        user = User.objects.get(email='maria@example.com')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertEqual(user.agricultor.rut, '12345678-5')
        self.assertFalse(user.is_staff)
        another = Client()
        self.assertRedirects(another.post('/login/', {'email':user.email,'password':PASSWORD}), '/')

    def test_registration_rejects_bad_rut_phone_and_weak_password(self):
        for data in [self.registration_data(rut='12.345.678-9'), self.registration_data(phone='abc'),
                     self.registration_data(password='123456',password2='123456'), self.registration_data(comuna='Inventada'),
                     self.registration_data(password2='diferente')]:
            self.assertEqual(self.client.post('/login/', data).status_code, 200)
        self.assertFalse(User.objects.filter(email='maria@example.com').exists())

    def test_registration_duplicate_email(self):
        self.assertEqual(self.client.post('/login/', self.registration_data(email='FARMER@example.com')).status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    def test_login_logout_and_invalid_credentials(self):
        self.assertEqual(self.client.get('/').status_code, 302)
        self.assertContains(self.client.post('/login/', {'email':self.user.email,'password':'wrong'}), 'incorrectos')
        self.assertRedirects(self.client.post('/login/', {'email':'FARMER@example.com','password':PASSWORD}), '/')
        self.assertEqual(self.client.get('/logout/').status_code, 405)
        self.assertRedirects(self.client.post('/logout/'), '/login/')
        self.assertEqual(self.client.get('/predios/').status_code, 302)

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
            f'/predios/{self.predio.pk}/editar/', '/decisiones/', '/calculadora/',
            '/cobertura/', '/asesor/', '/calendario/', '/actividades/nueva/',
            '/predictor/', '/reportes/', '/busqueda/',
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
                    '/decisiones/', '/calculadora/?modo=insumos', '/asesor/',
                    '/reportes/',
                ):
                    self.assertIn(f'href="{href}"', quick_links)

    def test_decision_center_keeps_existing_tools_and_single_sidebar_link(self):
        response = self.client.get('/decisiones/')
        self.assertContains(response, 'Centro de decisiones')
        self.assertContains(response, 'Calcula, planifica y optimiza los recursos de tu terreno')
        self.assertContains(response, 'Semillas')
        self.assertContains(response, 'Disponibilidad')
        self.assertContains(response, 'Cosecha')
        self.assertContains(response, '/calculadora/?modo=insumos')
        self.assertContains(response, '/asesor/')
        decision_group = next(items for label, items in response.context['nav_groups'] if label == 'La decisión')
        self.assertEqual([(name, title) for name, title, _icon in decision_group], [('decisiones', 'Centro de decisiones')])

    def test_calculators_render_three_progressive_steps_and_validated_inputs(self):
        for url in ['/calculadora/','/cobertura/','/predictor/']:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.content.decode().count('data-progress-step='), 3)
                self.assertContains(response, 'data-step-panel="1"')
                self.assertContains(response, 'data-step-panel="2"')
                self.assertContains(response, 'data-step-panel="3"')
                self.assertContains(response, 'min="0.01"')

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
        response=self.client.get('/calculadora/')
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
        response=self.client.get('/calculadora/')
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
        response = self.calculate(operation='yield', plot_id=self.plot.pk, crop=self.crop.nombre, area='2.5', rate='6')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['production'], 15)
        self.assertEqual(
            self.calculate(operation='yield', plot_id=self.plot.pk, crop=self.crop.nombre, area='-1', rate='6').status_code,
            400,
        )

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
        self.assertRedirects(response, '/calendario/')
        activity = ActividadAgricola.objects.get()
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
        self.assertRedirects(response, '/calendario/')
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
