#!/usr/bin/env python3
"""
generate_unc.py — Tạo UNC Park Hill 1 GIỮ NGUYÊN logo + textbox + định dạng.

Khác với openpyxl (làm mất ảnh/textbox khi clone sheet), engine này nhân bản
sheet ở mức XML/ZIP: mỗi nhà thầu = 1 sheet mới = bản sao sheet mẫu + drawing
mẫu (2 logo + 4 textbox chữ ký), CHỈ thay các ô dữ liệu người thụ hưởng.
Đồng thời dọn sạch externalLinks/definedNames rác để file nhẹ, không popup
"update links".

Dùng:
    python3 generate_unc.py --input payments.json --output OUT.xlsx
    python3 generate_unc.py --output OUT.xlsx        # chạy sample
"""
import argparse, json, os, re, zipfile
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "UNC_TEMPLATE.xlsx")

MASTER_SHEET = "xl/worksheets/sheet1.xml"          # sheet khuôn (có drawing)
MASTER_DRAWING = "xl/drawings/drawing1.xml"
MASTER_DRAWING_RELS = "xl/drawings/_rels/drawing1.xml.rels"
BLANK_SHEET = "xl/worksheets/sheet4.xml"           # sheet 00000000 (ẩn, không drawing)

# Ô dữ liệu người thụ hưởng (GIỮ NGUYÊN mọi ô khác)
CELLS = ["G6", "B11", "B12", "G12", "B13", "B14", "B15", "B16", "B19"]

# ── số → chữ tiếng Việt ─────────────────────────────────────────────────
_DV = ["không","một","hai","ba","bốn","năm","sáu","bảy","tám","chín"]
def _doc3(n, full):
    tram, n = divmod(n,100); chuc, dv = divmod(n,10); out=[]
    if full or tram>0: out.append(_DV[tram]+" trăm")
    if chuc==0:
        if dv>0 and (full or tram>0): out.append("lẻ")
        if dv>0: out.append(_DV[dv])
    elif chuc==1:
        out.append("mười")
        if dv==5: out.append("lăm")
        elif dv>0: out.append(_DV[dv])
    else:
        out.append(_DV[chuc]+" mươi")
        if dv==1: out.append("mốt")
        elif dv==5: out.append("lăm")
        elif dv>0: out.append(_DV[dv])
    return " ".join(out)
def so_thanh_chu(n):
    n=int(round(n))
    if n==0: return "Không đồng"
    dv=["","nghìn","triệu","tỷ"]; g=[]
    while n>0: n,r=divmod(n,1000); g.append(r)
    parts=[]
    for i in range(len(g)-1,-1,-1):
        if g[i]==0: continue
        parts.append(_doc3(g[i], i<len(g)-1)+((" "+dv[i]) if dv[i] else ""))
    s=" ".join(" ".join(parts).split())
    return s[0].upper()+s[1:]+" đồng"
def dinh_dang_so(n): return f"{int(round(n)):,}".replace(",", ".")+" VNĐ"

def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def set_cell(xml, ref, value):
    """Thay giá trị 1 ô bằng inline-string, GIỮ NGUYÊN style (thuộc tính s)."""
    m = re.search(r'<c r="'+ref+r'"([^>]*?)(/>|>.*?</c>)', xml, re.S)
    if not m:
        raise ValueError(f"Không thấy ô {ref} trong sheet mẫu")
    sm = re.search(r'\ss="(\d+)"', m.group(1))
    s = f' s="{sm.group(1)}"' if sm else ''
    if value in (None, "", "None"):
        new = f'<c r="{ref}"{s}/>'
    else:
        new = (f'<c r="{ref}"{s} t="inlineStr"><is>'
               f'<t xml:space="preserve">{esc(value)}</t></is></c>')
    return xml[:m.start()] + new + xml[m.end():]

def fill_sheet(master_xml, p, ngay):
    words = p.get("amount_words") or so_thanh_chu(p["amount"])
    vals = {
        "G6":  f"Ngày Date: {ngay}",
        "B11": p["beneficiary"],
        "B12": str(p["account"]),
        "G12": p["bank"],
        "B13": p.get("address") or None,
        "B14": p.get("id_no") or None,
        "B15": dinh_dang_so(p["amount"]),
        "B16": words,
        "B19": p["remarks"],
    }
    xml = master_xml
    for ref in CELLS:
        xml = set_cell(xml, ref, vals[ref])
    return xml

