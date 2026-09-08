import dns from "node:dns/promises";
import net from "node:net";
import tls from "node:tls";
import postgres from "postgres";

const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) throw new Error("Worker thiếu DATABASE_URL");

const sql = postgres(databaseUrl, { max: 4, connect_timeout: 10 });
const scanIntervalMinutes = Math.max(5, Number(process.env.SCAN_INTERVAL_MINUTES ?? 360));
const pageSpeedApiKey = process.env.PAGESPEED_API_KEY?.trim();
const backendInternalUrl = (process.env.BACKEND_INTERNAL_URL ?? "http://backend:4000").replace(/\/$/, "");
const internalWorkerToken = process.env.INTERNAL_WORKER_TOKEN ?? "siteops-worker-dev-token";
let stopping = false;

function isPrivateAddress(address) {
  if (net.isIPv6(address)) {
    const value = address.toLowerCase();
    return value === "::1" || value.startsWith("fc") || value.startsWith("fd") || value.startsWith("fe80:");
  }
  const parts = address.split(".").map(Number);
  return parts[0] === 10 || parts[0] === 127 || parts[0] === 0 ||
    (parts[0] === 169 && parts[1] === 254) ||
    (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) ||
    (parts[0] === 192 && parts[1] === 168) || parts[0] >= 224;
}

async function resolvePublicHost(hostname) {
  const addresses = await dns.lookup(hostname, { all: true });
  if (!addresses.length || addresses.some(({ address }) => isPrivateAddress(address))) {
    throw new Error("Tên miền trỏ tới địa chỉ nội bộ hoặc không hợp lệ");
  }
  return addresses[0].address;
}

async function fetchWebsite(startUrl) {
  let current = new URL(startUrl);
  const started = Date.now();
  for (let redirects = 0; redirects <= 5; redirects += 1) {
    if (!["http:", "https:"].includes(current.protocol)) throw new Error("Giao thức không được hỗ trợ");
    await resolvePublicHost(current.hostname);
    const response = await fetch(current, {
      redirect: "manual",
      signal: AbortSignal.timeout(15000),
      headers: { "user-agent": "SiteOps-Monitor/1.0" },
    });
    if ([301, 302, 303, 307, 308].includes(response.status)) {
      const location = response.headers.get("location");
      if (!location) throw new Error("Chuyển hướng không có địa chỉ đích");
      current = new URL(location, current);
      continue;
    }
    return { ok: response.ok, statusCode: response.status, responseTimeMs: Date.now() - started, finalUrl: current.toString() };
  }
  throw new Error("Website chuyển hướng quá nhiều lần");
}

async function checkSsl(url) {
  const target = new URL(url);
  if (target.protocol !== "https:") return null;
  const address = await resolvePublicHost(target.hostname);
  return await new Promise((resolve, reject) => {
    const socket = tls.connect({ host: address, port: 443, servername: target.hostname, timeout: 10000, rejectUnauthorized: true }, () => {
      const certificate = socket.getPeerCertificate();
      socket.end();
      resolve(certificate.valid_to ? new Date(certificate.valid_to) : null);
    });
    socket.once("timeout", () => socket.destroy(new Error("Kiểm tra SSL quá thời gian")));
    socket.once("error", reject);
  });
}

async function runPageSpeed(url, strategy) {
  const params = new URLSearchParams({ url, strategy, category: "performance" });
  if (pageSpeedApiKey) params.set("key", pageSpeedApiKey);
  const response = await fetch(`https://www.googleapis.com/pagespeedonline/v5/runPagespeed?${params}`, { signal: AbortSignal.timeout(120000) });
  if (!response.ok) throw new Error(`PageSpeed ${strategy}: HTTP ${response.status}`);
  const data = await response.json();
  const audits = data.lighthouseResult?.audits ?? {};
  return {
    score: Math.round((data.lighthouseResult?.categories?.performance?.score ?? 0) * 100),
    lcpSeconds: audits["largest-contentful-paint"]?.numericValue ? audits["largest-contentful-paint"].numericValue / 1000 : null,
    clsScore: audits["cumulative-layout-shift"]?.numericValue ?? null,
    fcpSeconds: audits["first-contentful-paint"]?.numericValue ? audits["first-contentful-paint"].numericValue / 1000 : null,
  };
}

async function ensureSchema() {
  await sql`CREATE TABLE IF NOT EXISTS scan_jobs (id BIGSERIAL PRIMARY KEY, website_id BIGINT NOT NULL UNIQUE REFERENCES websites(id) ON DELETE CASCADE, status VARCHAR(30) NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0, scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, last_error TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`;
  await sql`CREATE INDEX IF NOT EXISTS idx_scan_jobs_queue ON scan_jobs(status, scheduled_at)`;
}

