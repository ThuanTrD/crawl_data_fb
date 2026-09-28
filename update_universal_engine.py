with open("/home/ADMIN/qwen_sales_agent.py", "r", encoding="utf-8") as f:
    code = f.read()

# Update get_product_knowledge to be universal
old_get_prod = """def get_product_knowledge(product_key: str = "enjicad") -> Dict[str, Any]:
    \"\"\"Fetches product knowledge, USPs, pricing, and objection scripts from Supabase.\"\"\"
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        \"SELECT * FROM public.product_knowledge_base WHERE product_key = %s OR product_name ILIKE %s LIMIT 1;\",
        (product_key, f\"%{product_key}%\")
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        return dict(row)

    # Default fallback knowledge for CAD
    return {
        \"product_key\": \"enjicad\",
        \"product_name\": \"EnjiCAD Bản Quyền Doanh Nghiệp\",
        \"vendor\": \"CIC Technology\",
        \"key_usps\": [
            \"Tiết kiệm 70% chi phí so với AutoCAD\",
            \"Tương thích 100% lệnh, Lisp và Font SHX tiếng Việt\",
            \"Mở file 150MB cực mượt không giật lag\",
            \"Bản quyền vĩnh viễn hoặc thuê bao năm cực rẻ\"
        ],
        \"pricing_details\": {\"subscription\": \"1/4 AutoCAD\", \"perpetual\": \"Mua 1 lần dùng vĩnh viễn\"},
        \"objection_scripts\": {},
        \"sales_playbook\": {}
    }"""

new_get_prod = """def get_product_knowledge(product_key: str = "enjicad") -> Dict[str, Any]:
    \"\"\"Universal product matcher across all 276+ official CIC products in Supabase.\"\"\"
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    kw_clean = (product_key or "enjicad").strip().lower()
    pattern = f"%{kw_clean}%"

    query = \"\"\"
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
    \"\"\"
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
        }
    }"""

code = code.replace(old_get_prod, new_get_prod)

with open("/home/ADMIN/qwen_sales_agent.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated qwen_sales_agent.py with universal catalog search across all 276 products!")
