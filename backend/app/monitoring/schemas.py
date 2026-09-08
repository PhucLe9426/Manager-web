from pydantic import BaseModel


class ScanAllResult(BaseModel):
    message: str
    total: int
    queued: int


class ScanJobResult(BaseModel):
    id: int
    websiteId: int
    status: str
