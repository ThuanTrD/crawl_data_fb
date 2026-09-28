# Thiết kế Workflow n8n (Orchestration Architecture)

Tài liệu chi tiết về kiến trúc các luồng tự động hóa (Workflows) trên **n8n** điều phối toàn bộ vòng đời của dữ liệu Facebook Lead Intelligence V1.

---

## 1. Bản đồ tổng thể các Workflow (5 Modular Workflows)

```
[Facebook Source] ──> [WF-01: Ingestion & Checkpoint Controller]
                             │
                             ▼ (Ghi Raw & Bắn tín hiệu)
                      [WF-02: Normalizer & Intent Classifier (AI Qwen)]
                             │
                             ▼ (Trích xuất & Phân loại)
                      [WF-03: Deduplication & Scoring Engine]
                             │
                             ▼ (Lưu Lead & Provenance)
                      [WF-04: High-Value Lead Dispatcher (Telegram/CRM)]

[System Cron: 5m] ──> [WF-05: Health Check & Circuit Breaker Monitor]
```

Mỗi workflow được phân tách trách nhiệm rõ ràng (Decoupled), giao tiếp thông qua cơ sở dữ liệu PostgreSQL hoặc Webhook nội bộ, đảm bảo khi một khâu gặp sự cố (ví dụ: API AI quá tải, Telegram bảo trì) thì dữ liệu không bị thất thoát.

---

## 2. Chi tiết từng Workflow

### 2.1. WF-01: Ingestion & Checkpoint Controller
* **Mục tiêu:** Tiếp nhận dữ liệu từ các nguồn Facebook hợp lệ, kiểm tra trạng thái Circuit Breaker, lưu trữ bất biến (Immutable Raw) và cập nhật con trỏ Checkpoint.
* **Triggers:**
  1. `Webhook Node`: Nhận sự kiện Real-time từ Facebook Graph API Webhook (`/webhook/crawl-fb`).
  2. `Schedule Trigger`: Kích hoạt Poller định kỳ (mỗi 15 phút) cho các Fanpage dùng Access Token để kéo dữ liệu mới.
* **Các bước thực thi (Pipeline Steps):**
  1. **Check Circuit Breaker:** Đọc bảng `system_circuit_breaker`. Nếu `state = 'OPEN'` hoặc `kill_switch_active = true`, lập tức dừng tiếp nhận và trả về mã phản hồi an toàn.
  2. **Check Rate Limit per Source:** Kiểm tra số lượng request của `page_id` trong 1 phút qua bảng `fb_sources`.
  3. **Hash Raw Data:** Tính mã hash `SHA-256` của raw payload.
  4. **Idempotent Raw Insert:**
     ```sql
     INSERT INTO public.raw_fb_payloads (source_id, payload_hash, raw_payload, ingestion_channel)
     VALUES ($1, $2, $3, $4)
     ON CONFLICT (payload_hash) DO NOTHING
     RETURNING id;
     ```
  5. **Trigger Processing:** Nếu bản ghi là mới (insert thành công), đẩy sự kiện sang `WF-02`.
  6. **Update Checkpoint:** Lưu timestamp/cursor mới nhất vào `fb_sources.current_checkpoint_cursor`.

---

### 2.2. WF-02: Normalizer & Intent Classifier (Qwen AI & Regex)
* **Mục tiêu:** Chuẩn hóa dữ liệu bài viết/bình luận, bóc tách thực thể số điện thoại, email và phân loại ý định mua hàng ngành xây dựng.
* **Trigger:** Webhook nội bộ từ `WF-01` hoặc lắng nghe bản ghi có trạng thái `processed_status = 'pending'`.
* **Quy trình 2 lớp (Two-tier Hybrid Extraction):**
  
  **Lớp 1: Rule-based Regex Engine (Chính xác tuyệt đối, Zero Hallucination):**
  * SĐT Việt Nam: `/(?:0|\+84)(?:3[2-9]|5[2689]|7[06-9]|8[1-9]|9[0-46-9])[0-9]{7}\b/g`
  * Email: `/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g`
  * Từ khóa nhu cầu Xây dựng: `"báo giá"`, `"giá bao nhiêu"`, `"thuê máy xoa"`, `"license"`, `"dùng thử"`, `"bản quyền"`, `"catalogue"`, `"hóa đơn VAT"`.

  **Lớp 2: Qwen AI B2B Intelligence Engine (Hiểu ngữ cảnh chuyên sâu):**
  * Gửi ngữ cảnh bài viết / bình luận tới endpoint Qwen (`qwen3-vl-30b` / `Qwen-2.5`).
  * System Prompt nghiêm ngặt cấm bịa đặt:
    > "Bạn là chuyên gia phân loại Lead ngành Xây dựng & Kỹ thuật. Chỉ trích xuất thông tin CÓ THẬT trong văn bản. Nếu không có SĐT/Email/Tên công ty thì giá trị bắt buộc là null. Tuyệt đối không suy đoán."
  * Output chuẩn JSON:
    ```json
    {
      "product_group": "ROBOT_XAY_DUNG",
      "product_name": "Robot gạt phẳng & xoa nền bê tông",
      "intent_type": "request_quote",
      "customer_name": "Anh Hùng",
      "company": "Công ty Xây dựng Hòa Bình",
      "customer_type": "business",
      "quantity": 2,
      "need": "Cần báo giá 2 máy xoa nền thi công sàn công nghiệp tại Hải Phòng",
      "is_quote_requested": true,
      "confidence_score": 0.95
    }
    ```

