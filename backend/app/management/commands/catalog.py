"""Force a full storefront catalog sync."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from app.core.bootstrap import get_core


class Command(BaseCommand):
    help = "Sync the storefront catalog into the products table."

    def handle(self, *args, **options):
        result = get_core().catalog.sync()
        self.stdout.write(self.style.SUCCESS(str(result)))
