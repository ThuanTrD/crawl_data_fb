with open('/home/ADMIN/dashboard/templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add CSS for .limit-chip
css_target = ".crawl-btn:hover {"
css_addition = """    .limit-chip {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.12);
      color: #94a3b8;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .limit-chip:hover {
      background: rgba(99, 102, 241, 0.2);
      color: #fff;
      border-color: rgba(99, 102, 241, 0.4);
    }
    .limit-chip.active {
      background: var(--accent-indigo) !important;
      color: #fff !important;
      border-color: var(--accent-indigo) !important;
      box-shadow: 0 0 10px var(--accent-indigo-glow);
    }
"""

if ".limit-chip {" not in html and css_target in html:
    html = html.replace(css_target, css_addition + "\n    " + css_target)
    print("Added .limit-chip CSS")

# 2. Replace keyword-crawl-form
old_form = '''      <!-- Form Quét Theo Từ Khóa (Ẩn ban đầu) -->
      <form class="crawl-form" id="keyword-crawl-form" onsubmit="executeKeywordCrawl(event)" style="display:none;">
        <div class="input-wrapper" style="flex:2;">
          <span class="input-icon">🔑</span>
          <input 
            type="text" 
            id="keyword-input" 
            class="crawl-input" 
            placeholder="Nhập từ khóa sản phẩm CIC (VD: enjicad, etabs, plaxis, sap2000, robot...)..."
            value="enjicad"
          >
        </div>
        <div style="display:flex; align-items:center; gap:8px; background:rgba(255,255,255,0.04); border:1px solid var(--border-color); border-radius:8px; padding:0 12px;">
          <span style="font-size:12px; color:var(--text-muted);">Số bài hot:</span>
          <select id="max-posts-select" style="background:transparent; border:none; color:#fff; font-size:13px; outline:none; cursor:pointer;">
            <option value="1" selected style="background:#1e293b;">1 Bài hot nhất</option>
            <option value="2" style="background:#1e293b;">Top 2 Bài hot</option>
            <option value="3" style="background:#1e293b;">Top 3 Bài hot</option>
          </select>
        </div>
        <button type="submit" id="keyword-submit-btn" class="crawl-btn">
          <span>🔥 TÌM BÀI VIẾT HOT NHẤT & QWEN AGENT BÓC TÁCH</span>
        </button>
      </form>'''

new_form = '''      <!-- Form Quét Theo Từ Khóa -->
      <form class="crawl-form" id="keyword-crawl-form" onsubmit="executeKeywordCrawl(event)" style="display:none; flex-direction:column; gap:12px;">
        <div style="display:flex; gap:12px; width:100%; align-items:stretch; flex-wrap:wrap;">
          <div class="input-wrapper" style="flex:2; min-width:280px;">
            <span class="input-icon">🔑</span>
            <input 
              type="text" 
              id="keyword-input" 
              class="crawl-input" 
              placeholder="Nhập từ khóa sản phẩm CIC (VD: enjicad, etabs, plaxis, sap2000, robot, intellicad...)..."
              value="enjicad"
              required
            >
          </div>
          <button type="submit" id="keyword-submit-btn" class="crawl-btn" style="white-space:nowrap; padding:12px 24px;">
            <span>🔥 TÌM BÀI HOT & CÀO KHÁCH HÀNG</span>
          </button>
        </div>

        <!-- Bộ chọn số lượng bài hot tùy ý do người dùng nhập hoặc chọn nhanh -->
        <div style="display:flex; align-items:center; gap:12px; background:rgba(255,255,255,0.03); border:1px solid var(--border-subtle); border-radius:10px; padding:10px 16px; flex-wrap:wrap;">
          <span style="font-size:13px; font-weight:600; color:#cbd5e1; display:flex; align-items:center; gap:6px;">
            <span>📊</span> Số lượng bài viết hot bạn muốn cào:
          </span>

          <div style="display:flex; align-items:center; gap:6px;">
            <input 
              type="number" 
              id="max-posts-input" 
              min="1" 
              max="100" 
              value="5" 
              oninput="syncChipsWithInput(this.value)"
              style="width:75px; background:rgba(15,23,42,0.85); border:1px solid var(--border-focus); border-radius:8px; color:#38bdf8; padding:6px 10px; font-size:14px; font-weight:700; text-align:center; outline:none;"
              title="Nhập số lượng bài viết tùy ý (ví dụ: 5, 10, 15, 20...)"
            >
            <span style="font-size:13px; color:var(--text-muted); font-weight:500;">bài</span>
          </div>

          <div style="display:flex; gap:6px; align-items:center; margin-left:auto; flex-wrap:wrap;">
            <span style="font-size:12px; color:var(--text-muted); margin-right:4px;">Chọn nhanh:</span>
            <button type="button" onclick="setPostLimit(1)" class="limit-chip">1</button>
            <button type="button" onclick="setPostLimit(3)" class="limit-chip">3</button>
            <button type="button" onclick="setPostLimit(5)" class="limit-chip active">5</button>
            <button type="button" onclick="setPostLimit(10)" class="limit-chip">10</button>
            <button type="button" onclick="setPostLimit(20)" class="limit-chip">20</button>
            <button type="button" onclick="setPostLimit(50)" class="limit-chip">50</button>
          </div>
        </div>
      </form>'''

if old_form in html:
    html = html.replace(old_form, new_form)
    print("Replaced keyword-crawl-form with custom number selector")
else:
    print("Old form pattern not matched directly")

# 3. Update JavaScript helpers
js_target = "async function executeKeywordCrawl(e) {"
js_addition = """    function setPostLimit(n) {
      const inp = document.getElementById("max-posts-input");
      if (inp) inp.value = n;
      document.querySelectorAll(".limit-chip").forEach(btn => {
        btn.classList.toggle("active", parseInt(btn.textContent.trim()) === n);
      });
    }

    function syncChipsWithInput(val) {
      const num = parseInt(val);
      document.querySelectorAll(".limit-chip").forEach(btn => {
        btn.classList.toggle("active", parseInt(btn.textContent.trim()) === num);
      });
    }

"""

if "function setPostLimit" not in html and js_target in html:
    html = html.replace(js_target, js_addition + js_target)
    print("Added JS helpers setPostLimit and syncChipsWithInput")

# Update executeKeywordCrawl to read from max-posts-input
html = html.replace(
    'const maxPosts = parseInt(document.getElementById("max-posts-select").value) || 1;',
    'const inp = document.getElementById("max-posts-input");\n      const maxPosts = inp ? (parseInt(inp.value) || 5) : 5;'
)

with open('/home/ADMIN/dashboard/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated index.html successfully")
