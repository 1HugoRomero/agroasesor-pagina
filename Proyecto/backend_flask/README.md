# AgroAsesor API Flask · Borrador v0.2 con catálogo agrícola

**Alcance real:** El módulo **Catálogo** funciona sobre un archivo YAML local con fuentes institucionales SAG, INIA y ODEPA. Tiene filtros, detalle, categorías, fuentes, referencias de siembra, calculadora de sacos y una página de demostración. **No** es una migración completa de Django ni un ecommerce.

## Instalación Windows (PowerShell)

Copia `backend_flask/` en la raíz de tu proyecto AgroAsesor **sin borrar Django ni mover la base oficial**.

```powershell
cd backend_flask
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe run.py
```

Abre la demostración: **http://127.0.0.1:5050/catalogo**

API:

- `GET /api/v1/health`
- `GET /api/v1/catalogo/categorias`
- `GET /api/v1/catalogo/productos?categoria=repelentes&q=bird`
- `GET /api/v1/catalogo/productos/fungisei`
- `GET /api/v1/catalogo/fuentes`
- `GET /api/v1/catalogo/referencias-siembra`
- `POST /api/v1/catalogo/calcular-sacos`

Ejemplo para PowerShell:

```powershell
$datos = @{ referencia_id='trigo-invierno'; superficie_ha=1.5; peso_saco_kg=25; dosis_kg_ha=180 } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:5050/api/v1/catalogo/calcular-sacos -Method POST -ContentType 'application/json' -Body $datos
```

Ejemplo: 270 kg de semilla y 11 sacos hipotéticos de 25 kg. Opcionalmente, puedes ingresar un precio por saco para estimar el costo; no proviene de ODEPA ni de una tienda. El **peso del saco es elegido por el usuario**, no es una presentación comercial confirmada.

## Qué contiene el catálogo

- **9 categorías**: semillas, fertilizantes, bioestimulantes, herbicidas, fungicidas, insecticidas/acaricidas, repelentes, enmiendas y envases.
- **13 fichas**: 8 categorías/referencias genéricas y 5 productos con etiquetas publicadas por SAG.
- **15 fuentes institucionales** con URL y metadatos, consultadas el 28/10/2026.
- **3 referencias técnicas INIA** contextualizadas para calcular sacos.
- **Interfaz HTML/CSS/JS de demostración** en `/catalogo`, sin alterar la interfaz Django.
- **Pruebas de API**, contratos OpenAPI y documentación de procedencia.

## Qué NO contiene

- Ningún precio, stock o formato comercial verificado, ni datos de tiendas.
- Ningún sello institucional ni afirmación de aval de SAG, INIA u ODEPA.
- Cotejo automatizado de autorización vigente por producto: **pendiente**.
- Recomendaciones de dosificación de plaguicidas, compatibilidad o mezclas.
- Usuarios, predios, potreros, cálculos originales o predicciones conectados a Django: las rutas anteriores siguen con HTTP 501.
- Escritura o conexión a la base oficial `db.sqlite3`.

## Documentación

- `docs/catalogo_fuentes_oficiales.md`: fuentes, criterios y pasos para catálogo comercial real.
- `openapi.yaml`: contrato actualizado de endpoints.
- `data/catalogo_agricola.yaml`: información y procedencia; modificar solo tras validación editorial.

## Docker separado

```powershell
docker compose -f docker-compose.flask.yml up --build
```

Escucha en `127.0.0.1:5050`. **No monta la base oficial**. Detener con `docker compose -f docker-compose.flask.yml down`.

**Importante:** para producción aún faltan autenticación, autorización, auditoría, sincronización de registros oficiales, integración de base de datos y pruebas de seguridad. No publicar el catálogo como una certificación del SAG.

## Integridad local

```powershell
.\.venv\Scripts\python.exe scripts\verificar_integridad_catalogo.py
```

Comprueba SHA-256 del YAML entregado. **No** constituye sello de autenticidad de SAG, INIA u ODEPA.
