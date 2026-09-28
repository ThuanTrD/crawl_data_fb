# Thiết kế Cơ sở dữ liệu Hoàn chỉnh: Facebook Lead Intelligence V1 (Phase 1)

Tài liệu đặc tả chi tiết toàn bộ 14 nhóm bảng PostgreSQL (triển khai trên **Supabase** Project `crawl_data_fb`), hệ thống khóa ngoại (FK), chỉ mục (Indexes), ràng buộc Check Constraints, cơ chế bảo toàn dữ liệu thô bất biến (Raw Immutability), con trỏ thu thập tăng dần (Incremental Checkpoint), Circuit Breaker và cây nguồn gốc dữ liệu (Data Lineage / Provenance).

---

## 1. Sơ đồ Quan hệ Tổng thể (Entity Relationship Overview)

```
[facebook_sources] ◄─── (1:N) ─── [facebook_raw_items] (Raw Bất Biến: SHA-256 Hash)
       ▲                                 │
       │                                 ├───► [facebook_posts]
       │                                 ├───► [facebook_comments]
       │                                 └───► [facebook_lead_signals]
       │                                              │
       ├─────────────────┐                            │ (Trích xuất & Chấm điểm)
       │                 ▼                            ▼
[facebook_source_metrics] [lead_sources] ◄────── [leads] (Canonical Deduplicated)
                                 │                 │
                                 │                 ├───► [lead_scores]
                                 │                 └───► [lead_events] (Audit Trail)
                                 ▼
                    [facebook_collection_logs]
                    [facebook_errors]
                    [system_flags] (Circuit Breaker & Kill Switches)
```

---

## 2. Danh mục 14 Nhóm Bảng Chi tiết

