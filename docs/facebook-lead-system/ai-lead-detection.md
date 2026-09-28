# Phase 5: AI Lead Detection & Intent Extraction

## 1. Tổng quan Kiến trúc (Architecture Overview)

Phase 5 là tầng trí tuệ nhân tạo và khai phá tín hiệu thương mại (AI Intelligence & Signal Extraction Layer) thuộc hệ thống **Facebook Lead Intelligence V1**.

```
+-------------------------------------------------------------+
|               facebook_posts / comments                     |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| 1. KEYWORD FILTER (Chặn rác trước khi gọi AI)                |
|    - Nhóm MUA HÀNG                                          |
|    - Nhóm DỊCH VỤ                                           |
|    - Nhóm VẬT LIỆU                                          |
|    - Nhóm SOFTWARE                                          |
|    - Nhóm CONSTRUCTION                                      |
+-------------------------------------------------------------+
               |                               |
        (Khớp Keyword)                  (Không khớp)
               |                               |
               v                               v
+-----------------------------+ +-----------------------------+
| 2. CONTEXT BUNDLING         | | Bỏ qua hoàn toàn (SKIPPED)  |
| - Nếu là Comment:           | | - Tiết kiệm chi phí AI      |
|   Truy vấn Parent Post      | | - Loại bỏ 100% spam/chém gió|
|   Ghép: Post + Comment      | +-----------------------------+
+-----------------------------+
               |
               v
+-------------------------------------------------------------+
| 3. QWEN AI & HYBRID ENGINE (w/ Circuit Breaker)             |
| - Upstream: Qwen3-VL-30B via LiteLLM API                    |
| - Fallback: Deterministic Rule-Based Construction NLP Engine|
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| 4. ZERO-HALLUCINATION GUARDRAILS & JSON SCHEMA VALIDATION   |
| - Phone: Regex chuẩn Việt Nam (Không suy đoán bừa)          |
| - Email: Regex RFC compliant (Không bịa email)              |
| - Company / Name: Phải có căn cứ rõ ràng trong text        |
| - Missing fields -> null (Tuyệt đối không để placeholder)   |
| - Confidence: Giới hạn chặt chẽ trong khoảng [0.0, 1.0]     |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| 5. POSTGRESQL PERSISTENCE: facebook_lead_signals            |
| (Ghi nhận: ai_model, ai_raw_response, post_id, comment_id,  |
|  source_id, detected_at, intent, product_category,...)      |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Processing Queue -> Sẵn sàng cho Phase 6 (Scoring & CRM)   |
+-------------------------------------------------------------+
```

---

## 2. Bộ Lọc Từ Khóa (Keyword Filter - Pre-AI Gating)

Để tối ưu chi phí và độ trễ, toàn bộ bài viết/bình luận đều phải đi qua bộ lọc từ khóa trước khi kích hoạt AI:

1. **MUA HÀNG:** `báo giá`, `xin giá`, `giá bao nhiêu`, `cần mua`, `đang tìm mua`, `tìm mua`, `ai bán`, `mua ở đâu`, `cần cung cấp`.
2. **DỊCH VỤ:** `cần thiết kế`, `cần thi công`, `tìm nhà thầu`, `tìm thầu`, `cần kỹ sư`, `cần kiến trúc sư`, `cần bóc tách`, `cần dự toán`.
3. **VẬT LIỆU:** `thép`, `xi măng`, `gạch`, `cát`, `đá`, `bê tông`, `sắt`, `tôn`, `vật liệu xây dựng`.
4. **SOFTWARE:** `AutoCAD`, `Revit`, `BIM`, `Tekla`, `Civil 3D`, `SketchUp`, `ETABS`, `SAP2000`, `PLAXIS`, `enjiCAD`.
5. **CONSTRUCTION:** `công trình`, `xây dựng`, `nhà phố`, `biệt thự`, `nhà xưởng`, `dự án`.

---

## 3. Chuẩn Đầu Ra JSON Schema & 13 Ý Định (Intent Taxonomy)

### 3.1. Cấu trúc JSON Schema
```json
{
  "construction_relevant": true,
  "commercial_intent": true,
  "intent": "REQUEST_QUOTE",
  "category": "EQUIPMENT",
  "product": "Robot Xoa Nền Bê Tông",
  "quantity": "2 chiếc",
  "requirement": "Cần mua 2 chiếc robot xoa nền bê tông đôi động cơ Honda GX690 tại Hà Nội...",
  "location": "Hà Nội",
  "budget": null,
  "timeline": null,
  "customer_name": "Tuấn",
  "company": null,
  "phone": "0988111222",
  "email": null,
  "confidence": 0.95
}
```

