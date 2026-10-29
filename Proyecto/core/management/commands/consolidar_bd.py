"""Trae a la base OFICIAL los datos que otras bases SQLite tengan y la oficial no.

Uso (Docker), siempre primero en modo prueba:

    docker exec agroasesor_hugo python manage.py consolidar_bd /backups/otra.sqlite3
    docker exec agroasesor_hugo python manage.py consolidar_bd /backups/otra.sqlite3 --aplicar

Qué hace
- Copia usuarios, datos de agricultor, predios, potreros, historial, temporadas, actividades y
  cálculos guardados.
- NO copia el catálogo (cultivos, insumos, zonas, problemas…): ese se carga desde data/*.csv.
  Los datos copiados se enlazan al cultivo/zona/insumo de la oficial que tenga el mismo nombre.
- Nunca borra ni modifica nada de la base oficial: lo que ya existe se deja tal cual.
- Cuentas: dos usuarios con el mismo nombre de usuario pero correo distinto se consideran PERSONAS DISTINTAS: no se
  fusionan; la segunda se conserva con otro nombre de usuario (por ejemplo «nombre_2») y se informa. Cuentas con
  nombres de usuario distintos nunca se unen, aunque compartan correo.
- --equivalencias «A=B,C=D»: enlaza un cultivo/zona de la otra base con uno de la oficial que tenga otro nombre
  (sirve para pasar datos de prueba «MAIZ DEMO» al cultivo real «Maíz» sin copiar el cultivo de prueba).
- En modo prueba (por defecto) no se guarda nada; solo muestra el informe.
- Con --aplicar hace antes un respaldo completo de la oficial.
"""
import sqlite3
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, connection, transaction

from core import dbutils

def _plano(texto):
    """Minúsculas y sin tildes, para comparar nombres sin depender de la codificación de la consola."""
    return ''.join(c for c in unicodedata.normalize('NFD', texto or '') if unicodedata.category(c) != 'Mn').strip().lower()


# (tabla, columnas que identifican un registro repetido [None = toda la fila], claves foráneas {col: (tabla_destino, obligatoria)})
PLAN = [
    ('auth_user', ['username'], {}),
    ('core_agricultor', ['user_id'], {'user_id': ('auth_user', True)}),
    ('core_aceptacionpoliticas', ['usuario_id', 'version'], {'usuario_id': ('auth_user', True)}),
    ('core_predio', ['propietario_id', 'nombre'], {
        'propietario_id': ('auth_user', True),
        'zona_id': ('core_zona', False),
    }),
    ('core_potrero', ['predio_id', 'nombre'], {
        'predio_id': ('core_predio', True),
        'cultivo_id': ('core_cultivo', False),
    }),
    ('core_prediohistorial', None, {
        'predio_id': ('core_predio', True),
        'usuario_id': ('auth_user', False),
        'potrero_id': ('core_potrero', False),
    }),
    ('core_temporadacultivo', ['potrero_id', 'cultivo_id', 'temporada_agricola', 'variedad'], {
        'potrero_id': ('core_potrero', True),
        'cultivo_id': ('core_cultivo', True),
    }),
    ('core_actividadagricola', ['potrero_id', 'usuario_id', 'nombre', 'tipo', 'fecha_programada'], {
        'potrero_id': ('core_potrero', True),
        'usuario_id': ('auth_user', True),
        'insumo_id': ('core_insumo', False),
        'temporada_id': ('core_temporadacultivo', False),
    }),
    ('core_calculoagricola', None, {
        'potrero_id': ('core_potrero', True),
        'usuario_id': ('auth_user', True),
    }),
]

# Catálogo: se enlaza por nombre con lo que ya tiene la base oficial.
CATALOGO = ['core_cultivo', 'core_zona', 'core_insumo']
# Tablas de funciones retiradas: si traen datos solo se avisa.
RETIRADAS = ['core_existenciainsumo', 'core_movimientobodega']


