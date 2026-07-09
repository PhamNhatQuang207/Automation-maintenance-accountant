import json
from datetime import datetime

def extract_information(image_path: str) -> dict:
    """
    Mock function simulating LLM/OCR extraction from an image or PDF.
    In a real scenario, this would call Google Cloud Vision or Gemini API.
    """
    print(f"[Extractor] Đang phân tích chứng từ: {image_path}...")
    
    # Dữ liệu giả lập trích xuất từ 1 đề nghị thanh toán (Case study 10.1)
    mock_data = {
        "sheet": "DTC",
        "beneficiary": "CÔNG TY CP THƯƠNG MẠI KỸ THUẬT DTC",
        "account": "0000123456789",
        "bank": "Vietcombank - CN Sở Giao Dịch",
        "address": "Số 1, Phố Y, Hà Nội",
        "id_no": "",
        "amount": 18934560,
        "amount_words": "Mười tám triệu chín trăm ba mươi tư nghìn năm trăm sáu mươi đồng",
        "remarks": "Thanh toán thay cáp hồi dầu điều hòa theo Báo giá 130526/BG/DTC-P01 ngày 13/05/2026",
        # Các thông tin phụ dùng cho validation
        "request_date": "13/06/2026",
        "vat_invoice_no": None,
        "vat_date": None,
        "vat_amount": None,
        "acceptance_date": "19/05/2026",
        "contract_date": "13/05/2026", # Báo giá
        "approval_date": "16/05/2026",
        "proposal_date": "16/05/2026",
    }
    
    print("[Extractor] Trích xuất thành công!")
    return mock_data

if __name__ == "__main__":
    data = extract_information("sample_de_nghi_tt.jpg")
    print(json.dumps(data, indent=2, ensure_ascii=False))
