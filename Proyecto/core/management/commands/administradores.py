"""Gestiona quiénes son los administradores del sistema (RF-04: tres integrantes del equipo).

No existe registro público de administradores y este comando NUNCA crea cuentas ni contraseñas:
solo marca como administradoras cuentas que ya existen. Siempre empieza en modo prueba.

Uso (Docker):
    docker exec agroasesor_hugo python manage.py administradores                      # lista las cuentas
    docker exec agroasesor_hugo python manage.py administradores --asignar CORREO1 CORREO2 CORREO3
    docker exec agroasesor_hugo python manage.py administradores --asignar CORREO1 CORREO2 CORREO3 --aplicar
    docker exec agroasesor_hugo python manage.py administradores --quitar CORREO   (+ --aplicar)

Si una cuenta todavía no existe, créala con tu propia contraseña (la escribes tú, no queda en ningún archivo):
    docker exec -it agroasesor_hugo python manage.py createsuperuser
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

MAX_ADMINISTRADORES = 3


class Command(BaseCommand):
    help = 'Lista las cuentas y marca como administradores (con acceso al panel) cuentas que ya existen.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--asignar',
            nargs='+',
            metavar='CORREO_O_USUARIO',
            default=[],
            help='Cuentas a marcar como administradoras.',
        )
        parser.add_argument(
            '--quitar',
            nargs='+',
            metavar='CORREO_O_USUARIO',
            default=[],
            help='Cuentas a las que se les quita el acceso de administrador.',
        )
        parser.add_argument(
            '--aplicar', action='store_true', help='Guarda los cambios (sin esto solo se muestra qué pasaría).'
        )

    def _resolver(self, texto):
        usuarios = get_user_model().objects
        coincidencias = list(
            usuarios.filter(Q(username__iexact=texto.strip()) | Q(email__iexact=texto.strip())).order_by('pk')
        )
        exactas = [u for u in coincidencias if u.username.lower() == texto.strip().lower()]
        if len(exactas) == 1:
            return exactas[0]
        if len(coincidencias) == 1:
            return coincidencias[0]
        if not coincidencias:
            raise CommandError(
                f'No existe ninguna cuenta con «{texto}». No se crea nada automáticamente. '
                'Si es una cuenta nueva, créala tú con: docker exec -it agroasesor_hugo python manage.py createsuperuser'
            )
        detalle = ', '.join(f'{u.username} <{u.email}>' for u in coincidencias)
        raise CommandError(
            f'«{texto}» coincide con varias cuentas ({detalle}). Usa el nombre de usuario exacto de la que corresponde.'
        )

    def _listar(self):
        usuarios = get_user_model().objects.order_by('-is_staff', 'pk')
        self.stdout.write(f'{"id":>3}  {"admin":<6} {"usuario":<34} {"correo":<36} nombre')
        for u in usuarios:
            self.stdout.write(
                f'{u.pk:>3}  {"SÍ" if u.is_staff else "":<6} {u.username[:33]:<34} {u.email[:35]:<36} {u.get_full_name()}'
            )
        admins = usuarios.filter(is_staff=True).count()
        self.stdout.write(f'\nAdministradores actuales: {admins} (meta del proyecto: {MAX_ADMINISTRADORES}).')

    def handle(self, *args, **options):
        asignar, quitar, aplicar = options['asignar'], options['quitar'], options['aplicar']
        self.stdout.write('')
        if not asignar and not quitar:
            self._listar()
            return
        a_asignar = [self._resolver(t) for t in asignar]
        a_quitar = [self._resolver(t) for t in quitar]
        if {u.pk for u in a_asignar} & {u.pk for u in a_quitar}:
            raise CommandError('Una misma cuenta no puede estar en --asignar y --quitar.')

        staff_final = set(get_user_model().objects.filter(is_staff=True).values_list('pk', flat=True))
        staff_final |= {u.pk for u in a_asignar}
        staff_final -= {u.pk for u in a_quitar}

        self.stdout.write(self.style.SUCCESS('MODO APLICAR' if aplicar else 'MODO PRUEBA: no se guardará nada.'))
        for u in a_asignar:
            estado = 'ya era administrador' if u.is_staff and u.is_superuser else 'pasará a ser administrador'
            self.stdout.write(f'  + {u.username} <{u.email}> → {estado}')
        for u in a_quitar:
            self.stdout.write(f'  - {u.username} <{u.email}> → dejará de ser administrador')
        if len(staff_final) > MAX_ADMINISTRADORES:
            otros = get_user_model().objects.filter(pk__in=staff_final).exclude(pk__in=[u.pk for u in a_asignar])
            self.stdout.write(
                self.style.WARNING(
                    f'Aviso: quedarían {len(staff_final)} administradores y la meta es {MAX_ADMINISTRADORES}. '
                    'Otros administradores que ya existen: '
                    + ', '.join(f'{u.username} <{u.email}>' for u in otros)
                    + '. Si sobran, quítales el acceso con --quitar.'
                )
            )
        elif len(staff_final) < MAX_ADMINISTRADORES:
            self.stdout.write(f'Nota: quedarían {len(staff_final)} de {MAX_ADMINISTRADORES} administradores.')

        if not aplicar:
            self.stdout.write('\nEsto fue una prueba. Repite el comando con --aplicar para guardar.')
            return
        with transaction.atomic():
            for u in a_asignar:
                u.is_staff = True
                u.is_superuser = True
                u.is_active = True
                u.save(update_fields=['is_staff', 'is_superuser', 'is_active'])
            for u in a_quitar:
                u.is_staff = False
                u.is_superuser = False
                u.save(update_fields=['is_staff', 'is_superuser'])
        self.stdout.write(self.style.SUCCESS('\nListo. Las contraseñas no se tocaron.'))
        self._listar()
