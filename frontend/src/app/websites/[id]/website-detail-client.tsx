"use client";

import Link from "next/link";
import {
  Activity, AlertTriangle, ArrowLeft, CheckCircle2, ChevronLeft, ChevronRight, CircleUserRound, Clock3,
  ExternalLink, FileBarChart, Gauge, Globe2, LayoutDashboard, ListChecks,
  FileText, KeyRound, Menu, Moon, Palette, Plug, RefreshCw, Search, ShieldAlert, ShieldCheck, Sun,
  UsersRound, X, XCircle,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useTheme } from "@/hooks/use-theme";
import { NotificationBell } from "@/components/notification-bell";

type Check = {
  id: number; checkType: string; status: string; responseTimeMs: number | null;
  performanceScore: number | null; lcpSeconds: number | null; clsScore: number | null;
  details: { fcpSeconds?: number; statusCode?: number; finalUrl?: string; error?: string } | null;
  checkedAt: string;
};
type ActivityHistory = {
  activityId: string; checkType: string; status: string;
  responseTimeMs: number | null; performanceScore: number | null;
  details: { error?: string; total?: number; modified?: number; warning?: number; unknown?: number; totalFiles?: number; scannedFiles?: number; danger?: number; info?: number } | null;
  checkedAt: string;
};
type Detail = {
  website: {
    id: number; domain: string; url: string; platform: string; status: string;
    performanceScore: number | null; uptimePercent: number; sslExpiresAt: string | null;
    lastCheckedAt: string | null; customerName: string; contactName: string | null; contactEmail: string | null;
  };
  checks: Check[];
  activities: ActivityHistory[];
  job: { status: string; attempts: number; startedAt: string | null; completedAt: string | null; lastError: string | null } | null;
};
type WordPressPlugin = {
  plugin: string; status: "active" | "inactive"; name: string; version: string;
  author?: { rendered?: string } | string;
};
type WordPressTheme = {
  stylesheet: string; status: "active" | "inactive"; version: string;
  name: { rendered?: string } | string;
};
type WordPressData = {
  connected: boolean; username?: string; connectedAt?: string;
  profile?: { id?: number; name?: string; roles?: string[] };
  plugins: WordPressPlugin[]; themes: WordPressTheme[];
};
type CachedWordPressData = { savedAt: number; data: WordPressData };
type SeoPost = {
  id: number; title: string; slug: string; status: string; link?: string; editUrl: string;
  date?: string; modified?: string; wordCount: number; titleLength: number; excerptLength: number;
  featuredImage: boolean; imageCount: number; imagesMissingAlt: number; h1Count: number;
  internalLinks: number; externalLinks: number; categoryCount: number; tagCount: number;
  seoScore: number | null; internalScore: number; seoStatus: "good" | "warning" | "critical" | "unknown"; issues: string[];
  rankMath: { available: boolean; score?: number | null; title?: string; description?: string; focusKeyword?: string };
};
type PostsSeoData = {
  posts: SeoPost[];
  summary: {
    total: number; published: number; draft: number; needsAttention: number; averageScore: number | null; rankMathScored: number;
    missingFeaturedImage: number; shortContent: number; rankMathDataAvailable: boolean;
    totalAvailable: number; allPostsLoaded: boolean;
  };
};
type CachedPostsSeoData = { savedAt: number; data: PostsSeoData };
type SecurityPlugin = {
  plugin: string; name: string; version: string; active: boolean;
  source: "wordpress.org" | "third-party-or-custom";
  licenseStatus: "not-required" | "unknown";
  integrity: "verified" | "modified" | "unknown";
  risk: "low" | "medium" | "high" | "unknown";
  findings: string[]; changedFiles: string[];
  codeSignals: { type: string; level: string; file: string }[];
};
type SecurityScan = {
  id?: number; checkedAt?: string; scannedAt?: string; agentVersion?: string;
  wordpressVersion?: string; phpVersion?: string; plugins: SecurityPlugin[];
  summary: { total: number; verified: number; modified: number; warning: number; unknown: number };
};
type MalwareScan = {
  id: number; websiteId: number; scanType: "quick" | "full";
  status: "queued" | "running" | "completed" | "failed";
  cursor: number; totalFiles: number; scannedFiles: number; skippedFiles: number;
  infoCount: number; warningCount: number; dangerCount: number;
  agentVersion?: string; rulesVersion?: string; lastError?: string;
  createdAt: string; startedAt?: string; completedAt?: string; updatedAt: string;
};
type MalwareFinding = {
  id: number; filePath: string; fileHash?: string; component: string;
  ruleCode: string; severity: "info" | "warning" | "danger";
  title: string; message: string; lineNumber?: number; snippet?: string;
  status: "open" | "acknowledged" | "false_positive" | "resolved"; createdAt: string;
};
type MalwareFindingsData = { findings: MalwareFinding[]; total: number; page: number; pageSize: number };

const navigation = [
  ["Tổng quan", LayoutDashboard, "/"], ["Khách hàng", UsersRound, "/customers"],
  ["Website", Globe2, "/websites"], ["Công việc", ListChecks, "/tasks"], ["Báo cáo", FileBarChart, "/reports"],
] as const;
const labels: Record<string, string> = { healthy: "Ổn định", attention: "Cần xử lý", watching: "Theo dõi", scanning: "Đang quét", monitoring: "Đang thiết lập", failed: "Quét thất bại" };
const integrityLabels: Record<string, string> = { verified: "Checksum hợp lệ", modified: "File đã thay đổi", unknown: "Chưa xác định" };
const riskLabels: Record<string, string> = { low: "Rủi ro thấp", medium: "Cần kiểm tra", high: "Rủi ro cao", unknown: "Chưa xác định" };
const postStatusLabels: Record<string, string> = { publish: "Đã đăng", draft: "Bản nháp", pending: "Chờ duyệt", private: "Riêng tư", future: "Đã lên lịch" };
const malwareScanStatusLabels: Record<string, string> = { queued: "Đang chờ", running: "Đang quét", completed: "Đã hoàn tất", failed: "Quét thất bại" };
const malwareSeverityLabels: Record<string, string> = { info: "Thông tin", warning: "Cảnh báo", danger: "Nguy hiểm" };
const malwareFindingStatusLabels: Record<string, string> = { open: "Chưa xử lý", acknowledged: "Đã xem", false_positive: "Báo nhầm", resolved: "Đã xử lý" };
const checkTypeLabels: Record<string, string> = {
  availability: "Kiểm tra hoạt động", "pagespeed-mobile": "PageSpeed Mobile",
  "pagespeed-desktop": "PageSpeed Desktop", "plugin-security": "Bảo mật plugin",
  "malware-quick": "Malware · Quét nhanh", "malware-full": "Malware · Quét toàn bộ",
};
const WORDPRESS_CACHE_TTL_MS = 10 * 60 * 1000;
const POSTS_SEO_CACHE_TTL_MS = 5 * 60 * 1000;
const POSTS_PER_PAGE = 20;
const PLUGINS_PER_PAGE = 10;

