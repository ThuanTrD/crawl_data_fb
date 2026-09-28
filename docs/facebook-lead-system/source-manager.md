# Đặc tả Kỹ thuật: Facebook Source Manager Workflow (Phase 2)

Workflow **`[FB LEAD INTEL] - 01 Facebook Source Manager`** (ID: `FB_SOURCE_MANAGER_V1`) chịu trách nhiệm nạp, sàng lọc, xếp thứ tự ưu tiên và điều phối danh sách các nguồn Facebook (Fanpage, Group, Authorized Feed) đủ điều kiện vào hàng đợi thu thập mà không hard-code bất kỳ nguồn nào.

---

## 1. Bản đồ Luồng Xử lý (Workflow Visual Flow)

```
[Manual Trigger] ──────┐
                       ▼
[Schedule Trigger] ──> [Node 1: Kiểm Tra Kill Switch]
                             │
                             ▼
                       [Node 2: If Kill Switch OFF?] ──(False)──> [Node 2B: Dừng & Ghi Log Halted]
                             │ (True)
                             ▼
                       [Node 3: Tải Danh Sách Sources Hợp Lệ & Xếp Hạng Yield]
                             │
                             ▼
                       [Node 4: If Có Nguồn Đủ Điều Kiện?] ──(False)──> [Node 4B: Dừng & Ghi Log Idle]
                             │ (True)
                             ▼
                       [Node 5: Phân Phối Hàng Đợi & Sinh Batch Token]
                             │
                             ▼
                       [Node 6: Cập Nhật next_run_at Vào DB (Chống Quét Trùng)]
                             │
                             ▼
                       [Node 7: Ghi Nhật Ký Dispatch Vào facebook_collection_logs]
                             │
                             ▼
                       [Node 8: Xuất Danh Sách Hàng Đợi Hoàn Tất (Queue Output)]
```

---

## 2. Chi tiết Từng Node trong Workflow

### Node 1: Kiểm Tra Kill Switch & Circuit Breaker (`check-kill-switch`)
* **Loại node:** `n8n-nodes-base.postgres` (Version 2.5)
* **Chức năng:** Truy vấn bảng `public.system_flags` để đọc trạng thái cờ `FB_GLOBAL_COLLECTION_ENABLED`.
* **Query SQL:**
  ```sql
  SELECT 
    flag_value, 
    state, 
    (flag_value = TRUE AND state = 'CLOSED') AS is_collection_allowed,
    description
  FROM public.system_flags
  WHERE id = 'FB_GLOBAL_COLLECTION_ENABLED';
  ```

### Node 2: Cho phép Thu thập? (`is-kill-switch-active`)
* **Loại node:** `n8n-nodes-base.if` (Version 2)
* **Điều kiện:** `{{ $json.is_collection_allowed === true }}`
* **Nhánh True:** Tiếp tục chuyển sang Node 3.
* **Nhánh False:** Rẽ nhánh sang `log-kill-switch-halt`, trả về thông báo ngắt an toàn, không gọi database hay hạ tầng phía sau.

### Node 3: Tải Danh Sách Sources Hợp Lệ & Ưu Tiên Yield (`fetch-eligible-sources`)
* **Loại node:** `n8n-nodes-base.postgres` (Version 2.5)
* **Chức năng:** Lọc động 100% từ bảng `facebook_sources` thỏa mãn tất cả tiêu chí an toàn:
  1. `enabled = TRUE` (Bật cấp nguồn).
  2. `status = 'ACTIVE'` (Tuyệt đối không lấy `PAUSED`, `RATE_LIMITED`, `BLOCKED`, `DISABLED`, `AUTH_ERROR`...).
  3. `next_run_at <= NOW()` (Đã đến giờ chạy chu kỳ tiếp theo).
  4. `backoff_until IS NULL OR backoff_until <= NOW()` (Đã hết thời gian lùi trễ).
  5. `circuit_breaker_tripped = FALSE` (Nguồn chưa bị ngắt mạch).
* **Xếp hạng:** `ORDER BY yield_score DESC, leads_yield_count DESC, next_run_at ASC` (Nguồn nào trong lịch sử cho ra nhiều lead chất lượng cao hơn sẽ được ưu tiên quét trước).

### Node 4: Có Nguồn Nào Đủ Điều Kiện? (`has-eligible-sources`)
* **Loại node:** `n8n-nodes-base.if` (Version 2)
* **Điều kiện:** Kiểm tra có ít nhất 1 source_id hợp lệ.
* **Nhánh False:** Chuyển sang `log-no-sources`, kết thúc chu kỳ ở trạng thái `IDLE`.

### Node 5: Phân Phối Hàng Đợi & Lên Lịch Đợt Tới (`prioritize-and-enqueue`)
* **Loại node:** `n8n-nodes-base.code` (Version 2)
* **Chức năng:** Đóng gói metadata thành item queue chuẩn, sinh `batch_token` duy nhất, chuẩn bị payload cho bước ghi nhận tiếp theo.

### Node 6: Cập Nhật next_run_at Trong DB (`update-next-run`)
* **Loại node:** `n8n-nodes-base.postgres` (Version 2.5)
* **Chức năng:** Đẩy thời gian chạy tiếp theo `next_run_at = NOW() + collection_interval_seconds` ngay lập tức để khóa nguồn, chống race-condition hoặc quét lặp khi có nhiều worker chạy đồng thời.

### Node 7: Ghi Log Dispatch Vào `facebook_collection_logs` (`log-dispatch-audit`)
* **Loại node:** `n8n-nodes-base.postgres` (Version 2.5)
* **Chức năng:** Ghi nhật ký phân phối vào bảng audit, lưu con trỏ bắt đầu (`checkpoint_cursor_start = last_cursor`), mã trạng thái HTTP 200.

### Node 8: Xuất Danh Sách Hàng Đợi Hoàn Tất (`final-queue-summary`)
* **Loại node:** `n8n-nodes-base.code` (Version 2)
* **Chức năng:** Tổng hợp kết quả đầu ra chứa danh sách mảng các source đã được phân phối thành công vào hàng đợi, sẵn sàng làm đầu vào cho Phase 3 (Collector).

---

## 3. Tổng kết Kết quả Test Suite (Automated Verification)

Script kiểm thử tự động: `/home/ADMIN/test_source_manager.py`
Kết quả: **5/5 Tests PASSED (100%)**

1. **Test 1 - Global Kill Switch:** Đổi cờ `FB_GLOBAL_COLLECTION_ENABLED` sang `FALSE` -> Ngắt lập tức. Đổi lại `TRUE` -> Mở lại bình thường.
2. **Test 2 - Eligibility Filtering:** Trong 9 nguồn mock, hệ thống lọc đúng duy nhất 2 nguồn `ACTIVE` đến hạn, loại bỏ triệt để 7 nguồn không đủ điều kiện (`disabled`, `paused`, `rate_limited`, `blocked`, `auth_error`, `future_next_run`, `backoff_cooldown`).
3. **Test 3 - Yield Prioritization:** Nguồn `mock_page_robot_hot` (yield 9.80) được xếp trên `mock_page_cad_vietnam` (yield 5.20).
4. **Test 4 - Schedule Bump & Audit Log:** Cập nhật chính xác `next_run_at` và sinh bản ghi log trong `facebook_collection_logs`.
5. **Test 5 - Queue Idempotency:** Chạy lại ngay lập tức không sinh trùng lặp nguồn.
