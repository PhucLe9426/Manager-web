import postgres from "postgres";

// Next.js sẽ import các API route trong lúc build. Dùng URL dự phòng chỉ để
// khởi tạo client; khi container chạy, Docker Compose luôn cấp DATABASE_URL thật.
const connectionString =
  process.env.DATABASE_URL ?? "postgres://siteops:siteops_dev_change@db:5432/siteops";

const globalForDb = globalThis as unknown as { sql?: ReturnType<typeof postgres> };

export const sql =
  globalForDb.sql ??
  postgres(connectionString, {
    max: 10,
    idle_timeout: 20,
    connect_timeout: 10,
  });

if (process.env.NODE_ENV !== "production") globalForDb.sql = sql;
