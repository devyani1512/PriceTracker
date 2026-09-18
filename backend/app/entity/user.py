from __future__ import annotations

from django.db import models


class User(models.Model):
    id = models.CharField(primary_key=True, max_length=36)
    email = models.EmailField(max_length=320, unique=True, db_index=True)
    password_hash = models.CharField(max_length=255)
    display_name = models.CharField(max_length=80, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"

    def public(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "displayName": self.display_name,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
