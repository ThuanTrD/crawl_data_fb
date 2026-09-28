with open('/home/ADMIN/dashboard/templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update hero card to have switcher and default link form visible
old_hero = '''      <!-- Form Quét Theo Từ Khóa (Mặc định) -->
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

new_hero = '''      <div style="display:flex; gap:12px; align-items:center; margin-bottom:16px; flex-wrap:wrap;">
        <div style="display:flex; background:rgba(255,255,255,0.06); padding:4px; border-radius:12px; border:1px solid var(--border-subtle);">
          <button id="btn-mode-link" type="button" onclick="switchCrawlMode('link')" style="padding:8px 18px; border-radius:8px; border:none; font-size:13px; font-weight:700; cursor:pointer; background:var(--accent-indigo); color:#fff; transition:all 0.2s; display:flex; align-items:center; gap:6px;">
            <span>🔗</span> Dán Link Bài Viết Test
          </button>
          <button id="btn-mode-keyword" type="button" onclick="switchCrawlMode('keyword')" style="padding:8px 18px; border-radius:8px; border:none; font-size:13px; font-weight:600; cursor:pointer; background:transparent; color:var(--text-muted); transition:all 0.2s; display:flex; align-items:center; gap:6px;">
            <span>🔑</span> Quét Theo Từ Khóa Sản Phẩm CIC
          </button>
        </div>
      </div>

      <!-- Form Quét Theo Link Cụ Thể (Mặc định hiển thị để test link) -->
      <form class="crawl-form" id="link-crawl-form" onsubmit="executeCrawl(event)">
        <div class="input-wrapper" style="flex:2;">
          <span class="input-icon">🔗</span>
          <input 
            type="url" 
            id="post-url-input" 
            class="crawl-input" 
            placeholder="Dán đường link bài viết Facebook (VD: https://www.facebook.com/share/p/1QhxSWmYdP/)..."
            required
            value="https://www.facebook.com/share/p/1QhxSWmYdP/"
          >
        </div>
        <button type="submit" id="crawl-submit-btn" class="crawl-btn">
          <span>🚀 BẮT ĐẦU CÀO BÀI VIẾT & SINH KỊCH BẢN AI</span>
        </button>
      </form>

      <!-- Form Quét Theo Từ Khóa (Ẩn ban đầu) -->
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

if old_hero in html:
    html = html.replace(old_hero, new_hero)
    print('Hero replaced successfully')
else:
    print('Hero pattern NOT matched directly')

js_inject = '''
    function switchCrawlMode(mode) {
      const linkForm = document.getElementById("link-crawl-form");
      const kwForm = document.getElementById("keyword-crawl-form");
      const btnLink = document.getElementById("btn-mode-link");
      const btnKw = document.getElementById("btn-mode-keyword");

      if (mode === "link") {
        linkForm.style.display = "flex";
        kwForm.style.display = "none";
        btnLink.style.background = "var(--accent-indigo)";
        btnLink.style.color = "#fff";
        btnLink.style.fontWeight = "700";
        btnKw.style.background = "transparent";
        btnKw.style.color = "var(--text-muted)";
        btnKw.style.fontWeight = "600";
      } else {
        linkForm.style.display = "none";
        kwForm.style.display = "flex";
        btnKw.style.background = "var(--accent-indigo)";
        btnKw.style.color = "#fff";
        btnKw.style.fontWeight = "700";
        btnLink.style.background = "transparent";
        btnLink.style.color = "var(--text-muted)";
        btnLink.style.fontWeight = "600";
      }
    }

    async function executeKeywordCrawl(e) {
      if (e) e.preventDefault();
      const kwInput = document.getElementById("keyword-input");
      const kw = kwInput.value.trim();
      const maxPosts = parseInt(document.getElementById("max-posts-select").value) || 1;

      if (!kw) {
        showToast("Vui lòng nhập từ khóa tìm kiếm (Ví dụ: enjicad, etabs, plaxis)", "⚠️");
        return;
      }

      const submitBtn = document.getElementById("keyword-submit-btn");
      const progress = document.getElementById("crawl-progress");
      const step1 = document.getElementById("step-1");
      const step2 = document.getElementById("step-2");
      const step3 = document.getElementById("step-3");

      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span>⏳ Đang tìm kiếm & cào bài viết...</span>`;
      progress.style.display = "block";

      step1.className = "step-item active";
      step2.className = "step-item";
      step3.className = "step-item";

      setTimeout(() => {
        step1.className = "step-item done";
        step2.className = "step-item active";
        step2.innerHTML = `<div class="spinner"></div><span>2. Qwen Agent bóc tách bình luận & đối soát 276 sản phẩm CIC...</span>`;
      }, 3000);

      setTimeout(() => {
        step2.className = "step-item done";
        step3.className = "step-item active";
        step3.innerHTML = `<div class="spinner"></div><span>3. Sinh kịch bản chốt đơn & đồng bộ Supabase...</span>`;
      }, 7000);

      try {
        const res = await fetch("/api/keyword/crawl", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keyword: kw, max_posts: maxPosts })
        });
        const json = await res.json();

        if (json.success) {
          step3.className = "step-item done";
          step3.innerHTML = `<span>✅ Hoàn tất quét theo từ khóa!</span>`;
          showToast(`Thành công! Sản phẩm: ${json.product_knowledge_used || kw}. Tìm thấy ${json.total_leads_identified} khách hàng (${json.hot_leads_count} HOT)!`, "🎉");
          setTimeout(() => { progress.style.display = "none"; }, 2500);
          await refreshDashboard();
        } else {
          showToast(`Lỗi: ${json.error}`, "❌");
          progress.style.display = "none";
        }
      } catch (err) {
        showToast(`Lỗi mạng khi quét: ${err.message}`, "❌");
        progress.style.display = "none";
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>🔥 TÌM BÀI VIẾT HOT NHẤT & QWEN AGENT BÓC TÁCH</span>`;
      }
    }
'''

if 'function fillDemoPost()' in html:
    html = html.replace('function fillDemoPost() {', js_inject + '\n    function fillDemoPost() {\n      switchCrawlMode("link");')
    print('JS injected successfully')
else:
    print('fillDemoPost NOT found')

with open('/home/ADMIN/dashboard/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Updated index.html saved successfully')
