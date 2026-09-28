with open('/home/ADMIN/dashboard/templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update Switcher
old_switcher = '''      <div style="display:flex; gap:12px; align-items:center; margin-bottom:16px; flex-wrap:wrap;">
        <div style="display:flex; background:rgba(255,255,255,0.06); padding:4px; border-radius:12px; border:1px solid var(--border-subtle);">
          <button id="btn-mode-link" type="button" onclick="switchCrawlMode('link')" style="padding:8px 18px; border-radius:8px; border:none; font-size:13px; font-weight:700; cursor:pointer; background:var(--accent-indigo); color:#fff; transition:all 0.2s; display:flex; align-items:center; gap:6px;">
            <span>🔗</span> Dán Link Bài Viết Test
          </button>
          <button id="btn-mode-keyword" type="button" onclick="switchCrawlMode('keyword')" style="padding:8px 18px; border-radius:8px; border:none; font-size:13px; font-weight:600; cursor:pointer; background:transparent; color:var(--text-muted); transition:all 0.2s; display:flex; align-items:center; gap:6px;">
            <span>🔑</span> Quét Theo Từ Khóa Sản Phẩm CIC
          </button>
        </div>
      </div>'''

new_switcher = '''      <div style="display:flex; gap:12px; align-items:center; margin-bottom:16px; flex-wrap:wrap;">
        <div style="display:flex; background:rgba(255,255,255,0.06); padding:4px; border-radius:12px; border:1px solid var(--border-subtle); flex-wrap:wrap; gap:4px;">
          <button id="btn-mode-link" type="button" onclick="switchCrawlMode('link')" style="padding:8px 16px; border-radius:8px; border:none; font-size:13px; font-weight:600; cursor:pointer; background:transparent; color:var(--text-muted); transition:all 0.2s; display:flex; align-items:center; gap:6px;">
            <span>🔗</span> Dán Link Bài Viết Test
          </button>
          <button id="btn-mode-keyword" type="button" onclick="switchCrawlMode('keyword')" style="padding:8px 16px; border-radius:8px; border:none; font-size:13px; font-weight:600; cursor:pointer; background:transparent; color:var(--text-muted); transition:all 0.2s; display:flex; align-items:center; gap:6px;">
            <span>⚡</span> Cào Tự Động Theo Key
          </button>
          <button id="btn-mode-selective" type="button" onclick="switchCrawlMode('selective')" style="padding:8px 16px; border-radius:8px; border:none; font-size:13px; font-weight:700; cursor:pointer; background:var(--accent-indigo); color:#fff; transition:all 0.2s; display:flex; align-items:center; gap:6px; box-shadow:0 0 12px var(--accent-indigo-glow);">
            <span>🎯</span> 2 Giai Đoạn: Tìm Bài Hot & Tích Chọn Cào
          </button>
        </div>
      </div>'''

if old_switcher in html:
    html = html.replace(old_switcher, new_switcher)
    print("Replaced switcher with 3 tabs")
else:
    print("Old switcher pattern not matched")

# 2. Add selective-crawl-container after keyword-crawl-form
target_after_form = '</form>\n\n      <!-- Progress Banner -->'
if target_after_form not in html:
    target_after_form = '</form>\n      <!-- Progress Banner -->'

selective_container_html = '''</form>

      <!-- Tab 3: Cào 2 Giai Đoạn (Giai đoạn 1: Tìm bài hot -> Giai đoạn 2: Tích chọn bài cần cào) -->
      <div id="selective-crawl-container" style="display:flex; flex-direction:column; gap:16px;">
        <!-- Giai đoạn 1: Form tìm bài hot -->
        <form class="crawl-form" id="selective-search-form" onsubmit="executeSelectiveSearch(event)" style="display:flex; gap:12px; width:100%; align-items:stretch; flex-wrap:wrap;">
          <div class="input-wrapper" style="flex:2; min-width:260px;">
            <span class="input-icon">🔑</span>
            <input 
              type="text" 
              id="selective-keyword-input" 
              class="crawl-input" 
              placeholder="Nhập từ khóa cần tìm bài viết (VD: enjicad, etabs, plaxis, sap2000, robot, intellicad...)..."
              value="enjicad"
              required
            >
          </div>
          <div style="display:flex; align-items:center; gap:8px; background:rgba(255,255,255,0.04); border:1px solid var(--border-subtle); border-radius:10px; padding:0 12px;">
            <span style="font-size:12px; color:var(--text-muted); white-space:nowrap;">Quét tìm:</span>
            <input 
              type="number" 
              id="selective-limit-input" 
              min="1" 
              max="50" 
              value="10" 
              style="width:50px; background:transparent; border:none; color:#38bdf8; font-size:13px; font-weight:700; text-align:center; outline:none;"
            >
            <span style="font-size:12px; color:var(--text-muted);">bài</span>
          </div>
          <button type="submit" id="selective-search-btn" class="crawl-btn" style="white-space:nowrap; padding:12px 24px;">
            <span>🔎 GIAI ĐOẠN 1: TÌM BÀI VIẾT NỔI BẬT</span>
          </button>
        </form>

        <!-- Giai đoạn 2: Danh sách bài viết & Tích chọn cào -->
        <div id="selective-results-box" style="display:none; background:rgba(15,23,42,0.7); border:1px solid rgba(99,102,241,0.3); border-radius:12px; padding:18px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; flex-wrap:wrap; gap:12px;">
            <div>
              <h3 style="font-size:15px; font-weight:700; color:#fff; display:flex; align-items:center; gap:8px;">
                <span>📋</span> Danh Sách Bài Viết Đã Tìm Thấy (<span id="selective-found-count" style="color:#38bdf8;">0</span> bài)
              </h3>
              <p style="font-size:12px; color:var(--text-muted); margin-top:2px;">
                Tích chọn những bài viết bạn thấy tiềm năng để AI tiến hành cào bình luận và bóc tách khách hàng:
              </p>
            </div>

            <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
              <button type="button" onclick="toggleSelectAllPosts()" class="btn btn-secondary" style="padding:7px 14px; font-size:12px; background:rgba(255,255,255,0.06);">
                ☑️ Chọn / Bỏ chọn tất cả
              </button>
              <button type="button" id="selective-crawl-btn" onclick="executeSelectiveCrawl()" class="btn" style="background:linear-gradient(135deg,#10b981,#059669); color:#fff; padding:8px 20px; font-weight:700; border:none; box-shadow:0 0 16px rgba(16,185,129,0.35); display:flex; align-items:center; gap:8px; cursor:pointer;" disabled>
                <span>🚀</span> GIAI ĐOẠN 2: CÀO BÀI ĐÃ CHỌN (<span id="selected-posts-badge">0</span>)
              </button>
            </div>
          </div>

          <!-- Bảng danh sách bài viết -->
          <div style="overflow-x:auto; max-height:420px; overflow-y:auto; border-radius:8px; border:1px solid rgba(255,255,255,0.08);">
            <table style="width:100%; border-collapse:collapse; font-size:13px; text-align:left;">
              <thead style="background:rgba(30,41,59,0.95); position:sticky; top:0; z-index:2;">
                <tr style="border-bottom:1px solid rgba(255,255,255,0.1); color:var(--text-muted);">
                  <th style="padding:10px 12px; width:45px; text-align:center;">
                    <input type="checkbox" id="select-all-cb" onchange="handleSelectAllChange(this.checked)" style="cursor:pointer; width:16px; height:16px;">
                  </th>
                  <th style="padding:10px 12px; min-width:320px;">Tiêu Đề / Nội Dung Bài Viết</th>
                  <th style="padding:10px 12px; min-width:180px;">Nguồn / Trang</th>
                  <th style="padding:10px 12px; text-align:center; min-width:160px;">Tương Tác</th>
                  <th style="padding:10px 12px; text-align:center; width:90px;">Xem Bài</th>
                </tr>
              </thead>
              <tbody id="selective-posts-tbody">
                <!-- Dynamic rows rendered here -->
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Progress Banner -->'''

if target_after_form in html:
    html = html.replace(target_after_form, selective_container_html, 1)
    print("Added selective-crawl-container")
else:
    print("target_after_form pattern not matched")

# 3. Update switchCrawlMode and add JavaScript functions
old_switch_func = '''    function switchCrawlMode(mode) {
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
    }'''

new_switch_func = '''    let CURRENT_SELECTIVE_POSTS = [];

    function switchCrawlMode(mode) {
      const linkForm = document.getElementById("link-crawl-form");
      const kwForm = document.getElementById("keyword-crawl-form");
      const selContainer = document.getElementById("selective-crawl-container");

      const btnLink = document.getElementById("btn-mode-link");
      const btnKw = document.getElementById("btn-mode-keyword");
      const btnSel = document.getElementById("btn-mode-selective");

      // Reset active states
      [btnLink, btnKw, btnSel].forEach(b => {
        if (b) {
          b.style.background = "transparent";
          b.style.color = "var(--text-muted)";
          b.style.fontWeight = "600";
          b.style.boxShadow = "none";
        }
      });

      linkForm.style.display = "none";
      kwForm.style.display = "none";
      if (selContainer) selContainer.style.display = "none";

      if (mode === "link") {
        linkForm.style.display = "flex";
        btnLink.style.background = "var(--accent-indigo)";
        btnLink.style.color = "#fff";
        btnLink.style.fontWeight = "700";
        btnLink.style.boxShadow = "0 0 12px var(--accent-indigo-glow)";
      } else if (mode === "keyword") {
        kwForm.style.display = "flex";
        btnKw.style.background = "var(--accent-indigo)";
        btnKw.style.color = "#fff";
        btnKw.style.fontWeight = "700";
        btnKw.style.boxShadow = "0 0 12px var(--accent-indigo-glow)";
      } else if (mode === "selective") {
        if (selContainer) selContainer.style.display = "flex";
        btnSel.style.background = "var(--accent-indigo)";
        btnSel.style.color = "#fff";
        btnSel.style.fontWeight = "700";
        btnSel.style.boxShadow = "0 0 12px var(--accent-indigo-glow)";
      }
    }

    // Giai đoạn 1: Tìm kiếm bài viết hot theo từ khóa
    async function executeSelectiveSearch(e) {
      if (e) e.preventDefault();
      const kw = document.getElementById("selective-keyword-input").value.trim();
      const limit = parseInt(document.getElementById("selective-limit-input").value) || 10;
      if (!kw) {
        showToast("Vui lòng nhập từ khóa cần tìm", "⚠️");
        return;
      }

      const searchBtn = document.getElementById("selective-search-btn");
      searchBtn.disabled = true;
      searchBtn.innerHTML = `<span>⏳ Đang tìm kiếm các bài hot...</span>`;

      try {
        const res = await fetch("/api/keyword/search-posts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keyword: kw, limit: limit })
        });
        const json = await res.json();

        if (json.success && json.posts && json.posts.length > 0) {
          CURRENT_SELECTIVE_POSTS = json.posts;
          document.getElementById("selective-found-count").textContent = json.posts.length;
          renderSelectivePostsTable(json.posts);
          document.getElementById("selective-results-box").style.display = "block";
          showToast(`Tìm thấy ${json.posts.length} bài viết! Hãy tích chọn các bài cần cào.`, "✨");
        } else {
          showToast("Không tìm thấy bài viết nào phù hợp với từ khóa này.", "⚠️");
          document.getElementById("selective-results-box").style.display = "none";
        }
      } catch (err) {
        showToast(`Lỗi tìm kiếm: ${err.message}`, "❌");
      } finally {
        searchBtn.disabled = false;
        searchBtn.innerHTML = `<span>🔎 GIAI ĐOẠN 1: TÌM BÀI VIẾT NỔI BẬT</span>`;
      }
    }

    function renderSelectivePostsTable(posts) {
      const tbody = document.getElementById("selective-posts-tbody");
      tbody.innerHTML = "";

      posts.forEach((p, idx) => {
        const tr = document.createElement("tr");
        tr.style.borderBottom = "1px solid rgba(255,255,255,0.05)";
        tr.style.transition = "background 0.2s";
        tr.onmouseover = () => { tr.style.background = "rgba(255,255,255,0.03)"; };
        tr.onmouseout = () => { tr.style.background = "transparent"; };

        // Auto select first post by default for convenience
        const isChecked = (idx === 0) ? "checked" : "";

        tr.innerHTML = `
          <td style="padding:12px; text-align:center;">
            <input type="checkbox" class="selective-post-cb" data-idx="${idx}" ${isChecked} onchange="updateSelectiveCount()" style="cursor:pointer; width:16px; height:16px;">
          </td>
          <td style="padding:12px;">
            <div style="font-weight:600; color:#f1f5f9; line-height:1.4;">${escapeHtml(p.title || "Bài viết Facebook")}</div>
            <div style="font-size:11px; color:var(--text-muted); margin-top:3px;">
              <span style="background:rgba(99,102,241,0.15); color:#a5b4fc; padding:2px 6px; border-radius:4px;">${p.origin || "CANDIDATE"}</span>
              <span style="margin-left:6px;">ID: ${escapeHtml(p.post_id || "-")}</span>
            </div>
          </td>
          <td style="padding:12px; color:#cbd5e1;">
            <div>🏢 ${escapeHtml(p.source_name || "Trang Facebook")}</div>
          </td>
          <td style="padding:12px; text-align:center;">
            <div style="display:flex; gap:6px; justify-content:center; flex-wrap:wrap;">
              <span style="background:rgba(239,68,68,0.15); color:#fca5a5; padding:2px 6px; border-radius:4px; font-size:11px;">👍 ${p.reactions_count || 0}</span>
              <span style="background:rgba(59,130,246,0.15); color:#93c5fd; padding:2px 6px; border-radius:4px; font-size:11px;">💬 ${p.comments_count || 0}</span>
              <span style="background:rgba(245,158,11,0.15); color:#fde68a; padding:2px 6px; border-radius:4px; font-size:11px;">🔥 ${p.engagement_score || 0}</span>
            </div>
          </td>
          <td style="padding:12px; text-align:center;">
            <a href="${escapeHtml(p.url)}" target="_blank" rel="noopener noreferrer" style="color:#38bdf8; text-decoration:none; font-size:16px; padding:4px 8px; border-radius:6px; background:rgba(56,189,248,0.1);" title="Mở bài viết trên Facebook">
              🔗
            </a>
          </td>
        `;
        tbody.appendChild(tr);
      });

      updateSelectiveCount();
    }

    function handleSelectAllChange(checked) {
      document.querySelectorAll(".selective-post-cb").forEach(cb => {
        cb.checked = checked;
      });
      updateSelectiveCount();
    }

    function toggleSelectAllPosts() {
      const allCbs = document.querySelectorAll(".selective-post-cb");
      const anyUnchecked = Array.from(allCbs).some(cb => !cb.checked);
      allCbs.forEach(cb => { cb.checked = anyUnchecked; });
      const selectAllMaster = document.getElementById("select-all-cb");
      if (selectAllMaster) selectAllMaster.checked = anyUnchecked;
      updateSelectiveCount();
    }

    function updateSelectiveCount() {
      const checkedBoxes = document.querySelectorAll(".selective-post-cb:checked");
      const count = checkedBoxes.length;
      const badge = document.getElementById("selected-posts-badge");
      if (badge) badge.textContent = count;

      const crawlBtn = document.getElementById("selective-crawl-btn");
      if (crawlBtn) {
        crawlBtn.disabled = (count === 0);
        crawlBtn.style.opacity = (count === 0) ? "0.5" : "1";
      }

      const allCbs = document.querySelectorAll(".selective-post-cb");
      const masterCb = document.getElementById("select-all-cb");
      if (masterCb && allCbs.length > 0) {
        masterCb.checked = (checkedBoxes.length === allCbs.length);
      }
    }

    // Giai đoạn 2: Cào bình luận từ các bài viết người dùng đã tích chọn
    async function executeSelectiveCrawl() {
      const checkedBoxes = document.querySelectorAll(".selective-post-cb:checked");
      if (checkedBoxes.length === 0) {
        showToast("Vui lòng tích chọn ít nhất 1 bài viết cần cào", "⚠️");
        return;
      }

      const selectedPosts = [];
      checkedBoxes.forEach(cb => {
        const idx = parseInt(cb.getAttribute("data-idx"));
        if (CURRENT_SELECTIVE_POSTS[idx]) {
          selectedPosts.push(CURRENT_SELECTIVE_POSTS[idx]);
        }
      });

      const keyword = document.getElementById("selective-keyword-input").value.trim() || "enjicad";
      const crawlBtn = document.getElementById("selective-crawl-btn");
      const progress = document.getElementById("crawl-progress");
      const step1 = document.getElementById("step-1");
      const step2 = document.getElementById("step-2");
      const step3 = document.getElementById("step-3");

      crawlBtn.disabled = true;
      crawlBtn.innerHTML = `<span>⏳ Đang cào ${selectedPosts.length} bài viết...</span>`;
      progress.style.display = "block";

      step1.className = "step-item active";
      step2.className = "step-item";
      step3.className = "step-item";

      setTimeout(() => {
        step1.className = "step-item done";
        step2.className = "step-item active";
        step2.innerHTML = `<div class="spinner"></div><span>2. AI bóc tách thông tin khách hàng & profile...</span>`;
      }, 3000);

      setTimeout(() => {
        step2.className = "step-item done";
        step3.className = "step-item active";
        step3.innerHTML = `<div class="spinner"></div><span>3. Đồng bộ Supabase & chuyển giao Qwen...</span>`;
      }, 7000);

      try {
        const res = await fetch("/api/keyword/crawl-selected", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ posts: selectedPosts, keyword: keyword })
        });
        const json = await res.json();

        if (json.success) {
          step3.className = "step-item done";
          step3.innerHTML = `<span>✅ Đã cào xong ${json.posts_crawled} bài viết!</span>`;
          showToast(`Hoàn tất! Cào ${json.posts_crawled} bài viết: Tìm thấy ${json.total_leads_identified} khách (${json.hot_leads_count} HOT)!`, "🎉");
          setTimeout(() => { progress.style.display = "none"; }, 2500);
          await refreshDashboard();

          // Scroll smoothly to CRM Leads section
          const leadsSection = document.querySelector(".leads-section");
          if (leadsSection) leadsSection.scrollIntoView({ behavior: "smooth" });
        } else {
          showToast(`Lỗi: ${json.error}`, "❌");
          progress.style.display = "none";
        }
      } catch (err) {
        showToast(`Lỗi mạng: ${err.message}`, "❌");
        progress.style.display = "none";
      } finally {
        crawlBtn.disabled = false;
        crawlBtn.innerHTML = `<span>🚀</span> GIAI ĐOẠN 2: CÀO BÀI ĐÃ CHỌN (<span id="selected-posts-badge">${selectedPosts.length}</span>)`;
      }
    }'''

if old_switch_func in html:
    html = html.replace(old_switch_func, new_switch_func)
    print("Replaced switchCrawlMode and added Phase 1 & 2 handlers")
else:
    print("old_switch_func pattern not matched directly")

# Set selective mode as default active tab on load
html = html.replace(
    'id="link-crawl-form" onsubmit="executeCrawl(event)"',
    'id="link-crawl-form" onsubmit="executeCrawl(event)" style="display:none;"'
)

with open('/home/ADMIN/dashboard/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated index.html for 2-stage selective crawl")
