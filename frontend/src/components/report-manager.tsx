"use client";

import { CalendarDays, Download, FileBarChart, FileText, ImagePlus, Plus, Trash2 } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { publishNotification } from "@/lib/notifications";

type Website = {
  id: number;
  domain: string;
  url: string;
  customerName: string;
  uptimePercent: number;
  mobilePerformanceScore: number | null;
  desktopPerformanceScore: number | null;
};

type Report = {
  id: number;
  title: string;
  websiteId: number;
  domain: string;
  url: string;
  customerName: string;
  periodStart: string;
  periodEnd: string;
  summary: string | null;
  itemCount: number;
  attachmentCount: number;
  createdAt: string;
};

type WorkItem = { performedDate: string; description: string; result: string; attachments: File[] };

type ReportContext = {
  pageSpeed: {
    uptimePercent?: number; responseTimeMs?: number | null; sslExpiresAt?: string | null;
    availabilityCheckedAt?: string; mobileScore?: number | null; mobileFcpSeconds?: number | null;
    mobileLcpSeconds?: number | null; mobileClsScore?: number | null; mobileCheckedAt?: string;
    desktopScore?: number | null; desktopFcpSeconds?: number | null; desktopLcpSeconds?: number | null;
    desktopClsScore?: number | null; desktopCheckedAt?: string;
  } | null;
  pluginScan: { summary?: { total?: number; verified?: number; warning?: number; modified?: number }; checkedAt?: string } | null;
  seoScan: { summary?: { total?: number; published?: number; averageScore?: number | null; needsAttention?: number }; checkedAt?: string } | null;
  malwareScan: { status?: string; scanType?: string; scannedFiles?: number; totalFiles?: number; dangerCount?: number; warningCount?: number; completedAt?: string; updatedAt?: string } | null;
};

function inputDate(value = new Date()) {
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 10);
}

function displayDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN").format(new Date(`${value.slice(0, 10)}T00:00:00`));
}

function displayDateTime(value?: string) {
  if (!value) return "Chưa có lần quét";
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value));
}

function sslRemaining(value?: string | null) {
  if (!value) return "-";
  return `${Math.max(0, Math.ceil((new Date(value).getTime() - Date.now()) / 86_400_000))} ngày`;
}

function metricSeconds(value?: number | null) {
  return value == null ? "-" : `${Number(value).toFixed(2)}s`;
}

function EvidencePreview({ file }: { file: File }) {
  const url = useMemo(() => URL.createObjectURL(file), [file]);
  useEffect(() => () => URL.revokeObjectURL(url), [url]);
  return <span className="evidence-thumb"><img src={url} alt={file.name} /><small title={file.name}>{file.name}</small></span>;
}

