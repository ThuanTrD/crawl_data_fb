import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_URI = os.getenv('DATABASE_URL', 'postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres')
conn = psycopg2.connect(DB_URI)
cur = conn.cursor(cursor_factory=RealDictCursor)

for tbl in ['facebook_posts', 'facebook_comments', 'facebook_lead_signals', 'leads']:
    print(f"\n--- COLUMNS IN {tbl} ---")
    cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{tbl}';")
    for r in cur.fetchall():
        print(f"  {r['column_name']} ({r['data_type']})")

conn.close()
