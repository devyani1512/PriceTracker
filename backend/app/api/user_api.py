"""User endpoints: register, login, me."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from app.api.auth.jwt import generate_jwt
from app.core.bootstrap import get_services
from app.services.errors import Unauthorized


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    svc = get_services()
    user = svc.register_user(
        request.data.get("email"), request.data.get("password"), request.data.get("displayName")
    )
    return Response({"token": generate_jwt(user.id), "user": user.public()})


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    svc = get_services()
    user = svc.login_user(request.data.get("email"), request.data.get("password"))
    return Response({"token": generate_jwt(user.id), "user": user.public()})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    svc = get_services()
    user = svc.get_user(request.user.id)
    if user is None:
        raise Unauthorized("account not found")
    return Response({"user": user.public()})
