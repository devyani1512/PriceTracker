"""ASGI entrypoint. The lifespan hook starts the background core exactly once."""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application  # noqa: E402

django_app = get_asgi_application()

from app.core.bootstrap import boot_core, shutdown_core  # noqa: E402


async def application(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                boot_core()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                shutdown_core()
                await send({"type": "lifespan.shutdown.complete"})
                return
    else:
        await django_app(scope, receive, send)
