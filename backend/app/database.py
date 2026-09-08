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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS malware_scans (
              id BIGSERIAL PRIMARY KEY,
              website_id BIGINT NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
              scan_type VARCHAR(20) NOT NULL DEFAULT 'quick',
              status VARCHAR(30) NOT NULL DEFAULT 'queued',
              cursor_position INTEGER NOT NULL DEFAULT 0,
              total_files INTEGER NOT NULL DEFAULT 0,
              scanned_files INTEGER NOT NULL DEFAULT 0,
              skipped_files INTEGER NOT NULL DEFAULT 0,
              info_count INTEGER NOT NULL DEFAULT 0,
              warning_count INTEGER NOT NULL DEFAULT 0,
              danger_count INTEGER NOT NULL DEFAULT 0,
              agent_version VARCHAR(30),
              rules_version VARCHAR(30),
              summary JSONB NOT NULL DEFAULT '{}'::jsonb,
              last_error TEXT,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              started_at TIMESTAMPTZ,
              completed_at TIMESTAMPTZ,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_malware_scans_queue
            ON malware_scans(status, created_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_malware_scans_website_time
            ON malware_scans(website_id, created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS malware_findings (
              id BIGSERIAL PRIMARY KEY,
              scan_id BIGINT NOT NULL REFERENCES malware_scans(id) ON DELETE CASCADE,
              website_id BIGINT NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
              file_path TEXT NOT NULL,
              file_hash VARCHAR(64),
              component VARCHAR(40) NOT NULL DEFAULT 'unknown',
              rule_code VARCHAR(80) NOT NULL,
              severity VARCHAR(20) NOT NULL,
              title VARCHAR(240) NOT NULL,
              message TEXT NOT NULL,
              line_number INTEGER,
              snippet TEXT,
              status VARCHAR(30) NOT NULL DEFAULT 'open',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              UNIQUE (scan_id, file_path, rule_code, line_number)
            )
            """
        )
        conn.execute(
            "ALTER TABLE malware_findings ADD COLUMN IF NOT EXISTS component VARCHAR(40) NOT NULL DEFAULT 'unknown'"
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_malware_findings_scan_severity
            ON malware_findings(scan_id, severity, status)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS file_baselines (
              id BIGSERIAL PRIMARY KEY,
              website_id BIGINT NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
              file_path TEXT NOT NULL,
              file_hash VARCHAR(64) NOT NULL,
              source VARCHAR(40) NOT NULL DEFAULT 'internal',
              component VARCHAR(190),
              component_version VARCHAR(80),
              approved_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
              approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              UNIQUE (website_id, file_path)
            )
            """
        )
