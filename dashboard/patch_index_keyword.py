import re

html_path = "/home/ADMIN/dashboard/templates/index.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Add Knowledge Base modal button in nav actions
if 'id="kb-btn"' not in html:
    kb_btn = '''
      <button class="btn btn-secondary" onclick="openKnowledgeModal()" id="kb-btn" style="border-color: rgba(99, 102, 241, 0.4); background: rgba(99, 102, 241, 0.1); color: #818cf8;">
        📚 DB Kịch Bản Sale
      </button>'''
    html = html.replace('<button class="btn btn-secondary" onclick="exportLeads(\'all\')">', kb_btn + '\n      <button class="btn btn-secondary" onclick="exportLeads(\'all\')">')

# 2. Add Tab Switcher in crawl-box-header
old_header = r'<div class="crawl-box-header">.*?</div>\s*</div>'
new_header = '''<div class="crawl-box-header">
        <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
          <h2>BỘ THU THẬP & BÓC TÁCH KHÁCH HÀNG TIỀM NĂNG</h2>
          <div class="tab-switcher" style="display:flex; gap:6px; background:rgba(255,255,255,0.06); padding:3px; border-radius:8px;">
            <button type="button" class="chip active" id="tab-keyword" onclick="switchCrawlTab('keyword')" style="padding:4px 12px; font-size:12px;">
              🔍 Quét Theo Từ Khóa (Key)
            </button>
            <button type="button" class="chip" id="tab-link" onclick="switchCrawlTab('link')" style="padding:4px 12px; font-size:12px;">
              🔗 Dán Link Bài Viết
            </button>
          </div>
        </div>

        <div class="quick-pill" onclick="fillKeywordDemo('enjicad')">
          ✨ Từ Khóa Mẫu: enjicad
        </div>
      </div>'''

html = re.sub(old_header, new_header, html, flags=re.DOTALL)

# 3. Add Keyword Crawl Form & Link Crawl Form
old_form = r'<form class="crawl-form" onsubmit="executeCrawl\(event\)">.*?</form>'
new_form = '''<!-- Form Quét Theo Từ Khóa (Mặc định) -->
      <form class="crawl-form" id="keyword-crawl-form" onsubmit="executeKeywordCrawl(event)">
        <div class="input-wrapper" style="flex:2;">
          <span class="input-icon">🔑</span>
          <input 
            type="text" 
            id="keyword-input" 
            class="crawl-input" 
            placeholder="Nhập cụm từ khóa (VD: enjicad, bản quyền cad, autocad...)..."
            required
            value="enjicad"
          >
        </div>
        <div style="display:flex; align-items:center; gap:8px; background:rgba(255,255,255,0.04); border:1px solid var(--border-color); border-radius:8px; padding:0 12px;">
          <span style="font-size:12px; color:var(--text-muted);">Số bài hot:</span>
          <select id="max-posts-select" style="background:transparent; border:none; color:#fff; font-size:13px; outline:none; cursor:pointer;">
            <option value="1" style="background:#1e293b;">1 Bài hot nhất</option>
            <option value="2" selected style="background:#1e293b;">Top 2 Bài hot</option>
            <option value="3" style="background:#1e293b;">Top 3 Bài hot</option>
          </select>
        </div>
        <button type="submit" id="keyword-submit-btn" class="crawl-btn">
          <span>🔥 TÌM BÀI VIẾT HOT NHẤT & QWEN AGENT BÓC TÁCH</span>
        </button>
      </form>

      <!-- Form Quét Theo Link Cụ Thể (Ẩn ban đầu) -->
      <form class="crawl-form" id="link-crawl-form" onsubmit="executeCrawl(event)" style="display:none;">
        <div class="input-wrapper">
          <span class="input-icon">🔗</span>
          <input 
            type="url" 
            id="post-url-input" 
            class="crawl-input" 
            placeholder="Dán đường link bài viết Facebook (VD: https://www.facebook.com/share/p/1QhxSWmYdP/)..."
            value="https://www.facebook.com/share/p/1QhxSWmYdP/"
          >
        </div>
        <button type="submit" id="crawl-submit-btn" class="crawl-btn">
          <span>🚀 BẮT ĐẦU QUÉT THEO LINK & PHÂN TÍCH AI</span>
        </button>
      </form>'''

html = re.sub(old_form, new_form, html, flags=re.DOTALL)

