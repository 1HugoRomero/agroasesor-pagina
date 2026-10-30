"""Puerta de enlace Django → API Flask (``/api/v1/...``).

Django sigue siendo el ÚNICO sistema de cuentas y sesiones. Esta vista:

* comprueba la sesión de Django (y el CSRF de Django en POST/PATCH/DELETE: no está exenta);
* reenvía la petición a la API Flask (URL fija en ajustes, nunca elegida por el visitante);
* firma el reenvío con HMAC-SHA256 indicando quién es el usuario y si es admin (la API no vuelve a pedir contraseña);
* descarta cualquier cabecera ``X-AgroAsesor-*`` que venga del navegador.

Sin ``AGROASESOR_API_URL`` y ``AGROASESOR_INTERNAL_SECRET`` (≥ 32 caracteres) responde 503 y no reenvía nada.
La definición de la firma debe coincidir con ``backend_flask/app/security/gateway.py`` (hay una prueba con un
vector fijo en ambos lados).
"""

import hashlib
import hmac
import re
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.http import HttpResponse, JsonResponse

MIN_SECRETO = 32
METODOS = {"GET", "POST", "PATCH", "DELETE"}
RUTA_SEGURA = re.compile(r"^[A-Za-z0-9_\-][A-Za-z0-9_\-.]*(?:/[A-Za-z0-9_\-][A-Za-z0-9_\-.]*)*/?$")
MAX_CUERPO = 64 * 1024
# Lo único que se puede consultar sin iniciar sesión (solo lectura y sin datos de personas).
PUBLICAS_GET = re.compile(r"^(health|openapi\.json|catalogo/[A-Za-z0-9_\-/]*)$")


def firmar(secreto, usuario_id, es_admin, marca, metodo, destino, cuerpo=b""):
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


def _error(status, codigo, mensaje):
    return JsonResponse({"error": {"codigo": codigo, "mensaje": mensaje}}, status=status)


class _SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def api_v1(request, ruta):
    base = getattr(settings, "AGROASESOR_API_URL", "")
    secreto = getattr(settings, "AGROASESOR_INTERNAL_SECRET", "")
    if not base or len(secreto) < MIN_SECRETO:
        return _error(503, "API_NO_CONFIGURADA", "La API de AgroAsesor no está configurada en este entorno.")
    if request.method not in METODOS:
        return _error(405, "HTTP_405", "Método no permitido.")
    if not RUTA_SEGURA.match(ruta) or ".." in ruta:
        return _error(404, "HTTP_404", "Ruta no encontrada.")

    destino = "/api/v1/" + ruta
    consulta = request.META.get("QUERY_STRING", "")
    if consulta:
        destino += "?" + consulta
    cuerpo = request.body if request.method != "GET" else b""
    if len(cuerpo) > MAX_CUERPO:
        return _error(413, "CUERPO_MUY_GRANDE", "La petición es demasiado grande.")

    cabeceras = {"Accept": "application/json"}
    if cuerpo:
        cabeceras["Content-Type"] = request.META.get("CONTENT_TYPE", "application/json")
    if request.user.is_authenticated:
        marca = int(time.time())
        es_admin = bool(request.user.is_staff)
        cabeceras.update(
            {
                "X-AgroAsesor-User": str(request.user.pk),
                "X-AgroAsesor-Staff": "1" if es_admin else "0",
                "X-AgroAsesor-Timestamp": str(marca),
                "X-AgroAsesor-Signature": firmar(
                    secreto, request.user.pk, es_admin, marca, request.method, destino, cuerpo
                ),
            }
        )
    elif not (request.method == "GET" and PUBLICAS_GET.match(ruta.rstrip("/"))):
        return _error(401, "NO_AUTENTICADO", "Inicia sesión para usar esta función.")

    peticion = urllib.request.Request(base + destino, data=cuerpo or None, headers=cabeceras, method=request.method)
    # ProxyHandler({}): la llamada interna jamás debe pasar por un proxy del entorno (HTTP_PROXY, etc.).
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}), _SinRedireccion)
    try:
        with abridor.open(peticion, timeout=getattr(settings, "AGROASESOR_API_TIMEOUT", 10)) as r:
            status, datos, tipo = r.status, r.read(), r.headers.get("Content-Type", "application/json")
    except urllib.error.HTTPError as e:  # 4xx/5xx de la API: se devuelven tal cual (son JSON de error)
        status, datos, tipo = e.code, e.read(), e.headers.get("Content-Type", "application/json")
    except (urllib.error.URLError, TimeoutError, OSError):
        return _error(502, "API_NO_DISPONIBLE", "El servicio de la API no responde.")

    respuesta = HttpResponse(datos, status=status, content_type=tipo)
    if request.user.is_authenticated:
        respuesta["Cache-Control"] = "no-store"
    return respuesta
