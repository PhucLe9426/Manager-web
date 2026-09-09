export type NotificationSeverity = "info" | "success" | "warning" | "danger";
export type NotificationCategory = "system" | "website" | "customer" | "report" | "scan";

type NotificationPayload = {
  category?: NotificationCategory;
  severity?: NotificationSeverity;
  title: string;
  message: string;
  websiteId?: number;
  link?: string;
  eventKey?: string;
};

export async function publishNotification(payload: NotificationPayload) {
  try {
    const response = await fetch("/api/notifications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) return false;
    window.dispatchEvent(new Event("siteops:notifications-changed"));
    return true;
  } catch {
    return false;
  }
}