function wordpressCacheKey(websiteId: number) {
  return `siteops-wordpress-${websiteId}`;
}
function postsSeoCacheKey(websiteId: number) {
  return `siteops-posts-seo-${websiteId}`;
}

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : "Chưa có";
}
function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return <article className="detail-metric"><p>{label}</p><strong>{value}</strong><span>{note}</span></article>;
}
function rendered(value: { rendered?: string } | string | undefined) {
  return typeof value === "string" ? value : value?.rendered ?? "Không rõ";
}
function activityValue(activity: ActivityHistory) {
  if (activity.performanceScore !== null) return `${activity.performanceScore}/100`;
  if (activity.responseTimeMs !== null) return `${activity.responseTimeMs} ms`;
  if (activity.checkType === "plugin-security") {
    return `${activity.details?.total ?? 0} plugin · ${(activity.details?.modified ?? 0) + (activity.details?.warning ?? 0)} cần kiểm tra`;
  }
  if (activity.checkType.startsWith("malware-")) {
    return `${activity.details?.scannedFiles ?? 0}/${activity.details?.totalFiles ?? 0} file · ${(activity.details?.danger ?? 0) + (activity.details?.warning ?? 0)} cảnh báo`;
  }
  return activity.details?.error ?? "—";
}

export function WebsiteDetailClient({ websiteId }: { websiteId: number }) {
  const { theme, toggleTheme } = useTheme();
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [queuing, setQueuing] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [wordpress, setWordpress] = useState<WordPressData | null>(null);
  const [wordpressLoading, setWordpressLoading] = useState(true);
  const [wordpressError, setWordpressError] = useState("");
  const [wordpressModal, setWordpressModal] = useState(false);
  const [wordpressSaving, setWordpressSaving] = useState(false);
  const [changingPlugin, setChangingPlugin] = useState("");
  const [securityScan, setSecurityScan] = useState<SecurityScan | null>(null);
  const [securityScanning, setSecurityScanning] = useState(false);
  const [securityPage, setSecurityPage] = useState(1);
  const [malwareScan, setMalwareScan] = useState<MalwareScan | null>(null);
  const [malwareFindings, setMalwareFindings] = useState<MalwareFindingsData>({ findings: [], total: 0, page: 1, pageSize: 20 });
  const [malwareLoading, setMalwareLoading] = useState(true);
  const [malwareStarting, setMalwareStarting] = useState(false);
  const [malwareError, setMalwareError] = useState("");
  const [malwarePage, setMalwarePage] = useState(1);
  const [malwareSeverity, setMalwareSeverity] = useState("");
  const [malwareFindingStatus, setMalwareFindingStatus] = useState("");
  const [postsSeo, setPostsSeo] = useState<PostsSeoData | null>(null);
  const [postsSeoLoading, setPostsSeoLoading] = useState(false);
  const [postsSeoError, setPostsSeoError] = useState("");
  const [postSearch, setPostSearch] = useState("");
  const [postStatus, setPostStatus] = useState("all");
  const [postPage, setPostPage] = useState(1);

  const load = useCallback(async () => {
    const response = await fetch(`/api/websites/${websiteId}`, { cache: "no-store" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message ?? "Không thể tải dữ liệu website.");
    setData(result);
  }, [websiteId]);

  const loadWordPress = useCallback(async (force = false) => {
    if (!force) {
      try {
        const cachedRaw = window.localStorage.getItem(wordpressCacheKey(websiteId));
        if (cachedRaw) {
          const cached = JSON.parse(cachedRaw) as CachedWordPressData;
          if (cached.data && Date.now() - cached.savedAt < WORDPRESS_CACHE_TTL_MS) {
            setWordpress(cached.data);
            setWordpressLoading(false);
            return;
          }
          window.localStorage.removeItem(wordpressCacheKey(websiteId));
        }
      } catch {
        window.localStorage.removeItem(wordpressCacheKey(websiteId));
      }
    }

    setWordpressLoading(true);
    setWordpressError("");
    try {
      const response = await fetch(`/api/websites/${websiteId}/wordpress`, { cache: "no-store" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message ?? "Không thể tải dữ liệu WordPress.");
      setWordpress(result);
      window.localStorage.setItem(
        wordpressCacheKey(websiteId),
        JSON.stringify({ savedAt: Date.now(), data: result } satisfies CachedWordPressData),
      );
    } catch (reason) {
      setWordpressError(reason instanceof Error ? reason.message : "Không thể tải dữ liệu WordPress.");
    } finally {
      setWordpressLoading(false);
    }
  }, [websiteId]);

  const loadPostsSeo = useCallback(async (force = false) => {
    if (!force) {
      try {
        const cachedRaw = window.localStorage.getItem(postsSeoCacheKey(websiteId));
        if (cachedRaw) {
          const cached = JSON.parse(cachedRaw) as CachedPostsSeoData;
          if (cached.data && Date.now() - cached.savedAt < POSTS_SEO_CACHE_TTL_MS) {
            setPostsSeo(cached.data);
            return;
          }
          window.localStorage.removeItem(postsSeoCacheKey(websiteId));
        }
      } catch {
        window.localStorage.removeItem(postsSeoCacheKey(websiteId));
      }
    }

    setPostsSeoLoading(true);
    setPostsSeoError("");
    try {
      const response = await fetch(`/posts-seo-proxy/websites/${websiteId}`, { cache: "no-store" });
      const raw = await response.text();
      let result: PostsSeoData & { message?: string };
      try {
        result = JSON.parse(raw || "{}");
      } catch {
        throw new Error(`Máy chủ SEO trả về dữ liệu không hợp lệ (HTTP ${response.status}).`);
      }
      if (!response.ok) throw new Error(result.message ?? "Không thể tải bài viết WordPress.");
      setPostsSeo(result);
      window.localStorage.setItem(
        postsSeoCacheKey(websiteId),
        JSON.stringify({ savedAt: Date.now(), data: result } satisfies CachedPostsSeoData),
      );
    } catch (reason) {
      setPostsSeoError(reason instanceof Error ? reason.message : "Không thể tải dữ liệu SEO.");
    } finally {
      setPostsSeoLoading(false);
    }
  }, [websiteId]);

  const loadMalwareScan = useCallback(async () => {
    try {
      const response = await fetch(`/api/websites/${websiteId}/malware-scans/latest`, { cache: "no-store" });
      const result = await response.json() as { scan?: MalwareScan | null; detail?: string };
      if (!response.ok) throw new Error(result.detail ?? "Không thể tải trạng thái quét malware.");
      setMalwareScan(result.scan ?? null);
      setMalwareError("");
    } catch (reason) {
      setMalwareError(reason instanceof Error ? reason.message : "Không thể tải trạng thái quét malware.");
    } finally {
      setMalwareLoading(false);
    }
  }, [websiteId]);

  const loadMalwareFindings = useCallback(async (scanId: number) => {
    const query = new URLSearchParams({ page: String(malwarePage), pageSize: "20" });
    if (malwareSeverity) query.set("severity", malwareSeverity);
    if (malwareFindingStatus) query.set("status", malwareFindingStatus);
    try {
      const response = await fetch(`/api/malware-scans/${scanId}/findings?${query}`, { cache: "no-store" });
      const result = await response.json() as MalwareFindingsData & { detail?: string };
      if (!response.ok) throw new Error(result.detail ?? "Không thể tải phát hiện malware.");
      setMalwareFindings(result);
    } catch (reason) {
      setMalwareError(reason instanceof Error ? reason.message : "Không thể tải phát hiện malware.");
    }
  }, [malwareFindingStatus, malwarePage, malwareSeverity]);

  useEffect(() => {
    void load().catch((reason) => setError(reason instanceof Error ? reason.message : "Không thể tải dữ liệu."));
    const timer = window.setInterval(() => void load().catch(() => undefined), 10000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => { void loadWordPress(); }, [loadWordPress]);

  useEffect(() => { void loadMalwareScan(); }, [loadMalwareScan]);

  useEffect(() => {
    if (!malwareScan || !["queued", "running"].includes(malwareScan.status)) return;
    const timer = window.setInterval(() => void loadMalwareScan(), 3000);
    return () => window.clearInterval(timer);
  }, [loadMalwareScan, malwareScan]);

  useEffect(() => {
    if (malwareScan) void loadMalwareFindings(malwareScan.id);
    else setMalwareFindings({ findings: [], total: 0, page: 1, pageSize: 20 });
  }, [loadMalwareFindings, malwareScan?.id, malwareScan?.status]);

  useEffect(() => {
    if (wordpress?.connected) void loadPostsSeo();
    else if (wordpress && !wordpress.connected) setPostsSeo(null);
  }, [loadPostsSeo, wordpress?.connected]);

  useEffect(() => {
    void fetch(`/api/websites/${websiteId}/wordpress/security-scan/latest`, { cache: "no-store" })
      .then(async (response) => {
        const result = await response.json();
        if (response.ok && result.scan) setSecurityScan({ ...result.scan.results, id: result.scan.id, checkedAt: result.scan.checkedAt });
      })
      .catch(() => undefined);
  }, [websiteId]);

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

  const filteredSeoPosts = useMemo(() => {
    const keyword = postSearch.trim().toLocaleLowerCase("vi");
    return (postsSeo?.posts ?? [])
      .filter((post) => {
        const matchesKeyword = !keyword || `${post.title} ${post.slug}`.toLocaleLowerCase("vi").includes(keyword);
        const matchesStatus = postStatus === "all"
          || (postStatus === "attention" ? post.seoScore !== null && post.seoScore < 70 : post.status === postStatus);
        return matchesKeyword && matchesStatus;
      })
      .sort((left, right) => new Date(right.date ?? 0).getTime() - new Date(left.date ?? 0).getTime());
  }, [postSearch, postStatus, postsSeo]);

  const postPageCount = Math.max(1, Math.ceil(filteredSeoPosts.length / POSTS_PER_PAGE));
  const pagedSeoPosts = useMemo(
    () => filteredSeoPosts.slice((postPage - 1) * POSTS_PER_PAGE, postPage * POSTS_PER_PAGE),
    [filteredSeoPosts, postPage],
  );

  useEffect(() => { setPostPage(1); }, [postSearch, postStatus, postsSeo]);

  const securityPageCount = Math.max(1, Math.ceil((securityScan?.plugins.length ?? 0) / PLUGINS_PER_PAGE));
  const pagedSecurityPlugins = useMemo(
    () => (securityScan?.plugins ?? []).slice((securityPage - 1) * PLUGINS_PER_PAGE, securityPage * PLUGINS_PER_PAGE),
    [securityPage, securityScan],
  );

  useEffect(() => { setSecurityPage(1); }, [securityScan]);

  const malwarePageCount = Math.max(1, Math.ceil(malwareFindings.total / malwareFindings.pageSize));
  const malwareProgress = malwareScan?.totalFiles
    ? Math.min(100, Math.round((malwareScan.cursor / malwareScan.totalFiles) * 100))
    : malwareScan?.status === "completed" ? 100 : 0;

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

  async function connectWordPress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWordpressSaving(true);
    setWordpressError("");
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch(`/api/websites/${websiteId}/wordpress/connection`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: form.get("username"),
          applicationPassword: form.get("applicationPassword"),
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message ?? "Không thể kết nối WordPress.");
      setWordpressModal(false);
      window.localStorage.removeItem(wordpressCacheKey(websiteId));
      window.localStorage.removeItem(postsSeoCacheKey(websiteId));
      await loadWordPress(true);
    } catch (reason) {
      setWordpressError(reason instanceof Error ? reason.message : "Không thể kết nối WordPress.");
    } finally {
      setWordpressSaving(false);
    }
  }

  async function disconnectWordPress() {
    if (!window.confirm("Ngắt kết nối WordPress của website này?")) return;
    const response = await fetch(`/api/websites/${websiteId}/wordpress/connection`, { method: "DELETE" });
    const result = await response.json();
    if (!response.ok) { setWordpressError(result.message ?? "Không thể ngắt kết nối."); return; }
    window.localStorage.removeItem(wordpressCacheKey(websiteId));
    window.localStorage.removeItem(postsSeoCacheKey(websiteId));
    setPostsSeo(null);
    setWordpress({ connected: false, plugins: [], themes: [] });
  }

  async function togglePlugin(plugin: WordPressPlugin) {
    setChangingPlugin(plugin.plugin);
    setWordpressError("");
    try {
      const response = await fetch(`/api/websites/${websiteId}/wordpress/plugin`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plugin: plugin.plugin,
          status: plugin.status === "active" ? "inactive" : "active",
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message ?? "Không thể cập nhật plugin.");
      await loadWordPress(true);
    } catch (reason) {
      setWordpressError(reason instanceof Error ? reason.message : "Không thể cập nhật plugin.");
    } finally {
      setChangingPlugin("");
    }
  }

  async function scanPluginSecurity() {
    setSecurityScanning(true);
    setWordpressError("");
    try {
      const response = await fetch(`/scan-proxy/websites/${websiteId}`, { method: "POST" });
      const raw = await response.text();
      let result: { message?: string; scan?: SecurityScan } = {};
      try {
        result = raw ? JSON.parse(raw) : {};
      } catch {
        throw new Error(response.ok ? "Máy chủ trả về dữ liệu không hợp lệ." : `Máy chủ quét gặp lỗi HTTP ${response.status}.`);
      }
      if (!response.ok) throw new Error(result.message ?? "Không thể quét bảo mật plugin.");
      if (!result.scan) throw new Error("Kết quả quét không hợp lệ.");
      setSecurityScan(result.scan);
    } catch (reason) {
      setWordpressError(reason instanceof Error ? reason.message : "Không thể quét bảo mật plugin.");
    } finally {
      setSecurityScanning(false);
    }
  }

  async function startMalwareScan(scanType: "quick" | "full") {
    setMalwareStarting(true);
    setMalwareError("");
    try {
      const response = await fetch(`/api/websites/${websiteId}/malware-scans`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scanType }),
      });
      const result = await response.json() as { scan?: MalwareScan; detail?: string };
      if (!response.ok || !result.scan) throw new Error(result.detail ?? "Không thể đưa malware scan vào hàng đợi.");
      setMalwarePage(1);
      await loadMalwareScan();
    } catch (reason) {
      setMalwareError(reason instanceof Error ? reason.message : "Không thể bắt đầu quét malware.");
    } finally {
      setMalwareStarting(false);
    }
  }

  async function updateMalwareFinding(findingId: number, status: MalwareFinding["status"]) {
    setMalwareError("");
    try {
      const response = await fetch(`/api/malware-findings/${findingId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const result = await response.json() as { detail?: string };
      if (!response.ok) throw new Error(result.detail ?? "Không thể cập nhật phát hiện.");
      if (malwareScan) await loadMalwareFindings(malwareScan.id);
    } catch (reason) {
      setMalwareError(reason instanceof Error ? reason.message : "Không thể cập nhật phát hiện.");
    }
  }

  async function retryMalwareScan() {
    if (!malwareScan || malwareScan.status !== "failed") return;
    setMalwareStarting(true);
    setMalwareError("");
    try {
      const response = await fetch(`/api/malware-scans/${malwareScan.id}/retry`, { method: "POST" });
      const result = await response.json() as { detail?: string };
      if (!response.ok) throw new Error(result.detail ?? "Không thể tiếp tục lần quét.");
      await loadMalwareScan();
    } catch (reason) {
      setMalwareError(reason instanceof Error ? reason.message : "Không thể tiếp tục lần quét.");
    } finally {
      setMalwareStarting(false);
    }
  }

  if (error && !data) return <main className="detail-error"><XCircle /><h1>Không mở được website</h1><p>{error}</p><Link href="/websites">Quay lại danh sách</Link></main>;
  if (!data) return <main className="detail-loading"><RefreshCw className="spin" /><p>Đang tải kết quả quét...</p></main>;
  const { website, checks, job } = data;
  const sslDays = website.sslExpiresAt ? Math.ceil((new Date(website.sslExpiresAt).getTime() - Date.now()) / 86400000) : null;
  const pageSpeedPending = website.status === "scanning" || job?.status === "queued" || job?.status === "running";

  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? "open" : ""} ${sidebarCollapsed ? "collapsed" : ""}`}><div className="brand"><span className="brand-mark"><Activity size={21} /></span><span className="brand-copy"><strong>SiteOps</strong><small>Web Care Center</small></span><button type="button" className="sidebar-toggle" onClick={toggleSidebar} aria-label={sidebarCollapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"} title={sidebarCollapsed ? "Mở rộng" : "Thu gọn"}><Menu size={21} /></button></div><nav><p>Vận hành</p>{navigation.map(([label, Icon, href]) => <Link className={label === "Website" ? "active" : ""} href={href} key={label} onClick={() => setMenuOpen(false)} title={sidebarCollapsed ? label : undefined}><Icon size={17} /><span className="nav-label">{label}</span></Link>)}</nav><div className="sidebar-note"><ShieldCheck size={17} /><strong>Hệ thống an toàn</strong><span>Docker và PostgreSQL đang hoạt động</span></div></aside>
    <div className="content"><header className="topbar"><button className="icon-button mobile-menu" onClick={() => setMenuOpen(!menuOpen)} aria-label="Mở trình đơn"><Menu size={20} /></button><Link className="back-link" href="/websites"><ArrowLeft size={17} />Danh sách website</Link><div className="user-area"><button type="button" className="icon-button theme-toggle" onClick={toggleTheme} aria-label={theme === "dark" ? "Chuyển sang chế độ sáng" : "Chuyển sang chế độ tối"} title={theme === "dark" ? "Chế độ sáng" : "Chế độ tối"}>{theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button><NotificationBell /><span className="avatar"><CircleUserRound size={21} /></span><span><strong>Quản trị viên</strong><small>Administrator</small></span></div></header>
      <main className="detail-main">
        <section className="detail-heading"><div><div className="detail-domain"><Globe2 size={22} /><span><h1>{website.domain}</h1><p>{website.customerName} · {website.platform}</p></span></div><span className={`status ${website.status}`}>{labels[website.status] ?? website.status}</span></div><div className="detail-actions"><a className="secondary" href={website.url} target="_blank" rel="noreferrer">Mở website <ExternalLink size={15} /></a><button className="primary" disabled={pageSpeedPending || queuing} onClick={() => void scanNow()}><RefreshCw size={16} className={pageSpeedPending ? "spin" : ""} />{pageSpeedPending ? "Đang quét" : "Quét lại"}</button></div></section>
        {error && <div className="notice error">{error}</div>}
        <section className="detail-metrics"><Metric label="Uptime 30 ngày" value={website.lastCheckedAt ? `${Number(website.uptimePercent).toFixed(2)}%` : "—"} note="Từ các lần kiểm tra HTTP" /><Metric label="Thời gian phản hồi" value={latest.availability?.responseTimeMs ? `${latest.availability.responseTimeMs} ms` : "—"} note={`HTTP ${latest.availability?.details?.statusCode ?? "chưa có"}`} /><Metric label="SSL còn hạn" value={sslDays === null ? "—" : `${sslDays} ngày`} note={website.sslExpiresAt ? `Hết hạn ${formatDate(website.sslExpiresAt)}` : "Chưa có kết quả"} /><Metric label="Lần quét gần nhất" value={website.lastCheckedAt ? "Đã hoàn tất" : "Chưa quét"} note={formatDate(website.lastCheckedAt)} /></section>
        <section className="detail-grid"><article className="panel performance-panel"><div className="panel-head"><div><h2>PageSpeed Insights</h2><p>Kết quả Lighthouse gần nhất</p></div><Gauge size={19} /></div><div className="strategy-grid">{[["Mobile", latest.mobile], ["Desktop", latest.desktop]].map(([name, raw]) => { const check = raw as Check | undefined; return <div className="strategy" key={name as string}><header><strong>{name as string}</strong><span className={`big-score ${(check?.performanceScore ?? 0) >= 90 ? "good" : (check?.performanceScore ?? 0) >= 50 ? "warn" : "bad"}`}>{check?.performanceScore ?? "—"}</span></header><dl><div><dt>FCP</dt><dd>{check?.details?.fcpSeconds ? `${check.details.fcpSeconds.toFixed(2)}s` : "—"}</dd></div><div><dt>LCP</dt><dd>{check?.lcpSeconds ? `${check.lcpSeconds.toFixed(2)}s` : "—"}</dd></div><div><dt>CLS</dt><dd>{check?.clsScore ?? "—"}</dd></div></dl><small>{check ? formatDate(check.checkedAt) : "Chưa có kết quả"}</small></div>; })}</div></article>
          <article className="panel scan-info"><div className="panel-head"><div><h2>Trạng thái lần quét</h2><p>Thông tin từ worker</p></div><Clock3 size={18} /></div><dl><div><dt>Trạng thái job</dt><dd>{job?.status ?? "Chưa tạo"}</dd></div><div><dt>Số lần thực hiện</dt><dd>{job?.attempts ?? 0}</dd></div><div><dt>Bắt đầu</dt><dd>{formatDate(job?.startedAt ?? null)}</dd></div><div><dt>Hoàn thành</dt><dd>{formatDate(job?.completedAt ?? null)}</dd></div></dl>{job?.lastError && <div className="scan-error"><strong>Lỗi gần nhất</strong><p>{job.lastError}</p></div>}</article></section>
        <section className="panel wordpress-panel">
          <div className="panel-head"><div><h2>Quản lý WordPress</h2><p>Theme và kết nối quản trị</p></div><div className="wordpress-actions">{wordpress?.connected && <><button className="secondary" type="button" disabled={wordpressLoading} onClick={() => void loadWordPress(true)}><RefreshCw size={15} className={wordpressLoading ? "spin" : ""} />Làm mới</button><button className="secondary danger-button" type="button" onClick={() => void disconnectWordPress()}>Ngắt kết nối</button></>}<Plug size={19} /></div></div>
          {wordpressError && <div className="wordpress-error"><XCircle size={17} /><span>{wordpressError}</span></div>}
          {wordpressLoading && !wordpress && <div className="wordpress-empty"><RefreshCw className="spin" size={23} /><strong>Đang kiểm tra kết nối WordPress...</strong></div>}
          {!wordpressLoading && !wordpress?.connected && <div className="wordpress-empty"><span className="wordpress-logo">W</span><strong>Website chưa kết nối WordPress</strong><p>Tạo Application Password trong tài khoản quản trị WordPress, sau đó kết nối tại đây.</p><button className="primary" type="button" onClick={() => { setWordpressError(""); setWordpressModal(true); }}><KeyRound size={16} />Kết nối WordPress</button></div>}
          {wordpress?.connected && <div className="wordpress-content"><div className="wordpress-summary"><span className="wordpress-logo small">W</span><div><strong>Đã kết nối</strong><small>Tài khoản {wordpress.profile?.name ?? wordpress.username} · {wordpress.themes.length} theme</small></div><span className="status healthy">Hoạt động</span></div><div className="wordpress-columns single-column"><section><header><div><Palette size={18} /><strong>Theme</strong></div><span>{wordpress.themes.length} theme</span></header><div className="wordpress-list">{wordpress.themes.map((themeItem) => <article key={themeItem.stylesheet}><div><strong>{rendered(themeItem.name)}</strong><small>Phiên bản {themeItem.version}</small></div><span className={`theme-status ${themeItem.status}`}>{themeItem.status === "active" ? "Đang dùng" : "Chưa dùng"}</span></article>)}{wordpress.themes.length === 0 && <p className="muted">Không tìm thấy theme.</p>}</div></section></div></div>}
        </section>
        {wordpress?.connected && <section className="panel seo-posts-panel">
          <div className="panel-head"><div><h2>Bài viết & SEO</h2><p>Kiểm tra SEO on-page từ dữ liệu WordPress thật</p></div><button className="secondary" type="button" disabled={postsSeoLoading} onClick={() => void loadPostsSeo(true)}><RefreshCw size={15} className={postsSeoLoading ? "spin" : ""} />{postsSeoLoading ? "Đang phân tích" : "Làm mới SEO"}</button></div>
          {postsSeoError && <div className="wordpress-error"><XCircle size={17} /><span>{postsSeoError}</span></div>}
          {postsSeoLoading && !postsSeo && <div className="seo-loading"><RefreshCw className="spin" size={24} /><strong>Đang tải và phân tích bài viết...</strong><span>Thời gian phụ thuộc số lượng bài trên WordPress.</span></div>}
          {postsSeo && <>
            {!postsSeo.summary.rankMathDataAvailable && <div className="seo-info"><AlertTriangle size={17} /><span>Chưa đọc được điểm Rank Math. Hãy cài hoặc cập nhật SiteOps Agent 1.7 trên WordPress rồi bấm “Làm mới SEO”.</span></div>}
            <div className="seo-summary">
              <article><span>Tổng bài viết</span><strong>{postsSeo.summary.total}</strong><small>{postsSeo.summary.published} đã đăng · {postsSeo.summary.draft} bản nháp</small></article>
              <article className="average"><span>Điểm Rank Math trung bình</span><strong>{postsSeo.summary.averageScore ?? "—"}</strong><small>{postsSeo.summary.rankMathScored}/{postsSeo.summary.total} bài đã được Rank Math chấm</small></article>
              <article className="attention"><span>Cần tối ưu</span><strong>{postsSeo.summary.needsAttention}</strong><small>Bài có điểm dưới 70</small></article>
              <article><span>Nội dung ngắn</span><strong>{postsSeo.summary.shortContent}</strong><small>{postsSeo.summary.missingFeaturedImage} bài thiếu ảnh đại diện</small></article>
            </div>
            <div className="seo-toolbar"><label><Search size={16} /><input value={postSearch} onChange={(event) => setPostSearch(event.target.value)} placeholder="Tìm tiêu đề hoặc đường dẫn..." /></label><select value={postStatus} onChange={(event) => setPostStatus(event.target.value)} aria-label="Lọc bài viết"><option value="all">Tất cả bài viết</option><option value="publish">Đã đăng</option><option value="draft">Bản nháp</option><option value="attention">Cần tối ưu</option></select><span>{filteredSeoPosts.length} kết quả</span></div>
            <div className="table-wrap seo-posts-table"><table><thead><tr><th>Bài viết</th><th>Trạng thái</th><th>Ngày đăng</th><th>Điểm Rank Math</th><th>Nội dung</th><th>Thao tác</th></tr></thead><tbody>
              {pagedSeoPosts.map((post) => <tr key={post.id}><td><div className="post-title"><FileText size={17} /><div><strong>{post.title}</strong><small>/{post.slug}</small></div></div></td><td><span className={`post-status ${post.status}`}>{postStatusLabels[post.status] ?? post.status}</span></td><td className="post-dates"><strong>{formatDate(post.date ?? null)}</strong><small>Cập nhật {formatDate(post.modified ?? null)}</small></td><td><span className={`seo-score ${post.seoStatus}`} title={post.seoScore === null ? "Bài viết chưa có điểm Rank Math" : "Điểm Rank Math"}>{post.seoScore ?? "—"}</span></td><td><strong>{post.wordCount} từ</strong><small>{post.imageCount} ảnh · {post.internalLinks} link nội bộ</small></td><td><div className="post-actions"><a href={post.editUrl} target="_blank" rel="noreferrer">Sửa SEO</a>{post.link && <a href={post.link} target="_blank" rel="noreferrer" aria-label={`Mở ${post.title}`}><ExternalLink size={14} /></a>}</div></td></tr>)}
              {filteredSeoPosts.length === 0 && <tr><td colSpan={6}><div className="empty-state"><FileText size={23} /><strong>Không có bài viết phù hợp</strong><span>Thử thay đổi từ khóa hoặc bộ lọc.</span></div></td></tr>}
            </tbody></table></div>
            {filteredSeoPosts.length > 0 && <div className="seo-pagination"><span>Hiển thị {(postPage - 1) * POSTS_PER_PAGE + 1}–{Math.min(postPage * POSTS_PER_PAGE, filteredSeoPosts.length)} trong {filteredSeoPosts.length} bài</span><div><button type="button" disabled={postPage === 1} onClick={() => setPostPage((page) => Math.max(1, page - 1))} aria-label="Trang trước"><ChevronLeft size={15} /></button><strong>Trang {postPage} / {postPageCount}</strong><button type="button" disabled={postPage === postPageCount} onClick={() => setPostPage((page) => Math.min(postPageCount, page + 1))} aria-label="Trang sau"><ChevronRight size={15} /></button></div></div>}
          </>}
        </section>}
        {wordpress?.connected && <section className="panel malware-panel">
          <div className="panel-head"><div><h2>Malware Scanner</h2><p>Quét mã độc chỉ đọc, không tự động sửa hoặc xóa file</p></div><div className="wordpress-actions"><a className="secondary" href="/downloads/siteops-malware-agent-v17.zip" download="siteops-malware-agent-v17.zip">Cài Agent 1.7</a>{malwareScan?.status === "failed" && <button className="secondary" type="button" disabled={malwareStarting} onClick={() => void retryMalwareScan()}><RefreshCw size={16} className={malwareStarting ? "spin" : ""} />Tiếp tục từ {malwareScan.cursor}</button>}<button className="secondary" type="button" disabled={malwareStarting || malwareScan?.status === "queued" || malwareScan?.status === "running"} onClick={() => void startMalwareScan("quick")}><ShieldAlert size={16} />Quét nhanh</button><button className="primary" type="button" disabled={malwareStarting || malwareScan?.status === "queued" || malwareScan?.status === "running"} onClick={() => void startMalwareScan("full")}><RefreshCw size={16} className={malwareStarting || malwareScan?.status === "running" ? "spin" : ""} />Quét toàn bộ</button></div></div>
          {malwareError && <div className="wordpress-error"><XCircle size={17} /><span>{malwareError}</span></div>}
          {malwareLoading && !malwareScan && <div className="security-intro"><RefreshCw className="spin" size={26} /><strong>Đang tải trạng thái quét...</strong></div>}
          {!malwareLoading && !malwareScan && <div className="security-intro"><ShieldAlert size={30} /><strong>Chưa có lần quét malware</strong><p>Cài và kích hoạt Agent 1.7 trên WordPress. Nên chạy “Quét nhanh” trước; “Quét toàn bộ” sẽ đọc nhiều file hơn và mất nhiều thời gian hơn.</p></div>}
          {malwareScan && <>
            <div className={`malware-run ${malwareScan.status}`}><div><strong>{malwareScanStatusLabels[malwareScan.status] ?? malwareScan.status}</strong><span>{malwareScan.status === "running" ? `Đã quét ${malwareScan.scannedFiles}/${malwareScan.totalFiles || "?"} file` : malwareScan.status === "failed" ? malwareScan.lastError ?? "Không thể hoàn thành lần quét." : `${malwareScan.scanType === "quick" ? "Quét nhanh" : "Quét toàn bộ"} · tạo lúc ${formatDate(malwareScan.createdAt)}`}</span></div><b>{malwareProgress}%</b></div>
            <div className="malware-progress" aria-label={`Tiến độ ${malwareProgress}%`}><span style={{ width: `${malwareProgress}%` }} /></div>
            <div className="security-summary malware-summary"><article><span>Tổng file</span><strong>{malwareScan.totalFiles}</strong></article><article className="safe"><span>Đã quét</span><strong>{malwareScan.scannedFiles}</strong></article><article className="danger"><span>Nguy hiểm</span><strong>{malwareScan.dangerCount}</strong></article><article className="warn"><span>Cảnh báo</span><strong>{malwareScan.warningCount}</strong></article><article><span>Thông tin</span><strong>{malwareScan.infoCount}</strong></article></div>
            <div className="malware-toolbar"><div><select value={malwareSeverity} onChange={(event) => { setMalwareSeverity(event.target.value); setMalwarePage(1); }} aria-label="Lọc mức độ"><option value="">Tất cả mức độ</option><option value="danger">Nguy hiểm</option><option value="warning">Cảnh báo</option><option value="info">Thông tin</option></select><select value={malwareFindingStatus} onChange={(event) => { setMalwareFindingStatus(event.target.value); setMalwarePage(1); }} aria-label="Lọc trạng thái xử lý"><option value="">Tất cả trạng thái</option><option value="open">Chưa xử lý</option><option value="acknowledged">Đã xem</option><option value="false_positive">Báo nhầm</option><option value="resolved">Đã xử lý</option></select></div><span>{malwareFindings.total} phát hiện</span></div>
            <div className="table-wrap malware-table"><table><thead><tr><th>Mức độ</th><th>File</th><th>Phát hiện</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>
              {malwareFindings.findings.map((finding) => <tr key={finding.id}><td><span className={`malware-severity ${finding.severity}`}>{malwareSeverityLabels[finding.severity]}</span></td><td><div className="malware-file"><strong>{finding.filePath}</strong><small>{finding.component}{finding.lineNumber ? ` · dòng ${finding.lineNumber}` : ""}</small></div></td><td><span className="finding-text"><strong>{finding.title}</strong>{finding.message}</span>{finding.snippet && <code title={finding.snippet}>{finding.snippet}</code>}</td><td><span className={`finding-status ${finding.status}`}>{malwareFindingStatusLabels[finding.status]}</span></td><td><div className="finding-actions"><button type="button" disabled={finding.status === "acknowledged"} onClick={() => void updateMalwareFinding(finding.id, "acknowledged")}>Đã xem</button><button type="button" disabled={finding.status === "false_positive"} onClick={() => void updateMalwareFinding(finding.id, "false_positive")}>Báo nhầm</button></div></td></tr>)}
              {malwareFindings.findings.length === 0 && <tr><td colSpan={5}><div className="empty-state"><ShieldCheck size={24} /><strong>Không có phát hiện phù hợp</strong><span>{malwareScan.status === "completed" ? "Không tìm thấy dấu hiệu theo bộ lọc hiện tại." : "Kết quả sẽ xuất hiện trong lúc quét."}</span></div></td></tr>}
            </tbody></table></div>
            {malwareFindings.total > 0 && <div className="seo-pagination"><span>Hiển thị {(malwarePage - 1) * malwareFindings.pageSize + 1}–{Math.min(malwarePage * malwareFindings.pageSize, malwareFindings.total)} trong {malwareFindings.total} phát hiện</span><div><button type="button" disabled={malwarePage === 1} onClick={() => setMalwarePage((page) => Math.max(1, page - 1))} aria-label="Trang phát hiện trước"><ChevronLeft size={15} /></button><strong>Trang {malwarePage} / {malwarePageCount}</strong><button type="button" disabled={malwarePage === malwarePageCount} onClick={() => setMalwarePage((page) => Math.min(malwarePageCount, page + 1))} aria-label="Trang phát hiện sau"><ChevronRight size={15} /></button></div></div>}
            <footer className="security-footer"><span>Agent {malwareScan.agentVersion ?? "—"} · Bộ luật {malwareScan.rulesVersion ?? "—"} · bỏ qua {malwareScan.skippedFiles} file</span><span>{malwareScan.completedAt ? `Hoàn tất: ${formatDate(malwareScan.completedAt)}` : `Cập nhật: ${formatDate(malwareScan.updatedAt)}`}</span></footer>
          </>}
        </section>}
        {wordpress?.connected && <section className="panel security-panel"><div className="panel-head"><div><h2>Kiểm tra plugin bản quyền & mã nguồn</h2><p>So sánh checksum và tìm dấu hiệu mã cần kiểm tra</p></div><div className="wordpress-actions"><button className="primary" type="button" disabled={securityScanning} onClick={() => void scanPluginSecurity()}><ShieldCheck size={16} className={securityScanning ? "spin" : ""} />{securityScanning ? "Đang quét..." : "Quét bảo mật plugin"}</button></div></div>
          {!securityScan && <div className="security-intro"><ShieldCheck size={28} /><strong>Chưa có kết quả kiểm tra</strong><p>Tải và kích hoạt SiteOps Agent trên WordPress, sau đó bấm “Quét bảo mật plugin”. Kết quả chỉ là đánh giá kỹ thuật, không thay thế xác nhận license từ nhà cung cấp.</p></div>}
          {securityScan && <><div className="security-summary"><article><span>Tổng plugin</span><strong>{securityScan.summary.total}</strong></article><article className="safe"><span>Checksum hợp lệ</span><strong>{securityScan.summary.verified}</strong></article><article className="warn"><span>Cần kiểm tra</span><strong>{securityScan.summary.warning}</strong></article><article className="danger"><span>File thay đổi</span><strong>{securityScan.summary.modified}</strong></article><article><span>Chưa xác định</span><strong>{securityScan.summary.unknown}</strong></article></div><div className="table-wrap security-table"><table><thead><tr><th>Plugin</th><th>Nguồn / bản quyền</th><th>Tính toàn vẹn</th><th>Mức rủi ro</th><th>Phát hiện</th></tr></thead><tbody>{pagedSecurityPlugins.map((plugin) => <tr key={plugin.plugin}><td><strong>{plugin.name}</strong><small>Phiên bản {plugin.version} · {plugin.active ? "Đang bật" : "Đang tắt"}</small></td><td><span className="security-source">{plugin.source === "wordpress.org" ? "WordPress.org" : "Trả phí / tùy chỉnh"}</span><small>{plugin.licenseStatus === "not-required" ? "Không cần license trả phí" : "Cần xác minh với nhà cung cấp"}</small></td><td><span className={`security-badge ${plugin.integrity}`}>{integrityLabels[plugin.integrity]}</span></td><td><span className={`security-badge risk-${plugin.risk}`}>{riskLabels[plugin.risk]}</span></td><td><span className="finding-text">{plugin.findings[0] ?? "Không có dấu hiệu bất thường"}</span>{plugin.changedFiles.length > 0 && <small title={plugin.changedFiles.join("\n")}>{plugin.changedFiles.length} file cần xem</small>}</td></tr>)}</tbody></table></div><div className="seo-pagination"><span>Hiển thị {(securityPage - 1) * PLUGINS_PER_PAGE + 1}–{Math.min(securityPage * PLUGINS_PER_PAGE, securityScan.plugins.length)} trong {securityScan.plugins.length} plugin</span><div><button type="button" disabled={securityPage === 1} onClick={() => setSecurityPage((page) => Math.max(1, page - 1))} aria-label="Trang plugin trước"><ChevronLeft size={15} /></button><strong>Trang {securityPage} / {securityPageCount}</strong><button type="button" disabled={securityPage === securityPageCount} onClick={() => setSecurityPage((page) => Math.min(securityPageCount, page + 1))} aria-label="Trang plugin sau"><ChevronRight size={15} /></button></div></div><footer className="security-footer"><span>Agent {securityScan.agentVersion ?? "—"} · WordPress {securityScan.wordpressVersion ?? "—"} · PHP {securityScan.phpVersion ?? "—"}</span><span>Lần quét: {formatDate(securityScan.checkedAt ?? securityScan.scannedAt ?? null)}</span></footer></>}
        </section>}
        <section className="panel history-panel"><div className="panel-head"><div><h2>Lịch sử kiểm tra</h2><p>{data.activities?.length ?? 0} bản ghi gần nhất · gồm PageSpeed, plugin và malware</p></div><CheckCircle2 size={18} /></div><div className="table-wrap"><table><thead><tr><th>Thời gian</th><th>Loại kiểm tra</th><th>Kết quả</th><th>Điểm / Phản hồi</th></tr></thead><tbody>{(data.activities ?? []).map((activity) => <tr key={activity.activityId}><td>{formatDate(activity.checkedAt)}</td><td>{checkTypeLabels[activity.checkType] ?? activity.checkType}</td><td><span className={`check-result ${activity.status}`}>{activity.status === "ok" ? "Thành công" : activity.status === "running" ? "Đang chạy" : activity.status === "queued" ? "Đang chờ" : "Có lỗi"}</span></td><td>{activityValue(activity)}</td></tr>)}{!data.activities?.length && <tr><td colSpan={4}><div className="empty-state"><Activity size={24} /><strong>Chưa có lịch sử quét</strong><span>Bấm “Quét lại” để bắt đầu.</span></div></td></tr>}</tbody></table></div></section>
      </main>
    </div>
    {wordpressModal && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setWordpressModal(false)}><form className="modal" onSubmit={connectWordPress}><div><h2>Kết nối WordPress</h2><button type="button" className="icon-button" onClick={() => setWordpressModal(false)} aria-label="Đóng"><X size={18} /></button></div>{wordpressError && <div className="form-error" role="alert"><XCircle size={16} /><span>{wordpressError}</span></div>}<label>Tên đăng nhập WordPress<input name="username" autoComplete="username" required placeholder="admin" /></label><label>Application Password<input name="applicationPassword" type="password" autoComplete="new-password" required placeholder="xxxx xxxx xxxx xxxx xxxx xxxx" /></label><p>Trong WordPress: Người dùng → Hồ sơ → Mật khẩu ứng dụng. Kết nối chỉ hoạt động qua HTTPS và tài khoản cần quyền quản trị plugin.</p><footer><button type="button" className="secondary" onClick={() => setWordpressModal(false)}>Hủy</button><button className="primary" type="submit" disabled={wordpressSaving}>{wordpressSaving ? "Đang kiểm tra..." : "Kết nối"}</button></footer></form></div>}
  </div>;
}
