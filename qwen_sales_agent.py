"""
Qwen Customer Intelligence & Database-Driven Sales Pitch Agent
- Aggregates customer profiles from crawled Facebook comments.
- Queries product knowledge base & objection scripts from Supabase for ALL 276+ CIC products.
- Uses Qwen3-VL-30B (with robust deterministic fallback) to generate persuasive sales pitches.
- Persists enriched leads into Supabase & dispatches alerts.
"""

import os
import re
import json
import time
import ssl
import hashlib
import urllib.request
from typing import Dict, Any, List, Optional
import psycopg2
import psycopg2.extras

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"
)

QWEN_ENDPOINT = os.getenv("QWEN_ENDPOINT", "https://ai-api.cic.com.vn:9443/v1/chat/completions")
QWEN_TOKEN = os.getenv("QWEN_TOKEN", "sk-cic-c708615648777c1a926b275c250c3684")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3-vl-30b")

def get_product_knowledge(product_key: str = "enjicad") -> Dict[str, Any]:
    """Universal product matcher across all 276+ official CIC products in Supabase."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    kw_clean = (product_key or "enjicad").strip().lower()
    pattern = f"%{kw_clean}%"

    query = """
        SELECT *
        FROM public.product_knowledge_base
        WHERE product_key = %s
           OR product_key ILIKE %s
           OR product_name ILIKE %s
           OR key_usps::text ILIKE %s
           OR target_audience ILIKE %s
           OR metadata::text ILIKE %s
        ORDER BY 
            CASE 
                WHEN product_key = %s THEN 1
                WHEN product_name ILIKE %s THEN 2
                WHEN product_key ILIKE %s THEN 3
                ELSE 4
            END,
            LENGTH(product_name) ASC
        LIMIT 1;
    """
    cur.execute(query, (kw_clean, pattern, pattern, pattern, pattern, pattern, kw_clean, f"{kw_clean}%", pattern))
    row = cur.fetchone()

    # Try word-by-word match if not found
    if not row and " " in kw_clean:
        for word in kw_clean.split():
            if len(word) >= 3:
                w_pat = f"%{word}%"
                cur.execute(query, (word, w_pat, w_pat, w_pat, w_pat, w_pat, word, f"{word}%", w_pat))
                row = cur.fetchone()
                if row:
                    break

    cur.close()
    conn.close()

    if row:
        return dict(row)

    # General Corporate Profile for CIC Products
    prod_title = kw_clean.upper()
    return {
        "product_key": kw_clean,
        "product_name": f"Giải pháp phần mềm {prod_title} (Chính hãng CIC)",
        "vendor": "Công ty Cổ phần Công nghệ và Tư vấn CIC (37 Lê Đại Hành, Hà Nội)",
        "target_audience": "Kỹ sư và Doanh nghiệp tư vấn thiết kế, thi công xây dựng & hạ tầng kỹ thuật",
        "key_usps": [
            f"Giải pháp {prod_title} được phân phối và chuyển giao công nghệ chính hãng bởi CIC (35+ năm kinh nghiệm).",
            "Đầy đủ giấy chứng nhận bản quyền doanh nghiệp hợp pháp, chứng từ CO/CQ và hóa đơn VAT.",
            "Đội ngũ chuyên gia kỹ sư CIC trực tiếp đào tạo, chuyển giao công nghệ và hỗ trợ kỹ thuật tại Việt Nam."
        ],
        "pricing_details": {
            "policy": "Báo giá chính hãng ưu đãi từ CIC kèm chính sách hỗ trợ kỹ thuật tận nơi.",
            "trial": "Hỗ trợ bản dùng thử (Trial), demo tính năng trực tiếp."
        },
        "objection_scripts": {
            "GIA_VA_HO_TRO": {
                "concern": "Cần báo giá chính hãng và cam kết hỗ trợ kỹ thuật.",
                "selling_point": "CIC là đại diện phân phối chính thức tại Việt Nam, cam kết giá tốt nhất và hỗ trợ kỹ thuật 24/7.",
                "action": "Xin số lượng máy và thông tin dự án để gửi báo giá chiết khấu tối đa."
            }
        },
        "sales_playbook": {
            "pitch_template_pricing": f"Dạ em chào anh {{name}}! Em thấy anh quan tâm đến giải pháp {prod_title} của CIC. Hiện tại bên em là đơn vị phân phối chính hãng với chính sách giá ưu đãi tốt nhất cho doanh nghiệp. Anh dự kiến trang bị cho bao nhiêu người dùng để em gửi bảng báo giá chi tiết nhé ạ!"
        },
        "metadata": {
            "category": "PHẦN MỀM KỸ THUẬT",
            "official_url": "https://www.cic.com.vn/"
        }
    }


_QWEN_AVAILABLE = None
_QWEN_CHAT_DISABLED_UNTIL = 0

def is_qwen_available():
    global _QWEN_AVAILABLE
    if _QWEN_AVAILABLE is not None:
        return _QWEN_AVAILABLE
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            QWEN_ENDPOINT.replace('/chat/completions', '/models'),
            headers={'Authorization': f'Bearer {QWEN_TOKEN}'}
        )
        with urllib.request.urlopen(req, context=ctx, timeout=2) as r:
            _QWEN_AVAILABLE = (r.status == 200)
    except Exception:
        _QWEN_AVAILABLE = False
    return _QWEN_AVAILABLE

def call_qwen_agent(prompt: str, system_prompt: str = "", timeout_sec: int = 4) -> Optional[str]:
    """Calls Qwen3-VL-30B API with SSL bypass, timeout protection, and fast recovery."""
    global _QWEN_CHAT_DISABLED_UNTIL
    if time.time() < _QWEN_CHAT_DISABLED_UNTIL:
        return None

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        payload = {
            "model": QWEN_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt or "Bạn là chuyên gia tư vấn bán hàng phần mềm kỹ thuật B2B của CIC."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }

        req = urllib.request.Request(
            QWEN_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {QWEN_TOKEN}"
            },
            data=json.dumps(payload).encode("utf-8")
        )

        with urllib.request.urlopen(req, context=ctx, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            # Clean thinking tags if present
            cleaned = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
            return cleaned
    except Exception:
        # If upstream GPU API is busy or timing out, brief 10s cooldown
        _QWEN_CHAT_DISABLED_UNTIL = time.time() + 10
        return None

def generate_knowledge_pitch(lead_data: Dict[str, Any], knowledge: Dict[str, Any]) -> Dict[str, str]:
    """Tạo kịch bản tư vấn chốt sales Messenger & Telesale thông minh dựa trên dữ liệu sản phẩm Supabase."""
    cust_name = lead_data.get("full_name") or lead_data.get("author") or "Quý khách"
    first_name = cust_name.split()[-1] if cust_name and cust_name != "Quý khách" else "Anh/Chị"
    
    meta = lead_data.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
            
    comment = (lead_data.get("comment_text") or meta.get("comment_text") or lead_data.get("primary_intent") or "").strip()
    c_lower = comment.lower()
    
    prod_name = knowledge.get("product_name") or lead_data.get("product_interest") or "Giải pháp phần mềm CIC"
    vendor = knowledge.get("vendor") or "Công ty Cổ phần Công nghệ và Tư vấn CIC (37 Lê Đại Hành, Hà Nội)"
    usps = knowledge.get("key_usps") or []
    pricing = knowledge.get("pricing_details") or {}
    metadata = knowledge.get("metadata") or {}
    
    primary_usp = usps[0] if usps else f"Giải pháp {prod_name} chính hãng từ CIC (35+ năm kinh nghiệm)"
    second_usp = usps[1] if len(usps) > 1 else "Hỗ trợ kỹ thuật trực tiếp bởi đội ngũ kỹ sư CIC tại Việt Nam"
    
    # 1. Khách hỏi giá, chi phí, bản quyền, thuê bao
    if any(k in c_lower for k in ["giá", "báo giá", "thuê bao", "chi phí", "bao tiền", "license", "năm", "mua", "kinh phí", "bản quyền", "hóa đơn", "vat"]):
        policy = pricing.get("policy") or pricing.get("perpetual_license") or "chính sách bản quyền vĩnh viễn ưu đãi nhất kèm chứng nhận hợp pháp và hóa đơn VAT"
        messenger_pitch = (
            f"Dạ em chào anh {first_name}! Em bên Công ty CIC - đơn vị phân phối chính thức giải pháp {prod_name} tại Việt Nam ạ.\n"
            f"Hiện tại bên em đang có {policy}, hỗ trợ đào tạo chuyển giao và kỹ sư bảo hành kỹ thuật trực tiếp.\n"
            f"Anh {first_name} dự kiến trang bị cho khoảng bao nhiêu người dùng/máy tính để em gửi bảng báo giá chiết khấu ưu đãi tối đa ngay cho mình nhé ạ!"
        )
    # 2. Khách xin link tải, dùng thử, cài test
    elif any(k in c_lower for k in ["dùng thử", "cài thử", "test", "link tải", "bộ cài", "demo", "tải về", "download", "link"]):
        messenger_pitch = (
            f"Dạ em chào anh {first_name}! Em thấy mình đang muốn trải nghiệm thử giải pháp {prod_name} của CIC.\n"
            f"{prod_name} sở hữu tốc độ xử lý đồ họa mượt mà ({primary_usp}) và tương thích 100% định dạng kỹ thuật hiện hành.\n"
            f"Em xin phép gửi anh link tải bộ cài chính hãng kèm tài liệu hướng dẫn kích hoạt dùng thử. Nếu cần hỗ trợ cài đặt hoặc hướng dẫn tính năng, đội ngũ kỹ sư CIC sẵn sàng hỗ trợ trực tiếp từ xa cho anh ạ!"
        )
    # 3. Khách hỏi kỹ thuật, font, lisp, giật lag, tính toán, TCVN
    elif any(k in c_lower for k in ["mượt", "lag", "giật", "nặng", "lisp", "font", "shx", "vinacad", "autocad", "tính toán", "mô hình", "tiêu chuẩn", "tcvn", "cấu hình"]):
        messenger_pitch = (
            f"Dạ em chào anh {first_name}! Về vấn đề kỹ thuật anh đang quan tâm đối với {prod_name}:\n"
            f"Sản phẩm được tối ưu hoàn toàn: {primary_usp}. Đặc biệt {second_usp}.\n"
            f"Em xin phép gửi anh tài liệu kỹ thuật chi tiết và video demo trực quan. Anh có thể nhắn lại em để chuyên gia kỹ sư CIC hỗ trợ giải đáp chuyên sâu cho dự án của mình nhé ạ!"
        )
    # 4. Khách yêu cầu inbox / tư vấn riêng
    elif any(k in c_lower for k in ["ib", "inbox", "nhắn tin", "check ib", "tư vấn"]):
        messenger_pitch = (
            f"Dạ em chào anh {first_name}! Em liên hệ với anh từ Công ty Cổ phần Công nghệ và Tư vấn CIC (37 Lê Đại Hành, HN) về giải pháp {prod_name}.\n"
            f"Bên em là đại diện cung cấp chính hãng: {primary_usp}.\n"
            f"Em xin phép gửi anh brochure giải pháp và thông tin chính sách ưu đãi qua tin nhắn này. Anh cần tư vấn cho cá nhân hay cho dự án công ty để em hỗ trợ chính xác nhất ạ?"
        )
    # 5. Mặc định: Phân tích theo USP & giới thiệu thân thiện
    else:
        messenger_pitch = (
            f"Dạ em chào anh {first_name}! Em thấy mình vừa quan tâm đến bài viết về giải pháp {prod_name} của CIC.\n"
            f"{prod_name} là {primary_usp}, được hàng nghìn kỹ sư và doanh nghiệp tư vấn xây dựng tại Việt Nam tin dùng.\n"
            f"Em xin phép gửi anh bản thông tin tính năng nổi bật cùng chính sách hỗ trợ kỹ thuật từ CIC. Anh tham khảo và nhắn em hỗ trợ mình bất cứ lúc nào nhé ạ!"
        )
        
    telesale_script = (
        f"Dạ alo em chào anh {first_name}, em là chuyên viên tư vấn phần mềm {prod_name} từ Công ty CIC (37 Lê Đại Hành). "
        f"Em thấy anh có để lại quan tâm '{comment}' về phần mềm trên Facebook. "
        f"Em gọi để hỗ trợ gửi anh tài liệu kỹ thuật và chính sách báo giá chính hãng ưu đãi nhất của CIC ạ..."
    )
    
    return {
        "messenger_pitch": messenger_pitch,
        "telesale_script": telesale_script,
        "ai_agent": "CIC AI Sales Engine (Supabase KB)"
    }


class QwenCustomerIntelligenceAgent:
    """Agent for customer aggregation, intent analysis, and database-informed sales pitching."""

    def __init__(self, post_info: Dict[str, Any], raw_comments: List[Dict[str, Any]], product_key: str = "enjicad"):
        self.post_info = post_info
        self.raw_comments = raw_comments
        self.product_key = product_key
        self.knowledge = get_product_knowledge(product_key)
        self.post_id = str(post_info.get("post_id") or f"post_{int(time.time())}")[:99]
        self.canonical_url = post_info.get("canonical_url") or post_info.get("url") or post_info.get("permalink_url") or "https://www.facebook.com/CICTechnologyandConsultancyVN"
        self.source_name = post_info.get("source_name") or "Công ty Cổ phần Công nghệ và Tư vấn CIC"
        self.post_title = post_info.get("post_title") or post_info.get("title") or post_info.get("message") or f"Giải Pháp {self.product_key.upper()} - CIC Technology"

    def analyze_and_pitch(self) -> Dict[str, Any]:
        # 1. Deduplicate & group comments by author
        grouped = {}
        for c in self.raw_comments:
            name = c.get("author_name") or "Khách hàng"
            user_id = c.get("user_id") or c.get("author_id") or ""
            text = c.get("comment_text") or c.get("message") or ""
            p_url = c.get("profile_url") or (f"https://www.facebook.com/profile.php?id={user_id}" if user_id else "#")

            # Filter out page/admin
            lower_name = name.lower()
            if any(k in lower_name for k in ["cic", "enjicad", "admin", "công nghệ"]):
                continue

            key = f"{user_id}_{name}" if user_id else name
            if key not in grouped:
                grouped[key] = {
                    "author_name": name,
                    "user_id": user_id,
                    "profile_url": p_url,
                    "comments": [],
                    "phone": None,
                    "email": None
                }
            grouped[key]["comments"].append(text)

            # Check phone / email in comment
            pm = re.search(r"(?:0|\+84)(?:3[2-9]|5[2689]|7[06-9]|8[1-9]|9[0-46-9])[0-9]{7}\b", text)
            em = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
            if pm and not grouped[key]["phone"]:
                grouped[key]["phone"] = pm.group(0)
            if em and not grouped[key]["email"]:
                grouped[key]["email"] = em.group(0)

        # 2. Analyze each customer using Qwen / Knowledge Base
        usps = self.knowledge.get("key_usps", [])
        pricing = self.knowledge.get("pricing_details", {})
        objections = self.knowledge.get("objection_scripts", {})
        metadata = self.knowledge.get("metadata", {})
        prod_name = self.knowledge.get("product_name") or f"Giải pháp {self.product_key.upper()}"
        vendor = self.knowledge.get("vendor", "Công ty Cổ phần Công nghệ và Tư vấn CIC (37 Lê Đại Hành, Hà Nội)")
        official_url = metadata.get("official_url") or metadata.get("product_portal") or "https://www.cic.com.vn/"
        primary_usp = usps[0] if usps else f"Giải pháp {prod_name} chính hãng từ CIC"
        second_usp = usps[1] if len(usps) > 1 else "Đội ngũ chuyên gia kỹ sư CIC trực tiếp hỗ trợ kỹ thuật và đào tạo chuyển giao"

        is_enjicad = any(k in self.product_key.lower() or k in prod_name.lower() for k in ["enjicad", "intellicad"])

        customers = []
        hot_count = 0
        warm_count = 0

        for key, cust in grouped.items():
            full_text = " | ".join(cust["comments"])
            t_lower = full_text.lower()

            # Intent classification
            intent = "DISCUSSION"
            sub_intent = "GENERAL_INTERACTION"
            score = 65
            tier = "WARM"
            pain_point = f"Tìm hiểu thông tin giải pháp {prod_name}"
            sales_action = f"Nhắn tin Messenger tư vấn chi tiết về tính năng giải pháp {prod_name}"

            if any(k in t_lower for k in ["giá", "báo giá", "thuê bao", "chi phí", "bao tiền", "license", "năm", "mua"]):
                intent = "REQUEST_QUOTE"
                sub_intent = "PRICING_LICENSING"
                score = 90
                tier = "HOT"
                pain_point = f"Cần bảng giá và chính sách cấp phép {prod_name}, tối ưu ngân sách cho đơn vị"
                sales_action = f"Gửi báo giá {prod_name} chính hãng kèm chính sách ưu đãi và tư vấn gói bản quyền"
            elif any(k in t_lower for k in ["ib", "inbox", "nhắn tin", "check ib"]):
                intent = "URGENT_NEED"
                sub_intent = "DIRECT_INBOX_REQUEST"
                score = 88
                tier = "HOT"
                pain_point = f"Yêu cầu tư vấn riêng tư trực tiếp về giải pháp {prod_name}"
                sales_action = f"Nhắn tin Messenger tư vấn giải pháp {prod_name}, gửi brochure và tài liệu giới thiệu"
            elif any(k in t_lower for k in ["mượt", "lag", "giật", "nặng", "lisp", "font", "shx", "vinacad", "autocad", "tính toán", "mô hình", "tiêu chuẩn", "tcvn"]):
                intent = "RESEARCH"
                sub_intent = "TECHNICAL_INQUIRY"
                score = 85
                tier = "HOT"
                pain_point = f"Tìm hiểu thông số kỹ thuật, khả năng tính toán và độ tương thích của {prod_name}"
                sales_action = f"Tư vấn kỹ thuật {prod_name}: Giải đáp tính năng, gửi tài liệu hướng dẫn kỹ thuật"
            elif any(k in t_lower for k in ["dùng thử", "cài thử", "test", "link tải", "bộ cài", "demo"]):
                intent = "LOOKING_TO_BUY"
                sub_intent = "TRIAL_REQUEST"
                score = 85
                tier = "HOT"
                pain_point = f"Muốn cài đặt dùng thử / trải nghiệm thực tế {prod_name} trước khi quyết định mua"
                sales_action = f"Gửi link tải bộ cài / demo {prod_name} và hướng dẫn trải nghiệm dùng thử"

            if cust["phone"]:
                score = min(100, score + 10)
                tier = "HOT"

            if tier == "HOT":
                hot_count += 1
            else:
                warm_count += 1

            # Generate Persuasive Pitch informed by Knowledge Base
            first_name = cust["author_name"].split()[-1] if cust["author_name"] else "Anh/Chị"

            # 1. Try Qwen first for bespoke persuasive script
            usp_summary = "\n- ".join(usps[:3]) if usps else f"Giải pháp {prod_name} chính hãng từ CIC"
            pricing_summary = pricing.get("policy") or pricing.get("perpetual_license") or "Bản quyền chính hãng, hỗ trợ kỹ thuật trực tiếp từ kỹ sư CIC"

            qwen_prompt = f"""Bạn là chuyên viên tư vấn bán hàng giải pháp phần mềm kỹ thuật của {vendor}.
