import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_URI = os.getenv('DATABASE_URL', 'postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres')
conn = psycopg2.connect(DB_URI)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== 1. CHECK CONSTRAINTS ON LEADS & LEAD_SCORES ===")
cur.execute("""
    SELECT conname, pg_get_constraintdef(c.oid) as def
    FROM pg_constraint c
    JOIN pg_class t ON c.conrelid = t.oid
    WHERE t.relname IN ('leads', 'lead_scores', 'facebook_raw_items')
    ORDER BY t.relname, conname;
""")
for r in cur.fetchall():
    print(f"[{r['conname']}] {r['def']}")

print("\n=== 2. FOREIGN KEYS WITHOUT INDEXES ===")
cur.execute("""
    SELECT
        tc.table_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND NOT EXISTS (
          SELECT 1
          FROM pg_index i
          JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
          JOIN pg_class c ON c.oid = i.indrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          WHERE c.relname = tc.table_name
            AND a.attname = kcu.column_name
            AND n.nspname = 'public'
      );
""")
unindexed_fks = cur.fetchall()
for fk in unindexed_fks:
    print(f"Table: {fk['table_name']}.{fk['column_name']} -> {fk['foreign_table_name']}.{fk['foreign_column_name']}")

print("\n=== 3. TABLE ROW COUNTS ===")
tables = [
    'facebook_sources', 'facebook_raw_items', 'facebook_posts', 'facebook_comments',
    'facebook_processing_jobs', 'facebook_lead_signals', 'leads', 'lead_sources',
    'lead_events', 'lead_scores', 'facebook_collection_logs', 'facebook_errors',
    'facebook_source_metrics', 'system_flags', 'lead_notification_queue'
]
for t in tables:
    try:
        cur.execute(f"SELECT count(*) FROM public.{t};")
        cnt = cur.fetchone()['count']
        print(f"  {t}: {cnt} rows")
    except Exception as e:
        print(f"  {t}: ERROR ({e})")
        conn.rollback()

conn.close()
