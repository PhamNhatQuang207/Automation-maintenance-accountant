"""
Test suite cho UNC AutoBot Web App
Bao phủ tất cả các kịch bản lỗi đầu vào của user:
- API Key sai / trống / nhầm provider
- Link folder Drive sai định dạng / không tồn tại / trống
- Link Sheets sai định dạng / không tồn tại / trống  
- Validator: logic thời gian, số tiền, v.v.
- Extractor: parse lỗi từ AI response
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

# ────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Tạo Flask test client, mock bỏ qua việc load client_secret.json."""
    import builtins
    original_open = builtins.open

    # Mock client_secret.json để app.py không crash khi import
    fake_secret = json.dumps({
        "web": {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    })

    def patched_open(path, *args, **kwargs):
        if 'client_secret.json' in str(path):
            from io import StringIO
            return StringIO(fake_secret)
        return original_open(path, *args, **kwargs)

    with patch('builtins.open', patched_open):
        # Import lại app module với mock
        import importlib
        import sys
        # Xóa cache nếu đã import trước đó
        for mod_name in list(sys.modules.keys()):
            if 'app' in mod_name or 'core' in mod_name:
                del sys.modules[mod_name]
        
        sys.path.insert(0, 'backend')
        from app import app as flask_app
        
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test_key'
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_client(client, app):
    """Client đã đăng nhập (có session user + tokens)."""
    with client.session_transaction() as sess:
        sess['user'] = {
            'name': 'Test User',
            'email': 'test@gmail.com',
            'picture': 'https://ui-avatars.com/api/?name=Test'
        }
        sess['tokens'] = {
            'access_token': 'fake_access_token',
            'refresh_token': 'fake_refresh_token'
        }
        sess['api_key'] = 'AIzaSyTest_VALID_KEY_1234567890'
        sess['ocr_model'] = 'gemini-2.5-pro'
    return client


# ════════════════════════════════════════════════════
# NHÓM 1: AUTH - Chưa đăng nhập
# ════════════════════════════════════════════════════

class TestAuth:
    """Kiểm tra các route khi user chưa đăng nhập."""

    def test_redirect_to_login_when_not_logged_in(self, client):
        """GET / phải redirect về /login nếu chưa đăng nhập."""
        res = client.get('/', follow_redirects=False)
        assert res.status_code == 302
        assert '/login' in res.headers['Location']

    def test_api_analyze_returns_401_when_not_logged_in(self, client):
        """POST /api/analyze phải trả 401 nếu chưa có token."""
        res = client.post('/api/analyze',
                          data=json.dumps({'drive_link': 'https://drive.google.com/drive/folders/abc',
                                           'sheet_link': 'https://docs.google.com/spreadsheets/d/xyz'}),
                          content_type='application/json')
        assert res.status_code == 401
        data = res.get_json()
        assert data['status'] == 'error'
        assert 'Chưa đăng nhập' in data['message']


# ════════════════════════════════════════════════════
# NHÓM 2: INPUT VALIDATION - Link sai định dạng
# ════════════════════════════════════════════════════

class TestInputValidation:
    """Kiểm tra xử lý khi user nhập link sai hoặc thiếu."""

    def test_missing_drive_link(self, logged_in_client):
        """Thiếu drive_link → 400."""
        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({'sheet_link': 'https://docs.google.com/spreadsheets/d/xyz'}),
                                    content_type='application/json')
        assert res.status_code == 400
        assert 'Thiếu link' in res.get_json()['message']

    def test_missing_sheet_link(self, logged_in_client):
        """Thiếu sheet_link → 400."""
        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({'drive_link': 'https://drive.google.com/drive/folders/abc'}),
                                    content_type='application/json')
        assert res.status_code == 400
        assert 'Thiếu link' in res.get_json()['message']

    def test_empty_body(self, logged_in_client):
        """Body rỗng → 400."""
        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({}),
                                    content_type='application/json')
        assert res.status_code == 400

    def test_invalid_drive_link_format(self, logged_in_client):
        """Link Drive không chứa /folders/ → parse ra None → 400."""
        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({
                                        'drive_link': 'https://drive.google.com/file/d/abc',
                                        'sheet_link': 'https://docs.google.com/spreadsheets/d/xyz'
                                    }),
                                    content_type='application/json')
        assert res.status_code == 400
        assert 'không hợp lệ' in res.get_json()['message']

    def test_invalid_sheet_link_format(self, logged_in_client):
        """Link Sheets không chứa /spreadsheets/d/ → parse ra None → 400."""
        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({
                                        'drive_link': 'https://drive.google.com/drive/folders/abc123',
                                        'sheet_link': 'https://docs.google.com/document/d/xyz'
                                    }),
                                    content_type='application/json')
        assert res.status_code == 400
        assert 'không hợp lệ' in res.get_json()['message']

    def test_random_url_not_google(self, logged_in_client):
        """URL hoàn toàn không phải Google → parse ra None → 400."""
        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({
                                        'drive_link': 'https://example.com/something',
                                        'sheet_link': 'https://facebook.com/page'
                                    }),
                                    content_type='application/json')
        assert res.status_code == 400
        assert 'không hợp lệ' in res.get_json()['message']

    def test_plain_text_not_url(self, logged_in_client):
        """Nhập text bình thường, không phải URL → 400."""
        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({
                                        'drive_link': 'xin chao toi la folder',
                                        'sheet_link': 'day la sheet master'
                                    }),
                                    content_type='application/json')
        assert res.status_code == 400


