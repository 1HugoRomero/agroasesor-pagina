"""Pruebas de las herramientas de la base de datos única (estado, respaldo y consolidación)."""
import sqlite3
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from core import dbutils
from core.models import Agricultor, Predio


def _crear_origen(carpeta):
    """Crea un SQLite «de otra persona» con la misma estructura que la base actual."""
    ruta = Path(carpeta) / 'otra.sqlite3'
    con = sqlite3.connect(str(ruta))
    with connection.cursor() as cur:
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name IN ('auth_user','core_predio')")
        for (ddl,) in cur.fetchall():
            con.execute(ddl)
    con.execute(
        "INSERT INTO auth_user (id,password,is_superuser,username,last_name,email,is_staff,is_active,date_joined,first_name) "
        "VALUES (1,'x',0,'ana','','ana@correo.cl',0,1,'2026-01-01 00:00:00','')"
    )
    con.execute(
        "INSERT INTO auth_user (id,password,is_superuser,username,last_name,email,is_staff,is_active,date_joined,first_name) "
        "VALUES (2,'y',0,'luis','','luis@correo.cl',0,1,'2026-01-02 00:00:00','')"
    )
    for pid, nombre, dueno in ((1, 'Fundo Ana', 1), (2, 'Campo de Luis', 2)):
        con.execute(
            "INSERT INTO core_predio (id,nombre,ubicacion,superficie_ha,creado,propietario_id,actualizado,descripcion,observaciones) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (pid, nombre, 'Melipilla', 10, '2026-01-01 00:00:00', dueno, '2026-01-01 00:00:00', '', ''),
        )
    con.commit()
    con.close()
    return ruta


