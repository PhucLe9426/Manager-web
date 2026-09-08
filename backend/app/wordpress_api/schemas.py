from typing import Literal

from pydantic import BaseModel


class WordPressConnectionCreate(BaseModel):
    username: str | None = None
    applicationPassword: str | None = None


class WordPressPluginUpdate(BaseModel):
    plugin: str | None = None
    status: Literal["active", "inactive"]