async function scheduleDueScans() {
  await sql`
    INSERT INTO scan_jobs (website_id, status, scheduled_at)
    SELECT id, 'queued', NOW() FROM websites
    WHERE status = 'monitoring' OR last_checked_at IS NULL OR last_checked_at < NOW() - (${scanIntervalMinutes} * INTERVAL '1 minute')
    ON CONFLICT (website_id) DO UPDATE SET status = 'queued', scheduled_at = NOW(), updated_at = NOW()
    WHERE scan_jobs.status IN ('completed', 'failed')
  `;
}

async function claimJob() {
  return await sql.begin(async (transaction) => {
    const [job] = await transaction`
      UPDATE scan_jobs SET status = 'running', started_at = NOW(), attempts = attempts + 1, updated_at = NOW()
      WHERE id = (SELECT id FROM scan_jobs WHERE status = 'queued' AND scheduled_at <= NOW() ORDER BY scheduled_at FOR UPDATE SKIP LOCKED LIMIT 1)
      RETURNING id, website_id AS "websiteId"
    `;
    if (job) await transaction`UPDATE websites SET status = 'scanning', updated_at = NOW() WHERE id = ${job.websiteId}`;
    return job;
  });
}

async function claimMalwareJob() {
  return await sql.begin(async (transaction) => {
    const [job] = await transaction`
      UPDATE malware_scans SET status = 'running', started_at = COALESCE(started_at, NOW()), updated_at = NOW()
      WHERE id = (
        SELECT id FROM malware_scans WHERE status = 'queued'
        ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
      )
      RETURNING id, website_id AS "websiteId", scan_type AS "scanType"
    `;
    return job;
  });
}

