import re
import io
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import os
import json

def get_google_services(tokens):
    """Khởi tạo Google Services client bằng Tokens (chứa access_token và refresh_token nếu có)"""
    client_secret_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'client_secret.json')
    
    try:
        with open(client_secret_path, 'r') as f:
            client_config = json.load(f)['web']
            
        creds = Credentials(
            token=tokens.get('access_token'),
            refresh_token=tokens.get('refresh_token'),
            token_uri=client_config.get('token_uri'),
            client_id=client_config.get('client_id'),
            client_secret=client_config.get('client_secret')
        )
    except Exception as e:
        print(f"[Warning] Không load được credentials để tự động refresh: {e}")
        creds = Credentials(token=tokens.get('access_token'))
        
    drive_service = build('drive', 'v3', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    return drive_service, sheets_service

def parse_folder_id(url):
    """Trích xuất ID thư mục từ link Google Drive"""
    match = re.search(r'folders/([a-zA-Z0-9-_]+)', url)
    return match.group(1) if match else None

def parse_spreadsheet_id(url):
    """Trích xuất ID bảng tính từ link Google Sheets"""
    match = re.search(r'spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    return match.group(1) if match else None

def list_files_in_folder(drive_service, folder_id):
    """Liệt kê danh sách file (ảnh, PDF) trong thư mục"""
    query = f"'{folder_id}' in parents and trashed = false"
    results = drive_service.files().list(
        q=query,
        fields="files(id, name, mimeType)"
    ).execute()
    return results.get('files', [])

def download_file_to_bytes(drive_service, file_id):
    """Tải nội dung file từ Google Drive về bộ nhớ RAM"""
    request = drive_service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    file_stream.seek(0)
    return file_stream.read()

def read_sheet_data(sheets_service, spreadsheet_id, range_name):
    """Đọc dữ liệu từ Google Sheets"""
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()
    return result.get('values', [])

def append_sheet_row(sheets_service, spreadsheet_id, range_name, row_values):
    """Ghi thêm một dòng mới vào Google Sheets"""
    body = {
        'values': [row_values]
    }
    result = sheets_service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()
    return result
