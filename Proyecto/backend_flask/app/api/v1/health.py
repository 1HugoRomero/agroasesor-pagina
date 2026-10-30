"""Estado de la API. Es público pero NO expone rutas, claves ni datos: solo si la base está conectada."""

import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, jsonify

bp = Blueprint("health", __name__)


def _estado_bd():
    ruta = current_app.config.get("AGROASESOR_DB_PATH")
    if not ruta:
        return "no_configurada"
    if not Path(ruta).is_file():
        return "no_disponible"
    try:
        con = sqlite3.connect(f"{Path(ruta).resolve().as_uri()}?mode=ro", uri=True, timeout=3)
        try:
            con.execute("SELECT 1 FROM auth_user LIMIT 1")
        finally:
            con.close()
    except sqlite3.Error:
        return "no_disponible"
    return "conectada_solo_lectura"


@bp.get("/health")
def health():
    return jsonify({"status": "ok", "servicio": "agroasesor-api", "version": "v1", "base_datos": _estado_bd()}), 200


@bp.get("/openapi.json")
def openapi_json():
    """Especificación OpenAPI en JSON (la misma que openapi.yaml)."""
    import yaml
    from pathlib import Path

    ruta = Path(current_app.root_path).parent / "openapi.yaml"
    return jsonify(yaml.safe_load(ruta.read_text(encoding="utf-8")))
