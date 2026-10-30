# Auditoría de AgroAsesor y plan de cierre

Fecha: 2 de octubre de 2026. El diagnóstico se realizó antes de editar código.

## Alcance y evidencia

Se revisaron modelos, vistas, configuración, URLs, migraciones, comandos, pruebas,
plantillas, estilos, scripts, manifiesto de dependencias, estado Git y esquema de
SQLite. `diagrama.png` coincide con los cuatro modelos originales y las tablas de
autenticación Django. No hay un documento de requisitos adicional en el repositorio;
se utiliza la lista de 22 funcionalidades aportada por el usuario.

Arquitectura conservada: Python, Django 6.1.1 monolítico, Django Templates, HTML/CSS,
JavaScript, ORM Django y SQLite. El diseño existente usa CSS propio, sin Bootstrap
cargado. No se incorporó un framework frontend ni se sustituyó la base de datos.

La aplicación está en `Proyecto/`: configuración en `AgroAsesor/`, lógica en `core/`,
plantillas en `core/templates/` y recursos en `core/static/`. Las URLs originales
siguen disponibles: `/`, `/login/`, `/logout/`, `/predios/`, `/calculadora/`,
`/cobertura/`, `/asesor/`, `/predictor/`, `/calendario/`, `/busqueda/`, `/reportes/`,
`/panel-admin/` y `/admin/`.

## Estado previo por requisito

| Nº | Funcionalidad | Estado previo | Evidencia y brecha |
|---|---|---|---|
| 1 | Registro agricultor | PARCIAL | Formulario; cuentas y contraseñas en sesión, sin perfil ORM. |
| 2 | Inicio/cierre sesión | PARCIAL | Credenciales demo y sesión manual; no auth Django. |
| 3 | Administración restringida | PARCIAL | Django Admin tiene permisos; el panel personalizado permite entrar como admin sin credenciales. |
| 4 | Predios | PARCIAL | Formulario y almacenamiento local; sin propietario ni tabla. |
| 5 | Google Maps | NO IMPLEMENTADO | Leaflet, OSM y Esri; sin configuración de Google. |
| 6 | Ubicar, dibujar, medir | PARCIAL | Leaflet/Turf; geometría y superficie guardadas en localStorage, sin validación servidor. |
| 7 | Asociar cultivos | PARCIAL | Nombre de cultivo en objetos JavaScript; sin relación ORM. |
| 8 | Cálculos agrícolas | PARCIAL | Multiplicación superficie × dosis en JS; sin registro persistente. |
| 9 | Semillas | PARCIAL | JS lee densidades del catálogo o demo y usa valor predeterminado sin fuente. |
| 10 | Actividades | PARCIAL | Notas locales sin relación confiable a un terreno. |
| 11 | Historial por terreno | NO IMPLEMENTADO | No existe modelo ni consulta histórica por potrero. |
| 12 | Recomendar insumos | PARCIAL | Asistente JS; el payload ORM no contiene problema agrícola. |
| 13 | Ficha técnica y fuente | PARCIAL | Pantalla demo; botón muestra alert; modelo carece de fuente, seguridad y aplicación. |
| 14 | Dosis máxima | NO IMPLEMENTADO | No existe campo de dosis máxima ni validación. |
| 15 | Vigencia | IMPLEMENTADO (base) | Campo `Insumo.vigente`, filtro ORM y Django Admin; sin fechas ni trazabilidad de vigencia. |
| 16 | Rendimiento | PARCIAL | Tasa por cultivo × superficie; zona no determina la estimación, sin fuentes. |
| 17 | Calendario | PARCIAL | Meses/ciclos demo en JS; sin modelo persistente. |
| 18 | Cobertura | PARCIAL | Fórmula y grilla JS; sin cálculo persistente ni aplicación espacial al perímetro real. |
| 19 | Búsqueda y filtros | PARCIAL | Filtrado JS de catálogos y objetos locales; sin búsqueda completa en ORM. |
| 20 | PDF | PARCIAL | jsPDF exporta resultados locales; no historial persistente ni fuentes confiables. |
| 21 | CRUD catálogos | PARCIAL | Cultivo, Zona, TipoInsumo e Insumo sí tienen CRUD Django Admin; falta calendario. Panel custom no guarda catálogos en DB. |
| 22 | Dashboard admin | PARCIAL | Métricas estáticas de demo. |

