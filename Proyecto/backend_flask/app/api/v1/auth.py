"""Borrador de endpoints de auth. Sin acceso a datos reales."""

from flask import Blueprint, request
from app.api.v1.responses import pendiente

bp = Blueprint("auth", __name__)


@bp.route("/auth/registro", methods=['POST'])
def registrar_usuario():
    return pendiente("auth", request.method + " /auth/registro")


@bp.route("/auth/login", methods=['POST'])
def iniciar_sesion():
    return pendiente("auth", request.method + " /auth/login")


@bp.route("/auth/logout", methods=['POST'])
def cerrar_sesion():
    return pendiente("auth", request.method + " /auth/logout")
