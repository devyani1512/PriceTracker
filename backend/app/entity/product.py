from __future__ import annotations

from django.db import models


class Product(models.Model):
    """A storefront product. ``id`` is the store's own numeric product id.

    Catalog rows are synced at boot (< 1000 rows triggers a full sync); detail
    rows (specs/reviews) are filled lazily from ``/api/product/{id}``.
    """

    id = models.IntegerField(primary_key=True)
    slug = models.CharField(max_length=200, null=True, blank=True)
    name = models.CharField(max_length=300, db_index=True)
    brand = models.CharField(max_length=120, null=True, blank=True)
    category = models.CharField(max_length=120, null=True, blank=True, db_index=True)
    sku = models.CharField(max_length=60, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    specs = models.JSONField(null=True, blank=True)
    reviews = models.JSONField(null=True, blank=True)
    detail_loaded_at = models.DateTimeField(null=True, blank=True)

    # Change detection: when the storefront page structure stops matching the
    # layout we know how to parse, we flag the product instead of guessing.
    structure_changed_at = models.DateTimeField(null=True, blank=True)
    structure_note = models.CharField(max_length=300, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"

    def card(self) -> dict:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "sku": self.sku,
            "description": self.description,
            "structureChanged": self.structure_changed_at is not None,
        }
