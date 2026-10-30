"""RF-26: estadísticas del panel de administración, con datos reales y sin confundir cálculos con consultas."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.estadisticas import resumen_administrador
from core.models import ActividadAgricola, CalculoAgricola, Cultivo, Insumo, Potrero, Predio

User = get_user_model()


class EstadisticasAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            'admin1', 'admin1@example.com', 'Clave-segura-123', is_staff=True, is_superuser=True
        )
        self.agri = User.objects.create_user('agri1', 'agri1@example.com', 'Clave-segura-123')
        self.agri2 = User.objects.create_user('agri2', 'agri2@example.com', 'Clave-segura-123')
        self.trigo = Cultivo.objects.create(nombre='Trigo')
        self.papa = Cultivo.objects.create(nombre='Papa')
        self.predio = Predio.objects.create(
            propietario=self.agri, nombre='Campo', ubicacion='Melipilla', superficie_ha=10
        )
        self.potrero = Potrero.objects.create(predio=self.predio, nombre='Lote 1', superficie_ha=2, cultivo=self.trigo)
        Potrero.objects.create(predio=self.predio, nombre='Lote 2', superficie_ha=1)

    def _calculo(self, operacion, entrada=None, resultado=None):
        return CalculoAgricola.objects.create(
            usuario=self.agri,
            potrero=self.potrero,
            operacion=operacion,
            entrada=entrada or {},
            resultado=resultado or {},
        )

    def test_conteos_basicos_sin_contar_administradores_como_agricultores(self):
        datos = resumen_administrador()
        self.assertEqual(datos['agricultores'], 2)
        self.assertEqual(datos['administradores'], 1)
        self.assertEqual(datos['predios'], 1)
        self.assertEqual(datos['potreros'], 2)
        self.assertEqual(datos['cultivos_catalogo'], 2)
        self.assertEqual(datos['potreros_con_cultivo'], 1)

    def test_sin_datos_no_inventa_ranking(self):
        datos = resumen_administrador()
        self.assertEqual(datos['calculos'], 0)
        self.assertEqual(datos['cultivos_mas_usados'], [])
        self.assertEqual(datos['insumos_mas_usados'], [])
        self.assertEqual(datos['actividades'], 0)

    def test_ranking_de_cultivos_e_insumos_usados_en_calculos(self):
        urea = Insumo.objects.create(nombre='Urea', tipo=self._tipo())
        self._calculo('dose', {'crop': 'Trigo'}, {'crop': 'Trigo', 'product': 'Urea'})
        self._calculo('dose', {'crop': 'Trigo'}, {'crop': 'Trigo', 'product': 'Urea'})
        self._calculo('yield', {'crop': 'Papa'}, {})
        self._calculo('fertilizer_nutrition', {'crop': 'Trigo', 'product_id': str(urea.pk)}, {})
        self._calculo('seed_population', {}, {})
        datos = resumen_administrador()
        self.assertEqual(datos['calculos'], 5)
        self.assertEqual(datos['cultivos_mas_usados'][0]['nombre'], 'Trigo')
        self.assertEqual(datos['cultivos_mas_usados'][0]['cantidad'], 3)
        self.assertEqual(datos['cultivos_mas_usados'][1]['nombre'], 'Papa')
        self.assertEqual(datos['insumos_mas_usados'][0], {'nombre': 'Urea', 'cantidad': 3, 'porcentaje': 100})
        self.assertEqual(datos['calculos_sin_cultivo'], 1)
        self.assertEqual(datos['calculos_sin_insumo'], 2)

    def test_datos_malformados_no_rompen(self):
        self._calculo('dose', {'crop': 123, 'product_id': 'abc'}, {'crop': None, 'product': ['x']})
        datos = resumen_administrador()
        self.assertEqual(datos['calculos'], 1)
        self.assertEqual(datos['cultivos_mas_usados'], [])

    def test_actividades_por_estado(self):
        for estado in ('pendiente', 'pendiente', 'completada'):
            ActividadAgricola.objects.create(
                usuario=self.agri,
                potrero=self.potrero,
                nombre='Tarea',
                tipo='riego',
                fecha_programada=date(2026, 10, 1),
                estado=estado,
            )
        datos = resumen_administrador()
        self.assertEqual(datos['actividades'], 3)
        self.assertEqual(datos['actividades_pendientes'], 2)
        self.assertEqual(datos['actividades_completadas'], 1)

    def test_panel_solo_para_administradores_y_muestra_datos(self):
        self._calculo('dose', {'crop': 'Trigo'}, {'crop': 'Trigo'})
        self.client.force_login(self.agri)
        self.assertEqual(self.client.get('/panel-admin/').status_code, 403)
        self.client.force_login(self.admin)
        respuesta = self.client.get('/panel-admin/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Cálculos realizados')
        self.assertContains(respuesta, 'Trigo')
        self.assertContains(respuesta, 'no se registran')

    def _tipo(self):
        from core.models import TipoInsumo

        return TipoInsumo.objects.get_or_create(nombre='Fertilizante')[0]
