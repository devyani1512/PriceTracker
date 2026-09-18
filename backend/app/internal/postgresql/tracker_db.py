from __future__ import annotations

from app.entity.tracker import Tracker


class TrackerRepo:
    def __init__(self, db):
        self.db = db

    def create(self, tracker: Tracker) -> None:
        tracker.save()

    def get(self, tracker_id: str) -> Tracker | None:
        return Tracker.objects.filter(pk=tracker_id).first()

    def get_by_user_product(self, user_id: str, product_id: int) -> Tracker | None:
        return Tracker.objects.filter(user_id=user_id, product_id=product_id).first()

    def list_for_user(self, user_id: str, active_only: bool = False) -> list[Tracker]:
        queryset = Tracker.objects.filter(user_id=user_id)
        if active_only:
            queryset = queryset.filter(active=True)
        return list(queryset.order_by("-created_at"))

    def list_active(self) -> list[Tracker]:
        return list(
            Tracker.objects.filter(active=True).order_by("product_id", "refresh_minutes")
        )

    def list_active_for_product(self, product_id: int) -> list[Tracker]:
        return list(Tracker.objects.filter(product_id=product_id, active=True))

    def list_all(self) -> list[Tracker]:
        return list(Tracker.objects.all())

    def update(self, tracker: Tracker) -> None:
        tracker.save()

    def mark_covered(self, tracker_id: str, slot, scraped_at=None) -> None:
        fields: dict = {"last_covered_slot": slot}
        if scraped_at is not None:
            fields["last_scraped_at"] = scraped_at
        Tracker.objects.filter(pk=tracker_id).update(**fields)

    def delete(self, tracker_id: str) -> None:
        Tracker.objects.filter(pk=tracker_id).delete()
