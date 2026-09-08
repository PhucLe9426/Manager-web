from ..database import connection


def queue_all() -> tuple[int, int]:
    with connection() as conn:
        total = conn.execute("SELECT COUNT(*)::int AS total FROM websites").fetchone()["total"]
        if total == 0:
            return 0, 0
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
    return total, queued


def queue_one(website_id: int) -> dict | None:
    with connection() as conn:
        if not conn.execute("SELECT id FROM websites WHERE id = %s", (website_id,)).fetchone():
            return None
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
    return job
