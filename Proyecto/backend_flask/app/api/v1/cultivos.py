"""Catálogo de cultivos (lectura). Los datos sin fuente verificada se marcan como «sin_verificar»."""
from flask import Blueprint, jsonify

from app.security.gateway import requiere_usuario
from app.services import terreno

bp = Blueprint("cultivos", __name__)


@bp.get("/cultivos")
@requiere_usuario
def listar_cultivos():
    return jsonify({"cultivos": terreno.listar_cultivos()})


@bp.get("/cultivos/<int:cultivo_id>")
@requiere_usuario
def detalle_cultivo(cultivo_id):
    return jsonify(terreno.obtener_cultivo(cultivo_id))
