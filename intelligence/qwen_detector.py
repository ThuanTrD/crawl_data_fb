"""
Facebook Lead Intelligence V1 - Phase 5: Qwen AI & Deterministic Hybrid Lead Detector
"""

import re
import json
import urllib.request
import ssl
import time
from typing import Dict, Any, Optional
from schema_validator import validate_and_sanitize_lead

QWEN_ENDPOINT = "https://ai-api.cic.com.vn:9443/v1/chat/completions"
QWEN_TOKEN = "sk-cic-c708615648777c1a926b275c250c3684"
QWEN_MODEL = "qwen3-vl-30b"

PROMPT_SYSTEM = """Bạn là trợ lý AI chuyên gia phân tích dữ liệu mạng xã hội ngành Xây dựng & Kỹ thuật công trình (B2B Lead Intelligence).
Nhiệm vụ: Phân loại ý định thương mại và trích xuất thông tin khách hàng tiềm năng.

QUY TẮC BẮT BUỘC:
1. KHÔNG được suy đoán hoặc bịa số điện thoại (phone). Nếu không thấy rõ trong văn bản -> null.
2. KHÔNG được bịa email. Nếu không thấy rõ -> null.
3. KHÔNG được bịa công ty hoặc suy đoán bừa tên người. Nếu thiếu -> null.
4. Trường thiếu BẮT BUỘC để giá trị null.
5. Chỉ trả về duy nhất 1 JSON object theo định dạng chính xác sau, không thêm lời dẫn:
{
  "construction_relevant": true/false,
  "commercial_intent": true/false,
  "intent": "IGNORE|INFORMATION|DISCUSSION|RECOMMENDATION|RESEARCH|COMPARISON|LOOKING_TO_BUY|REQUEST_QUOTE|LOOKING_FOR_SERVICE|URGENT_NEED|HIRING|PARTNERSHIP|EXISTING_CUSTOMER",
  "category": "string hoặc null",
  "product": "string hoặc null",
  "quantity": "string hoặc null",
  "requirement": "string hoặc null",
  "location": "string hoặc null",
  "budget": "string hoặc null",
  "timeline": "string hoặc null",
  "customer_name": "string hoặc null",
  "company": "string hoặc null",
  "phone": "string hoặc null",
  "email": "string hoặc null",
  "confidence": 0.0 đến 1.0
}
"""

_CB_FAILURES = 0
_CB_THRESHOLD = 2
_CB_COOLDOWN = 120
_CB_LAST_FAIL_TIME = 0.0

def is_circuit_open() -> bool:
    global _CB_FAILURES, _CB_LAST_FAIL_TIME
    if _CB_FAILURES >= _CB_THRESHOLD:
        if (time.time() - _CB_LAST_FAIL_TIME) < _CB_COOLDOWN:
            return True
        _CB_FAILURES = 0
    return False

def record_circuit_failure():
    global _CB_FAILURES, _CB_LAST_FAIL_TIME
    _CB_FAILURES += 1
    _CB_LAST_FAIL_TIME = time.time()

def record_circuit_success():
    global _CB_FAILURES
    _CB_FAILURES = 0

