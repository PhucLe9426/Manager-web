from ..core.errors import ServiceError
from . import repository


def list_notifications(limit: int) -> dict:
    return repository.list_recent(min(50, max(1, limit)))


def mark_notification_read(notification_id: int) -> dict:
    if notification_id <= 0:
        raise ServiceError("Thông báo không hợp lệ.")
    notification = repository.mark_read(notification_id)
    if not notification:
        raise ServiceError("Không tìm thấy thông báo.", 404)
    return notification


def mark_all_notifications_read() -> int:
    return repository.mark_all_read()
