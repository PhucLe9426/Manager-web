import type { Metadata } from "next";
import "./globals.css";

const themeScript = `
  (() => {
    try {
      const saved = localStorage.getItem("siteops-theme");
      const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      document.documentElement.dataset.theme = saved === "dark" || (!saved && systemDark) ? "dark" : "light";
    } catch (_) {
      document.documentElement.dataset.theme = "light";
    }
  })();
`;

export const metadata: Metadata = {
  title: "SiteOps — Quản lý website khách hàng",
  description: "Trung tâm giám sát và bảo trì website khách hàng.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      <body>{children}</body>
    </html>
  );
}
