import psycopg2
import json

db_url = 'postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres'

def purge_and_setup():
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    print("[1/4] Truncating demo & test data from tables...")
    truncate_query = """
    TRUNCATE TABLE 
      public.lead_events,
      public.lead_scores,
      public.lead_sources,
      public.lead_notification_queue,
      public.leads,
      public.facebook_lead_signals,
      public.facebook_comments,
      public.facebook_posts,
      public.facebook_raw_items,
      public.facebook_collection_logs,
      public.facebook_errors,
      public.facebook_source_metrics,
      public.facebook_processing_jobs
    CASCADE;
    """
    cur.execute(truncate_query)

    print("[2/4] Cleaning up all test sources...")
    cur.execute("""
    DELETE FROM public.facebook_sources 
    WHERE external_id NOT IN ('CICTechnologyandConsultancyVN', 'techazcompany');
    """)

    print("[3/4] Adding/Updating official CIC Page & Target Page Sources...")
    # Add CIC official page
    cur.execute("""
    INSERT INTO public.facebook_sources (
        name, source_type, external_id, url, status, metadata
    ) VALUES (
        'Công ty CP Công nghệ và Tư vấn CIC',
        'PAGE',
        'CICTechnologyandConsultancyVN',
        'https://www.facebook.com/CICTechnologyandConsultancyVN',
        'ACTIVE',
        '{"description": "Trang chính thức Công ty CP Công nghệ và Tư vấn CIC - Giải pháp CAD, BIM, kết cấu, địa kỹ thuật"}'::jsonb
    )
    ON CONFLICT (external_id) DO UPDATE SET 
        status = 'ACTIVE',
        url = EXCLUDED.url,
        name = EXCLUDED.name,
        metadata = EXCLUDED.metadata;
    """)

    # Add Techaz / CMS IntelliCAD page source
    cur.execute("""
    INSERT INTO public.facebook_sources (
        name, source_type, external_id, url, status, metadata
    ) VALUES (
        'TECHAZ - Giải Pháp CAD/BIM Doanh Nghiệp',
        'PAGE',
        'techazcompany',
        'https://www.facebook.com/techazcompany',
        'ACTIVE',
        '{"description": "Trang giải pháp phần mềm CMS IntelliCAD bản quyền"}'::jsonb
    )
    ON CONFLICT (external_id) DO UPDATE SET 
        status = 'ACTIVE',
        url = EXCLUDED.url,
        name = EXCLUDED.name,
        metadata = EXCLUDED.metadata;
    """)

    conn.commit()

    print("[4/4] Verification check:")
    cur.execute("SELECT count(*) FROM public.leads;")
    leads_cnt = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM public.facebook_posts;")
    posts_cnt = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM public.facebook_raw_items;")
    raw_cnt = cur.fetchone()[0]
    cur.execute("SELECT id, name, external_id, url, status FROM public.facebook_sources;")
    sources = cur.fetchall()

    print(f"-> Leads in DB: {leads_cnt}")
    print(f"-> Posts in DB: {posts_cnt}")
    print(f"-> Raw items in DB: {raw_cnt}")
    print(f"-> Total Sources in DB: {len(sources)}")
    for s in sources:
        print(f"   - [{s[0]}] {s[1]} | ID: {s[2]} | URL: {s[3]} | Status: {s[4]}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    purge_and_setup()
