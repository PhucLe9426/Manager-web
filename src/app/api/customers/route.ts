import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  const customers = await sql`
    SELECT
      c.id,
      c.name,
      c.contact_name AS "contactName",
      c.contact_email AS "contactEmail",
      c.contact_phone AS "contactPhone",
      c.status,
      COUNT(w.id)::int AS "websiteCount"
    FROM customers c
    LEFT JOIN websites w ON w.customer_id = c.id
    GROUP BY c.id
    ORDER BY c.created_at DESC
  `;
  return NextResponse.json({ customers });
}

export async function POST(request: NextRequest) {
  const body = (await request.json()) as {
    name?: string;
    contactName?: string;
    contactEmail?: string;
    contactPhone?: string;
  };
  const name = body.name?.trim();
  if (!name) return NextResponse.json({ message: "Tên công ty không được để trống." }, { status: 400 });

  const [customer] = await sql`
    INSERT INTO customers (name, contact_name, contact_email, contact_phone)
    VALUES (
      ${name},
      ${body.contactName?.trim() || null},
      ${body.contactEmail?.trim() || null},
      ${body.contactPhone?.trim() || null}
    )
    RETURNING id, name
  `;
  return NextResponse.json({ customer }, { status: 201 });
}
