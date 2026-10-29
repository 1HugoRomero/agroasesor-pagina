"""Respuestas provisionales para rutas pendientes de implementación."""
from flask import jsonify


def pendiente(modulo: str, operacion: str):
    """Indica explícitamente que todavía NO existe lógica de negocio."""
    return jsonify({"error": {
        "codigo": "NO_IMPLEMENTADO",
        "mensaje": "Endpoint definido en el borrador; aún no implementado.",
        "modulo": modulo,
        "operacion": operacion,
    }}), 501
