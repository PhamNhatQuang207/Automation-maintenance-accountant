import io
import json
from typing import Optional

from pydantic import BaseModel
from google import genai
from google.genai import types

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
  "vat_amount": 12345678, // Tổng cộng tiền thanh toán sau thuế (tiền hàng + tiền thuế VAT/GTGT) ghi trên hóa đơn VAT bằng số (không lấy riêng tiền thuế, nếu không có hóa đơn để null)
  "vat_invoice_no": "Số hóa đơn VAT (nếu không có để null)",
  "request_date": "Ngày trên giấy Đề nghị thanh toán (định dạng dd/mm/yyyy, nếu không có ghi ngày hiện tại)"
}
"""

# Model mặc định là Flash (có gói miễn phí); có thể chọn Pro khi cần độ chính xác cao hơn.
DEFAULT_MODEL = "gemini-2.5-flash"


class PaymentRecord(BaseModel):
    """Cấu trúc dữ liệu 1 bộ hồ sơ thanh toán, dùng để ép Gemini trả về JSON đúng schema."""
    sheet: str
    beneficiary: str
    account: str
    bank: str
    address: str = ""
    id_no: str = ""
    amount: Optional[int] = None
    amount_words: str = ""
    remarks: str = ""
    proposal_date: Optional[str] = None
    approval_date: Optional[str] = None
    contract_date: Optional[str] = None
    acceptance_date: Optional[str] = None
    vat_date: Optional[str] = None
    vat_amount: Optional[int] = None
    vat_invoice_no: Optional[str] = None
    request_date: Optional[str] = None


def extract_information_from_files(files_list: list, api_key: str, model: str = DEFAULT_MODEL) -> dict:
    """
    Trích xuất thông tin hồ sơ bằng cách gửi toàn bộ danh sách files sang Gemini (multimodal).
    files_list: danh sách dict gồm {'name': ..., 'mimeType': ..., 'content': bytes}
    model: tên model Gemini (mặc định gemini-2.5-pro, có thể chọn gemini-2.5-flash).
    """
    if not api_key:
        raise ValueError("Chưa cấu hình API Key trong mục Cài đặt.")

    return _extract_gemini(files_list, api_key, model or DEFAULT_MODEL)


def _extract_gemini(files_list, api_key, model):
    # Dùng SDK chính thức + File API: upload từng file thay vì nhúng base64 trực tiếp,
    # tránh giới hạn ~20MB/request khi bộ hồ sơ có nhiều trang (100+ trang).
    client = genai.Client(api_key=api_key)

    uploaded = []
    try:
        for file in files_list:
            buf = io.BytesIO(file['content'])
            uploaded.append(client.files.upload(
                file=buf,
                config=types.UploadFileConfig(mime_type=file['mimeType'])
            ))

        response = client.models.generate_content(
            model=model,
            contents=[PROMPT, *uploaded],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PaymentRecord,
            ),
        )

        try:
            return json.loads(response.text)
        except (TypeError, ValueError) as e:
            raise Exception(f"Lỗi phân tích phản hồi JSON từ Gemini: {str(e)}. Phản hồi gốc: {response.text}")
    except Exception as e:
        # Giữ nguyên các Exception đã có message tiếng Việt, bọc phần còn lại.
        if str(e).startswith("Lỗi"):
            raise
        raise Exception(f"Lỗi gọi Gemini API: {str(e)}")
    finally:
        # Dọn dẹp file đã upload để không tồn đọng (File API giữ 48h).
        for f in uploaded:
            try:
                client.files.delete(name=f.name)
            except Exception:
                pass
