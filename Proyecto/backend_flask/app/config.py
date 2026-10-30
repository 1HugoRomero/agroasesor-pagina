"""Configuración de la API. Nada sensible está escrito aquí: todo llega por variables de entorno."""

import os


class Config:
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    # Base SQLite que la API LEE (siempre en modo solo lectura). En desarrollo debe ser una COPIA; en Docker es
    # /data/db.sqlite3 montada con «:ro». Si no se configura, los endpoints con datos responden 503.
    AGROASESOR_DB_PATH = os.getenv("AGROASESOR_DB_PATH", "")
    # Clave compartida con Django para firmar las peticiones internas (mínimo 32 caracteres).
    # Sin ella la API rechaza (503) todo lo que requiera usuario: falla cerrada, nunca abierta.
    AGROASESOR_INTERNAL_SECRET = os.getenv("AGROASESOR_INTERNAL_SECRET", "")
    # Tolerancia del reloj entre Django y la API, en segundos.
    AGROASESOR_FIRMA_VIGENCIA_SEGUNDOS = int(os.getenv("AGROASESOR_FIRMA_VIGENCIA_SEGUNDOS", "60"))
    MAX_CONTENT_LENGTH = 64 * 1024
