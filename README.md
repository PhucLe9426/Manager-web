# SiteOps Manager

Hệ thống quản lý website khách hàng đã được tách thành các dịch vụ độc lập:

- `frontend/`: giao diện Next.js, chạy ở cổng `3000`.
- `backend/`: REST API FastAPI và kết nối PostgreSQL, chạy ở cổng `4000`.
- `backend/app/malware/`: API, nghiệp vụ và truy vấn PostgreSQL riêng của Malware Scanner.
- `worker/`: tiến trình nền kiểm tra uptime, SSL và PageSpeed mobile/desktop.
- `wordpress-agent/`: mã nguồn các SiteOps Agent cài trên WordPress.
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

## Cấu trúc backend

```text
backend/app/
├── core/           # Tiện ích và response dùng chung
├── customers/      # router/service/repository/schemas khách hàng
├── websites/       # router/service/repository/schemas website
├── monitoring/     # router/service/repository/schemas hàng đợi quét
├── wordpress_api/  # router/service/repository/schemas/client WordPress
├── malware/        # Router, service, repository và schema malware
├── database.py     # Pool kết nối và migration PostgreSQL
└── main.py         # Khởi tạo FastAPI và đăng ký router
```

Mỗi module nghiệp vụ dùng cùng quy ước:

- `router.py`: khai báo endpoint và xử lý HTTP.
- `service.py`: kiểm tra và điều phối nghiệp vụ.
- `repository.py`: truy vấn và ghi dữ liệu PostgreSQL.
- `schemas.py`: dữ liệu đầu vào/đầu ra bằng Pydantic.
- `client.py`: chỉ có ở module WordPress, giao tiếp WordPress REST API bên ngoài.

Các module giữ nguyên URL API cũ nên frontend không phụ thuộc vào cách tổ chức nội
bộ của backend. `main.py` không chứa nghiệp vụ hoặc câu truy vấn dữ liệu.

## Cấu hình

Sao chép `.env.example` thành `.env`, sau đó điền:

- `POSTGRES_PASSWORD`: mật khẩu PostgreSQL.
- `PGADMIN_DEFAULT_EMAIL`: email đăng nhập pgAdmin.
- `PGADMIN_DEFAULT_PASSWORD`: mật khẩu đăng nhập pgAdmin.
- `PGADMIN_PORT`: cổng pgAdmin trên máy, mặc định `5051`.
- `PAGESPEED_API_KEY`: API key Google PageSpeed (có thể để trống khi thử nghiệm).
- `SCAN_INTERVAL_MINUTES`: chu kỳ quét lại, mặc định 360 phút.
- `INTERNAL_WORKER_TOKEN`: khóa riêng dùng giữa FastAPI và worker.

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

## Malware Scanner MVP

1. Mở trang chi tiết một website đã kết nối WordPress.
2. Trong khối **Malware Scanner**, tải `SiteOps Agent 1.7`.
3. Vào WordPress → Plugin → Cài plugin → Tải plugin lên, chọn file ZIP và kích hoạt.
4. Quay lại SiteOps và chạy **Quét nhanh**. Chỉ dùng **Quét toàn bộ** khi cần rà soát sâu.
5. Theo dõi tiến độ, lọc phát hiện theo mức độ/trạng thái và đánh dấu **Đã xem** hoặc **Báo nhầm**.

Scanner chỉ đọc file, tính SHA-256 và tìm các mẫu mã đáng ngờ. MVP không tự xóa,
sửa hay cách ly file. Một phát hiện là tín hiệu kỹ thuật cần kiểm tra, không phải kết
luận chắc chắn website đã nhiễm malware.

## Trước khi triển khai thật

- Đổi mật khẩu PostgreSQL và lưu secret ngoài mã nguồn.
- Bổ sung đăng nhập, phân quyền và audit log.
- Đặt reverse proxy HTTPS phía trước frontend/backend.
- Thiết lập backup volume PostgreSQL và giám sát container.