| STT | Tên bảng | Mục đích & Trách nhiệm | Khóa chính & Ràng buộc chính |
| :---: | :--- | :--- | :--- |
| **1** | `facebook_sources` | Quản lý Fanpage/Group/Nguồn Facebook được cấp phép | UUID PK, `external_id UNIQUE`, Check Status (8 trạng thái) |
| **2** | `facebook_raw_items` | Lưu trữ dữ liệu thô bất biến, không ghi đè | UUID PK, `payload_hash CHAR(64) UNIQUE` (SHA-256), FK `source_id` |
| **3** | `facebook_posts` | Bài viết Facebook đã chuẩn hóa | UUID PK, `post_id UNIQUE`, FK `source_id`, FK `raw_item_id` |
| **4** | `facebook_comments` | Bình luận Facebook đã chuẩn hóa | UUID PK, `comment_id UNIQUE`, FK `source_id`, FK `raw_item_id` |
| **5** | `facebook_processing_jobs` | Quản lý tiến trình/phiên xử lý lô dữ liệu | UUID PK, Check Job Status (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`) |
| **6** | `facebook_lead_signals` | Tín hiệu bóc tách ý định mua hàng & liên hệ | UUID PK, Check Intent (13 giá trị), FK `raw_item_id`, FK `source_id` |
| **7** | `leads` | Bảng khách hàng tiềm năng chuẩn hóa (Canonical) | UUID PK, Check Status, Check Resolution, `dedup_fingerprint CHAR(32)` |
| **8** | `lead_sources` | Cây phả hệ nguồn gốc Lead (Provenance Lineage) | UUID PK, FK `lead_id`, FK `source_id`, FK `signal_id`, FK `raw_item_id` |
| **9** | `lead_events` | Nhật ký sự kiện kiểm toán (Audit Trail) | UUID PK, FK `lead_id`, `event_type`, `old_state`, `new_state` |
| **10**| `lead_scores` | Chi tiết phân rã điểm chất lượng Lead (0-100) | UUID PK, FK `lead_id`, FK `signal_id`, Check Tier (`HOT`, `WARM`, `COLD`) |
| **11**| `facebook_collection_logs` | Nhật ký mỗi lượt quét/nhận webhook | UUID PK, FK `source_id`, FK `job_id`, Cursor checkpoints |
| **12**| `facebook_errors` | Kho lưu trữ và phân loại lỗi hệ thống | UUID PK, FK `source_id`, FK `raw_item_id`, `error_category` |
| **13**| `facebook_source_metrics` | Số liệu thống kê tổng hợp theo ngày | UUID PK, `UNIQUE (source_id, metric_date)` |
| **14**| `system_flags` | Cờ hệ thống, Circuit Breaker & Kill Switch | VARCHAR(50) PK, Check State (`CLOSED`, `OPEN`, `HALF_OPEN`) |

---

## 3. Hệ thống Trạng thái & Ràng buộc Chuẩn hóa (Enums & Constraints)

### 3.1. Trạng thái Nguồn (`facebook_sources.status`):
* `ACTIVE`: Nguồn đang hoạt động bình thường.
* `PAUSED`: Tạm dừng chủ động bởi quản trị viên.
* `RATE_LIMITED`: Đang chạm trần tần suất của Meta, tự động giảm tải.
* `AUTH_ERROR`: Lỗi xác thực Access Token (token hết hạn hoặc bị hủy).
* `PERMISSION_ERROR`: Thiếu quyền đọc feed/comments trên Page.
* `TEMP_ERROR`: Lỗi mạng tạm thời, đang kích hoạt retry backoff.
* `BLOCKED`: Nguồn bị chặn truy cập từ phía nền tảng.
* `DISABLED`: Nguồn đã dừng hoạt động vĩnh viễn.

### 3.2. Trạng thái Lead (`leads.status`):
`NEW` ➔ `CONTACTING` ➔ `QUALIFIED` ➔ `QUOTED` ➔ `NEGOTIATING` ➔ `WON` / `LOST` / `SPAM`

### 3.3. Độ phân giải trùng lặp (`leads.resolution`):
* `NEW`: Lead mới tinh lần đầu xuất hiện.
* `POSSIBLE_DUPLICATE`: Nghi vấn trùng lặp (cùng tên/công ty, khác SĐT).
* `EXISTING_LEAD`: Đã có Lead trong hệ thống (cùng SĐT + cùng ngành hàng trong 7 ngày).
* `EXISTING_CUSTOMER`: Khách hàng cũ đã từng ký hợp đồng trước đây.

### 3.4. Danh mục Ý định Khách hàng (`intent`):
* `IGNORE`: Tin rác, icon, không có nghĩa.
* `INFORMATION`: Hỏi thông tin kỹ thuật cơ bản.
* `DISCUSSION`: Tranh luận, chia sẻ kinh nghiệm thi công.
* `RECOMMENDATION`: Khuyên dùng hoặc giới thiệu đơn vị khác.
* `RESEARCH`: Đang tìm hiểu nghiên cứu thị trường.
* `COMPARISON`: So sánh giữa các giải pháp (ví dụ: enjiCAD vs AutoCAD, máy xoa đôi vs máy xoa đơn).
* `LOOKING_TO_BUY`: Có nhu cầu mua sắm rõ ràng.
* `REQUEST_QUOTE`: Yêu cầu gửi bảng báo giá gấp.
* `LOOKING_FOR_SERVICE`: Cần tìm dịch vụ thi công / đo đạc / kiểm định.
* `URGENT_NEED`: Cần máy hoặc giải pháp gấp cho công trường.
* `HIRING`: Tuyển dụng nhân sự công trường / kỹ sư.
* `PARTNERSHIP`: Đề xuất hợp tác kinh doanh / làm đại lý.
* `EXISTING_CUSTOMER`: Khách hàng đang dùng sản phẩm cần hỗ trợ kỹ thuật.

---

## 4. Đặc tả Cơ chế Bất biến (Raw Immutability) & Nguồn gốc (Provenance)

1. **Nguyên tắc Raw Immutability:**
   * Mọi dữ liệu đi vào cổng n8n đều được lưu nguyên vẹn vào `facebook_raw_items.raw_payload` (JSONB).
   * Mã băm `payload_hash = SHA-256(raw_payload)` đảm bảo nếu cùng một sự kiện được gửi lại, cơ sở dữ liệu sẽ bỏ qua nhờ `ON CONFLICT (payload_hash) DO NOTHING`.
   * AI hoặc các tác vụ chuẩn hóa chỉ đọc từ `raw_payload` và tạo bản ghi ở `facebook_posts`, `facebook_comments`, `facebook_lead_signals`, **tuyệt đối không bao giờ được ghi đè hay sửa đổi nội dung bảng `facebook_raw_items`**.

2. **Cơ chế Truy xuất Nguồn gốc (Data Lineage):**
   * Bảng `lead_sources` lưu vết chính xác: Lead này bắt nguồn từ bài viết (`post_id`) hay bình luận (`comment_id`) nào, đường dẫn URL gốc là gì, do payload thô nào chứa.
   * Bảng `lead_scores` lưu bảng điểm chi tiết (Intent: 40, Contact: 25, Profile: 15, Context: 10) và danh sách các rule đã áp dụng.
   * Bảng `lead_events` ghi nhận toàn bộ biến thiên trạng thái (`old_state` ➔ `new_state`) từ lúc tạo, bắn Telegram, đến khi nhân viên sale tiếp nhận.

---

## 5. Dữ liệu Khởi tạo Hệ thống (Seed Data - `system_flags`)

| Mã cờ (ID) | Trạng thái | Cờ bật/tắt | Ngưỡng ngắt | Thời gian chờ | Chức năng |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `circuit_breaker_global` | `CLOSED` | `TRUE` | 5 lần | 300 giây | Mạch ngắt bảo vệ toàn hệ thống chống quá tải |
| `kill_switch_ingestion` | `CLOSED` | `FALSE` | 0 lần | 0 giây | Nút dừng khẩn cấp: Bật `TRUE` sẽ dừng toàn bộ Ingestion |
| `qwen_ai_enabled` | `CLOSED` | `TRUE` | 3 lần | 180 giây | Cờ bật/tắt bóc tách bằng mô hình Qwen AI B2B |
| `telegram_dispatch_enabled` | `CLOSED` | `TRUE` | 5 lần | 120 giây | Cờ bật/tắt đẩy cảnh báo Lead HOT/WARM sang Telegram |
| `google_sheets_sync_enabled` | `CLOSED` | `TRUE` | 5 lần | 120 giây | Cờ bật/tắt đồng bộ sang Google Sheets / CRM |

---

## 6. File Migration Nguồn

File migration SQL hoàn chỉnh được lưu trữ tại:
* Đường dẫn máy chủ: `/home/ADMIN/facebook_lead_schema_v1.sql`
* Trạng thái thực thi: Đã chạy thành công trên Supabase Pooler IPv4, tạo đủ 14 bảng, 3 trigger tự động cập nhật `updated_at`, 24 index và 5 bản ghi seed data.
