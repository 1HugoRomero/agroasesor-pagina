# Fase 1 · Auditoría (28-oct-2026)

## Estado encontrado
| Área | Estado real |
|---|---|
| Base de datos | Una sola base oficial `/data/db.sqlite3` (consolidada el 26-oct). 23 usuarios, 16 predios, 11 potreros, 3 temporadas, 5 cálculos, 51 cultivos, 1 zona, 0 insumos, 0 actividades. Integridad OK, 0 huérfanos. |
| Django | Funciona: cuentas, predios, potreros, mapa Leaflet, temporadas, calculadora/cobertura/predictor/decisiones/calendario/actividades/reportes/panel admin, recuperación de contraseña (`cuenta/recuperar/…`). 276 pruebas previas en verde. |
| Flask (borrador) | 46 operaciones definidas en OpenAPI: **7 funcionan** (`/health` + 6 del catálogo con fuentes) y **39 devuelven 501**. No tenía acceso a datos, ni autenticación, ni conexión con Django. |
| Catálogo agrícola | YAML con productos/referencias y fuentes. Referencias de siembra verificadas contra páginas INIA solo en parte (arroz, plan predial, IPA Quilamapu). Páginas ODEPA/SAG y la ficha INIA de trigo invierno **no se pudieron verificar**: quedan marcadas como sin verificar. |
| Inventario/consumo | No existe (las tablas de inventario se retiraron antes). Reintroducirlo requiere diseño y migración: es Fase 5. |
| Comparador de cultivos | No existe como página. Fase 4. |
| Diseño de la imagen | Aún no adoptado en Django. Fase 3 en adelante. |
| Recuperación de contraseña | Ya existe con tokens de un solo uso de Django y caducidad. **Falta revisar**: límite de intentos, configuración de correo por entorno (ahora con `.env.example`), respuesta idéntica exista o no el correo. Fase 6. |

## Riesgos detectados
1. Dos sistemas de autenticación serían un error: se decidió que **Django es el único**.
2. Dos escritores sobre el mismo SQLite: la API Flask es de **solo lectura** hasta una migración autorizada.
3. Datos sin verificar mostrados como si fueran oficiales: la API marca cada dato como `verificado` / `sin_verificar` y no inventa precios ni presentaciones comerciales.