async function runMalwareJob(job) {
  try {
    let finished = false;
    while (!finished) {
      let response;
      for (let attempt = 1; attempt <= 3; attempt += 1) {
        try {
          response = await fetch(`${backendInternalUrl}/api/internal/malware-scans/${job.id}/run`, {
            method: "POST",
            headers: { "x-worker-token": internalWorkerToken },
            signal: AbortSignal.timeout(150 * 1000),
          });
          break;
        } catch (error) {
          if (attempt === 3) throw error;
          await new Promise((resolve) => setTimeout(resolve, 3000 * attempt));
        }
      }
      if (!response?.ok) {
        const body = response ? await response.text() : "Không có phản hồi";
        throw new Error(`Backend malware HTTP ${response?.status ?? "?"}: ${body.slice(0, 500)}`);
      }
      const result = await response.json();
      const scan = result?.scan;
      if (!scan) throw new Error("Backend malware trả về dữ liệu không hợp lệ");
      finished = scan.status === "completed";
      console.log(`[malware] website=${job.websiteId}, scan=${job.id}: ${scan.scannedFiles}/${scan.totalFiles || "?"}`);
    }
    console.log(`[malware] website=${job.websiteId}, scan=${job.id}: completed`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await sql`UPDATE malware_scans SET status = 'failed', completed_at = NOW(), last_error = ${message.slice(0, 2000)}, updated_at = NOW() WHERE id = ${job.id}`;
    await sql`INSERT INTO notifications (website_id, event_key, category, severity, title, message, link) VALUES (${job.websiteId}, ${`malware:${job.id}:failed`}, 'malware', 'danger', 'Quét malware thất bại', ${message.slice(0, 500)}, ${`/websites/${job.websiteId}`}) ON CONFLICT (event_key) DO NOTHING`;
    console.error(`[malware] website=${job.websiteId}, scan=${job.id}: ${message}`);
  }
}

async function scan(job) {
  const [website] = await sql`SELECT id, url, domain FROM websites WHERE id = ${job.websiteId}`;
  if (!website) return;
  try {
    const availability = await fetchWebsite(website.url);
    const [sslResult, mobileResult, desktopResult] = await Promise.allSettled([
      checkSsl(website.url), runPageSpeed(website.url, "mobile"), runPageSpeed(website.url, "desktop"),
    ]);
    const mobile = mobileResult.status === "fulfilled" ? mobileResult.value : null;
    const desktop = desktopResult.status === "fulfilled" ? desktopResult.value : null;
    const sslExpiresAt = sslResult.status === "fulfilled" ? sslResult.value : null;
    const score = mobile?.score ?? desktop?.score ?? null;
    const sslDaysRemaining = sslExpiresAt ? (sslExpiresAt.getTime() - Date.now()) / 86400000 : null;
    const status = !availability.ok || (score !== null && score < 50) || (sslDaysRemaining !== null && sslDaysRemaining <= 7)
      ? "attention"
      : score === null || score < 70 || (sslDaysRemaining !== null && sslDaysRemaining <= 30)
        ? "watching"
        : "healthy";

    await sql.begin(async (transaction) => {
      await transaction`INSERT INTO monitoring_checks (website_id, check_type, status, response_time_ms, details) VALUES (${website.id}, 'availability', ${availability.ok ? "ok" : "error"}, ${availability.responseTimeMs}, ${sql.json({ statusCode: availability.statusCode, finalUrl: availability.finalUrl })})`;
      if (mobile) await transaction`INSERT INTO monitoring_checks (website_id, check_type, status, performance_score, lcp_seconds, cls_score, details) VALUES (${website.id}, 'pagespeed-mobile', 'ok', ${mobile.score}, ${mobile.lcpSeconds}, ${mobile.clsScore}, ${sql.json({ fcpSeconds: mobile.fcpSeconds })})`;
      if (desktop) await transaction`INSERT INTO monitoring_checks (website_id, check_type, status, performance_score, lcp_seconds, cls_score, details) VALUES (${website.id}, 'pagespeed-desktop', 'ok', ${desktop.score}, ${desktop.lcpSeconds}, ${desktop.clsScore}, ${sql.json({ fcpSeconds: desktop.fcpSeconds })})`;
      const [{ uptime }] = await transaction`SELECT COALESCE(100.0 * COUNT(*) FILTER (WHERE status = 'ok') / NULLIF(COUNT(*), 0), 0)::float AS uptime FROM monitoring_checks WHERE website_id = ${website.id} AND check_type = 'availability' AND checked_at >= NOW() - INTERVAL '30 days'`;
      await transaction`UPDATE websites SET status = ${status}, performance_score = ${score}, uptime_percent = ${uptime}, ssl_expires_at = ${sslExpiresAt}, last_checked_at = NOW(), updated_at = NOW() WHERE id = ${website.id}`;
      await transaction`UPDATE scan_jobs SET status = 'completed', completed_at = NOW(), last_error = NULL, updated_at = NOW() WHERE id = ${job.id}`;
      const eventKey = `monitoring:${job.id}:completed:${Date.now()}`;
      const scanMessage = `Uptime ${Number(uptime).toFixed(2)}%, Mobile ${mobile?.score ?? "—"}, Desktop ${desktop?.score ?? "—"}.`;
      await transaction`INSERT INTO notifications (website_id, event_key, category, severity, title, message, link) VALUES (${website.id}, ${eventKey}, 'monitoring', ${status === "healthy" ? "success" : status === "watching" ? "warning" : "danger"}, 'Kiểm tra website đã hoàn tất', ${scanMessage}, ${`/websites/${website.id}`}) ON CONFLICT (event_key) DO NOTHING`;
    });
    console.log(`[scan] ${website.domain}: ${status}, score=${score ?? "n/a"}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await sql.begin(async (transaction) => {
      await transaction`INSERT INTO monitoring_checks (website_id, check_type, status, details) VALUES (${website.id}, 'availability', 'error', ${sql.json({ error: message })})`;
      await transaction`UPDATE websites SET status = 'attention', last_checked_at = NOW(), updated_at = NOW() WHERE id = ${website.id}`;
      await transaction`UPDATE scan_jobs SET status = 'failed', completed_at = NOW(), last_error = ${message.slice(0, 1000)}, updated_at = NOW() WHERE id = ${job.id}`;
      const eventKey = `monitoring:${job.id}:failed:${Date.now()}`;
      await transaction`INSERT INTO notifications (website_id, event_key, category, severity, title, message, link) VALUES (${website.id}, ${eventKey}, 'monitoring', 'danger', 'Kiểm tra website thất bại', ${message.slice(0, 500)}, ${`/websites/${website.id}`}) ON CONFLICT (event_key) DO NOTHING`;
    });
    console.error(`[scan] ${website.domain}: ${message}`);
  }
}

async function main() {
  await ensureSchema();
  console.log(`[worker] sẵn sàng; chu kỳ quét ${scanIntervalMinutes} phút`);
  while (!stopping) {
    await scheduleDueScans();
    const malwareJob = await claimMalwareJob();
    if (malwareJob) {
      await runMalwareJob(malwareJob);
      continue;
    }
    const job = await claimJob();
    if (job) await scan(job);
    else await new Promise((resolve) => setTimeout(resolve, 5000));
  }
  await sql.end();
}

process.on("SIGTERM", () => { stopping = true; });
process.on("SIGINT", () => { stopping = true; });
main().catch((error) => { console.error(error); process.exit(1); });
