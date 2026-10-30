"""Acceso de SOLO LECTURA a la base SQLite de AgroAsesor.

La API nunca escribe en la base: Django es hoy el único escritor. La conexión se abre con ``mode=ro`` y
``PRAGMA query_only`` (doble protección); en Docker el volumen además se monta como solo lectura.
No hay ``create_all`` ni migraciones aquí.
"""

import sqlite3
from pathlib import Path

from flask import current_app, g

from app.errors import ApiError


def abrir_bd():
    if "bd" in g:
        return g.bd
    ruta = current_app.config.get("AGROASESOR_DB_PATH")
    if not ruta:
        raise ApiError(503, "BASE_NO_CONECTADA", "La API no tiene una base de datos configurada.")
    archivo = Path(ruta)
    if not archivo.is_file():
        raise ApiError(503, "BASE_NO_DISPONIBLE", "No se encontró el archivo de la base de datos.")
    try:
        con = sqlite3.connect(f"{archivo.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only = ON")
    except sqlite3.Error:
        raise ApiError(503, "BASE_NO_DISPONIBLE", "No se pudo abrir la base de datos en modo lectura.")
    g.bd = con
    return con


def cerrar_bd(_error=None):
    con = g.pop("bd", None)
    if con is not None:
        con.close()
