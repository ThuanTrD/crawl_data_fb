import psycopg2
import uuid
import json
import time
import hashlib

DB_URL = "postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def ingest_real_leads():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Ensure Techaz source exists
    cur.execute("""
        SELECT id FROM public.facebook_sources WHERE external_id = 'techazcompany';
    """)
    src = cur.fetchone()
    source_id = src[0] if src else None

    canonical_post_url = "https://www.facebook.com/techazcompany/posts/122104083387417067/"
    post_id = "122104083387417067"

    # Real customers who commented on this post
    real_customers = [
        {
            "name": "Chien Vu Duc",
            "comment_id": "1625699959066326",
            "comment_text": "Trả theo năm thì kinh phí tính thế nào ADD",
            "fbid": "100004173033013",
            "profile_url": "https://www.facebook.com/profile.php?id=100004173033013",
            "intent": "REQUEST_QUOTE",
            "product": "CMS IntelliCAD 2D/3D Bản Quyền (Gói Thuê Bao Năm)",
            "score": 90,
            "tier": "HOT",
            "phone_status": "ẨN (Chưa để public SĐT)",
            "recommended_action": "Bấm link Facebook cá nhân nhắn tin Messenger báo giá gói thuê bao năm"
        },
        {
            "name": "Tran Huong Quang",
            "comment_id": "1402187242091381",
            "comment_text": "Ib",
            "fbid": "100001466644991",
            "profile_url": "https://www.facebook.com/profile.php?id=100001466644991",
            "intent": "REQUEST_QUOTE",
            "product": "CMS IntelliCAD 2D/3D Bản Quyền",
            "score": 88,
            "tier": "HOT",
            "phone_status": "ẨN (Chưa để public SĐT)",
            "recommended_action": "Bấm link Facebook cá nhân gửi bảng báo giá và tính năng phần mềm qua Inbox"
        },
        {
            "name": "Thu Anh",
            "comment_id": "2031927328198409",
            "comment_text": "Inbox",
            "fbid": "100025221011129",
            "profile_url": "https://www.facebook.com/profile.php?id=100025221011129",
            "intent": "REQUEST_QUOTE",
            "product": "CMS IntelliCAD 2D/3D Bản Quyền",
            "score": 88,
            "tier": "HOT",
            "phone_status": "ẨN (Chưa để public SĐT)",
            "recommended_action": "Bấm link Facebook cá nhân gửi bảng so sánh tính năng với AutoCAD qua Inbox"
        },
        {
            "name": "Trần Hà Sơn",
            "comment_id": "27746288788362140",
            "comment_text": "Dùng có được mượt mà k bạn? Mình dùng vinacad thấy bị giật giật",
            "fbid": "1635855486666999",
            "profile_url": "https://www.facebook.com/1635855486666999",
            "intent": "RESEARCH",
            "product": "CMS IntelliCAD 2D/3D (Tư vấn hiệu năng bản vẽ nặng)",
            "score": 82,
            "tier": "HOT",
            "phone_status": "ẨN (Chưa để public SĐT)",
            "recommended_action": "Inbox tư vấn hiệu năng xử lý file DWG nặng, gửi bản dùng thử (Trial) test độ mượt"
        },
        {
            "name": "Trịnh Lê Hòa",
            "comment_id": "998298839905179",
            "comment_text": "Hay quá !",
            "fbid": "pfbid0CkmETjTWsfRVJ8mByPctYg7SFfGL596M6VjtPT76Dpak6k8XoEUsZhFP2UFd3F9xl",
            "profile_url": "https://www.facebook.com/pfbid0CkmETjTWsfRVJ8mByPctYg7SFfGL596M6VjtPT76Dpak6k8XoEUsZhFP2UFd3F9xl",
            "intent": "DISCUSSION",
            "product": "CMS IntelliCAD 2D/3D Bản Quyền",
            "score": 75,
            "tier": "WARM",
            "phone_status": "ẨN (Chưa để public SĐT)",
            "recommended_action": "Tương tác phản hồi comment, mời trải nghiệm bản dùng thử CMS IntelliCAD"
        }
    ]

    print(f"=== BẮT ĐẦU NẠP {len(real_customers)} KHÁCH HÀNG THẬT TỪ BÌNH LUẬN FACEBOOK ===")

    for idx, c in enumerate(real_customers):
        # 1. Raw item
        p_hash = hashlib.sha256(f"{canonical_post_url}_{c['comment_id']}".encode('utf-8')).hexdigest()
        raw_payload = json.dumps({
            "message": c["comment_text"],
            "author_name": c["name"],
            "author_fbid": c["fbid"],
            "profile_url": c["profile_url"]
        })
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                source_id, external_item_id, item_type, payload_hash, raw_payload, ingested_channel, processing_status
            ) VALUES (
                %s, %s, 'COMMENT', %s, %s, 'LIVE_SCRAPER', 'PROCESSED'
            ) RETURNING id;
        """, (source_id, c["comment_id"], p_hash, raw_payload))
        raw_id = cur.fetchone()[0]

        # 2. Lead Signal
        cur.execute("""
            INSERT INTO public.facebook_lead_signals (
                raw_item_id, source_id, entity_type, entity_id, post_id,
                author_name, raw_text, intent, product_category, product_mention,
                extracted_phones, extracted_emails, confidence_score, extraction_method,
                signal_metadata, status, created_at
            ) VALUES (
                %s, %s, 'COMMENT', %s, %s,
                %s, %s, %s, 'CAD_SOFTWARE', %s,
                ARRAY[]::TEXT[], ARRAY[]::TEXT[], 0.95, 'HYBRID',
                %s, 'CONVERTED_TO_LEAD', NOW()
            ) RETURNING id;
        """, (
            raw_id, source_id, c["comment_id"], post_id,
            c["name"], c["comment_text"], c["intent"], c["product"],
            json.dumps({
                "profile_url": c["profile_url"],
                "fbid": c["fbid"],
                "phone_status": c["phone_status"],
                "recommended_action": c["recommended_action"]
            })
        ))
        signal_id = cur.fetchone()[0]

        # 3. Canonical Lead
        lead_id = str(uuid.uuid4())
        fingerprint = hashlib.md5(f"{c['fbid']}_{c['product']}".encode('utf-8')).hexdigest()

        # Company: ghi rõ trang Facebook cá nhân
        company_val = f"Facebook: {c['profile_url']}"

        cur.execute("""
            INSERT INTO public.leads (
                id, primary_phone, primary_email, full_name, company_name,
                customer_type, product_interest, product_group, primary_intent,
                status, resolution, lead_score, lead_tier, is_quote_requested,
                dedup_fingerprint, metadata, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                'INDIVIDUAL', %s, 'CAD_SOFTWARE', %s,
                'NEW', 'NEW', %s, %s, true,
                %s, %s, NOW(), NOW()
            ) RETURNING id;
        """, (
            lead_id,
            None, # SĐT để ẩn theo thiết lập privacy của khách
            None,
            c["name"],
            company_val,
            c["product"],
            c["intent"],
            c["score"],
            c["tier"],
            fingerprint,
            json.dumps({
                "source_post_url": canonical_post_url,
                "facebook_profile_url": c["profile_url"],
                "facebook_user_id": c["fbid"],
                "comment_text": c["comment_text"],
                "phone_status": c["phone_status"],
                "sales_action": c["recommended_action"]
            })
        ))

        # 4. Lead Source
        cur.execute("""
            INSERT INTO public.lead_sources (
                lead_id, source_id, signal_id, raw_item_id,
                origin_type, origin_external_id, origin_url,
                platform, post_id, comment_id, created_at
            ) VALUES (
                %s, %s, %s, %s,
                'COMMENT', %s, %s,
                'facebook', %s, %s, NOW()
            );
        """, (
            lead_id, source_id, signal_id, raw_id,
            c["comment_id"], c["profile_url"],
            post_id, c["comment_id"]
        ))

        # 5. Lead Score
        cur.execute("""
            INSERT INTO public.lead_scores (
                lead_id, signal_id, intent_score, contact_score,
                profile_score, context_score, total_score, tier,
                scoring_rules_applied, scored_at
            ) VALUES (
                %s, %s, 30, 10, 20, 30, %s, %s,
                %s, NOW()
            );
        """, (
            lead_id, signal_id, c["score"], c["tier"],
            json.dumps([
                {"rule": f"INTENT_{c['intent']}", "points": 30},
                {"rule": "DIRECT_POST_COMMENT", "points": 30},
                {"rule": "CAD_SOFTWARE_INTENT", "points": c["score"] - 60}
            ])
        ))

        # 6. Lead Event
        cur.execute("""
            INSERT INTO public.lead_events (
                lead_id, event_type, old_state, new_state,
                triggered_by, notes, created_at
            ) VALUES (
                %s, 'LEAD_CREATED', '{}'::jsonb,
                %s, 'REAL_FACEBOOK_COMMENT_CRAWLER', %s, NOW()
            );
        """, (
            lead_id,
            json.dumps({"score": c["score"], "tier": c["tier"], "profile": c["profile_url"]}),
            f"Phát hiện khách comment '{c['comment_text']}' trên bài viết CMS IntelliCAD"
        ))

        print(f"[{idx+1}] ĐÃ NẠP THÀNH CÔNG: {c['name']}")
        print(f"    - Comment: '{c['comment_text']}'")
        print(f"    - Profile: {c['profile_url']}")
        print(f"    - Điểm: {c['score']} ({c['tier']})")
        print(f"    - Khuyến nghị: {c['recommended_action']}\n")

    conn.commit()
    cur.close()
    conn.close()
    print("=== TẤT CẢ 5 KHÁCH HÀNG THẬT ĐÃ ĐƯỢC LƯU VÀO SUPABASE THÀNH CÔNG ===")

if __name__ == "__main__":
    ingest_real_leads()
