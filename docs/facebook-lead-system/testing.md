# Chiến lược & Kịch bản Kiểm thử: Testing Strategy

Tài liệu hướng dẫn quy trình kiểm thử đơn vị (Unit Test), kiểm thử tích hợp (Integration Test), bộ dữ liệu mẫu thực tế ngành xây dựng (Mock Payloads) và phương pháp xác thực tính đúng đắn (Zero-Hallucination Verification).

---

## 1. Kiểm thử Đơn vị: Bộ lọc Regex & Chuẩn hóa Dữ liệu

### 1.1. Test Suite Số điện thoại Việt Nam (Phone Regex Benchmark)
Đoạn mã kiểm thử chạy trực tiếp trên Node.js hoặc n8n Code Node để kiểm chứng độ nhạy của bộ lọc SĐT:

```javascript
const phoneRegex = /(?:0|\+84)(?:3[2-9]|5[2689]|7[06-9]|8[1-9]|9[0-46-9])[0-9]{7}\b/g;

function normalizePhone(v) {
  if (!v) return null;
  let p = v.replace(/[^\d+]/g, '');
  if (p.startsWith('+84')) p = '0' + p.slice(3);
  else if (p.startsWith('84')) p = '0' + p.slice(2);
  return p;
}

const testCases = [
  { input: "Báo giá cho tôi vào số 0988123456 nhé", expected: "0988123456" },
  { input: "Liên hệ: +84 912.345.678 gặp Hùng", expected: "0912345678" },
  { input: "SĐT em: 0868-999-888 cần tư vấn máy xoa nền", expected: "0868999888" },
  { input: "Dự án diện tích 10000m2 giá 500000000 đ", expected: null }, // Không được nhầm diện tích/giá tiền thành SĐT
  { input: "Số nhà 123 đường 456 quận 7", expected: null }
];

testCases.forEach((tc, idx) => {
  const matches = tc.input.replace(/[\s.-]/g, '').match(phoneRegex);
  const result = matches ? normalizePhone(matches[0]) : null;
  console.assert(result === tc.expected, `Test case ${idx + 1} FAILED! Expected: ${tc.expected}, Got: ${result}`);
});
console.log("All Phone Regex Unit Tests PASSED!");
```

---

## 2. Dữ liệu Mẫu Thực tế Ngành Xây dựng (Mock Test Vectors)

Hệ thống được kiểm thử tự động với 4 kịch bản điển hình của ngành Xây dựng:

### Kịch bản 1: Lead HOT - Hỏi Báo giá Robot Xây dựng (Đầy đủ SĐT + Tên Cty)
```json
{
  "post_id": "post_robot_001",
  "page_id": "cic_technology",
  "message": "Trình diễn Robot xoa nền bê tông laser tại công trường KCN VSIP Hải Phòng. Tốc độ xoa 300m2/h, bề mặt phẳng tuyệt đối.",
  "created_time": "2026-09-17T08:00:00Z",
  "comments": [
    {
      "comment_id": "cmt_hot_001",
      "from_name": "Nguyễn Văn Hùng",
      "message": "Tôi bên Công ty Xây dựng Coteccons, đang cần báo giá 2 máy xoa nền này để đổ sàn 50.000m2 tháng sau. Gọi số 0988.123.456 gặp tôi nhé!",
      "created_time": "2026-09-17T08:15:00Z"
    }
  ]
}
```
* **Kỳ vọng kết quả:**
  * `product_group`: `ROBOT_XAY_DUNG`
  * `product_name`: `Robot xoa nền bê tông`
  * `customer_name`: `Nguyễn Văn Hùng`
  * `company`: `Coteccons`
  * `normalized_phone`: `0988123456`
  * `intent_type`: `request_quote`
  * `lead_score`: `95`
  * `lead_tier`: `HOT`
  * **Hành động:** Kích hoạt gửi Telegram tức thì!

---

### Kịch bản 2: Lead WARM - Hỏi Bản quyền phần mềm enjiCAD (Có Email, chưa có SĐT)
```json
{
  "post_id": "post_cad_002",
  "page_id": "enjicad_vietnam",
  "message": "enjiCAD 2026 chính thức phát hành với tốc độ mở file DWG nhanh gấp 3 lần!",
  "created_time": "2026-09-17T09:00:00Z",
  "comments": [
    {
      "comment_id": "cmt_warm_002",
      "from_name": "KTS. Lê Minh",
      "message": "Bên mình đang dùng AutoCAD đắt quá muốn chuyển 15 máy sang enjiCAD, shop gửi báo giá và link tải dùng thử vào email: minh.le@arcviet.com giúp mình với.",
      "created_time": "2026-09-17T09:20:00Z"
    }
  ]
}
```
* **Kỳ vọng kết quả:**
  * `product_group`: `CAD_SOFTWARE`
  * `product_name`: `enjiCAD`
  * `normalized_phone`: `null` *(Tuyệt đối không tự bịa đặt SĐT)*
  * `normalized_email`: `minh.le@arcviet.com`
  * `requested_quantity`: 15
  * `lead_score`: `75`
  * `lead_tier`: `WARM`
  * **Hành động:** Lưu vào database, bắn thông báo nhóm bán hàng phần mềm.

---

### Kịch bản 3: Lead COLD / Spam - Chào hàng hoặc Bình luận dạo
```json
{
  "post_id": "post_plaxis_003",
  "page_id": "cic_technology",
  "message": "Hội thảo trực tuyến: Ứng dụng PLAXIS 3D trong phân tích móng bè cọc sâu.",
  "created_time": "2026-09-17T10:00:00Z",
  "comments": [
    {
      "comment_id": "cmt_cold_003",
      "from_name": "Bất Động Sản Giá Rẻ",
      "message": "Đất nền sổ đỏ ven biển giá chỉ 500tr/nền, anh em kỹ sư đầu tư liên hệ em nhé!",
      "created_time": "2026-09-17T10:05:00Z"
    }
  ]
}
```
* **Kỳ vọng kết quả:**
  * `lead_score`: `10`
  * `lead_tier`: `COLD`
  * `intent_type`: `general_info` (hoặc `spam`)
  * **Hành động:** Bỏ qua, không bắn thông báo làm phiền nhân viên kinh doanh.

---

### Kịch bản 4: Kiểm thử Khử trùng lặp (Deduplication Test)
Gửi lại Kịch bản 1 lần thứ hai trong vòng 24 giờ.
* **Kỳ vọng kết quả:**
  * Bảng `raw_fb_payloads`: Trùng `payload_hash` -> Bỏ qua (`ON CONFLICT DO NOTHING`).
  * Bảng `fb_leads`: Không phát sinh thêm bản ghi lead mới nào.

---

## 3. Kiểm thử Xác thực Không Ảo giác (Zero-Hallucination Audit)

Để đảm bảo tuân thủ nguyên tắc số 11 và 12 của hệ thống:
1. Chạy 50 mẫu bình luận chỉ có câu hỏi chung chung (ví dụ: *"Phần mềm này hay quá"*, *"Dự án ở đâu vậy"*).
2. Kiểm tra SQL:
   ```sql
   SELECT count(*) FROM public.fb_leads 
   WHERE (normalized_phone IS NOT NULL OR normalized_email IS NOT NULL)
     AND source_entity_id IN ('danh_sách_comment_không_có_sđt');
   ```
3. **Tiêu chuẩn đạt (Acceptance Criteria):** `count(*) = 0`. Nếu lớn hơn 0 nghĩa là AI đang tự suy đoán hoặc hallucinate thông tin -> Buộc phải điều chỉnh lại System Prompt.
