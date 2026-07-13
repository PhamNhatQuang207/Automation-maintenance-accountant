# UNC WebApp — Trợ lý tạo Ủy Nhiệm Chi cho BQT Park Hill 1

Ứng dụng web nội bộ giúp **tự động tạo Ủy Nhiệm Chi (UNC)** từ bộ hồ sơ thanh toán
bảo trì. Người dùng chỉ cần đưa link thư mục Google Drive chứa hồ sơ (ảnh/PDF) và
link File Master tổng hợp; ứng dụng sẽ:

1. Đọc toàn bộ tài liệu bằng AI (Google Gemini) và trích xuất thông tin.
2. Kiểm tra tính hợp lệ (chuỗi ngày tháng, số tiền, hóa đơn VAT…).
3. Xuất ra file Excel UNC đúng mẫu (giữ nguyên logo, chữ ký, định dạng).

> Ứng dụng được thiết kế cho **1 máy, 1 người dùng** (kế toán BQT), triển khai
> đơn giản bằng Docker.

---

## 1. Tính năng chính

- 🔎 **OCR bằng AI đa phương thức**: đọc trực tiếp ảnh và PDF nhiều trang bằng
  Google Gemini (không cần cài OCR cục bộ). Mặc định dùng **Gemini 2.5 Flash**
  (có gói miễn phí); có thể chuyển sang **Gemini 2.5 Pro** để tăng độ chính xác.
- ✅ **Kiểm tra nghiệp vụ**: cảnh báo khi thứ tự ngày sai, thiếu hóa đơn VAT, số
  tiền không khớp…
- 📄 **Tạo file UNC Excel** đúng mẫu Park Hill 1, tự đọc số tiền thành chữ tiếng Việt.
- 🔐 **Đăng nhập Google (OAuth2)** để truy cập Drive/Sheets của chính bạn.
- 🧾 **Sổ ghi UNC (SQLite)** + **cảnh báo thanh toán trùng** (cùng đơn vị thụ
  hưởng và số tiền trong 30 ngày gần nhất).

## 2. Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Backend | Python 3.12, Flask, Gunicorn |
| Giao diện | Jinja2 templates + Nginx |
| AI OCR | Google Gemini qua SDK `google-genai` |
| Session | Flask-Session (lưu phía server) |
| Sổ ghi | SQLite (thư viện chuẩn) |
| Triển khai | Docker + Docker Compose |

---

## 3. Yêu cầu trước khi cài

- **Docker Desktop** (đã bật Docker Compose).
- Một **tài khoản Google** có quyền truy cập thư mục Drive và File Master.
- **Gemini API Key** (miễn phí): https://aistudio.google.com/api-keys
- **Google OAuth Client** (Client ID + Client Secret) — xem bước 2 bên dưới.

---

## 4. Cài đặt & Chạy

### Bước 1 — Tải mã nguồn

```bash
git clone https://github.com/PhamNhatQuang207/Automation-maintenance-accountant.git
cd Automation-maintenance-accountant
```

### Bước 2 — Tạo Google OAuth Client