def deterministic_rules_fallback(text: str, context: Optional[str] = None) -> Dict[str, Any]:
    full_text = f"{context or ''}\n{text}".strip()
    norm = full_text.lower()
    text_only_norm = text.lower()

    # 1. Relevance check
    construction_keywords = [
        'bê tông', 'robot xoa nền', 'máy xoa', 'công trình', 'xây dựng',
        'thép', 'xi măng', 'gạch', 'cát', 'đá', 'sắt', 'tôn', 'nhà xưởng', 'nhà phố', 'biệt thự', 'dự án',
        'autocad', 'revit', 'bim', 'tekla', 'civil 3d', 'sketchup', 'etabs', 'sap2000', 'plaxis', 'enjicad',
        'bóc tách', 'dự toán', 'kết cấu', 'địa kỹ thuật', 'mặt sàn', 'nhà thầu', 'kiến trúc sư'
    ]
    is_construction = any(kw in norm for kw in construction_keywords)

    # 2. Commercial intent and specific intent classification
    intent = 'INFORMATION'
    commercial = False
    confidence = 0.50

    # Check applicant response first
    if any(k in text_only_norm for k in ['gửi cv', 'em đã gửi cv', 'gửi cv qua mail', 'đã nộp cv', 'đã gửi hồ sơ']):
        intent = 'INFORMATION'
        commercial = False
        confidence = 0.85
    elif any(k in norm for k in ['tuyển dụng', 'tuyển kỹ sư', 'cần tuyển', 'tuyển thợ', 'tìm thợ', 'cần thợ']):
        intent = 'HIRING'
        commercial = True
        confidence = 0.85
    elif any(k in norm for k in ['báo giá', 'xin giá', 'giá bao nhiêu', 'báo em giá', 'inbox giá', 'ib giá', 'cho xin giá']):
        intent = 'REQUEST_QUOTE'
        commercial = True
        confidence = 0.95
    elif any(k in norm for k in ['cần mua', 'tìm mua', 'đang tìm mua', 'ai bán', 'mua ở đâu', 'cần cung cấp', 'cần nhượng lại']):
        intent = 'LOOKING_TO_BUY'
        commercial = True
        confidence = 0.90
    elif any(k in norm for k in ['cần thi công', 'cần thiết kế', 'tìm nhà thầu', 'tìm thầu', 'cần kỹ sư', 'cần kiến trúc sư', 'tìm kiến trúc sư', 'cần bóc tách', 'cần dự toán', 'đơn vị thi công']):
        intent = 'LOOKING_FOR_SERVICE'
        commercial = True
        confidence = 0.90
    elif any(k in norm for k in ['gấp', 'khẩn cấp', 'cần ngay', 'trong ngày']):
        intent = 'URGENT_NEED'
        commercial = True
        confidence = 0.92
    elif any(k in norm for k in ['hợp tác', 'đối tác', 'đại lý', 'phân phối']):
        intent = 'PARTNERSHIP'
        commercial = True
        confidence = 0.80
    elif any(k in norm for k in ['so sánh', 'nên dùng loại nào', 'hay hơn', 'hay mua', 'hay dùng', 'giữa ']) and any(k in norm for k in ['so sánh', 'hay', 'thì cái nào', 'tối ưu hơn']):
        intent = 'COMPARISON'
        commercial = False
        confidence = 0.70
    elif any(k in norm for k in ['tư vấn', 'cho hỏi', 'có ai biết', 'hỏi ý kiến']):
        intent = 'RESEARCH'
        commercial = False
        confidence = 0.65
    elif any(k in norm for k in ['lỗi license', 'không kích hoạt', 'hỗ trợ kỹ thuật']):
        intent = 'EXISTING_CUSTOMER'
        commercial = False
        confidence = 0.85
    elif any(k in norm for k in ['kinh nghiệm', 'thảo luận', 'chia sẻ']):
        intent = 'DISCUSSION'
        commercial = False
        confidence = 0.60
    elif not is_construction:
        intent = 'IGNORE'
        commercial = False
        confidence = 0.10

    # Category determination
    category = None
    if any(k in norm for k in ['autocad', 'revit', 'bim', 'tekla', 'civil 3d', 'sketchup', 'etabs', 'sap2000', 'plaxis', 'enjicad']):
        category = 'SOFTWARE'
    elif any(k in norm for k in ['robot', 'máy xoa', 'máy đầm', 'thiết bị']):
        category = 'EQUIPMENT'
    elif any(k in norm for k in ['thép', 'xi măng', 'gạch', 'cát', 'đá', 'bê tông', 'sắt', 'tôn']):
        category = 'MATERIALS'
    elif any(k in norm for k in ['nhà phố', 'biệt thự', 'nhà xưởng', 'công trình', 'dự án']):
        category = 'CONSTRUCTION_PROJECT'

    # Product extraction
    product = None
    product_patterns = [
        r'(robot xoa nền(?: đôi)?(?: bê tông)?)',
        r'(máy xoa nền(?: đôi)?)',
        r'(phần mềm (?:etabs|sap2000|plaxis|autocad|revit|enjicad|tekla|civil 3d))',
        r'(etabs|sap2000|plaxis|autocad|revit|bim|tekla|civil 3d|sketchup|enjicad)',
        r'(thép [a-z0-9]+|xi măng [a-z0-9]+|bê tông tươi|gạch [a-z0-9]+|tôn [a-z0-9]+|sắt [a-z0-9]+)'
    ]
    for p in product_patterns:
        m = re.search(p, norm, re.IGNORECASE)
        if m:
            product = m.group(1).title()
            break

    # Quantity extraction
    quantity = None
    m_qty = re.search(r'(\d+(?:[.,]\d+)?\s*(?:chiếc|bộ|cái|m2|m3|tấn|m|mét|tấm|cây|xe))', norm)
    if m_qty:
        quantity = m_qty.group(1)

    # Budget extraction
    budget = None
    m_budget = re.search(r'((?:khoảng|tầm|dưới|ngân sách)\s*\d+(?:[.,]\d+)?\s*(?:triệu|tỷ|tr|k|usd|\$))', norm)
    if m_budget:
        budget = m_budget.group(1)

    # Timeline extraction
    timeline = None
    m_time = re.search(r'((?:trong ngày|ngay|gấp|tháng \d+|tuần này|tiến độ \d+ ngày))', norm)
    if m_time:
        timeline = m_time.group(1)

    # Location extraction
    location = None
    for loc in ['hà nội', 'tp hcm', 'tp.hcm', 'hồ chí minh', 'đà nẵng', 'hải phòng', 'bình dương', 'đồng nai', 'quảng ninh', 'bắc ninh', 'long an', 'hưng yên', 'hải dương']:
        if loc in norm:
            location = loc.title()
            break

    # Customer Name extraction
    customer_name = None
    m_name = re.search(r'(?:mình là|em là|tôi là|tên em là|tên mình là|liên hệ(?:\s+mr\.?|\s+ms\.?|\s+anh|\s+chị)?|mr\.?|ms\.?|anh|chị|bác)\s+([A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+){0,3})', full_text)
    if m_name:
        candidate = m_name.group(1).strip()
        if candidate.lower() not in ('báo giá', 'inbox', 'sđt', 'zalo', 'qua mail', 'email', 'nhé', 'ạ'):
            customer_name = candidate

    # Company extraction
    company = None
    m_company = re.search(r'((?:Công ty|Cty|TNHH|Cổ phần|Tập đoàn|Doanh nghiệp|Nhà thầu)\s+[^,\n;]+)', full_text, re.IGNORECASE)
    if m_company:
        company = m_company.group(1).strip()[:100]

    return {
        'construction_relevant': is_construction,
        'commercial_intent': commercial,
        'intent': intent,
        'category': category,
        'product': product,
        'quantity': quantity,
        'requirement': full_text[:200] if commercial else None,
        'location': location,
        'budget': budget,
        'timeline': timeline,
        'customer_name': customer_name,
        'company': company,
        'phone': None,
        'email': None,
        'confidence': confidence
    }

