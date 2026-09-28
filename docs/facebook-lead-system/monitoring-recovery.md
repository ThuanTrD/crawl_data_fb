# Facebook Lead Intelligence V1 - Phase 7: Monitoring + Recovery Architecture

## 1. Mục Tiêu & Cơ Chế Vận Hành

Phase 7 hoàn thiện lớp giám sát tự động (Monitoring), phản ứng sự cố (Incident Detection) và khôi phục có kiểm soát (Controlled Recovery) cho toàn bộ hệ thống Facebook Lead Intelligence V1.

### 1.1. Các sự cố được giám sát liên tục:
- **Lỗi Facebook Graph API:** `429` (Rate limit), `401` (Unauthorized/Token expired), `403` (Forbidden/Permission missing), `5xx` (Server error).
- **Lỗi mạng & hạ tầng:** `Timeout`, `Collector failure`, `Database failure`.
- **Lỗi xử lý & Cổng AI:** `Processing backlog quá lớn`, `AI failure tăng mạnh / Circuit breaker mở`.
- **Bất thường dữ liệu:** `Duplicate spike`, `Spam spike`, `Chất lượng nguồn suy giảm`.

---

## 2. Máy Trạng Thái Nguồn (Source State Machine)

Hệ thống điều khiển trạng thái từng nguồn dữ liệu qua 8 trạng thái xác định:

```
                  ┌───────────────┐
                  │    ACTIVE     │ ◄── (Controlled Recovery khi hết backoff_until)
                  └──────┬────────┘
                         │ 
        ┌────────────────┼────────────────┐
        │ (5xx / Timeout)│ (HTTP 429)     │ (401 / 403 / BLOCKED)
        ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌───────────────────┐
│  TEMP_ERROR  │ │ RATE_LIMITED │ │ AUTH/PERMISSION/  │
│ (Exp.Backoff)│ │ (60m Cooldown│ │      BLOCKED      │
└──────┬───────┘ └──────┬───────┘ └─────────┬─────────┘
       │                │                   │
       │ (>= 5 errors)  │ (>= 3 errors)     │ (Chuyển ngay lập tức)
       └────────────────┼───────────────────┘
                        ▼
                 ┌───────────────┐
                 │    PAUSED     │ (Dừng thu thập, yêu cầu Admin can thiệp)
                 └───────────────┘
```

### Nguyên tắc phục hồi có kiểm soát (Controlled Recovery):
- Chỉ tự động phục hồi về `ACTIVE` đối với các nguồn ở trạng thái `RATE_LIMITED` hoặc `TEMP_ERROR` khi mốc thời gian `NOW() >= backoff_until`.
- **Tuyệt đối không spam retry** hoặc tự động kích hoạt lại các nguồn đang ở `PAUSED`, `AUTH_ERROR`, `PERMISSION_ERROR`, `BLOCKED`, `DISABLED`.

---

## 3. Chỉ Số Vận Hành & Báo Cáo Sức Khỏe (Health Summary)

Hệ thống đo lường 10 chỉ số sức khỏe định kỳ:

| Chỉ số | Mô tả |
|---|---|
| `sources_active` | Số lượng Facebook Page/Group đang thu thập bình thường |
| `sources_paused` | Số lượng nguồn đang tạm dừng (cần can thiệp cấu hình) |
| `sources_rate_limited` | Số lượng nguồn đang chờ hết hạn cooldown 429 |
| `posts_collected` | Tổng số bài viết Facebook đã cào về |
| `posts_relevant` | Số bài viết có nội dung kỹ thuật/xây dựng phù hợp |
| `leads_detected` | Số tín hiệu tiềm năng đã phát hiện |
| `qualified_leads` | Số khách hàng tiềm năng chất lượng cao (`HIGH`, `VERY_HIGH`, `HOT`) |
| `errors` | Tổng số lỗi phát sinh trong 24 giờ qua |
| `429_count` | Số lần chạm giới hạn tần suất trong 24 giờ qua |
| `AI_errors` | Số lỗi cổng AI (timeout / circuit breaker) trong 24 giờ qua |

---

## 4. Đánh Giá Chất Lượng Nguồn Hàng Ngày (Daily Source Quality)

Mỗi ngày, hệ thống tính toán các chỉ số cho từng nguồn trong bảng `facebook_source_metrics`:
- `posts/day`: Số lượng bài viết cào được mỗi ngày
- `relevant_posts/day`: Số bài viết đúng lĩnh vực
- `lead/day`: Số lead thương mại trích xuất được
- `qualified_lead/day`: Số lead chất lượng cao
- `spam_rate`: Tỷ lệ bài rác phi kỹ thuật $\frac{\text{posts} - \text{relevant}}{\text{posts}}$
- `duplicate_rate`: Tỷ lệ bài trùng lặp nội dung
- `error_rate`: Tỷ lệ phát sinh lỗi

> [!NOTE]
> **Quy tắc thiết kế:** Không đưa ra "best source" dưới dạng bảng xếp hạng chủ quan. Hệ thống chỉ cung cấp metric trung thực, khách quan để người vận hành tự phân tích và ra quyết định.

---

## 5. Điều Kiện Cảnh Báo Telegram (Telegram Alert Triggers)

Hệ thống gửi cảnh báo khẩn cấp qua Telegram khi thỏa mãn bất kỳ điều kiện nào sau đây:
1. **Nhiều source bị rate limit:** `sources_rate_limited >= 3`.
2. **Lỗi phân quyền source:** Phát hiện lỗi HTTP 403 (`PERMISSION_ERROR`).
3. **Lỗi xác thực Facebook:** Phát hiện token hết hạn HTTP 401 (`AUTH_ERROR`).
4. **Hàng đợi xử lý quá tải:** `processing_backlog > 200 items`.
5. **Cổng AI gặp sự cố tăng mạnh:** `AI_errors >= 5` trong 24h.
6. **Lỗi cơ sở dữ liệu:** Mất kết nối Supabase hoặc cạn pool kết nối.
7. **Collector chết:** Không có dữ liệu thu thập mới trong hơn 2 giờ khi nguồn đang `ACTIVE`.
8. **Global collection bị disable:** Cờ `FB_GLOBAL_COLLECTION_ENABLED` bị gạt sang `FALSE`.
