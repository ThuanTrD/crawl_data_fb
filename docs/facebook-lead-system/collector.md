# Đặc tả Kỹ thuật: Facebook Collector & Ingestion Queue (Phase 3)

Tài liệu đặc tả chi tiết kiến trúc tầng Thu thập (**Facebook Collector Layer**), thiết kế giao diện Adapter (Modular Interface), quy chuẩn phong bì chuẩn hóa (Normalized Envelope), xử lý phân loại lỗi và cơ chế tự động ghi nhận nhật ký vào cơ sở dữ liệu PostgreSQL.

---

## 1. Kiến trúc Tầng Thu thập Tách rời (Decoupled Collector Architecture)

```
[n8n: FB_SOURCE_MANAGER_V1]
             │
             ▼ (Dispatched Sources)
[n8n: FB_COLLECTOR_QUEUE_V1]
             │
             ▼ (Gatekeeper: Check FB_GLOBAL_COLLECTION_ENABLED & Source Status)
     [CollectorAdapter Interface]
             │
             ├──► [FacebookGraphApiAdapter] (Dùng cho Live Production)
             └──► [MockFacebookAdapter]     (Dùng cho Kiểm thử Tự động & Mô phỏng Lỗi)
             │
             ▼ (Normalized Envelope Items)
[SHA-256 Hash Calculation] ──► [facebook_raw_items] (Idempotent Raw Storage: ON CONFLICT DO NOTHING)
             │
             ├──► [facebook_posts] & [facebook_comments] (Normalized Entities)
             ├──► [facebook_sources] (Checkpoint Cursor Advancement & Error Reset)
             └──► [facebook_collection_logs] (Audit Log)
```

---

## 2. Chuẩn Phong bì Dữ liệu Chuẩn hóa (Normalized Envelope Schema)

Mọi Collector Adapter khi thu thập dữ liệu (bất kể phương thức truy cập nào) đều phải trả về mảng các đối tượng tuân thủ cấu trúc 11 trường bắt buộc sau:

```json
{
  "source_id": "9f5d376c-3729-45bc-9db0-f5483179e185",
  "external_id": "post_1092837465_987654321",
  "item_type": "POST",
  "external_parent_id": null,
  "source_url": "https://facebook.com/1092837465/posts/987654321",
  "author_id": "1092837465",
  "author_name": "Hội Máy Xây Dựng & Bê Tông Việt Nam",
  "content": "Bàn giao 2 máy xoa nền bê tông tự hành tại công trình Hải Dương. Liên hệ hotline: 0988123456.",
  "published_at": "2026-09-17T07:45:00.000Z",
  "raw_payload": {
    "id": "post_1092837465_987654321",
    "message": "Bàn giao 2 máy xoa nền bê tông tự hành tại công trình Hải Dương. Liên hệ hotline: 0988123456.",
    "created_time": "2026-09-17T07:45:00.000Z",
    "reactions": { "summary": { "total_count": 48 } }
  },
  "collected_at": "2026-09-17T07:50:00.000Z"
}
```

* Đối với bình luận (`item_type = 'COMMENT'`), `external_parent_id` lưu `post_id` (hoặc `parent_comment_id` nếu là comment cấp 2).

---

## 3. Phân loại Lỗi & Ma trận Chuyển đổi Trạng thái (Error Classification Matrix)

Hệ thống phân loại lỗi nghiêm ngặt và không thực hiện retry mù quáng:

| Mã phản hồi | Phân loại | Retryable? | Xử lý & Chuyển đổi Trạng thái Nguồn (`facebook_sources`) |
| :---: | :---: | :---: | :--- |
| **HTTP 429** / Meta code 4, 17, 32, 613 | `RATE_LIMIT` | Có (sau backoff) | **Không retry ngay.** Tính `backoff_until = NOW() + (2^limits * 120s)`. Tăng `consecutive_rate_limits += 1`. Nếu $\ge 3$ lần $\rightarrow$ Chuyển `status = 'RATE_LIMITED'`. |
| **HTTP 401** / Meta code 190 | `AUTH_ERROR` | Không | Chuyển ngay lập tức `status = 'AUTH_ERROR'`. Bắn cảnh báo Admin gia hạn Token. |
| **HTTP 403** / Meta code 10, 200 | `PERMISSION_ERROR`| Không | Chuyển ngay lập tức `status = 'PERMISSION_ERROR'`. Không tiếp tục quét. |
| **HTTP 5xx** / Meta code 1, 2 | `SERVER_ERROR` | Có | Tăng `consecutive_errors += 1`. Nếu $\ge 5$ lỗi liên tiếp $\rightarrow$ Tự động chuyển `status = 'PAUSED'`. |
| **Timeout (HTTP 408)** | `TIMEOUT` | Có | Timeout sau 15 giây. Kích hoạt backoff và tăng `consecutive_errors += 1`. |
| **Khác** | `UNKNOWN` | Tùy trường hợp | Lưu chi tiết vào bảng `facebook_errors` để đối soát. |

