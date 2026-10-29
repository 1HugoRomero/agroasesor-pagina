# Fase 2 · Integración segura de Flask

## Arquitectura
```
Navegador ──sesión Django──▶ Django  /api/v1/…  ──HTTP interno + firma HMAC──▶ Flask (solo lectura) ──▶ /data/db.sqlite3 (:ro)
```
* **Una sola autenticación**: la de Django (cuentas, contraseñas, sesión, CSRF). Flask no tiene login, ni contraseñas, ni sesiones.
* **Firma**: Django envía `X-AgroAsesor-User/Staff/Timestamp/Signature`. La firma HMAC-SHA256 cubre usuario, rol, hora, método, ruta+consulta y huella del cuerpo; caduca a los 60 s. No sirve para otra ruta, otro usuario ni otro cuerpo.
* **Falla cerrada**: sin clave interna (≥ 32 caracteres) → 503. Las cabeceras `X-AgroAsesor-*` que traiga el navegador se descartan.
* **Solo lectura**: la conexión SQLite se abre con `mode=ro` + `PRAGMA query_only=ON`; en Docker el volumen va con `:ro`. Ninguna operación de escritura está implementada (siguen en 501).
* **Propiedad de los datos**: cada consulta filtra por el usuario firmado. Un recurso ajeno responde igual que uno inexistente (404).
* **Opcional**: sin `AGROASESOR_API_URL`/`AGROASESOR_INTERNAL_SECRET`, `/api/v1/` responde 503 y AgroAsesor funciona como antes.

## Endpoints reales (lectura)
`GET /api/v1/health`, `/openapi.json`, `/usuarios/me`, `/predios`, `/predios/{id}`, `/predios/{id}/potreros`, `/potreros/{id}`, `/cultivos`, `/cultivos/{id}`, `/insumos`, `/insumos/{id}`, `/zonas`, `/calculos` (historial) y los del catálogo. Las superficies salen siempre en ha **y** m² (`1,5 ha (15.000 m²)`).

## Cómo probar
* Flask: `cd backend_flask && pip install -r requirements.txt && pytest`
* Django (incluye integración real con Flask): `docker compose exec agroasesor python manage.py test core.tests_api`
* Docker opcional: ver `docker-compose.api.yml`.

## Límites conocidos
* Servidor de la API = servidor integrado de Flask (red interna, sin puertos publicados). Para producción conviene gunicorn/waitress.
* El contenedor `api` no se ha probado en Docker en esta sesión; sí la API y la puerta de enlace con pruebas automáticas.
* SQLite en modo `:ro` funciona con el modo de diario por defecto de Django; si algún día se activa WAL habrá que revisarlo.
