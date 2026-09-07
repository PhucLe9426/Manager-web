export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 240;

type RouteContext = {
  params: Promise<{ id: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  const { id } = await context.params;
  if (!/^\d+$/.test(id)) {
    return Response.json({ message: "Website không hợp lệ." }, { status: 400 });
  }

  const apiUrl = (process.env.API_INTERNAL_URL ?? "http://backend:4000").replace(/\/$/, "");

  try {
    const response = await fetch(`${apiUrl}/api/websites/${id}/wordpress/posts-seo`, {
      cache: "no-store",
      signal: AbortSignal.timeout(240_000),
    });
    const body = await response.text();

    return new Response(body || JSON.stringify({ message: "Backend không trả về dữ liệu." }), {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") ?? "application/json; charset=utf-8" },
    });
  } catch (error) {
    const message = error instanceof Error && error.name === "TimeoutError"
      ? "Quá trình tải bài viết vượt quá 240 giây."
      : "Không thể kết nối tới dịch vụ phân tích SEO.";
    return Response.json({ message }, { status: 502 });
  }
}
