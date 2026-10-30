"""Librerías del navegador (íconos, mapa, PDF, fuentes): copia local primero, CDN solo si falta.

Si existe ``core/static/vendor/<archivo>`` (lo crea ``descargar-librerias.ps1``), la página lo usa y deja de
depender de internet para dibujar íconos, menús y mapas. Si no existe, usa el CDN como hasta ahora.
"""

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def vendor(archivo, cdn):
    ruta = f'vendor/{archivo}'
    return static(ruta) if finders.find(ruta) else cdn
