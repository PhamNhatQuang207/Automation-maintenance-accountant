import os
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from flask_session import Session
from core.extractor import extract_information_from_files
from core.validator import validate_payment_record

app = Flask(__name__, 
            template_folder='../frontend/templates', 
            static_folder='../frontend/static')
# Khóa ký session: BẮT BUỘC lấy từ biến môi trường. KHÔNG dùng khóa cố định
# (khóa cố định cho phép bất kỳ ai giả mạo cookie session). Nếu thiếu, sinh khóa
# ngẫu nhiên tạm thời — session sẽ mất khi restart, kèm cảnh báo rõ ràng.
_secret = os.environ.get('FLASK_SECRET_KEY')
if not _secret:
    _secret = secrets.token_hex(32)
    print("[WARN] FLASK_SECRET_KEY chưa được đặt — dùng khóa ngẫu nhiên tạm thời "
          "(session sẽ mất khi restart). Hãy đặt FLASK_SECRET_KEY ở môi trường production.")
app.secret_key = _secret

# Cookie an toàn: chặn JS đọc cookie (HttpOnly), hạn chế gửi cross-site (SameSite=Lax
# giảm thiểu CSRF), và chỉ gửi qua HTTPS khi COOKIE_SECURE=true (bật ở production).
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', 'false').lower() in ('1', 'true'),
)

# Lưu session phía SERVER: token OAuth Google và API key KHÔNG còn nằm trong cookie
# trình duyệt (cookie chỉ chứa session id đã ký). Backend 'filesystem' không cần hạ tầng.
app.config.update(
    SESSION_TYPE='filesystem',
    SESSION_FILE_DIR=os.environ.get('SESSION_FILE_DIR', '/tmp/unc_flask_session'),
    SESSION_PERMANENT=False,
)
Session(app)

# Cấu hình giả lập cho giai đoạn thiết kế UI (mặc định TẮT; bật bằng DEMO_MODE=true)
app.config['DEMO_MODE'] = os.environ.get('DEMO_MODE', 'false').lower() in ('1', 'true')

import io
import json
import urllib.parse
import requests

# Thông tin OAuth Google: ưu tiên biến môi trường; nếu thiếu thì fallback đọc file
# client_secret.json (chỉ dùng cho dev — file này đã được .gitignore, KHÔNG commit).
CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
AUTH_URI = os.environ.get('GOOGLE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth')
TOKEN_URI = os.environ.get('GOOGLE_TOKEN_URI', 'https://oauth2.googleapis.com/token')

CLIENT_SECRET_FILE = os.path.join(os.path.dirname(__file__), 'client_secret.json')
if not (CLIENT_ID and CLIENT_SECRET) and os.path.exists(CLIENT_SECRET_FILE):
    with open(CLIENT_SECRET_FILE, 'r') as f:
        client_config = json.load(f)['web']
    CLIENT_ID = CLIENT_ID or client_config.get('client_id')
    CLIENT_SECRET = CLIENT_SECRET or client_config.get('client_secret')
    AUTH_URI = client_config.get('auth_uri', AUTH_URI)
    TOKEN_URI = client_config.get('token_uri', TOKEN_URI)

# URL chuyển hướng sau khi đăng nhập thành công
# Lưu ý: Khi chạy Docker qua Nginx ở cổng 80, REDIRECT_URI nên là cổng 80
REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost/auth/google/callback')

@app.route('/')
def index():
    if not session.get('user'):
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=session.get('user'))

@app.route('/login')
def login():
    if session.get('user'):
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/auth/google')
def auth_google():
    # Redirect user to Google Auth URI
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': ' '.join([
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]),
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent'
    }
    url = f"{AUTH_URI}?{urllib.parse.urlencode(params)}"
    return redirect(url)

