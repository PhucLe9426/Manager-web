import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/db";
import { ensureScanQueueSchema } from "@/lib/scan-queue";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const rows = await sql`
      SELECT
        w.id,
        w.domain,
        w.url,
        w.status,
        w.performance_score AS "performanceScore",
        (
          SELECT mc.performance_score FROM monitoring_checks mc
          WHERE mc.website_id = w.id AND mc.check_type = 'pagespeed-mobile'
          ORDER BY mc.checked_at DESC LIMIT 1
        ) AS "mobilePerformanceScore",
        (
          SELECT mc.performance_score FROM monitoring_checks mc
          WHERE mc.website_id = w.id AND mc.check_type = 'pagespeed-desktop'
          ORDER BY mc.checked_at DESC LIMIT 1
        ) AS "desktopPerformanceScore",
        w.uptime_percent::float AS "uptimePercent",
        w.ssl_expires_at AS "sslExpiresAt",
        w.last_checked_at AS "lastCheckedAt",
        c.name AS "customerName"
      FROM websites w
      JOIN customers c ON c.id = w.customer_id
      ORDER BY w.created_at ASC
    `;
    return NextResponse.json({ websites: rows });
  } catch (error) {
    console.error(error);
    return NextResponse.json({ message: "Không thể tải danh sách website." }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    await ensureScanQueueSchema();
    const body = (await request.json()) as { domain?: string; customerId?: number };
    const domain = body.domain?.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/\/$/, "");
    const customerId = Number(body.customerId);

    if (!domain || !Number.isInteger(customerId) || customerId <= 0 || !/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(domain)) {
      return NextResponse.json({ message: "Khách hàng hoặc tên miền không hợp lệ." }, { status: 400 });
    }

    const website = await sql.begin(async (transaction) => {
      const [customer] = await transaction`SELECT id FROM customers WHERE id = ${customerId}`;
      if (!customer) throw new Error("CUSTOMER_NOT_FOUND");
      const [created] = await transaction`
        INSERT INTO websites (customer_id, domain, url, status, performance_score, uptime_percent, last_checked_at)
        VALUES (${customerId}, ${domain}, ${`https://${domain}`}, 'scanning', NULL, 0, NULL)
        RETURNING id, domain, url, status
      `;
      await transaction`
        INSERT INTO scan_jobs (website_id, status, scheduled_at)
        VALUES (${created.id}, 'queued', NOW())
        ON CONFLICT (website_id) DO UPDATE SET status = 'queued', scheduled_at = NOW(), updated_at = NOW()
      `;
      return created;
    });

    return NextResponse.json({ website }, { status: 201 });
  } catch (error) {
    if (error instanceof Error && error.message === "CUSTOMER_NOT_FOUND") {
      return NextResponse.json({ message: "Không tìm thấy khách hàng đã chọn." }, { status: 404 });
    }
    if (typeof error === "object" && error && "code" in error && error.code === "23505") {
      return NextResponse.json({ message: "Tên miền này đã tồn tại." }, { status: 409 });
    }
    console.error(error);
    return NextResponse.json({ message: "Không thể thêm website." }, { status: 500 });
  }
}
