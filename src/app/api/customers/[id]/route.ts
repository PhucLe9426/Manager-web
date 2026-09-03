import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function PATCH(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const customerId = Number(id);
  if (!Number.isInteger(customerId) || customerId <= 0) {
    return NextResponse.json({ message: "Khách hàng không hợp lệ." }, { status: 400 });
  }

  const body = (await request.json()) as {
    name?: string;
    contactName?: string;
    contactEmail?: string;
    contactPhone?: string;
    status?: string;
  };
  const name = body.name?.trim();
  const status = body.status?.trim();
  if (!name || !["active", "paused"].includes(status ?? "")) {
    return NextResponse.json({ message: "Thông tin khách hàng không hợp lệ." }, { status: 400 });
  }

  const [customer] = await sql`
    UPDATE customers SET
      name = ${name},
      contact_name = ${body.contactName?.trim() || null},
      contact_email = ${body.contactEmail?.trim() || null},
      contact_phone = ${body.contactPhone?.trim() || null},
      status = ${status!},
      updated_at = NOW()
    WHERE id = ${customerId}
    RETURNING id, name
  `;
  if (!customer) return NextResponse.json({ message: "Không tìm thấy khách hàng." }, { status: 404 });
  return NextResponse.json({ customer, message: "Đã cập nhật khách hàng." });
}
