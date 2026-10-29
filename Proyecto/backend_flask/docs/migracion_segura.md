# Hoja de ruta: Django -> API Flask

1. **Inventario**: revisar modelos, migraciones, URLs, vistas, tests y base de datos Django actual.
2. **Respaldo**: obtener copia verificada del SQLite oficial y de sus archivos relacionados.
3. **Contrato**: validar las rutas de `openapi.yaml` con los casos de uso y rúbrica del proyecto.
4. **Prueba aislada**: trabajar con una copia de datos, nunca con la base oficial durante el prototipo.
5. **Persistencia**: diseñar modelos SQLAlchemy/Alembic después de mapear relaciones y claves actuales.
6. **Usuarios**: resolver compatibilidad de hashes de contraseñas y sesiones Django sin reiniciar cuentas.
7. **Módulos**: migrar primero catálogos y consultas; luego predios/potreros, cálculos, historial, etc.
8. **Seguridad**: autenticación, autorización por propietario, CSRF o tokens según cliente, validaciones.
9. **Frontend**: adaptar vistas para consumir JSON sin romper diseño y flujo actuales.
10. **Corte controlado**: detener escrituras Django, respaldar, validar conteos/integridad y habilitar Flask.
11. **Documentación académica**: actualizar DAS/ATAM y diagramas, que hoy describen un monolito Django.

## Prohibiciones para esta fase

- No ejecutar `db.create_all()` sobre el SQLite oficial.
- No conectar Flask y Django como escritores concurrentes de ese SQLite.
- No eliminar ni renombrar tablas por intuición.
- No copiar hashes de contraseñas a un sistema incompatible sin un plan comprobado.
- No asumir que una ruta `501` implementa su funcionalidad.
