"use client";

import Link from "next/link";
import { Bell, CheckCheck, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

type NotificationItem = {
  id: number; websiteId: number | null; category: string;
  severity: "info" | "success" | "warning" | "danger";
  title: string; message: string; link: string | null;
  isRead: boolean; createdAt: string; domain?: string | null;
};

function formatNotificationDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function collapseRepeatedSystemNotifications(items: NotificationItem[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (item.category !== "system") return true;
    const signature = `${item.severity}\u0000${item.title}\u0000${item.message}\u0000${item.websiteId ?? ""}`;
    if (seen.has(signature)) return false;
    seen.add(signature);
    return true;
  });
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/notifications?limit=20", { cache: "no-store" });
      if (!response.ok) return;
      const result = await response.json() as { notifications: NotificationItem[]; unreadCount: number };
      setItems(collapseRepeatedSystemNotifications(result.notifications));
      setUnreadCount(result.unreadCount);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 15000);
    const refresh = () => void load();
    window.addEventListener("siteops:notifications-changed", refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("siteops:notifications-changed", refresh);
    };
  }, [load]);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  async function markRead(id: number) {
    setItems((current) => current.map((item) => item.id === id ? { ...item, isRead: true } : item));
    setUnreadCount((current) => Math.max(0, current - (items.find((item) => item.id === id)?.isRead ? 0 : 1)));
    await fetch(`/api/notifications/${id}/read`, { method: "PATCH" });
  }

  async function markAllRead() {
    await fetch("/api/notifications/read-all", { method: "POST" });
    setItems((current) => current.map((item) => ({ ...item, isRead: true })));
    setUnreadCount(0);
  }

  return <div className="notification-shell" ref={containerRef}>
    <button type="button" className="icon-button notification" aria-label={`Thông báo${unreadCount ? `, ${unreadCount} chưa đọc` : ""}`} aria-expanded={open} onClick={() => { setOpen((current) => !current); if (!open) void load(); }}><Bell size={18} />{unreadCount > 0 && <span className="notification-count">{unreadCount > 99 ? "99+" : unreadCount}</span>}</button>
    {open && <div className="notification-panel">
      <header><div><strong>Thông báo</strong><span>{unreadCount} chưa đọc</span></div>{unreadCount > 0 && <button type="button" onClick={() => void markAllRead()}><CheckCheck size={14} />Đọc tất cả</button>}</header>
      <div className="notification-list">
        {items.map((item) => <Link href={item.link ?? "#"} key={item.id} className={`${item.isRead ? "read" : "unread"} ${item.severity}`} onClick={() => { void markRead(item.id); setOpen(false); }}><span className="notification-symbol"><ShieldAlert size={16} /></span><span><strong>{item.title}</strong><small>{item.domain ? `${item.domain} · ` : ""}{item.message}</small><time>{formatNotificationDate(item.createdAt)}</time></span></Link>)}
        {!loading && items.length === 0 && <div className="notification-empty"><Bell size={23} /><strong>Chưa có thông báo</strong><span>Kết quả quét mới sẽ xuất hiện tại đây.</span></div>}
        {loading && items.length === 0 && <div className="notification-empty"><span>Đang tải thông báo...</span></div>}
      </div>
    </div>}
  </div>;
}
