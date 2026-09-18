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
    svc = get_services()
    cfg = get_cfg()
    alive = svc.db.ping()
    return Response(
        {
            "status": "ok" if alive else "degraded",
            "database": alive,
            "catalog": svc.catalog_status(),
            "storefront": cfg["Core"]["storefrontBase"],
            "selfTick": cfg["Core"]["selfTick"],
            "headless": cfg["Core"]["headless"],
        }
    )