### ERRORES / DEUDA TÉCNICA

- Escalamiento de privilegios mediante `/entrar-admin/` (3).
- Restablecimiento sin demostrar propiedad del correo (2).
- Contraseñas claras en sesión y cuentas no persistentes (1–2).
- Datos locales compartidos por navegador, sin aislamiento de propietario (4, 7, 10–11).
- Esquema reducido a cuatro modelos: `Zona`, `Cultivo`, `TipoInsumo`, `Insumo`.
- En la inspección inicial, usuarios y catálogos estaban vacíos. No se importaron datos demo.
- Las pruebas iniciales esperaban comportamientos inseguros como el acceso admin directo.
- `django_extensions` figuraba en settings sin declararse en requirements; se retiró esa dependencia opcional.
- Secret key fija, DEBUG fijo, ruta de static inexistente y archivos SQLite/pyc versionados.
- Interpolación de nombres en `innerHTML`; se agregó escape en los puntos de integración modificados.
- Los scripts de módulos B–D conservan deuda de demo, datos sin fuente y persistencia local.
- El comando `seed_catalog` contiene valores demostrativos, no datos oficiales validados.

## Reutilización y archivos de Fase A

Se conservaron los cuatro modelos originales y la migración `0001`; también el
layout, estilos, módulos de cálculo/exportación y rutas existentes. Se amplió el
esquema usando el `User` de Django y relaciones nuevas, sin reemplazar auth tables.

| Archivos | Cambio |
|---|---|
| `.gitignore`, `Proyecto/.env.example`, `.env` local | Variables y exclusión de secretos, backups y archivos generados. |
| `Proyecto/requirements.txt`, `AgroAsesor/settings.py` | dotenv, clave Maps, seguridad/configuración por entorno y mailers de Django 6.1. |
| `core/models.py`, `forms.py`, `auth.py`, `geometry.py` | Perfil agricultor, predio con propietario, potrero/cultivo, validaciones y área esférica. |
| `core/migrations/0002_agricultor_predio_potrero_and_more.py` | Tablas nuevas y restricciones positivas, migración aditiva. |
| `core/views.py`, `AgroAsesor/urls.py` | Auth real, permisos, formularios protegidos, recuperación con tokens y consultas por propietario. |
| `core/templates/body.html`, `login.html`, `registration/` | Navegación, logout POST con CSRF y recuperación segura. |
| `core/templates/predios.html`, `terreno_form.html`, `static/js/predios-map.js`, `static/css/predios.css` | Listado real, altas/edición, Google Maps y formulario manual sin clave. |
| `core/catalog.py`, `static/js/services.js` | Catálogo vacío honesto, terrenos reales desde ORM y resultados locales separados por usuario. |
| `templates/dashboard.html`, `static/js/dashboard.js` | Terrenos reales, escape HTML y eliminación del crecimiento ficticio de superficie. |
| `static/js/calculadora.js`, `cobertura.js`, `busqueda.js` | Escape de nombres reales; eliminación de dosis automática de 25 cuando no hay dato. |
| `core/admin.py`, `templates/admin.html` | Registro de modelos nuevos y panel con conteos reales y enlaces al CRUD existente. |
| `core/tests/` | Pruebas de seguridad y flujo completo; conserva regresión del contrato de catálogo. |

## Resultado de Fase A

