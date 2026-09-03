# SiteOps Manager

Bộ khung quản lý website khách hàng, gồm dashboard Next.js, API nội bộ, PostgreSQL, worker quét website và Docker Compose.

## Chạy bằng Docker

```bash
docker compose up --build -d
```

Mở `http://localhost:3000`. Kiểm tra trạng thái:

```bash
docker compose ps
curl http://localhost:3000/api/health
```

Worker tự quét website mới và quét lại theo chu kỳ `SCAN_INTERVAL_MINUTES`. Kết quả gồm trạng thái truy cập, thời gian phản hồi, uptime 30 ngày, PageSpeed mobile/desktop và hạn SSL. Có thể thêm `PAGESPEED_API_KEY` vào file `.env` để dùng quota Google riêng.

## Chạy chế độ phát triển

1. Khởi động riêng PostgreSQL: `docker compose up -d db`
2. Sao chép `.env.example` thành `.env.local`.
3. Chạy `npm install`, sau đó `npm run dev`.

## Cấu trúc chính

- `src/app`: dashboard và API route.
- `src/lib/db.ts`: kết nối PostgreSQL.
- `docker/postgres/init.sql`: schema, chỉ mục và dữ liệu mẫu.
- `docker-compose.yml`: app, database, health-check và volume.

## Trước khi đưa lên máy chủ thật

- Đổi `POSTGRES_PASSWORD` bằng secret mạnh.
- Bổ sung đăng nhập, phân quyền và nhật ký thao tác.
- Cấu hình HTTPS/reverse proxy, backup volume và giám sát định kỳ.
