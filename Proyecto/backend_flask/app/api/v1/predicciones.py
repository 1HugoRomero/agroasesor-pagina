"""Borrador de endpoints de predicciones. Sin acceso a datos reales."""
from flask import Blueprint, request
from app.api.v1.responses import pendiente

bp = Blueprint("predicciones", __name__)


@bp.route("/predicciones/rendimiento", methods=['POST'])
def estimar_rendimiento():
    return pendiente("predicciones", request.method + " /predicciones/rendimiento")
