import json

from ..database import connection


def list_all() -> list[dict]:
    with connection() as conn:
        return conn.execute(
            """
            SELECT r.id, r.title, r.period_start AS "periodStart",
              r.period_end AS "periodEnd", r.summary, r.created_at AS "createdAt",
              w.id AS "websiteId", w.domain, w.url,
              c.name AS "customerName", COUNT(ri.id)::int AS "itemCount",
              (SELECT COUNT(*)::int FROM report_item_attachments ria
                JOIN report_items item ON item.id = ria.report_item_id
                WHERE item.report_id = r.id) AS "attachmentCount"
            FROM reports r
            JOIN websites w ON w.id = r.website_id
            JOIN customers c ON c.id = w.customer_id
            LEFT JOIN report_items ri ON ri.report_id = r.id
            GROUP BY r.id, w.id, c.id
            ORDER BY r.created_at DESC
            """
        ).fetchall()


def website_exists(website_id: int) -> bool:
    with connection() as conn:
        return bool(conn.execute("SELECT id FROM websites WHERE id = %s", (website_id,)).fetchone())


def create(data: dict) -> dict:
    with connection() as conn:
        snapshot = _load_context(conn, data["websiteId"])
        report = conn.execute(
            """
            INSERT INTO reports (website_id, title, period_start, period_end, summary, system_snapshot)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, title, period_start AS "periodStart",
              period_end AS "periodEnd", summary, created_at AS "createdAt"
            """,
            (
                data["websiteId"], data["title"], data["periodStart"], data["periodEnd"],
                data["summary"], json.dumps(snapshot, default=str),
            ),
        ).fetchone()
        created_items = []
        for index, item in enumerate(data["items"]):
            created_item = conn.execute(
                """
                INSERT INTO report_items (report_id, performed_date, description, result, sort_order)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, performed_date AS "performedDate", description, result
                """,
                (report["id"], item["performedDate"], item["description"], item["result"], index),
            ).fetchone()
            created_items.append(created_item)
    return {**report, "items": created_items}


def item_belongs_to_report(report_id: int, item_id: int) -> bool:
    with connection() as conn:
        return bool(conn.execute(
            "SELECT id FROM report_items WHERE id = %s AND report_id = %s",
            (item_id, report_id),
        ).fetchone())


def attachment_count(item_id: int) -> int:
    with connection() as conn:
        return conn.execute(
            "SELECT COUNT(*)::int AS total FROM report_item_attachments WHERE report_item_id = %s",
            (item_id,),
        ).fetchone()["total"]


def create_attachment(item_id: int, original_name: str, stored_name: str, size_bytes: int) -> dict:
    with connection() as conn:
        return conn.execute(
            """
            INSERT INTO report_item_attachments
              (report_item_id, original_name, stored_name, mime_type, size_bytes)
            VALUES (%s, %s, %s, 'image/jpeg', %s)
            RETURNING id, original_name AS "originalName", stored_name AS "storedName",
              mime_type AS "mimeType", size_bytes AS "sizeBytes", created_at AS "createdAt"
            """,
            (item_id, original_name, stored_name, size_bytes),
        ).fetchone()


def _load_context(conn, website_id: int) -> dict:
    page_speed_row = conn.execute(
        """
        SELECT w.uptime_percent::float AS "uptimePercent",
          w.ssl_expires_at AS "sslExpiresAt",
          availability.response_time_ms AS "responseTimeMs",
          availability.checked_at AS "availabilityCheckedAt",
          mobile.performance_score AS "mobileScore",
          mobile.lcp_seconds::float AS "mobileLcpSeconds",
          mobile.cls_score::float AS "mobileClsScore",
          (mobile.details->>'fcpSeconds')::float AS "mobileFcpSeconds",
          mobile.checked_at AS "mobileCheckedAt",
          desktop.performance_score AS "desktopScore",
          desktop.lcp_seconds::float AS "desktopLcpSeconds",
          desktop.cls_score::float AS "desktopClsScore",
          (desktop.details->>'fcpSeconds')::float AS "desktopFcpSeconds",
          desktop.checked_at AS "desktopCheckedAt"
        FROM websites w
        LEFT JOIN LATERAL (
          SELECT response_time_ms, checked_at FROM monitoring_checks
          WHERE website_id = w.id AND check_type = 'availability'
          ORDER BY checked_at DESC LIMIT 1
        ) availability ON TRUE
        LEFT JOIN LATERAL (
          SELECT performance_score, lcp_seconds, cls_score, details, checked_at
          FROM monitoring_checks
          WHERE website_id = w.id AND check_type = 'pagespeed-mobile'
          ORDER BY checked_at DESC LIMIT 1
        ) mobile ON TRUE
        LEFT JOIN LATERAL (
          SELECT performance_score, lcp_seconds, cls_score, details, checked_at
          FROM monitoring_checks
          WHERE website_id = w.id AND check_type = 'pagespeed-desktop'
          ORDER BY checked_at DESC LIMIT 1
        ) desktop ON TRUE
        WHERE w.id = %s
        """,
        (website_id,),
    ).fetchone()
    plugin_row = conn.execute(
        """
        SELECT summary, results, checked_at AS "checkedAt"
        FROM wordpress_security_scans WHERE website_id = %s
        ORDER BY checked_at DESC LIMIT 1
        """,
        (website_id,),
    ).fetchone()
    seo_row = conn.execute(
        """
        SELECT summary, posts, checked_at AS "checkedAt"
        FROM wordpress_seo_scans WHERE website_id = %s
        ORDER BY checked_at DESC LIMIT 1
        """,
        (website_id,),
    ).fetchone()
    malware_row = conn.execute(
        """
        SELECT id, scan_type AS "scanType", status,
          total_files AS "totalFiles", scanned_files AS "scannedFiles",
          skipped_files AS "skippedFiles", info_count AS "infoCount",
          warning_count AS "warningCount", danger_count AS "dangerCount",
          agent_version AS "agentVersion", rules_version AS "rulesVersion",
          created_at AS "createdAt", started_at AS "startedAt",
          completed_at AS "completedAt", updated_at AS "updatedAt"
        FROM malware_scans WHERE website_id = %s
        ORDER BY created_at DESC LIMIT 1
        """,
        (website_id,),
    ).fetchone()
    malware_findings = []
    if malware_row:
        malware_findings = conn.execute(
            """
            SELECT file_path AS "filePath", component, severity, title, message, status
            FROM malware_findings
            WHERE scan_id = %s AND status <> 'false_positive'
            ORDER BY CASE severity WHEN 'danger' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END, id
            LIMIT 20
            """,
            (malware_row["id"],),
        ).fetchall()

    plugin_scan = None
    if plugin_row:
        plugin_results = plugin_row["results"] or {}
        plugin_scan = {
            **plugin_results,
            "summary": plugin_row["summary"] or plugin_results.get("summary", {}),
            "checkedAt": plugin_row["checkedAt"],
        }
    seo_scan = None
    if seo_row:
        seo_scan = {
            "summary": seo_row["summary"] or {},
            "posts": seo_row["posts"] or [],
            "checkedAt": seo_row["checkedAt"],
        }
    malware_scan = {**malware_row, "findings": malware_findings} if malware_row else None
    return {
        "pageSpeed": page_speed_row,
        "pluginScan": plugin_scan,
        "seoScan": seo_scan,
        "malwareScan": malware_scan,
    }


