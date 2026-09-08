from fastapi import APIRouter
from psycopg.errors import ForeignKeyViolation, UniqueViolation

from ..core.responses import message
from ..database import connection
from .schemas import WebsiteCreate
from .utils import normalize_website_address


router = APIRouter(prefix="/api/websites", tags=["Websites"])


@router.get("")
def list_websites():
    with connection() as conn:
        websites = conn.execute(
            """
            SELECT w.id, w.domain, w.url, w.status,
              w.performance_score AS "performanceScore",
              (SELECT mc.performance_score FROM monitoring_checks mc
                WHERE mc.website_id = w.id AND mc.check_type = 'pagespeed-mobile'
                ORDER BY mc.checked_at DESC LIMIT 1) AS "mobilePerformanceScore",
              (SELECT mc.performance_score FROM monitoring_checks mc
                WHERE mc.website_id = w.id AND mc.check_type = 'pagespeed-desktop'
                ORDER BY mc.checked_at DESC LIMIT 1) AS "desktopPerformanceScore",
              w.uptime_percent::float AS "uptimePercent",
              w.ssl_expires_at AS "sslExpiresAt",
              w.last_checked_at AS "lastCheckedAt",
              c.name AS "customerName"
            FROM websites w JOIN customers c ON c.id = w.customer_id
            ORDER BY w.created_at ASC
            """
        ).fetchall()
    return {"websites": websites}


@router.post("", status_code=201)
def create_website(payload: WebsiteCreate):
    address = normalize_website_address(payload.domain)
    customer_id = payload.customerId
    if not address or not customer_id or customer_id <= 0:
        return message("Khách hàng, tên miền hoặc URL không hợp lệ.", 400)
    domain, website_url = address
    try:
        with connection() as conn:
            if not conn.execute("SELECT id FROM customers WHERE id = %s", (customer_id,)).fetchone():
                return message("Không tìm thấy khách hàng đã chọn.", 404)
            website = conn.execute(
                """
                INSERT INTO websites
                  (customer_id, domain, url, status, performance_score, uptime_percent, last_checked_at)
                VALUES (%s, %s, %s, 'scanning', NULL, 0, NULL)
                RETURNING id, domain, url, status
                """,
                (customer_id, domain, website_url),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO scan_jobs (website_id, status, scheduled_at)
                VALUES (%s, 'queued', NOW())
                ON CONFLICT (website_id) DO UPDATE SET
                  status = 'queued', scheduled_at = NOW(), updated_at = NOW()
                """,
                (website["id"],),
            )
        return {"website": website}
    except UniqueViolation:
        return message("URL này đã tồn tại.", 409)
    except ForeignKeyViolation:
        return message("Không tìm thấy khách hàng đã chọn.", 404)
    except Exception:
        return message("Không thể thêm website.", 500)


@router.get("/{website_id}")
def website_detail(website_id: int):
    if website_id <= 0:
        return message("Website không hợp lệ.", 400)
    with connection() as conn:
        website = conn.execute(
            """
            SELECT w.id, w.domain, w.url, w.platform, w.status,
              w.performance_score AS "performanceScore",
              w.uptime_percent::float AS "uptimePercent",
              w.ssl_expires_at AS "sslExpiresAt",
              w.last_checked_at AS "lastCheckedAt",
              c.id AS "customerId", c.name AS "customerName",
              c.contact_name AS "contactName", c.contact_email AS "contactEmail"
            FROM websites w JOIN customers c ON c.id = w.customer_id
            WHERE w.id = %s
            """,
            (website_id,),
        ).fetchone()
        if not website:
            return message("Không tìm thấy website.", 404)
        checks = conn.execute(
            """
            SELECT id, check_type AS "checkType", status,
              response_time_ms AS "responseTimeMs",
              performance_score AS "performanceScore",
              lcp_seconds::float AS "lcpSeconds", cls_score::float AS "clsScore",
              details, checked_at AS "checkedAt"
            FROM monitoring_checks WHERE website_id = %s
            ORDER BY checked_at DESC LIMIT 60
            """,
            (website_id,),
        ).fetchall()
        job = conn.execute(
            """
            SELECT status, attempts, started_at AS "startedAt",
              completed_at AS "completedAt", last_error AS "lastError"
            FROM scan_jobs WHERE website_id = %s
            """,
            (website_id,),
        ).fetchone()
    return {"website": website, "checks": checks, "job": job}
