"""Borrador de endpoints de temporadas. Sin acceso a datos reales."""

from flask import Blueprint, request
from app.api.v1.responses import pendiente

bp = Blueprint("temporadas", __name__)


@bp.route("/temporadas", methods=['GET', 'POST'])
def listar_o_crear_temporadas():
    return pendiente("temporadas", request.method + " /temporadas")


@bp.route("/temporadas/<int:temporada_id>", methods=['GET', 'PATCH', 'DELETE'])
def detalle_temporada(temporada_id):
    return pendiente("temporadas", request.method + " /temporadas/<int:temporada_id>")
