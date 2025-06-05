from django.contrib.auth.backends import ModelBackend
from .models import CustomUser


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = username or kwargs.get('email')
        if not email:
            return None

        try:
            user = CustomUser.objects.get(email__iexact=email)
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            pass
        return None