Thông tin chính thức từ website {official_url}:
- Sản phẩm: {prod_name}
- Nhà cung cấp / Phân phối: {vendor}
- Điểm mạnh chính (USPs):
- {usp_summary}
- Chính sách bản quyền & Giá: {pricing_summary}
- Hỗ trợ kỹ thuật: Kỹ sư CIC hỗ trợ trực tiếp bằng tiếng Việt, đầy đủ chứng nhận bản quyền doanh nghiệp và hóa đơn VAT.

Khách hàng: {cust['author_name']} ({first_name})
Bình luận của khách: "{full_text}"
Nhu cầu / Khúc mắc: {pain_point}

Nhiệm vụ: Viết 1 tin nhắn Messenger tư vấn chân thành, tự nhiên, đánh trúng nhu cầu khách hàng dựa trên thông tin chính thức của CIC ở trên. Kêu gọi hành động gửi báo giá hoặc tài liệu demo/dùng thử. Xưng hô Em - Anh/Chị {first_name}. Viết ngắn gọn 3-4 câu."""

            # Gọi Qwen Agent sinh lời thoại dựa trên dữ liệu sản phẩm trong DB
            qwen_pitch = call_qwen_agent(qwen_prompt, timeout_sec=3)

            if qwen_pitch:
                pitch_status = "GENERATED_BY_QWEN"
                ai_agent_name = "Qwen3-VL-30B"
                final_pitch = qwen_pitch
                telesale = f"Dạ alo em chào anh {first_name}, em là chuyên viên tư vấn giải pháp {prod_name} từ {vendor}. Em thấy anh vừa để lại bình luận '{full_text}' trên Facebook nên em liên hệ hỗ trợ tư vấn kỹ thuật và gửi tài liệu demo/báo giá chính hãng ngay cho anh..."
            else:
                # Nếu Qwen bận/quá tải, sinh kịch bản ngay bằng Knowledge Base Supabase
                kb_pitch = generate_knowledge_pitch({
                    "full_name": cust["author_name"],
                    "comment_text": full_text,
                    "product_interest": prod_name,
                    "pain_point": pain_point,
                    "intent": intent,
                    "phone": cust["phone"]
                }, self.knowledge)
                pitch_status = "GENERATED_BY_KNOWLEDGE"
                ai_agent_name = "CIC AI Sales Engine (Supabase KB)"
                final_pitch = kb_pitch["messenger_pitch"]
                telesale = kb_pitch["telesale_script"]

            fingerprint = hashlib.md5(f"{cust['user_id'] or cust['author_name']}_{self.post_id}".encode("utf-8")).hexdigest()

            customers.append({
                "lead_id": cust["user_id"] or cust["author_name"],
                "author": cust["author_name"],
                "user_id": cust["user_id"],
                "profile_url": cust["profile_url"],
                "company": f"Facebook: {cust['profile_url']}",
                "phone": cust["phone"] or "-",
                "email": cust["email"] or "-",
                "phone_status": "CÔNG KHAI" if cust["phone"] else "ẨN (Bảo mật Facebook)",
                "intent": intent,
                "sub_intent": sub_intent,
                "product": prod_name,
                "score": score,
                "tier": tier,
                "comment_text": full_text,
                "pain_point": pain_point,
                "recommended_action": sales_action,
                "messenger_pitch": final_pitch,
                "pitch_status": pitch_status,
                "ai_agent": ai_agent_name,
                "telesale_script": telesale,
                "dedup_fingerprint": fingerprint
            })

        # Sort highest score first
        customers.sort(key=lambda x: x["score"], reverse=True)

        return {
            "post_id": self.post_id,
            "post_url": self.canonical_url,
            "post_title": self.post_title,
            "product_key": self.product_key,
            "product_name": prod_name,
            "statistics": {
                "total_comments": len(self.raw_comments),
                "total_customers": len(customers),
                "hot_leads": hot_count,
                "warm_leads": warm_count
            },
            "customers": customers
        }

    def persist_results(self, result: Dict[str, Any]) -> int:
        """Saves leads, post, and comments to Supabase."""
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        # 1. Ensure source
        cur.execute("""
            INSERT INTO public.facebook_sources (external_id, name, source_type, url, status, updated_at)
            VALUES (%s, %s, 'PAGE', %s, 'ACTIVE', NOW())
            ON CONFLICT (external_id) DO UPDATE SET updated_at = NOW()
            RETURNING id;
        """, (f"src_{self.product_key}", self.source_name, self.canonical_url))
        source_id = cur.fetchone()[0]

        # 2. Save post
        cur.execute("""
            INSERT INTO public.facebook_posts (
                source_id, post_id, page_id, permalink_url, author_name, message,
                reactions_count, comments_count, created_time, crawled_at, updated_at, metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                28, %s, NOW() - INTERVAL '1 hour', NOW(), NOW(), %s
            )
            ON CONFLICT (post_id) DO UPDATE SET
                comments_count = EXCLUDED.comments_count,
                metadata = EXCLUDED.metadata,
                updated_at = NOW();
        """, (
            source_id, self.post_id, f"page_{self.product_key}", self.canonical_url,
            self.source_name, self.post_title, result["statistics"]["total_comments"],
            json.dumps({"keyword_crawl": True, "product_key": self.product_key})
        ))

        # 3. Save leads
        saved = 0
        prod_category = (self.knowledge.get("metadata") or {}).get("category") or "PHẦN MỀM KỸ THUẬT"

        for c in result["customers"]:
            phone_val = c["phone"] if c["phone"] != "-" else None
            email_val = c["email"] if c["email"] != "-" else None
            meta = json.dumps({
                "post_id": self.post_id,
                "source_post_url": self.canonical_url,
                "source_post_title": self.post_title,
                "source_name": self.source_name,
                "facebook_profile_url": c["profile_url"],
                "comment_text": c["comment_text"],
                "phone_status": c["phone_status"],
                "pain_point": c["pain_point"],
                "sales_action": c["recommended_action"],
                "messenger_pitch": c["messenger_pitch"],
                "telesale_script": c["telesale_script"],
                "pitch_status": c.get("pitch_status", "PENDING_QWEN"),
                "ai_agent": "Qwen3-VL-30B-SalesAgent"
            })

            cur.execute("""
                INSERT INTO public.leads (
                    full_name, company_name, primary_phone, primary_email,
                    customer_type, primary_intent, product_interest, product_group,
                    lead_score, lead_tier, status, resolution, is_quote_requested,
                    dedup_fingerprint, metadata, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    'INDIVIDUAL', %s, %s, %s,
                    %s, %s, 'NEW', 'NEW', true,
                    %s, %s::jsonb, NOW(), NOW()
                )
                ON CONFLICT (dedup_fingerprint) DO UPDATE SET
                    lead_score = EXCLUDED.lead_score,
                    lead_tier = EXCLUDED.lead_tier,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING id;
            """, (
                c["author"], c["company"], phone_val, email_val,
                c["intent"], c["product"], prod_category, c["score"], c["tier"],
                c["dedup_fingerprint"], meta
            ))
            lead_row = cur.fetchone()
            if lead_row:
                lead_id = lead_row[0]
                try:
                    cur.execute("""
                        INSERT INTO public.lead_sources (lead_id, source_id, origin_url, post_id, platform, created_at)
                        VALUES (%s, %s, %s, %s, 'FACEBOOK', NOW())
                        ON CONFLICT DO NOTHING;
                    """, (lead_id, source_id, self.canonical_url, self.post_id))
                except Exception:
                    pass
            saved += 1

        conn.commit()
        cur.close()
        conn.close()
        return saved

def run_keyword_pipeline(keyword: str = "enjicad", max_posts: int = 5) -> Dict[str, Any]:
    """
    Complete Universal Workflow for ANY CIC Product:
    Keyword -> Find Hottest Posts -> Parallel Crawl Comments -> Qwen Sales Agent -> Supabase
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    from keyword_search_engine import find_hottest_posts
    from facebook_comment_crawler import crawl_facebook_post_and_all_comments

    # 1. Find hottest posts with user-chosen quantity
    hottest = find_hottest_posts(keyword, top_k=max_posts)
    if not hottest:
        return {"success": False, "error": f"Không tìm thấy bài viết nào cho từ khóa '{keyword}'"}

    total_leads = []
    hot_posts_processed = []

    def process_single_post(post):
        try:
            post_url = post["url"]
            crawled = crawl_facebook_post_and_all_comments(post_url, manual_content=post["title"])
            post_info = crawled["post_info"]
            post_info["title"] = post["title"]
            post_info["reactions_count"] = post["reactions_count"]
            raw_comments = crawled["comments"]

            agent = QwenCustomerIntelligenceAgent(post_info, raw_comments, product_key=keyword)
            analysis = agent.analyze_and_pitch()
            saved_count = agent.persist_results(analysis)
            analysis["saved_leads_count"] = saved_count

            summary = {
                "post_title": post["title"],
                "url": post["url"],
                "engagement_score": post["engagement_score"],
                "comments_crawled": len(raw_comments),
                "customers_found": len(analysis["customers"]),
                "hot_leads": analysis["statistics"]["hot_leads"]
            }
            return analysis["customers"], summary
        except Exception as e:
            return [], None

    workers = min(8, len(hottest))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(process_single_post, p) for p in hottest]
        for f in as_completed(futures):
            custs, summary = f.result()
            if summary:
                total_leads.extend(custs)
                hot_posts_processed.append(summary)

    # Trigger Telegram alert in background thread so API response is instant
    hot_count = sum(1 for l in total_leads if l.get("tier") == "HOT")
    if hot_count > 0:
        def bg_notify():
            try:
                from notification.notification_runner import run_notification_cycle
                run_notification_cycle(20)
            except Exception:
                pass
        threading.Thread(target=bg_notify, daemon=True).start()

    return {
        "success": True,
        "keyword": keyword,
        "product_knowledge_used": get_product_knowledge(keyword).get("product_name"),
        "posts_scanned": len(hot_posts_processed),
        "hot_posts": hot_posts_processed,
        "total_leads_identified": len(total_leads),
        "hot_leads_count": hot_count,
        "leads": total_leads
    }

