# Catálogo agrícola de AgroAsesor

Estos CSV están **vacíos a propósito** (solo encabezados): ningún dato técnico se inventa.
Completa cada fila solo con valores respaldados por una fuente oficial (SAG, ODEPA, INIA, etiqueta del fabricante).

Orden recomendado de carga (el comando ya lo respeta):
`zonas` → `cultivos` → `problemas` → `insumos` → `usos` → `calendario` + `rendimientos`.

Cómo importar:

    python manage.py importar_catalogo --categorias        # categorías de insumo (una vez)
    python manage.py importar_catalogo data                # simulación: valida y no guarda
    python manage.py importar_catalogo data --aplicar      # guarda
    python manage.py importar_catalogo data --aplicar --actualizar   # además corrige registros ya existentes

Reglas de los CSV:
- Separador `;` o `,`; codificación UTF-8; decimales con coma o punto; fechas AAAA-MM-DD.
- Listas (problemas, cultivos, cultivos_autorizados, objetivos_control) separadas por `|`.
- Celda vacía = «sin dato». Nunca borra un valor ya guardado.
- `calendario.csv` y `rendimientos.csv` se fusionan en la misma referencia (cultivo + zona + variedad + año).
- `usos.csv` declara «este insumo sirve para este problema en este cultivo» y exige fuente y fecha.
- Es seguro ejecutarlo varias veces: no duplica registros.
