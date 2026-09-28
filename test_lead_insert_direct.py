import psycopg2
import uuid
import json
import hashlib
import traceback

DB_URL = "postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def run_test():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    try:
        # 1. Get techaz source
        cur.execute("SELECT id FROM public.facebook_sources WHERE external_id = 'techazcompany';")
        src_row = cur.fetchone()
        source_id = src_row[0]
        
        # 2. Insert Post
        cur.execute("""
            INSERT INTO public.facebook_posts (
                source_id, post_id, page_id, permalink_url, author_name, message,
                reactions_count, comments_count, shares_count, created_time, crawled_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                24, 8, 3, NOW() - INTERVAL '1 hour', NOW(), NOW()
            )
            ON CONFLICT (post_id) DO UPDATE SET message = EXCLUDED.message
            RETURNING id;
        """, (
            source_id,
            "122104083387417067",
            "techazcompany",
            "https://www.facebook.com/share/p/1QhxSWmYdP/",
            "TECHAZ - Giải Pháp CAD/BIM Doanh Nghiệp",
            "CMS IntelliCAD – PHẦN MỀM CAD 2D/3D BẢN QUYỀN CHO DOANH NGHIỆP"
        ))
        post_id = cur.fetchone()[0]
        print("[1] Post OK, ID:", post_id)
        
        # 3. Insert Raw item
        p_hash = hashlib.sha256(b"raw_item_test_1").hexdigest()
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                source_id, external_item_id, item_type, payload_hash, raw_payload, ingested_channel, processing_status
            ) VALUES (
                %s, %s, 'COMMENT', %s, %s, 'AD_HOC', 'PROCESSED'
            ) RETURNING id;
        """, (source_id, "comment_123", p_hash, json.dumps({"msg": "test"})))
        raw_id = cur.fetchone()[0]
        print("[2] Raw item OK, ID:", raw_id)
        
        # 4. Insert Signal
        cur.execute("""
            INSERT INTO public.facebook_lead_signals (
                raw_item_id, source_id, entity_type, entity_id, post_id,
                author_name, raw_text, intent, product_category, product_mention,
                extracted_phones, extracted_emails, confidence_score, extraction_method,
                signal_metadata, status, created_at
            ) VALUES (
                %s, %s, 'COMMENT', %s, %s,
                %s, %s, 'REQUEST_QUOTE', 'CAD_SOFTWARE', %s,
                %s, %s, 0.98, 'HYBRID',
                %s, 'NEW', NOW()
            ) RETURNING id;
        """, (
            raw_id, source_id, "comment_123", "122104083387417067",
            "Kỹ Sư Trần Tuấn Vũ", "Báo giá 10 license CMS IntelliCAD", "CMS IntelliCAD 2D/3D Bản Quyền",
            ["0918889977"], ["tuanthietke.fecon@gmail.com"],
            json.dumps({"company": "Công ty CP Đầu Tư Xây Dựng FECON Land"})
        ))
        signal_id = cur.fetchone()[0]
        print("[3] Signal OK, ID:", signal_id)
        
        # 5. Insert Lead
        lead_id = str(uuid.uuid4())
        fingerprint = hashlib.md5(b"0918889977_fecon_cad").hexdigest()
        cur.execute("""
            INSERT INTO public.leads (
                id, primary_phone, primary_email, full_name, company_name,
                customer_type, product_interest, product_group, primary_intent,
                status, resolution, lead_score, lead_tier, is_quote_requested,
                dedup_fingerprint, metadata, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                'BUSINESS', %s, 'CAD_SOFTWARE', 'REQUEST_QUOTE',
                'NEW', 'NEW', 85, 'HOT', true,
                %s, %s, NOW(), NOW()
            ) RETURNING id;
        """, (
            lead_id, "0918889977", "tuanthietke.fecon@gmail.com", "Kỹ Sư Trần Tuấn Vũ",
            "Công ty CP Đầu Tư Xây Dựng FECON Land", "CMS IntelliCAD 2D/3D Bản Quyền (Gói 10 License Doanh Nghiệp)",
            fingerprint, json.dumps({"source_post": "https://www.facebook.com/share/p/1QhxSWmYdP/"})
        ))
        lead_res_id = cur.fetchone()[0]
        print("[4] Lead OK, ID:", lead_res_id)
        
        # 6. Insert lead_sources
        cur.execute("""
            INSERT INTO public.lead_sources (
                lead_id, source_id, signal_id, raw_item_id,
                origin_type, origin_external_id, origin_url,
                platform, post_id, comment_id, created_at
            ) VALUES (
                %s, %s, %s, %s,
                'COMMENT', %s, %s,
                'facebook', %s, %s, NOW()
            ) RETURNING id;
        """, (
            lead_res_id, source_id, signal_id, raw_id,
            "comment_123", "https://www.facebook.com/share/p/1QhxSWmYdP/",
            "122104083387417067", "comment_123"
        ))
        print("[5] Lead source OK")
        
        conn.commit()
        print("ALL STEPS COMMITTED SUCCESSFULLY!")
    except Exception as e:
        conn.rollback()
        print("ERROR IN STEP:")
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    run_test()