---

## 4. Các Module Mã nguồn Đã Xây dựng (Source Code)

Toàn bộ mã nguồn Phase 3 được tổ chức trong thư mục `/home/ADMIN/collector/`:

1. **`interface.js`:** Lớp trừu tượng `CollectorAdapter` định nghĩa phương thức `collect(sourceConfig)` và hợp đồng Envelope Schema.
2. **`error_classifier.js`:** Module phân loại lỗi HTTP status, mã lỗi Meta, thuật toán Exponential Backoff with Jitter và hàm quyết định chuyển đổi trạng thái nguồn `evaluateSourceErrorTransition()`.
3. **`facebook_adapter.js`:** Adapter Facebook Graph API chính thức (hỗ trợ phân trang incremental, con trỏ `since`, timeout 15s qua `AbortController`, phân giải token động không hard-code).
4. **`mock_adapter.js`:** Mock Adapter phục vụ kiểm thử tích hợp tự động và mô phỏng tiêm lỗi (Error Injection: 429, 401, 403, 500, timeout).
5. **`ingestion_engine.js`:** Bộ điều khiển đường ống nạp dữ liệu: kiểm tra cờ `FB_GLOBAL_COLLECTION_ENABLED`, bảo toàn dữ liệu thô với mã băm SHA-256 (`payload_hash`), nạp bài viết/bình luận, cập nhật checkpoint và ghi log kiểm toán.

---

## 5. Workflow n8n: Facebook Collector & Ingestion Queue

Workflow đã được xuất file JSON tại `/home/ADMIN/n8n/data/workflow_collector_queue.json` và **import trực tiếp vào n8n**:

🔗 **Tên workflow:** `[FB LEAD INTEL] - 02 Facebook Collector & Ingestion Queue`  
🔗 **Mã định danh (ID):** `FB_COLLECTOR_QUEUE_V1`  
🔗 **Link truy cập:** `https://feb-bookmark-foot-grateful.trycloudflare.com/workflow/FB_COLLECTOR_QUEUE_V1`

### Các Node chính:
* **Node 1 & 2 (`verify-gatekeeper-status` & `is-collection-permitted`):** Kiểm tra cờ Master Kill Switch và trạng thái của source trước khi thực thi.
* **Node 3 (`execute-collector-adapter`):** Gọi Collector Adapter thu thập và chuẩn hóa dữ liệu.
* **Node 4 (`hash-and-normalize-envelope`):** Tính toán mã băm SHA-256 cho từng raw payload.
* **Node 5 (`insert-immutable-raw-item`):** Ghi vào `public.facebook_raw_items` với cơ chế `ON CONFLICT (payload_hash) DO NOTHING` bảo vệ dữ liệu thô không bao giờ bị ghi đè.
* **Node 6 (`advance-checkpoint-cursor`):** Cập nhật con trỏ `last_cursor` mới nhất vào bảng `facebook_sources` và reset bộ đếm lỗi.
* **Node 7 (`log-collection-success`):** Ghi nhận nhật ký lượt quét vào bảng `public.facebook_collection_logs`.
* **Node 8 (`output-normalized-envelope`):** Xuất mảng Envelope chuẩn hóa sẵn sàng cho các phase phân tích tiếp theo.

---

## 6. Kết quả Kiểm thử Tích hợp (Integration Test Results)

Script kiểm thử: `/home/ADMIN/test_collector_integration.py`
Kết quả: **5/5 Tests PASSED (100%)**

* ✅ **Test 1:** Xác thực cấu trúc Normalized Envelope chứa đầy đủ 11 trường bắt buộc.
* ✅ **Test 2:** Xác thực tính bất biến (Raw Immutability) và khả năng chống trùng lặp tuyệt đối qua mã băm SHA-256 (`ON CONFLICT DO NOTHING`).
* ✅ **Test 3:** Xác thực tịnh tiến con trỏ Checkpoint (`last_cursor`).
* ✅ **Test 4:** Xác thực ma trận phân loại lỗi và chuyển đổi trạng thái (`429` $\rightarrow$ `RATE_LIMITED`, `401` $\rightarrow$ `AUTH_ERROR`, `5 errors` $\rightarrow$ `PAUSED`).
* ✅ **Test 5:** Xác thực ghi nhận vết kiểm toán vào bảng `facebook_collection_logs`.