# 4. Add Knowledge Base Modal HTML before </body>
kb_modal = '''
  <!-- Modal Quản Lý Cơ Sở Dữ Liệu Sản Phẩm & Lời Thoại Sale -->
  <div id="kb-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.75); z-index:9999; justify-content:center; align-items:center; padding:20px;">
    <div style="background:#0f172a; border:1px solid #334155; border-radius:14px; width:100%; max-width:850px; max-height:90vh; overflow-y:auto; padding:24px; box-shadow:0 20px 40px rgba(0,0,0,0.6);">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1e293b; padding-bottom:14px; margin-bottom:18px;">
        <div style="display:flex; align-items:center; gap:10px;">
          <span style="font-size:24px;">📚</span>
          <div>
            <h3 style="margin:0; font-size:18px; color:#fff;">Cơ Sở Dữ Liệu Sản Phẩm & Lời Thoại Thuyết Phục Khách</h3>
            <p style="margin:0; font-size:12px; color:var(--text-muted);">Thông tin trong Database Supabase mà Qwen Agent sẽ dựa vào để gợi ý lời thoại</p>
          </div>
        </div>
        <button onclick="closeKnowledgeModal()" style="background:transparent; border:none; color:#94a3b8; font-size:22px; cursor:pointer;">✕</button>
      </div>

      <div id="kb-content-loading" style="text-align:center; padding:30px; color:var(--text-muted);">
        <div class="spinner" style="margin:0 auto 10px;"></div>
        Đang tải dữ liệu từ Supabase (public.product_knowledge_base)...
      </div>

      <div id="kb-content" style="display:none;">
        <div id="kb-products-list"></div>
      </div>
    </div>
  </div>
'''

if 'id="kb-modal"' not in html:
    html = html.replace('</body>', kb_modal + '\n</body>')

