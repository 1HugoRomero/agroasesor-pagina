"""Borrar cookies / sesión vencida: la página responde con avisos claros, no con errores ni botones muertos."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class SesionVencidaTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user('sesion', 'sesion@example.com', 'Clave-segura-123')

    def test_login_con_cookies_borradas_vuelve_al_login_con_aviso(self):
        c = Client(enforce_csrf_checks=True)
        r = c.post('/login/', {'username': 'sesion', 'password': 'Clave-segura-123'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/login/')
        pagina = c.get('/login/')
        self.assertContains(pagina, 'se borraron las cookies')

    def test_logout_sin_token_con_sesion_vuelve_a_la_pagina_anterior(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.usuario)
        r = c.post('/logout/', HTTP_REFERER='http://testserver/predios/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], 'http://testserver/predios/')

    def test_referer_de_otro_sitio_no_se_usa(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.usuario)
        r = c.post('/logout/', HTTP_REFERER='https://sitio-malo.example/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/')

    def test_llamada_json_sin_token_responde_json(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.usuario)
        r = c.post('/calculos/ejecutar/', '{}', content_type='application/json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['codigo'], 'sesion_vencida')
        self.assertEqual(r.json()['login_url'], '/login/')

    def test_llamada_ajax_sin_sesion_responde_401_json(self):
        r = Client().get('/predios/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['codigo'], 'sesion_vencida')

    def test_json_sin_sesion_tambien(self):
        r = Client().post('/calculos/ejecutar/', '{}', content_type='application/json')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['codigo'], 'sesion_vencida')

    def test_navegacion_normal_sin_sesion_sigue_redirigiendo_al_login(self):
        r = Client().get('/predios/')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].startswith('/login/'))
