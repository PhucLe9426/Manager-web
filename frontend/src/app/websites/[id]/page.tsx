import { WebsiteDetailClient } from "./website-detail-client";

export default async function WebsiteDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <WebsiteDetailClient websiteId={Number(id)} />;
}
