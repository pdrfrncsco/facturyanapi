import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "Admin", "Administrador"
        FINANCIAL_DIRECTOR = "Financial_Director", "Director Financeiro"
        BILLING_CLERK = "Billing_Clerk", "Técnico de Facturação"
        AUDITOR = "Auditor", "Auditor"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.BILLING_CLERK)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self) -> str:
        return self.get_full_name() or self.username
