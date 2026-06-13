from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from apps.empresas.models import Empresa, EmpresaMembership

User = get_user_model()


def register_user(*, first_name: str, last_name: str, email: str, password: str, company_name: str, company_nif: str) -> User:
    if User.objects.filter(email=email).exists():
        raise ValidationError(_("Já existe um utilizador registado com este email."))
    if Empresa.objects.filter(nif=company_nif).exists():
        raise ValidationError(_("Já existe uma empresa registada com este NIF."))
    
    # generate username from email
    username = email.split('@')[0]
    
    with transaction.atomic():
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            role=User.Role.ADMIN
        )
        
        empresa = Empresa.objects.create(
            name=company_name,
            nif=company_nif
        )
        
        EmpresaMembership.objects.create(
            user=user,
            empresa=empresa,
            role=EmpresaMembership.Role.OWNER,
            is_default=True
        )
    
    return user
