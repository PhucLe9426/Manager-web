from datetime import date

from pydantic import BaseModel, Field


class ReportItemCreate(BaseModel):
    performedDate: date
    description: str = Field(min_length=1, max_length=2000)
    result: str | None = Field(default=None, max_length=2000)


class ReportCreate(BaseModel):
    websiteId: int
    title: str = Field(min_length=1, max_length=240)
    periodStart: date
    periodEnd: date
    summary: str | None = Field(default=None, max_length=5000)
    items: list[ReportItemCreate] = Field(min_length=1, max_length=50)