---

### 2.3. WF-03: Deduplication & Scoring Engine
* **Mục tiêu:** Tính toán điểm chất lượng Lead (Lead Score), chống trùng lặp và lưu trữ vết nguồn gốc (Provenance).
* **Công thức chấm điểm Lead (0 - 100 điểm):**
  $$\text{Lead Score} = S_{\text{intent}} + S_{\text{contact}} + S_{\text{customer}} + S_{\text{context}}$$
  
  * **$S_{\text{intent}}$ (Ý định mua hàng - Tối đa 40 điểm):**
    * Hỏi giá, xin báo giá, mua ngay: `+40 điểm`
    * Hỏi dùng thử, demo kỹ thuật: `+25 điểm`
    * Hỏi tính năng thông thường: `+10 điểm`
  * **$S_{\text{contact}}$ (Thông tin liên hệ - Tối đa 35 điểm):**
    * Có Số điện thoại hợp lệ: `+25 điểm`
    * Có Email công ty/cá nhân: `+10 điểm`
  * **$S_{\text{customer}}$ (Chân dung khách hàng - Tối đa 15 điểm):**
    * Có tên Công ty / Nhà thầu / Mã số thuế: `+15 điểm`
    * Khách hàng cá nhân: `+5 điểm`
  * **$S_{\text{context}}$ (Khối lượng / Ngân sách - Tối đa 10 điểm):**
    * Có số lượng cụ thể (ví dụ: cần 2 máy, 10 license CAD): `+10 điểm`

  * **Phân hạng Lead:**
    * 🔴 **HOT (80 - 100 điểm):** Có SĐT/Email + Hỏi báo giá mua hàng + Doanh nghiệp/Nhà thầu.
    * 🟡 **WARM (50 - 79 điểm):** Có nhu cầu rõ ràng nhưng thiếu SĐT hoặc đang xin dùng thử.
    * ⚪ **COLD (0 - 49 điểm):** Hỏi chung chung, chào hàng, hoặc spam.

* **Deduplication Check:**
  * Tính `dedup_fingerprint`.
  * Truy vấn kiểm tra nếu đã tồn tại Lead trong 7 ngày: Nếu có -> chỉ update append ghi chú vào `fb_leads`. Nếu chưa -> insert bản ghi mới.
* **Ghi Audit Trail vào `lead_provenance`:**
  * Lưu ID bản ghi raw, tên model AI, version prompt, confidence score.

---

### 2.4. WF-04: High-Value Lead Dispatcher (Telegram & CRM Sync)
* **Mục tiêu:** Bắn thông báo tức thì cho các Lead HOT/WARM sang Telegram phòng kinh doanh và đồng bộ vào CRM / Google Sheets.
* **Trigger:** Sau khi `WF-03` hoàn tất lưu Lead và kiểm tra `lead_tier IN ('HOT', 'WARM')`.
* **Mẫu thông báo Telegram (Rich Markdown Formatter):**
  ```markdown
  🚨 **PHÁT HIỆN LEAD MỚI [HOT - 95 ĐIỂM]**
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 **Sản phẩm:** Robot Xây dựng (Máy xoa nền bê tông)
  👤 **Khách hàng:** Anh Hùng - Cty XD Hòa Bình
  📞 **Số điện thoại:** `0912345678` 
  📧 **Email:** `hung.hoabinh@gmail.com`
  🏢 **Đối tượng:** Doanh nghiệp / Nhà thầu
  
  📝 **Nhu cầu:** Cần báo giá 2 máy xoa nền thi công sàn công nghiệp tại Hải Phòng
  🔗 **Link gốc:** [Xem bài viết trên Facebook](https://facebook.com/...)
  
  🤖 *Nguồn bóc tách: Qwen AI + Regex | Tin cậy: 95%*
  ⏰ *Thời gian: 17/09/2026 14:45*
  ```
