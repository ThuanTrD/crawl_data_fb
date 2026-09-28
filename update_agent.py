import re

with open('/home/ADMIN/qwen_sales_agent.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace pitch generation in analyze_and_pitch
old_pitch_block = '''            qwen_pitch = call_qwen_agent(qwen_prompt, timeout_sec=2)

            # 2. Deterministic pitch using DB Knowledge Base if Qwen is offline or times out
            if not qwen_pitch:
                if is_enjicad:
                    if sub_intent == "PRICING_LICENSING":
                        qwen_pitch = (
                            f"Dạ em chào anh {first_name}! Em thấy anh vừa để lại bình luận quan tâm đến chi phí bản quyền {prod_name} trên bài viết của CIC. "
                            f"Hiện tại bên em đang có chính sách giá ưu đãi tiết kiệm hơn 80% so với AutoCAD, hỗ trợ cả giấy phép Vĩnh viễn (mua 1 lần dùng trọn đời) "
                            f"lẫn gói Thuê bao năm và bản quyền Network cho nhiều máy trong công ty, đầy đủ chứng nhận bản quyền doanh nghiệp hợp pháp từ CIC và hóa đơn VAT. "
                            f"Anh dự kiến trang bị cho bao nhiêu máy để em gửi bảng báo giá chiết khấu tốt nhất cho công ty mình nhé ạ!"
                        )
                    elif sub_intent == "TECHNICAL_INQUIRY":
                        qwen_pitch = (
                            f"Dạ em chào anh {first_name}! Thấy anh đang băn khoăn về độ mượt khi mở bản vẽ nặng và tương thích Lisp/Font tiếng Việt. "
                            f"Phiên bản enjiCAD mới nhất của CIC đã tối ưu hóa nhân đồ họa tăng tốc phần cứng, mở cực mượt các file DWG dung lượng lớn (>150MB) "
                            f"và cam kết tương thích 100% với toàn bộ Lisp, VLISP, Font SHX tiếng Việt của AutoCAD mà không cần sửa code. "
                            f"Em xin phép gửi anh link tải bản dùng thử 30 ngày full tính năng tại enjicad.vn để anh mở thử trực tiếp file dự án của mình trải nghiệm nhé ạ!"
                        )
                    elif sub_intent == "DIRECT_INBOX_REQUEST":
                        qwen_pitch = (
                            f"Dạ em chào anh {first_name}! Em thấy anh cmt '{full_text}' quan tâm đến phần mềm {prod_name} của Công ty CIC. "
                            f"Em xin phép gửi anh tài liệu so sánh tính năng enjiCAD với AutoCAD kèm bảng chào giá ưu đãi tiết kiệm hơn 80% qua tin nhắn để anh tham khảo nhé ạ! "
                            f"Anh đang cần trang bị cho cá nhân hay văn phòng thiết kế của công ty ạ?"
                        )
                    else:
                        qwen_pitch = (
                            f"Dạ em chào anh {first_name}! Cảm ơn anh đã quan tâm đến giải pháp {prod_name} của {vendor}. "
                            f"Em xin phép gửi anh brochure chi tiết các tính năng mới của {prod_name} và link tải bản dùng thử 30 ngày để anh trải nghiệm thực tế nhé ạ!"
                        )
                else:
                    # Universal dynamic pitch for ANY other CIC product (ETABS, PLAXIS, SAP2000, Robot, Delft3D, GeoStudio, etc.)
                    if sub_intent == "PRICING_LICENSING":
                        qwen_pitch = (
                            f"Dạ em chào anh {first_name}! Em thấy anh vừa để lại bình luận quan tâm đến bản quyền và chi phí trang bị {prod_name} trên bài viết của CIC. "
                            f"CIC hiện là đại diện phân phối và chuyển giao công nghệ chính thức tại Việt Nam, cung cấp đầy đủ giấy chứng nhận bản quyền doanh nghiệp hợp pháp, chứng từ CO/CQ và hóa đơn VAT. "
                            f"Hiện CIC đang áp dụng chính sách giá ưu đãi cùng gói hỗ trợ kỹ thuật trực tiếp từ đội ngũ kỹ sư chuyên gia. Anh dự kiến trang bị cho bao nhiêu người dùng để em gửi bảng báo giá chiết khấu tốt nhất cho mình nhé ạ!"
                        )
                    elif sub_intent == "TECHNICAL_INQUIRY":
                        qwen_pitch = (
                            f"Dạ em chào anh {first_name}! Về thắc mắc kỹ thuật của anh đối với giải pháp {prod_name}: {primary_usp}. "
                            f"{second_usp}. "
                            f"Đội ngũ kỹ sư chuyên gia CIC sẵn sàng hỗ trợ demo kỹ thuật trực tiếp trên bài toán thực tế của đơn vị mình. Em xin phép gửi anh tài liệu kỹ thuật chi tiết qua tin nhắn nhé ạ!"
                        )
                    elif sub_intent == "DIRECT_INBOX_REQUEST":
                        qwen_pitch = (
                            f"Dạ em chào anh {first_name}! Em thấy anh để lại bình luận '{full_text}' quan tâm đến giải pháp {prod_name} từ {vendor}. "
                            f"Em xin phép gửi anh brochure giải pháp kèm bảng chào giá chính hãng qua tin nhắn riêng để anh tham khảo ngay nhé ạ! "
                            f"Anh đang cần triển khai cho dự án nào sắp tới chưa ạ?"
                        )
                    else:
                        qwen_pitch = (
                            f"Dạ em chào anh {first_name}! Cảm ơn anh đã quan tâm đến giải pháp {prod_name} do {vendor} phân phối chính hãng. "
                            f"{primary_usp}. Em xin phép gửi anh thông tin chi tiết giải pháp kèm tài liệu demo để anh trải nghiệm thực tế nhé ạ!"
                        )

            telesale = f"Dạ alo em chào anh {first_name}, em là chuyên viên tư vấn giải pháp {prod_name} từ {vendor}. Em thấy anh vừa để lại bình luận '{full_text}' trên Facebook nên em liên hệ hỗ trợ tư vấn kỹ thuật và gửi tài liệu demo/báo giá chính hãng ngay cho anh..."'''

new_pitch_block = '''            # Gọi Qwen Agent sinh lời thoại dựa trên dữ liệu sản phẩm trong DB
            qwen_pitch = call_qwen_agent(qwen_prompt, timeout_sec=3)

            if qwen_pitch:
                pitch_status = "GENERATED_BY_QWEN"
                ai_agent_name = "Qwen3-VL-30B"
                final_pitch = qwen_pitch
                telesale = f"Dạ alo em chào anh {first_name}, em là chuyên viên tư vấn giải pháp {prod_name} từ {vendor}. Em thấy anh vừa để lại bình luận '{full_text}' trên Facebook nên em liên hệ hỗ trợ tư vấn kỹ thuật và gửi tài liệu demo/báo giá chính hãng ngay cho anh..."
            else:
                # Nếu Qwen đang bận/quá tải, giữ nguyên dữ liệu cào khách hàng và đánh dấu chờ Qwen xử lý
                pitch_status = "PENDING_QWEN"
                ai_agent_name = "Qwen3-VL-30B (Chờ sinh thoại)"
                final_pitch = None
                telesale = None'''

if old_pitch_block in code:
    code = code.replace(old_pitch_block, new_pitch_block)
    print("Replaced pitch block with pure Qwen delegation")
else:
    print("Old pitch block not matched exactly")

# Update dictionary insertion
code = code.replace('"messenger_pitch": qwen_pitch,', '"messenger_pitch": final_pitch,\n                "pitch_status": pitch_status,\n                "ai_agent": ai_agent_name,')
code = code.replace('"ai_agent": "Qwen3-VL-30B"', '"ai_agent": c.get("ai_agent", "Qwen3-VL-30B"),\n                "pitch_status": c.get("pitch_status", "PENDING_QWEN")')

# Append generate_pitch_with_qwen function at bottom
func_code = '''

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
    usp_summary = "\\n- ".join(usps[:3]) if usps else f"Giải pháp {prod_name} chính hãng từ CIC"
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

    # 3. Gọi Qwen3-VL-30B
    pitch = call_qwen_agent(prompt, timeout_sec=15)
    if pitch:
        meta["messenger_pitch"] = pitch
        meta["ai_agent"] = "Qwen3-VL-30B"
        meta["pitch_status"] = "GENERATED_BY_QWEN"
        meta["pitch_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        telesale = f"Dạ alo em chào anh {first_name}, em là chuyên viên tư vấn giải pháp {prod_name} từ {vendor}. Em thấy anh vừa để lại bình luận '{comment_text}' trên Facebook nên em liên hệ hỗ trợ tư vấn kỹ thuật và gửi tài liệu demo/báo giá chính hãng ngay cho anh..."
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
            "ai_agent": "Qwen3-VL-30B"
        }
    else:
        cur.close()
        conn.close()
        return {
            "success": False,
            "error": "Mô hình Qwen3-VL-30B hiện đang trong hàng đợi GPU hoặc quá thời gian phản hồi (Timeout). Dữ liệu khách hàng vẫn được bảo toàn trong Database."
        }
'''

if "def generate_pitch_with_qwen" not in code:
    code += func_code
    print("Added generate_pitch_with_qwen")

with open('/home/ADMIN/qwen_sales_agent.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated qwen_sales_agent.py successfully")