# 5. Add JavaScript functions for keyword crawl & knowledge base
js_additions = '''
    let CURRENT_CRAWL_TAB = 'keyword';

    function switchCrawlTab(tab) {
      CURRENT_CRAWL_TAB = tab;
      const tabKw = document.getElementById("tab-keyword");
      const tabLink = document.getElementById("tab-link");
      const formKw = document.getElementById("keyword-crawl-form");
      const formLink = document.getElementById("link-crawl-form");

      if (tab === 'keyword') {
        tabKw.classList.add("active");
        tabLink.classList.remove("active");
        formKw.style.display = "flex";
        formLink.style.display = "none";
      } else {
        tabKw.classList.remove("active");
        tabLink.classList.add("active");
        formKw.style.display = "none";
        formLink.style.display = "flex";
      }
    }

    function fillKeywordDemo(kw) {
      switchCrawlTab('keyword');
      document.getElementById("keyword-input").value = kw;
    }

    async function executeKeywordCrawl(e) {
      e.preventDefault();
      const kw = document.getElementById("keyword-input").value.trim();
      const maxPosts = document.getElementById("max-posts-select").value;
      if (!kw) return;

      const submitBtn = document.getElementById("keyword-submit-btn");
      const progress = document.getElementById("crawl-progress");
      const step1 = document.getElementById("step-1");
      const step2 = document.getElementById("step-2");
      const step3 = document.getElementById("step-3");

      submitBtn.disabled = true;
      submitBtn.innerHTML = `<div class="spinner"></div><span>ĐANG TÌM BÀI VIẾT HOT & QWEN AGENT PHÂN TÍCH...</span>`;
      progress.style.display = "block";

      step1.className = "step-item active";
      step1.innerHTML = `<div class="spinner"></div><span>1. Đang tìm bài viết có tương tác cao nhất cho từ khóa: "${kw}"...</span>`;
      step2.className = "step-item";
      step3.className = "step-item";

      setTimeout(() => {
        step1.className = "step-item done";
        step2.className = "step-item active";
        step2.innerHTML = `<div class="spinner"></div><span>2. Agent Qwen3-VL-30B bóc tách khách hàng & lọc SĐT ẩn...</span>`;
      }, 3500);

      setTimeout(() => {
        step2.className = "step-item done";
        step3.className = "step-item active";
        step3.innerHTML = `<div class="spinner"></div><span>3. Đối chiếu Database Knowledge Base & sinh kịch bản chốt khách...</span>`;
      }, 7500);

      try {
        const res = await fetch("/api/keyword/crawl", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keyword: kw, max_posts: maxPosts })
        });
        const json = await res.json();

        if (json.success) {
          step3.className = "step-item done";
          showToast(`Tìm thấy ${json.total_leads_identified} khách hàng tiềm năng (${json.hot_leads_count} HOT) cho từ khóa "${kw}"!`, "🔥");
          await fetchStats();
          await fetchLeads();
        } else {
          showToast(`Lỗi: ${json.error || "Không thể cào dữ liệu"}`, "⚠️");
        }
      } catch (err) {
        showToast(`Lỗi kết nối: ${err.message}`, "❌");
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>🔥 TÌM BÀI VIẾT HOT NHẤT & QWEN AGENT BÓC TÁCH</span>`;
        setTimeout(() => { progress.style.display = "none"; }, 4000);
      }
    }

    async function openKnowledgeModal() {
      const modal = document.getElementById("kb-modal");
      modal.style.display = "flex";
      const loading = document.getElementById("kb-content-loading");
      const content = document.getElementById("kb-content");
      const list = document.getElementById("kb-products-list");

      loading.style.display = "block";
      content.style.display = "none";

      try {
        const res = await fetch("/api/knowledge");
        const json = await res.json();
        loading.style.display = "none";
        content.style.display = "block";

        if (json.success && json.data && json.data.length > 0) {
          list.innerHTML = json.data.map(p => {
            const usps = (p.key_usps || []).map(u => `<li>${u}</li>`).join("");
            const pricing = p.pricing_details || {};
            const pricingHtml = Object.entries(pricing).map(([k, v]) => `<div><strong>${k}:</strong> ${v}</div>`).join("");
            const objections = p.objection_scripts || {};
            const objHtml = Object.entries(objections).map(([k, o]) => `
              <div style="background:#1e293b; padding:10px; border-radius:6px; margin-top:8px;">
                <div style="color:#fbbf24; font-weight:600; font-size:12px;">Khúc mắc: ${o.concern || k}</div>
                <div style="color:#34d399; font-size:12px; margin-top:4px;">✨ Giải pháp DB: ${o.selling_point || '-'}</div>
                <div style="color:#94a3b8; font-size:11px; margin-top:2px;">👉 Hành động: ${o.action || '-'}</div>
              </div>
            `).join("");

            return `
              <div style="background:rgba(255,255,255,0.03); border:1px solid #334155; border-radius:10px; padding:18px; margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <h4 style="margin:0; color:#38bdf8; font-size:16px;">${p.product_name}</h4>
                  <span class="badge-tag" style="background:rgba(99,102,241,0.2); color:#818cf8;">Key: ${p.product_key}</span>
                </div>
                <p style="font-size:12px; color:var(--text-muted); margin:4px 0 12px;">Đơn vị: ${p.vendor || '-'}</p>
                
                <div style="margin-bottom:12px;">
                  <span style="font-size:12px; font-weight:600; color:#fff;">Ưu điểm vượt trội (USPs):</span>
                  <ul style="margin:6px 0 0 18px; font-size:12.5px; color:#cbd5e1; line-height:1.6;">${usps}</ul>
                </div>

                <div style="margin-bottom:12px;">
                  <span style="font-size:12px; font-weight:600; color:#fff;">Chính sách giá trong DB:</span>
                  <div style="font-size:12px; color:#94a3b8; margin-top:4px; line-height:1.6;">${pricingHtml}</div>
                </div>

                <div>
                  <span style="font-size:12px; font-weight:600; color:#fff;">Kịch bản gỡ rối / đập tan từ chối (Objection Scripts):</span>
                  <div>${objHtml}</div>
                </div>
              </div>
            `;
          }).join("");
        } else {
          list.innerHTML = `<p style="color:var(--text-muted);">Chưa có sản phẩm nào trong cơ sở dữ liệu.</p>`;
        }
      } catch (err) {
        loading.innerHTML = `<p style="color:#f87171;">Lỗi tải dữ liệu: ${err.message}</p>`;
      }
    }

    function closeKnowledgeModal() {
      document.getElementById("kb-modal").style.display = "none";
    }
'''

if 'executeKeywordCrawl' not in html:
    html = html.replace('function exportLeads(scope', js_additions + '\n    function exportLeads(scope')

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Đã cập nhật giao diện index.html với tính năng Quét theo Từ Khóa & Knowledge Base thành công!")
