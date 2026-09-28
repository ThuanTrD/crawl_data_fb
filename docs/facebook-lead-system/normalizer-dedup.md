# Phase 4: Normalization & Deduplication Pipeline Documentation

## 1. Tổng quan Kiến trúc (Architecture Overview)

Phase 4 đóng vai trò là tầng chuyển hóa (Transformation & Deduplication Layer) giữa kho dữ liệu thô (`facebook_raw_items`) và kho dữ liệu đã chuẩn hóa (`facebook_posts`, `facebook_comments`), chuẩn bị sẵn sàng cho tầng Trí tuệ nhân tạo & Khai thác Tín hiệu (Phase 5: Signal Extraction & Lead Scoring).

```
+-------------------------------------------------------------+
|             facebook_raw_items (Status: PENDING)             |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|        n8n Workflow: FB_NORMALIZER_DEDUP_V1                 |
|                                                             |
|   1. Unicode NFC Normalization                              |
|   2. Whitespace & Newline Canonicalization                  |
|   3. Vietnamese Diacritics & Meaning Preservation           |
|   4. SHA-256 Content Hashing                                |
|   5. Language Detection (vi, en, other, empty)              |
|   6. Hierarchy Resolution (POST, COMMENT, REPLY)            |
+-------------------------------------------------------------+
                               |
               +---------------+---------------+
               |                               |
        (Valid Item)                   (Malformed Item)
               |                               |
               v                               v
+-----------------------------+ +-----------------------------+
| Level 1 Dedup: External ID  | | Dead-Letter Path:           |
| (post_id / comment_id)      | | - Log to facebook_errors    |
| - If exists: Mark PROCESSED | | - Update raw item: FAILED   |
|   last_error='DUPLICATE_ID' | +-----------------------------+
+-----------------------------+
               |
               v
+-----------------------------+
| Level 2 Dedup: Content Hash |
| (SHA-256 Content Matching)  |
| - If duplicate content found|
|   Flag is_duplicate_content |
|   Set duplicate_of_id       |
+-----------------------------+
               |
               v
+-------------------------------------------------------------+
| PostgreSQL Persistence:                                     |
| - facebook_posts (Upsert ON CONFLICT post_id)               |
| - facebook_comments (Insert ON CONFLICT comment_id)         |
| - Update facebook_raw_items (Status: PROCESSED)             |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Processing Queue (Ready for Phase 5: AI & Lead Extraction)  |
+-------------------------------------------------------------+
```

---

## 2. Tiêu chuẩn Chuẩn hóa Dữ liệu (Normalization Standards)

### 2.1. Unicode NFC
- Toàn bộ chuỗi văn bản được chuẩn hóa qua `String.prototype.normalize('NFC')`.
- Loại bỏ triệt để xung đột giữa tổ hợp phím tiếng Việt Unicode dựng sẵn (NFC) và tổ hợp (NFD), đảm bảo tính đồng nhất khi tạo hash và tìm kiếm.

### 2.2. Chuẩn hóa Whitespace & Newline
- **Khoảng trắng ngang:** Gộp mọi ký tự tab (`\t`), Non-Breaking Space (`\u00A0`), Zero-Width Spaces (`\u200B`, `\u200C`, `\u200D`, `\uFEFF`) và nhiều dấu cách liên tiếp thành 1 dấu cách duy nhất ` `.
- **Xuống dòng:** Quy chuẩn `\r\n` và `\r` về `\n`.
- **Giới hạn khoảng trống đoạn văn:** Rút gọn từ 3 dấu xuống dòng liên tiếp trở lên thành tối đa 2 dấu `\n\n`, vừa giữ nguyên cấu trúc đoạn văn bản vừa loại bỏ các khoảng trắng vô ích do spam.
- **Biên:** Cắt tỉa (`trim()`) khoảng trắng đầu và cuối mỗi dòng và toàn chuỗi.

### 2.3. Bảo tồn tiếng Việt & Ý nghĩa Nguyên bản
- **Tuyệt đối không bỏ dấu tiếng Việt.** Mọi nguyên âm có dấu (`á, à, ả, ã, ạ, ă, ắ, ằ, ẳ, ẵ, ặ, â, ấ, ầ, ẩ, ẫ, ậ, đ, é, è, ẻ, ẽ, ẹ, ê, ế, ề, ể, ễ, ệ, í, ì, ỉ, ĩ, ị, ó, ò, ỏ, õ, ọ, ô, ố, ồ, ổ, ỗ, ộ, ơ, ớ, ờ, ở, ỡ, ợ, ú, ù, ủ, ũ, ụ, ư, ứng, ừ, ử, ữ, ự, ý, ỳ, ỷ, ỹ, ỵ`) được bảo tồn 100%.
- **Không tự ý sửa từ:** Không dùng auto-correct hoặc sửa chính tả làm biến dạng các thuật ngữ kỹ thuật chuyên ngành xây dựng (`ETABS`, `PLAXIS`, `enjiCAD`, `robot xoa nền bê tông`, `GPR`).
- **Emoji & Ký tự đặc biệt:** Bảo toàn UTF-8 4-byte (`🤖`, `🏗️`, `🚀`) và các ký tự toán học, tiền tệ, liên hệ (`$`, `±`, `%`, `@`, `#`).

### 2.4. Mã băm Nội dung (SHA-256 Content Hash)
- Tính toán mã băm SHA-256 từ nội dung đã chuẩn hóa:
  ```javascript
  crypto.createHash('sha256').update(normalizedContent, 'utf8').digest('hex')
  ```
- Chuỗi rỗng cho mã hash chuẩn: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

