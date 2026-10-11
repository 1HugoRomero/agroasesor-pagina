# AgroAsesor

Django 6.1.1 monolítico, Django Templates, HTML/CSS/JavaScript y SQLite.
La auditoría, estado de los 22 requisitos y fases siguientes están en [AUDITORIA.md](AUDITORIA.md).

## Ejecutar localmente (PowerShell, desde esta carpeta)

Requiere Python 3.12 o superior.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Proyecto/requirements.txt
# Solo si no existe .env: copiar y completar la plantilla, sin sobreescribir el archivo local.
Copy-Item Proyecto/.env.example Proyecto/.env
.\.venv\Scripts\python.exe Proyecto/manage.py migrate
.\.venv\Scripts\python.exe Proyecto/manage.py createsuperuser
.\.venv\Scripts\python.exe Proyecto/manage.py runserver
```

En este workspace ya se preparó un entorno virtual en la carpeta padre
`APLICACION/.venv`; se puede usar `..\.venv\Scripts\python.exe` desde `AgroAsesor`.
No hay credenciales demo habilitadas. Registra un agricultor en `/login/?mode=register`.
Para el administrador, crea una cuenta mediante `createsuperuser` y usa `/admin/`.
Configura un correo en esa cuenta para ingresar también por `/login/`.

## Variables locales

El archivo `Proyecto/.env` queda ignorado por Git. Nunca publiques sus secretos.

```dotenv
DJANGO_SECRET_KEY=un-secreto-aleatorio-largo
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
MAP_TILE_URL=https://tile.openstreetmap.de/{z}/{x}/{y}.png
```

Las variables del sistema tienen prioridad sobre `.env`. Para producción utiliza
DEBUG=False, un secreto estable, dominios explícitos y HTTPS; las cookies seguras
se activan con DEBUG=False.

## Cartografía GIS

La pantalla de predios utiliza Leaflet y Leaflet-Geoman Free con teselas raster
de OpenStreetMap.de para uso interactivo de bajo volumen; no requiere clave.
Se verificó que el servidor de teselas OSM estándar bloqueaba peticiones de este
entorno. La atribución visible identifica a OpenStreetMap. Respeta la política
de uso y atribución del proveedor configurado. Para mayor carga, configura un
proveedor apropiado mediante `MAP_TILE_URL` y, si corresponde,
`MAP_TILE_ATTRIBUTION`.

Los vértices heredados se conservan en el campo `perimetro`; la migración aditiva
`0003` los copia a GeoJSON sin borrar el formato previo. El registro de predios
guía al usuario por el dibujo, la aceptación expresa del perímetro, la revisión
de la medición y el formulario. Django vuelve a validar el polígono cerrado,
rechaza autointersecciones y recalcula la superficie antes de persistir. La ficha
del predio muestra su geometría, los potreros y el historial versionado de cambios.
La migración aditiva `0005` añade la fecha de modificación y los eventos de
historial sin borrar predios existentes. La longitud se deriva del contorno
guardado. Los potreros se comprueban contra el límite GeoJSON del predio cuando
este existe y se rechazan superposiciones dentro del mismo predio. Los registros
anteriores sin geometría se conservan y pueden actualizarse sin descartar
implícitamente su perímetro.
La página «Mis predios y potreros» lista todos los predios propios, sincroniza la
selección del listado con las geometrías Leaflet y ofrece búsqueda, filtros y
paginación para el registro persistente de potreros. La migración aditiva `0006`
asocia los eventos nuevos de creación y modificación con su potrero; los eventos
anteriores no se reconstruyen ni se modifican retroactivamente. En el formulario
de potreros, el mapa enfoca y destaca el perímetro del predio, muestra la
superficie aún disponible y alerta antes de guardar si el perímetro dibujado
queda fuera del predio o supera esa superficie. Django mantiene las validaciones
del lado del servidor.

## Catálogo y recuperación de cuenta

Registra los cultivos y zonas reales en Django Admin. Solo cultivos activos se
pueden asociar. Si el catálogo está vacío, se explica en el formulario.
`seed_catalog` conserva datos de demostración del proyecto original: **no lo
ejecutes como carga de datos agrícolas oficiales**.

Los productos del catálogo parten en estado **Información no verificada**. El
formulario de ficha no presenta esos datos como autorización ni habilita su uso
en cálculos verificados. Un administrador debe registrar fuente, URL, fecha y
documentación de etiqueta antes de cambiar el estado. No se cargaron dosis ni
autorizaciones SAG ficticias. La verificación es una declaración de catálogo y
requiere que el administrador contraste la etiqueta oficial para el cultivo y
objetivo concretos.

La recuperación de contraseña usa el flujo de Django con token. Localmente el
correo se imprime en la consola; para enviar mensajes reales configura
`EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD` y `DEFAULT_FROM_EMAIL` en `.env`. Esas variables se traducen
al ajuste `MAILERS` de Django 6.1. No guardes credenciales SMTP en Git.

## Centro de decisiones

En **La decisión**, el acceso **Centro de decisiones** reúne semillas, insumos,
disponibilidad y cosecha. Las URLs anteriores (`/calculadora/`, `/cobertura/`,
`/predictor/` y `/asesor/`) siguen activas; las fichas de insumo también se abren
desde Insumos. Los cálculos de cantidades, disponibilidad y cosecha se validan y ejecutan en
`/calculos/ejecutar/` mediante POST JSON autenticado y protegido por CSRF. El
servidor valida el propietario del potrero, la superficie y los parámetros antes
de devolver el resultado; los resultados mostrados en Reporte todavía se guardan
localmente en el navegador, no como historial persistente de SQLite.
Los pasos de configuración permiten ajustar la superficie solo para el cálculo;
no actualizan el terreno. Las dosis y rendimientos son datos del catálogo, no
recomendaciones técnicas. Los cálculos guardados siguen disponibles en **Reporte**
para exportar las categorías PDF que ya admite esa sección (ficha, semillas,
insumos y disponibilidad).

## Pruebas y límites

```powershell
.\.venv\Scripts\python.exe Proyecto/manage.py check
.\.venv\Scripts\python.exe Proyecto/manage.py test core
.\.venv\Scripts\python.exe Proyecto/manage.py makemigrations --check --dry-run
```

La Fase A tiene autenticación y terrenos persistentes. Los módulos B–D existentes
siguen disponibles, pero actividades/historial y calendario aún requieren
persistencia. Los resultados locales se separan por usuario; no equivalen a
historial en SQLite.

Las migraciones `0002` y `0003` amplían el esquema de manera aditiva y conservan
las tablas y perímetros anteriores. El respaldo
previo está en `Proyecto/backups/db-antes-fase-a-2026-10-02.sqlite3` (ignorado por Git).
Los archivos SQLite y pyc que ya estaban versionados no fueron borrados: `.gitignore`
evita nuevas inclusiones, pero no deja de rastrear archivos existentes automáticamente.