def get_context(website_id: int) -> dict | None:
    with connection() as conn:
        website = conn.execute("SELECT id FROM websites WHERE id = %s", (website_id,)).fetchone()
        if not website:
            return None
        return _load_context(conn, website_id)


def get_by_id(report_id: int) -> dict | None:
    with connection() as conn:
        report = conn.execute(
            """
            SELECT r.id, r.title, r.period_start AS "periodStart",
              r.period_end AS "periodEnd", r.summary, r.created_at AS "createdAt",
              r.system_snapshot AS "systemSnapshot",
              w.id AS "websiteId", w.domain, w.url,
              w.uptime_percent::float AS "uptimePercent", w.ssl_expires_at AS "sslExpiresAt",
              c.name AS "customerName", c.contact_name AS "contactName",
              c.contact_email AS "contactEmail", c.contact_phone AS "contactPhone",
              (SELECT mc.performance_score FROM monitoring_checks mc
                WHERE mc.website_id = w.id AND mc.check_type = 'pagespeed-mobile'
                ORDER BY mc.checked_at DESC LIMIT 1) AS "mobileScore",
              (SELECT mc.checked_at FROM monitoring_checks mc
                WHERE mc.website_id = w.id AND mc.check_type = 'pagespeed-mobile'
                ORDER BY mc.checked_at DESC LIMIT 1) AS "mobileCheckedAt",
              (SELECT mc.performance_score FROM monitoring_checks mc
                WHERE mc.website_id = w.id AND mc.check_type = 'pagespeed-desktop'
                ORDER BY mc.checked_at DESC LIMIT 1) AS "desktopScore",
              (SELECT mc.checked_at FROM monitoring_checks mc
                WHERE mc.website_id = w.id AND mc.check_type = 'pagespeed-desktop'
                ORDER BY mc.checked_at DESC LIMIT 1) AS "desktopCheckedAt"
            FROM reports r
            JOIN websites w ON w.id = r.website_id
            JOIN customers c ON c.id = w.customer_id
            WHERE r.id = %s
            """,
            (report_id,),
        ).fetchone()
        if not report:
            return None
        items = conn.execute(
            """
            SELECT id, performed_date AS "performedDate", description, result
            FROM report_items WHERE report_id = %s ORDER BY sort_order, id
            """,
            (report_id,),
        ).fetchall()
        attachments = conn.execute(
            """
            SELECT ria.id, ria.report_item_id AS "reportItemId",
              ria.original_name AS "originalName", ria.stored_name AS "storedName",
              ria.mime_type AS "mimeType", ria.size_bytes AS "sizeBytes"
            FROM report_item_attachments ria
            JOIN report_items ri ON ri.id = ria.report_item_id
            WHERE ri.report_id = %s ORDER BY ria.created_at, ria.id
            """,
            (report_id,),
        ).fetchall()
        attachments_by_item: dict[int, list[dict]] = {}
        for attachment in attachments:
            attachments_by_item.setdefault(attachment["reportItemId"], []).append(attachment)
        for item in items:
            item["attachments"] = attachments_by_item.get(item["id"], [])
        stored_context = report.pop("systemSnapshot", None)
        context = stored_context or _load_context(conn, report["websiteId"])
    return {**report, "items": items, **context}


def delete(report_id: int) -> bool:
    with connection() as conn:
        return conn.execute("DELETE FROM reports WHERE id = %s RETURNING id", (report_id,)).fetchone() is not None


def attachment_names_for_report(report_id: int) -> list[str]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT ria.stored_name AS "storedName"
            FROM report_item_attachments ria
            JOIN report_items ri ON ri.id = ria.report_item_id
            WHERE ri.report_id = %s
            """,
            (report_id,),
        ).fetchall()
    return [row["storedName"] for row in rows]
