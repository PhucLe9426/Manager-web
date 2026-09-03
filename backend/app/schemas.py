from typing import Literal

from pydantic import BaseModel


class CustomerCreate(BaseModel):
    name: str | None = None
    contactName: str | None = None
    contactEmail: str | None = None
    contactPhone: str | None = None


class CustomerUpdate(CustomerCreate):
    status: Literal["active", "paused"] | None = None


class WebsiteCreate(BaseModel):
    domain: str | None = None
    customerId: int | None = None

