from pydantic import BaseModel


class WebsiteCreate(BaseModel):
    domain: str | None = None
    customerId: int | None = None
