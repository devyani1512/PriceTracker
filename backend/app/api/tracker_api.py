"""Tracker + notification endpoints (all user-scoped)."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.core.bootstrap import get_services


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_tracker(request):
    svc = get_services()
    data = request.data
    return Response(
        svc.add_tracker(
            request.user.id,
            int(data.get("productId")),
            refresh_minutes=data.get("refreshMinutes"),
            alert_on_price_drop=data.get("alertOnPriceDrop", True),
            price_drop_threshold_pct=data.get("priceDropThresholdPct"),
            alert_on_back_in_stock=data.get("alertOnBackInStock", True),
            run_now=data.get("runNow", True),
        )
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_trackers(request):
    return Response({"items": get_services().list_trackers(request.user.id)})


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def tracker_detail(request, tracker_id: str):
    svc = get_services()
    if request.method == "GET":
        return Response(svc.get_tracker(request.user.id, tracker_id))
    if request.method == "DELETE":
        svc.untrack(request.user.id, tracker_id)
        return Response({"status": "untracked"})

    data = request.data
    fields = {
        "refresh_minutes": data.get("refreshMinutes"),
        "active": data.get("active"),
        "alert_on_price_drop": data.get("alertOnPriceDrop"),
        "alert_on_back_in_stock": data.get("alertOnBackInStock"),
    }
    if "priceDropThresholdPct" in data:
        fields["price_drop_threshold_pct"] = data.get("priceDropThresholdPct")
    fields = {
        k: v
        for k, v in fields.items()
        if k == "price_drop_threshold_pct" or v is not None
    }
    return Response(svc.update_tracker(request.user.id, tracker_id, **fields))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tracker_history(request, tracker_id: str):
    svc = get_services()
    days = request.query_params.get("days")
    return Response(
        svc.tracker_history(request.user.id, tracker_id, days=int(days) if days else None)
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tracker_logs(request, tracker_id: str):
    svc = get_services()
    return Response(
        svc.tracker_logs(
            request.user.id,
            tracker_id,
            limit=int(request.query_params.get("limit", 50) or 50),
            page=int(request.query_params.get("page", 1) or 1),
        )
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    return Response(get_services().dashboard(request.user.id))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def subscribe(request):
    svc = get_services()
    data = request.data
    return Response(
        svc.subscribe_back_in_stock(
            request.user.id, int(data.get("productId")), data.get("trackerId")
        )
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    return Response({"items": get_services().list_notifications(request.user.id)})
