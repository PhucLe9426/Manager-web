# SiteOps Agent

Plugin WordPress chỉ đọc dùng để kiểm tra tính toàn vẹn và dấu hiệu rủi ro trong mã nguồn plugin.

## Cài đặt

1. Cài file `siteops-agent.zip` trong **Plugin → Cài plugin → Tải plugin lên**.
2. Kích hoạt **SiteOps Agent**.
3. Tạo Application Password cho tài khoản quản trị và kết nối website với SiteOps.
4. Trong trang chi tiết website, bấm **Quét bảo mật plugin**.

Endpoint: `POST /wp-json/siteops/v1/security/plugins`

Endpoint yêu cầu người dùng đã xác thực và có quyền `manage_options`. Plugin không gửi nội dung file, không sửa và không xóa plugin.
