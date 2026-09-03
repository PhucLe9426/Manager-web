"use client";

import {
  Activity, AlertTriangle, Bell, CheckCircle2, ChevronRight, CircleUserRound,
  Clock3, FileBarChart, Gauge, Globe2, LayoutDashboard, ListChecks, Menu,
  Pencil, Plus, RefreshCw, Search, Server, ShieldCheck, UsersRound, X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

type Website = {
  id: number;
  domain: string;
  url: string;
  customerName: string;
  status: "healthy" | "attention" | "watching" | "monitoring" | "scanning" | "failed";
  performanceScore: number | null;
  mobilePerformanceScore: number | null;
  desktopPerformanceScore: number | null;
  uptimePercent: number;
  sslExpiresAt: string | null;
  lastCheckedAt: string | null;
};

type Customer = {
  id: number;
  name: string;
  contactName: string | null;
  contactEmail: string | null;
  contactPhone: string | null;
  status: string;
  websiteCount: number;
};

const navItems = [
  ["Tổng quan", LayoutDashboard, "/"], ["Khách hàng", UsersRound, "/customers"], ["Website", Globe2, "/websites"],
  ["Công việc", ListChecks, "/tasks"], ["Báo cáo", FileBarChart, "/reports"],
] as const;

const fallbackWebsites: Website[] = [];

const statusLabel = { healthy: "Ổn định", attention: "Cần xử lý", watching: "Theo dõi", monitoring: "Đang thiết lập", scanning: "Đang quét", failed: "Quét thất bại" };

function Score({ value }: { value: number | null }) {
  if (value === null) return <span className="score pending">—</span>;
  const tone = value >= 90 ? "good" : value >= 70 ? "warn" : "bad";
  return <span className={`score ${tone}`}>{value}</span>;
}

function websiteAddress(site: Website) {
  try {
    const parsed = new URL(site.url);
    return `${parsed.host}${parsed.pathname === "/" ? "" : parsed.pathname}${parsed.search}`;
  } catch {
    return site.domain;
  }
}

export function DashboardApp({ initialPage = "Tổng quan" }: { initialPage?: (typeof navItems)[number][0] }) {
  const [websites, setWebsites] = useState<Website[]>(fallbackWebsites);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalType, setModalType] = useState<"customer" | "website" | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [modalError, setModalError] = useState("");
  const [activePage] = useState<(typeof navItems)[number][0]>(initialPage);
  const [scanningIds, setScanningIds] = useState<number[]>([]);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);

  const loadWebsites = useCallback(async () => {
    try {
      const response = await fetch("/api/websites", { cache: "no-store" });
      if (!response.ok) throw new Error();
      const data = (await response.json()) as { websites: Website[] };
      setWebsites(data.websites);
    } catch {
      setMessage("Không thể kết nối cơ sở dữ liệu. Vui lòng kiểm tra PostgreSQL.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCustomers = useCallback(async () => {
    try {
      const response = await fetch("/api/customers", { cache: "no-store" });
      if (!response.ok) throw new Error();
      const data = (await response.json()) as { customers: Customer[] };
      setCustomers(data.customers);
    } catch {
      setMessage("Không thể tải danh sách khách hàng.");
    }
  }, []);

  useEffect(() => {
    void Promise.all([loadWebsites(), loadCustomers()]);
    const timer = window.setInterval(() => void loadWebsites(), 10000);
    return () => window.clearInterval(timer);
  }, [loadCustomers, loadWebsites]);

  useEffect(() => {
    if (modalType) setModalError("");
  }, [modalType]);

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

  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return keyword ? websites.filter((item) => `${item.domain} ${item.customerName}`.toLowerCase().includes(keyword)) : websites;
  }, [query, websites]);

  const scannedWebsites = websites.filter((site) => site.lastCheckedAt);
  const averageUptime = scannedWebsites.length
    ? scannedWebsites.reduce((total, site) => total + Number(site.uptimePercent), 0) / scannedWebsites.length
    : 0;
  const attentionCount = websites.filter((site) => site.status === "attention" || site.status === "failed").length;
  const healthScore = scannedWebsites.length
    ? Math.round(scannedWebsites.reduce((sum, site) => sum + (site.performanceScore ?? 0), 0) / scannedWebsites.length)
    : 0;
  const pageInfo = {
    "Tổng quan": ["Trung tâm vận hành", "Tổng quan hệ thống", "Theo dõi tình trạng website và công việc của đội ngũ."],
    "Khách hàng": ["Quản lý dữ liệu", "Danh sách khách hàng", "Thông tin liên hệ, gói dịch vụ và website đang phụ trách."],
    Website: ["Giám sát tập trung", "Tất cả website", "Theo dõi trạng thái, hiệu năng và thời gian hoạt động."],
    "Công việc": ["Điều phối kỹ thuật", "Công việc bảo trì", "Ưu tiên, thời hạn và tiến độ xử lý của đội ngũ."],
    "Báo cáo": ["Thống kê định kỳ", "Báo cáo khách hàng", "Tổng hợp hiệu năng, uptime và kết quả bảo trì."],
  }[activePage];

  async function addWebsite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setModalError("");
    try {
      const data = new FormData(event.currentTarget);
      const response = await fetch("/api/websites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customerId: Number(data.get("customerId")), domain: data.get("domain") }),
      });
      const result = (await response.json()) as { message?: string };
      if (!response.ok) { setModalError(result.message ?? "Không thể thêm website."); return; }
      setModalType(null);
      setMessage("Đã thêm website và đưa vào hàng đợi quét.");
      await loadWebsites();
    } catch {
      setModalError("Không thể kết nối máy chủ. Vui lòng thử lại.");
    }
  }

  async function addCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setModalError("");
    try {
      const data = new FormData(event.currentTarget);
      const response = await fetch(editingCustomer ? `/api/customers/${editingCustomer.id}` : "/api/customers", {
        method: editingCustomer ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: data.get("name"), contactName: data.get("contactName"),
          contactEmail: data.get("contactEmail"), contactPhone: data.get("contactPhone"), status: data.get("status") ?? "active",
        }),
      });
      const result = (await response.json()) as { message?: string };
      if (!response.ok) { setModalError(result.message ?? "Không thể lưu khách hàng."); return; }
      setModalType(null);
      setMessage(editingCustomer ? "Đã cập nhật thông tin khách hàng." : "Đã thêm khách hàng mới.");
      setEditingCustomer(null);
      await loadCustomers();
    } catch {
      setModalError("Không thể kết nối máy chủ. Vui lòng thử lại.");
    }
  }

  async function queueScan(websiteId: number) {
    if (scanningIds.includes(websiteId)) return { queued: true };
    setScanningIds((items) => [...items, websiteId]);
    try {
      const response = await fetch(`/api/websites/${websiteId}/scan`, { method: "POST" });
      const result = (await response.json()) as { message?: string };
      if (!response.ok) throw new Error(result.message ?? "Không thể bắt đầu quét.");
      setMessage(result.message ?? "Đã đưa website vào hàng đợi quét.");
      await loadWebsites();
      return { queued: true, websiteId };
    } finally {
      setScanningIds((items) => items.filter((id) => id !== websiteId));
    }
  }

  useEffect(() => {
    const context = (document as Document & { modelContext?: { registerTool: (tool: object, options?: { signal?: AbortSignal }) => void | Promise<void> } }).modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    void Promise.resolve(context.registerTool({
      name: "queue_website_scan",
      title: "Quét website",
      description: "Đưa một website đang quản lý vào hàng đợi kiểm tra uptime, PageSpeed và SSL.",
      inputSchema: { type: "object", properties: { websiteId: { type: "integer", minimum: 1 } }, required: ["websiteId"], additionalProperties: false },
      annotations: { readOnlyHint: false, untrustedContentHint: false },
      execute: async (input: unknown) => {
        const websiteId = Number((input as { websiteId?: unknown })?.websiteId);
        if (!Number.isInteger(websiteId) || websiteId <= 0) throw new Error("websiteId không hợp lệ");
        return await queueScan(websiteId);
      },
    }, { signal: lifecycle.signal })).catch(() => undefined);
    return () => lifecycle.abort();
  });

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? "open" : ""} ${sidebarCollapsed ? "collapsed" : ""}`}>
        <div className="brand"><span className="brand-mark"><Activity size={21} /></span><span className="brand-copy"><strong>SiteOps</strong><small>Web Care Center</small></span><button type="button" className="sidebar-toggle" onClick={toggleSidebar} aria-label={sidebarCollapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"} title={sidebarCollapsed ? "Mở rộng" : "Thu gọn"}><Menu size={21} /></button></div>
        <nav aria-label="Điều hướng chính">
          <p>Vận hành</p>
          {navItems.map(([label, Icon, href]) => <Link className={activePage === label ? "active" : ""} href={href} key={label} onClick={() => setMenuOpen(false)} title={sidebarCollapsed ? label : undefined}><Icon size={17} /><span className="nav-label">{label}</span></Link>)}
        </nav>
        <div className="sidebar-note"><ShieldCheck size={17} /><strong>Hệ thống an toàn</strong><span>Docker và PostgreSQL đã sẵn sàng</span></div>
      </aside>

      <div className="content">
        <header className="topbar">
          <button className="icon-button mobile-menu" onClick={() => setMenuOpen(!menuOpen)} aria-label="Mở trình đơn"><Menu size={20} /></button>
          <div className="user-area"><button className="icon-button notification" aria-label="Thông báo"><Bell size={18} /><i /></button><span className="avatar"><CircleUserRound size={21} /></span><span><strong>Quản trị viên</strong><small>Administrator</small></span></div>
        </header>

        <main>
          <section className="heading"><div><p>{pageInfo[0]}</p><h1>{pageInfo[1]}</h1><span>{pageInfo[2]}</span></div>{activePage === "Khách hàng" ? <button className="primary" onClick={() => { setEditingCustomer(null); setModalType("customer"); }}><Plus size={17} />Thêm khách hàng</button> : (activePage === "Tổng quan" || activePage === "Website") ? <button className="primary" onClick={() => customers.length ? setModalType("website") : setMessage("Hãy tạo khách hàng trước khi thêm website.")}><Plus size={17} />Thêm website</button> : null}</section>
          {message && <div className="notice" role="status">{message}<button onClick={() => setMessage("")} aria-label="Đóng"><X size={15} /></button></div>}

          {activePage === "Tổng quan" ? <>
          <section className="metrics" aria-label="Chỉ số tổng quan">
            <article><span className="metric-icon navy"><Globe2 /></span><div><p>Website đang quản lý</p><strong>{websites.length}</strong><small>Dữ liệu đồng bộ từ PostgreSQL</small></div></article>
            <article><span className="metric-icon green"><Activity /></span><div><p>Uptime trung bình</p><strong>{scannedWebsites.length ? `${averageUptime.toFixed(2)}%` : "—"}</strong><small>30 ngày gần nhất</small></div></article>
            <article><span className="metric-icon red"><AlertTriangle /></span><div><p>Cảnh báo cần xử lý</p><strong>{attentionCount}</strong><small>Cần đội kỹ thuật kiểm tra</small></div></article>
            <article><span className="metric-icon amber"><ListChecks /></span><div><p>Công việc đang mở</p><strong>0</strong><small>Chưa có công việc</small></div></article>
          </section>

          <section className="dashboard-grid">
            <article className="panel sites-panel">
              <div className="panel-head"><div><h2>Tình trạng website</h2><p>Uptime, hiệu năng và cảnh báo mới nhất</p></div><Link className="secondary" href="/websites">Xem tất cả <ChevronRight size={15} /></Link></div>
              <div className="panel-search-row"><label className="search table-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm website hoặc khách hàng..." /></label></div>
              <div className="table-wrap"><table><thead><tr><th>Website / Khách hàng</th><th>Trạng thái</th><th>Mobile</th><th>Máy tính</th><th>Uptime</th><th>Ghi chú</th></tr></thead><tbody>
                {filtered.map((site) => <tr key={site.id}><td><div className="site-name"><span><Globe2 size={17} /></span><div><strong>{websiteAddress(site)}</strong><small>{site.customerName}</small></div></div></td><td><span className={`status ${site.status}`}>{statusLabel[site.status]}</span></td><td><Score value={site.mobilePerformanceScore} /></td><td><Score value={site.desktopPerformanceScore} /></td><td><strong>{site.lastCheckedAt ? `${Number(site.uptimePercent).toFixed(2)}%` : "—"}</strong><small>{site.status === "scanning" ? "Đang quét..." : site.lastCheckedAt ? "Đã cập nhật" : "Chưa quét"}</small></td><td><span className="muted">{site.status === "attention" ? "Có lỗi cần ưu tiên" : site.status === "watching" ? "Cần theo dõi" : site.status === "scanning" ? "Đang chạy kiểm tra" : site.status === "monitoring" ? "Chờ lần quét đầu" : site.status === "failed" ? "Hãy thử quét lại" : "Không có lỗi mới"}</span></td></tr>)}
                {!loading && filtered.length === 0 && <tr><td colSpan={6}><div className="empty-state"><Globe2 size={25} /><strong>Chưa có website</strong><span>Bấm “Thêm website” để tạo dữ liệu đầu tiên.</span></div></td></tr>}
              </tbody></table></div>
            </article>

            <div className="right-column">
              <article className="health-card"><div><h2>Sức khỏe hệ thống</h2><Gauge size={21} /></div><p>Tổng hợp {websites.length} website</p><section><strong>{scannedWebsites.length ? healthScore : "—"}</strong><span>{scannedWebsites.length ? "Đang theo dõi" : "Chưa có dữ liệu"}</span></section><div className="progress"><i style={{ width: `${healthScore}%` }} /></div><footer><span><b>{websites.filter((site) => site.status === "healthy").length}</b>Ổn định</span><span><b>{websites.filter((site) => site.status === "watching" || site.status === "scanning").length}</b>Cần theo dõi</span><span><b>{attentionCount}</b>Có lỗi</span></footer></article>
              <article className="panel tasks"><div className="panel-head"><div><h2>Việc sắp đến hạn</h2><p>Ưu tiên trong tuần</p></div><Clock3 size={18} /></div><div className="empty-state compact"><ListChecks size={23} /><strong>Chưa có công việc</strong><span>Công việc mới sẽ xuất hiện tại đây.</span></div></article>
            </div>
          </section>

          <section className="quick-cards">
            <article><span><Server /></span><div><p>Backup gần nhất</p><strong>Chưa có dữ liệu</strong><small>Thiết lập sau khi thêm website</small></div></article>
            <article><span><ShieldCheck /></span><div><p>SSL & tên miền</p><strong>0 cảnh báo</strong><small>Chưa có website cần theo dõi</small></div></article>
            <article><span><CheckCircle2 /></span><div><p>Báo cáo tháng</p><strong>Chưa có báo cáo</strong><small>Báo cáo sẽ được tạo từ dữ liệu thật</small></div></article>
          </section>
          </> : <section className="panel module-page">
            <div className="panel-head"><div><h2>{pageInfo[1]}</h2><p>Dữ liệu được đồng bộ từ PostgreSQL</p></div><span className="record-count">{activePage === "Khách hàng" ? customers.length : activePage === "Công việc" || activePage === "Báo cáo" ? 0 : websites.length} mục</span></div>
            {activePage === "Website" && <div className="panel-search-row"><label className="search table-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm website hoặc khách hàng..." /></label></div>}
            {activePage === "Khách hàng" && <div className="module-list">{customers.map((customer) => <button type="button" className="module-row customer-row" key={customer.id} onClick={() => { setEditingCustomer(customer); setModalType("customer"); }}><span className="row-icon"><UsersRound size={18} /></span><span><strong>{customer.name}</strong><small>{customer.contactName || "Chưa có người liên hệ"}{customer.contactEmail ? ` · ${customer.contactEmail}` : ""}{customer.contactPhone ? ` · ${customer.contactPhone}` : ""}</small></span><span className="customer-meta"><b>{customer.websiteCount}</b> website<small>{customer.status === "paused" ? "Tạm dừng" : "Đang hoạt động"}</small></span><Pencil size={16} /></button>)}{!loading && customers.length === 0 && <div className="empty-state"><UsersRound size={25} /><strong>Chưa có khách hàng</strong><span>Bấm “Thêm khách hàng” để tạo công ty đầu tiên.</span></div>}</div>}
            {activePage === "Website" && <div className="module-list">{filtered.map((site) => <div className="module-row" key={site.id}><span className="row-icon"><Globe2 size={18} /></span><Link className="site-link" href={`/websites/${site.id}`}><strong>{websiteAddress(site)}</strong><small>{site.customerName} · {site.lastCheckedAt ? `Uptime ${Number(site.uptimePercent).toFixed(2)}%` : "Chưa có kết quả quét"}</small></Link><span className={`status ${site.status}`}>{statusLabel[site.status]}</span><button type="button" className="scan-action" disabled={site.status === "scanning" || scanningIds.includes(site.id)} onClick={() => void queueScan(site.id)}><RefreshCw size={14} className={site.status === "scanning" ? "spin" : ""} />{site.status === "scanning" ? "Đang quét" : "Quét ngay"}</button></div>)}</div>}
            {activePage === "Công việc" && <div className="empty-state"><ListChecks size={25} /><strong>Chưa có công việc</strong><span>Công việc thật sẽ được hiển thị tại đây.</span></div>}
            {activePage === "Báo cáo" && <div className="empty-state"><FileBarChart size={25} /><strong>Chưa có báo cáo</strong><span>Báo cáo sẽ được tạo sau khi hệ thống có dữ liệu.</span></div>}
          </section>}
        </main>
      </div>

      {modalType === "website" && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setModalType(null)}><form className="modal" onSubmit={addWebsite}><div><h2>Thêm website mới</h2><button type="button" className="icon-button" onClick={() => setModalType(null)} aria-label="Đóng"><X size={18} /></button></div>{modalError && <div className="form-error" role="alert"><X size={16} /><span>{modalError}</span></div>}<label>Khách hàng<select name="customerId" required defaultValue=""><option value="" disabled>Chọn khách hàng</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select></label><label>Tên miền hoặc URL<input name="domain" required placeholder="example.com hoặc https://example.com/store/" /></label><p>Có thể nhập một đường dẫn cụ thể. Website sẽ tự động được đưa vào hàng đợi quét.</p><footer><button type="button" className="secondary" onClick={() => setModalType(null)}>Hủy</button><button className="primary" type="submit">Thêm website</button></footer></form></div>}
      {modalType === "customer" && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setModalType(null)}><form className="modal" key={editingCustomer?.id ?? "new"} onSubmit={addCustomer}><div><h2>{editingCustomer ? "Sửa khách hàng" : "Thêm khách hàng"}</h2><button type="button" className="icon-button" onClick={() => { setModalType(null); setEditingCustomer(null); }} aria-label="Đóng"><X size={18} /></button></div>{modalError && <div className="form-error" role="alert"><X size={16} /><span>{modalError}</span></div>}<label>Tên công ty<input name="name" required placeholder="Công ty ABC" defaultValue={editingCustomer?.name ?? ""} /></label><div className="form-grid"><label>Người liên hệ<input name="contactName" placeholder="Nguyễn Văn A" defaultValue={editingCustomer?.contactName ?? ""} /></label><label>Số điện thoại<input name="contactPhone" placeholder="0900 000 000" defaultValue={editingCustomer?.contactPhone ?? ""} /></label></div><label>Email liên hệ<input name="contactEmail" type="email" placeholder="contact@company.vn" defaultValue={editingCustomer?.contactEmail ?? ""} /></label><label>Trạng thái<select name="status" defaultValue={editingCustomer?.status ?? "active"}><option value="active">Đang hoạt động</option><option value="paused">Tạm dừng</option></select></label><footer><button type="button" className="secondary" onClick={() => { setModalType(null); setEditingCustomer(null); }}>Hủy</button><button className="primary" type="submit">{editingCustomer ? "Lưu thay đổi" : "Thêm khách hàng"}</button></footer></form></div>}
    </div>
  );
}

export default function HomePage() {
  return <DashboardApp />;
}
