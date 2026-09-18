"""Cron + admin endpoints. Protected by the shared CRON_SECRET header."""

from __future__ import annotations

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from app.core.bootstrap import get_core, get_services


class HasCronSecret(BasePermission):
    def has_permission(self, request, view) -> bool:
        cfg = settings.PRICE_TRACKER
        expected = str(cfg["Security"]["cronSecret"])
        provided = request.headers.get("X-Cron-Secret") or request.query_params.get("secret")
        return bool(expected) and provided == expected


@api_view(["POST"])
@permission_classes([HasCronSecret])
def cron_tick(request):
    """External cron (cron-job.org) calls this every N minutes."""
    force = str(request.query_params.get("force", "")).lower() in {"1", "true", "yes"}
    scrape = str(request.query_params.get("scrape", "true")).lower() not in {"0", "false", "no"}
    budget = request.query_params.get("budgetSeconds")
    return Response(
        get_core().cron.tick(
            force=force,
            scrape=scrape,
            budget_seconds=float(budget) if budget else None,
        )
    )


@api_view(["POST"])
@permission_classes([HasCronSecret])
def cron_notify(request):
    return Response({"dispatched": get_services().dispatch_pending()})


@api_view(["POST"])
@permission_classes([HasCronSecret])
def catalog_sync(request):
    return Response(get_services().sync_catalog())
