with open('/home/ADMIN/dashboard/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = "@app.route('/api/keyword/crawl', methods=['POST'])"
new_routes = """@app.route('/api/keyword/search-posts', methods=['POST'])
def api_keyword_search_posts():
    \"\"\"Giai doan 1: Tim kiem danh sach cac bai viet hot theo tu khoa de nguoi dung lua chon.\"\"\"
    try:
        data = request.json or {}
        keyword = data.get('keyword', '').strip()
        limit = int(data.get('limit', 10))

        if not keyword:
            return jsonify({'success': False, 'error': 'Vui lòng nhập từ khóa tìm kiếm'}), 400

        from keyword_search_engine import find_hottest_posts
        posts = find_hottest_posts(keyword, top_k=limit)
        add_log('INFO', f'[Khám phá bài viết] Tìm thấy {len(posts)} bài viết nổi bật cho từ khóa: \"{keyword}\"')
        return jsonify({
            'success': True,
            'keyword': keyword,
            'total_found': len(posts),
            'posts': posts
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/keyword/crawl-selected', methods=['POST'])
def api_keyword_crawl_selected():
    \"\"\"Giai doan 2: Cao binh luan & thong tin khach hang tu cac bai viet nguoi dung da tich chon.\"\"\"
    try:
        data = request.json or {}
        selected_posts = data.get('posts', [])
        keyword = data.get('keyword', 'enjicad').strip()

        if not selected_posts:
            return jsonify({'success': False, 'error': 'Vui lòng chọn ít nhất 1 bài viết để cào'}), 400

        add_log('START', f'=== [Cào chọn lọc] Bắt đầu cào {len(selected_posts)} bài viết đã chọn (Từ khóa: \"{keyword}\") ===')
        from qwen_sales_agent import crawl_and_analyze_selected_posts
        result = crawl_and_analyze_selected_posts(selected_posts, keyword=keyword)
        
        total_leads = result.get('total_leads_identified', 0)
        hot_leads = result.get('hot_leads_count', 0)
        add_log('SUCCESS', f'[Cào chọn lọc] Hoàn tất cào {len(selected_posts)} bài viết: Bóc tách {total_leads} khách hàng ({hot_leads} HOT)!')
        return jsonify(result)
    except Exception as e:
        add_log('ERROR', f'[Cào chọn lọc] Lỗi: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/keyword/crawl', methods=['POST'])"""

if target in text:
    text = text.replace(target, new_routes, 1)
    with open('/home/ADMIN/dashboard/app.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Added search-posts and crawl-selected routes to app.py")
else:
    print("Target not found in app.py")
