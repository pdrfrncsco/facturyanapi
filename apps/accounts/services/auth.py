from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

User = get_user_model()


def register_user(*, first_name: str, last_name: str, email: str, password: str) -> User:
    if User.objects.filter(email=email).exists():
        raise ValidationError(_("Já existe um utilizador registado com este email."))
    
    # generate username from email
    username = email.split('@')[0]
    
    user = User.objects.create_user(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
    )
    return user
