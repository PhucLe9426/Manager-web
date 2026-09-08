from fastapi import APIRouter

from ..core.errors import ServiceError
from ..core.responses import message
from . import service


router = APIRouter(prefix="/api/websites", tags=["Monitoring"])


@router.post("/scan-all")
def queue_all_website_scans():
    return service.queue_all_website_scans()


@router.post("/{website_id}/scan")
def queue_website_scan(website_id: int):
    try:
        job = service.queue_website_scan(website_id)
        return {"message": "Đã đưa website vào hàng đợi quét.", "job": job}
    except ServiceError as error:
        return message(str(error), error.status_code)
