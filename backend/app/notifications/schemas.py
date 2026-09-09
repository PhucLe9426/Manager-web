from typing import Literal

from pydantic import BaseModel, Field


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


class NotificationCreate(BaseModel):
    category: Literal["system", "website", "customer", "report", "scan"] = "system"
    severity: Literal["info", "success", "warning", "danger"] = "info"
    title: str = Field(min_length=1, max_length=240)
    message: str = Field(min_length=1, max_length=2000)
    websiteId: int | None = Field(default=None, ge=1)
    link: str | None = Field(default=None, max_length=500)
    eventKey: str | None = Field(default=None, min_length=1, max_length=190)
