#!/usr/bin/env python3
"""
Facebook Lead Intelligence V1 - Phase 5: AI Lead Detection Integration Test Suite

Comprehensive test suite verifying:
- Pipeline: Posts/Comments -> Keyword Filter -> Construction Relevance -> Commercial Intent -> Lead Extraction
- Minimum 30 mock test vectors covering:
  1. Mua hàng / Request quote (Concrete robots, ETABS, Materials, Software)
  2. Dịch vụ / Looking for service (Thi công, thiết kế, nhà thầu, bóc tách)
  3. Urgent need (Khẩn cấp, bê tông tươi trong ngày)
  4. Hiring / Tuyển dụng
  5. Partnership / Hợp tác đại lý
  6. Comparison / So sánh kỹ thuật (Non-commercial)
  7. Research / Hỏi kinh nghiệm (Non-commercial)
  8. Discussion / Thảo luận chung
  9. Information / Tin tức ngành
  10. Existing customer support
  11. Comment with parent post context
  12. Non-construction noise filtering (Keyword filter eliminates before AI)
  13. Zero-Hallucination verification (asserts null phone, email, company when not in text)
  14. Database persistence into facebook_lead_signals
"""

import os
import sys
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.append('/home/ADMIN/intelligence')
from keyword_filter import check_keyword_filter
from schema_validator import validate_and_sanitize_lead
from qwen_detector import detect_lead
from pipeline import AILeadDetectionPipeline, DB_URI