# ════════════════════════════════════════════════════
# NHÓM 3: API KEY & PROVIDER - Key sai, nhầm provider
# ════════════════════════════════════════════════════

class TestApiKeyValidation:
    """Kiểm tra xử lý khi user chưa nhập API Key hoặc nhập sai."""

    @patch('app.list_files_in_folder')
    @patch('app.read_sheet_data')
    @patch('app.get_google_services')
    def test_missing_api_key(self, mock_gservices, mock_sheet, mock_files, logged_in_client):
        """Chưa cấu hình API Key → 400."""
        mock_gservices.return_value = (MagicMock(), MagicMock())
        mock_files.return_value = [{'id': '1', 'name': 'test.jpg', 'mimeType': 'image/jpeg'}]
        mock_sheet.return_value = [['A', 'B']]

        # Xóa api_key khỏi session
        with logged_in_client.session_transaction() as sess:
            sess.pop('api_key', None)

        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({
                                        'drive_link': 'https://drive.google.com/drive/folders/abc123',
                                        'sheet_link': 'https://docs.google.com/spreadsheets/d/xyz123'
                                    }),
                                    content_type='application/json')
        assert res.status_code == 400
        assert 'API Key' in res.get_json()['message']

    @patch('core.google_connector.download_file_to_bytes')
    @patch('app.extract_information_from_files')
    @patch('app.list_files_in_folder')
    @patch('app.read_sheet_data')
    @patch('app.get_google_services')
    def test_invalid_gemini_api_key(self, mock_gservices, mock_sheet, mock_files, mock_extract, mock_download, logged_in_client):
        """API Key Gemini sai → Gemini trả 400/403 → exception → 500."""
        mock_gservices.return_value = (MagicMock(), MagicMock())
        mock_files.return_value = [{'id': '1', 'name': 'test.jpg', 'mimeType': 'image/jpeg'}]
        mock_sheet.return_value = [['A', 'B']]
        mock_download.return_value = b'fake_image_bytes'
        mock_extract.side_effect = Exception("Lỗi gọi Gemini API (Status 400): API key not valid")

        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({
                                        'drive_link': 'https://drive.google.com/drive/folders/abc123',
                                        'sheet_link': 'https://docs.google.com/spreadsheets/d/xyz123'
                                    }),
                                    content_type='application/json')
        assert res.status_code == 500
        data = res.get_json()
        assert 'API key not valid' in data['message'] or 'Gemini' in data['message']


# ════════════════════════════════════════════════════
# NHÓM 4: GOOGLE DRIVE / SHEETS - Folder / Sheet lỗi
# ════════════════════════════════════════════════════

