"""Calculadora de semillas: página, menú nuevo y cálculo de sacos/costo hecho por el servidor."""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import CalculoAgricola, Cultivo, Potrero, Predio
from ..agronomy import referencias_siembra


class CalculadoraSemillasTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('semilla', 'semilla@example.com', 'Clave-segura-123')
        self.otro = User.objects.create_user('otro', 'otro@example.com', 'Clave-segura-123')
        self.cultivo = Cultivo.objects.create(nombre='Trigo', densidad_siembra=Decimal('180'), unidad_siembra='kg')
        self.predio = Predio.objects.create(propietario=self.user, nombre='El Roble', ubicacion='Maule', superficie_ha='12')
        self.potrero = Potrero.objects.create(predio=self.predio, nombre='Norte', superficie_ha='1.5', cultivo=self.cultivo, perimetro=[])
        predio_ajeno = Predio.objects.create(propietario=self.otro, nombre='Ajeno', ubicacion='X', superficie_ha='5')
        self.potrero_ajeno = Potrero.objects.create(predio=predio_ajeno, nombre='Ajeno', superficie_ha='2', perimetro=[])
        self.client.force_login(self.user)

    def calcular(self, **extra):
        cuerpo = {'operation': 'dose', 'calculation_type': 'semillas', 'plot_id': self.potrero.pk, 'area': '1.5',
                  'crop': 'Trigo', 'dose': '180', 'unit': 'kg/ha', **extra}
        return self.client.post(reverse('calculate'), json.dumps(cuerpo), content_type='application/json')

    # ---- página y menú ----
    def test_pagina_y_menu(self):
        r = self.client.get('/calculadoras/semillas/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Calculadora de semillas')
        self.assertContains(r, 'id="cs-plot"')
        menu = r.content.decode().split('aria-label="Principal"', 1)[1].split('</nav>', 1)[0]
        for etiqueta in ('Inicio', 'Mis predios', 'Mapa', 'Catálogo agrícola', 'Calculadoras', 'Semillas',
                         'Fertilizantes', 'Actividades', 'Toma de decisiones', 'Reportes', 'Calendario'):
            self.assertIn(f'<span>{etiqueta}</span>', menu)
        self.assertIn('href="/calculadoras/semillas/"', menu)
        self.assertIn('nav-sublink is-active', menu)
        self.assertIn('<details class="nav-group" open>', menu)

    def test_menu_no_tiene_enlaces_muertos(self):
        r = self.client.get('/')
        menu = r.content.decode().split('aria-label="Principal"', 1)[1].split('</nav>', 1)[0]
        import re
        for href in re.findall(r'href="([^"#]+)', menu):
            destino = self.client.get(href.replace('&amp;', '&'))
            self.assertIn(destino.status_code, (200, 302), href)
        for pendiente in ('Riego', 'Inventario', 'Fitosanitarios', 'Conversión'):
            self.assertNotIn(pendiente, menu)  # no se muestran herramientas que aún no existen

    def test_administracion_solo_para_admin(self):
        self.assertNotContains(self.client.get('/'), '<span>Administración</span>')
        self.user.is_staff = True
        self.user.save()
        self.assertContains(self.client.get('/'), '<span>Administración</span>')

    def test_sin_sesion_redirige_al_login(self):
        self.client.logout()
        r = self.client.get('/calculadoras/semillas/')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].startswith('/login/'))

    def test_datos_de_la_pagina_traen_referencia_inia_con_estado(self):
        r = self.client.get('/calculadoras/semillas/')
        trigo = next(c for c in r.context['semillas_data']['crops'] if c['name'] == 'Trigo')
        if not referencias_siembra('Trigo'):
            self.skipTest('PyYAML o el catálogo no están disponibles en este entorno')
        ref = trigo['references'][0]
        self.assertEqual((ref['min'], ref['max']), (160.0, 200.0))
        self.assertEqual(ref['estado'], 'citada_sin_cotejar')
        self.assertTrue(ref['fuente']['url'].startswith('https://'))

    def test_arroz_aparece_cotejado(self):
        if not referencias_siembra('Arroz'):
            self.skipTest('PyYAML o el catálogo no están disponibles en este entorno')
        self.assertEqual(referencias_siembra('arroz')[0]['estado'], 'cotejada_con_fuente')
        self.assertEqual(referencias_siembra('ARROZ')[0]['fecha_consulta'], '2026-10-28')

    # ---- cálculo ----
    def test_sacos_sobrante_y_costo(self):
        r = self.calcular(bag_kg='25', bag_price_clp='20000', preview=True)
        self.assertEqual(r.status_code, 200)
        cuerpo = r.json()
        self.assertEqual(cuerpo['amount'], 270.0)
        self.assertEqual(cuerpo['user_bag']['count'], 11)
        self.assertEqual(cuerpo['user_bag']['leftover'], 5.0)
        self.assertEqual(cuerpo['user_bag']['total_cost_clp'], 220000.0)
        self.assertEqual(cuerpo['user_bag']['source'], 'ingresado por la persona')

    def test_sin_saco_no_inventa_sacos_ni_costo(self):
        cuerpo = self.calcular(preview=True).json()
        self.assertNotIn('user_bag', cuerpo)
        self.assertNotIn('package', cuerpo)

    def test_precio_sin_saco_no_calcula_costo(self):
        self.assertNotIn('user_bag', self.calcular(bag_price_clp='20000', preview=True).json())

    def test_vista_previa_no_guarda_y_guardar_si(self):
        self.calcular(bag_kg='25', preview=True)
        self.assertEqual(CalculoAgricola.objects.count(), 0)
        r = self.calcular(bag_kg='25', bag_price_clp='20000')
        self.assertEqual(r.status_code, 200)
        guardado = CalculoAgricola.objects.get()
        self.assertEqual(guardado.usuario, self.user)
        self.assertEqual(guardado.entrada['bag_kg'], '25')
        self.assertEqual(guardado.resultado['user_bag']['count'], 11)

    def test_validaciones_del_saco(self):
        for malo in ('0', '-5', 'abc', '1001'):
            self.assertEqual(self.calcular(bag_kg=malo, preview=True).status_code, 400, malo)
        self.assertEqual(self.calcular(bag_kg='25', bag_price_clp='-1', preview=True).status_code, 400)

    def test_saco_solo_con_dosis_en_kg(self):
        r = self.calcular(bag_kg='25', unit='g/ha', preview=True)
        self.assertEqual(r.status_code, 400)

    def test_dosis_igual_a_la_del_cultivo_sin_fuente_es_catalogo_no_documentada(self):
        cuerpo = self.calcular(preview=True).json()
        self.assertEqual(cuerpo['origin'], 'catalog')  # no tiene fuente verificada: nunca «documentada»
        self.assertTrue(cuerpo['simulation'])

    def test_potrero_ajeno_rechazado(self):
        r = self.calcular(plot_id=self.potrero_ajeno.pk, area='1', preview=True)
        self.assertEqual(r.status_code, 400)

    def test_superficie_mayor_a_la_del_potrero_rechazada(self):
        self.assertEqual(self.calcular(area='99', preview=True).status_code, 400)
