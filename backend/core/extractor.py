import base64
import json
import requests

PROMPT = """Bạn là chuyên gia kế toán giám sát tài chính của Ban Quản trị Park Hill 1 (Tòa P01).
Dưới đây là các tài liệu hình ảnh/PDF liên quan đến 1 bộ hồ sơ thanh toán bảo trì (có thể bao gồm: Tờ trình đề xuất, Phê duyệt BQT, Hợp đồng/Báo giá, Biên bản nghiệm thu, Đề nghị thanh toán, Hóa đơn VAT).

Nhiệm vụ của bạn là đọc kỹ tất cả các tài liệu đính kèm này và trích xuất thông tin để phục vụ làm Ủy Nhiệm Chi (UNC) và cập nhật File Master tổng hợp.

Yêu cầu trả về kết quả dưới dạng JSON duy nhất, khớp chính xác theo cấu trúc dưới đây. Không thêm bất kỳ văn bản giải thích nào ngoài khối JSON.

Cấu trúc JSON yêu cầu:
{
  "sheet": "Tên viết tắt ngắn gọn không dấu để làm tên sheet Excel, tối đa 30 ký tự, dùng gạch dưới thay dấu cách, viết hoa (ví dụ: DTC, CUONG_THINH_VUONG, MAI_ANH)",
  "beneficiary": "Tên đầy đủ của đơn vị/cá nhân thụ hưởng nhận tiền (IN HOA)",
  "account": "Số tài khoản ngân hàng nhận tiền (chỉ lấy số/chữ số, giữ nguyên định dạng nếu có dấu chấm như 2680.123)",
  "bank": "Tên ngân hàng thụ hưởng (viết gọn tên ngân hàng + chi nhánh/phòng giao dịch nếu có, ví dụ: MB Bank - CN Thanh Xuân)",
  "address": "Địa chỉ đơn vị thụ hưởng (nếu có trên hồ sơ, không có thì để trống \"\")",
  "id_no": "Số CCCD/CMND/Hộ chiếu (chỉ điền nếu người thụ hưởng là cá nhân, nếu là công ty thì để trống \"\")",
  "amount": 12345678, // Số tiền đề nghị thanh toán bằng số (số nguyên VND, đã bao gồm thuế VAT nếu có)
  "amount_words": "Số tiền đề nghị thanh toán viết bằng chữ (lấy từ Đề nghị thanh toán; nếu trên đó để trống hãy tự dịch số tiền amount ở trên thành chữ tiếng Việt chuẩn, viết hoa chữ cái đầu và kết thúc bằng chữ 'đồng')",
  "remarks": "Nội dung thanh toán điền vào UNC (ví dụ: Thanh toán 100% đơn hàng sửa chữa máy bơm theo báo giá ngày 17/04/2026 hoặc Thanh toán đợt 1 bảo trì điều hòa theo Hợp đồng số 1509/2025/HĐBT ngày 15/09/2025)",
  "proposal_date": "Ngày đề xuất trên Tờ trình (định dạng dd/mm/yyyy, nếu không thấy để null)",
  "approval_date": "Ngày BQT phê duyệt duyệt chọn nhà thầu (định dạng dd/mm/yyyy, nếu không thấy để null)",
  "contract_date": "Ngày ký hợp đồng hoặc ngày trên Báo giá căn cứ (định dạng dd/mm/yyyy, nếu không thấy để null)",
  "acceptance_date": "Ngày ký nghiệm thu hoàn thành công việc (định dạng dd/mm/yyyy, nếu không thấy để null)",
  "vat_date": "Ngày xuất hóa đơn VAT nếu có (định dạng dd/mm/yyyy, nếu không thấy để null)",
  "vat_amount": 12345678, // Số tiền ghi trên hóa đơn VAT bằng số (nếu không có hóa đơn để null)
  "vat_invoice_no": "Số hóa đơn VAT (nếu không có để null)",
  "request_date": "Ngày trên giấy Đề nghị thanh toán (định dạng dd/mm/yyyy, nếu không có ghi ngày hiện tại)"
}
"""

def extract_information_from_files(files_list: list, api_key: str, provider: str = "gemini") -> dict:
    """
    Trích xuất thông tin hồ sơ bằng cách gửi toàn bộ danh sách files sang Gemini hoặc OpenAI.
    files_list: danh sách dict gồm {'name': ..., 'mimeType': ..., 'content': bytes}
    """
    if not api_key:
        raise ValueError("Chưa cấu hình API Key trong mục Cài đặt.")

    if provider == "openai":
        return _extract_openai(files_list, api_key)
    else:
        return _extract_gemini(files_list, api_key)

def _extract_gemini(files_list, api_key):
    # Gemini 1.5 Flash hỗ trợ Multimodal (nhiều ảnh/PDF cùng lúc)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    parts = [{"text": PROMPT}]
    
    for file in files_list:
        encoded_content = base64.b64encode(file['content']).decode('utf-8')
        parts.append({
            "inlineData": {
                "mimeType": file['mimeType'],
                "data": encoded_content
            }
        })
        
    payload = {
        "contents": [{
            "parts": parts
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    headers = {'Content-Type': 'application/json'}
    res = requests.post(url, headers=headers, json=payload)
    
    if res.status_code != 200:
        raise Exception(f"Lỗi gọi Gemini API (Status {res.status_code}): {res.text}")
        
    result_json = res.json()
    try:
        text_response = result_json['candidates'][0]['content']['parts'][0]['text']
        return json.loads(text_response)
    except (KeyError, IndexError, ValueError) as e:
        raise Exception(f"Lỗi phân tích phản hồi JSON từ Gemini: {str(e)}. Phản hồi gốc: {res.text}")

def _extract_openai(files_list, api_key):
    url = "https://api.openai.com/v1/chat/completions"
    
    messages_content = [{"type": "text", "text": PROMPT}]
    
    for file in files_list:
        # OpenAI chỉ nhận ảnh qua URL base64 trực tiếp (không hỗ trợ PDF trực tiếp qua API chat)
        if 'image' not in file['mimeType']:
            continue
        encoded_content = base64.b64encode(file['content']).decode('utf-8')
        messages_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{file['mimeType']};base64,{encoded_content}"
            }
        })
        
    payload = {
        "model": "gpt-4o",
        "messages": [{
            "role": "user",
            "content": messages_content
        }],
        "response_format": {"type": "json_object"}
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code != 200:
        raise Exception(f"Lỗi gọi OpenAI API (Status {res.status_code}): {res.text}")
        
    result_json = res.json()
    try:
        text_response = result_json['choices'][0]['message']['content']
        return json.loads(text_response)
    except (KeyError, IndexError, ValueError) as e:
        raise Exception(f"Lỗi phân tích phản hồi JSON từ OpenAI: {str(e)}")
