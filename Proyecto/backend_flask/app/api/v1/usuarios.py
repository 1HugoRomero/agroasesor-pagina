"""Perfil del usuario autenticado (lectura). La edición sigue en Django hasta una fase posterior."""

from flask import Blueprint, g, jsonify, request

from app.api.v1.responses import pendiente
from app.security.gateway import requiere_usuario
from app.services import terreno

bp = Blueprint("usuarios", __name__)


@bp.route("/usuarios/me", methods=["GET", "PATCH"])
@requiere_usuario
def mi_perfil():
    if request.method == "PATCH":
        return pendiente("usuarios", "PATCH /usuarios/me")
    return jsonify(terreno.perfil_usuario(g.usuario.id))
