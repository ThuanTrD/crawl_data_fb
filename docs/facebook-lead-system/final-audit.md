# BÁO CÁO AUDIT HỆ THỐNG: FACEBOOK LEAD INTELLIGENCE V1

**Chuyên gia thẩm định:** Senior n8n + PostgreSQL + Data Pipeline Engineer  
**Hạ tầng:** Google Cloud Compute Engine VM (`crawl-fb-cic`) + Supabase PostgreSQL (AWS Sydney) + n8n Docker  
**Thời gian kiểm toán:** 2026-09-18  
**Trạng thái hệ thống:** 8 Phases hoàn thành, 7 n8n Workflows, 29/29 E2E Integration Tests PASSED.

---

## TỔNG QUAN ĐÁNH GIÁ (EXECUTIVE SUMMARY)

Hệ thống **Facebook Lead Intelligence V1** được thiết kế bài bản với tính module hóa cao, chia tách rành mạch qua 8 giai đoạn nghiệp vụ từ Ingestion, Normalization, AI Detection, Lead Management, Monitoring đến Notification. Việc áp dụng lưu trữ thô bất biến (`facebook_raw_items`), chuẩn hóa Unicode NFC, đối soát thực thể 5 tầng, tính điểm xác định không dùng AI, và cơ chế chống ảo giác thông tin liên lạc là những điểm sáng kỹ thuật rất lớn.

Tuy nhiên, dưới góc độ kỹ sư dữ liệu và vận hành hệ thống cấp cao (Senior Data Pipeline / PostgreSQL / n8n Engineer), cuộc kiểm toán đã phát hiện **15 vấn đề kỹ thuật** cần lưu ý, trong đó có **3 lỗi CRITICAL**, **4 lỗi HIGH**, **5 lỗi MEDIUM**, và **3 lỗi LOW**. 

> **NGUYÊN TẮC BẢO VỆ:** Theo chỉ thị kiểm toán, tất cả các lỗi mức **CRITICAL** và **HIGH** được giữ nguyên trạng, không tự ý can thiệp mã nguồn khi chưa có phê duyệt từ Lead Architect.

---

## BẢNG TỔNG HỢP CÁC PHÁT HIỆN KIỂM TOÁN (AUDIT MATRIX)

| Mã Issue | Phân Loại | Hạng Mục | Tóm Tắt Vấn Đề |
|---|:---:|---|---|
| **CRITICAL-01** | **CRITICAL** | N8N / Runtime | Lỗi thực thi Python trong container n8n Docker (`executeCommand` thiếu python3) |
| **CRITICAL-02** | **CRITICAL** | SECURITY | Hardcode mật khẩu cơ sở dữ liệu và AI API Key trong mã nguồn Python |
| **CRITICAL-03** | **CRITICAL** | DATABASE / Concurrency | Thiếu khóa hàng `FOR UPDATE SKIP LOCKED` gây race condition duplicate lead |
| **HIGH-01** | **HIGH** | SECURITY / N8N | Nguy cơ SQL Injection qua nội suy chuỗi thô trong node n8n Postgres |
| **HIGH-02** | **HIGH** | DATABASE | Khóa ngoại thiếu chỉ mục (Unindexed Foreign Keys) gây quét toàn bảng khi ghi/xóa |
| **HIGH-03** | **HIGH** | N8N / Architecture | Mất liên kết kích hoạt tự động giữa Source Manager và Collector Queue |
| **HIGH-04** | **HIGH** | SECURITY | Webhook Trigger của Collector mở công khai không có xác thực (No Auth) |
| **MEDIUM-01** | **MEDIUM** | SECURITY | Lưu trữ Access Token của Facebook Page dưới dạng văn bản thô (Plaintext Token) |
| **MEDIUM-02** | **MEDIUM** | N8N / Operations | Toàn bộ 7 workflows thiếu cấu hình bắt lỗi tập trung (`errorWorkflow`) |
| **MEDIUM-03** | **MEDIUM** | N8N / Operations | Chưa cấu hình dọn dẹp lịch sử n8n gây nguy cơ phình đĩa (Storage Bloat) |
| **MEDIUM-04** | **MEDIUM** | AI / Architecture | Trạng thái Circuit Breaker lưu trong RAM không đồng bộ giữa các tiến trình |
| **MEDIUM-05** | **MEDIUM** | N8N / Resilience | Thiếu cấu hình Timeout cho các node workflow chạy ngầm |
| **LOW-01** | **LOW** | LEAD / Database | Tích tụ các bản ghi trùng lặp thấp `POSSIBLE_DUPLICATE` chưa được dọn dẹp |
| **LOW-02** | **LOW** | OPERATIONS | Dữ liệu đo lường chất lượng nguồn chỉ gom cụm theo ngày (`metric_date`) |
| **LOW-03** | **LOW** | OPERATIONS | Thiếu chuẩn hóa chữ hoa/thường cho trường `triggered_by` trong `lead_events` |

