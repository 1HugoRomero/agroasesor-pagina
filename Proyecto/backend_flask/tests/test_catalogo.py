"""Pruebas de integración para la parte funcional del borrador."""


def test_categorias_y_fuentes(client):
    cats = client.get('/api/v1/catalogo/categorias')
    assert cats.status_code == 200
    assert any(x['id'] == 'repelentes' for x in cats.get_json()['resultados'])
    sources = client.get('/api/v1/catalogo/fuentes')
    assert sources.status_code == 200
    assert {'SAG', 'INIA', 'ODEPA'} <= {s['organismo'] for s in sources.get_json()['resultados']}


def test_filtros_y_detalle(client):
    response = client.get('/api/v1/catalogo/productos?categoria=repelentes')
    assert response.status_code == 200
    products = response.get_json()['resultados']
    assert products and all(p['categoria'] == 'repelentes' for p in products)
    assert all(p['estado_autorizacion'] == 'requiere_cotejo_vigente' for p in products)
    detail = client.get('/api/v1/catalogo/productos/fungisei')
    assert detail.status_code == 200
    assert detail.get_json()['registro_indicado_en_etiqueta'] == '20045'
    assert detail.get_json()['precio_clp'] is None
    assert client.get('/api/v1/catalogo/productos/no-existe').status_code == 404
    assert client.get('/api/v1/catalogo/productos?categoria=inventada').status_code == 400


def test_calculadora_semillas_ha_y_m2(client):
    for surface in ({'superficie_ha': 1.5}, {'superficie_m2': 15000}):
        r = client.post(
            '/api/v1/catalogo/calcular-sacos',
            json={
                'referencia_id': 'trigo-invierno',
                **surface,
                'peso_saco_kg': 25,
                'dosis_kg_ha': 180,
            },
        )
        assert r.status_code == 200
        j = r.get_json()
        assert j['semilla_requerida_kg'] == 270.0
        assert j['sacos_necesarios'] == 11
        assert j['sobrante_teorico_kg'] == 5.0
        assert j['fuente']['organismo'] == 'INIA'
        assert j['costo_estimado_clp'] is None


def test_validaciones_y_no_dosificacion_fitosanitaria(client):
    body = {'referencia_id': 'trigo-invierno', 'superficie_ha': 1, 'peso_saco_kg': 25, 'dosis_kg_ha': 180}
    assert client.post('/api/v1/catalogo/calcular-sacos', json={**body, 'dosis_kg_ha': 400}).status_code == 400
    assert client.post('/api/v1/catalogo/calcular-sacos', json={**body, 'peso_saco_kg': True}).status_code == 400
    assert client.post('/api/v1/catalogo/calcular-sacos', json={**body, 'superficie_m2': 10000}).status_code == 400
    assert client.post('/api/v1/catalogo/calcular-sacos', json={**body, 'extra': 1}).status_code == 400
    assert client.post('/api/v1/catalogo/calcular-sacos', data='hola').status_code == 415


def test_vista_demo(client):
    r = client.get('/catalogo')
    assert r.status_code == 200
    assert b'AgroAsesor' in r.data


def test_costo_usuario_no_es_precio_oficial(client):
    r = client.post(
        '/api/v1/catalogo/calcular-sacos',
        json={
            'referencia_id': 'trigo-invierno',
            'superficie_ha': 1.5,
            'peso_saco_kg': 25,
            'dosis_kg_ha': 180,
            'precio_saco_clp': 20000,
        },
    )
    assert r.status_code == 200
    assert r.get_json()['costo_estimado_clp'] == 220000
