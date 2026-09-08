from fastapi import APIRouter

from ..core.responses import message
from ..database import connection


router = APIRouter(prefix="/api/websites", tags=["Monitoring"])


@router.post("/scan-all")
def queue_all_website_scans():
    with connection() as conn:
        total = conn.execute("SELECT COUNT(*)::int AS total FROM websites").fetchone()["total"]
        if total == 0:
            return {"message": "Chưa có website để quét.", "total": 0, "queued": 0}
        conn.execute(
            """
            INSERT INTO scan_jobs
              (website_id, status, scheduled_at, attempts, last_error, updated_at)
            SELECT id, 'queued', NOW(), 0, NULL, NOW() FROM websites
            ON CONFLICT (website_id) DO UPDATE SET
              status = 'queued', scheduled_at = NOW(), attempts = 0,
              last_error = NULL, completed_at = NULL, updated_at = NOW()
            WHERE scan_jobs.status <> 'running'
            """
        )
        conn.execute(
            """
            UPDATE websites SET status = 'scanning', updated_at = NOW()
            WHERE id IN (SELECT website_id FROM scan_jobs WHERE status IN ('queued', 'running'))
            """
        )
        queued = conn.execute(
            """
            SELECT COUNT(*)::int AS total FROM scan_jobs
            WHERE status IN ('queued', 'running') AND website_id IN (SELECT id FROM websites)
            """
        ).fetchone()["total"]
    return {"message": f"Đã đưa {total} website vào hàng đợi quét.", "total": total, "queued": queued}


@router.post("/{website_id}/scan")
def queue_website_scan(website_id: int):
    if website_id <= 0:
        return message("Website không hợp lệ.", 400)
    with connection() as conn:
        if not conn.execute("SELECT id FROM websites WHERE id = %s", (website_id,)).fetchone():
            return message("Không tìm thấy website.", 404)
        job = conn.execute(
            """
            INSERT INTO scan_jobs
              (website_id, status, scheduled_at, attempts, last_error, updated_at)
            VALUES (%s, 'queued', NOW(), 0, NULL, NOW())
            ON CONFLICT (website_id) DO UPDATE SET
              status = 'queued', scheduled_at = NOW(), attempts = 0,
              last_error = NULL, updated_at = NOW()
            RETURNING id, website_id AS "websiteId", status
            """,
            (website_id,),
        ).fetchone()
        conn.execute(
            "UPDATE websites SET status = 'scanning', updated_at = NOW() WHERE id = %s",
            (website_id,),
        )
    return {"message": "Đã đưa website vào hàng đợi quét.", "job": job}
