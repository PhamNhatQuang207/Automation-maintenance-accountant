from datetime import datetime

def parse_date(date_str):
    if not date_str:
        return None
    return datetime.strptime(date_str, "%d/%m/%Y")

def validate_payment_record(data: dict) -> dict:
    """
    Kiểm tra các luật logic theo Mục 8 của PROCESS.md
    """
    results = {
        "is_valid": True,
        "warnings": [],
        "errors": []
    }
    
    print("[Validator] Đang chạy kiểm tra logic...")
    
    # 8.2 Kiểm tra chuỗi thời gian
    # Ngày đề xuất <= Ngày duyệt <= Ngày ký HĐ < Ngày nghiệm thu < Ngày HĐ VAT <= Ngày đề nghị TT
    dates = {
        "Đề xuất": parse_date(data.get("proposal_date")),
        "Duyệt": parse_date(data.get("approval_date")),
        "Hợp đồng": parse_date(data.get("contract_date")),
        "Nghiệm thu": parse_date(data.get("acceptance_date")),
        "VAT": parse_date(data.get("vat_date")),
        "Đề nghị TT": parse_date(data.get("request_date")),
    }
    
    # Validate VAT
    if not dates["VAT"]:
        results["warnings"].append("Cảnh báo: Hồ sơ chưa có Hóa đơn VAT.")
        results["is_valid"] = False
        
    # Validate chuỗi thời gian nếu có đủ ngày
    if dates["Đề xuất"] and dates["Duyệt"] and dates["Đề xuất"] > dates["Duyệt"]:
        results["errors"].append("Lỗi thời gian: Ngày đề xuất sau Ngày duyệt.")
        results["is_valid"] = False
        
    if dates["Duyệt"] and dates["Hợp đồng"] and dates["Duyệt"] > dates["Hợp đồng"]:
        # Có thể du di nếu là Báo giá có sẵn
        results["warnings"].append("Cảnh báo thời gian: Ngày duyệt sau Ngày báo giá/Hợp đồng (có thể là Báo giá lấy trước).")
        
    if dates["Hợp đồng"] and dates["Nghiệm thu"] and dates["Hợp đồng"] > dates["Nghiệm thu"]:
        results["errors"].append("Lỗi thời gian: Hợp đồng sau Nghiệm thu.")
        results["is_valid"] = False
        
    # 8.3 Số tiền
    if data.get("vat_amount") is not None and data.get("amount") != data.get("vat_amount"):
        results["errors"].append("Lỗi tuyệt đối: Số tiền đề nghị TT không khớp số tiền VAT.")
        results["is_valid"] = False
        
    if not results["is_valid"]:
        print("[Validator] Có cảnh báo/lỗi trong hồ sơ!")
    else:
        print("[Validator] Hồ sơ hợp lệ!")
        
    return results

if __name__ == "__main__":
    from extractor import extract_information
    data = extract_information("test")
    res = validate_payment_record(data)
    print(res)
