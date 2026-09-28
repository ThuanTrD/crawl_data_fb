import psycopg2
import psycopg2.extras
import json
import hashlib
import time

DB_URL = "postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def debug_run():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    print("TX status 1:", conn.get_transaction_status()) # 0 = IDLE
    
    # Check source
    cur.execute("SELECT id, name, source_type FROM public.facebook_sources WHERE external_id = 'techazcompany';")
    src = cur.fetchone()
    source_db_id = src[0]
    source_name = src[1]
    print("TX status 2 (after select):", conn.get_transaction_status()) # 1 = ACTIVE
    
    # Save post
    try:
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
            source_db_id,
            "122104083387417067",
            "techazcompany",
            "https://www.facebook.com/techazcompany/posts/122104083387417067/",
            source_name,
            "CMS IntelliCAD Test"
        ))
        p_id = cur.fetchone()[0]
        print("Post ID:", p_id)
        conn.commit()
        print("TX status 3 (after commit):", conn.get_transaction_status())
    except Exception as e:
        print("Error in post:", e)
        conn.rollback()

    # Raw item
    payload_str = json.dumps({"msg": "test"})
    payload_hash = hashlib.sha256(b"test1234").hexdigest()
    
    print("TX status 4 (before raw_item):", conn.get_transaction_status())
    try:
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                source_id, external_item_id, item_type, payload_hash, raw_payload, ingested_channel, processing_status
            ) VALUES (
                %s, %s, 'COMMENT', %s, %s, 'AD_HOC', 'PROCESSED'
            ) RETURNING id;
        """, (
            source_db_id,
            "c_test_99",
            payload_hash,
            payload_str
        ))
        raw_id = cur.fetchone()[0]
        print("Raw ID:", raw_id)
        conn.commit()
    except Exception as e:
        print("Error in raw_item:", e)
        conn.rollback()

    cur.close()
    conn.close()

if __name__ == "__main__":
    debug_run()
