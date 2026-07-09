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

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """Mock API cho phân tích OCR, gọi core/extractor"""
    # Trong môi trường thật, sẽ nhận file/URL từ request và gọi LLM API
    # Ở đây chúng ta gọi hàm PoC extract_information mock
    data = extract_information("dummy_path")
    validation = validate_payment_record(data)
    
    return jsonify({
        "status": "success",
        "data": data,
        "validation": validation
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
