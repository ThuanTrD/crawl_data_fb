# Facebook Lead Intelligence V1 - Phase 6: Lead Scoring, Deduplication & Provenance Engine

## 1. Mục Tiêu & Kiến Trúc

Phase 6 chịu trách nhiệm tiếp nhận các tín hiệu (`facebook_lead_signals`) đã được AI và Rule Engine phát hiện từ Phase 5, sau đó:
1. **Chấm điểm đa chiều (Multi-Dimensional Scoring):** Thang điểm 0 - 100 dựa trên Intent, Contact Completeness, Customer Profile, và Context Richness.
2. **Phân hạng Lead (Tiering):**
   - **`HOT` (Score $\ge 75$):** Khách hàng có nhu cầu khẩn cấp, xin báo giá mua thiết bị/phần mềm/vật liệu lớn, có số điện thoại/email trực tiếp. Đủ điều kiện chuyển tiếp ngay sang Telegram / CRM (Phase 7).
   - **`WARM` ($50 \le \text{Score} < 75$):** Khách hàng có nhu cầu tìm dịch vụ, tư vấn kỹ thuật, có phương thức liên hệ cơ bản.
   - **`COLD` (Score $< 50$):** Bài viết/bình luận mang tính thảo luận kỹ thuật, hỏi kinh nghiệm, thông tin chung hoặc thiếu phương thức liên lạc.
3. **Khử trùng lặp thực thể & Phân giải định danh (Deduplication & Entity Resolution):**
   - Tạo `dedup_fingerprint` (chuẩn băm 32-character MD5).
   - Thứ bậc nhận diện: `PHONE` (ưu tiên 1) $\to$ `EMAIL` (ưu tiên 2) $\to$ `AUTHOR_ID:SOURCE_ID` (ưu tiên 3).
   - Phân loại trạng thái phân giải (`resolution`):
     - `NEW`: Lead lần đầu xuất hiện trong hệ thống.
     - `EXISTING_LEAD`: Tín hiệu mới từ lead đã có sẵn (ghép signal mới vào hồ sơ, nâng điểm nếu có tín hiệu mạnh hơn).
     - `EXISTING_CUSTOMER`: Khách hàng cũ cần hỗ trợ kỹ thuật hoặc bảo hành.
     - `POSSIBLE_DUPLICATE`: Trùng lặp tác giả trên cùng một nguồn bài viết.
4. **Bảo toàn nguồn gốc & Kiểm toán (Full Provenance & Audit Trail):**
   - Lưu trữ bản đồ nguồn gốc vào bảng `lead_sources`.
   - Lưu trữ lịch sử từng lần chấm điểm vào `lead_scores`.
   - Ghi nhận nhật ký sự kiện vào `lead_events` (`LEAD_CREATED`, `SIGNAL_ATTACHED`, `SCORE_UPDATED`).
   - Cập nhật trạng thái `facebook_lead_signals` thành `CONVERTED_TO_LEAD`, `MERGED`, hoặc `DISCARDED`.

---

## 2. Ma Trận Chấm Điểm (Scoring Matrix)

Hệ thống tính điểm độc lập theo 4 nhóm tiêu chí:

### 2.1. Intent Score (Tối đa 50 điểm)
| Ý định thương mại (`intent`) | Điểm cơ sở | Mô tả |
|---|:---:|---|
| `URGENT_NEED` | 50 | Cần gấp trong ngày (bơm bê tông, máy xoa nền sự cố, vật liệu công trình khẩn) |
| `REQUEST_QUOTE` | 45 | Yêu cầu báo giá chính thức, hỏi giá máy móc, phần mềm, vật liệu |
| `LOOKING_TO_BUY` | 40 | Đang tìm mua máy, vật tư, bản quyền phần mềm |
| `LOOKING_FOR_SERVICE` | 38 | Cần tìm thầu phụ, thiết kế, thi công, bóc tách dự toán |
| `PARTNERSHIP` | 25 | Đề xuất làm đại lý, hợp tác phân phối thiết bị/phần mềm |
| `HIRING` | 15 | Tuyển dụng kỹ sư, nhân lực công trường |
| `RESEARCH` / `COMPARISON` | 10 | So sánh giải pháp kỹ thuật, tìm hiểu phần mềm |
| `RECOMMENDATION` | 10 | Nhờ tư vấn giải pháp |
| `EXISTING_CUSTOMER` | 10 | Khách hàng cũ hỏi hỗ trợ |
| `DISCUSSION` / `INFORMATION` | 5 | Thảo luận kiến trúc/kỹ thuật thông thường |
| `IGNORE` | 0 | Không liên quan, tự động discard |

### 2.2. Contact Completeness Score (Tối đa 30 điểm)
| Tiêu chí | Điểm cộng | Ghi chú |
|---|:---:|---|
| Có số điện thoại hợp lệ (`extracted_phones`) | +20 | Trích xuất chuẩn số điện thoại VN (10 chữ số) |
| Có địa chỉ email hợp lệ (`extracted_emails`) | +10 | Chuẩn RFC email |

### 2.3. Customer Profile Score (Tối đa 10 điểm)
| Tiêu chí | Điểm cộng | Ghi chú |
|---|:---:|---|
| Có tên công ty/pháp nhân (`company`) | +5 | Tổ chức, nhà thầu, công ty xây dựng (`customer_type = 'BUSINESS'`) |
| Có tên người liên hệ cụ thể (`customer_name`) | +5 | Xưng hô hoặc thông tin người phụ trách |

### 2.4. Context & Actionability Score (Tối đa 10 điểm)
| Tiêu chí | Điểm cộng | Ghi chú |
|---|:---:|---|
| Có số lượng cụ thể (`quantity`) | +3 | Ví dụ: "2 máy", "500m2", "100 tấn" |
| Có địa điểm công trình cụ thể (`location`) | +3 | Ví dụ: "Hà Nội", "Hưng Yên", "Bình Dương" |
| Có yêu cầu chi tiết/tiến độ/ngân sách | +4 | `requirement`, `timeline`, `budget` |

$$\text{Total Score} = \min(100, \text{Intent} + \text{Contact} + \text{Profile} + \text{Context})$$

---

## 3. Workflow n8n: `FB_LEAD_SCORING_V1`

* **Workflow ID:** `FB_LEAD_SCORING_V1`
* **Tên hiển thị:** `[FB LEAD INTEL] - 05 Lead Scoring, Deduplication & Provenance Engine`
* **Cơ chế kích hoạt:**
  * Schedule Trigger mỗi 5 phút.
  * Manual Trigger khi cần kích hoạt thủ công.
* **Các bước thực thi:**
  1. `Check Pending Signals`: Truy vấn số lượng signal `status = 'NEW'` từ `facebook_lead_signals`.
  2. `Has Pending Signals? (IF)`: Điều kiện rẽ nhánh nếu pending > 0.
  3. `Run Lead Scoring & Dedup Engine`: Gọi bộ máy xử lý giao dịch `lead_processor.py`.
  4. `Parse Engine Results`: Bóc tách số liệu `created`, `merged`, `discarded`.
  5. `Log Job Metrics`: Ghi nhận tiến trình vào `facebook_processing_jobs`.
