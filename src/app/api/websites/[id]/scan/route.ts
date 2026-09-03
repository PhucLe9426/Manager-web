import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/db";
import { queueWebsiteScan } from "@/lib/scan-queue";

export const dynamic = "force-dynamic";

export async function POST(_request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const websiteId = Number(id);
  if (!Number.isInteger(websiteId) || websiteId <= 0) {
    return NextResponse.json({ message: "Website không hợp lệ." }, { status: 400 });
  }

  const [website] = await sql`SELECT id FROM websites WHERE id = ${websiteId}`;
  if (!website) return NextResponse.json({ message: "Không tìm thấy website." }, { status: 404 });

  const job = await queueWebsiteScan(websiteId);
  return NextResponse.json({ message: "Đã đưa website vào hàng đợi quét.", job });
}
