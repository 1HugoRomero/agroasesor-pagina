"""Formato consistente de errores JSON: {"error": {"codigo": ..., "mensaje": ...}}."""
from flask import jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """Error previsto de la API (validación, permisos, recurso inexistente...)."""

    def __init__(self, status, codigo, mensaje):
        super().__init__(mensaje)
        self.status, self.codigo, self.mensaje = status, codigo, mensaje


def respuesta_error(status, codigo, mensaje):
    return jsonify({"error": {"codigo": codigo, "mensaje": mensaje}}), status


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def api_error(error):
        return respuesta_error(error.status, error.codigo, error.mensaje)

    @app.errorhandler(HTTPException)
    def http_error(error):
        return respuesta_error(error.code, f"HTTP_{error.code}", error.description)

    @app.errorhandler(Exception)
    def internal_error(error):
        app.logger.exception("Error no controlado")
        return respuesta_error(500, "ERROR_INTERNO", "Error interno del servidor")
