# SiteOps Manager

Hệ thống quản lý website khách hàng đã được tách thành các dịch vụ độc lập:

- `frontend/`: giao diện Next.js, chạy ở cổng `3000`.
- `backend/`: REST API FastAPI và kết nối PostgreSQL, chạy ở cổng `4000`.
- `worker/`: tiến trình nền kiểm tra uptime, SSL và PageSpeed mobile/desktop.
- `docker/postgres/`: schema PostgreSQL.
- `pgadmin`: giao diện quản trị PostgreSQL, mặc định chạy ở cổng `5051`.

## Chạy toàn bộ bằng Docker

```powershell
docker compose up --build -d
docker compose ps
```

Mở giao diện tại `http://localhost:3000`. Tài liệu tương tác của API nằm tại
`http://localhost:4000/docs`, và health check tại `http://localhost:4000/api/health`.

Mở pgAdmin tại `http://localhost:5051`. Đăng nhập bằng
`PGADMIN_DEFAULT_EMAIL` và `PGADMIN_DEFAULT_PASSWORD` trong file `.env`.
Server `SiteOps PostgreSQL` được tạo sẵn với các thông số:

- Host: `db`
- Port: `5432`
- Database: `siteops`
- Username: `siteops`
- Password: giá trị `POSTGRES_PASSWORD` trong `.env`

Frontend chuyển tiếp các đường dẫn `/api/*` sang FastAPI thông qua biến
`API_INTERNAL_URL`, vì vậy trình duyệt không cần gọi chéo cổng và không gặp lỗi CORS.

## Cấu hình

Sao chép `.env.example` thành `.env`, sau đó điền:

- `POSTGRES_PASSWORD`: mật khẩu PostgreSQL.
- `PGADMIN_DEFAULT_EMAIL`: email đăng nhập pgAdmin.
- `PGADMIN_DEFAULT_PASSWORD`: mật khẩu đăng nhập pgAdmin.
- `PGADMIN_PORT`: cổng pgAdmin trên máy, mặc định `5051`.
- `PAGESPEED_API_KEY`: API key Google PageSpeed (có thể để trống khi thử nghiệm).
- `SCAN_INTERVAL_MINUTES`: chu kỳ quét lại, mặc định 360 phút.

Không commit file `.env` lên GitHub.

## Chạy từng phần khi phát triển

Khởi động database:

```powershell
docker compose up -d db
```

Backend FastAPI:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL="postgres://siteops:siteops_dev_change@localhost:5432/siteops"
uvicorn app.main:app --reload --port 4000
```

Frontend Next.js (mở terminal khác):

```powershell
cd frontend
npm install
$env:API_INTERNAL_URL="http://localhost:4000"
npm run dev
```

Worker thường nên chạy bằng Docker để giữ môi trường giống production:

```powershell
docker compose up -d worker
```

## Trước khi triển khai thật

- Đổi mật khẩu PostgreSQL và lưu secret ngoài mã nguồn.
- Bổ sung đăng nhập, phân quyền và audit log.
- Đặt reverse proxy HTTPS phía trước frontend/backend.
- Thiết lập backup volume PostgreSQL và giám sát container.