export function ReportManager({ websites }: { websites: Website[] }) {
  const today = useMemo(() => inputDate(), []);
  const monthStart = useMemo(() => {
    const date = new Date();
    date.setDate(1);
    return inputDate(date);
  }, []);
  const [reports, setReports] = useState<Report[]>([]);
  const [websiteId, setWebsiteId] = useState("");
  const [title, setTitle] = useState("Báo cáo chăm sóc website định kỳ");
  const [periodStart, setPeriodStart] = useState(monthStart);
  const [periodEnd, setPeriodEnd] = useState(today);
  const [summary, setSummary] = useState("");
  const [items, setItems] = useState<WorkItem[]>([{ performedDate: today, description: "", result: "Đã hoàn thành", attachments: [] }]);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [context, setContext] = useState<ReportContext | null>(null);
  const [contextLoading, setContextLoading] = useState(false);

  const selectedWebsite = websites.find((website) => website.id === Number(websiteId));

  const loadReports = useCallback(async () => {
    try {
      const response = await fetch("/api/reports", { cache: "no-store" });
      const data = (await response.json()) as { reports?: Report[]; message?: string };
      if (!response.ok) throw new Error(data.message || "Không thể tải báo cáo.");
      setReports(data.reports ?? []);
    } catch (reason) {
      void publishNotification({ category: "report", severity: "danger", title: "Không thể tải báo cáo", message: reason instanceof Error ? reason.message : "Không thể tải danh sách báo cáo.", link: "/reports" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadReports(); }, [loadReports]);

  useEffect(() => {
    if (!websiteId) { setContext(null); return; }
    const controller = new AbortController();
    setContextLoading(true);
    void fetch(`/api/reports/context/${websiteId}`, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        setContext(await response.json() as ReportContext);
      })
      .catch((reason) => { if (reason?.name !== "AbortError") setContext(null); })
      .finally(() => setContextLoading(false));
    return () => controller.abort();
  }, [websiteId]);

  function updateItem(index: number, field: "performedDate" | "description" | "result", value: string) {
    setItems((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item));
  }

  function addItem() {
    setItems((current) => [...current, { performedDate: today, description: "", result: "Đã hoàn thành", attachments: [] }]);
  }

  function removeItem(index: number) {
    setItems((current) => current.length === 1 ? current : current.filter((_, itemIndex) => itemIndex !== index));
  }

  function selectAttachments(index: number, selected: FileList | null) {
    const files = Array.from(selected ?? []);
    const accepted = files.filter((file) => ["image/jpeg", "image/png", "image/webp"].includes(file.type) && file.size <= 8 * 1024 * 1024).slice(0, 5);
    if (accepted.length !== files.length) void publishNotification({ category: "report", severity: "warning", title: "Một số ảnh không hợp lệ", message: "Chỉ nhận tối đa 5 ảnh JPG/PNG/WebP, mỗi ảnh không quá 8 MB.", link: "/reports" });
    setItems((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, attachments: accepted } : item));
  }

  async function createReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      const response = await fetch("/api/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ websiteId: Number(websiteId), title, periodStart, periodEnd, summary, items: items.map(({ attachments: _, ...item }) => item) }),
      });
      const data = (await response.json()) as { report?: { id: number; items: { id: number }[] }; message?: string };
      if (!response.ok || !data.report) throw new Error(data.message || "Không thể tạo báo cáo.");
      const uploads = items.flatMap((item, itemIndex) => item.attachments.map(async (file) => {
        const form = new FormData();
        form.append("file", file);
        const upload = await fetch(`/api/reports/${data.report!.id}/items/${data.report!.items[itemIndex].id}/attachments`, { method: "POST", body: form });
        if (!upload.ok) {
          const result = await upload.json().catch(() => ({})) as { message?: string };
          throw new Error(result.message || `Không thể tải ảnh ${file.name}.`);
        }
      }));
      const uploadResults = await Promise.allSettled(uploads);
      const failedUploads = uploadResults.filter((result) => result.status === "rejected");
      if (failedUploads.length) void publishNotification({ category: "report", severity: "warning", title: "Báo cáo đã lưu", message: `Có ${failedUploads.length} ảnh minh chứng tải lên thất bại.`, link: "/reports" });
      else void publishNotification({ category: "report", severity: "success", title: "Đã tạo báo cáo", message: `Đã lưu báo cáo${uploads.length ? ` cùng ${uploads.length} ảnh minh chứng` : ""}.`, link: "/reports" });
      setItems([{ performedDate: today, description: "", result: "Đã hoàn thành", attachments: [] }]);
      setSummary("");
      await loadReports();
      window.open(`/api/reports/${data.report.id}/pdf`, "_blank", "noopener,noreferrer");
    } catch (reason) {
      void publishNotification({ category: "report", severity: "danger", title: "Không thể tạo báo cáo", message: reason instanceof Error ? reason.message : "Vui lòng thử lại.", link: "/reports" });
    } finally {
      setSaving(false);
    }
  }

  async function deleteReport(reportId: number) {
    if (!window.confirm("Xóa báo cáo này? Thao tác không thể hoàn tác.")) return;
    const response = await fetch(`/api/reports/${reportId}`, { method: "DELETE" });
    if (!response.ok) {
      void publishNotification({ category: "report", severity: "danger", title: "Không thể xóa báo cáo", message: "Vui lòng thử lại.", link: "/reports" });
      return;
    }
    setReports((current) => current.filter((report) => report.id !== reportId));
    void publishNotification({ category: "report", severity: "success", title: "Đã xóa báo cáo", message: "Báo cáo và ảnh minh chứng liên quan đã được xóa.", link: "/reports" });
  }

  return <div className="reports-page">
    <section className="report-workspace">
      <form className="panel report-form" onSubmit={createReport}>
        <div className="panel-head"><div><h2>Tạo báo cáo mới</h2><p>Chọn website và nhập các công việc đã thực hiện</p></div><FileBarChart size={20} /></div>
        <div className="report-form-body">
          <label>Website<select required value={websiteId} onChange={(event) => setWebsiteId(event.target.value)}><option value="">Chọn website</option>{websites.map((website) => <option key={website.id} value={website.id}>{website.url} - {website.customerName}</option>)}</select><small className="report-auto-note">PDF tự lấy kết quả plugin, Bài viết & SEO, malware và thời gian quét gần nhất đã lưu trong hệ thống.</small></label>
          <label>Tiêu đề báo cáo<input required maxLength={240} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
          <div className="form-grid"><label>Từ ngày<input required type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} /></label><label>Đến ngày<input required type="date" min={periodStart} value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} /></label></div>

          <div className="work-items-title"><div><strong>Công việc đã thực hiện</strong><small>Mỗi dòng sẽ xuất hiện trong bảng công việc của PDF</small></div><button className="secondary" type="button" onClick={addItem}><Plus size={15} />Thêm dòng</button></div>
          <div className="work-items">{items.map((item, index) => <div className="work-item" key={index}>
            <header><b>Công việc {index + 1}</b><button type="button" disabled={items.length === 1} onClick={() => removeItem(index)} aria-label={`Xóa công việc ${index + 1}`}><Trash2 size={15} /></button></header>
            <label>Ngày thực hiện<input required type="date" value={item.performedDate} onChange={(event) => updateItem(index, "performedDate", event.target.value)} /></label>
            <label>Nội dung<textarea required rows={2} maxLength={2000} placeholder="Ví dụ: Cập nhật WordPress và kiểm tra giao diện..." value={item.description} onChange={(event) => updateItem(index, "description", event.target.value)} /></label>
            <label>Kết quả / ghi chú<textarea rows={2} maxLength={2000} placeholder="Ví dụ: Hoàn tất, website hoạt động bình thường" value={item.result} onChange={(event) => updateItem(index, "result", event.target.value)} /></label>
            <label className="evidence-field"><span>Ảnh minh chứng <small>(tối đa 5 ảnh)</small></span><span className="evidence-picker"><ImagePlus size={16} />{item.attachments.length ? "Chọn lại ảnh" : "Chọn ảnh từ máy"}<input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => selectAttachments(index, event.target.files)} /></span>{item.attachments.length > 0 && <span className="evidence-previews">{item.attachments.map((file, fileIndex) => <EvidencePreview key={`${file.name}-${file.lastModified}-${fileIndex}`} file={file} />)}</span>}</label>
          </div>)}</div>
          <label>Tổng kết<textarea rows={3} maxLength={5000} placeholder="Đánh giá chung và đề xuất cho khách hàng..." value={summary} onChange={(event) => setSummary(event.target.value)} /></label>
          <button className="primary report-submit" type="submit" disabled={saving || websites.length === 0}>{saving ? "Đang tạo PDF..." : "Lưu và tải PDF"}<Download size={17} /></button>
        </div>
      </form>

      <aside className="panel report-preview">
        <div className="panel-head"><div><h2>Xem trước nội dung</h2><p>Bố cục tóm tắt của báo cáo PDF</p></div><FileText size={20} /></div>
        <div className="paper-preview">
          <header><span>SITEOPS<small>WEB CARE CENTER</small></span><i /></header>
          <h3>{title || "Tiêu đề báo cáo"}</h3>
          <p className="preview-period"><CalendarDays size={13} /> {periodStart && periodEnd ? `${displayDate(periodStart)} - ${displayDate(periodEnd)}` : "Chọn kỳ báo cáo"}</p>
          <div className="preview-client"><span>Khách hàng<strong>{selectedWebsite?.customerName || "Chưa chọn"}</strong></span><span>Website<strong>{selectedWebsite?.url || "Chưa chọn"}</strong></span></div>
          <div className="preview-metrics"><span>Uptime 30 ngày<b>{context?.pageSpeed ? `${Number(context.pageSpeed.uptimePercent ?? 0).toFixed(2)}%` : selectedWebsite ? `${Number(selectedWebsite.uptimePercent).toFixed(2)}%` : "-"}</b></span><span>Phản hồi HTTP<b>{context?.pageSpeed?.responseTimeMs != null ? `${context.pageSpeed.responseTimeMs} ms` : "-"}</b></span><span>SSL còn hạn<b>{sslRemaining(context?.pageSpeed?.sslExpiresAt)}</b></span></div>
          <div className="preview-pagespeed">
            {(["mobile", "desktop"] as const).map((device) => { const label = device === "mobile" ? "Mobile" : "Desktop"; const score = context?.pageSpeed?.[`${device}Score`]; return <article key={device}><header><strong>{label}</strong><b>{score ?? (device === "mobile" ? selectedWebsite?.mobilePerformanceScore : selectedWebsite?.desktopPerformanceScore) ?? "-"}</b></header><div><span>FCP<b>{metricSeconds(context?.pageSpeed?.[`${device}FcpSeconds`])}</b></span><span>LCP<b>{metricSeconds(context?.pageSpeed?.[`${device}LcpSeconds`])}</b></span><span>CLS<b>{context?.pageSpeed?.[`${device}ClsScore`] == null ? "-" : Number(context.pageSpeed[`${device}ClsScore`]).toFixed(4)}</b></span></div><small>{displayDateTime(context?.pageSpeed?.[`${device}CheckedAt`])}</small></article>; })}
          </div>
          <div className="preview-auto-data">
            <article><span>Plugin WordPress</span><b>{contextLoading ? "Đang tải..." : context?.pluginScan ? `${context.pluginScan.summary?.total ?? 0} plugin · ${(context.pluginScan.summary?.warning ?? 0) + (context.pluginScan.summary?.modified ?? 0)} cần kiểm tra` : "Chưa có dữ liệu quét"}</b><small>{displayDateTime(context?.pluginScan?.checkedAt)}</small></article>
            <article><span>Bài viết & SEO</span><b>{contextLoading ? "Đang tải..." : context?.seoScan ? `${context.seoScan.summary?.total ?? 0} bài · Rank Math TB ${context.seoScan.summary?.averageScore ?? "-"}` : "Chưa có dữ liệu quét"}</b><small>{displayDateTime(context?.seoScan?.checkedAt)}</small></article>
            <article><span>Malware Scanner</span><b>{contextLoading ? "Đang tải..." : context?.malwareScan ? `${context.malwareScan.scannedFiles ?? 0}/${context.malwareScan.totalFiles ?? 0} file · ${(context.malwareScan.dangerCount ?? 0) + (context.malwareScan.warningCount ?? 0)} cảnh báo` : "Chưa có dữ liệu quét"}</b><small>{displayDateTime(context?.malwareScan?.completedAt ?? context?.malwareScan?.updatedAt)}</small></article>
          </div>
          <h4>Công việc đã thực hiện</h4>
          <ol>{items.filter((item) => item.description.trim()).map((item, index) => <li key={index}><span>{item.description}</span><small>{item.result || "Đã hoàn thành"}{item.attachments.length ? ` · ${item.attachments.length} ảnh minh chứng` : ""}</small></li>)}{!items.some((item) => item.description.trim()) && <li className="preview-empty">Nội dung công việc sẽ hiển thị tại đây.</li>}</ol>
          {summary && <><h4>Tổng kết</h4><p className="preview-summary">{summary}</p></>}
        </div>
      </aside>
    </section>

    <section className="panel report-list">
      <div className="panel-head"><div><h2>Báo cáo đã lưu</h2><p>Dữ liệu được lưu trong PostgreSQL</p></div><span className="record-count">{reports.length} mục</span></div>
      {loading ? <div className="empty-state"><span>Đang tải báo cáo...</span></div> : reports.length === 0 ? <div className="empty-state"><FileBarChart size={25} /><strong>Chưa có báo cáo</strong><span>Điền biểu mẫu bên trên để tạo báo cáo đầu tiên.</span></div> : <div className="report-rows">{reports.map((report) => <article key={report.id}>
        <span className="row-icon"><FileText size={18} /></span><div><strong>{report.title}</strong><small>{report.url} · {report.customerName} · {report.itemCount} công việc{report.attachmentCount ? ` · ${report.attachmentCount} ảnh` : ""}</small></div><time>{displayDate(report.periodStart)} - {displayDate(report.periodEnd)}</time><a className="secondary" href={`/api/reports/${report.id}/pdf`} target="_blank" rel="noreferrer"><Download size={15} />Tải PDF</a><button className="report-delete" type="button" onClick={() => void deleteReport(report.id)} aria-label={`Xóa ${report.title}`}><Trash2 size={16} /></button>
      </article>)}</div>}
    </section>
  </div>;
}
