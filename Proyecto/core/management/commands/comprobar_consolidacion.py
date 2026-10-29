"""Comprueba, registro por registro, que TODO lo de otras bases SQLite está en la base oficial.

Uso (Docker):
    docker exec agroasesor_hugo python manage.py comprobar_consolidacion /backups/origenes/1_X.sqlite3 /backups/origenes/2_Y.sqlite3

Es una revisión independiente de «consolidar_bd»: para cada usuario, agricultor, predio, potrero, historial,
temporada, actividad y cálculo de la otra base busca su equivalente en la oficial comparando TODOS sus datos
(contraseña cifrada, superficies, coordenadas, polígonos, fechas, entradas y resultados de cálculos).
No modifica nada. Termina con error si falta algún registro.
"""
import re
import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from core import dbutils
from core.management.commands.consolidar_bd import PLAN

# Claves foráneas al catálogo: se enlazan por nombre (y a veces por equivalencia), por eso no se comparan como número.
CATALOGO_FK = {'cultivo_id', 'zona_id', 'insumo_id'}


class Command(BaseCommand):
    help = 'Verifica que cada registro de las otras bases exista en la base oficial (no modifica nada).'

    def add_arguments(self, parser):
        parser.add_argument('origenes', nargs='+', help='Archivos .sqlite3 a comprobar.')

    def _cols_destino(self, tabla):
        with connection.cursor() as cur:
            cur.execute(f'PRAGMA table_info("{tabla}")')
            return [f[1] for f in cur.fetchall()]

    def _buscar(self, tabla, condiciones, username_base, fila):
        """Id del registro de la oficial que cumple las condiciones (None si no hay)."""
        partes, valores = [], []
        for c, v in condiciones.items():
            if tabla == 'auth_user' and c == 'email':
                partes.append('lower("email") = lower(%s)')
                valores.append(v or '')
            else:
                partes.append(f'"{c}" IS %s')
                valores.append(v)
        sql = f'SELECT id{", username" if tabla == "auth_user" else ""} FROM "{tabla}" WHERE ' + (' AND '.join(partes) or '1=1')
        with connection.cursor() as cur:
            cur.execute(sql, valores)
            candidatos = cur.fetchall()
        if tabla == 'auth_user':
            patron = re.compile(rf'^{re.escape(username_base)}(_\d+)?$')
            candidatos = [c for c in candidatos if patron.match(c[1])]
        return candidatos[0][0] if candidatos else None

    def handle(self, *args, **options):
        destino = dbutils.ruta_bd()
        total_faltan = 0
        self.stdout.write(f'Base oficial: {destino}')
        for texto in options['origenes']:
            ruta = Path(texto)
            if not ruta.is_file():
                raise CommandError(f'No existe el archivo: {texto}')
            if ruta.resolve() == destino:
                raise CommandError('Indica una base distinta de la oficial.')
            src = sqlite3.connect(f'file:{ruta}?mode=ro', uri=True)
            src.row_factory = sqlite3.Row
            self.stdout.write(self.style.MIGRATE_HEADING(f'\n--- {ruta.name} ---'))
            mapas = {}
            for tabla, clave, fks in PLAN:
                mapas[tabla] = {}
                existe = src.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabla,)).fetchone()
                if not existe:
                    continue
                cols_dest = self._cols_destino(tabla)
                cols_src = [f[1] for f in src.execute(f'PRAGMA table_info("{tabla}")')]
                comunes = [c for c in cols_src if c in cols_dest and c != 'id' and c not in CATALOGO_FK]
                filas = list(src.execute(f'SELECT * FROM "{tabla}" ORDER BY id'))
                faltan, distintos = [], []
                for fila in filas:
                    datos, sin_padre = {}, False
                    for c in comunes:
                        if c in fks:
                            if fila[c] is None:
                                datos[c] = None
                                continue
                            nuevo_id = mapas.get(fks[c][0], {}).get(fila[c])
                            if nuevo_id is None:
                                sin_padre = True
                                break
                            datos[c] = nuevo_id
                        else:
                            datos[c] = fila[c]
                    if sin_padre:
                        faltan.append((fila['id'], 'su registro padre no se encontró'))
                        continue
                    # 1) idéntico en todos los datos; 2) misma identidad natural (la oficial manda, se informa si difiere)
                    estricto = {c: v for c, v in datos.items() if not (tabla == 'auth_user' and c == 'username')}
                    encontrado = self._buscar(tabla, estricto, datos.get('username') if tabla == 'auth_user' else None, fila)
                    if encontrado is None:
                        natural = {'email': datos.get('email')} if tabla == 'auth_user' else (
                            {c: datos[c] for c in clave} if clave else None
                        )
                        if natural:
                            encontrado = self._buscar(tabla, natural, datos.get('username') if tabla == 'auth_user' else None, fila)
                            if encontrado is not None:
                                distintos.append(fila['id'])
                    if encontrado is not None:
                        mapas[tabla][fila['id']] = encontrado
                    else:
                        faltan.append((fila['id'], 'no se encontró con los mismos datos'))
                nombre = tabla.replace('core_', '')
                nota = f' ({len(distintos)} ya existían en la oficial con datos algo distintos: se conservó el de la oficial)' if distintos else ''
                if faltan:
                    self.stdout.write(self.style.ERROR(f'  {nombre:<24}{len(filas) - len(faltan):>3} de {len(filas):>3} encontrados · FALTAN {len(faltan)}'))
                    for ident, motivo in faltan[:10]:
                        self.stdout.write(self.style.ERROR(f'      #{ident}: {motivo}'))
                else:
                    self.stdout.write(f'  {nombre:<24}{len(filas):>3} de {len(filas):>3} encontrados{nota}')
                total_faltan += len(faltan)
            src.close()
        self.stdout.write('')
        if total_faltan:
            raise CommandError(f'Faltan {total_faltan} registros en la base oficial. NO borres las bases antiguas.')
        self.stdout.write(self.style.SUCCESS('Comprobación correcta: todos los registros de las bases antiguas están en la oficial. No se perdió nada.'))
