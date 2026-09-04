import json
import re
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from psycopg.errors import ForeignKeyViolation, UniqueViolation

from .database import close_pool, connection, ensure_scan_queue_schema, open_pool
from .schemas import (
    CustomerCreate,
    CustomerUpdate,
    WebsiteCreate,
    WordPressConnectionCreate,
    WordPressPluginUpdate,
)
from .wordpress import (
    WordPressError,
    decrypt_password,
    encrypt_password,
    get_inventory,
    run_plugin_security_scan,
    update_plugin_status,
    verify_connection,
)


DOMAIN_PATTERN = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$", re.IGNORECASE)


def message(text: str, status_code: int) -> JSONResponse:
    return JSONResponse({"message": text}, status_code=status_code)


def normalize_website_address(value: str | None) -> tuple[str, str] | None:
    raw_value = (value or "").strip()
    if not raw_value:
        return None

    candidate = raw_value if re.match(r"^https?://", raw_value, re.IGNORECASE) else f"https://{raw_value}"
    try:
        parsed = urlsplit(candidate)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        if (
            parsed.scheme.lower() not in ("http", "https")
            or parsed.username
            or parsed.password
            or not DOMAIN_PATTERN.fullmatch(hostname)
        ):
            return None
        port = parsed.port
    except ValueError:
        return None

    netloc = hostname if port is None else f"{hostname}:{port}"
    normalized_url = urlunsplit(
        (parsed.scheme.lower(), netloc, parsed.path or "", parsed.query, "")
    )
    return hostname, normalized_url


@asynccontextmanager
async def lifespan(_: FastAPI):
    open_pool()
    ensure_scan_queue_schema()
    yield
    close_pool()


app = FastAPI(title="SiteOps API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/api/health")
def health():
    try:
        with connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "database": "connected"}
    except Exception:
        return message("Không thể kết nối cơ sở dữ liệu.", 503)