def create_unc_file(payments, output_path, ngay=None, template=TEMPLATE):
    ngay = ngay or date.today().strftime("%d/%m/%Y")
    zin = zipfile.ZipFile(template)
    parts = {n: zin.read(n) for n in zin.namelist()}
    zin.close()

    master_sheet = parts[MASTER_SHEET].decode("utf-8")
    master_draw  = parts[MASTER_DRAWING].decode("utf-8")
    master_draw_rels = parts[MASTER_DRAWING_RELS].decode("utf-8")
    blank_sheet  = parts[BLANK_SHEET].decode("utf-8")
    N = len(payments)
    blank_idx = N + 1

    out = {}
    for k in ["xl/styles.xml","xl/sharedStrings.xml","xl/theme/theme1.xml",
              "xl/media/image1.png","xl/media/image2.png",
              "docProps/core.xml","docProps/app.xml","_rels/.rels"]:
        if k in parts: out[k] = parts[k]

    for i, p in enumerate(payments, start=1):
        out[f"xl/worksheets/sheet{i}.xml"] = fill_sheet(master_sheet, p, ngay).encode("utf-8")
        out[f"xl/worksheets/_rels/sheet{i}.xml.rels"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing{i}.xml"/>'
            '</Relationships>').encode("utf-8")
        out[f"xl/drawings/drawing{i}.xml"] = master_draw.encode("utf-8")
        out[f"xl/drawings/_rels/drawing{i}.xml.rels"] = master_draw_rels.encode("utf-8")

    blank = re.sub(r'<drawing[^>]*/>', '', blank_sheet)
    out[f"xl/worksheets/sheet{blank_idx}.xml"] = blank.encode("utf-8")

    wb = parts["xl/workbook.xml"].decode("utf-8")
    wb = re.sub(r'<externalReferences>.*?</externalReferences>', '', wb, flags=re.S)
    wb = re.sub(r'<definedNames>.*?</definedNames>', '', wb, flags=re.S)
    sheets = "".join(
        f'<sheet name="{esc(p["sheet"][:31])}" sheetId="{i}" r:id="rId{i}"/>'
        for i, p in enumerate(payments, start=1))
    sheets += f'<sheet name="00000000" sheetId="{blank_idx}" state="hidden" r:id="rId{blank_idx}"/>'
    wb = re.sub(r'<sheets>.*?</sheets>', f'<sheets>{sheets}</sheets>', wb, flags=re.S)
    out["xl/workbook.xml"] = wb.encode("utf-8")

    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for i in range(1, blank_idx+1):
        rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
    rels.append(f'<Relationship Id="rId{blank_idx+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    rels.append(f'<Relationship Id="rId{blank_idx+2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>')
    rels.append(f'<Relationship Id="rId{blank_idx+3}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>')
    rels.append('</Relationships>')
    out["xl/_rels/workbook.xml.rels"] = "".join(rels).encode("utf-8")

    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="png" ContentType="image/png"/>',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
          '<Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
          '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>',
          '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
          '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>']
    for i in range(1, blank_idx+1):
        ct.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    for i in range(1, N+1):
        ct.append(f'<Override PartName="/xl/drawings/drawing{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>')
    ct.append('</Types>')
    out["[Content_Types].xml"] = "".join(ct).encode("utf-8")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in out.items():
            z.writestr(name, data)
    print(f"✅ Xuất: {output_path}  [{N} UNC]  Sheets: "
          + ", ".join(p['sheet'][:31] for p in payments) + ", 00000000(ẩn)")


SAMPLE = {"date": date.today().strftime("%d/%m/%Y"), "payments": [{
    "sheet":"MAU_THU","beneficiary":"CÔNG TY ABC","account":"123456789",
    "bank":"BIDV - CN Thái Hà","address":"","id_no":"","amount":12345678,
    "amount_words":"","remarks":"Thanh toán thử nghiệm"}]}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input","-i"); ap.add_argument("--output","-o",default="UNC_PARK1.xlsx")
    ap.add_argument("--template","-t",default=TEMPLATE)
    a = ap.parse_args()
    data = json.load(open(a.input,encoding="utf-8")) if a.input else SAMPLE
    create_unc_file(data["payments"], a.output, ngay=data.get("date"), template=a.template)
