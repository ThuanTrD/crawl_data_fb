import re

app_file = "/home/ADMIN/dashboard/app.py"
with open(app_file, "r", encoding="utf-8") as f:
    code = f.read()

new_routes = """
@app.route('/api/keyword/crawl', methods=['POST'])
def api_keyword_crawl():
    \"\"\"
    Cao du lieu khach hang tu dong theo tu khoa:
    1. Tim bai viet hot nhat theo tu khoa
    2. Cao toan bo binh luan & thong tin khach hang
    3. Agent Qwen3-VL-30B tong hop insight
    4. Dua vao DB product_knowledge_base sinh loi thoai thuyet phuc
    5. Luu Supabase & ban alert
    \"\"\"
    try:
        data = request.json or {}
        keyword = data.get('keyword', '').strip()
        max_posts = int(data.get('max_posts', 2))

        if not keyword:
            return jsonify({'success': False, 'error': 'Vui lòng nhập từ khóa tìm kiếm (Ví dụ: enjicad)'}), 400

        add_log('START', f'=== [Keyword Bot] Bắt đầu tìm bài viết hot nhất cho từ khóa: \"{keyword}\" ===')
        
        from qwen_sales_agent import run_keyword_pipeline
        result = run_keyword_pipeline(keyword=keyword, max_posts=max_posts)

        if not result.get('success'):
            add_log('WARN', f'[Keyword Bot] {result.get("error", "Không tìm thấy bài viết")}')
            return jsonify(result), 404

        total_leads = result.get('total_leads_identified', 0)
        hot_leads = result.get('hot_leads_count', 0)
        add_log('SUCCESS', f'[Keyword Bot] Hoàn tất quét \"{keyword}\": Quét {result.get("posts_scanned")} bài viết hot, tìm thấy {total_leads} khách hàng ({hot_leads} HOT)!')

        return jsonify(result)
    except Exception as e:
        add_log('ERROR', f'[Keyword Bot] Lỗi quét theo từ khóa: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/knowledge', methods=['GET', 'POST'])
def api_product_knowledge():
    \"\"\"Quan ly co so du lieu san pham & kich ban chot sale trong Supabase.\"\"\"
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        try:
            data = request.json or {}
            key = data.get('product_key', 'enjicad').lower().strip()
            name = data.get('product_name', 'EnjiCAD')
            vendor = data.get('vendor', 'Công ty CP Công nghệ và Tư vấn CIC')
            usps = data.get('key_usps', [])
            pricing = data.get('pricing_details', {})
            objections = data.get('objection_scripts', {})
            playbook = data.get('sales_playbook', {})

            sql = \"\"\"
                INSERT INTO public.product_knowledge_base (
                    product_key, product_name, vendor, key_usps, pricing_details, objection_scripts, sales_playbook, updated_at
                ) VALUES (
                    %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, NOW()
                )
                ON CONFLICT (product_key) DO UPDATE SET
                    product_name = EXCLUDED.product_name,
                    vendor = EXCLUDED.vendor,
                    key_usps = EXCLUDED.key_usps,
                    pricing_details = EXCLUDED.pricing_details,
                    objection_scripts = EXCLUDED.objection_scripts,
                    sales_playbook = EXCLUDED.sales_playbook,
                    updated_at = NOW()
                RETURNING id;
            \"\"\"
            cur.execute(sql, (key, name, vendor, json.dumps(usps), json.dumps(pricing), json.dumps(objections), json.dumps(playbook)))
            conn.commit()
            cur.close()
            conn.close()
            add_log('SUCCESS', f'Đã lưu thông tin sản phẩm \"{name}\" vào database thành công.')
            return jsonify({'success': True, 'message': 'Đã cập nhật cơ sở dữ liệu sản phẩm'})
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': str(e)}), 500
    else:
        try:
            cur.execute('SELECT * FROM public.product_knowledge_base ORDER BY updated_at DESC;')
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            conn.close()
            return jsonify({'success': True, 'data': rows})
        except Exception as e:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': str(e)}), 500
"""

if "def api_keyword_crawl():" not in code:
    code = code.replace('@app.route("/api/adhoc/crawl"', new_routes + '\n@app.route("/api/adhoc/crawl"')
    with open(app_file, "w", encoding="utf-8") as f:
        f.write(code)
    print("Added /api/keyword/crawl and /api/knowledge successfully!")
else:
    print("Routes already exist.")
