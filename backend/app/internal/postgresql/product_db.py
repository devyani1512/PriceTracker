from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from app.entity.product import Product

# Columns refreshed by the catalog sync. Specs/reviews are deliberately left
# alone so a cheap catalog sync never wipes lazily-loaded detail data.
_CATALOG_FIELDS = ["slug", "name", "brand", "category", "sku", "description"]


class ProductRepo:
    def __init__(self, db):
        self.db = db

    def count(self) -> int:
        return Product.objects.count()

    def list_ids(self) -> set[int]:
        return set(Product.objects.values_list("id", flat=True))

    def get(self, product_id: int) -> Product | None:
        return Product.objects.filter(pk=product_id).first()

    def list_page(self, limit: int, offset: int) -> tuple[list[Product], int]:
        queryset = Product.objects.order_by("id")
        return list(queryset[offset : offset + limit]), queryset.count()

    def search(self, query: str, limit: int, offset: int) -> tuple[list[Product], int]:
        pattern = query.strip()
        queryset = Product.objects.filter(
            Q(name__icontains=pattern)
            | Q(brand__icontains=pattern)
            | Q(sku__icontains=pattern)
        ).order_by("name")
        return list(queryset[offset : offset + limit]), queryset.count()

    def upsert_catalog(self, rows: list[dict]) -> int:
        """Bulk upsert catalog rows by primary key. Returns rows written."""
        if not rows:
            return 0
        now = timezone.now()
        objects = [Product(updated_at=now, **row) for row in rows]
        Product.objects.bulk_create(
            objects,
            update_conflicts=True,
            unique_fields=["id"],
            update_fields=[*_CATALOG_FIELDS, "updated_at"],
            batch_size=250,
        )
        return len(objects)

    def update_detail(
        self, product_id: int, specs: dict, reviews: list, loaded_at
    ) -> None:
        Product.objects.filter(pk=product_id).update(
            specs=specs,
            reviews=reviews,
            detail_loaded_at=loaded_at,
            updated_at=timezone.now(),
        )

    def flag_structure_change(self, product_id: int, note: str, at) -> None:
        Product.objects.filter(pk=product_id).update(
            structure_changed_at=at,
            structure_note=(note or "")[:300],
            updated_at=timezone.now(),
        )

    def clear_structure_flag(self, product_id: int) -> None:
        Product.objects.filter(pk=product_id).update(
            structure_changed_at=None,
            structure_note=None,
            updated_at=timezone.now(),
        )
