from ..core.errors import ServiceError
from . import repository


def queue_all_website_scans() -> dict:
    total, queued = repository.queue_all()
    if total == 0:
        return {"message": "Chưa có website để quét.", "total": 0, "queued": 0}
    return {"message": f"Đã đưa {total} website vào hàng đợi quét.", "total": total, "queued": queued}


def queue_website_scan(website_id: int) -> dict:
    if website_id <= 0:
        raise ServiceError("Website không hợp lệ.")
    job = repository.queue_one(website_id)
    if not job:
        raise ServiceError("Không tìm thấy website.", 404)
    return job
