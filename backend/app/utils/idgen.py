"""ID generation — the Python analogue of Go's utils.GenerateID / uuid.NewString.

Go mixes incremental ids (users/rooms) with uuid (contests). We use a
time-sortable string for every entity because it plays nicely with Postgres
text keys and keeps created_at ordering implicit.
"""

from __future__ import annotations

import secrets
import time
import uuid


class IDGenerator:
    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or {}

    def new_id(self) -> str:
        """UUID4 string. Used for users, trackers, snapshots, notifications."""
        return str(uuid.uuid4())

    def new_short_id(self, prefix: str = "") -> str:
        """Sortable, human-readable id: <prefix><ms-timestamp><random>."""
        token = f"{int(time.time() * 1000):013d}{secrets.token_hex(4)}"
        return f"{prefix}{token}" if prefix else token
