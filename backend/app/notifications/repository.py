from ..database import connection


def create_notification(
    event_key: str,
    category: str,
    severity: str,
    title: str,
    message: str,
    website_id: int | None = None,
    link: str | None = None,
) -> dict | None:
    with connection() as conn:
        return conn.execute(
            """
            INSERT INTO notifications
              (website_id, event_key, category, severity, title, message, link)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_key) DO NOTHING
            RETURNING id, website_id AS "websiteId", category, severity, title,
              message, link, is_read AS "isRead", created_at AS "createdAt"
            """,
            (website_id, event_key, category, severity, title, message, link),
        ).fetchone()


def list_recent(limit: int) -> dict:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT n.id, n.website_id AS "websiteId", n.category, n.severity,
              n.title, n.message, n.link, n.is_read AS "isRead",
              n.created_at AS "createdAt", w.domain
            FROM notifications n LEFT JOIN websites w ON w.id = n.website_id
            ORDER BY n.created_at DESC LIMIT %s
            """,
            (limit,),
        ).fetchall()
        unread = conn.execute(
            "SELECT COUNT(*)::int AS total FROM notifications WHERE is_read = FALSE"
        ).fetchone()["total"]
    return {"notifications": rows, "unreadCount": unread}


def get_by_event_key(event_key: str) -> dict | None:
    with connection() as conn:
        return conn.execute(
            """
            SELECT id, website_id AS "websiteId", category, severity, title,
              message, link, is_read AS "isRead", created_at AS "createdAt"
            FROM notifications WHERE event_key = %s
            """,
            (event_key,),
        ).fetchone()


def mark_read(notification_id: int) -> dict | None:
    with connection() as conn:
        return conn.execute(
            """
            UPDATE notifications SET is_read = TRUE, read_at = COALESCE(read_at, NOW())
            WHERE id = %s RETURNING id, is_read AS "isRead"
            """,
            (notification_id,),
        ).fetchone()


def mark_all_read() -> int:
    with connection() as conn:
        result = conn.execute(
            """
            UPDATE notifications SET is_read = TRUE, read_at = COALESCE(read_at, NOW())
            WHERE is_read = FALSE
            """
        )
    return result.rowcount