- Registro persistente de agricultor con RUT validado y contraseña hasheada.
- Login/logout Django, recuperación con token firmado de un solo uso. SMTP requiere configuración; local usa consola.
- Restricción del panel por `is_staff`; cada cambio en Django Admin exige permisos del modelo.
- Alta/edición de predio y potrero, aislamiento por propietario y consulta tras nueva sesión.
- Cultivo activo asociado mediante FK; variedad y fechas opcionales.
- Ubicación manual o mapa, polígonos editables, medición m²/ha y persistencia de vértices.
- Área recalculada por backend en esfera de radio 6378137 m. Rechazo de polígonos cruzados, degenerados, fuera de rango o con más de 200 vértices.
- Suma de superficies de potreros limitada por superficie del predio; no se permite reducir un predio por debajo de sus potreros.
- No se importan automáticamente terrenos ni cuentas de la demo. Los registros locales originales no son equivalentes a registros productivos.
- Dashboard y módulos existentes reciben los terrenos reales del usuario. Actividades persistentes siguen pendientes de Fase B.
- Panel admin usa conteos ORM. No se afirma tener métricas de consultas que todavía no existen.

Los requisitos 1–4 y 7 quedan implementados en este alcance. 5–6 tienen integración
implementada y validación local, pendiente de prueba contra Google con clave real.
La geometría es estimativa; no valida superposición entre potreros ni contención en
un perímetro de predio, porque el predio registra superficie total y sus potreros
registran el perímetro. División geométrica y eliminación no se ofrecen como acciones simuladas.

## Verificación

- `manage.py check`: sin incidencias.
- `manage.py makemigrations --check --dry-run`: sin cambios pendientes.
- Migraciones ejecutadas después de crear respaldo SQLite en `Proyecto/backups/`.
- 27 pruebas Django: registro, sesiones, recuperación, permisos, CSRF, aislamiento,
  superficies, fechas, geometría, clave serializada, ausencia de API key y rutas previas.
- Sintaxis de los scripts JavaScript comprobada con Node.
- Flujo real de navegador en SQLite separada de QA: login, alta de predio, alta de
  potrero, cultivo y visualización de confirmación. Sin errores JS en ese flujo.
- No se verifica carga/dibujo contra el servicio Google sin una clave configurada.

## Plan concreto siguiente

1. **Fase B:** añadir modelos `CalculoAgricola` y `ActividadAgricola`, formularios,
   migración aditiva, vistas por propietario, URLs de historial por potrero y
   adaptar calculadora/dashboard. Guardar entradas, resultado, unidad, fecha y
   relación con potrero. Validar dosis/densidad y área; registrar semillas como
   cálculo con datos aportados o respaldados por fuente.
2. **Fase C:** extender Insumo con fuente verificable, ficha, aplicación,
   seguridad, dosis máxima/unidad y vigencia temporal; modelar problemas y
   relaciones por cultivo. Adaptar asesor y cobertura con backend, persistencia
   y alertas; no construir recomendaciones desde cifras sin fuente.
3. **Fase D:** modelar calendario y referencias de rendimiento por cultivo/zona,
   filtros ORM, reportes PDF desde cálculos persistidos, CRUD de calendario y
   métricas basadas en eventos reales.

Después de cada fase: revisar migración, pruebas de permisos/validación y flujo
de navegador, documentar límites y actualizar esta matriz. No cambiar el stack.
2
## Integración de calendario, predios, decisiones y ficha de insumo (11 de octubre de 2026)

Se revisó el código real antes de editar. No se reconstruyó la aplicación, no se
borraron predios ni potreros y todas las migraciones son aditivas.

### Causas encontradas

- `models.py` tenía el campo `ReferenciaAgronomica.anio_referencia` sin migración: las
  85 pruebas fallaban. Se creó `0012_referencia_anio`.
- La base `db.sqlite3` solo tenía aplicadas las migraciones hasta la `0007`; calendario y
  centro de decisiones consultaban tablas inexistentes (0008–0011).
- Selectores vacíos del centro de decisiones: **catálogo vacío** (0 cultivos, zonas, tipos e
  insumos) y, además, un error de integración: las semillas registradas como `Insumo`
  de tipo «Semilla» nunca llegaban a la calculadora (solo se leía la densidad del cultivo).
  Los respaldos anteriores tampoco contienen catálogo, por lo que no hay datos que importar.