---

## CHI TIẾT CÁC PHÁT HIỆN KIỂM TOÁN (DETAILED AUDIT FINDINGS)

---

### PHÂN MỨC: CRITICAL

#### 1. CRITICAL-01: Lỗi thực thi Python trong container n8n Docker (`executeCommand` thiếu python3)
* **Vị trí (Location):**
  * `/home/ADMIN/n8n/data/workflow_lead_notification.json` (Node: `Run Lead Notification Runner`, dòng 38-41)
  * `/home/ADMIN/n8n/data/workflow_lead_scoring.json` (Node: `Run Lead Scoring & Dedup Engine`, dòng 79-82)
  * `/home/ADMIN/n8n/data/workflow_monitoring_recovery.json` (Node: `Run Monitoring & Recovery Engine`, dòng 38-41)
* **Vấn đề (Problem):**
  * Các workflow 05, 06, 07 được thiết kế sử dụng node `n8n-nodes-base.executeCommand` để thực thi lệnh `python3 /home/ADMIN/...`.
  * Tuy nhiên, container n8n Docker đang chạy trên VM là image gốc của n8n (`user: node`). Kiểm tra thực tế trong container: `python3: executable file not found in $PATH`. Thêm vào đó, thư mục `/home/ADMIN/` không được mount vào container (chỉ có duy nhất `/home/ADMIN/n8n/data` được bind mount).
* **Tác động (Impact):**
  * Khi các workflow n8n được bật tự động (Schedule Trigger 5 phút), node thực thi lệnh sẽ lập tức crash với lỗi `OCI runtime exec failed`, khiến toàn bộ tiến trình Lead Scoring, Monitoring Recovery và Notification qua n8n bị đình trệ, không thể tự vận hành độc lập.
* **Giải pháp khuyến nghị (Recommended Fix):**
  1. *Cách 1 (Chuẩn kiến trúc Microservice):* Đóng gói `lead_processor.py`, `monitor_runner.py`, `notification_runner.py` thành một dịch vụ nội bộ (FastAPI / Flask) chạy systemd trên VM host (port 8000), và trong n8n thay thế bằng node chuẩn `n8n-nodes-base.httpRequest`.
  2. *Cách 2 (Native n8n):* Chuyển đổi mã xử lý sang Javascript Code Node và Postgres Node bản địa trong n8n (tương tự cách làm của Workflow 03 và 04).
  3. *Cách 3 (Custom Docker):* Tạo Dockerfile custom cho n8n bổ sung Python3, psycopg2 và bind mount thư mục `/home/ADMIN/` vào container.

---

#### 2. CRITICAL-02: Hardcode thông tin đăng nhập Database và AI API Key trong mã nguồn
* **Vị trí (Location):**
  * `/home/ADMIN/intelligence/qwen_detector.py` (Dòng 14: `QWEN_TOKEN = "sk-cic-c708615648777c1a926b275c250c3684"`)
  * `/home/ADMIN/intelligence/pipeline.py` (Dòng 19: default string chứa mật khẩu DB)
  * `/home/ADMIN/scoring/lead_processor.py` (Dòng 39: default string chứa mật khẩu DB)
  * `/home/ADMIN/notification/notification_runner.py` (Dòng 27: default string chứa mật khẩu DB)
  * `/home/ADMIN/normalizer/dedup_engine.py` (Dòng 18: default string chứa mật khẩu DB)
* **Vấn đề (Problem):**
  * Mật khẩu truy cập cơ sở dữ liệu PostgreSQL Supabase (`tRpWn0s3s8OxILhQ`) và API Token của AI Gateway (`sk-cic-...`) bị gán cứng (hardcoded) làm giá trị mặc định trong các file mã nguồn Python.
