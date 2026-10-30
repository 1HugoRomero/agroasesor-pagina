"""Zonas agrícolas (lectura)."""

from flask import Blueprint, jsonify

from app.security.gateway import requiere_usuario
from app.services import terreno

bp = Blueprint("zonas", __name__)


@bp.get("/zonas")
@requiere_usuario
def listar_zonas():
    return jsonify({"zonas": terreno.listar_zonas()})
