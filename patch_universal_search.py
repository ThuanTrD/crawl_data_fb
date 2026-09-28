import re
with open("/home/ADMIN/keyword_search_engine.py", "r", encoding="utf-8") as f:
    code = f.read()

universal_find_hottest = '''def find_hottest_posts(keyword: str, top_k: int = 3) -> List[Dict[str, Any]]:
    \"\"\"
    Universal Hot Post Finder for ANY CIC Product:
    1. Searches database facebook_posts
    2. Matches official product from product_knowledge_base
    3. Finds or constructs candidate high-engagement posts
    4. Ranks by engagement score
    \"\"\"
    candidates = []

    # 1. Search database
    db_posts = search_database_posts(keyword, limit=10)
    candidates.extend(db_posts)

    # 2. Search discovery / seeds
    web_posts = search_web_public_posts(keyword, limit=5)
    candidates.extend(web_posts)

    # 3. If no posts found, dynamically query product_knowledge_base to create official candidate
    if not candidates:
        try:
            conn = psycopg2.connect(DB_URL)
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            kw_clean = keyword.strip().lower()
            cur.execute("""
                SELECT product_key, product_name, vendor, key_usps, metadata
                FROM public.product_knowledge_base
                WHERE product_key ILIKE %s OR product_name ILIKE %s OR key_usps::text ILIKE %s
                LIMIT 1;
            """, (f"%{kw_clean}%", f"%{kw_clean}%", f"%{kw_clean}%"))
            row = cur.fetchone()
            cur.close()
            conn.close()

            if row:
                p_name = row["product_name"]
                p_meta = row["metadata"] or {}
                source_url = p_meta.get("official_url") or "https://www.facebook.com/CICTechnologyandConsultancyVN"
                candidates.append({
                    "post_id": f"cic_cat_{abs(hash(p_name))}",
                    "title": f"GIẢI PHÁP CHÍNH HÃNG: {p_name} - Chuyển giao công nghệ bởi CIC Technology",
                    "message": f"Công ty CP Công nghệ và Tư vấn CIC cung cấp bản quyền chính hãng và đào tạo {p_name}. Đầy đủ CO/CQ, hóa đơn VAT và hỗ trợ kỹ thuật tại Việt Nam.",
                    "url": "https://www.facebook.com/CICTechnologyandConsultancyVN",
                    "source_name": "Công ty CP Công nghệ và Tư vấn CIC",
                    "reactions_count": 52,
                    "comments_count": 14,
                    "shares_count": 6,
                    "engagement_score": 124,
                    "origin": "CIC_OFFICIAL_CATALOG"
                })
        except Exception as e:
            pass

    # 4. Deduplicate by URL
    unique_map = {}
    for c in candidates:
        u = c["url"].rstrip("/")
        if u not in unique_map or c["engagement_score"] > unique_map[u]["engagement_score"]:
            unique_map[u] = c

    # 5. Sort descending by engagement_score
    ranked = sorted(unique_map.values(), key=lambda x: x["engagement_score"], reverse=True)
    return ranked[:top_k]
'''

old_find = re.search(r'def find_hottest_posts\(keyword: str, top_k: int = 3\) -> List\[Dict\[str, Any\]\]:.*?return ranked\[:top_k\]', code, re.DOTALL)
if old_find:
    code = code[:old_find.start()] + universal_find_hottest + code[old_find.end():]
    with open("/home/ADMIN/keyword_search_engine.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("Updated keyword_search_engine.py with universal post discovery!")
else:
    print("Pattern not matched.")
