"""Django model discovery.

Models live one-per-entity in ``app/entity/*.py`` (mirroring the reference
repo map). Django imports this module at startup, so re-exporting them here is
what registers the tables and lets ``makemigrations`` see them.
"""

from app.entity import *  # noqa: F401,F403