if __name__ == "__main__":
    kw = "etabs"
    print(f"=== Testing Keyword Pipeline for: '{kw}' ===")
    res = run_keyword_pipeline(kw, max_posts=1)
    print(f"Success: {res['success']}")
    print(f"Product Knowledge: {res.get('product_knowledge_used')}")
    print(f"Total Leads Identified: {res['total_leads_identified']}")
    print(f"Hot Leads: {res['hot_leads_count']}")
    if res["leads"]:
        lead = res["leads"][0]
        print(f"Top Customer: {lead['author']}")
        print(f"Score: {lead['score']} ({lead['tier']})")
        print(f"Pain Point: {lead['pain_point']}")
        print(f"Messenger Pitch:\n{lead['messenger_pitch']}")
        print(f"Telesale Script:\n{lead['telesale_script']}")


def generate_pitch_with_qwen(lead_id: str) -> Dict[str, Any]:
    """Sinh lời thoại trực tiếp bằng mô hình Qwen3-VL-30B kết hợp Database Supabase."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM public.leads WHERE id = %s;", (lead_id,))
    lead = cur.fetchone()
    if not lead:
        cur.close()
        conn.close()
        return {"success": False, "error": "Không tìm thấy khách hàng trong database"}

    lead_dict = dict(lead)
    prod_interest = lead_dict.get("product_interest") or "enjicad"
    meta = lead_dict.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}

    comment_text = meta.get("comment_text") or lead_dict.get("primary_intent") or ""
    cust_name = lead_dict.get("full_name") or "Khách hàng"
    first_name = cust_name.split()[-1] if cust_name else "Anh/Chị"

    # 1. Truy vấn thông tin sản phẩm từ Database Supabase
    knowledge = get_product_knowledge(prod_interest)
    prod_name = knowledge.get("product_name") or prod_interest
    vendor = knowledge.get("vendor", "Công ty Cổ phần Công nghệ và Tư vấn CIC (37 Lê Đại Hành, Hà Nội)")
    usps = knowledge.get("key_usps", [])
    pricing = knowledge.get("pricing_details", {})
    usp_summary = "\n- ".join(usps[:3]) if usps else f"Giải pháp {prod_name} chính hãng từ CIC"
    pricing_summary = pricing.get("policy") or pricing.get("perpetual_license") or "Bản quyền chính hãng, hỗ trợ kỹ thuật trực tiếp"
    official_url = (knowledge.get("metadata") or {}).get("official_url") or "https://www.cic.com.vn/"

    # 2. Tạo prompt gửi cho Qwen3-VL-30B
    prompt = f"""Bạn là chuyên viên tư vấn bán hàng giải pháp phần mềm kỹ thuật của {vendor}.
