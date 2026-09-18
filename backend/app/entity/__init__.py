"""Entity exports. Importing this module registers every model with Django."""

from app.entity.notification import Notification, NotificationStatus, NotificationType
from app.entity.price import (
    PriceSnapshot,
    ScrapeErrorKind,
    ScrapeLog,
    ScrapeOutcome,
    SnapshotTrigger,
    TrackerHistory,
)
from app.entity.product import Product
from app.entity.scheduler import JobType, Task
from app.entity.tracker import Tracker
from app.entity.user import User

__all__ = [
    "JobType",
    "Notification",
    "NotificationStatus",
    "NotificationType",
    "PriceSnapshot",
    "Product",
    "ScrapeErrorKind",
    "ScrapeLog",
    "ScrapeOutcome",
    "SnapshotTrigger",
    "Task",
    "Tracker",
    "TrackerHistory",
    "User",
]
