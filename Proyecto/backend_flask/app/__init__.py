"""Punto de entrada de la API Flask de AgroAsesor (servicio interno detrás de Django)."""

from flask import Flask, render_template
from app.api.v1 import register_v1_blueprints
from app.db import cerrar_bd
from app.errors import register_error_handlers


def create_app(test_config=None):
    """Construye la aplicación. La base (solo lectura) se abre bajo demanda, nunca aquí."""
    app = Flask(__name__)
    app.config.from_object("app.config.Config")
    if test_config is not None:
        app.config.update(test_config)
    register_v1_blueprints(app)
    register_error_handlers(app)
    app.teardown_appcontext(cerrar_bd)

    @app.get("/catalogo")
    def catalogo_demo():
        """Vista de demostración independiente, sin modificar Django."""
        return render_template("catalogo.html")
    return app