- La asignación de cultivo desde el formulario del potrero sobrescribía el cultivo sin
  historial; el panel del mapa no ofrecía asignar cultivo y dejaba de funcionar sin Leaflet.

### Cambios por fase

| Fase | Archivos | Resultado |
|---|---|---|
| Calendario | `views.calendario`, `agronomy.py`, `calendario.html/js/css` | Filtros reales sin recarga (zona, cultivo, variedad; el año consulta al servidor), 12 meses con leyenda completa, ciclos entre años, fila separada «Tu registro», ficha en 7 pestañas (General, Siembra, Desarrollo, Cosecha, Sanidad, Productos, Fuentes), evaluadores con 4 estados, días transcurridos (años bisiestos), factores no evaluados y guardado de fechas en una temporada real. |
| Predios | `seasons.py`, `views.potrero_assign_crop/potrero_api`, `predios.html`, `predios-map.js`, `predios.css` | Botón «Asignar/Cambiar cultivo» con modal, catálogo Django, temporada agrícola, estado y observaciones; cada cambio crea una `TemporadaCultivo` y conserva las anteriores; panel derecho con acciones e historial; etiquetas de potreros según zoom; selección sincronizada por URL; funciona sin mapa. |
| Decisiones | `views.calculate`, `catalog.py`, `decisiones.html`, `decisiones.js`, `decisiones.css` | Cuatro herramientas (Cuánto llevar —semillas / fertilizantes y otros—, Si alcanza, Cosecha, Ficha de insumo), indicadores reales, distinción catálogo/inventario, resultados a la derecha, cálculo avanzado conectado a `seed_population`, cálculo por nutriente, sacos solo con presentación registrada, procedencia «documentada» o «simulación», PDF. |
| Ficha de insumo | `decisiones.js` | Cultivo → problema (plaga, enfermedad, maleza, nutricional) → tipo → ficha, panel contextual, PDF, envío a «Cuánto llevar» sin asumir dosis no verificadas. |
| Catálogo | `importar_catalogo.py`, migración `0013` | Importación JSON validada, atómica y en modo simulación por defecto; plantilla vacía. Nuevos campos: tipo/síntomas/fuente del problema, modo de aplicación del insumo y rótulo de temporada. |

### Pendiente

- El catálogo sigue vacío: hay que cargar zonas, cultivos, referencias e insumos con
  fuentes oficiales (INIA, SAG, ODEPA, fichas técnicas). Sin eso las pantallas muestran
  estados vacíos honestos.
- La autorización de plaguicidas no se consulta en línea al SAG; depende de lo registrado.
- No se ofrece eliminar predios o potreros: su historial está protegido (`PROTECT`).

## Módulos de la barra lateral a nivel profesional (11 de octubre de 2026)

- **Planificar actividad** (`/actividades/`, `/actividades/nueva/`): formulario en 4 secciones con tipo de labor, temporada, prioridad, responsable, fecha realizada, condiciones y registro de aplicación (producto, objetivo, dosis, superficie y cantidad total). Pautas de Buenas Prácticas Agrícolas por labor, alerta de carencia frente a la cosecha registrada, listado con indicadores, filtros, vista de calendario mensual y plan de temporada a partir de las fechas del potrero. Migración aditiva `0014`.
- **Calcular insumos**: lleva directo a «Cuánto llevar › Fertilizantes y otros insumos»; los resultados se pueden planificar como actividad.
- **Consultar productos** (`/productos/`): catálogo con categorías, búsqueda y filtros; ficha técnica imprimible por producto con datos faltantes explícitos.
- **Generar reporte** (`/reportes/`): resumen del predio, cuaderno de campo, historial de cultivos y cálculos; impresión/PDF y CSV.
- Las rutas `/calculadora/`, `/cobertura/`, `/predictor/` y `/asesor/` redirigen a las herramientas integradas conservando sus parámetros.
- Todas las páginas usan un contenedor centrado común (máx. 1520 px) y paneles que ocupan el ancho disponible.