def detect_lead(text: str, context: Optional[str] = None) -> Dict[str, Any]:
    raw_response = None
    ai_model = QWEN_MODEL
    parsed_json = None

    user_prompt = f"VĂN BẢN CẦN PHÂN TÍCH:\n{text}"
    if context:
        user_prompt = f"BỐI CẢNH BÀI VIẾT GỐC:\n{context}\n\nBÌNH LUẬN CẦN PHÂN TÍCH:\n{text}"

    # Check Circuit Breaker
    if is_circuit_open():
        ai_model = "qwen-hybrid-fallback"
        raw_response = {"circuit_breaker": "OPEN", "reason": "Upstream AI endpoint in cooldown"}
        parsed_json = deterministic_rules_fallback(text, context)
    else:
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                QWEN_ENDPOINT,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f"Bearer {QWEN_TOKEN}"
                },
                data=json.dumps({
                    'model': QWEN_MODEL,
                    'messages': [
                        {'role': 'system', 'content': PROMPT_SYSTEM},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    'temperature': 0.0,
                    'max_tokens': 500,
                    'response_format': {'type': 'json_object'}
                }).encode('utf-8')
            )

            with urllib.request.urlopen(req, context=ctx, timeout=3) as resp:
                raw_body = resp.read().decode('utf-8')
                raw_response = json.loads(raw_body)
                content_str = raw_response['choices'][0]['message']['content']
                cleaned_str = re.sub(r'<think>[\s\S]*?</think>', '', content_str).strip()
                parsed_json = json.loads(cleaned_str)
                record_circuit_success()
        except Exception as ex:
            record_circuit_failure()
            ai_model = "qwen-hybrid-fallback"
            raw_response = {"fallback_reason": str(ex)}
            parsed_json = deterministic_rules_fallback(text, context)

    if not parsed_json:
        parsed_json = deterministic_rules_fallback(text, context)
        ai_model = "qwen-hybrid-fallback"

    # Enforce Zero-Hallucination Guardrails
    is_valid, errors, sanitized = validate_and_sanitize_lead(parsed_json, f"{context or ''}\n{text}")

    return {
        'success': True,
        'ai_model': ai_model,
        'ai_raw_response': raw_response or {},
        'data': sanitized,
        'validation_errors': errors
    }
