from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailBackend(ModelBackend):
    """Acceso con correo o con nombre de usuario (sin distinguir mayúsculas).

    Si por datos antiguos varias cuentas comparten el mismo correo, se prueba la contraseña con cada una
    (primero la que tenga exactamente ese nombre de usuario) y entra la que coincida, en vez de rechazar
    a todas. Así una cuenta registrada siempre puede volver a entrar.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        identificador = username.strip()
        model = get_user_model()
        candidatos = list(model.objects.filter(
            Q(username__iexact=identificador) | Q(email__iexact=identificador)
        ).order_by('pk')[:10])
        # Primero la cuenta cuyo nombre de usuario es justo lo escrito; luego las que coinciden por correo.
        candidatos.sort(key=lambda u: 0 if u.username.lower() == identificador.lower() else 1)
        if not candidatos:
            model().set_password(password)  # tiempo de respuesta parecido al de una cuenta real
            return None
        for user in candidatos:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
