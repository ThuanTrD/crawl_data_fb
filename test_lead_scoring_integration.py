#!/usr/bin/env python3
"""
Facebook Lead Intelligence V1 - Phase 6: Lead Management Integration Test Suite

Verifies all 8 required test scenarios:
1. Lead mới
2. Cùng phone (merge exact phone)
3. Cùng email (merge exact email)
4. Cùng company (low confidence -> do not auto-merge -> POSSIBLE_DUPLICATE)
5. Duplicate post (provenance attached)
6. Comment tạo lead (comment_id, post_id, parent context mapped in lead_sources)
7. Lead có phone/email (scores +5 each, band verification)
8. Lead không có contact info (scores 0 for contacts, anonymous fingerprint)
"""

import os
import sys
import uuid
import json
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.append('/home/ADMIN/scoring')
from scoring_engine import calculate_lead_score
from dedup_resolver import resolve_entity, compute_dedup_fingerprint
from lead_processor import process_single_signal, run_scoring_batch, DB_URI

def insert_signal_db(cur, sig):
    cur.execute("""
        INSERT INTO public.facebook_lead_signals (
            id, source_id, entity_type, entity_id, post_id, comment_id, author_id, author_name,
            raw_text, intent, product_category, product_mention, extracted_phones,
            extracted_emails, confidence_score, signal_metadata, status, detected_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, 0.95, %s, 'NEW', %s
        ) ON CONFLICT (id) DO NOTHING;
    """, (
        sig['id'], sig['source_id'], sig['entity_type'], sig.get('comment_id') or sig['post_id'],
        sig['post_id'], sig.get('comment_id'), sig.get('author_id'), sig.get('author_name'),
        sig['raw_text'], sig['intent'], sig.get('product_category'), sig.get('product_mention'),
        sig.get('extracted_phones', []), sig.get('extracted_emails', []),
        json.dumps(sig.get('signal_metadata', {})), sig.get('detected_at') or '2026-09-18T01:00:00Z'
    ))