* **Lưu nhật ký:** Ghi nhận mã phản hồi của Telegram/Sheets vào bảng `lead_deliveries`.

---

### 2.5. WF-05: Health Check, Circuit Breaker & Monitor
* **Mục tiêu:** Quét kiểm tra sức khỏe hệ thống mỗi 5 phút.
* **Nhiệm vụ:**
  1. Kiểm tra tỷ lệ lỗi trong bảng `raw_fb_payloads` và `lead_deliveries`.
  2. Nếu tỷ lệ lỗi > 20% trong 15 phút qua -> Kích hoạt chuyển Circuit Breaker sang `OPEN` và gửi cảnh báo khẩn tới Telegram Admin.
  3. Kiểm tra hạn ngạch token Fanpage Facebook: Nếu Access Token hết hạn -> Tự động đánh dấu `token_expired` trong `fb_sources`.


---

## 3. Workflow 03: Normalization & Deduplication Pipeline (`FB_NORMALIZER_DEDUP_V1`)

- **Workflow ID:** `FB_NORMALIZER_DEDUP_V1`
- **Mục tiêu:** Chuẩn hóa Unicode NFC, loại bỏ khoảng trắng rác, bảo toàn tiếng Việt và ý nghĩa nguyên bản, băm nội dung SHA-256, khử trùng lặp 2 cấp (external ID & content hash), phân cấp bài viết/bình luận/phản hồi, định tuyến dead-letter khi gặp lỗi.
- **Trigger:** Schedule 5 phút một lần hoặc Manual.
- **Input:** `facebook_raw_items` (status: `PENDING`).
- **Output:** `facebook_posts`, `facebook_comments`, `facebook_errors` (Dead-letter), `Processing Queue`.
- **Node Cốt lõi:**
  1. `1. Fetch Pending Raw Items` (PostgreSQL)
  2. `2. Check Has Pending Items` (IF)
  3. `3. Normalize & Deduplicate Code Node` (Code Node - Unicode NFC, Whitespace, SHA256, Lang detect, Hierarchy)
  4. `4. Route Valid vs Dead-Letter` (IF)
  5. `5a/5b. Dead-Letter Path` (PostgreSQL - log `facebook_errors`, mark raw item `FAILED`)
  6. `6. Is POST vs COMMENT` (IF)
  7. `7a/7b. Store in Posts / Comments` (PostgreSQL - Upsert / Insert)
  8. `8. Mark Raw Item Processed` (PostgreSQL - Status `PROCESSED`)
  9. `9. Processing Queue Output` (Code Node - sẵn sàng cho Phase 5 AI & Scoring)


---

## 4. Workflow 04: AI Lead Detection & Extraction (`FB_AI_LEAD_DETECTION_V1`)

- **Workflow ID:** `FB_AI_LEAD_DETECTION_V1`
- **Mục tiêu:** Lọc từ khóa xây dựng/thương mại trước khi gọi AI, ghép ngữ cảnh bài viết gốc cho bình luận, phân loại ý định theo 13 taxonomy chuẩn, trích xuất thực thể (sản phẩm, số lượng, hotline, email, công ty) với nguyên tắc Zero-Hallucination, lưu vết đầy đủ vào `facebook_lead_signals`.
- **Trigger:** Schedule 5 phút một lần hoặc Manual Trigger.
- **Input:** `facebook_posts`, `facebook_comments` (chưa có tín hiệu trong `facebook_lead_signals`).
- **Output:** `facebook_lead_signals`, `facebook_errors` (Dead-letter), `Processing Queue` (chuẩn bị cho Phase 6).
- **Các Node cốt lõi:**
  1. `1. Fetch Posts & Comments` (PostgreSQL - tải tối đa 25 posts + 25 comments kèm parent context)
  2. `2. Check Has Items` (IF)
  3. `3. Keyword Filter Code Node` (Lọc 5 nhóm: Mua hàng, Dịch vụ, Vật liệu, Software, Construction)
  4. `4. Route Keyword Matched` (IF - chỉ gửi dữ liệu ngành sang AI)
  5. `5. Lead Detection Engine` (Code Node - Hybrid Qwen AI + Deterministic Rules + Guardrails)
  6. `6. Store facebook_lead_signals` (PostgreSQL - ghi nhận tín hiệu và provenance)
  7. `7. Enqueue to Lead Scoring` (Code Node - chuyển giao sang Phase 6)
