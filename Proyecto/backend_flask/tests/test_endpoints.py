def test_crear_predio_existe_pero_no_esta_implementado(client_bd):
    from tests.helpers import pedir
    response = pedir(client_bd, "/api/v1/predios", metodo="POST", json_body={"nombre": "x"})
    assert response.status_code == 501
    assert response.get_json()["error"]["codigo"] == "NO_IMPLEMENTADO"


def test_calculadora_no_inventa_resultados(client):
    response = client.post("/api/v1/calculos/semillas", json={"superficie_ha": 2})
    assert response.status_code == 501


def test_confirmacion_perimetro_es_pendiente(client_bd):
    from tests.helpers import pedir
    response = pedir(client_bd, "/api/v1/potreros/1/confirmar-perimetro", metodo="POST", json_body={})
    assert response.status_code == 501


def test_ruta_desconocida_devuelve_json(client):
    response = client.get("/api/v1/no-existe")
    assert response.status_code == 404
    assert response.get_json()["error"]["codigo"] == "HTTP_404"


def test_metodo_no_permitido_devuelve_json(client):
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    assert response.get_json()["error"]["codigo"] == "HTTP_405"