### 3.2. Bảng 13 Ý Định Chuẩn (Khớp 100% DB Constraint)
| Mã Intent | Ý nghĩa Nghiệp vụ | Ví dụ Thực tế |
|---|---|---|
| `REQUEST_QUOTE` | Xin báo giá, hỏi giá sản phẩm/dịch vụ | "Báo giá cho em 02 máy xoa nền đôi GX690" |
| `LOOKING_TO_BUY` | Cần mua, tìm mua, ai bán | "Đang tìm mua 100 tấn xi măng Nghi Sơn tại Hải Phòng" |
| `LOOKING_FOR_SERVICE` | Cần thi công, thiết kế, tìm nhà thầu | "Cần thi công 10.000m2 sàn bê tông xoa phẳng" |
| `URGENT_NEED` | Nhu cầu gấp, khẩn cấp trong ngày | "Cần gấp 3 xe bê tông tươi mác 300 trong sáng nay" |
| `HIRING` | Tuyển dụng nhân sự, thầu phụ | "Tuyển dụng 05 kỹ sư giám sát công trình xây dựng" |
| `PARTNERSHIP` | Hợp tác đại lý, phân phối | "Muốn hợp tác làm đại lý phân phối phụ gia bê tông" |
| `COMPARISON` | So sánh kỹ thuật giữa các giải pháp | "Nên dùng Revit hay Tekla cho kết cấu thép?" |
| `RESEARCH` | Xin tư vấn kỹ thuật, tài liệu | "Kinh nghiệm xử lý sàn bê tông nứt chân chim" |
| `DISCUSSION` | Thảo luận xu hướng, công nghệ | "Lộ trình áp dụng bắt buộc BIM từ 2026" |
| `INFORMATION` | Tin tức, quy chuẩn, ứng tuyển | "Bộ Xây Dựng ban hành quy chuẩn kỹ thuật mới" |
| `RECOMMENDATION` | Giới thiệu, đề xuất giải pháp | "Nên dùng robot xoa nền để tối ưu chi phí" |
| `EXISTING_CUSTOMER` | Khách hàng cũ cần hỗ trợ kỹ thuật | "Phần mềm SAP2000 bị lỗi kích hoạt license" |
| `IGNORE` | Không liên quan ngành xây dựng | Bài đăng spam bán xe máy, rủ đi cafe |

---

## 4. Nguyên Tắc Phòng Chống Hallucination (Zero-Hallucination)

1. **Số điện thoại (`phone`):**
   - Bắt buộc quét bằng regex chuẩn số điện thoại Việt Nam (hỗ trợ phân tách chấm, dấu cách, dấu gạch nối).
   - Nếu trong văn bản không có số điện thoại thực tế $\to$ ép buộc giá trị `null`.
2. **Email (`email`):**
   - Chỉ trích xuất chuỗi định dạng RFC hợp lệ (`user@domain.ext`). Nếu không có $\to$ ép buộc `null`.
3. **Công ty (`company`):**
   - Chỉ ghi nhận khi văn bản có tiền tố pháp nhân rõ ràng (`Công ty`, `TNHH`, `Cổ phần`, `Tập đoàn`, `Nhà thầu`,...). Tuyệt đối không bịa đặt tên công ty nếu người đăng không nhắc tới.
4. **Tên khách hàng (`customer_name`):**
   - Chỉ ghi nhận khi có câu tự xưng hoặc xưng hô rõ ràng (`em là Tuấn`, `liên hệ Mr. Tuấn`,...). Không tự suy diễn từ username Facebook.
5. **Độ tin cậy (`confidence`):**
   - Kẹp chặt (`clamp`) trong khoảng `[0.0, 1.0]`.

---

## 5. Ghép Ngữ Cảnh Cho Bình Luận (Comment Context Bundling)

Khi phân tích bình luận:
- Hệ thống **không phân tích bình luận đơn lẻ** nếu thiếu ngữ cảnh.
- Tự động truy vấn bài viết gốc trong bảng `facebook_posts` theo `post_id`.
- Ghép gói dữ liệu:
  ```
  BÀI ĐĂNG GỐC CỦA [Tác giả]:
  [Nội dung bài viết gốc]

  BÌNH LUẬN CẦN PHÂN TÍCH:
  [Nội dung bình luận]
  ```
- Giúp AI hiểu chính xác bình luận "Báo giá em với" hay "Cho xin thông số chiếc này" đang đề cập đến sản phẩm gì ở bài gốc.

---

## 6. Kết Quả Kiểm Thử Toàn Diện (32/32 Mock Vectors PASSED)

Bộ kiểm thử tích hợp `/home/ADMIN/test_ai_detection_integration.py` đã vượt qua 100%:

```
===========================================================================
📊 TEST SUMMARY:
  Total Mock Vectors Tested : 32
  Passed                    : 32/32
  Failed                    : 0

🎉 ALL 32/32 PHASE 5 AI LEAD DETECTION TESTS PASSED 100%!
===========================================================================
```

---

## 7. Tài nguyên Triển khai

- **Bộ lọc Từ khóa:** `/home/ADMIN/intelligence/keyword_filter.js` & `keyword_filter.py`
- **Bộ kiểm định Guardrails:** `/home/ADMIN/intelligence/schema_validator.js` & `schema_validator.py`
- **Bộ máy AI Detector & Hybrid Fallback:** `/home/ADMIN/intelligence/qwen_detector.py`
- **Pipeline Xử lý Dữ liệu:** `/home/ADMIN/intelligence/pipeline.py`
- **Workflow n8n:** `/home/ADMIN/n8n/data/workflow_ai_lead_detection.json` (ID: `FB_AI_LEAD_DETECTION_V1`)
- **Bộ kiểm thử Tích hợp 32 Vector:** `/home/ADMIN/test_ai_detection_integration.py`
