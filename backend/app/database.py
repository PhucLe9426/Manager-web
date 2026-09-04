import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgres://siteops:siteops_dev_change@localhost:5432/siteops",
)

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=10,
    open=False,
    kwargs={"row_factory": dict_row},
)


def open_pool() -> None:
    pool.open(wait=True, timeout=30)


def close_pool() -> None:
    pool.close()


@contextmanager
def connection():
    with pool.connection() as conn:
        yield conn


def ensure_scan_queue_schema() -> None:
    with connection() as conn:
        conn.execute(
            "ALTER TABLE websites ADD COLUMN IF NOT EXISTS wp_username VARCHAR(190)"
        )
        conn.execute(
            "ALTER TABLE websites ADD COLUMN IF NOT EXISTS wp_application_password TEXT"
        )
        conn.execute(
            "ALTER TABLE websites ADD COLUMN IF NOT EXISTS wp_connected_at TIMESTAMPTZ"
        )
        # Cho phép theo dõi nhiều URL/trang khác nhau trên cùng một tên miền.
        conn.execute(
            "ALTER TABLE websites DROP CONSTRAINT IF EXISTS websites_domain_key"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_websites_url ON websites(url)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_websites_domain ON websites(domain)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_jobs (
              id BIGSERIAL PRIMARY KEY,
              website_id BIGINT NOT NULL UNIQUE REFERENCES websites(id) ON DELETE CASCADE,
              status VARCHAR(30) NOT NULL DEFAULT 'queued',
              attempts INTEGER NOT NULL DEFAULT 0,
              scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              started_at TIMESTAMPTZ,
              completed_at TIMESTAMPTZ,
              last_error TEXT,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_scan_jobs_queue ON scan_jobs(status, scheduled_at)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wordpress_security_scans (
              id BIGSERIAL PRIMARY KEY,
              website_id BIGINT NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
              summary JSONB NOT NULL DEFAULT '{}'::jsonb,
              results JSONB NOT NULL DEFAULT '{}'::jsonb,
              checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wp_security_scans_website_time
            ON wordpress_security_scans(website_id, checked_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_checks_website_type_time
            ON monitoring_checks(website_id, check_type, checked_at DESC)
            """
        )
