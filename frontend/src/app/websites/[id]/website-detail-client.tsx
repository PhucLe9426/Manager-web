"use client";

import Link from "next/link";
import {
  Activity, ArrowLeft, Bell, CheckCircle2, CircleUserRound, Clock3,
  ExternalLink, FileBarChart, Gauge, Globe2, LayoutDashboard, ListChecks,
  Menu, Moon, RefreshCw, ShieldCheck, Sun, UsersRound, XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTheme } from "@/hooks/use-theme";

type Check = {
  id: number; checkType: string; status: string; responseTimeMs: number | null;
  performanceScore: number | null; lcpSeconds: number | null; clsScore: number | null;
  details: { fcpSeconds?: number; statusCode?: number; finalUrl?: string; error?: string } | null;
  checkedAt: string;
};
type Detail = {
  website: {
    id: number; domain: string; url: string; platform: string; status: string;
    performanceScore: number | null; uptimePercent: number; sslExpiresAt: string | null;
    lastCheckedAt: string | null; customerName: string; contactName: string | null; contactEmail: string | null;
  };
  checks: Check[];
  job: { status: string; attempts: number; startedAt: string | null; completedAt: string | null; lastError: string | null } | null;
};

const navigation = [
  ["Tổng quan", LayoutDashboard, "/"], ["Khách hàng", UsersRound, "/customers"],
  ["Website", Globe2, "/websites"], ["Công việc", ListChecks, "/tasks"], ["Báo cáo", FileBarChart, "/reports"],
] as const;
const labels: Record<string, string> = { healthy: "Ổn định", attention: "Cần xử lý", watching: "Theo dõi", scanning: "Đang quét", monitoring: "Đang thiết lập", failed: "Quét thất bại" };

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : "Chưa có";
}
function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return <article className="detail-metric"><p>{label}</p><strong>{value}</strong><span>{note}</span></article>;
}

