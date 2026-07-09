import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from core.extractor import extract_information
from core.validator import validate_payment_record

app = Flask(__name__, 
            template_folder='../frontend/templates', 
            static_folder='../frontend/static')
app.secret_key = os.urandom(24)

# Cấu hình giả lập cho giai đoạn thiết kế UI
app.config['DEMO_MODE'] = True

import json
import urllib.parse
import requests

# Load Google Client Credentials
CLIENT_SECRET_FILE = os.path.join(os.path.dirname(__file__), 'client_secret.json')
with open(CLIENT_SECRET_FILE, 'r') as f:
    client_config = json.load(f)['web']

CLIENT_ID = client_config['client_id']
CLIENT_SECRET = client_config['client_secret']
AUTH_URI = client_config['auth_uri']
TOKEN_URI = client_config['token_uri']

# URL chuyển hướng sau khi đăng nhập thành công
# Lưu ý: Khi chạy Docker qua Nginx ở cổng 80, REDIRECT_URI nên là cổng 80
REDIRECT_URI = 'http://localhost/auth/google/callback'

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
        session['ocr_provider'] = request.form.get('ocr_provider')
        # In real app, save this securely
        return redirect(url_for('settings', success=True))
        
    return render_template('settings.html', 
                           api_key=session.get('api_key', ''),
                           ocr_provider=session.get('ocr_provider', 'gemini'),
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
        access_token = session['tokens']['access_token']
        drive_service, sheets_service = get_google_services(access_token)
        
        # 1. Liệt kê danh sách file trong thư mục
        files = list_files_in_folder(drive_service, folder_id)
        image_files = [f for f in files if 'image' in f['mimeType'] or 'pdf' in f['mimeType']]
        
        if not image_files:
            return jsonify({"status": "error", "message": "Không tìm thấy file ảnh hoặc PDF đề nghị thanh toán nào trong thư mục này"}), 400
            
        # 2. Đọc thử dữ liệu Sheet (Ví dụ đọc sheet TongHop_HangMuc)
        # Chúng ta giả lập đọc để kiểm tra kết nối Sheets
        sheet_data = read_sheet_data(sheets_service, spreadsheet_id, 'TongHop_HangMuc!A1:C5')
        print(f"[API] Đã đọc dữ liệu Sheet. Số dòng: {len(sheet_data)}")
        
        # 3. Phân tích OCR bằng AI Mock (POC)
        # Trong giai đoạn sau, ta sẽ tải file đầu tiên trong image_files và truyền qua AI
        target_file = image_files[0]
        data = extract_information(target_file['name'])
        
        # Chạy kiểm tra luật logic
        validation = validate_payment_record(data)
        
        return jsonify({
            "status": "success",
            "files_found": [f['name'] for f in image_files],
            "data": data,
            "validation": validation
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi Google API: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
