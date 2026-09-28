# Facebook Lead Intelligence V1 - Phase 8: Lead Notification Engine

## 1. Mục Tiêu & Tiêu Chuẩn Thông Báo

Phase 8 đảm nhận vai trò phát tán thông báo tức thời (Real-time Lead Notification) đến kênh Telegram / CRM khi phát hiện khách hàng tiềm năng đạt tiêu chuẩn phân loại.

### 1.1. Điều kiện kích hoạt thông báo (Eligibility Filter):
Hệ thống chỉ gửi notification khi lead thỏa mãn ít nhất một trong các điều kiện:
- `lead_score >= LEAD_NOTIFICATION_MIN_SCORE` (Mặc định: $\ge 60$ điểm).
- `primary_intent = 'REQUEST_QUOTE'` (Báo giá ưu tiên hàng đầu, bất kể điểm số).
- Lead không thuộc diện `SPAM`.

---

## 2. Định Dạng Bản Tin Telegram & Quy Chuẩn Xử Lý Thiếu Dữ Liệu

### 2.1. Cấu trúc nội dung chuẩn:
```markdown
🎯 *[CƠ HỘI KINH DOANH MỚI - FACEBOOK LEAD]*
━━━━━━━━━━━━━━━━━━━━━━━━━━
🆔 *Lead ID:* `{lead_id}`
👤 *Tên:* {full_name or "-"}
🏢 *Company:* {company_name or "-"}
📞 *Phone:* `{primary_phone or "-"}`
📧 *Email:* {primary_email or "-"}
📍 *Location:* {location or "-"}
🏗️ *Product:* {product_interest or "-"}
📦 *Quantity:* {quantity or "-"}
📝 *Requirement:* {requirement or "-"}
🎯 *Intent:* `{primary_intent or "-"}`
⭐ *Score:* *{lead_score}*
🏷️ *Score Band:* `{lead_tier or "-"}`
🌐 *Facebook Source:* {source_name or "-"}
🔗 *Source URL:* {source_url}
⏰ *Detected Time:* `{detected_time}`
━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 2.2. Quy tắc bắt buộc:
1. **Không tự tạo thông tin còn thiếu:** Nếu field bị `null`, rỗng hoặc không xác định, **bắt buộc hiển thị dấu `-`**.
2. **Luôn có link bài đăng gốc (`Source URL`):** Giúp bộ phận kinh doanh có thể nhấp trực tiếp vào bài viết Facebook để tương tác ngay lập tức.

---

## 3. Cơ Chế Chống Trùng Lặp Thông Báo (Anti-Duplicate Notification)

- **Cửa sổ Cooldown (24 giờ):** Hệ thống kiểm tra lịch sử gửi trong bảng `lead_events` (`event_type = 'DISPATCHED_TELEGRAM'`) và `lead_notification_queue`.
- Nếu cùng một Lead đã được gửi thông báo trong vòng 24 giờ qua, hệ thống tự động bỏ qua (`SKIPPED_COOLDOWN`), ngăn chặn việc spam tin nhắn làm phiền đội ngũ bán hàng.

---

## 4. Chịu Lỗi & Hàng Đợi Gửi Bù (Retry Queue & Resilience)

Khi cổng Telegram hoặc CRM gặp sự cố (mất mạng, 429, timeout, 5xx):
- **Không bao giờ làm mất lead:** Tín hiệu được lưu an toàn trong bảng `lead_notification_queue`.
- **Thử lại có giới hạn:** Hệ thống tự động thử lại tối đa 3 lần với cơ chế giãn cách thời gian (`next_retry_at = NOW() + INTERVAL '10 minutes'`).
- **Ghi nhận kiểm toán:** Sự cố được ghi nhận vào `facebook_errors` và `lead_events` (`NOTIFICATION_FAILED`).

---

## 5. Cấu Hình Linh Hoạt (Public Flags & Credentials)

- `LEAD_NOTIFICATION_ENABLED`: Cờ bật/tắt toàn cục tính năng gửi thông báo.
- `LEAD_NOTIFICATION_MIN_SCORE`: Ngưỡng điểm tối thiểu để thông báo (mặc định: 60).
- **Tuyệt đối không hard-code thông tin nhạy cảm:** Token bot và Chat ID được nạp linh hoạt qua biến môi trường (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) hoặc tải từ bảng `system_flags`.
