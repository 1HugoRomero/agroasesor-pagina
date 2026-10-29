import pytest

from app import create_app
from tests.helpers import SECRETO, crear_bd


@pytest.fixture
def client():
    """Cliente SIN base ni clave: comprueba que la API falla cerrada."""
    app = create_app({"TESTING": True, "AGROASESOR_DB_PATH": "", "AGROASESOR_INTERNAL_SECRET": ""})
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def bd_path(tmp_path):
    return crear_bd(tmp_path / "prueba.sqlite3")


@pytest.fixture
def client_bd(bd_path):
    app = create_app({"TESTING": True, "AGROASESOR_DB_PATH": bd_path, "AGROASESOR_INTERNAL_SECRET": SECRETO})
    with app.test_client() as test_client:
        yield test_client
