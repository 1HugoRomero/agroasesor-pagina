# Prompt para Claude · Integración del catálogo de AgroAsesor

Estoy desarrollando AgroAsesor, mi proyecto de título. Ya existe un proyecto Django con usuarios, predios, potreros, historial, cálculos, etc. Recibí una carpeta `backend_flask/` v0.2 que tiene una API de catálogo agrícola funcional e independiente con datos YAML respaldados por SAG, INIA y ODEPA.

**Tu tarea es integrar con seguridad, no reescribir ni borrar mi proyecto.**

1. Audita primero la estructura real de mi repositorio, sus modelos, rutas, Docker, frontend y base SQLite. No asumas que las rutas de Django se pueden copiar sin cambios a Flask.
2. Incorpora `backend_flask/` sin borrar Django, sin ejecutar migraciones, sin tocar `db.sqlite3` oficial ni crear otra base de producción.
3. Instala dependencias y ejecuta `pytest -q`. Levanta Flask en puerto 5050 y verifica `/catalogo`, `/api/v1/catalogo/productos`, `/api/v1/catalogo/fuentes` y `/api/v1/catalogo/calcular-sacos`.
4. Revisa `data/catalogo_agricola.yaml` y `docs/catalogo_fuentes_oficiales.md`: NO atribuyas a SAG certificaciones, precios, formatos comerciales, autorizaciones vigentes o sellos que no hayan sido comprobados. Las etiquetas SAG no equivalen por sí solas a vigencia de registro.
5. Propón cómo conectar la interfaz de Django con la API, idealmente con un adaptador o una vista de catálogo, sin romper usuarios, sesiones, predios o cálculos existentes. La integración final debe seguir el plan de migración y tener una sola base de datos oficial.
6. Diseña un futuro importador para registros SAG con validación, checksum, fecha, id de registro, etiqueta, control de vigencia y auditoría; no lo ejecutes sobre producción sin aprobación.
7. Distingue datos oficiales, información de proveedores y datos de ejemplo. El peso del saco 25 kg es una simulación editable. No habilites cálculos de dosis de plaguicidas.
8. Al final informa exactamente qué archivos modificaste, pruebas realizadas, riesgos y próximos pasos. No digas que algo funciona si no lo ejecutaste.

**Objetivo:** catálogo agrícola de calidad para Chile, con trazabilidad verificable, sin perder funcionalidades existentes y sin inventar datos comerciales o avales oficiales.
