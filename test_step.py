import psycopg2
import psycopg2.extras
import json
import traceback

DB_URL = "postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def test_step():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cur.execute("SELECT id, name, source_type FROM public.facebook_sources WHERE external_id = 'techazcompany';")
        src = cur.fetchone()
        print("Source:", dict(src) if src else "None")
        source_id = src["id"] if src else None
        
        print("Testing facebook_posts insert...")
        cur.execute("""
            INSERT INTO public.facebook_posts (
                source_id, post_id, page_id, permalink_url, author_name, message,
                reactions_count, comments_count, shares_count, created_time, crawled_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                24, 8, 3, NOW() - INTERVAL '1 hour', NOW(), NOW()
            )
            ON CONFLICT (post_id) DO UPDATE SET
                message = EXCLUDED.message,
                permalink_url = EXCLUDED.permalink_url,
                updated_at = NOW()
            RETURNING id;
        """, (
            source_id,
            "122104083387417067",
            "techazcompany",
            "https://www.facebook.com/techazcompany/posts/122104083387417067/",
            "TECHAZ - Giải Pháp CAD/BIM Doanh Nghiệp",
            "CMS IntelliCAD – PHẦN MỀM CAD 2D/3D BẢN QUYỀN CHO DOANH NGHIỆP"
        ))
        post_id = cur.fetchone()[0]
        print("Post created with ID:", post_id)
        
        print("Testing raw_items insert...")
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                source_id, external_item_id, item_type, payload_hash, raw_payload, ingested_channel, processing_status
            ) VALUES (
                %s, %s, 'COMMENT', %s, %s, 'AD_HOC', 'PROCESSED'
            ) RETURNING id;
        """, (
            source_id,
            "c_test_1",
            "testhash1234567890",
            json.dumps({"msg": "hello"})
        ))
        raw_id = cur.fetchone()[0]
        print("Raw item created with ID:", raw_id)
        conn.commit()
    except Exception as e:
        print("ERROR AT STEP:")
        traceback.print_exc()
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    test_step()
