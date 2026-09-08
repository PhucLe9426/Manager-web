import json

from ..database import connection


def get_website_connection(website_id: int) -> dict | None:
    with connection() as conn:
        return conn.execute(
            """
            SELECT id, url, wp_username AS "username",
              wp_application_password AS "encryptedPassword",
              wp_connected_at AS "connectedAt"
            FROM websites WHERE id = %s
            """,
            (website_id,),
        ).fetchone()


def save_connection(website_id: int, username: str, encrypted_password: str) -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE websites SET wp_username = %s, wp_application_password = %s,
              wp_connected_at = NOW(), updated_at = NOW() WHERE id = %s
            """,
            (username, encrypted_password, website_id),
        )
        add_audit(conn, "wordpress.connected", website_id, {"source": "application-password"})


def clear_connection(website_id: int) -> bool:
    with connection() as conn:
        website = conn.execute(
            """
            UPDATE websites SET wp_username = NULL, wp_application_password = NULL,
              wp_connected_at = NULL, updated_at = NOW()
            WHERE id = %s RETURNING id
            """,
            (website_id,),
        ).fetchone()
        if website:
            add_audit(conn, "wordpress.disconnected", website_id)
    return bool(website)


def add_plugin_status_audit(website_id: int, plugin: str, status: str) -> None:
    with connection() as conn:
        add_audit(conn, "wordpress.plugin_status_changed", website_id, {"plugin": plugin, "status": status})


def save_security_scan(website_id: int, result: dict) -> dict:
    with connection() as conn:
        saved = conn.execute(
            """
            INSERT INTO wordpress_security_scans (website_id, summary, results, checked_at)
            VALUES (%s, %s::jsonb, %s::jsonb, NOW())
            RETURNING id, checked_at AS "checkedAt"
            """,
            (website_id, json.dumps(result.get("summary", {})), json.dumps(result)),
        ).fetchone()
        add_audit(conn, "wordpress.security_scan", website_id, result.get("summary", {}))
    return saved


def latest_security_scan(website_id: int) -> tuple[bool, dict | None]:
    with connection() as conn:
        exists = bool(conn.execute("SELECT id FROM websites WHERE id = %s", (website_id,)).fetchone())
        if not exists:
            return False, None
        scan = conn.execute(
            """
            SELECT id, results, checked_at AS "checkedAt"
            FROM wordpress_security_scans WHERE website_id = %s
            ORDER BY checked_at DESC LIMIT 1
            """,
            (website_id,),
        ).fetchone()
    return True, scan


def add_audit(conn, action: str, website_id: int, metadata: dict | None = None) -> None:
    if metadata is None:
        conn.execute(
            "INSERT INTO audit_logs (action, entity_type, entity_id) VALUES (%s, 'website', %s)",
            (action, str(website_id)),
        )
    else:
        conn.execute(
            """
            INSERT INTO audit_logs (action, entity_type, entity_id, metadata)
            VALUES (%s, 'website', %s, %s::jsonb)
            """,
            (action, str(website_id), json.dumps(metadata)),
        )
