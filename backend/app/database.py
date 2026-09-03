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
            CREATE INDEX IF NOT EXISTS idx_checks_website_type_time
            ON monitoring_checks(website_id, check_type, checked_at DESC)
            """
        )

