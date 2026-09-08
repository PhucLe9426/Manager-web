from ..database import connection


def list_all() -> list[dict]:
    with connection() as conn:
        return conn.execute(
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
              w.ssl_expires_at AS "sslExpiresAt", w.last_checked_at AS "lastCheckedAt",
              c.name AS "customerName"
            FROM websites w JOIN customers c ON c.id = w.customer_id
            ORDER BY w.created_at ASC
            """
        ).fetchall()


def customer_exists(customer_id: int) -> bool:
    with connection() as conn:
        return bool(conn.execute("SELECT id FROM customers WHERE id = %s", (customer_id,)).fetchone())


def create(customer_id: int, domain: str, website_url: str) -> dict:
    with connection() as conn:
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
    return website


def get_detail(website_id: int) -> dict | None:
    with connection() as conn:
        website = conn.execute(
            """
            SELECT w.id, w.domain, w.url, w.platform, w.status,
              w.performance_score AS "performanceScore",
              w.uptime_percent::float AS "uptimePercent",
              w.ssl_expires_at AS "sslExpiresAt", w.last_checked_at AS "lastCheckedAt",
              c.id AS "customerId", c.name AS "customerName",
              c.contact_name AS "contactName", c.contact_email AS "contactEmail"
            FROM websites w JOIN customers c ON c.id = w.customer_id
            WHERE w.id = %s
            """,
            (website_id,),
        ).fetchone()
        if not website:
            return None
        checks = conn.execute(
            """
            SELECT id, check_type AS "checkType", status,
              response_time_ms AS "responseTimeMs", performance_score AS "performanceScore",
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
        activities = conn.execute(
            """
            SELECT * FROM (
              SELECT 'monitoring-' || id::text AS "activityId", check_type AS "checkType",
                status, response_time_ms AS "responseTimeMs",
                performance_score AS "performanceScore", details,
                checked_at AS "checkedAt"
              FROM monitoring_checks WHERE website_id = %s
              UNION ALL
              SELECT 'plugin-' || id::text, 'plugin-security', 'ok',
                NULL::integer, NULL::smallint, summary, checked_at
              FROM wordpress_security_scans WHERE website_id = %s
              UNION ALL
              SELECT 'malware-' || id::text, 'malware-' || scan_type,
                CASE WHEN status = 'completed' THEN 'ok' WHEN status = 'failed' THEN 'error' ELSE status END,
                NULL::integer, NULL::smallint,
                jsonb_build_object(
                  'totalFiles', total_files, 'scannedFiles', scanned_files,
                  'danger', danger_count, 'warning', warning_count,
                  'info', info_count, 'error', last_error
                ), COALESCE(completed_at, updated_at)
              FROM malware_scans WHERE website_id = %s
            ) activity
            ORDER BY "checkedAt" DESC LIMIT 100
            """,
            (website_id, website_id, website_id),
        ).fetchall()
    return {"website": website, "checks": checks, "activities": activities, "job": job}
