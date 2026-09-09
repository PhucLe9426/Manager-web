from uuid import uuid4

from ..core.errors import ServiceError
from . import repository
from .schemas import NotificationCreate


def list_notifications(limit: int) -> dict:
    return repository.list_recent(min(50, max(1, limit)))


def create_notification(payload: NotificationCreate) -> dict:
    data = payload.model_dump()
    link = data["link"]
    if link and not link.startswith("/"):
        raise ServiceError("Đường dẫn thông báo không hợp lệ.")
    event_key = data["eventKey"] or f"ui:{uuid4().hex}"
    notification = repository.create_notification(
        event_key=event_key,
        category=data["category"],
        severity=data["severity"],
        title=data["title"],
        message=data["message"],
        website_id=data["websiteId"],
        link=link,
    )
    if notification:
        return notification
    existing = repository.get_by_event_key(event_key)
    if not existing:
        raise ServiceError("Không thể tạo thông báo.", 500)
    return existing


def mark_notification_read(notification_id: int) -> dict:
    if notification_id <= 0:
        raise ServiceError("Thông báo không hợp lệ.")
    notification = repository.mark_read(notification_id)
    if not notification:
        raise ServiceError("Không tìm thấy thông báo.", 404)
    return notification


def mark_all_notifications_read() -> int:
    return repository.mark_all_read()