class TestGoogleApiErrors:
    """Kiểm tra lỗi khi thao tác với Google Drive / Sheets."""

    @patch('app.get_google_services')
    def test_folder_not_found_404(self, mock_gservices, logged_in_client):
        """Folder ID đúng format nhưng không tồn tại trên Drive → Google trả 404."""
        from googleapiclient.errors import HttpError
        mock_drive = MagicMock()
        mock_sheets = MagicMock()
        mock_gservices.return_value = (mock_drive, mock_sheets)

        # Giả lập lỗi 404 từ Drive API
        http_error = HttpError(
            resp=MagicMock(status=404),
            content=b'File not found: folder_that_does_not_exist'
        )
        mock_drive.files().list().execute.side_effect = http_error

        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({
                                        'drive_link': 'https://drive.google.com/drive/folders/folder_that_does_not_exist',
                                        'sheet_link': 'https://docs.google.com/spreadsheets/d/xyz123'
                                    }),
                                    content_type='application/json')
        assert res.status_code == 500
        assert 'Google API' in res.get_json()['message'] or 'not found' in res.get_json()['message'].lower()

    @patch('app.list_files_in_folder')
    @patch('app.get_google_services')
    def test_folder_is_empty_no_images(self, mock_gservices, mock_files, logged_in_client):
        """Folder tồn tại nhưng không có file ảnh/PDF → 400."""
        mock_gservices.return_value = (MagicMock(), MagicMock())
        mock_files.return_value = []  # Không có file nào

        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({
                                        'drive_link': 'https://drive.google.com/drive/folders/empty_folder',
                                        'sheet_link': 'https://docs.google.com/spreadsheets/d/xyz123'
                                    }),
                                    content_type='application/json')
        assert res.status_code == 400
        assert 'Không tìm thấy file' in res.get_json()['message']

    @patch('app.list_files_in_folder')
    @patch('app.get_google_services')
    def test_folder_has_only_docx_no_images(self, mock_gservices, mock_files, logged_in_client):
        """Folder chỉ có file .docx, .xlsx (không có ảnh/PDF) → 400."""
        mock_gservices.return_value = (MagicMock(), MagicMock())
        mock_files.return_value = [
            {'id': '1', 'name': 'report.docx', 'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'},
            {'id': '2', 'name': 'data.xlsx', 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},
        ]

        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({
                                        'drive_link': 'https://drive.google.com/drive/folders/folder_with_docx',
                                        'sheet_link': 'https://docs.google.com/spreadsheets/d/xyz123'
                                    }),
                                    content_type='application/json')
        assert res.status_code == 400
        assert 'Không tìm thấy file' in res.get_json()['message']

    @patch('app.get_google_services')
    def test_sheet_not_found_or_no_permission(self, mock_gservices, logged_in_client):
        """Spreadsheet ID sai hoặc không có quyền → Google trả 403."""
        from googleapiclient.errors import HttpError

        mock_drive = MagicMock()
        mock_sheets = MagicMock()
        mock_gservices.return_value = (mock_drive, mock_sheets)

        # Drive list_files OK
        mock_drive.files().list().execute.return_value = {
            'files': [{'id': '1', 'name': 'test.jpg', 'mimeType': 'image/jpeg'}]
        }

        # Sheets read trả 403
        http_error = HttpError(
            resp=MagicMock(status=403),
            content=b'The caller does not have permission'
        )
        mock_sheets.spreadsheets().values().get().execute.side_effect = http_error

        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({
                                        'drive_link': 'https://drive.google.com/drive/folders/valid_folder',
                                        'sheet_link': 'https://docs.google.com/spreadsheets/d/no_permission_sheet'
                                    }),
                                    content_type='application/json')
        assert res.status_code == 500
        assert 'Google API' in res.get_json()['message']

    @patch('app.get_google_services')
    def test_token_expired(self, mock_gservices, logged_in_client):
        """Access token hết hạn và refresh thất bại → Google trả 401."""
        from googleapiclient.errors import HttpError
        mock_drive = MagicMock()
        mock_gservices.return_value = (mock_drive, MagicMock())

        http_error = HttpError(
            resp=MagicMock(status=401),
            content=b'Request had invalid authentication credentials'
        )
        mock_drive.files().list().execute.side_effect = http_error

        res = logged_in_client.post('/api/analyze',
                                    data=json.dumps({
                                        'drive_link': 'https://drive.google.com/drive/folders/abc',
                                        'sheet_link': 'https://docs.google.com/spreadsheets/d/xyz'
                                    }),
                                    content_type='application/json')
        assert res.status_code == 500
        assert 'Google API' in res.get_json()['message']


# ════════════════════════════════════════════════════
# NHÓM 5: VALIDATOR - Logic kiểm tra thời gian & số tiền
# ════════════════════════════════════════════════════

