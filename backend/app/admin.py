"""Django admin registrations — a free observability surface for the data."""

from __future__ import annotations

from django.contrib import admin

from app.entity import (
    Notification,
    PriceSnapshot,
    Product,
    ScrapeLog,
    Task,
    Tracker,
    TrackerHistory,
    User,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "brand", "category", "sku", "structure_changed_at")
    search_fields = ("name", "brand", "sku", "id")
    list_filter = ("category", "brand")
    ordering = ("id",)


@admin.register(Tracker)
class TrackerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "product",
        "refresh_minutes",
        "active",
        "last_covered_slot",
        "last_scraped_at",
    )
    search_fields = ("id", "user__email", "product__name")
    list_filter = ("active", "refresh_minutes")
    ordering = ("-created_at",)


@admin.register(PriceSnapshot)
class PriceSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "price",
        "in_stock",
        "stock_label",
        "trigger",
        "captured_at",
    )
    search_fields = ("product__name", "id")
    list_filter = ("trigger", "in_stock", "structure_changed")
    ordering = ("-captured_at",)


@admin.register(TrackerHistory)
class TrackerHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "tracker", "snapshot", "captured_at")
    ordering = ("-captured_at",)


@admin.register(ScrapeLog)
class ScrapeLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "product",
        "attempt",
        "outcome",
        "error_kind",
        "duration_ms",
        "price",
    )
    search_fields = ("product__name", "message")
    list_filter = ("outcome", "error_kind")
    ordering = ("-created_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "product", "type", "status", "created_at", "sent_at")
    search_fields = ("user__email", "product__name", "title")
    list_filter = ("type", "status")
    ordering = ("-created_at",)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "display_name", "created_at")
    search_fields = ("email", "display_name")
    ordering = ("-created_at",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("job_id", "category", "run_at", "created_at")
    list_filter = ("category",)
    ordering = ("run_at",)
