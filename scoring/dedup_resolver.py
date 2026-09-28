"""
Facebook Lead Intelligence V1 - Phase 6: Entity Resolution Engine

Checks matching in strict order:
1. exact phone (Confidence: HIGH -> Merge allowed)
2. exact email (Confidence: HIGH -> Merge allowed)
3. company (Confidence: MEDIUM -> Do NOT auto-merge if contact differs -> POSSIBLE_DUPLICATE)
4. normalized customer name (Confidence: LOW -> Do NOT auto-merge -> POSSIBLE_DUPLICATE)
5. semantic similarity / author fallback

Possible Results:
- NEW
- POSSIBLE_DUPLICATE
- EXISTING_LEAD
- EXISTING_CUSTOMER
"""

import re
import hashlib
import unicodedata
from typing import Dict, Any, Optional, Tuple

def normalize_text(text: Optional[str]) -> str:
    """Strip accents and lower for soft matching"""
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text).lower()
    return " ".join(text.split())

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    phone_str = str(phone).strip()
    m = re.search(r'(?:(?:\+84|84|0)[\s.-]?[35789])(?:[\s.-]?[0-9]){8}\b', phone_str)
    if m:
        digits = "".join(filter(str.isdigit, m.group(0)))
    else:
        digits = "".join(filter(str.isdigit, phone_str))
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return digits if len(digits) >= 9 else None

def normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    e = str(email).strip()
    m = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', e)
    if m:
        return m.group(0).lower()
    e_lower = e.lower()
    return e_lower if "@" in e_lower and "." in e_lower and " " not in e_lower else None

def normalize_company(company: Optional[str]) -> Optional[str]:
    if not company:
        return None
    norm = normalize_text(company)
    # Remove common prefix noise
    norm = re.sub(r'\b(cong ty|cty|tnhh|cp|co phan|tap doan|tong cong ty)\b', '', norm).strip()
    return norm if len(norm) >= 3 else None

def compute_dedup_fingerprint(
    phone: Optional[str] = None,
    email: Optional[str] = None,
    author_id: Optional[str] = None,
    source_id: Optional[str] = None,
    post_id: Optional[str] = None
) -> str:
    """Computes a deterministic 32-char MD5 fingerprint"""
    p = normalize_phone(phone)
    e = normalize_email(email)
    if p:
        raw_key = f"PHONE:{p}"
    elif e:
        raw_key = f"EMAIL:{e}"
    elif author_id:
        raw_key = f"AUTHOR:{str(author_id).strip()}:{source_id or 'fb'}"
    elif post_id:
        raw_key = f"POST:{post_id}"
    else:
        raw_key = f"ANON:{source_id or 'unknown'}"
    return hashlib.md5(raw_key.encode('utf-8')).hexdigest()

def resolve_entity(
    cur,
    phone: Optional[str],
    email: Optional[str],
    company: Optional[str],
    customer_name: Optional[str],
    author_id: Optional[str],
    source_id: Optional[str],
    post_id: Optional[str],
    intent: str
) -> Tuple[str, Optional[Dict[str, Any]], str, float]:
    """
    Executes Entity Resolution in strict hierarchical order:
    Returns: (resolution, existing_lead, match_rule, confidence)
    """
    p = normalize_phone(phone)
    e = normalize_email(email)
    comp_norm = normalize_company(company)
    name_norm = normalize_text(customer_name)

    # 1. Check exact phone
    if p:
        cur.execute("SELECT * FROM public.leads WHERE primary_phone = %s ORDER BY created_at ASC LIMIT 1;", (p,))
        row = cur.fetchone()
        if row:
            res = 'EXISTING_CUSTOMER' if intent == 'EXISTING_CUSTOMER' else 'EXISTING_LEAD'
            return res, dict(row), 'EXACT_PHONE', 1.0

    # 2. Check exact email
    if e:
        cur.execute("SELECT * FROM public.leads WHERE LOWER(primary_email) = %s ORDER BY created_at ASC LIMIT 1;", (e,))
        row = cur.fetchone()
        if row:
            res = 'EXISTING_CUSTOMER' if intent == 'EXISTING_CUSTOMER' else 'EXISTING_LEAD'
            return res, dict(row), 'EXACT_EMAIL', 1.0

    # 3. Check company (Do not merge automatically when confidence is low)
    if comp_norm:
        cur.execute("""
            SELECT * FROM public.leads 
            WHERE company_name IS NOT NULL 
              AND length(company_name) > 3
            ORDER BY created_at ASC;
        """)
        for cand in cur.fetchall():
            if normalize_company(cand['company_name']) == comp_norm:
                # Same company but phone/email differs or missing -> Mark as POSSIBLE_DUPLICATE
                return 'POSSIBLE_DUPLICATE', dict(cand), 'COMPANY_MATCH', 0.65

    # 4. Check normalized customer name
    if name_norm and len(name_norm) > 4:
        cur.execute("""
            SELECT * FROM public.leads 
            WHERE full_name IS NOT NULL 
              AND length(full_name) > 4
            ORDER BY created_at ASC;
        """)
        for cand in cur.fetchall():
            if normalize_text(cand['full_name']) == name_norm:
                # Same name -> Low confidence -> POSSIBLE_DUPLICATE
                return 'POSSIBLE_DUPLICATE', dict(cand), 'NAME_MATCH', 0.40

    # 5. Semantic / Author fallback
    if author_id and source_id:
        fp = compute_dedup_fingerprint(author_id=author_id, source_id=source_id)
        cur.execute("SELECT * FROM public.leads WHERE dedup_fingerprint = %s ORDER BY created_at ASC LIMIT 1;", (fp,))
        row = cur.fetchone()
        if row:
            return 'POSSIBLE_DUPLICATE', dict(row), 'AUTHOR_FALLBACK', 0.50

    # No match -> Brand NEW lead
    return 'NEW', None, 'NO_MATCH', 1.0
