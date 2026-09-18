"""Root URL configuration. API routes live in ``app.api.urls``."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("app.api.urls")),
]