### 2.5. Nhận diện Ngôn ngữ Tự động (Language Detection)
- Phát hiện ngôn ngữ tốc độ cao, không phụ thuộc thư viện nặng:
  - `vi`: Khớp dấu thanh tiếng Việt hoặc từ khóa B2B xây dựng tiếng Việt (`báo giá`, `tư vấn`, `bê tông`, `dự án`, `thi công`, `liên hệ`,...).
  - `en`: Khớp từ khóa tiếng Anh (`quotation`, `software`, `specifications`, `price`, `contact`,...) và mật độ chữ cái Latin ASCII.
  - `empty`: Chuỗi rỗng hoặc chỉ chứa khoảng trắng.
  - `other`: Ngôn ngữ hoặc ký tự khác.

---

## 3. Cơ chế Khử trùng lặp (Deduplication Mechanism)

### 3.1. Khử trùng lặp Cấp 1: Source + External ID
- Kiểm tra `post_id` trong `facebook_posts` hoặc `comment_id` trong `facebook_comments`.
- **Nếu đã tồn tại:**
  - Raw item được cập nhật trạng thái `PROCESSED`, `last_error = 'DUPLICATE_EXTERNAL_ID'`.
  - Không chèn thêm dòng mới vào bảng bài viết/bình luận.

### 3.2. Khử trùng lặp Cấp 2: Content Hash
- Quét `content_hash` trong các bài viết hoặc bình luận đã lưu.
- **Nếu phát hiện hash trùng khớp:**
  - Gắn cờ `is_duplicate_content = TRUE`.
  - Trỏ `duplicate_of_id` về UUID của bài viết/bình luận gốc xuất hiện đầu tiên.
  - Giúp tầng Lead Intelligence phát hiện bài đăng chéo (cross-post spam), nội dung sao chép giữa các hội nhóm hoặc bình luận spam hàng loạt của bot.

---

## 4. Phân cấp Đối tượng (Hierarchy Resolution)

| Category | Điều kiện nhận diện | Bảng đích | Khóa chính ngoài | Liên kết cha |
|---|---|---|---|---|
| **POST** | `item_type = 'POST'` hoặc không có parent id | `facebook_posts` | `post_id` | `page_id` / `source_id` |
| **COMMENT** | `item_type = 'COMMENT'`, trỏ vào bài viết | `facebook_comments` | `comment_id` | `post_id`, `parent_comment_id = NULL` |
| **REPLY** | `item_type = 'REPLY'` hoặc có `parent_comment_id` | `facebook_comments` | `comment_id` | `post_id`, `parent_comment_id = <parent_id>` |

---

## 5. Xử lý Lỗi Phòng thủ & Dead-Letter Queue

- Toàn bộ quá trình chuẩn hóa được bao bọc bởi khối `try/catch` phòng thủ.
- Một item hỏng (thiếu `external_id`, payload JSON biến dạng, định dạng ngày bất thường) **không bao giờ làm dừng hoặc crash workflow**.
- Item lỗi được định tuyến sang luồng **Dead-Letter**:
  1. Ghi log vào `facebook_errors` với danh mục `DATA_PARSE_ERROR`, mã `NORMALIZATION_FAILED` hoặc `MISSING_EXTERNAL_ID`.
  2. Cập nhật `facebook_raw_items` thành `FAILED`, tăng `processing_attempts`, lưu vết `last_error`.
  3. Cho phép kỹ sư kiểm tra và retry khi cần thiết.

---

## 6. Kết quả Kiểm thử Tích hợp (Test Matrix)

Toàn bộ 10 ca kiểm thử đã thực thi và vượt qua 100% trong môi trường Supabase:

| STT | Kịch bản kiểm thử | Mô tả chi tiết | Kết quả |
|---|---|---|---|
| 1 | `test_1_vietnamese` | Giữ nguyên dấu tiếng Việt NFC, bảo toàn 100% nội dung & ngữ nghĩa | **PASSED** |
| 2 | `test_2_english` | Nhận diện văn bản tiếng Anh chính xác (`en`) | **PASSED** |
| 3 | `test_3_empty_content` | Xử lý nội dung rỗng/null an toàn, sinh hash rỗng chuẩn | **PASSED** |
| 4 | `test_4_emoji` | Bảo toàn ký tự UTF-8 4-byte (`🤖`, `🏗️`, `⚡`, `🚀`) | **PASSED** |
| 5 | `test_5_special_chars` | Bảo toàn ký tự kỹ thuật (`$`, `~`, `±`, `%`, `@`, `#`) | **PASSED** |
| 6 | `test_6_multiline` | Chuẩn hóa thụt lề, tab, xóa `\r`, tối đa 2 `\n\n` | **PASSED** |
| 7 | `test_7_hierarchy` | Phân cấp chuẩn xác POST, COMMENT và REPLY (parent link) | **PASSED** |
| 8 | `test_8_duplicate_external_id` | Chặn trùng lặp external_id, cập nhật trạng thái `DUPLICATE_EXTERNAL_ID` | **PASSED** |
| 9 | `test_9_duplicate_content` | Phát hiện trùng nội dung bằng `content_hash`, gắn `duplicate_of_id` | **PASSED** |
| 10 | `test_10_dead_letter` | Định tuyến item lỗi vào `facebook_errors`, không crash hệ thống | **PASSED** |

---

## 7. Tài nguyên Triển khai

- **Mã nguồn Chuẩn hóa:** `/home/ADMIN/normalizer/normalizer.js` và `/home/ADMIN/normalizer/normalizer.py`
- **Bộ máy Khử trùng:** `/home/ADMIN/normalizer/dedup_engine.py`
- **Workflow n8n:** `/home/ADMIN/n8n/data/workflow_normalizer_dedup.json` (ID: `FB_NORMALIZER_DEDUP_V1`)
- **Bộ kiểm thử Tích hợp:** `/home/ADMIN/test_normalizer_integration.py`
