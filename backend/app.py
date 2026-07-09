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

@app.route('/')
def index():
    if not session.get('user'):
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=session.get('user'))

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/auth/google')
def auth_google():
    # Dummy OAuth2 Flow for UI development
    session['user'] = {
        'name': 'BQT Admin',
        'email': 'admin@bqt.parkhill.vn',
        'picture': 'https://ui-avatars.com/api/?name=Admin&background=random'
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
