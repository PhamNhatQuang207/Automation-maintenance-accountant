"""
audit.py — Sổ ghi (ledger) các Ủy Nhiệm Chi đã tạo, dùng SQLite (thư viện chuẩn).

Mục đích cho bản triển khai 1 máy, 1 người dùng:
  - Lưu lại mỗi UNC đã xuất để có bằng chứng đã tạo cái gì, khi nào.
  - Cảnh báo thanh toán TRÙNG (cùng đơn vị thụ hưởng + cùng số tiền) gần đây.

Không cần hạ tầng ngoài: file .db nằm trên máy (mặc định backend/data/unc_ledger.db,
đè bằng biến môi trường UNC_DB_PATH).
"""
import os
import sqlite3
from datetime import datetime, timedelta

DEFAULT_DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'unc_ledger.db')


def _db_path():
    path = os.environ.get('UNC_DB_PATH', DEFAULT_DB)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return path


def _connect():
    conn = sqlite3.connect(_db_path())
    conn.execute(
        """CREATE TABLE IF NOT EXISTS unc_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   TEXT NOT NULL,
            sheet        TEXT,
            beneficiary  TEXT,
            account      TEXT,
            bank         TEXT,
            amount       INTEGER,
            remarks      TEXT,
            request_date TEXT
        )"""
    )
    return conn


def find_recent_duplicate(beneficiary, amount, within_days=30):
    """Trả về bản ghi UNC gần nhất cùng beneficiary + amount trong 'within_days' ngày, nếu có."""
    since = (datetime.now() - timedelta(days=within_days)).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT created_at, amount FROM unc_log "
            "WHERE beneficiary = ? AND amount = ? AND created_at >= ? "
            "ORDER BY id DESC LIMIT 1",
            (beneficiary, int(amount), since),
        ).fetchone()
    if row:
        return {'created_at': row[0], 'amount': row[1]}
    return None


def record_unc(record):
    """Ghi 1 dòng nhật ký cho UNC vừa xuất thành công."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO unc_log "
            "(created_at, sheet, beneficiary, account, bank, amount, remarks, request_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now().isoformat(),
                record.get('sheet'),
                record.get('beneficiary'),
                str(record.get('account') or ''),
                record.get('bank'),
                int(record.get('amount')),
                record.get('remarks'),
                record.get('request_date'),
            ),
        )