@app.get("/api/customers")
def list_customers():
    with connection() as conn:
        customers = conn.execute(
            """
            SELECT c.id, c.name,
              c.contact_name AS "contactName",
              c.contact_email AS "contactEmail",
              c.contact_phone AS "contactPhone",
              c.status,
              COUNT(w.id)::int AS "websiteCount"
            FROM customers c
            LEFT JOIN websites w ON w.customer_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        ).fetchall()
    return {"customers": customers}


@app.post("/api/customers", status_code=201)
def create_customer(payload: CustomerCreate):
    name = (payload.name or "").strip()
    if not name:
        return message("Tên công ty không được để trống.", 400)

    with connection() as conn:
        customer = conn.execute(
            """
            INSERT INTO customers (name, contact_name, contact_email, contact_phone)
            VALUES (%s, %s, %s, %s)
            RETURNING id, name
            """,
            (
                name,
                (payload.contactName or "").strip() or None,
                (payload.contactEmail or "").strip() or None,
                (payload.contactPhone or "").strip() or None,
            ),
        ).fetchone()
    return {"customer": customer}


@app.patch("/api/customers/{customer_id}")
def update_customer(customer_id: int, payload: CustomerUpdate):
    if customer_id <= 0:
        return message("Khách hàng không hợp lệ.", 400)

    name = (payload.name or "").strip()
    if not name or payload.status not in ("active", "paused"):
        return message("Thông tin khách hàng không hợp lệ.", 400)

    with connection() as conn:
        customer = conn.execute(
            """
            UPDATE customers SET
              name = %s,
              contact_name = %s,
              contact_email = %s,
              contact_phone = %s,
              status = %s,
              updated_at = NOW()
            WHERE id = %s
            RETURNING id, name
            """,
            (
                name,
                (payload.contactName or "").strip() or None,
                (payload.contactEmail or "").strip() or None,
                (payload.contactPhone or "").strip() or None,
                payload.status,
                customer_id,
            ),
        ).fetchone()
    if not customer:
        return message("Không tìm thấy khách hàng.", 404)
    return {"customer": customer, "message": "Đã cập nhật khách hàng."}


@app.get("/api/websites")
def list_websites():
    with connection() as conn:
        websites = conn.execute(
            """
            SELECT w.id, w.domain, w.url, w.status,
              w.performance_score AS "performanceScore",
              (
                SELECT mc.performance_score FROM monitoring_checks mc
                WHERE mc.website_id = w.id AND mc.check_type = 'pagespeed-mobile'
                ORDER BY mc.checked_at DESC LIMIT 1
              ) AS "mobilePerformanceScore",
              (
                SELECT mc.performance_score FROM monitoring_checks mc
                WHERE mc.website_id = w.id AND mc.check_type = 'pagespeed-desktop'
                ORDER BY mc.checked_at DESC LIMIT 1
              ) AS "desktopPerformanceScore",
              w.uptime_percent::float AS "uptimePercent",
              w.ssl_expires_at AS "sslExpiresAt",
              w.last_checked_at AS "lastCheckedAt",
              c.name AS "customerName"
            FROM websites w
            JOIN customers c ON c.id = w.customer_id
            ORDER BY w.created_at ASC
            """
        ).fetchall()
    return {"websites": websites}


@app.post("/api/websites", status_code=201)
def create_website(payload: WebsiteCreate):
    address = normalize_website_address(payload.domain)
    customer_id = payload.customerId
    if not address or not customer_id or customer_id <= 0:
        return message("Khách hàng, tên miền hoặc URL không hợp lệ.", 400)
    domain, website_url = address

    try:
        with connection() as conn:
            customer = conn.execute(
                "SELECT id FROM customers WHERE id = %s", (customer_id,)
            ).fetchone()
            if not customer:
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


@app.post("/api/websites/scan-all")
def queue_all_website_scans():
    with connection() as conn:
        total = conn.execute("SELECT COUNT(*)::int AS total FROM websites").fetchone()["total"]
        if total == 0:
            return {"message": "Chưa có website để quét.", "total": 0, "queued": 0}

        conn.execute(
            """
            INSERT INTO scan_jobs
              (website_id, status, scheduled_at, attempts, last_error, updated_at)
            SELECT id, 'queued', NOW(), 0, NULL, NOW()
            FROM websites
            WHERE TRUE
            ON CONFLICT (website_id) DO UPDATE SET
              status = 'queued', scheduled_at = NOW(), attempts = 0,
              last_error = NULL, completed_at = NULL, updated_at = NOW()
            WHERE scan_jobs.status <> 'running'
            """
        )
        conn.execute(
            """
            UPDATE websites
            SET status = 'scanning', updated_at = NOW()
            WHERE id IN (
              SELECT website_id FROM scan_jobs WHERE status IN ('queued', 'running')
            )
            """
        )
        queued = conn.execute(
            """
            SELECT COUNT(*)::int AS total
            FROM scan_jobs
            WHERE status IN ('queued', 'running')
              AND website_id IN (SELECT id FROM websites)
            """
        ).fetchone()["total"]

    return {
        "message": f"Đã đưa {total} website vào hàng đợi quét.",
        "total": total,
        "queued": queued,
    }


@app.get("/api/websites/{website_id}")
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
            FROM websites w
            JOIN customers c ON c.id = w.customer_id
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
              lcp_seconds::float AS "lcpSeconds",
              cls_score::float AS "clsScore",
              details, checked_at AS "checkedAt"
            FROM monitoring_checks
            WHERE website_id = %s
            ORDER BY checked_at DESC
            LIMIT 60
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


@app.post("/api/websites/{website_id}/scan")
def queue_website_scan(website_id: int):
    if website_id <= 0:
        return message("Website không hợp lệ.", 400)

    with connection() as conn:
        website = conn.execute(
            "SELECT id FROM websites WHERE id = %s", (website_id,)
        ).fetchone()
        if not website:
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


@app.get("/api/websites/{website_id}/wordpress")
def wordpress_inventory(website_id: int):
    with connection() as conn:
        website = conn.execute(
            """
            SELECT url, wp_username AS "username",
              wp_application_password AS "encryptedPassword",
              wp_connected_at AS "connectedAt"
            FROM websites WHERE id = %s
            """,
            (website_id,),
        ).fetchone()

    if not website:
        return message("Không tìm thấy website.", 404)
    if not website["username"] or not website["encryptedPassword"]:
        return {"connected": False, "plugins": [], "themes": []}

    try:
        inventory = get_inventory(
            website["url"],
            website["username"],
            decrypt_password(website["encryptedPassword"]),
        )
        return {
            "connected": True,
            "username": website["username"],
            "connectedAt": website["connectedAt"],
            **inventory,
        }
    except WordPressError as error:
        return message(str(error), error.status_code)


@app.post("/api/websites/{website_id}/wordpress/connection")
def connect_wordpress(website_id: int, payload: WordPressConnectionCreate):
    username = (payload.username or "").strip()
    password = (payload.applicationPassword or "").replace(" ", "").strip()
    if not username or not password:
        return message("Hãy nhập tên đăng nhập và Application Password.", 400)

    with connection() as conn:
        website = conn.execute(
            "SELECT id, url FROM websites WHERE id = %s", (website_id,)
        ).fetchone()
    if not website:
        return message("Không tìm thấy website.", 404)

    try:
        profile = verify_connection(website["url"], username, password)
    except WordPressError as error:
        return message(str(error), error.status_code)

    with connection() as conn:
        conn.execute(
            """
            UPDATE websites SET wp_username = %s, wp_application_password = %s,
              wp_connected_at = NOW(), updated_at = NOW()
            WHERE id = %s
            """,
            (username, encrypt_password(password), website_id),
        )
        conn.execute(
            """
            INSERT INTO audit_logs (action, entity_type, entity_id, metadata)
            VALUES ('wordpress.connected', 'website', %s, %s::jsonb)
            """,
            (str(website_id), json.dumps({"source": "application-password"})),
        )
    return {
        "message": "Đã kết nối WordPress thành công.",
        "profile": {"id": profile.get("id"), "name": profile.get("name")},
    }


@app.delete("/api/websites/{website_id}/wordpress/connection")
def disconnect_wordpress(website_id: int):
    with connection() as conn:
        website = conn.execute(
            """
            UPDATE websites SET wp_username = NULL, wp_application_password = NULL,
              wp_connected_at = NULL, updated_at = NOW()
            WHERE id = %s RETURNING id
            """,
            (website_id,),
        ).fetchone()
        if not website:
            return message("Không tìm thấy website.", 404)
        conn.execute(
            """
            INSERT INTO audit_logs (action, entity_type, entity_id)
            VALUES ('wordpress.disconnected', 'website', %s)
            """,
            (str(website_id),),
        )
    return {"message": "Đã ngắt kết nối WordPress."}


@app.patch("/api/websites/{website_id}/wordpress/plugin")
def change_wordpress_plugin(website_id: int, payload: WordPressPluginUpdate):
    plugin = (payload.plugin or "").strip()
    if not plugin:
        return message("Plugin không hợp lệ.", 400)

    with connection() as conn:
        website = conn.execute(
            """
            SELECT url, wp_username AS "username",
              wp_application_password AS "encryptedPassword"
            FROM websites WHERE id = %s
            """,
            (website_id,),
        ).fetchone()
    if not website:
        return message("Không tìm thấy website.", 404)
    if not website["username"] or not website["encryptedPassword"]:
        return message("Website chưa kết nối WordPress.", 409)

    try:
        result = update_plugin_status(
            website["url"],
            website["username"],
            decrypt_password(website["encryptedPassword"]),
            plugin,
            payload.status,
        )
    except WordPressError as error:
        return message(str(error), error.status_code)

    with connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_logs (action, entity_type, entity_id, metadata)
            VALUES ('wordpress.plugin_status_changed', 'website', %s, %s::jsonb)
            """,
            (
                str(website_id),
                json.dumps({"plugin": plugin, "status": payload.status}),
            ),
        )
    return {"message": "Đã cập nhật trạng thái plugin.", "plugin": result}


