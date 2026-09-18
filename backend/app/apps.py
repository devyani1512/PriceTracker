from __future__ import annotations

from django.apps import AppConfig


class AppConfig(AppConfig):
    name = "app"
    label = "app"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Price Tracker"