export function WebsiteDetailClient({ websiteId }: { websiteId: number }) {
  const { theme, toggleTheme } = useTheme();
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [queuing, setQueuing] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch(`/api/websites/${websiteId}`, { cache: "no-store" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message ?? "Không thể tải dữ liệu website.");
    setData(result);
  }, [websiteId]);

  useEffect(() => {
    void load().catch((reason) => setError(reason instanceof Error ? reason.message : "Không thể tải dữ liệu."));
    const timer = window.setInterval(() => void load().catch(() => undefined), 10000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    setSidebarCollapsed(window.localStorage.getItem("siteops-sidebar-collapsed") === "true");
  }, []);

  function toggleSidebar() {
    setSidebarCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem("siteops-sidebar-collapsed", String(next));
      return next;
    });
  }

  const latest = useMemo(() => {
    const checks = data?.checks ?? [];
    return {
      availability: checks.find((item) => item.checkType === "availability"),
      mobile: checks.find((item) => item.checkType === "pagespeed-mobile"),
      desktop: checks.find((item) => item.checkType === "pagespeed-desktop"),
    };
  }, [data]);

  async function scanNow() {
    setQueuing(true); setError("");
    try {
      const response = await fetch(`/api/websites/${websiteId}/scan`, { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message ?? "Không thể bắt đầu quét.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể bắt đầu quét.");
    } finally { setQueuing(false); }
  }

  if (error && !data) return <main className="detail-error"><XCircle /><h1>Không mở được website</h1><p>{error}</p><Link href="/websites">Quay lại danh sách</Link></main>;
  if (!data) return <main className="detail-loading"><RefreshCw className="spin" /><p>Đang tải kết quả quét...</p></main>;
  const { website, checks, job } = data;
  const sslDays = website.sslExpiresAt ? Math.ceil((new Date(website.sslExpiresAt).getTime() - Date.now()) / 86400000) : null;
  const pageSpeedPending = website.status === "scanning" || job?.status === "queued" || job?.status === "running";

  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? "open" : ""} ${sidebarCollapsed ? "collapsed" : ""}`}><div className="brand"><span className="brand-mark"><Activity size={21} /></span><span className="brand-copy"><strong>SiteOps</strong><small>Web Care Center</small></span><button type="button" className="sidebar-toggle" onClick={toggleSidebar} aria-label={sidebarCollapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"} title={sidebarCollapsed ? "Mở rộng" : "Thu gọn"}><Menu size={21} /></button></div><nav><p>Vận hành</p>{navigation.map(([label, Icon, href]) => <Link className={label === "Website" ? "active" : ""} href={href} key={label} onClick={() => setMenuOpen(false)} title={sidebarCollapsed ? label : undefined}><Icon size={17} /><span className="nav-label">{label}</span></Link>)}</nav><div className="sidebar-note"><ShieldCheck size={17} /><strong>Hệ thống an toàn</strong><span>Docker và PostgreSQL đang hoạt động</span></div></aside>
    <div className="content"><header className="topbar"><button className="icon-button mobile-menu" onClick={() => setMenuOpen(!menuOpen)} aria-label="Mở trình đơn"><Menu size={20} /></button><Link className="back-link" href="/websites"><ArrowLeft size={17} />Danh sách website</Link><div className="user-area"><button type="button" className="icon-button theme-toggle" onClick={toggleTheme} aria-label={theme === "dark" ? "Chuyển sang chế độ sáng" : "Chuyển sang chế độ tối"} title={theme === "dark" ? "Chế độ sáng" : "Chế độ tối"}>{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button><button className="icon-button notification" aria-label="Thông báo"><Bell size={18} /><i /></button><span className="avatar"><CircleUserRound size={21} /></span><span><strong>Quản trị viên</strong><small>Administrator</small></span></div></header>
      <main className="detail-main">
        <section className="detail-heading"><div><div className="detail-domain"><Globe2 size={22} /><span><h1>{website.domain}</h1><p>{website.customerName} · {website.platform}</p></span></div><span className={`status ${website.status}`}>{labels[website.status] ?? website.status}</span></div><div className="detail-actions"><a className="secondary" href={website.url} target="_blank" rel="noreferrer">Mở website <ExternalLink size={15} /></a><button className="primary" disabled={pageSpeedPending || queuing} onClick={() => void scanNow()}><RefreshCw size={16} className={pageSpeedPending ? "spin" : ""} />{pageSpeedPending ? "Đang quét" : "Quét lại"}</button></div></section>
        {error && <div className="notice error">{error}</div>}
        <section className="detail-metrics"><Metric label="Uptime 30 ngày" value={website.lastCheckedAt ? `${Number(website.uptimePercent).toFixed(2)}%` : "—"} note="Từ các lần kiểm tra HTTP" /><Metric label="Thời gian phản hồi" value={latest.availability?.responseTimeMs ? `${latest.availability.responseTimeMs} ms` : "—"} note={`HTTP ${latest.availability?.details?.statusCode ?? "chưa có"}`} /><Metric label="SSL còn hạn" value={sslDays === null ? "—" : `${sslDays} ngày`} note={website.sslExpiresAt ? `Hết hạn ${formatDate(website.sslExpiresAt)}` : "Chưa có kết quả"} /><Metric label="Lần quét gần nhất" value={website.lastCheckedAt ? "Đã hoàn tất" : "Chưa quét"} note={formatDate(website.lastCheckedAt)} /></section>
        <section className="detail-grid"><article className="panel performance-panel"><div className="panel-head"><div><h2>PageSpeed Insights</h2><p>Kết quả Lighthouse gần nhất</p></div><Gauge size={19} /></div><div className="strategy-grid">{[["Mobile", latest.mobile], ["Desktop", latest.desktop]].map(([name, raw]) => { const check = raw as Check | undefined; return <div className="strategy" key={name as string}><header><strong>{name as string}</strong><span className={`big-score ${(check?.performanceScore ?? 0) >= 90 ? "good" : (check?.performanceScore ?? 0) >= 50 ? "warn" : "bad"}`}>{check?.performanceScore ?? "—"}</span></header><dl><div><dt>FCP</dt><dd>{check?.details?.fcpSeconds ? `${check.details.fcpSeconds.toFixed(2)}s` : "—"}</dd></div><div><dt>LCP</dt><dd>{check?.lcpSeconds ? `${check.lcpSeconds.toFixed(2)}s` : "—"}</dd></div><div><dt>CLS</dt><dd>{check?.clsScore ?? "—"}</dd></div></dl><small>{check ? formatDate(check.checkedAt) : "Chưa có kết quả"}</small></div>; })}</div></article>
          <article className="panel scan-info"><div className="panel-head"><div><h2>Trạng thái lần quét</h2><p>Thông tin từ worker</p></div><Clock3 size={18} /></div><dl><div><dt>Trạng thái job</dt><dd>{job?.status ?? "Chưa tạo"}</dd></div><div><dt>Số lần thực hiện</dt><dd>{job?.attempts ?? 0}</dd></div><div><dt>Bắt đầu</dt><dd>{formatDate(job?.startedAt ?? null)}</dd></div><div><dt>Hoàn thành</dt><dd>{formatDate(job?.completedAt ?? null)}</dd></div></dl>{job?.lastError && <div className="scan-error"><strong>Lỗi gần nhất</strong><p>{job.lastError}</p></div>}</article></section>
        <section className="panel history-panel"><div className="panel-head"><div><h2>Lịch sử kiểm tra</h2><p>{checks.length} bản ghi gần nhất</p></div><CheckCircle2 size={18} /></div><div className="table-wrap"><table><thead><tr><th>Thời gian</th><th>Loại kiểm tra</th><th>Kết quả</th><th>Điểm / Phản hồi</th></tr></thead><tbody>{checks.map((check) => <tr key={check.id}><td>{formatDate(check.checkedAt)}</td><td>{check.checkType}</td><td><span className={`check-result ${check.status}`}>{check.status === "ok" ? "Thành công" : "Có lỗi"}</span></td><td>{check.performanceScore !== null ? `${check.performanceScore}/100` : check.responseTimeMs ? `${check.responseTimeMs} ms` : check.details?.error ?? "—"}</td></tr>)}{checks.length === 0 && <tr><td colSpan={4}><div className="empty-state"><Activity size={24} /><strong>Chưa có lịch sử quét</strong><span>Bấm “Quét lại” để bắt đầu.</span></div></td></tr>}</tbody></table></div></section>
      </main>
    </div>
  </div>;
}
