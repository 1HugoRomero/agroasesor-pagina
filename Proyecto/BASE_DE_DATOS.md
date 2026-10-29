# Base de datos de AgroAsesor — una sola, la oficial

**La base oficial es el archivo SQLite `/data/db.sqlite3` que vive en el volumen persistente de Docker
(`agroasesor_hugo_agroasesor_data`).** Todo lo que se registre en la página (usuarios, predios, potreros,
temporadas, actividades, cálculos) queda ahí, y sobrevive a `docker compose down`, a reconstruir la imagen
y a reiniciar el PC.

## Reglas
1. Se trabaja **siempre** con Docker: `docker compose up -d` y entrar por http://localhost:8000/.
2. No usar `python manage.py runserver` directo: crearía un `db.sqlite3` local distinto (el sistema avisa).
3. **Nunca** ejecutar `docker compose down -v` ni `docker volume rm agroasesor_hugo_agroasesor_data`: borran la base oficial.
4. Los `db.sqlite3` sueltos y todo lo que esté en `backups/` son **copias**, no bases de trabajo.

## Comandos útiles (en PowerShell, dentro de la carpeta del proyecto, con Docker encendido)
| Para qué | Comando |
|---|---|
| Ver qué base se usa y cuánto contiene | `docker exec agroasesor_hugo python manage.py estado_bd` |
| Respaldo ahora (queda en `backups\`) | `docker exec agroasesor_hugo python manage.py respaldar_bd` |
| Probar traer datos de otra base (no guarda nada) | `docker exec agroasesor_hugo python manage.py consolidar_bd /backups/origenes/ARCHIVO.sqlite3` |
| Traerlos de verdad (hace respaldo antes) | el mismo comando agregando `--aplicar` |
| Dejar fuera cuentas de prueba | agregar `--excluir-usuarios usuario1,usuario2` |

Al encender el contenedor se hace un respaldo automático (se conservan los últimos 20) y se muestra el estado en el log.

## Qué se trae y qué no al consolidar
Se copian: usuarios (con su contraseña ya cifrada), agricultor, aceptación de políticas, predios, potreros, historial,
temporadas, actividades y cálculos. El catálogo (cultivos, insumos, zonas) **no** se copia: se carga desde `data/*.csv`.
Lo que ya existe en la oficial no se modifica ni se borra.


## Consolidación de las bases antiguas (un solo paso)
En PowerShell, dentro de la carpeta del proyecto y con Docker Desktop encendido:

    powershell -ExecutionPolicy Bypass -File .\consolidar-base-oficial.ps1

Reconstruye el contenedor, hace un respaldo verificado, trae lo que falta de las bases antiguas (`backups\origenes\`),
y comprueba que no se perdió nada. Deja el registro en `backups\consolidacion-FECHA.log`. Es seguro repetirlo.

Reglas de identidad: una cuenta se considera la misma solo si coinciden usuario **y** correo. Mismo usuario con otro
correo se conserva separada (`usuario_2`) y se informa. Distinto usuario con el mismo correo nunca se une.

Comandos de revisión: `verificar_bd` (integridad, huérfanos, duplicados, totales) y
`comprobar_consolidacion ARCHIVOS` (cada registro de las bases antiguas existe en la oficial).
