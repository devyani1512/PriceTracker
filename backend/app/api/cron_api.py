"""Cron + admin endpoints. Protected by the shared CRON_SECRET header."""

from __future__ import annotations

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from app.core.bootstrap import get_core, get_services
from app.utils.timeutil import utcnow


class HasCronSecret(BasePermission):
    def has_permission(self, request, view) -> bool:
        cfg = settings.PRICE_TRACKER
        expected = str(cfg["Security"]["cronSecret"])
        provided = request.headers.get("X-Cron-Secret") or request.query_params.get("secret")
        return bool(expected) and provided == expected


def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@api_view(["POST"])
@permission_classes([HasCronSecret])
def cron_tick(request):
    """External cron (cron-job.org) calls this on a schedule.

    By default it is fire-and-forget: it enqueues every due scrape, wakes the
    background scheduled workers, and returns immediately, so the scheduler
    never times out. The durable queue means the work still completes — the
    workers drain it while the instance is awake, and anything left over is
    picked up on the next tick. Pass ``?drain=true`` for a synchronous drain
    (bounded by ``budgetSeconds``), handy for debugging or one-shot runners.
    """
    cfg = settings.PRICE_TRACKER["Core"]
    force = _as_bool(request.query_params.get("force"), False)
    scrape = _as_bool(request.query_params.get("scrape"), True)
    drain = _as_bool(request.query_params.get("drain"), False)
    budget = request.query_params.get("budgetSeconds")
    budget_seconds = (
        float(budget)
        if budget
        else float(cfg.get("cronInlineBudgetSeconds", 120))
    )
    return Response(
        get_core().cron.tick(
            force=force,
            scrape=scrape,
            budget_seconds=budget_seconds,
            drain=drain,
        )
    )


@api_view(["GET"])
@permission_classes([HasCronSecret])
def cron_status(request):
    """Queue depth for observability (pending + currently due)."""
    core = get_core()
    now = utcnow()
    return Response(
        {
            "pendingTasks": core.jobs.pending_count(),
            "dueTasks": core.db.tasks.due_count(now),
            "selfTick": core.cfg["Core"]["selfTick"],
        }
    )


@api_view(["POST"])
@permission_classes([HasCronSecret])
def cron_notify(request):
    return Response({"dispatched": get_services().dispatch_pending()})


@api_view(["POST"])
@permission_classes([HasCronSecret])
def catalog_sync(request):
    return Response(get_services().sync_catalog())
