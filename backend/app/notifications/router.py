from fastapi import APIRouter, Query

from ..core.errors import ServiceError
from ..core.responses import message
from . import service
from .schemas import NotificationCreate


router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("")
def list_notifications(limit: int = Query(default=20, ge=1, le=50)):
    return service.list_notifications(limit)


@router.post("", status_code=201)
def create_notification(payload: NotificationCreate):
    try:
        return {"notification": service.create_notification(payload)}
    except ServiceError as error:
        return message(str(error), error.status_code)


@router.patch("/{notification_id}/read")
def mark_notification_read(notification_id: int):
    try:
        return {"notification": service.mark_notification_read(notification_id)}
    except ServiceError as error:
        return message(str(error), error.status_code)


@router.post("/read-all")
def mark_all_notifications_read():
    return {"updated": service.mark_all_notifications_read()}
