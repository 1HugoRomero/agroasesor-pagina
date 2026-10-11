from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Correo para agricultores; mantiene acceso por username a cuentas existentes."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        model = get_user_model()
        candidates = model.objects.filter(email__iexact=username) if '@' in username else model.objects.filter(username=username)
        user = candidates.first() if candidates.count() == 1 else None
        if user is None:
            model().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
