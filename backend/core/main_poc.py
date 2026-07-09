import json
import sys
import os
from extractor import extract_information
from validator import validate_payment_record
from generate_unc import create_unc_file

def main():
    print("=== HỆ THỐNG XỬ LÝ HỒ SƠ THANH TOÁN (POC) ===")
    image_path = "sample_de_nghi_tt.jpg"
    
    # Bước 1: Đọc & Trích xuất
    data = extract_information(image_path)
    
    # Bước 2: Kiểm tra logic
    validation_results = validate_payment_record(data)
    
    # In kết quả cho người dùng duyệt
    print("\n--- TÓM TẮT THÔNG TIN ---")
    print(f"Nhà thầu: {data['beneficiary']}")
    print(f"Số TK: {data['account']} - Ngân hàng: {data['bank']}")
    print(f"Số tiền: {data['amount']} VNĐ")
    print(f"Nội dung: {data['remarks']}")
    
    if not validation_results['is_valid']:
        print("\n[CẢNH BÁO LUẬT]")
        for w in validation_results['warnings']:
            print(f"- {w}")
        for e in validation_results['errors']:
            print(f"- {e}")
            
    # Bước 3: Xác nhận & Tạo UNC
    # Trong môi trường thực tế, script sẽ chờ lệnh từ user.
    # Ở đây POC sẽ tự động chạy luôn để demo việc tạo file.
    print("\n[Xác nhận] Tạo file UNC...")
    
    output_filename = "UNC_PARK1_DTC_PoC.xlsx"
    template_path = os.path.join(os.path.dirname(__file__), "..", "assets", "UNC_TEMPLATE.xlsx")
    
    # generate_unc.py yêu cầu list của payments
    payments = [data]
    
    create_unc_file(payments, output_path=output_filename, ngay=data['request_date'], template=template_path)
    
    print(f"=== ĐÃ HOÀN THÀNH. File lưu tại: {output_filename} ===")

if __name__ == "__main__":
    main()
