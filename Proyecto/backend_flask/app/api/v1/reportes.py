"""Borrador de endpoints de reportes. Sin acceso a datos reales."""

from flask import Blueprint, request
from app.api.v1.responses import pendiente

bp = Blueprint("reportes", __name__)


@bp.route("/reportes/resumen", methods=['GET'])
def resumen_reportes():
    return pendiente("reportes", request.method + " /reportes/resumen")


@bp.route("/reportes/predios/<int:predio_id>/historial", methods=['GET'])
def historial_predio(predio_id):
    return pendiente("reportes", request.method + " /reportes/predios/<int:predio_id>/historial")
