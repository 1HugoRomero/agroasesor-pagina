"""Borrador de endpoints de admin. Sin acceso a datos reales."""
from flask import Blueprint, request
from app.api.v1.responses import pendiente

bp = Blueprint("admin", __name__)


@bp.route("/admin/resumen", methods=['GET'])
def resumen_administrador():
    return pendiente("admin", request.method + " /admin/resumen")