class Command(BaseCommand):
    help = 'Trae a la base oficial los datos de usuarios y trabajo de otras bases SQLite (modo prueba por defecto).'

    def add_arguments(self, parser):
        parser.add_argument('origenes', nargs='+', help='Archivos .sqlite3 de donde traer datos.')
        parser.add_argument('--aplicar', action='store_true', help='Guarda los cambios (sin esto solo se muestra el informe).')
        parser.add_argument(
            '--excluir-usuarios', default='',
            help='Nombres de usuario (separados por coma) que NO se traen, junto con todo lo que les pertenece.',
        )
        parser.add_argument(
            '--equivalencias', default='',
            help='Pares «nombre en la otra base=nombre en la oficial» para cultivos y zonas, separados por coma.',
        )
        parser.add_argument(
            '--copiar-catalogo-faltante', action='store_true',
            help='Si un cultivo o zona de la otra base no existe en la oficial, lo crea (solo nombre y campos básicos).',
        )

    # ------------------------------------------------------------------ utilidades
    def _columnas_destino(self, tabla):
        with connection.cursor() as cur:
            cur.execute(f'PRAGMA table_info("{tabla}")')
            return [fila[1] for fila in cur.fetchall()]

    def _columnas_origen(self, src, tabla):
        return [fila[1] for fila in src.execute(f'PRAGMA table_info("{tabla}")')]

    def _tabla_existe(self, src, tabla):
        return bool(src.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabla,)).fetchone())

    def _buscar(self, tabla, clave, datos):
        condicion = ' AND '.join(f'"{c}" IS %s' for c in clave)
        with connection.cursor() as cur:
            cur.execute(f'SELECT id FROM "{tabla}" WHERE {condicion} LIMIT 1', [datos[c] for c in clave])
            fila = cur.fetchone()
        return fila[0] if fila else None

    def _insertar(self, tabla, datos):
        columnas = list(datos)
        marcadores = ', '.join(['%s'] * len(columnas))
        nombres = ', '.join(f'"{c}"' for c in columnas)
        with connection.cursor() as cur:
            cur.execute(f'INSERT INTO "{tabla}" ({nombres}) VALUES ({marcadores})', [datos[c] for c in columnas])
            return cur.lastrowid

    # ------------------------------------------------------------------ catálogo
    def _mapear_catalogo(self, src, mapas, copiar_faltante, informe):
        for tabla in CATALOGO:
            mapas[tabla] = {}
            if not self._tabla_existe(src, tabla):
                continue
            cols_origen = self._columnas_origen(src, tabla)
            cols_destino = self._columnas_destino(tabla)
            comunes = [c for c in cols_origen if c in cols_destino and c != 'id']
            for fila in src.execute(f'SELECT * FROM "{tabla}"'):
                nombre = fila['nombre']
                buscado = getattr(self, 'equivalencias', {}).get(nombre, nombre) if tabla in ('core_cultivo', 'core_zona') else nombre
                with connection.cursor() as cur:
                    cur.execute(f'SELECT MIN(id) FROM "{tabla}" WHERE nombre = %s', [buscado])
                    destino_id = cur.fetchone()[0]
                    if destino_id is None and buscado != nombre:
                        cur.execute(f'SELECT id, nombre FROM "{tabla}" ORDER BY id')
                        for ident, candidato in cur.fetchall():
                            if _plano(candidato) == _plano(buscado):
                                destino_id, buscado = ident, candidato
                                break
                if destino_id is not None and buscado != nombre:
                    informe['avisos'].append(f'{tabla.replace("core_", "")} «{nombre}» se enlazó con «{buscado}» de la oficial (equivalencia indicada).')
                if destino_id is None and copiar_faltante and tabla in ('core_cultivo', 'core_zona'):
                    datos = {c: fila[c] for c in comunes}
                    try:
                        with transaction.atomic():
                            destino_id = self._insertar(tabla, datos)
                        informe['catalogo_creado'].append(f'{tabla.replace("core_", "")}: «{nombre}»')
                    except IntegrityError as exc:
                        informe['avisos'].append(f'No se pudo crear {tabla} «{nombre}»: {exc}')
                if destino_id is None:
                    informe['catalogo_faltante'].add(f'{tabla.replace("core_", "")}: «{nombre}»')
                else:
                    mapas[tabla][fila['id']] = destino_id

    # ------------------------------------------------------------------ proceso de un archivo
    def _procesar(self, ruta, copiar_faltante, excluidos=()):
        informe = {
            'tablas': {}, 'usuarios': [], 'avisos': [], 'omitidos': [], 'conflictos': [],
            'catalogo_faltante': set(), 'catalogo_creado': [],
        }
        src = sqlite3.connect(f'file:{ruta}?mode=ro', uri=True)
        src.row_factory = sqlite3.Row
        try:
            mapas = {}
            self._mapear_catalogo(src, mapas, copiar_faltante, informe)
            for tabla, clave, fks in PLAN:
                mapas.setdefault(tabla, {})
                est = informe['tablas'].setdefault(tabla, {'nuevos': 0, 'existian': 0, 'omitidos': 0})
                if not self._tabla_existe(src, tabla):
                    continue
                cols_destino = self._columnas_destino(tabla)
                cols_origen = self._columnas_origen(src, tabla)
                comunes = [c for c in cols_origen if c in cols_destino and c != 'id']
                for fila in src.execute(f'SELECT * FROM "{tabla}" ORDER BY id'):
                    datos = {c: fila[c] for c in comunes}
                    motivo = None
                    for col, (ref, obligatoria) in fks.items():
                        valor = datos.get(col)
                        if valor is None:
                            continue
                        nuevo = mapas.get(ref, {}).get(valor)
                        if nuevo is None:
                            if obligatoria:
                                motivo = f'{col}={valor} no tiene equivalente en la oficial ({ref.replace("core_", "")})'
                                break
                            datos[col] = None
                            informe['avisos'].append(
                                f'{tabla.replace("core_", "")} #{fila["id"]}: {col} quedó vacío porque «{ref.replace("core_", "")}» no existe en la oficial.'
                            )
                        else:
                            datos[col] = nuevo
                    if motivo:
                        est['omitidos'] += 1
                        informe['omitidos'].append(f'{tabla.replace("core_", "")} #{fila["id"]}: {motivo}')
                        continue
                    if tabla == 'auth_user' and datos.get('username') in excluidos:
                        est['omitidos'] += 1
                        informe['usuarios'].append((datos.get('username'), datos.get('email') or '—', bool(datos.get('is_superuser')), 'EXCLUIDO por ti (no se trae)'))
                        continue
                    claves = clave or list(datos)
                    existente = self._buscar(tabla, claves, datos)
                    conflicto = None
                    if tabla == 'auth_user' and existente is not None:
                        with connection.cursor() as cur:
                            cur.execute('SELECT email FROM auth_user WHERE id = %s', [existente])
                            correo_destino = ((cur.fetchone() or [''])[0] or '').strip().lower()
                        correo_origen = (datos.get('email') or '').strip().lower()
                        if correo_destino != correo_origen:
                            # Mismo nombre de usuario, otro correo: no se puede asegurar que sea la misma persona.
                            base, n = datos['username'], 2
                            ya_separada = None
                            while True:
                                candidato = f'{base[:140]}_{n}'
                                encontrada = self._buscar('auth_user', ['username'], {'username': candidato})
                                if encontrada is None:
                                    break
                                with connection.cursor() as cur:
                                    cur.execute('SELECT lower(email) FROM auth_user WHERE id = %s', [encontrada])
                                    if ((cur.fetchone() or [''])[0] or '') == correo_origen:
                                        ya_separada = encontrada   # esta cuenta ya se había separado en una consolidación anterior
                                        break
                                n += 1
                            if ya_separada is not None:
                                existente = ya_separada
                            else:
                                conflicto = (datos['username'], correo_destino, correo_origen)
                                existente = None
                                informe['conflictos'].append(
                                    f'Usuario «{base}»: ya existe con el correo «{correo_destino or "—"}» y la otra base lo tiene con «{correo_origen or "—"}». '
                                    f'Se tratan como personas distintas: la segunda cuenta se conserva separada como «{candidato}».'
                                )
                                datos['username'] = candidato
                    if tabla == 'core_agricultor' and existente is None:
                        with connection.cursor() as cur:
                            cur.execute('SELECT 1 FROM core_agricultor WHERE rut = %s', [datos.get('rut')])
                            if cur.fetchone():
                                est['omitidos'] += 1
                                informe['omitidos'].append(f'agricultor #{fila["id"]}: el RUT {datos.get("rut")} ya está en la oficial con otro usuario')
                                continue
                    if existente is not None:
                        mapas[tabla][fila['id']] = existente
                        est['existian'] += 1
                        accion = 'ya existía (se conserva el de la oficial)'
                        if tabla == 'auth_user':
                            with connection.cursor() as cur:
                                cur.execute('SELECT email FROM auth_user WHERE id = %s', [existente])
                                correo_oficial = (cur.fetchone() or [''])[0]
                            if (correo_oficial or '').lower() != (datos.get('email') or '').lower():
                                accion = f'⚠ MISMO NOMBRE DE USUARIO pero otro correo (oficial: {correo_oficial or "—"}); sus datos se unirán a la cuenta oficial'
                    else:
                        try:
                            with transaction.atomic():
                                mapas[tabla][fila['id']] = self._insertar(tabla, datos)
                        except IntegrityError as exc:
                            est['omitidos'] += 1
                            informe['omitidos'].append(f'{tabla.replace("core_", "")} #{fila["id"]}: {exc}')
                            continue
                        est['nuevos'] += 1
                        accion = 'se agregará' if not conflicto else f'⚠ CONFLICTO de identidad: se agregará como cuenta separada «{datos["username"]}»'
                    if tabla == 'auth_user':
                        informe['usuarios'].append((datos.get('username'), datos.get('email') or '—', bool(datos.get('is_superuser')), accion))
            for tabla in RETIRADAS:
                if self._tabla_existe(src, tabla):
                    cantidad = src.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
                    if cantidad:
                        informe['avisos'].append(f'«{tabla}» trae {cantidad} registros de una función retirada; no se copian.')
        finally:
            src.close()
        return informe

    def _mostrar(self, nombre, informe):
        self.stdout.write(self.style.MIGRATE_HEADING(f'\n--- {nombre} ---'))
        if informe['usuarios']:
            self.stdout.write('Usuarios:')
            for usuario, correo, admin, accion in informe['usuarios']:
                marca = ' [admin]' if admin else ''
                self.stdout.write(f'  {usuario}{marca} <{correo}> → {accion}')
        self.stdout.write('Por tabla (nuevos / ya existían / omitidos):')
        for tabla, est in informe['tablas'].items():
            self.stdout.write(f'  {tabla.replace("core_", ""):<26}{est["nuevos"]:>4} /{est["existian"]:>4} /{est["omitidos"]:>4}')
        if informe['conflictos']:
            self.stdout.write(self.style.WARNING('Conflictos de identidad (se conservan SEPARADOS, nada se fusiona):'))
            for linea in informe['conflictos']:
                self.stdout.write(f'  ⚠ {linea}')
        if informe['catalogo_creado']:
            self.stdout.write('Catálogo creado en la oficial:')
            for linea in informe['catalogo_creado']:
                self.stdout.write(f'  + {linea}')
        if informe['catalogo_faltante']:
            self.stdout.write(self.style.WARNING('Elementos de catálogo que NO existen en la oficial (los datos que los usan se omiten o quedan sin vínculo):'))
            for linea in sorted(informe['catalogo_faltante']):
                self.stdout.write(f'  ! {linea}')
        if informe['omitidos']:
            self.stdout.write(self.style.WARNING('Registros omitidos:'))
            for linea in informe['omitidos']:
                self.stdout.write(f'  - {linea}')
        for linea in informe['avisos']:
            self.stdout.write(self.style.WARNING(f'Aviso: {linea}'))

    # ------------------------------------------------------------------ comando
    def handle(self, *args, **options):
        destino = dbutils.ruta_bd()
        archivos = []
        for texto in options['origenes']:
            ruta = Path(texto)
            if not ruta.is_file():
                raise CommandError(f'No existe el archivo: {texto}')
            if ruta.resolve() == destino:
                raise CommandError(f'«{texto}» es la misma base oficial; indica OTRO archivo.')
            archivos.append(ruta)

        aplicar = options['aplicar']
        excluidos = {u.strip() for u in options['excluir_usuarios'].split(',') if u.strip()}
        self.equivalencias = {}
        for par in options['equivalencias'].split(','):
            if par.strip():
                if '=' not in par:
                    raise CommandError(f'Equivalencia mal escrita: «{par}». Usa «nombre en la otra base=nombre en la oficial».')
                izquierda, derecha = par.split('=', 1)
                self.equivalencias[izquierda.strip()] = derecha.strip()
        self.stdout.write(f'Base oficial (destino): {destino}')
        self.stdout.write(self.style.WARNING('MODO PRUEBA: no se guardará nada.') if not aplicar else self.style.SUCCESS('MODO APLICAR: se guardarán los cambios.'))

        if aplicar:
            respaldo = dbutils.respaldar(prefijo='db-antes-de-consolidar', mantener=0)
            if respaldo:
                self.stdout.write(self.style.SUCCESS(f'Respaldo previo de la oficial: {respaldo}'))

        with transaction.atomic():
            for ruta in archivos:
                informe = self._procesar(ruta, options['copiar_catalogo_faltante'], excluidos)
                self._mostrar(ruta.name, informe)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write('')
        if aplicar:
            self.stdout.write(self.style.SUCCESS('Listo: los datos quedaron guardados en la base oficial.'))
        else:
            self.stdout.write('Esto fue una prueba. Si el informe está bien, repite el comando agregando --aplicar.')
