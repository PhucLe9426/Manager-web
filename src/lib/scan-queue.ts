import { sql } from "@/lib/db";

export async function ensureScanQueueSchema() {
  await sql`
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
  `;
  await sql`CREATE INDEX IF NOT EXISTS idx_scan_jobs_queue ON scan_jobs(status, scheduled_at)`;
  await sql`CREATE INDEX IF NOT EXISTS idx_checks_website_type_time ON monitoring_checks(website_id, check_type, checked_at DESC)`;
}

export async function queueWebsiteScan(websiteId: number) {
  await ensureScanQueueSchema();
  const [job] = await sql`
    INSERT INTO scan_jobs (website_id, status, scheduled_at, attempts, last_error, updated_at)
    VALUES (${websiteId}, 'queued', NOW(), 0, NULL, NOW())
    ON CONFLICT (website_id) DO UPDATE SET
      status = 'queued',
      scheduled_at = NOW(),
      attempts = 0,
      last_error = NULL,
      updated_at = NOW()
    RETURNING id, website_id AS "websiteId", status
  `;
  await sql`UPDATE websites SET status = 'scanning', updated_at = NOW() WHERE id = ${websiteId}`;
  return job;
}