@app.post("/api/websites/{website_id}/wordpress/security-scan")
def scan_wordpress_plugins(website_id: int):
    with connection() as conn:
        website = conn.execute(
            """
            SELECT url, wp_username AS "username",
              wp_application_password AS "encryptedPassword"
            FROM websites WHERE id = %s
            """,
            (website_id,),
        ).fetchone()
    if not website:
        return message("Không tìm thấy website.", 404)
    if not website["username"] or not website["encryptedPassword"]:
        return message("Website chưa kết nối WordPress.", 409)

    try:
        result = run_plugin_security_scan(
            website["url"],
            website["username"],
            decrypt_password(website["encryptedPassword"]),
        )
    except WordPressError as error:
        if error.status_code == 404:
            return message(
                "Chưa cài hoặc chưa kích hoạt SiteOps Agent trên website WordPress.",
                404,
            )
        return message(str(error), error.status_code)

    with connection() as conn:
        saved = conn.execute(
            """
            INSERT INTO wordpress_security_scans (website_id, summary, results, checked_at)
            VALUES (%s, %s::jsonb, %s::jsonb, NOW())
            RETURNING id, checked_at AS "checkedAt"
            """,
            (
                website_id,
                json.dumps(result.get("summary", {})),
                json.dumps(result),
            ),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO audit_logs (action, entity_type, entity_id, metadata)
            VALUES ('wordpress.security_scan', 'website', %s, %s::jsonb)
            """,
            (str(website_id), json.dumps(result.get("summary", {}))),
        )
    return {"scan": {**result, **saved}}


@app.get("/api/websites/{website_id}/wordpress/security-scan/latest")
def latest_wordpress_security_scan(website_id: int):
    with connection() as conn:
        website = conn.execute(
            "SELECT id FROM websites WHERE id = %s", (website_id,)
        ).fetchone()
        if not website:
            return message("Không tìm thấy website.", 404)
        scan = conn.execute(
            """
            SELECT id, results, checked_at AS "checkedAt"
            FROM wordpress_security_scans
            WHERE website_id = %s
            ORDER BY checked_at DESC LIMIT 1
            """,
            (website_id,),
        ).fetchone()
    return {"scan": scan}