@app.route('/auth/google/callback')
def auth_google_callback():
    code = request.args.get('code')
    if not code:
        return 'Không nhận được authorization code từ Google', 400

    # Exchange code for tokens
    data = {
        'code': code,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    res = requests.post(TOKEN_URI, data=data)
    if res.status_code != 200:
        return f'Lỗi khi lấy token từ Google: {res.text}', 400
        
    tokens = res.json()
    session['tokens'] = tokens

    # Get user profile information
    userinfo_url = 'https://www.googleapis.com/oauth2/v3/userinfo'
    headers = {'Authorization': f"Bearer {tokens['access_token']}"}
    userinfo_res = requests.get(userinfo_url, headers=headers)
    
    if userinfo_res.status_code == 200:
        user_data = userinfo_res.json()
        session['user'] = {
            'name': user_data.get('name'),
            'email': user_data.get('email'),
            'picture': user_data.get('picture')
        }
    else:
        # Fallback profile
        session['user'] = {
            'name': 'Google User',
            'email': 'user@gmail.com',
            'picture': 'https://ui-avatars.com/api/?name=User&background=random'
        }

    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if not session.get('user'):
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        session['api_key'] = request.form.get('api_key')
        session['ocr_model'] = request.form.get('ocr_model')
        # In real app, save this securely
        return redirect(url_for('settings', success=True))

    return render_template('settings.html',
                           api_key=session.get('api_key', ''),
                           ocr_model=session.get('ocr_model', 'gemini-2.5-flash'),
                           success=request.args.get('success'))

from core.google_connector import (
    get_google_services, parse_folder_id, parse_spreadsheet_id, 
    list_files_in_folder, read_sheet_data
)

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    if not session.get('tokens'):
        return jsonify({"status": "error", "message": "Chưa đăng nhập Google"}), 401
        
    req_data = request.get_json() or {}
    drive_link = req_data.get('drive_link')
    sheet_link = req_data.get('sheet_link')
    
    if not drive_link or not sheet_link:
        return jsonify({"status": "error", "message": "Thiếu link Drive hoặc link Master Sheets"}), 400
        
    folder_id = parse_folder_id(drive_link)
    spreadsheet_id = parse_spreadsheet_id(sheet_link)
    
    if not folder_id or not spreadsheet_id:
        return jsonify({"status": "error", "message": "Link Drive hoặc Sheets không hợp lệ"}), 400
        
    try:
        # Khởi tạo dịch vụ
        drive_service, sheets_service = get_google_services(session['tokens'])
        
        # 1. Liệt kê danh sách file trong thư mục
        files = list_files_in_folder(drive_service, folder_id)
        image_files = [f for f in files if 'image' in f['mimeType'] or 'pdf' in f['mimeType']]
        
        if not image_files:
            return jsonify({"status": "error", "message": "Không tìm thấy file ảnh hoặc PDF đề nghị thanh toán nào trong thư mục này"}), 400
            
        # 2. Đọc thử dữ liệu Sheet (Ví dụ đọc sheet TongHop_HangMuc)
        sheet_data = read_sheet_data(sheets_service, spreadsheet_id, 'TongHop_HangMuc!A1:C5')
        print(f"[API] Đã đọc dữ liệu Sheet. Số dòng: {len(sheet_data)}")
        
        # Kiểm tra cấu hình API Key
        api_key = session.get('api_key')
        ocr_model = session.get('ocr_model', 'gemini-2.5-flash')
        if not api_key:
            return jsonify({"status": "error", "message": "Vui lòng cấu hình API Key trong mục Cài đặt trước khi phân tích"}), 400
            
        # 3. Tải tất cả các file hình ảnh/PDF trong thư mục về bộ nhớ tạm (RAM)
        from core.google_connector import download_file_to_bytes
        downloaded_files = []
        for f in image_files:
            print(f"[API] Đang tải file: {f['name']}...")
            content = download_file_to_bytes(drive_service, f['id'])
            downloaded_files.append({
                'name': f['name'],
                'mimeType': f['mimeType'],
                'content': content
            })
            
        # 4. Gửi toàn bộ ảnh/PDF sang AI để trích xuất thông tin
        print(f"[API] Đang gửi {len(downloaded_files)} file sang {ocr_model} để xử lý...")
        data = extract_information_from_files(downloaded_files, api_key, ocr_model)
        
        # Chạy kiểm tra luật logic
        validation = validate_payment_record(data)

        # Lưu bản ghi đã phân tích+kiểm tra vào session (phía server) làm NGUỒN
        # ĐÁNG TIN CẬY để tạo UNC — tránh việc client sửa số tiền trước khi tạo file.
        session['last_record'] = data

        return jsonify({
            "status": "success",
            "files_found": [f['name'] for f in image_files],
            "data": data,
            "validation": validation
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi Google API: {str(e)}"}), 500

@app.route('/api/generate-unc', methods=['POST'])
def api_generate_unc():
    """Nhận 1 bản ghi hồ sơ đã duyệt và trả về file Excel UNC để tải xuống."""
    if not session.get('user'):
        return jsonify({"status": "error", "message": "Chưa đăng nhập"}), 401

    req_data = request.get_json() or {}
    # Nguồn dữ liệu ĐÁNG TIN CẬY là bản ghi server đã phân tích+kiểm tra (session).
    # Chỉ fallback về dữ liệu client khi chưa có (ví dụ gọi trực tiếp API).
    data = session.get('last_record') or req_data.get('data') or {}
    confirm_dup = bool(req_data.get('confirm'))

    # Các trường bắt buộc để dựng được UNC
    required = ['sheet', 'beneficiary', 'account', 'bank', 'remarks']
    missing = [f for f in required if not str(data.get(f) or '').strip()]
    if missing:
        return jsonify({"status": "error",
                        "message": f"Thiếu thông tin bắt buộc để tạo UNC: {', '.join(missing)}"}), 400

    # Số tiền phải là số nguyên hợp lệ (dùng cho định dạng số và đọc thành chữ)
    try:
        data['amount'] = int(data.get('amount'))
    except (TypeError, ValueError):
        return jsonify({"status": "error",
                        "message": "Số tiền (amount) không hợp lệ, không thể tạo UNC"}), 400

    # Cảnh báo thanh toán TRÙNG (cùng đơn vị thụ hưởng + số tiền) gần đây.
    from core.audit import find_recent_duplicate, record_unc
    dup = find_recent_duplicate(data['beneficiary'], data['amount'])
    if dup and not confirm_dup:
        return jsonify({
            "status": "duplicate",
            "message": (f"Đã tạo UNC cho '{data['beneficiary']}' số tiền "
                        f"{data['amount']:,} VND vào ngày {dup['created_at'][:10]}. "
                        f"Bạn có chắc muốn tạo lại?")
        }), 409

    try:
        from core.generate_unc import create_unc_file, TEMPLATE
        buf = io.BytesIO()
        create_unc_file([data], buf, ngay=data.get('request_date') or None, template=TEMPLATE)
        buf.seek(0)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi khi tạo file UNC: {str(e)}"}), 500

    # Ghi nhật ký UNC đã xuất thành công (phục vụ tra soát + phát hiện trùng lần sau).
    record_unc(data)

    filename = f"UNC_{str(data.get('sheet') or 'PARK1')[:31]}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true'), port=5000)
