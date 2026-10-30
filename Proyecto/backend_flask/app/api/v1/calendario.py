"""Borrador de endpoints de calendario. Sin acceso a datos reales."""

from flask import Blueprint, request
from app.api.v1.responses import pendiente

bp = Blueprint("calendario", __name__)


@bp.route("/calendario", methods=['GET'])
def consultar_calendario():
    return pendiente("calendario", request.method + " /calendario")
