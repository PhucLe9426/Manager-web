import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SiteOps — Quản lý website khách hàng",
  description: "Trung tâm giám sát và bảo trì website khách hàng.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