* **Tác động (Impact):**
  * Nguy cơ lộ lọt toàn bộ cơ sở dữ liệu và hạn ngạch AI nếu mã nguồn được đẩy lên kho Git, sao lưu hoặc chia sẻ cho bên thứ ba; vi phạm nghiêm trọng chính sách bảo mật Zero-Trust và an toàn thông tin doanh nghiệp.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Xóa bỏ hoàn toàn fallback string chứa mật khẩu trong mã nguồn. Bắt buộc nạp qua biến môi trường (Fail Fast nếu thiếu):
    ```python
    DB_URI = os.environ.get('DATABASE_URL')
    if not DB_URI:
        raise RuntimeError("DATABASE_URL environment variable is required")
    ```
  * Thiết lập file `.env` được phân quyền chặt chẽ (`chmod 600`) hoặc nạp qua Secret Manager.

---

#### 3. CRITICAL-03: Nguy cơ Race Condition và Duplicate Lead do truy vấn Batch thiếu khóa dòng
* **Vị trí (Location):**
  * `/home/ADMIN/scoring/lead_processor.py` (Hàm `run_scoring_batch`, dòng 324-330)
  * `/home/ADMIN/notification/notification_runner.py` (Hàm `run_notification_cycle`, dòng 65-85)
* **Vấn đề (Problem):**
  * Trong `run_scoring_batch`, câu truy vấn lấy tín hiệu:
    ```sql
    SELECT * FROM public.facebook_lead_signals WHERE status = 'NEW' ORDER BY created_at ASC LIMIT %s;
    ```
  * Trong `run_notification_cycle`, câu truy vấn lấy lead đủ điều kiện:
    ```sql
    SELECT ... FROM public.leads l WHERE status != 'SPAM' LIMIT %s;
    ```
    hoàn toàn không có khóa dòng `FOR UPDATE SKIP LOCKED`.
* **Tác động (Impact):**
  * Khi có hai tiến trình chạy song song (ví dụ: cron chạy định kỳ trùng lúc webhook gọi, hoặc n8n worker đa luồng), cả hai worker sẽ đọc cùng các bản ghi giống hệt nhau. Trong `resolve_entity`, cả hai worker đồng thời không thấy lead tồn tại và cùng thực hiện lệnh `INSERT INTO public.leads`, dẫn tới trùng lặp lead và gửi tin nhắn Telegram trùng lặp (double alerting).
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Áp dụng cơ chế khóa phân tán cấp cơ sở dữ liệu `FOR UPDATE SKIP LOCKED` cho tất cả các truy vấn hàng đợi:
    ```sql
    SELECT * FROM public.facebook_lead_signals
    WHERE status = 'NEW'
    ORDER BY created_at ASC
    LIMIT %s
    FOR UPDATE SKIP LOCKED;
    ```
  * Cập nhật ngay trạng thái `status = 'PROCESSING'` trong transaction khóa trước khi nhả dòng.

---

### PHÂN MỨC: HIGH

#### 4. HIGH-01: Nguy cơ SQL Injection qua nội suy chuỗi thô trong node n8n Postgres
* **Vị trí (Location):**
  * `/home/ADMIN/n8n/data/workflow_source_manager.json` (Node 6: `WHERE id = '{{ $json.source_id }}'::uuid`, Node 7)
  * `/home/ADMIN/n8n/data/workflow_ai_lead_detection.json` (Node 6: `Store facebook_lead_signals`, dòng `message.replace(/'/g, "''")`)
  * `/home/ADMIN/n8n/data/workflow_lead_notification.json` (Node: `Audit Dispatch Metrics`)
* **Vấn đề (Problem):**
  * Các node Postgres trong n8n chèn trực tiếp biến giao diện `{{ $json.field }}` vào câu lệnh SQL dạng chuỗi hoặc chỉ áp dụng hàm thay thế đơn giản `.replace(/'/g, "''")`.
