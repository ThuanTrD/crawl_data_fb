import re

html_path = "/home/ADMIN/dashboard/templates/index.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update top bar badge
old_nav_btn = r'<a id="n8n-studio-btn".*?</a>'
new_nav_badge = '''<div id="native-engine-badge" class="status-badge" style="border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.1); color: #34d399;">
        <span class="dot" style="background:#10b981; box-shadow:0 0 8px #10b981;"></span>
        <span>⚡ Native Python Engine: ACTIVE</span>
      </div>'''
html = re.sub(old_nav_btn, new_nav_badge, html, flags=re.DOTALL)

# 2. Update step 3 in modal
html = html.replace(
    "<span>3. Sinh kịch bản Messenger & Đồng bộ n8n Studio...</span>",
    "<span>3. Sinh kịch bản Messenger & Phân tích AI Thuần...</span>"
)
html = html.replace(
    "`<div class=\"spinner\"></div><span>3. Sinh kịch bản Messenger & Đồng bộ n8n Studio...</span>`",
    "`<div class=\"spinner\"></div><span>3. Sinh kịch bản Messenger & Phân tích AI Thuần...</span>`"
)

# 3. Update accordion section
html = html.replace(
    "<h3>⚙️ Trung Tâm Tự Động Hóa n8n Studio & Giám Sát Hệ Thống</h3>",
    "<h3>⚡ Động Cơ Tự Động Hóa Code Thuần (Pure Python Pipeline Engine)</h3>"
)
html = html.replace(
    "Tất cả 8 vi dịch vụ tự động hóa n8n đang hoạt động đồng bộ với Supabase Postgres và Web CRM.",
    "Hệ thống vận hành 100% bằng Code thuần Python 3.14, kết nối trực tiếp Supabase Postgres và Telegram Alert không qua trung gian n8n/Docker."
)

old_canvas_btn = r'<a href="https://receive-require-height-kick\.trycloudflare\.com".*?🔗 Mở Trực Tiếp Canvas n8n Studio ↗\s*</a>'
new_canvas_btn = '''<span class="badge-tag" style="background:rgba(16,185,129,0.2); color:#34d399; font-weight:600; padding:6px 12px; font-size:12px; border-radius:6px;">
            ✅ Pure Python V1 (Zero-Overhead)
          </span>'''
html = re.sub(old_canvas_btn, new_canvas_btn, html, flags=re.DOTALL)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Đã cập nhật giao diện index.html sang Pure Code thành công!")
