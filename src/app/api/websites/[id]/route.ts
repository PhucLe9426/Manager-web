import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/db";
import { ensureScanQueueSchema } from "@/lib/scan-queue";

export const dynamic = "force-dynamic";

export async function GET(_request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const websiteId = Number(id);
  if (!Number.isInteger(websiteId) || websiteId <= 0) {
    return NextResponse.json({ message: "Website không hợp lệ." }, { status: 400 });
  }

  await ensureScanQueueSchema();
  const [website] = await sql`
    SELECT
      w.id, w.domain, w.url, w.platform, w.status,
      w.performance_score AS "performanceScore",
      w.uptime_percent::float AS "uptimePercent",
      w.ssl_expires_at AS "sslExpiresAt",
      w.last_checked_at AS "lastCheckedAt",
      c.id AS "customerId", c.name AS "customerName",
      c.contact_name AS "contactName", c.contact_email AS "contactEmail"
    FROM websites w
    JOIN customers c ON c.id = w.customer_id
    WHERE w.id = ${websiteId}
  `;
  if (!website) return NextResponse.json({ message: "Không tìm thấy website." }, { status: 404 });

  const checks = await sql`
    SELECT
      id, check_type AS "checkType", status,
      response_time_ms AS "responseTimeMs",
      performance_score AS "performanceScore",
      lcp_seconds::float AS "lcpSeconds",
      cls_score::float AS "clsScore",
      details, checked_at AS "checkedAt"
    FROM monitoring_checks
    WHERE website_id = ${websiteId}
    ORDER BY checked_at DESC
    LIMIT 60
  `;
  const [job] = await sql`
    SELECT status, attempts, started_at AS "startedAt", completed_at AS "completedAt", last_error AS "lastError"
    FROM scan_jobs WHERE website_id = ${websiteId}
  `;

  return NextResponse.json({ website, checks, job: job ?? null });
}
