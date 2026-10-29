"""Insumos vigentes (lectura) con su estado de verificación y fuente."""
from flask import Blueprint, jsonify, request

from app.security.gateway import requiere_usuario
from app.services import terreno

bp = Blueprint("insumos", __name__)


@bp.get("/insumos")
@requiere_usuario
def listar_insumos():
    cultivo = request.args.get("cultivo_id", type=int)
    return jsonify({"insumos": terreno.listar_insumos(request.args.get("tipo"), cultivo)})


@bp.get("/insumos/<int:insumo_id>")
@requiere_usuario
def detalle_insumo(insumo_id):
    return jsonify(terreno.obtener_insumo(insumo_id))
