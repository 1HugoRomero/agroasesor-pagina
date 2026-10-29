"""Sesión vencida o cookies borradas: la página no debe «caerse».

* Formularios normales: si falta o venció la verificación CSRF (típico al borrar las cookies con la página abierta),
  en vez de la pantalla de error de Django se vuelve a la página anterior (o al login) con un aviso claro.
* Llamadas de la propia página (fetch/AJAX): responden JSON ``{"codigo": "sesion_vencida"}`` en vez de HTML,
  y ``static/js/layout.js`` lleva a la persona al login sin pantallas rotas.
"""
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme, urlencode

MENSAJE_VENCIDA = 'Tu sesión venció o se borraron las cookies. Vuelve a iniciar sesión para continuar.'
MENSAJE_REINTENTAR = 'La página estuvo abierta demasiado tiempo o se borraron las cookies. Inténtalo de nuevo.'


def es_ajax(request):
    tipo = request.META.get('CONTENT_TYPE', '')
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
        or tipo.startswith('application/json')
    )


def _json_vencida(status):
    return JsonResponse({
        'error': MENSAJE_VENCIDA,
        'codigo': 'sesion_vencida',
        'login_url': resolve_url(settings.LOGIN_URL),
    }, status=status)


def _volver(request):
    """Página anterior si es de este mismo sitio; si no, None."""
    anterior = request.META.get('HTTP_REFERER', '')
    if anterior and url_has_allowed_host_and_scheme(anterior, {request.get_host()}, request.is_secure()):
        return anterior
    return None


def fallo_csrf(request, reason=''):
    """Sustituye la pantalla 403 de Django (CSRF_FAILURE_VIEW)."""
    if es_ajax(request):
        return _json_vencida(403)
    login = resolve_url(settings.LOGIN_URL)
    if request.user.is_authenticated:
        messages.warning(request, MENSAJE_REINTENTAR)
        return redirect(_volver(request) or resolve_url(settings.LOGIN_REDIRECT_URL))
    messages.warning(request, MENSAJE_VENCIDA if request.path != login else MENSAJE_REINTENTAR)
    return redirect(login)


class SesionVencidaMiddleware:
    """Si una llamada AJAX sin sesión sería redirigida al login, responde 401 JSON (no el HTML del login)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        if respuesta.status_code in (301, 302) and es_ajax(request) and not request.user.is_authenticated:
            login = resolve_url(settings.LOGIN_URL)
            if respuesta.headers.get('Location', '').split('?')[0] == login:
                return _json_vencida(401)
        return respuesta