1. Vào [Google Cloud Console](https://console.cloud.google.com/) → tạo (hoặc chọn)
   một Project.
2. Bật 2 API: **Google Drive API** và **Google Sheets API**.
3. Vào **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
4. Chọn **Application type: Web application**.
5. Mục **Authorized redirect URIs**, thêm chính xác:
   ```
   http://localhost/auth/google/callback
   ```
6. Bấm **Create** và ghi lại **Client ID** và **Client Secret**.
7. (Nếu app đang ở chế độ *Testing*) thêm email của bạn vào mục **Test users**.

### Bước 3 — Lấy Gemini API Key

Tạo key miễn phí tại https://aistudio.google.com/api-keys và lưu lại.
> Key này bạn sẽ nhập trong trang **Cài đặt** của ứng dụng (không đặt trong `.env`).

### Bước 4 — Tạo file `.env`

Sao chép file mẫu rồi điền giá trị:

```bash
cp .env.example .env
```

Mở `.env` và điền:

```dotenv
# Sinh khóa ngẫu nhiên mạnh bằng lệnh:
#   python -c "import secrets; print(secrets.token_hex(32))"
FLASK_SECRET_KEY=dán_khóa_ngẫu_nhiên_vào_đây

# Để false khi chạy local http. Đặt true nếu chạy sau HTTPS.
COOKIE_SECURE=false
DEMO_MODE=false

# Lấy từ Bước 2
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxxxx
GOOGLE_REDIRECT_URI=http://localhost/auth/google/callback
```

> File `.env` đã được `.gitignore` — sẽ không bị đẩy lên GitHub.

### Bước 5 — Khởi động bằng Docker

```bash
docker compose up -d --build
```

Chờ build xong, ứng dụng chạy tại: **http://localhost**

Các lệnh hữu ích:

```bash
docker compose logs -f backend   # xem log
docker compose down              # dừng ứng dụng
docker compose up -d --build     # chạy lại sau khi cập nhật mã
```

### Bước 6 — Đăng nhập & cấu hình

1. Mở http://localhost → **Đăng nhập bằng Google**.
2. Vào **Cài đặt** → nhập **Gemini API Key** → chọn model (Flash hoặc Pro) → Lưu.

---

## 5. Cách sử dụng

1. Ở trang **Dashboard**, dán:
   - **Link Folder Google Drive** chứa hồ sơ (ảnh/PDF: Tờ trình, Hợp đồng, Nghiệm
     thu, Đề nghị thanh toán, Hóa đơn VAT…).
   - **Link File Master** (TonghopBaotri).
2. Bấm **Bắt đầu phân tích AI** → xem kết quả trích xuất và các cảnh báo kiểm tra.
3. Kiểm tra lại thông tin, sau đó bấm **Duyệt & Tạo File UNC**.
4. File Excel UNC sẽ được tải xuống máy.

**Cảnh báo trùng:** nếu bạn đã tạo UNC cho cùng đơn vị thụ hưởng và cùng số tiền
trong 30 ngày gần đây, ứng dụng sẽ hỏi lại để tránh thanh toán trùng. Bạn có thể
xác nhận để vẫn tạo.

---

## 6. Dữ liệu & Bảo mật

- **Sổ ghi UNC** lưu tại `backend/data/unc_ledger.db` (SQLite, trên máy bạn, không
  đẩy lên Git). Đổi vị trí bằng biến `UNC_DB_PATH` nếu cần.
- **Token Google và API Key** được lưu **phía server** (không nằm trong cookie
  trình duyệt); cookie chỉ chứa mã phiên đã ký.
- Phiên đăng nhập sẽ mất khi khởi động lại (đăng nhập lại là bình thường vì dùng
  không thường xuyên).
- Khi chạy thật sau **HTTPS**, đặt `COOKIE_SECURE=true` và cập nhật
  `GOOGLE_REDIRECT_URI` sang địa chỉ `https://...` (nhớ khai báo lại trong Google
  Cloud Console).

---

## 7. Chạy kiểm thử (test)

```bash
docker compose run --rm --no-deps backend sh -c "pip install -q pytest && python -m pytest tests/ -q"
```

---

## 8. Cấu trúc thư mục

```
.
├── docker-compose.yml         # Điều phối 2 dịch vụ backend + frontend
├── .env.example               # Mẫu biến môi trường (sao thành .env)
├── backend/
│   ├── app.py                 # Flask app: đăng nhập, /api/analyze, /api/generate-unc
│   ├── core/
│   │   ├── extractor.py       # Gọi Gemini để OCR & trích xuất JSON
│   │   ├── validator.py       # Kiểm tra nghiệp vụ (ngày tháng, số tiền, VAT)
│   │   ├── generate_unc.py    # Dựng file Excel UNC theo mẫu
│   │   ├── audit.py           # Sổ ghi SQLite + phát hiện trùng
│   │   └── google_connector.py# Truy cập Drive/Sheets
│   ├── assets/UNC_TEMPLATE.xlsx
│   ├── tests/test_app.py
│   └── requirements.txt
└── frontend/
    ├── templates/             # Giao diện (Jinja2)
    ├── static/                # CSS/JS
    └── nginx.conf
```

---

## 9. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Bấm đăng nhập báo `redirect_uri_mismatch` | Kiểm tra **Authorized redirect URI** trong Google Console phải đúng `http://localhost/auth/google/callback` |
| `Vui lòng cấu hình API Key` | Vào **Cài đặt** nhập Gemini API Key |
| `Không tìm thấy file ảnh hoặc PDF` | Thư mục Drive phải chứa file ảnh/PDF và đã chia sẻ đúng tài khoản đăng nhập |
| Không mở được http://localhost | Kiểm tra cổng 80 có bị ứng dụng khác chiếm không; xem `docker compose logs -f` |
| Muốn đổi model AI | Vào **Cài đặt** chọn Gemini 2.5 Pro (chính xác hơn) hoặc Flash (nhanh, miễn phí) |
