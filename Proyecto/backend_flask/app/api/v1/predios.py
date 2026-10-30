"""Predios del usuario autenticado (lectura). Crear/editar/borrar sigue en Django."""

from flask import Blueprint, g, jsonify, request

from app.api.v1.responses import pendiente
from app.security.gateway import requiere_usuario
from app.services import terreno

bp = Blueprint("predios", __name__)


@bp.route("/predios", methods=["GET", "POST"])
@requiere_usuario
def listar_o_crear_predios():
    if request.method == "POST":
        return pendiente("predios", "POST /predios")
    return jsonify({"predios": terreno.listar_predios(g.usuario)})


@bp.route("/predios/<int:predio_id>", methods=["GET", "PATCH", "DELETE"])
@requiere_usuario
def detalle_predio(predio_id):
    if request.method != "GET":
        return pendiente("predios", f"{request.method} /predios/<int:predio_id>")
    return jsonify(terreno.obtener_predio(predio_id, g.usuario))