Dữ liệu chính thức từ cơ sở dữ liệu Supabase của CIC (website: {official_url}):
- Sản phẩm: {prod_name}
- Nhà cung cấp / Phân phối: {vendor}
- Điểm mạnh chính (USPs):
- {usp_summary}
- Chính sách bản quyền & Giá: {pricing_summary}

Khách hàng: {cust_name} ({first_name})
Bình luận của khách hàng trên Facebook: "{comment_text}"

Nhiệm vụ: Dựa trên đúng dữ liệu sản phẩm trong database ở trên, hãy viết 1 tin nhắn Messenger tư vấn chân thành, tự nhiên, đánh trúng nhu cầu khách hàng. Kêu gọi hành động gửi báo giá hoặc tài liệu demo/dùng thử. Xưng hô Em - Anh/Chị {first_name}. Viết ngắn gọn 3-4 câu."""

    # 3. Thử gọi Qwen3-VL-30B với timeout bảo vệ 4s
    pitch = call_qwen_agent(prompt, timeout_sec=4)
    ai_agent_used = "Qwen3-VL-30B"

    # 4. Nếu Qwen GPU bận hoặc timeout, lập tức kích hoạt bộ sinh kịch bản Database Supabase
    if not pitch:
        kb_res = generate_knowledge_pitch(lead_dict, knowledge)
        pitch = kb_res["messenger_pitch"]
        telesale = kb_res["telesale_script"]
        ai_agent_used = "CIC AI Sales Engine (Supabase KB)"
    else:
        telesale = f"Dạ alo em chào anh {first_name}, em là chuyên viên tư vấn giải pháp {prod_name} từ {vendor}. Em thấy anh vừa để lại bình luận '{comment_text}' trên Facebook nên em liên hệ hỗ trợ tư vấn kỹ thuật và gửi tài liệu demo/báo giá chính hãng ngay cho anh..."

    meta["messenger_pitch"] = pitch
    meta["ai_agent"] = ai_agent_used
    meta["pitch_status"] = "GENERATED"
    meta["pitch_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    meta["telesale_script"] = telesale

    cur.execute("UPDATE public.leads SET metadata = %s::jsonb, updated_at = NOW() WHERE id = %s;", (json.dumps(meta), lead_id))
    conn.commit()
    cur.close()
    conn.close()

    return {
        "success": True,
        "lead_id": lead_id,
        "product": prod_name,
        "messenger_pitch": pitch,
        "telesale_script": telesale,
        "ai_agent": ai_agent_used
    }

def crawl_and_analyze_selected_posts(selected_posts: List[Dict[str, Any]], keyword: str = "enjicad") -> Dict[str, Any]:
    """
    Giai đoạn 2: Cào bình luận và bóc tách thông tin khách hàng từ danh sách bài viết người dùng đã tích chọn.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from facebook_comment_crawler import crawl_facebook_post_and_all_comments
    import threading

    total_leads = []
    processed_posts = []

    def process_one(post):
        try:
            post_url = post.get("url") or post.get("permalink_url")
            post_title = post.get("title") or post.get("post_title") or "Bài viết Facebook"
            crawled = crawl_facebook_post_and_all_comments(post_url, manual_content=post_title)
            post_info = crawled["post_info"]
            post_info["title"] = post_title
            raw_comments = crawled["comments"]

            agent = QwenCustomerIntelligenceAgent(post_info, raw_comments, product_key=keyword)
            analysis = agent.analyze_and_pitch()
            saved_count = agent.persist_results(analysis)
            analysis["saved_leads_count"] = saved_count

            summary = {
                "post_title": post_title,
                "url": post_url,
                "comments_crawled": len(raw_comments),
                "customers_found": len(analysis["customers"]),
                "hot_leads": analysis["statistics"]["hot_leads"]
            }
            return analysis["customers"], summary
        except Exception as e:
            return [], None

    workers = min(8, max(1, len(selected_posts)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(process_one, p) for p in selected_posts]
        for f in as_completed(futures):
            custs, summary = f.result()
            if summary:
                total_leads.extend(custs)
                processed_posts.append(summary)

    # Trigger Telegram notification in background if any HOT lead
    hot_count = sum(1 for l in total_leads if l.get("tier") == "HOT")
    if hot_count > 0:
        def bg_notify():
            try:
                from notification.notification_runner import run_notification_cycle
                run_notification_cycle(20)
            except Exception:
                pass
        threading.Thread(target=bg_notify, daemon=True).start()

    return {
        "success": True,
        "keyword": keyword,
        "posts_crawled": len(processed_posts),
        "posts": processed_posts,
        "total_leads_identified": len(total_leads),
        "hot_leads_count": hot_count,
        "leads": total_leads
    }
