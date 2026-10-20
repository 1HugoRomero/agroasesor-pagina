#!/bin/sh
set -e

# Crea/actualiza las tablas y asegura las categorías base de insumos (ambos pasos son idempotentes).
python manage.py migrate --noinput
python manage.py importar_catalogo --categorias

# Catálogo inicial desde data/*.csv: cultivos y zona Melipilla (solo nombres; sin densidades, dosis ni fuentes inventadas).
# Es idempotente: lo que ya existe no se modifica. Si falla, la aplicación igual arranca y el aviso queda en el log.
python manage.py importar_catalogo data --aplicar || echo "AVISO: no se pudo importar el catálogo inicial desde data/ (revisa los CSV)."

exec "$@"
