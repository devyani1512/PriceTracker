"""Root + health endpoints."""

from __future__ import annotations

from rest_framework.decorators import api_view
from rest_framework.response import Response

from app.core.bootstrap import get_cfg, get_services


@api_view(["GET"])
def root(request):
    return Response({"service": "Price Tracker API", "status": "ok"})


@api_view(["GET"])
def health(request):
    """Liveness/readiness probe.

    Always answers 2xx. A database blip (e.g. the pooler briefly refusing a
    connection) reports ``degraded`` instead of a 500: returning 5xx here makes
    Render restart the instance, which only adds more connection churn while it
    is trying to recover.
    """
    try:
        svc = get_services()
        cfg = get_cfg()
    except Exception:  # core failed to build (configuration/database)
        return Response(
            {"status": "degraded", "database": False, "catalog": None}
        )

    try:
        alive = svc.db.ping()
    except Exception:
        alive = False

    catalog = None
    if alive:
        try:
            catalog = svc.catalog_status()
        except Exception:
            alive = False

    return Response(
        {
            "status": "ok" if alive else "degraded",
            "database": alive,
            "catalog": catalog,
            "storefront": cfg["Core"]["storefrontBase"],
            "selfTick": cfg["Core"]["selfTick"],
            "headless": cfg["Core"]["headless"],
        }
    )