def run_suite():
    print("=" * 80)
    print("🚀 STARTING PHASE 6: LEAD MANAGEMENT FULL TEST SUITE")
    print("=" * 80)

    conn = psycopg2.connect(DB_URI)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT id FROM public.facebook_sources LIMIT 1;")
    source_row = cur.fetchone()
    source_id = str(source_row['id']) if source_row else str(uuid.uuid4())

    passed_tests = 0
    total_tests = 8

    # -----------------------------------------------------------------
    # TEST 1: Lead mới
    # -----------------------------------------------------------------
    print("\n--- [TEST 1] Lead Mới ---")
    import random
    u_suffix = uuid.uuid4().hex[:6]
    sig1_phone = f"091{random.randint(1000000, 9999999)}"
    sig1_email = f"lead_{u_suffix}@xaydung.vn"
    sig1 = {
        'id': str(uuid.uuid4()),
        'source_id': source_id,
        'entity_type': 'POST',
        'post_id': f"post_t1_{u_suffix}",
        'comment_id': None,
        'author_id': f"author_{u_suffix}",
        'author_name': f"Kỹ sư Nguyễn Văn {u_suffix.upper()}",
        'raw_text': f"Cần báo giá 2 máy xoa nền đôi cho dự án tại Hà Nội, liên hệ {sig1_phone}",
        'intent': 'REQUEST_QUOTE',
        'product_category': 'ROBOT_XAY_DUNG',
        'product_mention': 'Máy xoa nền đôi',
        'extracted_phones': [sig1_phone],
        'extracted_emails': [sig1_email],
        'signal_metadata': {
            'quantity': '2 máy',
            'location': 'Hà Nội',
            'timeline': 'gấp trong tuần',
            'company': f"Cty Xây Dựng Tiến Phát {u_suffix}"
        },
        'detected_at': '2026-09-18T01:00:00Z'
    }
    insert_signal_db(cur, sig1)
    conn.commit()

    res1 = process_single_signal(cur, sig1)
    conn.commit()
    lead1_id = res1['lead_id']
    assert res1['action'] == 'CREATED'
    assert res1['resolution'] == 'NEW'
    assert res1['lead_score'] >= 60
    print(f"  ✓ Lead Mới created successfully: ID={lead1_id} | Score={res1['lead_score']} | Tier={res1['lead_tier']}")
    passed_tests += 1

    # -----------------------------------------------------------------
    # TEST 2: Cùng Phone -> Merge vào existing lead
    # -----------------------------------------------------------------
    print("\n--- [TEST 2] Cùng Phone (Exact Phone Resolution) ---")
    sig2 = {
        'id': str(uuid.uuid4()),
        'source_id': source_id,
        'entity_type': 'POST',
        'post_id': f"post_t2_{u_suffix}",
        'comment_id': None,
        'author_id': f"author_{u_suffix}_diff",
        'author_name': "Kỹ sư Khác",
        'raw_text': f"Báo giá thêm phụ kiện xoa nền, sđt {sig1_phone}",
        'intent': 'REQUEST_QUOTE',
        'product_category': 'ROBOT_XAY_DUNG',
        'product_mention': 'Phụ kiện xoa nền',
        'extracted_phones': [sig1_phone],
        'extracted_emails': [],
        'signal_metadata': {},
        'detected_at': '2026-09-18T01:10:00Z'
    }
    insert_signal_db(cur, sig2)
    conn.commit()

    res2 = process_single_signal(cur, sig2)
    conn.commit()
    assert res2['action'] == 'MERGED'
    assert res2['lead_id'] == lead1_id, "Must merge to exact lead1_id matching same phone"
    assert res2['resolution'] == 'EXISTING_LEAD'
    assert res2['match_rule'] == 'EXACT_PHONE'
    print(f"  ✓ Cùng Phone merged into existing lead {lead1_id} via {res2['match_rule']}")
    passed_tests += 1

    # -----------------------------------------------------------------
    # TEST 3: Cùng Email -> Merge vào existing lead
    # -----------------------------------------------------------------
    print("\n--- [TEST 3] Cùng Email (Exact Email Resolution) ---")
    sig3 = {
        'id': str(uuid.uuid4()),
        'source_id': source_id,
        'entity_type': 'POST',
        'post_id': f"post_t3_{u_suffix}",
        'comment_id': None,
        'author_id': f"author_email_{u_suffix}",
        'author_name': "Phòng Kỹ Thuật",
        'raw_text': f"Gửi catalog phần mềm qua mail {sig1_email} giúp bên mình",
        'intent': 'REQUEST_QUOTE',
        'product_category': 'CAD_SOFTWARE',
        'product_mention': 'Phần mềm CAD',
        'extracted_phones': [],
        'extracted_emails': [sig1_email],
        'signal_metadata': {},
        'detected_at': '2026-09-18T01:20:00Z'
    }
    insert_signal_db(cur, sig3)
    conn.commit()

    res3 = process_single_signal(cur, sig3)
    conn.commit()
    assert res3['action'] == 'MERGED'
    assert res3['lead_id'] == lead1_id, "Must merge to exact lead1_id matching same email"
    assert res3['match_rule'] == 'EXACT_EMAIL'
    print(f"  ✓ Cùng Email merged into existing lead {lead1_id} via {res3['match_rule']}")
    passed_tests += 1

    # -----------------------------------------------------------------
    # TEST 4: Cùng Company (Do NOT auto-merge when contact differs)
    # -----------------------------------------------------------------
    print("\n--- [TEST 4] Cùng Company (Low Confidence -> POSSIBLE_DUPLICATE) ---")
    sig4_phone = f"098{random.randint(1000000, 9999999)}"
    sig4 = {
        'id': str(uuid.uuid4()),
        'source_id': source_id,
        'entity_type': 'POST',
        'post_id': f"post_t4_{u_suffix}",
        'comment_id': None,
        'author_id': f"author_comp_{u_suffix}",
        'author_name': "Chị Lan Kế Toán",
        'raw_text': f"Bên em Cty Xây Dựng Tiến Phát {u_suffix} cần hợp đồng, gọi {sig4_phone}",
        'intent': 'LOOKING_TO_BUY',
        'product_category': 'ROBOT_XAY_DUNG',
        'product_mention': 'Robot xoa nền',
        'extracted_phones': [sig4_phone],
        'extracted_emails': [],
        'signal_metadata': {
            'company': f"Cty Xây Dựng Tiến Phát {u_suffix}"
        },
        'detected_at': '2026-09-18T01:30:00Z'
    }
    insert_signal_db(cur, sig4)
    conn.commit()

    res4 = process_single_signal(cur, sig4)
    conn.commit()
    assert res4['action'] == 'CREATED', "Do NOT auto-merge different contact info even if same company"
    assert res4['resolution'] == 'POSSIBLE_DUPLICATE'
    assert res4['lead_id'] != lead1_id
    assert res4['match_rule'] == 'COMPANY_MATCH'
    # Verify LEAD_DUPLICATE_DETECTED event logged
    cur.execute("SELECT * FROM public.lead_events WHERE lead_id = %s AND event_type = 'LEAD_DUPLICATE_DETECTED';", (res4['lead_id'],))
    assert cur.fetchone() is not None, "Must log LEAD_DUPLICATE_DETECTED event"
    print(f"  ✓ Cùng Company kept unmerged as POSSIBLE_DUPLICATE: ID={res4['lead_id']} (Rule: {res4['match_rule']})")
    passed_tests += 1

    # -----------------------------------------------------------------
    # TEST 5: Duplicate Post (Provenance preservation)
    # -----------------------------------------------------------------
    print("\n--- [TEST 5] Duplicate Post (Provenance Tracking) ---")
    sig5 = {
        'id': str(uuid.uuid4()),
        'source_id': source_id,
        'entity_type': 'POST',
        'post_id': f"post_t1_{u_suffix}",  # Duplicate post_id
        'comment_id': None,
        'author_id': f"author_{u_suffix}",
        'author_name': f"Kỹ sư Nguyễn Văn {u_suffix.upper()}",
        'raw_text': f"Cần báo giá 2 máy xoa nền đôi cho dự án tại Hà Nội, liên hệ {sig1_phone}",
        'intent': 'REQUEST_QUOTE',
        'product_category': 'ROBOT_XAY_DUNG',
        'product_mention': 'Máy xoa nền đôi',
        'extracted_phones': [sig1_phone],
        'extracted_emails': [sig1_email],
        'signal_metadata': {},
        'detected_at': '2026-09-18T01:35:00Z'
    }
    insert_signal_db(cur, sig5)
    conn.commit()

    res5 = process_single_signal(cur, sig5)
    conn.commit()
    assert res5['action'] == 'MERGED'
    assert res5['lead_id'] == lead1_id
    cur.execute("SELECT count(*) FROM public.lead_sources WHERE lead_id = %s;", (lead1_id,))
    cnt_sources = cur.fetchone()['count']
    assert cnt_sources >= 3, "Provenance must accumulate sources"
    print(f"  ✓ Duplicate post attached to lead {lead1_id} with full provenance (total sources: {cnt_sources})")
    passed_tests += 1

    # -----------------------------------------------------------------
    # TEST 6: Comment tạo Lead (comment_id, post_id, parent context)
    # -----------------------------------------------------------------
    print("\n--- [TEST 6] Comment Tạo Lead (Hierarchical Context) ---")
    sig6_phone = f"093{random.randint(1000000, 9999999)}"
    sig6_comment_id = f"comm_t6_{uuid.uuid4().hex[:6]}"
    sig6_post_id = f"post_parent_{uuid.uuid4().hex[:6]}"
    sig6 = {
        'id': str(uuid.uuid4()),
        'source_id': source_id,
        'entity_type': 'COMMENT',
        'post_id': sig6_post_id,
        'comment_id': sig6_comment_id,
        'author_id': f"author_comm_{u_suffix}",
        'author_name': "Kỹ sư Công trường",
        'raw_text': f"Anh cho em xin giá 1 bộ chuyển về Hải Phòng nhé, số em {sig6_phone}",
        'intent': 'REQUEST_QUOTE',
        'product_category': 'ROBOT_XAY_DUNG',
        'product_mention': 'Robot xoa nền đơn',
        'extracted_phones': [sig6_phone],
        'extracted_emails': [],
        'signal_metadata': {
            'location': 'Hải Phòng',
            'quantity': '1 bộ'
        },
        'detected_at': '2026-09-18T01:40:00Z'
    }
    insert_signal_db(cur, sig6)
    conn.commit()

    res6 = process_single_signal(cur, sig6)
    conn.commit()
    lead6_id = res6['lead_id']
    assert res6['action'] == 'CREATED'
    # Verify provenance has platform=facebook, post_id, and comment_id
    cur.execute("SELECT * FROM public.lead_sources WHERE lead_id = %s AND comment_id = %s;", (lead6_id, sig6_comment_id))
    ls_row = cur.fetchone()
    assert ls_row is not None
    assert ls_row['platform'] == 'facebook'
    assert ls_row['post_id'] == sig6_post_id
    assert ls_row['comment_id'] == sig6_comment_id
    print(f"  ✓ Comment Lead created: ID={lead6_id} | post_id={ls_row['post_id']} | comment_id={ls_row['comment_id']}")
    passed_tests += 1

    # -----------------------------------------------------------------
    # TEST 7: Lead có Phone/Email (Point scoring & Band verification)
    # -----------------------------------------------------------------
    print("\n--- [TEST 7] Lead Có Phone/Email (Scoring & Bands) ---")
    sig7_phone = f"094{random.randint(1000000, 9999999)}"
    sig7_email = f"lead7_{uuid.uuid4().hex[:6]}@cic.com.vn"
    sig7 = {
        'id': str(uuid.uuid4()),
        'source_id': source_id,
        'entity_type': 'POST',
        'post_id': f"post_t7_{u_suffix}",
        'comment_id': None,
        'author_id': f"author_t7_{u_suffix}",
        'author_name': "Nguyễn Văn Đạt",
        'raw_text': f"Cần thi công sàn bê tông mài bóng nhà xưởng 5000m2 tại Bắc Ninh, alo {sig7_phone} mail {sig7_email}",
        'intent': 'LOOKING_FOR_SERVICE',
        'product_category': 'CONSTRUCTION',
        'product_mention': 'Thi công sàn bê tông mài bóng',
        'extracted_phones': [sig7_phone],
        'extracted_emails': [sig7_email],
        'signal_metadata': {
            'location': 'Bắc Ninh',
            'quantity': '5000m2',
            'timeline': 'Tháng 10',
            'company': 'Công ty CP Đầu tư Xây dựng Kinh Bắc'
        },
        'detected_at': '2026-09-18T01:45:00Z'
    }
    # Expected score:
    # LOOKING_FOR_SERVICE: 25
    # product: 10
    # quantity: 5
    # location: 5
    # timeline: 5
    # phone: 5
    # email: 5
    # Total = 60 -> HIGH tier
    score7 = calculate_lead_score(sig7)
    assert score7['total_score'] == 60, f"Expected 60, got {score7['total_score']}"
    assert score7['tier'] == 'HIGH'
    insert_signal_db(cur, sig7)
    conn.commit()

    res7 = process_single_signal(cur, sig7)
    conn.commit()
    print(f"  ✓ Score calculated: {score7['total_score']} (Tier: {score7['tier']}) - Phone (+5) & Email (+5) awarded")
    passed_tests += 1

    # -----------------------------------------------------------------
    # TEST 8: Lead không có Contact Info (Score 0 contacts, anonymous fallback)
    # -----------------------------------------------------------------
    print("\n--- [TEST 8] Lead Không Có Contact Info ---")
    sig8_author = f"anon_author_{uuid.uuid4().hex[:8]}"
    sig8 = {
        'id': str(uuid.uuid4()),
        'source_id': source_id,
        'entity_type': 'POST',
        'post_id': f"post_t8_{u_suffix}",
        'comment_id': None,
        'author_id': sig8_author,
        'author_name': "Thành viên Ẩn danh",
        'raw_text': "Anh em có ai bán máy xoa nền cũ giá mềm không?",
        'intent': 'LOOKING_TO_BUY',
        'product_category': 'ROBOT_XAY_DUNG',
        'product_mention': 'Máy xoa nền cũ',
        'extracted_phones': [],
        'extracted_emails': [],
        'signal_metadata': {},
        'detected_at': '2026-09-18T01:50:00Z'
    }
    # Score: LOOKING_TO_BUY(25) + product(10) = 35 -> MEDIUM tier
    score8 = calculate_lead_score(sig8)
    assert score8['contact_score'] == 0, "No contacts should give 0 contact points"
    assert score8['total_score'] == 35
    assert score8['tier'] == 'MEDIUM'

    insert_signal_db(cur, sig8)
    conn.commit()

    res8 = process_single_signal(cur, sig8)
    conn.commit()
    lead8_id = res8['lead_id']
    cur.execute("SELECT primary_phone, primary_email, dedup_fingerprint FROM public.leads WHERE id = %s;", (lead8_id,))
    l8_row = cur.fetchone()
    assert l8_row['primary_phone'] is None
    assert l8_row['primary_email'] is None
    assert len(l8_row['dedup_fingerprint']) == 32
    print(f"  ✓ Lead without contacts processed: ID={lead8_id} | Score={score8['total_score']} | Fingerprint={l8_row['dedup_fingerprint']}")
    passed_tests += 1

    cur.close()
    conn.close()

    print("\n" + "=" * 80)
    print("📊 TEST SUITE RESULTS:")
    print(f"  Total Required Tests : {total_tests}")
    print(f"  Passed               : {passed_tests}/{total_tests}")
    print(f"  Failed               : {total_tests - passed_tests}")
    if passed_tests == total_tests:
        print("\n🎉 ALL 8/8 PHASE 6 LEAD MANAGEMENT TESTS PASSED 100%!")
        print("=" * 80)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)

if __name__ == '__main__':
    run_suite()
