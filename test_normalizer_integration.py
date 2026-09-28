#!/usr/bin/env python3
"""
Facebook Lead Intelligence V1 - Phase 4: Normalization & Deduplication Integration Test Suite

Tests all mandatory requirements:
1. tiếng Việt (accents, NFC, meaning preserved)
2. tiếng Anh
3. nội dung rỗng (empty content, whitespace-only, null)
4. duplicate external ID (source + external_id dedup)
5. duplicate content (content_hash detection)
6. emoji (UTF-8 4-byte preservation)
7. ký tự đặc biệt (technical symbols, currencies, delimiters)
8. multiline text (whitespace, tab, carriage return normalization)
9. comment / reply hierarchy (post_id, parent_comment_id preservation)
10. dead-letter error handling (defensive execution on malformed payload)
11. comment & reply database persistence verification
"""

import os
import sys
import uuid
import json
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime, timezone

sys.path.append('/home/ADMIN/normalizer')
from normalizer import normalize_text, generate_content_hash, detect_language, classify_item_type, normalize_raw_item
from dedup_engine import NormalizerDedupEngine, DB_URI

def run_tests():
    print("=" * 70)
    print("🚀 STARTING PHASE 4: NORMALIZATION & DEDUPLICATION TEST SUITE")
    print("=" * 70)

    conn = psycopg2.connect(DB_URI)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    engine = NormalizerDedupEngine(DB_URI)

    # Pick an active source for testing
    cur.execute("SELECT id, name FROM public.facebook_sources WHERE status = 'ACTIVE' LIMIT 1;")
    source_row = cur.fetchone()
    if not source_row:
        test_source_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO public.facebook_sources (
                id, name, source_type, external_id, status, access_method
            ) VALUES (%s, 'Test Source Phase 4', 'PAGE', 'test_source_p4', 'ACTIVE', 'GRAPH_API')
            RETURNING id, name;
        """, (test_source_id,))
        source_row = cur.fetchone()
        conn.commit()

    source_id = source_row['id']
    print(f"📌 Using Test Source: {source_row['name']} (ID: {source_id})\n")

    test_results = {}

    try:
        # -------------------------------------------------------------
        # TEST 1: Tiếng Việt (NFC & Diacritics Preservation)
        # -------------------------------------------------------------
        print("--- [TEST 1] Tiếng Việt (NFC & Diacritics Preservation) ---")
        raw_vi = "   Chào   anh chị bên   em đang cần   tư vấn máy xoa nền bê tông và phần mềm ETABS!   "
        norm_vi = normalize_text(raw_vi)
        lang_vi = detect_language(norm_vi)
        hash_vi = generate_content_hash(norm_vi)
        
        assert "máy xoa nền bê tông" in norm_vi, "Vietnamese text corrupted!"
        assert norm_vi == "Chào anh chị bên em đang cần tư vấn máy xoa nền bê tông và phần mềm ETABS!", f"Unexpected norm: {norm_vi}"
        assert lang_vi == 'vi', f"Expected lang 'vi', got '{lang_vi}'"
        print(f"  Normalized: '{norm_vi}'")
        print(f"  Language: '{lang_vi}' | Hash: {hash_vi[:16]}...")
        test_results['test_1_vietnamese'] = 'PASSED'

        # -------------------------------------------------------------
        # TEST 2: Tiếng Anh
        # -------------------------------------------------------------
        print("\n--- [TEST 2] Tiếng Anh (English Detection) ---")
        raw_en = "Looking for quotation and technical specifications for concrete finishing robotics and PLAXIS software."
        norm_en = normalize_text(raw_en)
        lang_en = detect_language(norm_en)
        assert lang_en == 'en', f"Expected lang 'en', got '{lang_en}'"
        print(f"  Normalized: '{norm_en}'")
        print(f"  Language: '{lang_en}'")
        test_results['test_2_english'] = 'PASSED'

        # -------------------------------------------------------------
        # TEST 3: Nội dung rỗng (Empty Content & Nulls)
        # -------------------------------------------------------------
        print("\n--- [TEST 3] Nội dung rỗng (Empty Content & Nulls) ---")
        assert normalize_text("") == ""
        assert normalize_text("   \t\r\n\n\t  ") == ""
        assert normalize_text(None) == ""
        lang_empty = detect_language("")
        hash_empty = generate_content_hash("")
        assert lang_empty == 'empty', f"Expected 'empty', got '{lang_empty}'"
        assert hash_empty == 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
        print(f"  Empty normalized to: ''")
        print(f"  Language: '{lang_empty}' | Hash: {hash_empty}")
        test_results['test_3_empty_content'] = 'PASSED'

        # -------------------------------------------------------------
        # TEST 4: Emoji
        # -------------------------------------------------------------
        print("\n--- [TEST 4] Emoji (UTF-8 4-byte preservation) ---")
        raw_emoji = "🤖 Robot hoàn thiện mặt sàn bê tông 🏗️⚡ Siêu tiết kiệm chi phí! 🚀"
        norm_emoji = normalize_text(raw_emoji)
        assert "🤖" in norm_emoji and "🏗️" in norm_emoji and "🚀" in norm_emoji, "Emojis were stripped or damaged!"
        print(f"  Emoji Text: {norm_emoji}")
        test_results['test_4_emoji'] = 'PASSED'

        # -------------------------------------------------------------
        # TEST 5: Ký tự đặc biệt (Special characters & Symbols)
        # -------------------------------------------------------------
        print("\n--- [TEST 5] Ký tự đặc biệt (Special characters & Symbols) ---")
        raw_special = "Đơn giá: $4,500 (~115.000.000 VNĐ) ± 0.5% tolerance. Liên hệ: sales@cic.com.vn #robot @CIC_Official!"
        norm_special = normalize_text(raw_special)
        for char in ['$', '~', '±', '%', '@', '#', '(', ')', '!']:
            assert char in norm_special, f"Missing special character {char} in output!"
        print(f"  Special Text: {norm_special}")
        test_results['test_5_special_chars'] = 'PASSED'

        # -------------------------------------------------------------
        # TEST 6: Multiline text (Whitespace & Newline normalization)
        # -------------------------------------------------------------
        print("\n--- [TEST 6] Multiline Text (Whitespace & Newline normalization) ---")
        raw_multi = "\r\n\tDự án xây dựng nhà xưởng.\r\n\n\n\n\t\tHạng mục:\n\n- Đổ bê tông\n\n\n\n- Xoa phẳng mặt sàn\n\n\n"
        norm_multi = normalize_text(raw_multi)
        assert '\r' not in norm_multi
        assert '\n\n\n' not in norm_multi
        assert not norm_multi.startswith('\n') and not norm_multi.endswith('\n')
        print(f"  Clean Multiline:\n{norm_multi}")
        test_results['test_6_multiline'] = 'PASSED'

        # -------------------------------------------------------------
        # TEST 7: Comment & Reply Hierarchy Resolution
        # -------------------------------------------------------------
        print("\n--- [TEST 7] Comment & Reply Hierarchy Resolution ---")
        test_uid = uuid.uuid4().hex[:8]
        post_ext_id = f"post_parent_{test_uid}"
        comm_ext_id = f"comm_child_{test_uid}"
        reply_ext_id = f"reply_grandchild_{test_uid}"

        raw_post_item = {
            'item_type': 'POST',
            'external_item_id': post_ext_id,
            'raw_payload': {'id': post_ext_id, 'message': 'Bài viết chính thức về máy xoa bê tông mới'}
        }
        post_class = classify_item_type(raw_post_item)
        assert post_class['category'] == 'POST' and post_class['targetTable'] == 'facebook_posts'

        raw_comm_item = {
            'item_type': 'COMMENT',
            'external_item_id': comm_ext_id,
            'external_parent_id': post_ext_id,
            'raw_payload': {'id': comm_ext_id, 'post_id': post_ext_id, 'message': 'Báo giá em với anh ơi'}
        }
        comm_class = classify_item_type(raw_comm_item)
        assert comm_class['category'] == 'COMMENT' and comm_class['parentCommentId'] is None
        assert comm_class['postId'] == post_ext_id

        raw_reply_item = {
            'item_type': 'COMMENT',
            'external_item_id': reply_ext_id,
            'external_parent_id': f"{post_ext_id}_{comm_ext_id}",
            'raw_payload': {
                'id': reply_ext_id,
                'parent_comment_id': comm_ext_id,
                'post_id': post_ext_id,
                'message': 'Đã gửi inbox báo giá chi tiết qua mail ạ!'
            }
        }
        reply_class = classify_item_type(raw_reply_item)
        assert reply_class['category'] == 'REPLY'
        assert reply_class['parentCommentId'] == comm_ext_id
        assert reply_class['postId'] == post_ext_id
        print(f"  Post Category: {post_class['category']} -> {post_class['targetTable']}")
        print(f"  Comment Category: {comm_class['category']} (Parent Post: {comm_class['postId']})")
        print(f"  Reply Category: {reply_class['category']} (Parent Comment: {reply_class['parentCommentId']})")
        test_results['test_7_hierarchy'] = 'PASSED'

        # -------------------------------------------------------------
        # TEST 8: Duplicate External ID (Source + External ID Dedup)
        # -------------------------------------------------------------
        print("\n--- [TEST 8] Duplicate External ID (Dedup Check 1) ---")
        unique_post_ext_id = f"ext_dedup_test_{uuid.uuid4().hex[:8]}"
        
        # 1. First raw item
        first_raw_id = str(uuid.uuid4())
        first_payload_hash = generate_content_hash(f"payload_1_{unique_post_ext_id}")
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                id, source_id, item_type, external_item_id, payload_hash, raw_payload, processing_status
            ) VALUES (%s, %s, 'POST', %s, %s, %s, 'PENDING');
        """, (first_raw_id, source_id, unique_post_ext_id, first_payload_hash, Json({
            'id': unique_post_ext_id,
            'message': 'Nội dung bài viết gốc thử nghiệm dedup external id',
            'created_time': datetime.now(timezone.utc).isoformat()
        })))
        conn.commit()

        # Process first item
        res1 = engine.process_raw_items_batch(limit=10)
        assert res1['processed_posts'] >= 1, "First post failed to process!"
        print(f"  First item processed successfully into facebook_posts.")

        # 2. Second raw item with SAME external_id but different payload hash
        second_raw_id = str(uuid.uuid4())
        second_payload_hash = generate_content_hash(f"payload_2_{unique_post_ext_id}")
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                id, source_id, item_type, external_item_id, payload_hash, raw_payload, processing_status
            ) VALUES (%s, %s, 'POST', %s, %s, %s, 'PENDING');
        """, (second_raw_id, source_id, unique_post_ext_id, second_payload_hash, Json({
            'id': unique_post_ext_id,
            'message': 'Nội dung cập nhật lại từ nguồn nhưng cùng external id',
            'created_time': datetime.now(timezone.utc).isoformat()
        })))
        conn.commit()

        # Process second item
        res2 = engine.process_raw_items_batch(limit=10)
        assert res2['skipped_duplicate_ids'] >= 1, f"Expected duplicate external ID skipped, got: {res2}"
        
        # Verify second raw item status
        cur.execute("SELECT processing_status, last_error FROM public.facebook_raw_items WHERE id = %s", (second_raw_id,))
        r2_status = cur.fetchone()
        assert r2_status['processing_status'] == 'PROCESSED', f"Expected PROCESSED, got {r2_status['processing_status']}"
        assert r2_status['last_error'] == 'DUPLICATE_EXTERNAL_ID', f"Expected DUPLICATE_EXTERNAL_ID, got {r2_status['last_error']}"
        print(f"  Second item correctly identified as DUPLICATE_EXTERNAL_ID and skipped from re-insertion.")
        test_results['test_8_duplicate_external_id'] = 'PASSED'

        # -------------------------------------------------------------
        # TEST 9: Duplicate Content Detection (Content Hash Dedup)
        # -------------------------------------------------------------
        print("\n--- [TEST 9] Duplicate Content Detection (Content Hash Dedup) ---")
        run_uid = uuid.uuid4().hex[:8]
        shared_content = f"Cần nhượng lại 02 robot xoa nền đôi động cơ Honda GX690 tại Hà Nội [Run {run_uid}], liên hệ 0912.999.888!"
        
        # Post A
        post_a_ext_id = f"ext_content_a_{run_uid}"
        raw_a_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                id, source_id, item_type, external_item_id, payload_hash, raw_payload, processing_status
            ) VALUES (%s, %s, 'POST', %s, %s, %s, 'PENDING');
        """, (raw_a_id, source_id, post_a_ext_id, generate_content_hash(f"hash_a_{post_a_ext_id}"), Json({
            'id': post_a_ext_id,
            'message': shared_content,
            'created_time': datetime.now(timezone.utc).isoformat()
        })))
        conn.commit()
        engine.process_raw_items_batch(limit=10)

        # Retrieve Post A record ID
        cur.execute("SELECT id FROM public.facebook_posts WHERE post_id = %s", (post_a_ext_id,))
        post_a_db_row = cur.fetchone()
        assert post_a_db_row is not None
        post_a_uuid = post_a_db_row['id']

        # Post B with DIFFERENT external ID but IDENTICAL content (cross-post / spam)
        post_b_ext_id = f"ext_content_b_{run_uid}"
        raw_b_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                id, source_id, item_type, external_item_id, payload_hash, raw_payload, processing_status
            ) VALUES (%s, %s, 'POST', %s, %s, %s, 'PENDING');
        """, (raw_b_id, source_id, post_b_ext_id, generate_content_hash(f"hash_b_{post_b_ext_id}"), Json({
            'id': post_b_ext_id,
            'message': f"  {shared_content}   \r\n\t",
            'created_time': datetime.now(timezone.utc).isoformat()
        })))
        conn.commit()

        res_b = engine.process_raw_items_batch(limit=10)
        assert res_b['detected_duplicate_contents'] >= 1, f"Expected duplicate content detected, got: {res_b}"

        cur.execute("SELECT is_duplicate_content, duplicate_of_id FROM public.facebook_posts WHERE post_id = %s", (post_b_ext_id,))
        post_b_db_row = cur.fetchone()
        assert post_b_db_row['is_duplicate_content'] is True, "Post B should be flagged is_duplicate_content=True"
        assert str(post_b_db_row['duplicate_of_id']) == str(post_a_uuid), f"Post B duplicate_of_id ({post_b_db_row['duplicate_of_id']}) should point to Post A ({post_a_uuid})"
        print(f"  Duplicate content detected: Post B correctly flagged with duplicate_of_id -> {post_a_uuid}")
        test_results['test_9_duplicate_content'] = 'PASSED'

        # -------------------------------------------------------------
        # TEST 10: Dead-Letter & Error Path (Malformed item does not crash)
        # -------------------------------------------------------------
        print("\n--- [TEST 10] Dead-Letter Error Path (Defensive Execution) ---")
        malformed_raw_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                id, source_id, item_type, external_item_id, payload_hash, raw_payload, processing_status
            ) VALUES (%s, %s, 'POST', NULL, %s, %s, 'PENDING');
        """, (malformed_raw_id, source_id, generate_content_hash(f"malformed_{malformed_raw_id}"), Json({
            'invalid_key': True
        })))
        conn.commit()

        res_dead = engine.process_raw_items_batch(limit=10)
        assert res_dead['failed_dead_letter'] >= 1, "Expected at least 1 failed item in dead letter"
        
        # Verify raw item marked FAILED
        cur.execute("SELECT processing_status, last_error FROM public.facebook_raw_items WHERE id = %s", (malformed_raw_id,))
        dead_status = cur.fetchone()
        assert dead_status['processing_status'] == 'FAILED', f"Expected FAILED, got {dead_status['processing_status']}"
        
        # Verify error record logged to facebook_errors
        cur.execute("SELECT error_category, error_code, error_message FROM public.facebook_errors WHERE raw_item_id = %s", (malformed_raw_id,))
        err_logged = cur.fetchone()
        assert err_logged is not None, "Error should be recorded in facebook_errors"
        assert err_logged['error_category'] == 'DATA_PARSE_ERROR'
        print(f"  Handled gracefully without throwing. Logged to facebook_errors: {err_logged['error_category']} ({err_logged['error_code']}).")
        test_results['test_10_dead_letter'] = 'PASSED'

        # -------------------------------------------------------------
        # TEST 11: Comment & Reply Database Storage Verification
        # -------------------------------------------------------------
        print("\n--- [TEST 11] Comment & Reply Database Storage Verification ---")
        # Ingest Comment raw item
        raw_comm_db_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                id, source_id, item_type, external_item_id, payload_hash, raw_payload, processing_status
            ) VALUES (%s, %s, 'COMMENT', %s, %s, %s, 'PENDING');
        """, (raw_comm_db_id, source_id, comm_ext_id, generate_content_hash(f"hash_comm_{comm_ext_id}"), Json({
            'id': comm_ext_id,
            'post_id': post_ext_id,
            'from': {'id': 'user_comm_123', 'name': 'Nguyễn Văn Kỹ Sư'},
            'message': 'Chào anh, bên em muốn tư vấn máy xoa đôi động cơ Honda GX690.',
            'created_time': datetime.now(timezone.utc).isoformat()
        })))
        conn.commit()

        # Ingest Reply raw item
        raw_reply_db_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                id, source_id, item_type, external_item_id, payload_hash, raw_payload, processing_status
            ) VALUES (%s, %s, 'COMMENT', %s, %s, %s, 'PENDING');
        """, (raw_reply_db_id, source_id, reply_ext_id, generate_content_hash(f"hash_reply_{reply_ext_id}"), Json({
            'id': reply_ext_id,
            'post_id': post_ext_id,
            'parent_comment_id': comm_ext_id,
            'from': {'id': 'page_admin_456', 'name': 'Admin CIC Construction'},
            'message': 'Đã gửi tài liệu và báo giá chi tiết qua inbox cho anh rồi nhé!',
            'created_time': datetime.now(timezone.utc).isoformat()
        })))
        conn.commit()

        res_comm_db = engine.process_raw_items_batch(limit=10)
        assert res_comm_db['processed_comments'] >= 2, f"Expected at least 2 processed comments, got: {res_comm_db}"

        # Verify Comment in DB
        cur.execute("SELECT comment_id, post_id, parent_comment_id, comment_type, author_name FROM public.facebook_comments WHERE comment_id = %s", (comm_ext_id,))
        row_c = cur.fetchone()
        assert row_c is not None, "Comment not found in facebook_comments"
        assert row_c['post_id'] == post_ext_id and row_c['parent_comment_id'] is None and row_c['comment_type'] == 'COMMENT'

        # Verify Reply in DB
        cur.execute("SELECT comment_id, post_id, parent_comment_id, comment_type, author_name FROM public.facebook_comments WHERE comment_id = %s", (reply_ext_id,))
        row_r = cur.fetchone()
        assert row_r is not None, "Reply not found in facebook_comments"
        assert row_r['post_id'] == post_ext_id and row_r['parent_comment_id'] == comm_ext_id and row_r['comment_type'] == 'REPLY'

        print(f"  Comment verified: ID={row_c['comment_id']}, Type={row_c['comment_type']}, Author={row_c['author_name']}")
        print(f"  Reply verified: ID={row_r['comment_id']}, Type={row_r['comment_type']}, Parent={row_r['parent_comment_id']}")
        test_results['test_11_comment_reply_persistence'] = 'PASSED'

    finally:
        cur.close()
        conn.close()

    print("\n" + "=" * 70)
    print("📊 INTEGRATION TEST SUITE RESULTS:")
    all_passed = True
    for test_name, status in test_results.items():
        print(f"  ✓ {test_name.ljust(35)}: {status}")
        if status != 'PASSED':
            all_passed = False

    if all_passed:
        print("\n🎉 ALL PHASE 4 INTEGRATION TESTS PASSED 100%!")
        print("=" * 70)
    else:
        print("\n❌ SOME TESTS FAILED!")
        sys.exit(1)

if __name__ == '__main__':
    run_tests()
