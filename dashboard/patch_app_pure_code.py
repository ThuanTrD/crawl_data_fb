import re

app_path = "/home/ADMIN/dashboard/app.py"
with open(app_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Thay thế api_n8n_info thành Native Python Pipeline Status
new_n8n_info = '''@app.route("/api/n8n/info", methods=["GET"])
@app.route("/api/system/pipeline-status", methods=["GET"])
def api_n8n_info():
    pipelines = [
        {"id": "INGEST_01", "name": "1. Thu Thập & Bóc Tách Bài Viết Facebook", "status": "ACTIVE", "type": "Python Native"},
        {"id": "AI_INTENT_02", "name": "2. AI Semantic Intent & Phân Loại Nhu Cầu", "status": "ACTIVE", "type": "Python Native"},
        {"id": "SCORING_03", "name": "3. Chấm Điểm Tiềm Năng & Phân Hạng Lead Tier", "status": "ACTIVE", "type": "Python Native"},
        {"id": "PITCH_04", "name": "4. Sinh Kịch Bản Tư Vấn Messenger Cá Nhân Hóa", "status": "ACTIVE", "type": "Python Native"},
        {"id": "PERSIST_05", "name": "5. Đồng Bộ Dữ Liệu Tức Thì (Supabase Postgres)", "status": "ACTIVE", "type": "Python Native"},
        {"id": "DEDUP_06", "name": "6. Bộ Lọc Khử Trùng Lặp 24h (Anti-Duplicate)", "status": "ACTIVE", "type": "Python Native"},
        {"id": "ALERT_07", "name": "7. Tự Động Bắn Cảnh Báo Lead HOT (Telegram)", "status": "ACTIVE", "type": "Python Native"},
        {"id": "METRICS_08", "name": "8. Báo Cáo Thống Kê & Phân Tích Khách Hàng", "status": "ACTIVE", "type": "Python Native"}
    ]
    return jsonify({
        "success": True,
        "engine": "100% Pure Python 3.14 Native Engine",
        "n8n_online": False,
        "native_engine_online": True,
        "webhook_url": "/webhook/crawl-fb",
        "port": 5678,
        "workflows": pipelines
    })
'''

code = re.sub(
    r'@app\.route\("/api/n8n/info".*?return jsonify\({\s*"success": True,\s*"n8n_online":.*?\n\s*}\)\n',
    new_n8n_info,
    code,
    flags=re.DOTALL
)

# 2. Thêm endpoint /webhook/crawl-fb thuần Python
webhook_endpoint = '''
@app.route("/webhook/crawl-fb", methods=["POST"])
def webhook_crawl_fb():
    """Native Python Webhook Endpoint thay thế hoàn toàn n8n Webhook Studio."""
    try:
        data = request.json or {}
        post_url = data.get("post_url") or data.get("permalink_url") or ""
        post_title = data.get("post_title") or data.get("message") or ""
        comments = data.get("comments") or []
        raw_content = data.get("raw_content") or ""

        if not post_url and not comments:
            return jsonify({"success": False, "error": "Thiếu post_url hoặc danh sách bình luận"}), 400

        add_log("START", f"=== [Native Webhook] Nhận dữ liệu crawl: {post_url or 'Ad-hoc Payload'} ===")
        from adhoc_collector import process_adhoc_post
        result = process_adhoc_post(post_url, raw_content=raw_content, raw_comments=comments)

        hot_leads = [l for l in result.get("leads", []) if l.get("tier") == "HOT" or (l.get("score") and l.get("score") >= 60)]
        if hot_leads:
            add_log("INFO", f"[Native Webhook] Phát hiện {len(hot_leads)} Lead HOT! Kích hoạt Telegram alert...")
            def async_notify():
                try:
                    from notification.notification_runner import run_notification_cycle
                    n_res = run_notification_cycle(20)
                    add_log("SUCCESS", f"[Native Webhook] Đã dispatch Telegram: {n_res.get('dispatched', 0)} lead.")
                except Exception as n_err:
                    add_log("WARN", f"[Native Webhook] Dispatcher: {str(n_err)}")
            threading.Thread(target=async_notify, daemon=True).start()

        return jsonify({
            "status": "SUCCESS",
            "engine": "Pure Python Native V1",
            "post_id": result.get("post_id"),
            "total_crawled": result.get("total_analyzed", 0),
            "leads_found": result.get("leads_found", 0),
            "hot_leads": len(hot_leads),
            "data": result
        })
    except Exception as e:
        add_log("ERROR", f"[Native Webhook] Lỗi xử lý: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

'''

# 3. Thay thế đoạn gửi n8n webhook trong api_adhoc_crawl
old_adhoc_dispatch = r'# Tự động dispatch sang n8n Webhook.*?add_log\("WARN", f"Thông báo n8n Webhook: {str\(n_err\)}"\)'
new_adhoc_dispatch = '''# Tự động kích hoạt cảnh báo Telegram cho Sales nếu có Hot Lead (Chạy bằng code thuần)
        hot_leads = [l for l in result.get("leads", []) if l.get("tier") == "HOT" or (l.get("score") and l.get("score") >= 60)]
        if hot_leads:
            add_log("INFO", f"Phát hiện {len(hot_leads)} Lead HOT! Đang kích hoạt thông báo Telegram tự động...")
            def async_notify():
                try:
                    from notification.notification_runner import run_notification_cycle
                    n_res = run_notification_cycle(20)
                    add_log("SUCCESS", f"Đã gửi cảnh báo Sales Telegram: {n_res.get('dispatched', 0)} lead mới.")
                except Exception as n_err:
                    add_log("WARN", f"Thông báo Dispatcher: {str(n_err)}")
            threading.Thread(target=async_notify, daemon=True).start()'''

code = re.sub(old_adhoc_dispatch, new_adhoc_dispatch, code, flags=re.DOTALL)

# Chèn webhook_endpoint trước api_get_agent_report
if "/webhook/crawl-fb" not in code:
    code = code.replace('@app.route("/api/agent/report/<post_id>"', webhook_endpoint + '@app.route("/api/agent/report/<post_id>"')

with open(app_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Đã cập nhật app.py sang 100% code thuần thành công!")
