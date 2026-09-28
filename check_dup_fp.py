import os
import psycopg2

conn = psycopg2.connect('postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres')
cur = conn.cursor()
cur.execute("""
    SELECT dedup_fingerprint, count(*), array_agg(primary_phone), array_agg(full_name), array_agg(resolution)
    FROM public.leads
    WHERE dedup_fingerprint IS NOT NULL
    GROUP BY dedup_fingerprint HAVING count(*) > 1
    LIMIT 5;
""")
for r in cur.fetchall():
    print(r)
conn.close()
