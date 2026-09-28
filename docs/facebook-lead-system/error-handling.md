# Quản trị Lỗi, Giám sát, Circuit Breaker & Kill Switch

Tài liệu chi tiết về cơ chế kiểm soát sự cố, thuật toán Exponential Backoff, cơ chế tự ngắt mạch (Circuit Breaker) và nút dừng khẩn cấp (Kill Switch) bảo vệ hệ thống Facebook Lead Intelligence V1.

---

## 1. Phân loại Lỗi (Error Taxonomy)

Hệ thống phân loại toàn bộ các lỗi phát sinh thành 5 nhóm chính để áp dụng chiến lược xử lý tương ứng:

| Mã nhóm | Loại lỗi | Dấu hiệu nhận diện | Chiến lược phản ứng (Strategy) |
| :--- | :--- | :--- | :--- |
| **ERR_RATE_LIMIT** | Vượt hạn ngạch truy cập | HTTP `429`, Meta error codes `4`, `17`, `32`, `613` | Exponential Backoff with Jitter, tạm dừng source |
| **ERR_AUTH_EXPIRED**| Token hết hạn / Mất quyền | HTTP `401`, `403`, Meta error code `190` | Chuyển trạng thái `token_expired`, bắn cảnh báo Admin |
| **ERR_UPSTREAM_AI** | Lỗi dịch vụ AI (Qwen) | HTTP `500`, `502`, `504`, Timeout > 30s | Fallback sang Rule-based Regex, xếp hàng đợi thử lại |
| **ERR_NETWORK_DISP**| Lỗi mạng Telegram / CRM | HTTP `408`, `503`, Connection reset | Retry tối đa 3 lần với khoảng cách tăng dần |
| **ERR_DATA_INVALID**| Lỗi định dạng dữ liệu | JSON cú pháp hỏng, thiếu trường bắt buộc | Chuyển thẳng vào **Dead-Letter Queue (DLQ)** |

---

## 2. Thuật toán Exponential Backoff with Full Jitter

Khi gặp lỗi tạm thời (`ERR_RATE_LIMIT`, `5xx`), hệ thống áp dụng thuật toán lùi thời gian ngẫu nhiên (Full Jitter) để tránh hiện tượng "bão request" (Thundering Herd):

$$T_{\text{wait}} = \text{random}(0, \min(T_{\max}, T_{\text{base}} \times 2^{\text{attempt}}))$$

* $T_{\text{base}} = 2\text{ giây}$ (Thời gian lùi cơ sở).
* $T_{\max} = 300\text{ giây}$ (Thời gian trễ tối đa 5 phút).
* $\text{attempt}$: Số lần thử lại (tối đa 5 lần).
* Nếu sau 5 lần vẫn không thành công -> Kích hoạt ghi nhận lỗi vào `system_circuit_breaker`.

---

## 3. Cơ chế Tự ngắt mạch: Circuit Breaker State Machine

Để bảo vệ server và ngăn ngừa tài khoản Facebook bị khóa do gửi request liên tục trong tình trạng lỗi:

```
          ┌───────────────────────────┐
          │          CLOSED           │  (Hệ thống vận hành bình thường)
          └─────────────┬─────────────┘
                        │ Failure Count >= 5 trong 5 phút
                        ▼
          ┌───────────────────────────┐
          │           OPEN            │  (Tự ngắt mọi request mới,
          └─────────────┬─────────────┘   chuyển sang chế độ ngủ đông 300s)
                        │ Sau 300 giây (Cooldown hết hạn)
                        ▼
          ┌───────────────────────────┐
          │         HALF-OPEN         │  (Cho phép 1 request thăm dò)
          └───────┬───────────▲───────┘
  Thăm dò Thành công │           │ Thăm dò Thất bại
                  │           └───────────┐
                  ▼                       │
          ┌───────────────────────────┐   │
          │          CLOSED           │   │
          └───────────────────────────┘   │
                  ▲                       │
                  └───────────────────────┘
```

### Bảng trạng thái (`system_circuit_breaker`):
1. **CLOSED (Bình thường):** Dữ liệu được tiếp nhận và xử lý bình thường.
2. **OPEN (Ngắt mạch):** Khi số lỗi liên tiếp vượt quá `failure_threshold = 5` hoặc phát hiện cờ rate limit:
   * Toàn bộ Poller dừng gọi Facebook API.
   * Toàn bộ Webhook chỉ phản hồi HTTP `200 OK` (để Facebook không hủy webhook) nhưng chỉ ghi nhận raw vào hàng đợi, không kích hoạt AI.
   * Bắn cảnh báo khẩn cấp tới Telegram Admin.
3. **HALF-OPEN (Thử nghiệm hồi phục):** Sau `cooldown_seconds = 300s`, hệ thống cho phép 1 request kiểm tra. Nếu thành công -> reset `failure_count = 0` và chuyển về `CLOSED`. Nếu thất bại -> chuyển lại `OPEN` thêm 300s.

---

## 4. Nút dừng Khẩn cấp: Emergency Kill Switch

Trong trường hợp phát hiện sự cố nghiêm trọng (ví dụ: vòng lặp vô tận, sự cố bảo mật token, hoặc lệnh khẩn cấp từ người quản trị):

### 4.1. Kích hoạt qua Database SQL:
```sql
UPDATE public.system_circuit_breaker 
SET kill_switch_active = TRUE, 
    reason = 'Manual admin shutdown via emergency SQL command',
    updated_at = NOW()
WHERE id = 'fb_ingestion_global';
```
Ngay khi cờ `kill_switch_active = TRUE`, mọi workflow trong n8n khi bắt đầu chạy đều đọc bản ghi này và lập tức dừng lại ở bước đầu tiên, không thực thi bất kỳ thao tác nào tiếp theo.

### 4.2. Khôi phục hoạt động:
```sql
UPDATE public.system_circuit_breaker 
SET kill_switch_active = FALSE,
    state = 'CLOSED',
    failure_count = 0,
    reason = 'Admin restored service',
    updated_at = NOW()
WHERE id = 'fb_ingestion_global';
```

---

## 5. Hàng đợi Chết: Dead-Letter Queue (DLQ)

Mọi bản ghi dữ liệu thô gặp lỗi phân tích (ví dụ: JSON hỏng, lỗi parse AI không hợp lệ) không bị xóa bỏ mà được đánh dấu trong bảng `raw_fb_payloads`:
* `processed_status = 'failed'`
* `processing_error = 'Lỗi chi tiết: Stack trace...'`

Admin có thể xem danh sách các payload lỗi bất kỳ lúc nào bằng truy vấn:
```sql
SELECT id, source_id, processing_error, received_at 
FROM public.raw_fb_payloads 
WHERE processed_status = 'failed' 
ORDER BY received_at DESC 
LIMIT 20;
```
Khi lỗi được khắc phục (ví dụ: sửa prompt AI hoặc điều chỉnh regex), Admin chỉ cần cập nhật `processed_status = 'pending'`, n8n sẽ tự động chạy lại các bản ghi này mà không mất dữ liệu.
