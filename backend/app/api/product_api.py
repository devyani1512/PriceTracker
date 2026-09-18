"""Product endpoints: search, browse, detail, refresh, logs, catalog."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from app.core.bootstrap import get_services


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@api_view(["GET"])
@permission_classes([AllowAny])
def search_products(request):
    svc = get_services()
    return Response(
        svc.search_products(
            request.query_params.get("q", ""),
            int(request.query_params.get("page", 1) or 1),
            int(request.query_params.get("pageSize", 20) or 20),
        )
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def list_products(request):
    svc = get_services()
    return Response(
        svc.list_products(
            int(request.query_params.get("page", 1) or 1),
            int(request.query_params.get("pageSize", 20) or 20),
        )
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_product(request, product_id: int):
    svc = get_services()
    ensure = _as_bool(request.query_params.get("ensurePrice"))
    return Response(svc.get_product(product_id, ensure_price=ensure))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def refresh_product(request, product_id: int):
    svc = get_services()
    wait = _as_bool(request.query_params.get("wait"))
    headless = request.query_params.get("headless")
    headless_flag = None if headless is None else _as_bool(headless)
    return Response(svc.refresh_product(product_id, wait=wait, headless=headless_flag))


@api_view(["GET"])
@permission_classes([AllowAny])
def product_logs(request, product_id: int):
    svc = get_services()
    return Response(
        svc.product_logs(
            product_id,
            limit=int(request.query_params.get("limit", 50) or 50),
            page=int(request.query_params.get("page", 1) or 1),
        )
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def catalog_status(request):
    return Response(get_services().catalog_status())
