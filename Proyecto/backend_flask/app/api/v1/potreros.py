"""Potreros del usuario autenticado (lectura) con superficie en ha y m²."""

from flask import Blueprint, g, jsonify, request

from app.api.v1.responses import pendiente
from app.security.gateway import requiere_usuario
from app.services import terreno

bp = Blueprint("potreros", __name__)


@bp.route("/predios/<int:predio_id>/potreros", methods=["GET", "POST"])
@requiere_usuario
def potreros_de_predio(predio_id):
    if request.method == "POST":
        return pendiente("potreros", "POST /predios/<int:predio_id>/potreros")
    return jsonify({"potreros": terreno.listar_potreros(predio_id, g.usuario)})


@bp.route("/potreros/<int:potrero_id>", methods=["GET", "PATCH", "DELETE"])
@requiere_usuario
def detalle_potrero(potrero_id):
    if request.method != "GET":
        return pendiente("potreros", f"{request.method} /potreros/<int:potrero_id>")
    return jsonify(terreno.obtener_potrero(potrero_id, g.usuario))


@bp.route("/potreros/<int:potrero_id>/confirmar-perimetro", methods=["POST"])
@requiere_usuario
def confirmar_perimetro(potrero_id):
    return pendiente("potreros", "POST /potreros/<int:potrero_id>/confirmar-perimetro")