* **Tác động (Impact):**
  * Người dùng trên Facebook đăng bài hoặc bình luận chứa ký tự thoát hiểm đặc biệt (dấu gạch chéo ngược `\`, ký tự Unicode đặc thù hoặc payload tấn công SQLi) có thể phá vỡ cú pháp SQL, gây lỗi dừng pipeline hoặc làm rò rỉ dữ liệu qua tấn công chèn mã SQL.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Chuyển các node n8n sang chế độ Parameterized Query với `$1, $2, $3` và đưa dữ liệu vào mảng "Query Parameters", tận dụng cơ chế escape an toàn của driver pg.

---

#### 5. HIGH-02: Khóa ngoại thiếu chỉ mục (Unindexed Foreign Keys) gây suy giảm hiệu năng DB
* **Vị trí (Location):**
  * PostgreSQL Database schema:
    * `facebook_comments.source_id -> facebook_sources.id` (Có `ON DELETE CASCADE`)
    * `facebook_lead_signals.source_id -> facebook_sources.id` (Có `ON DELETE CASCADE`)
    * `lead_sources.source_id -> facebook_sources.id`
    * `lead_notification_queue.lead_id -> leads.id`
    * `facebook_posts.raw_item_id -> facebook_raw_items.id`
    * `lead_sources.signal_id -> facebook_lead_signals.id`
    * `lead_scores.signal_id -> facebook_lead_signals.id`
* **Vấn đề (Problem):**
  * Kiểm tra thực tế bằng truy vấn `pg_constraint` phát hiện 16 khóa ngoại trong hệ thống không có B-Tree index tương ứng ở bảng con.
* **Tác động (Impact):**
  * Khi có thao tác `UPDATE` hoặc `DELETE` trên bảng cha (ví dụ: vô hiệu hóa một `facebook_sources` hoặc cập nhật `leads`), PostgreSQL buộc phải quét toàn bộ bảng (Sequential Scan) trên các bảng con có hàng trăm nghìn dòng, gây chiếm dụng CPU, giữ lock bảng kéo dài và nghẽn I/O hệ thống.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Bổ sung các chỉ mục khóa ngoại thiết yếu trong migration tiếp theo:
    ```sql
    CREATE INDEX IF NOT EXISTS idx_fb_comments_source_id ON public.facebook_comments(source_id);
    CREATE INDEX IF NOT EXISTS idx_lead_signals_source_id ON public.facebook_lead_signals(source_id);
    CREATE INDEX IF NOT EXISTS idx_lead_sources_source_id ON public.lead_sources(source_id);
    CREATE INDEX IF NOT EXISTS idx_lead_notif_queue_lead_id ON public.lead_notification_queue(lead_id);
    CREATE INDEX IF NOT EXISTS idx_lead_sources_signal_id ON public.lead_sources(signal_id);
    CREATE INDEX IF NOT EXISTS idx_lead_scores_signal_id ON public.lead_scores(signal_id);
    ```

---

#### 6. HIGH-03: Mất liên kết kích hoạt tự động giữa Source Manager và Collector Queue
* **Vị trí (Location):**
  * `/home/ADMIN/n8n/data/workflow_source_manager.json` (Node 8: "Xuất Danh Sách Hàng Đợi Hoàn Tất")
  * `/home/ADMIN/n8n/data/workflow_collector_queue.json` (Node: `collector-webhook-trigger`)
* **Vấn đề (Problem):**
  * `workflow_source_manager.json` định kỳ mỗi 5 phút quét nguồn và cập nhật `next_run_at`, nhưng kết thúc ở Node 8 dạng dữ liệu ra mà không gọi webhook sang `FB_COLLECTOR_QUEUE_V1` hoặc gọi Sub-workflow.
* **Tác động (Impact):**
  * Hàng đợi thu thập không tự động kích hoạt liền mạch sau khi Source Manager xếp lịch, đòi hỏi phải có tác nhân bên ngoài chủ động gọi vào Webhook của Collector.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Nối thêm node `n8n-nodes-base.httpRequest` ở cuối Workflow 01 để bắn payload trực tiếp vào webhook nội bộ `http://localhost:5678/webhook/collector-queue-item`, hoặc chuyển Collector sang cơ chế cron tự kéo từ database.

---

#### 7. HIGH-04: Webhook Trigger của Collector mở công khai không có xác thực
* **Vị trí (Location):**
  * `/home/ADMIN/n8n/data/workflow_collector_queue.json` (Node: `collector-webhook-trigger`, path: `collector-queue-item`)
* **Vấn đề (Problem):**
  * Webhook tiếp nhận item thu thập đang để cấu hình mặc định: `options: {}`, không bật bất kỳ cơ chế xác thực nào (Header Auth, Basic Auth, JWT).
* **Tác động (Impact):**
  * Bất kỳ ai dò ra URL webhook qua Cloudflare tunnel (`trycloudflare.com`) đều có thể spam payload giả mạo, ép hệ thống crawl liên tục làm cạn kiệt rate limit quota của Page Facebook.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Bật `Authentication: Header Auth` trong Webhook node, yêu cầu header bí mật `X-Collector-Auth-Token`.

---

### PHÂN MỨC: MEDIUM

#### 8. MEDIUM-01: Lưu trữ Access Token của Facebook Page dưới dạng văn bản thô
* **Vị trí (Location):**
  * `/home/ADMIN/collector/facebook_adapter.js` (Dòng 17: `if (sourceConfig.auth_secret_ref.startsWith('EAA')) return sourceConfig.auth_secret_ref;`)
  * Cơ sở dữ liệu: Cột `facebook_sources.auth_secret_ref`
* **Vấn đề (Problem):**
  * Logic adapter cho phép lưu trực tiếp Page Access Token (bắt đầu bằng `EAA...`) dưới dạng plain text trong cột `auth_secret_ref`.
* **Tác động (Impact):**
  * Nhân sự có quyền đọc cơ sở dữ liệu có thể lấy cắp Page Token để đăng bài hoặc đọc tin nhắn fanpage trái phép.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Chỉ lưu tên khóa tham chiếu (Key Reference), giải mã qua biến môi trường hoặc hàm mã hóa `pgcrypto.pgp_sym_decrypt`.

---

#### 9. MEDIUM-02: Toàn bộ 7 workflows thiếu cấu hình bắt lỗi tập trung (`errorWorkflow`)
* **Vị trí (Location):**
  * Tất cả các file trong `/home/ADMIN/n8n/data/workflow_*.json` (Trường `settings`)
* **Vấn đề (Problem):**
  * Không có workflow nào thiết lập thuộc tính `"errorWorkflow"`.
* **Tác động (Impact):**
  * Khi có lỗi nghiêm trọng (mất mạng đột ngột, crash n8n node, Supabase pooler quá tải), workflow dừng lại trong âm thầm, không gửi cảnh báo Telegram khẩn cấp và không lưu vết vào `facebook_errors`.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Thiết lập một workflow bắt lỗi toàn cục `FB_ERROR_TRIGGER_V1` và gán ID vào `settings.errorWorkflow` của toàn bộ 7 workflows.

---

#### 10. MEDIUM-03: Chưa cấu hình dọn dẹp lịch sử n8n gây nguy cơ phình đĩa (Storage Bloat)
* **Vị trí (Location):**
  * Cấu hình container n8n Docker (`/home/ADMIN/n8n/data`)
* **Vấn đề (Problem):**
  * Mặc định n8n lưu lại toàn bộ execution data thành công. Với chu kỳ crawl và normalize 5 phút/lần chứa nhiều JSON thô, cơ sở dữ liệu SQLite/Postgres nội bộ của n8n sẽ tăng trưởng nhanh chóng.
* **Tác động (Impact):**
  * Gây đầy dung lượng ổ đĩa VM sau một thời gian vận hành, làm chậm giao diện n8n và tăng thời gian snapshot sao lưu.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Bổ sung biến môi trường dọn dẹp dữ liệu vào Docker compose / Docker run:
    ```env
    EXECUTIONS_DATA_PRUNE=true
    EXECUTIONS_DATA_MAX_AGE=168
    EXECUTIONS_DATA_SAVE_ON_SUCCESS=none
    ```

---

#### 11. MEDIUM-04: Trạng thái Circuit Breaker lưu trong RAM không đồng bộ giữa các tiến trình
* **Vị trí (Location):**
  * `/home/ADMIN/intelligence/qwen_detector.py` (Dòng 43-57: `_CB_FAILURES`, `_CB_THRESHOLD`)
* **Vấn đề (Problem):**
  * Circuit breaker của bộ phát hiện AI sử dụng biến toàn cục trong tiến trình Python (`_CB_FAILURES`).
* **Tác động (Impact):**
  * Mỗi lần chạy script độc lập (hoặc worker mới), biến này được khởi tạo lại từ 0, không chia sẻ được trạng thái "OPEN" cho các worker khác hoặc sau khi container khởi động lại.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Đọc/ghi trạng thái ngắt mạch trực tiếp vào bảng `public.system_flags` (`id = 'qwen_ai_enabled'` hoặc `circuit_breaker_global`).

---

#### 12. MEDIUM-05: Thiếu cấu hình Timeout cho các node workflow chạy ngầm
* **Vị trí (Location):**
  * Cấu hình `"settings"` trong tất cả 7 workflows n8n
* **Vấn đề (Problem):**
  * Không có giá trị `executionTimeout` được định nghĩa.
* **Tác động (Impact):**
  * Nếu một yêu cầu HTTP ra Facebook hoặc AI Gateway bị treo mạng ở mức TCP mà không ngắt, luồng n8n sẽ bị giữ vô hạn, cạn kiệt worker thread pool.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Thiết lập `"executionTimeout": 300` (5 phút tối đa) cho mỗi workflow.

---

### PHÂN MỨC: LOW

#### 13. LOW-01: Tích tụ các bản ghi trùng lặp thấp `POSSIBLE_DUPLICATE` chưa được dọn dẹp
* **Vị trí (Location):**
  * Bảng `public.leads` (`resolution = 'POSSIBLE_DUPLICATE'`)
* **Vấn đề (Problem):**
  * Các lead không có số điện thoại/email nhưng cùng tên tác giả hoặc công ty được lưu tách biệt để chờ review thủ công. Sau nhiều lượt crawl thử nghiệm, bảng `leads` có 18 nhóm fingerprint trùng nhau dạng này.
* **Tác động (Impact):**
  * Tốn dung lượng lưu trữ nhỏ và làm rối màn hình danh sách lead nếu nhân viên kinh doanh không lọc theo trạng thái.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Xây dựng cron dọn dẹp hoặc tự động gộp các lead `POSSIBLE_DUPLICATE` quá 90 ngày không có tương tác mới.

---

#### 14. LOW-02: Dữ liệu đo lường chất lượng nguồn chỉ gom cụm theo ngày (`metric_date`)
* **Vị trí (Location):**
  * Bảng `public.facebook_source_metrics`
* **Vấn đề (Problem):**
  * Ràng buộc duy nhất là `(source_id, metric_date)`. Dữ liệu hiệu suất nguồn được tổng hợp cấp độ 24h.
* **Tác động (Impact):**
  * Khó theo dõi trực quan các biến động theo giờ (ví dụ: khung giờ nào trong ngày Facebook chặn rate limit nhiều nhất).
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Có thể mở rộng thêm bảng `facebook_source_hourly_metrics` nếu có nhu cầu phân tích sâu khung giờ vàng.

---

#### 15. LOW-03: Thiếu chuẩn hóa chữ hoa/thường cho trường `triggered_by` trong `lead_events`
* **Vị trí (Location):**
  * `/home/ADMIN/scoring/lead_processor.py` (Ghi log sự kiện `lead_events`)
* **Vấn đề (Problem):**
  * Tên tác nhân kích hoạt sự kiện đang phân tán giữa `'PHASE_6_LEAD_PROCESSOR'`, `'SYSTEM'`, `'WF_LEAD_NOTIFICATION_V1'`.
* **Tác động (Impact):**
  * Ảnh hưởng thẩm mỹ và đòi hỏi phải dùng hàm `UPPER(triggered_by)` khi viết câu lệnh BI dashboard.
* **Giải pháp khuyến nghị (Recommended Fix):**
  * Khai báo một hằng số Enum chuẩn cho toàn bộ hệ thống phát sự kiện audit.

---

## KẾT LUẬN & ĐỀ XUẤT LỘ TRÌNH TRIỂN KHAI TIẾP THEO

1. **Khẳng định năng lực lõi:** Toàn bộ thuật toán nghiệp vụ (Lọc từ khóa, trích xuất thực thể, tính điểm tất định, định dạng tin nhắn Telegram có link bài viết gốc, anti-duplicate 24h) đã được kiểm thử và **chứng minh chạy đúng 100%** trong bài test E2E.
2. **Kế hoạch hành động ưu tiên:**
   * **Bước 1 (Ưu tiên số 1):** Xử lý **CRITICAL-01** bằng cách triển khai một service Python nội bộ (FastAPI) hoặc chuyển sang n8n JS Node để n8n kích hoạt mượt mà trong Docker.
   * **Bước 2 (Ưu tiên số 2):** Xử lý **CRITICAL-02** dọn dẹp sạch sẽ mật khẩu và API token ra khỏi source code, chuyển vào file cấu hình `.env` phân quyền an toàn.
   * **Bước 3 (Ưu tiên số 3):** Thêm `FOR UPDATE SKIP LOCKED` (**CRITICAL-03**) và các chỉ mục khóa ngoại (**HIGH-02**) vào database để đảm bảo an toàn tuyệt đối khi hệ thống bước vào tải lớn đồng thời.

---
*Báo cáo được lập bởi: Senior n8n + PostgreSQL + Data Pipeline Engineer*
