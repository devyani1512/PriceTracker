"""API URL routes (≈ api/server.go route table)."""

from __future__ import annotations

from django.urls import path

from app.api import (
    cron_api,
    product_api,
    root_api,
    tracker_api,
    user_api,
)

urlpatterns = [
    # root
    path("", root_api.root, name="root"),
    path("health", root_api.health, name="health"),
    # user
    path("user/register", user_api.register, name="user-register"),
    path("user/login", user_api.login, name="user-login"),
    path("user/me", user_api.me, name="user-me"),
    # product
    path("product/search", product_api.search_products, name="product-search"),
    path("product/list", product_api.list_products, name="product-list"),
    path("product/<int:product_id>", product_api.get_product, name="product-detail"),
    path("product/<int:product_id>/refresh", product_api.refresh_product, name="product-refresh"),
    path("product/<int:product_id>/logs", product_api.product_logs, name="product-logs"),
    path("catalog/status", product_api.catalog_status, name="catalog-status"),
    # tracker + notifications
    path("tracker/add", tracker_api.add_tracker, name="tracker-add"),
    path("tracker/list", tracker_api.list_trackers, name="tracker-list"),
    path("tracker/<str:tracker_id>", tracker_api.tracker_detail, name="tracker-detail"),
    path("tracker/<str:tracker_id>/history", tracker_api.tracker_history, name="tracker-history"),
    path("tracker/<str:tracker_id>/logs", tracker_api.tracker_logs, name="tracker-logs"),
    path("dashboard", tracker_api.dashboard, name="dashboard"),
    path("notification/subscribe", tracker_api.subscribe, name="notification-subscribe"),
    path("notification/list", tracker_api.list_notifications, name="notification-list"),
    # cron + admin
    path("cron/tick", cron_api.cron_tick, name="cron-tick"),
    path("cron/status", cron_api.cron_status, name="cron-status"),
    path("cron/notify", cron_api.cron_notify, name="cron-notify"),
    path("admin/catalog/sync", cron_api.catalog_sync, name="catalog-sync"),
]
