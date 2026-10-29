# Arquitectura propuesta (NO implementada en producción)

```text
Interfaz web de AgroAsesor
         |
         | HTTP + JSON
         v
Flask /api/v1 (blueprints)
         |
         +--> Seguridad / autorización (pendiente)
         +--> Services: geometría, siembra, insumos, predicción (pendiente)
         +--> Models: ORM y migraciones (pendiente)
         |
         v
Base de datos única oficial (solo después de migración y pruebas)
```

## Decisiones de diseño

- **API-first**: primero contratos y rutas, después implementación y conexión del frontend.
- **Versionado**: todas las rutas nuevas comienzan por `/api/v1`.
- **Blueprints**: un módulo por área funcional.
- **Lógica desacoplada**: mover reglas agrícolas a `services/` sin depender de vistas Django.
- **Datos con trazabilidad**: los YAML de referencia deben citar fuente, fecha y unidades.
- **Una base oficial al final**: evitar dos procesos que escriban simultáneamente el mismo SQLite.
- **Migración controlada**: no alterar ni borrar cuentas, contraseñas, predios, potreros o historiales.

## Reglas para geometría y superficies

- Guardar geometría validada, idealmente en un formato bien documentado como GeoJSON.
- Confirmar explícitamente el perímetro antes de persistirlo.
- Calcular superficie con metodología apropiada para coordenadas geográficas.
- Exponer `superficie_m2` y `superficie_ha`, con conversión 1 ha = 10.000 m².
- Mantener historial de modificaciones de predios y potreros.
- La precisión, topología y método de medición quedan por definir con el código real.

## Estado real de este paquete

Solo funciona `/api/v1/health`. Las demás rutas responden **501**.
No hay autenticación, ORM, cálculos, predicción, administración ni conexión a SQLite.
