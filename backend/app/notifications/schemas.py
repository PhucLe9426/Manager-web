from pydantic import BaseModel


class NotificationItem(BaseModel):
    id: int
    websiteId: int | None
    category: str
    severity: str
    title: str
    message: str
    link: str | None
    isRead: bool
    createdAt: str