class ConsolidarBdTests(TestCase):
    def setUp(self):
        self.ana = get_user_model().objects.create_user('ana', 'ana@correo.cl', 'clave-segura-1')
        Predio.objects.create(nombre='Fundo Ana', ubicacion='Melipilla', superficie_ha=10, propietario=self.ana)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.origen = _crear_origen(self.tmp.name)

    def _correr(self, *extra):
        salida = StringIO()
        call_command('consolidar_bd', str(self.origen), *extra, stdout=salida)
        return salida.getvalue()

    def test_modo_prueba_no_guarda_nada(self):
        informe = self._correr()
        self.assertIn('MODO PRUEBA', informe)
        self.assertIn('luis', informe)
        self.assertFalse(get_user_model().objects.filter(username='luis').exists())
        self.assertEqual(Predio.objects.count(), 1)

    def test_aplicar_trae_lo_que_falta_sin_duplicar_ni_tocar_lo_existente(self):
        self._correr('--aplicar')
        luis = get_user_model().objects.get(username='luis')
        self.assertTrue(Predio.objects.filter(nombre='Campo de Luis', propietario=luis).exists())
        self.assertEqual(Predio.objects.filter(nombre='Fundo Ana').count(), 1)
        self.assertTrue(get_user_model().objects.get(username='ana').check_password('clave-segura-1'))
        self._correr('--aplicar')  # repetir es seguro
        self.assertEqual(Predio.objects.count(), 2)
        self.assertEqual(get_user_model().objects.count(), 2)

    def test_excluir_usuarios_deja_fuera_al_usuario_y_sus_datos(self):
        self._correr('--aplicar', '--excluir-usuarios', 'luis')
        self.assertFalse(get_user_model().objects.filter(username='luis').exists())
        self.assertFalse(Predio.objects.filter(nombre='Campo de Luis').exists())

    def test_la_contrasena_del_usuario_traido_se_conserva(self):
        self._correr('--aplicar')
        self.assertEqual(get_user_model().objects.get(username='luis').password, 'y')

    def test_mismo_usuario_con_otro_correo_se_conserva_separado_y_no_se_duplica_al_repetir(self):
        get_user_model().objects.filter(username='ana').update(email='otra.ana@correo.cl')
        informe = self._correr('--aplicar')
        self.assertIn('CONFLICTO', informe)
        self.assertEqual(get_user_model().objects.get(username='ana').email, 'otra.ana@correo.cl')
        separada = get_user_model().objects.get(username='ana_2')
        self.assertEqual(separada.email, 'ana@correo.cl')
        self.assertEqual(Predio.objects.filter(propietario=separada, nombre='Fundo Ana').count(), 1)
        self.assertEqual(Predio.objects.filter(propietario__username='ana', nombre='Fundo Ana').count(), 1)
        self._correr('--aplicar')
        self.assertFalse(get_user_model().objects.filter(username='ana_3').exists())
        self.assertEqual(get_user_model().objects.count(), 3)
        self.assertEqual(Predio.objects.count(), 3)

    def test_cuentas_con_distinto_usuario_y_mismo_correo_nunca_se_unen(self):
        get_user_model().objects.create_user('luis_otro', 'luis@correo.cl', 'clave-segura-1')
        self._correr('--aplicar')
        self.assertEqual(get_user_model().objects.filter(email='luis@correo.cl').count(), 2)

    def test_equivalencias_mal_escritas_se_rechazan(self):
        with self.assertRaises(Exception):
            self._correr('--equivalencias', 'mal escrito')

    def test_equivalencias_ignoran_tildes_y_mayusculas(self):
        from core.models import Cultivo, Potrero
        from core.management.commands.consolidar_bd import _plano
        self.assertEqual(_plano('Maíz'), _plano('MAIZ'))
        real = Cultivo.objects.create(nombre='Maíz')
        con = sqlite3.connect(str(self.origen))
        with connection.cursor() as cur:
            cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name IN ('core_cultivo','core_potrero')")
            for (ddl,) in cur.fetchall():
                con.execute(ddl)
        def insertar(tabla, **dados):
            info = list(con.execute(f'PRAGMA table_info({tabla})'))
            fila = {f[1]: ('' if f[3] else None) for f in info}
            fila.update(dados)
            con.execute(
                f"INSERT INTO {tabla} ({','.join(fila)}) VALUES ({','.join('?' * len(fila))})", list(fila.values())
            )
        insertar('core_cultivo', id=1, nombre='MAIZ DEMO', unidad_siembra='kg', activo=1)
        insertar('core_potrero', perimetro='{}', id=1, nombre='Lote Maiz', superficie_ha=2, predio_id=2, cultivo_id=1,
                 creado='2026-01-01 00:00:00', actualizado='2026-01-01 00:00:00')
        con.commit()
        con.close()
        self._correr('--aplicar', '--equivalencias', 'MAIZ DEMO=maiz')
        self.assertEqual(Potrero.objects.get(nombre='Lote Maiz').cultivo, real)
        self.assertFalse(Cultivo.objects.filter(nombre__icontains='DEMO').exists())

    def test_comprobar_y_verificar_tras_consolidar(self):
        self._correr('--aplicar')
        salida = StringIO()
        call_command('comprobar_consolidacion', str(self.origen), stdout=salida)
        self.assertIn('No se perdió nada', salida.getvalue())
        salida = StringIO()
        call_command('verificar_bd', stdout=salida)
        self.assertIn('Verificación correcta', salida.getvalue())

    def test_comprobar_detecta_lo_que_falta(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('comprobar_consolidacion', str(self.origen), stdout=StringIO())


class EstadoYRespaldoTests(TestCase):
    def test_estado_bd_informa_conteos(self):
        salida = StringIO()
        call_command('estado_bd', stdout=salida)
        texto = salida.getvalue()
        self.assertIn('BASE DE DATOS EN USO', texto)
        self.assertIn('Usuarios', texto)

    def test_ruta_oficial_solo_es_la_de_docker(self):
        self.assertFalse(dbutils.es_base_oficial())

    def test_respaldo_crea_copia_y_poda(self):
        with tempfile.TemporaryDirectory() as carpeta:
            base = Path(carpeta) / 'viva.sqlite3'
            con = sqlite3.connect(str(base))
            con.execute('CREATE TABLE t(x)')
            con.execute('INSERT INTO t VALUES (1)')
            con.commit()
            con.close()
            from unittest import mock
            with mock.patch.object(dbutils, 'ruta_bd', return_value=base):
                primero = dbutils.respaldar(directorio=Path(carpeta) / 'bk', mantener=1)
                self.assertTrue(primero.exists())
                self.assertEqual(sqlite3.connect(str(primero)).execute('SELECT x FROM t').fetchone()[0], 1)


class CicloDeCuentaTests(TestCase):
    """Registrarse, salir, volver más tarde y entrar directo al panel (por usuario o por correo)."""

    DATOS = {
        'mode': 'register', 'nombre_completo': 'Rosa Campo', 'email': 'Rosa@Correo.cl',
        'telefono': '+56 9 1111 2222', 'comuna': 'Melipilla', 'rut': '',
        'password1': 'Cultivo-Seguro-2026', 'password2': 'Cultivo-Seguro-2026',
        'acepta_politicas': 'on',
    }

    def test_registro_salida_y_regreso_con_el_correo(self):
        r = self.client.post('/login/', self.DATOS)
        self.assertRedirects(r, '/', fetch_redirect_response=False)
        self.client.post('/logout/')
        for identificador in ('rosa@correo.cl', 'ROSA@CORREO.CL', 'Rosa@Correo.cl'):
            with self.subTest(identificador=identificador):
                r = self.client.post('/login/', {'mode': 'login', 'username': identificador, 'password': 'Cultivo-Seguro-2026'})
                self.assertRedirects(r, '/', fetch_redirect_response=False)
                self.assertEqual(self.client.get('/').status_code, 200)  # entra directo al panel
                self.client.post('/logout/')

    def test_contrasena_incorrecta_no_entra(self):
        self.client.post('/login/', self.DATOS)
        self.client.post('/logout/')
        r = self.client.post('/login/', {'mode': 'login', 'username': 'rosa@correo.cl', 'password': 'otra-clave-123'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'incorrectos')

    def test_correo_compartido_por_cuentas_antiguas_no_bloquea_el_acceso(self):
        U = get_user_model()
        U.objects.create_user('vieja_a', email='mismo@correo.cl', password='clave-de-a-2026')
        U.objects.create_user('vieja_b', email='mismo@correo.cl', password='clave-de-b-2026')
        for clave, usuario in (('clave-de-a-2026', 'vieja_a'), ('clave-de-b-2026', 'vieja_b')):
            with self.subTest(usuario=usuario):
                r = self.client.post('/login/', {'mode': 'login', 'username': 'mismo@correo.cl', 'password': clave})
                self.assertRedirects(r, '/', fetch_redirect_response=False)
                self.assertEqual(int(self.client.session['_auth_user_id']), U.objects.get(username=usuario).pk)
                self.client.post('/logout/')
        r = self.client.post('/login/', {'mode': 'login', 'username': 'mismo@correo.cl', 'password': 'mala-clave'})
        self.assertContains(r, 'incorrectos')

    def test_cuenta_desactivada_no_entra(self):
        get_user_model().objects.create_user('baja', email='baja@correo.cl', password='clave-baja-2026', is_active=False)
        r = self.client.post('/login/', {'mode': 'login', 'username': 'baja', 'password': 'clave-baja-2026'})
        self.assertContains(r, 'incorrectos')


class RegistroAgricultorTests(TestCase):
    """RF-01: nombre completo, correo, contraseña, teléfono, comuna y RUT opcional (validado)."""

    CLAVE = 'Campo-Seguro-2026!'

    def datos(self, **extra):
        base = {
            'mode': 'register', 'nombre_completo': 'Ana María Pérez Soto', 'email': 'ana@correo.cl',
            'telefono': '9 8765 4321', 'comuna': 'san josé de maipo', 'rut': '',
            'password1': self.CLAVE, 'password2': self.CLAVE, 'acepta_politicas': 'on',
        }
        base.update(extra)
        return base

    def test_registro_guarda_la_ficha_completa_y_nunca_crea_administradores(self):
        r = self.client.post('/login/', self.datos(is_staff='on', is_superuser='on', rut='12.345.678-5'))
        self.assertRedirects(r, '/', fetch_redirect_response=False)
        usuario = get_user_model().objects.get(email='ana@correo.cl')
        self.assertFalse(usuario.is_staff or usuario.is_superuser)
        self.assertEqual((usuario.first_name, usuario.last_name), ('Ana María', 'Pérez Soto'))
        ficha = usuario.agricultor
        self.assertEqual(ficha.nombre, 'Ana María Pérez Soto')
        self.assertEqual(ficha.telefono, '+56987654321')
        self.assertEqual(ficha.comuna, 'San José de Maipo')
        self.assertEqual(ficha.rut, '12345678-5')

    def test_rut_es_opcional_y_varias_cuentas_pueden_no_tenerlo(self):
        self.client.post('/login/', self.datos())
        self.client.post('/logout/')
        self.client.post('/login/', self.datos(email='otra@correo.cl', nombre_completo='Luis Rojas'))
        self.assertEqual(Agricultor.objects.filter(rut__isnull=True).count(), 2)

    def test_campos_obligatorios_y_caracteres_invalidos(self):
        casos = {
            'nombre_completo': ['', 'Madonna', 'Ana 123 Pérez', 'Ana <b>Pérez</b>'],
            'telefono': ['', '12345', 'abc', '+1 555 123 4567', '+56 9 1234 56789'],
            'comuna': ['', 'Mel1pilla', '<script>'],
            'rut': ['12.345.678-9', '1234', 'abcdefgh-k', '12345678-5; DROP'],
        }
        for campo, valores in casos.items():
            for valor in valores:
                with self.subTest(campo=campo, valor=valor):
                    r = self.client.post('/login/', self.datos(**{campo: valor}))
                    self.assertEqual(r.status_code, 200)
                    self.assertFalse(get_user_model().objects.filter(email='ana@correo.cl').exists())

    def test_rut_repetido_es_rechazado(self):
        self.client.post('/login/', self.datos(rut='12.345.678-5'))
        self.client.post('/logout/')
        r = self.client.post('/login/', self.datos(email='otra@correo.cl', rut='12345678-5'))
        self.assertContains(r, 'Este RUT ya está registrado')

    def test_validadores_de_rut_y_telefono(self):
        from django.core.exceptions import ValidationError
        from core.validators import normalizar_rut, normalizar_telefono
        self.assertEqual(normalizar_rut('76.086.428-5'), '76086428-5')
        self.assertEqual(normalizar_rut('11.111.111-1'), '11111111-1')
        self.assertIsNone(normalizar_rut(''))
        for malo in ('11.111.111-2', '12345678', 'hola'):
            with self.assertRaises(ValidationError):
                normalizar_rut(malo)
        for bueno in ('+56 9 1234 5678', '912345678', '56912345678', '(22) 123 4567', '09 1234 5678'):
            self.assertRegex(normalizar_telefono(bueno), r'^\+56\d{9}$')

    def test_cuenta_antigua_sin_ficha_ve_aviso_y_puede_completar_su_perfil(self):
        antigua = get_user_model().objects.create_user('vieja@correo.cl', email='vieja@correo.cl', password=self.CLAVE)
        self.client.force_login(antigua)
        self.assertContains(self.client.get('/'), 'Completa tu perfil')
        r = self.client.post('/cuenta/perfil/', {
            'nombre_completo': 'Rosa Vieja', 'telefono': '+56 2 2123 4567', 'comuna': 'Melipilla', 'rut': '',
        })
        self.assertRedirects(r, '/cuenta/perfil/', fetch_redirect_response=False)
        self.assertEqual(antigua.agricultor.telefono, '+56221234567')
        self.assertNotContains(self.client.get('/'), 'Completa tu perfil')

    def test_perfil_exige_sesion_y_no_deja_usar_el_rut_de_otro(self):
        self.assertEqual(self.client.get('/cuenta/perfil/').status_code, 302)
        self.client.post('/login/', self.datos(rut='11.111.111-1'))
        self.client.post('/logout/')
        otra = get_user_model().objects.create_user('b@correo.cl', email='b@correo.cl', password=self.CLAVE)
        self.client.force_login(otra)
        r = self.client.post('/cuenta/perfil/', {'nombre_completo': 'Beto Pérez', 'telefono': '912345678', 'comuna': 'Melipilla', 'rut': '11111111-1'})
        self.assertContains(r, 'ya está registrado en otra cuenta')


class UnicaBaseConfiguradaTests(TestCase):
    """Django y Docker apuntan siempre a /data/db.sqlite3 (volumen persistente) y no hay otra base."""

    def _leer(self, nombre):
        from django.conf import settings
        return (Path(settings.BASE_DIR) / nombre).read_text(encoding='utf-8')

    def test_django_tiene_una_sola_base_y_sin_enrutadores(self):
        from django.conf import settings
        self.assertEqual(list(settings.DATABASES), ['default'])
        self.assertEqual(getattr(settings, 'DATABASE_ROUTERS', []), [])

    def test_docker_y_django_usan_la_misma_ruta_oficial(self):
        compose, dockerfile = self._leer('docker-compose.yml'), self._leer('Dockerfile')
        self.assertIn('DJANGO_DB_PATH: /data/db.sqlite3', compose)
        self.assertIn('DJANGO_DB_PATH=/data/db.sqlite3', dockerfile)
        self.assertIn('agroasesor_data:/data', compose)
        self.assertEqual(dbutils.RUTA_OFICIAL_DOCKER, '/data/db.sqlite3')

    def test_la_imagen_no_lleva_bases_ni_respaldos_dentro(self):
        ignorados = self._leer('.dockerignore')
        for patron in ('*.sqlite3', 'backups/'):
            self.assertIn(patron, ignorados)
