"""Autenticación por puerta de enlace: Django autentica, la API verifica.

AgroAsesor tiene UN solo sistema de usuarios (Django: cuentas, contraseñas y sesiones). Mientras Flask se
convierte en backend principal, las peticiones del navegador entran por Django (``/api/v1/...``); Django comprueba
la sesión y reenvía la petición a esta API con cuatro cabeceras firmadas con HMAC-SHA256:

    X-AgroAsesor-User, X-AgroAsesor-Staff, X-AgroAsesor-Timestamp, X-AgroAsesor-Signature

La firma cubre usuario, rol, fecha, método, ruta+consulta y huella del cuerpo, por lo que no se puede cambiar
el usuario, reutilizar la firma en otra ruta ni alterar el contenido. Caduca a los 60 s. La API no emite
sesiones ni contraseñas propias.
"""

import hashlib
import hmac
import time
from dataclasses import dataclass
from functools import wraps

from flask import current_app, g, request

from app.errors import ApiError

MIN_SECRETO = 32


@dataclass(frozen=True)
class Usuario:
    id: int
    es_admin: bool


def firmar(secreto, usuario_id, es_admin, marca, metodo, destino, cuerpo=b""):
    """Firma HMAC-SHA256 (hex). Django usa esta misma definición (ver core/api_gateway.py)."""
    base = "|".join(
        [
            str(int(usuario_id)),
            "1" if es_admin else "0",
            str(int(marca)),
            metodo.upper(),
            destino,
            hashlib.sha256(cuerpo).hexdigest(),
        ]
    )
    return hmac.new(secreto.encode("utf-8"), base.encode("utf-8"), hashlib.sha256).hexdigest()


def _destino_actual():
    consulta = request.query_string.decode("latin-1")
    return request.path + ("?" + consulta if consulta else "")


def usuario_firmado():
    secreto = current_app.config.get("AGROASESOR_INTERNAL_SECRET") or ""
    if len(secreto) < MIN_SECRETO:
        raise ApiError(503, "AUTENTICACION_NO_CONFIGURADA", "La API no tiene configurada la clave interna.")
    encabezados = request.headers
    try:
        usuario_id = int(encabezados.get("X-AgroAsesor-User", ""))
        marca = int(encabezados.get("X-AgroAsesor-Timestamp", ""))
    except ValueError:
        raise ApiError(401, "NO_AUTENTICADO", "Falta autenticación válida.")
    es_admin = encabezados.get("X-AgroAsesor-Staff") == "1"
    firma = encabezados.get("X-AgroAsesor-Signature", "")
    vigencia = current_app.config.get("AGROASESOR_FIRMA_VIGENCIA_SEGUNDOS", 60)
    if usuario_id <= 0 or abs(time.time() - marca) > vigencia:
        raise ApiError(401, "NO_AUTENTICADO", "La autenticación venció o no es válida.")
    esperada = firmar(secreto, usuario_id, es_admin, marca, request.method, _destino_actual(), request.get_data())
    if not hmac.compare_digest(esperada, firma):
        raise ApiError(401, "NO_AUTENTICADO", "La firma de la petición no es válida.")
    return Usuario(usuario_id, es_admin)


def requiere_usuario(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        g.usuario = usuario_firmado()
        return vista(*args, **kwargs)

    return envoltura


def requiere_admin(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        g.usuario = usuario_firmado()
        if not g.usuario.es_admin:
            raise ApiError(403, "SIN_PERMISO", "Esta operación es solo para administradores.")
        return vista(*args, **kwargs)

    return envoltura
