"""Borrador de endpoints de actividades. Sin acceso a datos reales."""
from flask import Blueprint, request
from app.api.v1.responses import pendiente

bp = Blueprint("actividades", __name__)


@bp.route("/actividades", methods=['GET', 'POST'])
def listar_o_crear_actividades():
    return pendiente("actividades", request.method + " /actividades")


@bp.route("/actividades/<int:actividad_id>", methods=['GET', 'PATCH', 'DELETE'])
def detalle_actividad(actividad_id):
    return pendiente("actividades", request.method + " /actividades/<int:actividad_id>")
