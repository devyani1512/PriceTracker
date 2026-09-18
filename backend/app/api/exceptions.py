"""Map service-layer domain errors to HTTP responses."""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import exception_handler

from app.services import errors

_STATUS = [
    (errors.NotFound, 404),
    (errors.Conflict, 409),
    (errors.Unauthorized, 401),
    (errors.ValidationError, 422),
]


def domain_exception_handler(exc, context):
    for exc_type, status_code in _STATUS:
        if isinstance(exc, exc_type):
            return Response({"detail": str(exc)}, status=status_code)
    return exception_handler(exc, context)
