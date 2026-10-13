import re

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

USERNAME_RE = re.compile(r"^[a-z0-9_.]{3,20}$")
RESERVED_USERNAMES = {
    "admin", "yeni", "giris", "kayit", "cikis", "api", "static", "kararsizim", "u", "a",
}


def validate_username(value):
    value = value.lower()
    if not USERNAME_RE.match(value):
        raise ValidationError(
            "Kullanıcı adı 3-20 karakter olmalı; yalnızca küçük harf, rakam, _ ve . kullanılabilir."
        )
    if value in RESERVED_USERNAMES:
        raise ValidationError("Bu kullanıcı adı kullanılamaz.")


class User(AbstractUser):
    email = models.EmailField("e-posta", unique=True)
    username = models.CharField(
        "kullanıcı adı", max_length=20, unique=True, validators=[validate_username]
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("username"), name="uniq_username_ci"),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        self.username = (self.username or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username