class TestValidator:
    """Kiểm tra logic validate_payment_record() trực tiếp."""

    def test_valid_record(self):
        """Hồ sơ hoàn toàn hợp lệ, chuỗi thời gian đúng thứ tự."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': '01/01/2026',
            'approval_date': '05/01/2026',
            'contract_date': '10/01/2026',
            'acceptance_date': '20/01/2026',
            'vat_date': '21/01/2026',
            'request_date': '22/01/2026',
            'amount': 30000000,
            'vat_amount': 30000000,
        }
        result = validate_payment_record(data)
        assert result['is_valid'] is True
        assert len(result['errors']) == 0

    def test_proposal_date_after_approval_date(self):
        """Ngày đề xuất SAU ngày duyệt → Lỗi."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': '15/02/2026',
            'approval_date': '01/02/2026',
            'contract_date': '20/02/2026',
            'acceptance_date': '25/02/2026',
            'vat_date': '26/02/2026',
            'request_date': '27/02/2026',
            'amount': 10000000,
            'vat_amount': 10000000,
        }
        result = validate_payment_record(data)
        assert result['is_valid'] is False
        assert any('Ngày đề xuất sau Ngày duyệt' in e for e in result['errors'])

    def test_proposal_date_equals_approval_date(self):
        """Ngày đề xuất BẰNG ngày duyệt → Hợp lệ (<=)."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': '10/03/2026',
            'approval_date': '10/03/2026',
            'contract_date': '15/03/2026',
            'acceptance_date': '20/03/2026',
            'vat_date': '21/03/2026',
            'request_date': '22/03/2026',
            'amount': 5000000,
            'vat_amount': 5000000,
        }
        result = validate_payment_record(data)
        assert not any('Ngày đề xuất sau Ngày duyệt' in e for e in result['errors'])

    def test_contract_date_after_acceptance_date(self):
        """Ngày hợp đồng SAU ngày nghiệm thu → Lỗi."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': '01/01/2026',
            'approval_date': '05/01/2026',
            'contract_date': '25/01/2026',
            'acceptance_date': '20/01/2026',
            'vat_date': '26/01/2026',
            'request_date': '27/01/2026',
            'amount': 8000000,
            'vat_amount': 8000000,
        }
        result = validate_payment_record(data)
        assert result['is_valid'] is False
        assert any('Hợp đồng sau Nghiệm thu' in e for e in result['errors'])

    def test_approval_after_contract_is_warning_not_error(self):
        """Ngày duyệt SAU ngày báo giá → Cảnh báo (không phải lỗi cứng)."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': '01/01/2026',
            'approval_date': '20/01/2026',
            'contract_date': '10/01/2026',
            'acceptance_date': '25/01/2026',
            'vat_date': '26/01/2026',
            'request_date': '27/01/2026',
            'amount': 6000000,
            'vat_amount': 6000000,
        }
        result = validate_payment_record(data)
        assert any('Báo giá lấy trước' in w for w in result['warnings'])
        # Không phải lỗi cứng
        assert not any('Báo giá' in e for e in result['errors'])

    def test_missing_vat_date_is_warning(self):
        """Không có ngày VAT → Cảnh báo (chưa có hóa đơn)."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': '01/01/2026',
            'approval_date': '05/01/2026',
            'contract_date': '10/01/2026',
            'acceptance_date': '20/01/2026',
            'vat_date': None,
            'request_date': '22/01/2026',
            'amount': 12000000,
            'vat_amount': None,
        }
        result = validate_payment_record(data)
        assert any('chưa có Hóa đơn VAT' in w for w in result['warnings'])

    def test_vat_amount_mismatch(self):
        """Số tiền đề nghị TT KHÔNG KHỚP số tiền trên VAT → Lỗi."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': '01/01/2026',
            'approval_date': '05/01/2026',
            'contract_date': '10/01/2026',
            'acceptance_date': '20/01/2026',
            'vat_date': '21/01/2026',
            'request_date': '22/01/2026',
            'amount': 30520800,
            'vat_amount': 2260800,  # Chỉ lấy riêng tiền thuế, không phải tổng
        }
        result = validate_payment_record(data)
        assert result['is_valid'] is False
        assert any('không khớp số tiền VAT' in e for e in result['errors'])

    def test_vat_amount_matches(self):
        """Số tiền đề nghị TT KHỚP số tiền trên VAT → OK."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': '01/01/2026',
            'approval_date': '05/01/2026',
            'contract_date': '10/01/2026',
            'acceptance_date': '20/01/2026',
            'vat_date': '21/01/2026',
            'request_date': '22/01/2026',
            'amount': 30520800,
            'vat_amount': 30520800,
        }
        result = validate_payment_record(data)
        assert not any('không khớp' in e for e in result['errors'])

    def test_vat_amount_as_string(self):
        """vat_amount từ AI trả về dạng string → parse int thành công → so sánh đúng."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': '01/01/2026',
            'approval_date': '05/01/2026',
            'contract_date': '10/01/2026',
            'acceptance_date': '20/01/2026',
            'vat_date': '21/01/2026',
            'request_date': '22/01/2026',
            'amount': 5000000,
            'vat_amount': '5000000',
        }
        result = validate_payment_record(data)
        assert not any('không khớp' in e for e in result['errors'])

    def test_vat_amount_null_string_ignored(self):
        """vat_amount = "null" (string) → bỏ qua, không báo lỗi khớp tiền."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': '01/01/2026',
            'approval_date': '05/01/2026',
            'vat_date': '21/01/2026',
            'amount': 5000000,
            'vat_amount': 'null',
        }
        result = validate_payment_record(data)
        assert not any('không khớp' in e for e in result['errors'])

    def test_vat_amount_none_string_ignored(self):
        """vat_amount = "None" (string) → bỏ qua."""
        from core.validator import validate_payment_record
        data = {'amount': 5000000, 'vat_amount': 'None', 'vat_date': '01/01/2026'}
        result = validate_payment_record(data)
        assert not any('không khớp' in e for e in result['errors'])

    def test_vat_amount_empty_string_ignored(self):
        """vat_amount = "" → bỏ qua."""
        from core.validator import validate_payment_record
        data = {'amount': 5000000, 'vat_amount': '', 'vat_date': '01/01/2026'}
        result = validate_payment_record(data)
        assert not any('không khớp' in e for e in result['errors'])

    def test_all_dates_missing(self):
        """Tất cả ngày đều null → không crash, không báo lỗi thời gian."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': None,
            'approval_date': None,
            'contract_date': None,
            'acceptance_date': None,
            'vat_date': None,
            'request_date': None,
            'amount': 1000000,
            'vat_amount': None,
        }
        result = validate_payment_record(data)
        # Không có lỗi thời gian (vì không có dữ liệu để so)
        assert not any('thời gian' in e.lower() for e in result['errors'])

    def test_invalid_date_format_raises(self):
        """Ngày sai định dạng (yyyy-mm-dd thay vì dd/mm/yyyy) → ValueError."""
        from core.validator import parse_date
        with pytest.raises(ValueError):
            parse_date('2026-01-15')

    def test_multiple_errors_accumulated(self):
        """Nhiều lỗi cùng lúc: đề xuất > duyệt + HĐ > nghiệm thu + tiền không khớp."""
        from core.validator import validate_payment_record
        data = {
            'proposal_date': '20/01/2026',
            'approval_date': '10/01/2026',
            'contract_date': '25/01/2026',
            'acceptance_date': '15/01/2026',
            'vat_date': '26/01/2026',
            'request_date': '27/01/2026',
            'amount': 30000000,
            'vat_amount': 20000000,
        }
        result = validate_payment_record(data)
        assert result['is_valid'] is False
        assert len(result['errors']) >= 3  # Ít nhất 3 lỗi


# ════════════════════════════════════════════════════
# NHÓM 6: EXTRACTOR - Parse lỗi response từ AI
# ════════════════════════════════════════════════════

class TestExtractor:
    """Kiểm tra xử lý lỗi trong module extractor."""

    def test_missing_api_key_raises(self):
        """api_key trống → ValueError."""
        from core.extractor import extract_information_from_files
        with pytest.raises(ValueError, match="API Key"):
            extract_information_from_files([], '', 'gemini')

    def test_none_api_key_raises(self):
        """api_key = None → ValueError."""
        from core.extractor import extract_information_from_files
        with pytest.raises(ValueError, match="API Key"):
            extract_information_from_files([], None, 'gemini')

    @staticmethod
    def _make_mock_client(generate_text=None, generate_side_effect=None):
        """Tạo mock genai.Client: files.upload/delete + models.generate_content."""
        mock_client = MagicMock()
        uploaded = MagicMock()
        uploaded.name = 'files/abc123'
        mock_client.files.upload.return_value = uploaded
        if generate_side_effect is not None:
            mock_client.models.generate_content.side_effect = generate_side_effect
        else:
            resp = MagicMock()
            resp.text = generate_text
            mock_client.models.generate_content.return_value = resp
        return mock_client

    @patch('core.extractor.genai.Client')
    def test_gemini_api_error(self, mock_client_cls):
        """generate_content ném lỗi → bọc thành 'Lỗi gọi Gemini API'."""
        from core.extractor import extract_information_from_files
        mock_client_cls.return_value = self._make_mock_client(
            generate_side_effect=Exception("500 Internal Server Error"))

        files = [{'name': 'test.jpg', 'mimeType': 'image/jpeg', 'content': b'\xff\xd8'}]
        with pytest.raises(Exception, match="Lỗi gọi Gemini API"):
            extract_information_from_files(files, 'fake_key', 'gemini-2.5-pro')

    @patch('core.extractor.genai.Client')
    def test_gemini_returns_invalid_json(self, mock_client_cls):
        """Gemini trả text không phải JSON → raise Exception 'Lỗi phân tích'."""
        from core.extractor import extract_information_from_files
        mock_client_cls.return_value = self._make_mock_client(
            generate_text='Tôi không hiểu yêu cầu')

        files = [{'name': 'test.jpg', 'mimeType': 'image/jpeg', 'content': b'\xff\xd8'}]
        with pytest.raises(Exception, match="Lỗi phân tích"):
            extract_information_from_files(files, 'fake_key', 'gemini-2.5-pro')

    @patch('core.extractor.genai.Client')
    def test_gemini_success_returns_dict(self, mock_client_cls):
        """Gemini trả JSON hợp lệ → parse thành công → trả về dict."""
        from core.extractor import extract_information_from_files
        expected = {
            'beneficiary': 'CONG TY ABC',
            'account': '123456789',
            'bank': 'Vietcombank',
            'amount': 10000000,
            'remarks': 'Thanh toan test',
        }
        mock_client = self._make_mock_client(generate_text=json.dumps(expected))
        mock_client_cls.return_value = mock_client

        files = [{'name': 'test.jpg', 'mimeType': 'image/jpeg', 'content': b'\xff\xd8'}]
        result = extract_information_from_files(files, 'valid_key', 'gemini-2.5-pro')
        assert result['beneficiary'] == 'CONG TY ABC'
        assert result['amount'] == 10000000

    @patch('core.extractor.genai.Client')
    def test_gemini_cleans_up_uploaded_files(self, mock_client_cls):
        """File đã upload phải được xóa sau khi trích xuất (dù thành công)."""
        from core.extractor import extract_information_from_files
        mock_client = self._make_mock_client(generate_text='{"beneficiary": "X"}')
        mock_client_cls.return_value = mock_client

        files = [{'name': 'test.jpg', 'mimeType': 'image/jpeg', 'content': b'\xff\xd8'}]
        extract_information_from_files(files, 'valid_key', 'gemini-2.5-pro')
        mock_client.files.delete.assert_called_once_with(name='files/abc123')


# ════════════════════════════════════════════════════
# NHÓM 7: GOOGLE CONNECTOR - Parse URL
# ════════════════════════════════════════════════════

class TestGoogleConnector:
    """Kiểm tra parse_folder_id và parse_spreadsheet_id."""

    def test_parse_valid_folder_url(self):
        from core.google_connector import parse_folder_id
        url = 'https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz'
        assert parse_folder_id(url) == '1AbCdEfGhIjKlMnOpQrStUvWxYz'

    def test_parse_folder_url_with_query_params(self):
        from core.google_connector import parse_folder_id
        url = 'https://drive.google.com/drive/folders/1AbCdEf?usp=sharing'
        assert parse_folder_id(url) == '1AbCdEf'

    def test_parse_folder_url_invalid(self):
        from core.google_connector import parse_folder_id
        assert parse_folder_id('https://drive.google.com/file/d/abc') is None
        assert parse_folder_id('https://example.com/folders/abc') == 'abc'  # regex vẫn match
        assert parse_folder_id('hello world') is None

    def test_parse_valid_spreadsheet_url(self):
        from core.google_connector import parse_spreadsheet_id
        url = 'https://docs.google.com/spreadsheets/d/1xYz_AbcDef-123/edit#gid=0'
        assert parse_spreadsheet_id(url) == '1xYz_AbcDef-123'

    def test_parse_spreadsheet_url_invalid(self):
        from core.google_connector import parse_spreadsheet_id
        assert parse_spreadsheet_id('https://docs.google.com/document/d/abc') is None
        assert parse_spreadsheet_id('not a url') is None

    def test_parse_empty_string(self):
        from core.google_connector import parse_folder_id, parse_spreadsheet_id
        assert parse_folder_id('') is None
        assert parse_spreadsheet_id('') is None


# ════════════════════════════════════════════════════
# NHÓM 8: SETTINGS - Lưu/đọc cấu hình
# ════════════════════════════════════════════════════

class TestSettings:
    """Kiểm tra trang cấu hình API Key."""

    def test_settings_redirect_if_not_logged_in(self, client):
        """GET /settings → redirect nếu chưa đăng nhập."""
        res = client.get('/settings', follow_redirects=False)
        assert res.status_code == 302

    def test_save_api_key_in_session(self, logged_in_client):
        """POST /settings → lưu api_key vào session."""
        res = logged_in_client.post('/settings',
                                    data={'api_key': 'new_test_key_123', 'ocr_model': 'gemini-2.5-pro'},
                                    follow_redirects=False)
        assert res.status_code == 302  # redirect về settings?success=True

        with logged_in_client.session_transaction() as sess:
            assert sess['api_key'] == 'new_test_key_123'
            assert sess['ocr_model'] == 'gemini-2.5-pro'

    def test_switch_model_to_flash(self, logged_in_client):
        """POST /settings chuyển model sang gemini-2.5-flash."""
        logged_in_client.post('/settings',
                              data={'api_key': 'AIzaSy-key', 'ocr_model': 'gemini-2.5-flash'})
        with logged_in_client.session_transaction() as sess:
            assert sess['ocr_model'] == 'gemini-2.5-flash'


# ════════════════════════════════════════════════════
# NHÓM 9: GENERATE UNC - Xuất file Excel
# ════════════════════════════════════════════════════

VALID_UNC_RECORD = {
    'sheet': 'CONG_TY_ABC',
    'beneficiary': 'CÔNG TY TNHH ABC',
    'account': '123456789',
    'bank': 'BIDV - CN Thái Hà',
    'address': 'Hà Nội',
    'id_no': '',
    'amount': 12345678,
    'amount_words': '',
    'remarks': 'Thanh toán sửa chữa máy bơm',
    'request_date': '14/07/2026',
}


class TestGenerateUnc:
    """Kiểm tra endpoint tạo file Excel UNC."""

    def test_generate_unc_requires_login(self, client):
        """POST /api/generate-unc khi chưa đăng nhập → 401."""
        res = client.post('/api/generate-unc',
                          data=json.dumps({'data': VALID_UNC_RECORD}),
                          content_type='application/json')
        assert res.status_code == 401

    def test_generate_unc_missing_required_fields(self, logged_in_client):
        """Thiếu trường bắt buộc (beneficiary, bank...) → 400."""
        res = logged_in_client.post('/api/generate-unc',
                                    data=json.dumps({'data': {'sheet': 'X'}}),
                                    content_type='application/json')
        assert res.status_code == 400
        assert 'Thiếu thông tin' in res.get_json()['message']

    def test_generate_unc_invalid_amount(self, logged_in_client):
        """Số tiền không phải số → 400."""
        record = dict(VALID_UNC_RECORD, amount='không phải số')
        res = logged_in_client.post('/api/generate-unc',
                                    data=json.dumps({'data': record}),
                                    content_type='application/json')
        assert res.status_code == 400
        assert 'Số tiền' in res.get_json()['message']

    def test_generate_unc_success_returns_xlsx(self, logged_in_client):
        """Dữ liệu hợp lệ → trả về file .xlsx (zip bắt đầu bằng 'PK')."""
        res = logged_in_client.post('/api/generate-unc',
                                    data=json.dumps({'data': VALID_UNC_RECORD}),
                                    content_type='application/json')
        assert res.status_code == 200
        assert 'spreadsheetml' in res.headers['Content-Type']
        assert 'attachment' in res.headers['Content-Disposition']
        assert res.data[:2] == b'PK'  # chữ ký file ZIP/xlsx
