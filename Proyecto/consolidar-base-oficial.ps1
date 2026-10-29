# ============================================================================================
# AgroAsesor - consolida las bases SQLite antiguas en LA unica base oficial (/data/db.sqlite3).
#
# Donde ejecutarlo: PowerShell, DENTRO de la carpeta del proyecto (donde esta docker-compose.yml),
#                   con Docker Desktop encendido:
#
#     powershell -ExecutionPolicy Bypass -File .\consolidar-base-oficial.ps1
#
# Que hace (en este orden, y se detiene si algo falla):
#   1. Reconstruye la imagen y enciende el contenedor (al arrancar hace un respaldo y aplica migraciones).
#   2. Hace un respaldo verificado (integridad + sha256) de la base oficial ANTES de tocarla.
#   3. Muestra el informe de prueba y luego trae a la oficial lo que falta de las 3 bases antiguas.
#      No borra ni modifica nada de lo que la oficial ya tiene. Las cuentas con el mismo usuario pero
#      otro correo se conservan SEPARADAS (no se fusionan personas distintas).
#   4. Verifica: integridad, relaciones, duplicados, y registro por registro que no se perdio nada.
#   5. Deja todo escrito en backups\consolidacion-FECHA.log
# No borra ninguna base antigua. Es seguro repetirlo (no duplica).
# ============================================================================================
# 'Continue': docker escribe su progreso por stderr y no debe contarse como error; los fallos reales se detectan con el codigo de salida.
$ErrorActionPreference = 'Continue'
Set-Location -Path $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot 'backups') | Out-Null
$log = Join-Path $PSScriptRoot ("backups\consolidacion-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))
Start-Transcript -Path $log | Out-Null

function Paso($texto) { Write-Host ""; Write-Host "=== $texto ===" -ForegroundColor Cyan }
function Dk {
    & docker.exe @args
    if ($LASTEXITCODE -ne 0) { throw "Fallo: docker $($args -join ' ') (codigo $LASTEXITCODE)" }
}
function Django {
    Dk exec agroasesor_hugo python manage.py @args
}

try {
    Paso "0. Comprobando Docker y las bases antiguas"
    & docker.exe info *> $null
    if ($LASTEXITCODE -ne 0) { throw "Docker Desktop no esta encendido. Abrelo, espera a que diga 'Running' y vuelve a ejecutar." }
    $origenes = @('1_APLICACION_db.sqlite3', '2_PAGINAHUGO_db.sqlite3', '3_REPO_db.sqlite3')
    foreach ($o in $origenes) {
        $ruta = Join-Path $PSScriptRoot "backups\origenes\$o"
        if (-not (Test-Path $ruta)) { throw "Falta $ruta (son las copias de las bases antiguas)." }
        "{0}  {1}" -f (Get-FileHash $ruta -Algorithm SHA256).Hash, $o
    }

    Paso "1. Reconstruyendo y encendiendo AgroAsesor"
    Dk compose build
    Dk compose up -d
    $listo = $false
    for ($i = 0; $i -lt 40 -and -not $listo; $i++) {
        Start-Sleep -Seconds 3
        & docker.exe exec agroasesor_hugo python manage.py estado_bd *> $null
        if ($LASTEXITCODE -eq 0) { $listo = $true }
    }
    if (-not $listo) { throw "El contenedor no respondio a tiempo. Revisa: docker logs agroasesor_hugo" }

    Paso "2. Estado de la base oficial ANTES de consolidar"
    Django estado_bd
    Paso "3. Respaldo verificado de la oficial (antes de tocarla)"
    Django respaldar_bd --prefijo db-previo-consolidacion --mantener 0

    $archivos = $origenes | ForEach-Object { "/backups/origenes/$_" }
    $equivalencias = 'MAIZ DEMO=Maiz,ZONA DEMO MELIPILLA=Melipilla'

    Paso "4. PRUEBA de consolidacion (no guarda nada)"
    Django consolidar_bd @archivos --equivalencias $equivalencias

    Paso "5. CONSOLIDANDO de verdad en /data/db.sqlite3"
    Django consolidar_bd @archivos --equivalencias $equivalencias --aplicar

    Paso "6. Verificando integridad, relaciones y duplicados"
    Django verificar_bd

    Paso "7. Comprobando registro por registro que no se perdio nada"
    $previo = (Get-ChildItem (Join-Path $PSScriptRoot 'backups') -Filter 'db-previo-consolidacion-*.sqlite3' | Sort-Object LastWriteTime | Select-Object -Last 1).Name
    Django comprobar_consolidacion @archivos "/backups/$previo"

    Paso "8. Estado final de la base oficial"
    Django estado_bd

    Write-Host ""
    Write-Host "LISTO. La consolidacion termino y se verifico. NO se borro ninguna base antigua." -ForegroundColor Green
    Write-Host "Registro guardado en: $log"
} catch {
    Write-Host ""
    Write-Host "SE DETUVO: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "No se borro nada. La base oficial tiene respaldo en la carpeta backups. Registro: $log"
    Stop-Transcript | Out-Null
    exit 1
}
Stop-Transcript | Out-Null
