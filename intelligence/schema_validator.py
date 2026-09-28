"""
Facebook Lead Intelligence V1 - Phase 5: Schema Validator & Zero-Hallucination Guardrails (Python)
"""

import re
import unicodedata
from typing import Dict, Any, Optional, Tuple, List

ALLOWED_INTENTS = {
  'IGNORE',
  'INFORMATION',
  'DISCUSSION',
  'RECOMMENDATION',
  'RESEARCH',
  'COMPARISON',
  'LOOKING_TO_BUY',
  'REQUEST_QUOTE',
  'LOOKING_FOR_SERVICE',
  'URGENT_NEED',
  'HIRING',
  'PARTNERSHIP',
  'EXISTING_CUSTOMER'
}

# Vietnamese Mobile phone regex (supports dots, spaces, hyphens)
PHONE_PATTERN = re.compile(r'(?:(?:\+84|84|0)[\s.-]?[35789])(?:[\s.-]?[0-9]){8}\b')

# Email regex
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Company indicators
COMPANY_INDICATORS = re.compile(r'\b(công ty|cty|tnhh|cổ phần|cp|doanh nghiệp|tập đoàn|nhà thầu|xí nghiệp|đơn vị thi công|tổng thầu)\b', re.IGNORECASE)

# Name indicators
NAME_PATTERN = re.compile(r'(?:mình là|em là|tôi là|tên em là|tên mình là|liên hệ(?:\s+mr\.?|\s+ms\.?|\s+anh|\s+chị)?|mr\.?|ms\.?|anh|chị|bác)\s+([A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+){0,3})', re.IGNORECASE)

def clean_string_field(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ('null', 'none', 'n/a', 'không', 'không có'):
        return None
    return s

def validate_and_sanitize_lead(ai_output: Dict[str, Any], source_text: str) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors = []
    if not ai_output or not isinstance(ai_output, dict):
        return False, ["AI output must be a dictionary"], {}

    text = unicodedata.normalize('NFC', str(source_text or ""))

    # 1. Booleans
    construction_relevant = bool(ai_output.get('construction_relevant'))
    commercial_intent = bool(ai_output.get('commercial_intent'))

    # 2. Intent
    intent = str(ai_output.get('intent') or '').upper().strip()
    if intent not in ALLOWED_INTENTS:
        if not construction_relevant or not commercial_intent:
            intent = 'IGNORE'
        else:
            errors.append(f"Invalid intent: {ai_output.get('intent')}")
            intent = 'INFORMATION'

    # 3. Clean string fields
    category = clean_string_field(ai_output.get('category'))
    product = clean_string_field(ai_output.get('product'))
    quantity = clean_string_field(ai_output.get('quantity'))
    requirement = clean_string_field(ai_output.get('requirement'))
    location = clean_string_field(ai_output.get('location'))
    budget = clean_string_field(ai_output.get('budget'))
    timeline = clean_string_field(ai_output.get('timeline'))

    # 4. Zero-Hallucination Guardrails on Phone
    phone = None
    phones_found = PHONE_PATTERN.findall(text)
    if phones_found:
        raw_p = phones_found[0]
        cleaned = re.sub(r'[\s.-]', '', raw_p)
        phone = re.sub(r'^(?:\+84|84)', '0', cleaned)

    # 5. Zero-Hallucination Guardrails on Email
    email = None
    emails_found = EMAIL_PATTERN.findall(text)
    if emails_found:
        email = emails_found[0].lower()

    # 6. Zero-Hallucination Guardrails on Company
    company = clean_string_field(ai_output.get('company'))
    if company:
        company_lower = company.lower()
        if company_lower not in text.lower() and not COMPANY_INDICATORS.search(text):
            company = None
    if not company:
        m_comp = re.search(r'((?:Công ty|Cty|TNHH|Cổ phần|Tập đoàn|Doanh nghiệp|Nhà thầu)\s+[^,\n;]+)', text, re.IGNORECASE)
        if m_comp:
            company = m_comp.group(1).strip()[:100]

    # 7. Zero-Hallucination Guardrails on Customer Name
    customer_name = clean_string_field(ai_output.get('customer_name'))
    if customer_name:
        name_lower = customer_name.lower()
        if name_lower not in text.lower():
            customer_name = None
    if not customer_name:
        m_n = NAME_PATTERN.search(text)
        if m_n:
            candidate = m_n.group(1).strip()
            if candidate.lower() not in ('báo giá', 'inbox', 'sđt', 'zalo', 'qua mail', 'email', 'nhé', 'ạ'):
                customer_name = candidate

    # 8. Confidence
    try:
        confidence = float(ai_output.get('confidence'))
    except (TypeError, ValueError):
        confidence = 0.85 if commercial_intent else 0.2
    confidence = max(0.0, min(1.0, confidence))

    sanitized = {
        'construction_relevant': construction_relevant,
        'commercial_intent': commercial_intent,
        'intent': intent,
        'category': category,
        'product': product,
        'quantity': quantity,
        'requirement': requirement,
        'location': location,
        'budget': budget,
        'timeline': timeline,
        'customer_name': customer_name,
        'company': company,
        'phone': phone,
        'email': email,
        'confidence': round(confidence, 2)
    }

    return (len(errors) == 0, errors, sanitized)
