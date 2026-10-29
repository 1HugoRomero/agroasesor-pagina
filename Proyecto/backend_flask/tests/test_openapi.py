"""La especificación debe describir EXACTAMENTE las rutas que existen (sin documentar de más ni de menos)."""
import re
from pathlib import Path

import yaml

from app import create_app

RAIZ = Path(__file__).resolve().parents[1]


def _operaciones_codigo():
    app = create_app({"TESTING": True})
    ops = set()
    for regla in app.url_map.iter_rules():
        if not regla.rule.startswith("/api/v1"):
            continue
        ruta = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", regla.rule[len("/api/v1"):])
        for m in regla.methods - {"HEAD", "OPTIONS"}:
            ops.add((ruta, m.lower()))
    return ops


def test_openapi_coincide_con_las_rutas(client=None):
    spec = yaml.safe_load((RAIZ / "openapi.yaml").read_text(encoding="utf-8"))
    doc = {(r, m) for r, ms in spec["paths"].items() for m in ms if m in {"get", "post", "patch", "delete", "put"}}
    codigo = _operaciones_codigo()
    assert doc - codigo == set(), f"documentadas pero inexistentes: {sorted(doc - codigo)}"
    assert codigo - doc == set(), f"existen pero sin documentar: {sorted(codigo - doc)}"


def test_openapi_json_disponible(client):
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200 and r.get_json()["openapi"] == "3.0.3"