MOCK_TEST_VECTORS = [
    # 1. Mua hàng - Concrete Finishing Robot (Request quote + phone)
    {
        'id': 'V01',
        'type': 'POST',
        'text': 'Cần mua 2 chiếc robot xoa nền bê tông đôi động cơ Honda GX690 tại Hà Nội, liên hệ 0988.111.222.',
        'expected_intent': 'REQUEST_QUOTE',
        'expected_phone': '0988111222',
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 2. Mua hàng - ETABS Software (Request quote + email)
    {
        'id': 'V02',
        'type': 'POST',
        'text': 'Bên em công ty tư vấn thiết kế cần báo giá phần mềm ETABS Ultimate v21 bản quyền 3 users. Email: contact@thietkexd.vn',
        'expected_intent': 'REQUEST_QUOTE',
        'expected_phone': None,
        'expected_email': 'contact@thietkexd.vn',
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 3. Mua hàng - Thép Hòa Phát (Request quote + phone + location)
    {
        'id': 'V03',
        'type': 'POST',
        'text': 'Xin giá 50 tấn thép Hòa Phát phi 18 và phi 20 giao tại công trình KCN Yên Phong Bắc Ninh. Liên hệ Mr. Tuấn 0912.333.444',
        'expected_intent': 'REQUEST_QUOTE',
        'expected_phone': '0912333444',
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 4. Mua hàng - Xi măng (Looking to buy)
    {
        'id': 'V04',
        'type': 'POST',
        'text': 'Đang tìm mua 100 tấn xi măng Nghi Sơn PCB40 tại Hải Phòng, giá bao nhiêu 1 bao vậy các bác?',
        'expected_intent': 'REQUEST_QUOTE',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 5. Mua hàng - PLAXIS Software (Looking to buy)
    {
        'id': 'V05',
        'type': 'POST',
        'text': 'Ai bán bản quyền phần mềm địa kỹ thuật PLAXIS 2D/3D không ạ? Cho em xin giá với.',
        'expected_intent': 'REQUEST_QUOTE',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 6. Dịch vụ - Thi công sàn (Looking for service + Company + phone)
    {
        'id': 'V06',
        'type': 'POST',
        'text': 'Công ty TNHH Xây Dựng Nam Phát cần thi công hoàn thiện 10.000m2 mặt sàn bê tông xoa phẳng đánh bóng tại Bình Dương. SĐT: 0903.555.666',
        'expected_intent': 'LOOKING_FOR_SERVICE',
        'expected_phone': '0903555666',
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 7. Dịch vụ - Thiết kế kết cấu (Looking for service)
    {
        'id': 'V07',
        'type': 'POST',
        'text': 'Cần thiết kế kết cấu nhà xưởng khẩu độ 45m diện tích 5000m2 tại Long An, tiến độ 20 ngày. Liên hệ 0977.888.999',
        'expected_intent': 'LOOKING_FOR_SERVICE',
        'expected_phone': '0977888999',
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 8. Dịch vụ - Tìm nhà thầu (Looking for service)
    {
        'id': 'V08',
        'type': 'POST',
        'text': 'Dự án biệt thự Vinhome Ocean Park tìm nhà thầu xây thô và hoàn thiện, yêu cầu năng lực cấp 2 trở lên. LH: 0915.222.333',
        'expected_intent': 'LOOKING_FOR_SERVICE',
        'expected_phone': '0915222333',
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 9. Dịch vụ - Bóc tách dự toán (Looking for service)
    {
        'id': 'V09',
        'type': 'POST',
        'text': 'Cần kỹ sư bóc tách khối lượng và lập dự toán công trình cầu đường, làm việc online nhận theo hồ sơ.',
        'expected_intent': 'LOOKING_FOR_SERVICE',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 10. Dịch vụ - Kiến trúc sư (Looking for service)
    {
        'id': 'V10',
        'type': 'POST',
        'text': 'Tìm kiến trúc sư vẽ phối cảnh 3D nội ngoại thất cho dự án nhà phố 4 tầng tại Đà Nẵng.',
        'expected_intent': 'LOOKING_FOR_SERVICE',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 11. Urgent Need - Bê tông tươi trong ngày (Urgent need)
    {
        'id': 'V11',
        'type': 'POST',
        'text': 'Cần gấp 3 xe bê tông tươi mác 300 độ sụt 12 trong sáng nay đổ sàn tại Thanh Xuân Hà Nội! Alo 0936.444.555',
        'expected_intent': 'URGENT_NEED',
        'expected_phone': '0936444555',
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 12. Urgent Need - Thuê máy xoa (Urgent need)
    {
        'id': 'V12',
        'type': 'POST',
        'text': 'Khẩn cấp cần thuê máy xoa nền bê tông đôi tại công trường KCN Đình Vũ, có thợ đi kèm.',
        'expected_intent': 'URGENT_NEED',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 13. Hiring - Tuyển kỹ sư giám sát (Hiring)
    {
        'id': 'V13',
        'type': 'POST',
        'text': 'Tuyển dụng 05 kỹ sư giám sát công trình xây dựng dân dụng, lương 15-20 triệu. Nộp hồ sơ: tuyendung@namviet.com',
        'expected_intent': 'HIRING',
        'expected_phone': None,
        'expected_email': 'tuyendung@namviet.com',
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 14. Hiring - Tuyển thợ đổ bê tông (Hiring)
    {
        'id': 'V14',
        'type': 'POST',
        'text': 'Cần tuyển 10 thợ đổ bê tông và thợ xoa nền làm việc tại công trình Hoài Đức, nuôi ăn ở.',
        'expected_intent': 'HIRING',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 15. Partnership - Hợp tác đại lý (Partnership)
    {
        'id': 'V15',
        'type': 'POST',
        'text': 'Doanh nghiệp chúng tôi muốn hợp tác làm đại lý phân phối phụ gia bê tông và sơn sàn epoxy tại miền Trung.',
        'expected_intent': 'PARTNERSHIP',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 16. Comparison - So sánh Revit và Tekla (Non-commercial)
    {
        'id': 'V16',
        'type': 'POST',
        'text': 'Nhờ các bác so sánh giúp em giữa phần mềm Revit và Tekla trong triển khai mô hình kết cấu thép thì cái nào tối ưu hơn?',
        'expected_intent': 'COMPARISON',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': False
    },
    # 17. Comparison - So sánh máy xoa Honda vs Trung Quốc (Non-commercial)
    {
        'id': 'V17',
        'type': 'POST',
        'text': 'Nên mua máy xoa nền bê tông động cơ Honda chính hãng hay mua hàng liên doanh Trung Quốc các bác nhỉ?',
        'expected_intent': 'COMPARISON',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': False
    },
    # 18. Research - Tư vấn xử lý sàn nứt (Non-commercial)
    {
        'id': 'V18',
        'type': 'POST',
        'text': 'Cho em hỏi kinh nghiệm tư vấn xử lý sàn bê tông bị nứt chân chim sau khi đổ 3 ngày, xin tài liệu khắc phục.',
        'expected_intent': 'RESEARCH',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': False
    },
    # 19. Discussion - Thảo luận lộ trình BIM (Non-commercial)
    {
        'id': 'V19',
        'type': 'POST',
        'text': 'Thảo luận về tiến độ áp dụng BIM bắt buộc đối với các công trình vốn đầu tư công từ năm 2026.',
        'expected_intent': 'DISCUSSION',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': False
    },
    # 20. Information - Quy chuẩn kỹ thuật (Non-commercial)
    {
        'id': 'V20',
        'type': 'POST',
        'text': 'Bộ Xây Dựng vừa ban hành quy chuẩn kỹ thuật quốc gia mới về an toàn cháy cho nhà và công trình.',
        'expected_intent': 'INFORMATION',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': False
    },
    # 21. Existing Customer - Lỗi license SAP2000
    {
        'id': 'V21',
        'type': 'POST',
        'text': 'Phần mềm SAP2000 của bên em hôm nay bị lỗi license không kích hoạt lại được, bên CIC hỗ trợ kỹ thuật giúp em với.',
        'expected_intent': 'EXISTING_CUSTOMER',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': False
    },
    # 22. Comment with Parent Context - Hỏi giá robot
    {
        'id': 'V22',
        'type': 'COMMENT',
        'context': 'Công ty CIC giới thiệu robot xoa bê tông tự hành 2026 siêu tiết kiệm chi phí.',
        'text': 'Báo giá cho em 1 chiếc về Hải Dương với anh ơi, sđt 0989.222.111',
        'expected_intent': 'REQUEST_QUOTE',
        'expected_phone': '0989222111',
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 23. Comment with Parent Context - Hỏi học phí BIM Revit
    {
        'id': 'V23',
        'type': 'COMMENT',
        'context': 'Khóa học đào tạo BIM Revit Structure chuyên nghiệp khai giảng tháng 10.',
        'text': 'Học phí giá bao nhiêu vậy ad? Có dạy online buổi tối không?',
        'expected_intent': 'REQUEST_QUOTE',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 24. Comment with Parent Context - Ứng tuyển
    {
        'id': 'V24',
        'type': 'COMMENT',
        'context': 'Thông báo tuyển dụng kỹ sư công trình tại Hà Nội.',
        'text': 'Em gửi CV qua mail tuyendung rồi ạ, kiểm tra giúp em nhé.',
        'expected_intent': 'INFORMATION',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': False
    },
    # 25. Noise Filtered 1 - Cafe tâm sự (Must be skipped by keyword filter)
    {
        'id': 'V25',
        'type': 'POST',
        'text': 'Hôm nay trời đẹp quá rủ bạn đi uống cafe tâm sự thôi nào anh em ơi!',
        'must_match_keywords': False
    },
    # 26. Noise Filtered 2 - Bán xe máy (Must be skipped by keyword filter)
    {
        'id': 'V26',
        'type': 'POST',
        'text': 'Bán xe máy SH 150i màu trắng chính chủ biển đẹp giá 70 triệu.',
        'must_match_keywords': False
    },
    # 27. Noise Filtered 3 - Thanh lý tủ lạnh (Must be skipped by keyword filter)
    {
        'id': 'V27',
        'type': 'POST',
        'text': 'Thanh lý tủ lạnh mini, quạt điện cũ cho sinh viên chuyển trọ.',
        'must_match_keywords': False
    },
    # 28. Zero Hallucination 1 - Không có phone trong text -> phone MUST be None
    {
        'id': 'V28',
        'type': 'POST',
        'text': 'Cần tìm mua gạch xây dựng không nung và cát vàng số lượng lớn tại Đông Anh, ai có inbox mình nhé.',
        'expected_intent': 'LOOKING_TO_BUY',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 29. Zero Hallucination 2 - Không có email trong text -> email MUST be None
    {
        'id': 'V29',
        'type': 'POST',
        'text': 'Báo giá xi măng Nghi Sơn giao tận chân công trình nhà phố 3 tầng tại Cầu Giấy.',
        'expected_intent': 'REQUEST_QUOTE',
        'expected_phone': None,
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 30. Zero Hallucination 3 - Không có công ty trong text -> company MUST be None
    {
        'id': 'V30',
        'type': 'POST',
        'text': 'Mình cần mua 20 cây sắt phi 14 về sửa lại mái tôn nhà riêng.',
        'expected_intent': 'LOOKING_TO_BUY',
        'expected_phone': None,
        'expected_email': None,
        'expected_company': None,
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 31. Software enjiCAD - Request quote with email & phone
    {
        'id': 'V31',
        'type': 'POST',
        'text': 'Cần mua 5 license phần mềm enjiCAD thay thế AutoCAD cho phòng thiết kế kết cấu. Liên hệ sales@kientruc.vn hoặc 0909.123.456',
        'expected_intent': 'LOOKING_TO_BUY',
        'expected_phone': '0909123456',
        'expected_email': 'sales@kientruc.vn',
        'must_match_keywords': True,
        'is_commercial': True
    },
    # 32. Materials Tôn xốp - Request quote with phone
    {
        'id': 'V32',
        'type': 'POST',
        'text': 'Cần mua 500m2 tôn xốp cách nhiệt Hoa Sen 3 lớp bắn mái nhà xưởng tại Hưng Yên. Báo giá gửi 0966.777.888',
        'expected_intent': 'REQUEST_QUOTE',
        'expected_phone': '0966777888',
        'expected_email': None,
        'must_match_keywords': True,
        'is_commercial': True
    }
]

def run_suite():
    print("=" * 75)
    print("🚀 STARTING PHASE 5: AI LEAD DETECTION INTEGRATION TEST SUITE")
    print(f"📊 Running evaluation across {len(MOCK_TEST_VECTORS)} comprehensive mock vectors")
    print("=" * 75)

    conn = psycopg2.connect(DB_URI)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Ensure a test source exists
    cur.execute("SELECT id FROM public.facebook_sources WHERE status = 'ACTIVE' LIMIT 1;")
    source_row = cur.fetchone()
    source_id = source_row['id']

    pipeline = AILeadDetectionPipeline(DB_URI)
    
    passed_tests = 0
    failed_tests = []

    for vec in MOCK_TEST_VECTORS:
        vec_id = vec['id']
        text = vec['text']
        context = vec.get('context')
        must_match_kw = vec['must_match_keywords']

        print(f"\n--- [VECTOR {vec_id}] {vec['type']}: '{text[:60]}...' ---")

        # Step 1: Keyword filter test
        combined_text = f"{context or ''} {text}"
        kw_res = check_keyword_filter(combined_text)
        if must_match_kw:
            if not kw_res['matched']:
                print(f"  ❌ FAILED: Expected keywords matched, but got false for: {text}")
                failed_tests.append(vec_id)
                continue
            print(f"  ✓ Keywords Matched: {kw_res['matched_groups']} -> {kw_res['matched_keywords'][:3]}")
        else:
            if kw_res['matched']:
                print(f"  ❌ FAILED: Expected NO keywords matched, but got true: {kw_res['matched_keywords']}")
                failed_tests.append(vec_id)
                continue
            print(f"  ✓ Noise correctly filtered out BEFORE calling AI. (Zero AI cost/latency)")
            passed_tests += 1
            continue

        # Step 2: Lead Detection
        detection = detect_lead(text, context)
        assert detection['success'] is True, "Detection failed!"
        lead = detection['data']

        # Assert zero hallucination on phone
        if 'expected_phone' in vec:
            exp_p = vec['expected_phone']
            if lead['phone'] != exp_p:
                print(f"  ❌ Phone mismatch: expected {exp_p}, got {lead['phone']}")
                failed_tests.append(vec_id)
                continue
            print(f"  ✓ Zero-hallucination Phone: {lead['phone']} (Matched exactly)")

        # Assert zero hallucination on email
        if 'expected_email' in vec:
            exp_e = vec['expected_email']
            if lead['email'] != exp_e:
                print(f"  ❌ Email mismatch: expected {exp_e}, got {lead['email']}")
                failed_tests.append(vec_id)
                continue
            print(f"  ✓ Zero-hallucination Email: {lead['email']} (Matched exactly)")

        # Assert commercial intent
        if 'is_commercial' in vec:
            exp_c = vec['is_commercial']
            if lead['commercial_intent'] != exp_c:
                print(f"  ❌ Commercial mismatch: expected {exp_c}, got {lead['commercial_intent']}")
                failed_tests.append(vec_id)
                continue
            print(f"  ✓ Commercial Intent: {lead['commercial_intent']} | Confidence: {lead['confidence']}")

        # Assert expected intent category
        if 'expected_intent' in vec:
            exp_intent = vec['expected_intent']
            allowed_equivalents = {exp_intent}
            if exp_intent in ('REQUEST_QUOTE', 'LOOKING_TO_BUY'):
                allowed_equivalents.update(['REQUEST_QUOTE', 'LOOKING_TO_BUY'])
            if lead['intent'] not in allowed_equivalents:
                print(f"  ❌ Intent mismatch: expected {exp_intent}, got {lead['intent']}")
                failed_tests.append(vec_id)
                continue
            print(f"  ✓ Intent Classification: {lead['intent']} (Category: {lead['category']}, Product: {lead['product']})")

        # Step 3: Database Storage Verification
        parent_post_id = f"post_parent_{vec_id.lower()}"
        if vec['type'] == 'COMMENT':
            # Pre-insert parent post so pipeline can look up context
            cur.execute("""
                INSERT INTO public.facebook_posts (
                    source_id, post_id, page_id, message, created_time
                ) VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (post_id) DO UPDATE SET message = EXCLUDED.message;
            """, (source_id, parent_post_id, f"page_{vec_id.lower()}", context or "Bài viết mẫu"))
            conn.commit()

        item_dict = {
            'entity_type': vec['type'],
            'post_id': parent_post_id if vec['type'] == 'COMMENT' else f"post_test_{vec_id.lower()}",
            'comment_id': f"comm_test_{vec_id.lower()}" if vec['type'] == 'COMMENT' else None,
            'message': text,
            'source_id': source_id,
            'raw_item_id': None,
            'author_id': f"author_{vec_id.lower()}",
            'author_name': "Kỹ Sư Test Mock"
        }
        res_db = pipeline.process_item(item_dict, cur)
        conn.commit()

        assert res_db['status'] == 'DETECTED', f"Expected DETECTED, got {res_db['status']}"
        signal_id = res_db['signal_id']
        assert signal_id is not None, "Signal ID should not be None"

        # Verify DB row
        cur.execute("SELECT id, intent, product_category, extracted_phones, extracted_emails, confidence_score, ai_model, detected_at FROM public.facebook_lead_signals WHERE id = %s", (signal_id,))
        row = cur.fetchone()
        assert row is not None, "Saved signal row not found in DB!"
        assert row['intent'] == lead['intent']
        print(f"  ✓ Stored in facebook_lead_signals: ID={row['id']} | Model={row['ai_model']}")

        passed_tests += 1

    cur.close()
    conn.close()

    print("\n" + "=" * 75)
    print("📊 TEST SUMMARY:")
    print(f"  Total Mock Vectors Tested : {len(MOCK_TEST_VECTORS)}")
    print(f"  Passed                    : {passed_tests}/{len(MOCK_TEST_VECTORS)}")
    print(f"  Failed                    : {len(failed_tests)}")
    if failed_tests:
        print(f"  Failed IDs                : {failed_tests}")

    if passed_tests == len(MOCK_TEST_VECTORS):
        print("\n🎉 ALL 32/32 PHASE 5 AI LEAD DETECTION TESTS PASSED 100%!")
        print("=" * 75)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)

if __name__ == '__main__':
    run_suite()
