"""Domain exceptions. Handlers translate these to HTTP status codes."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all service-layer errors."""


class NotFound(DomainError):
    pass


class Conflict(DomainError):
    pass


class ValidationError(DomainError):
    pass


class Unauthorized(DomainError):
    pass
