import os
import psycopg2

conn = psycopg2.connect('postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres')
cur = conn.cursor()
cur.execute("""
    SELECT primary_phone, count(*)
    FROM public.leads
    WHERE primary_phone IS NOT NULL
    GROUP BY primary_phone HAVING count(*) > 1;
""")
phones = cur.fetchall()
print("Duplicate phones count:", len(phones))

cur.execute("""
    SELECT primary_email, count(*)
    FROM public.leads
    WHERE primary_email IS NOT NULL
    GROUP BY primary_email HAVING count(*) > 1;
""")
emails = cur.fetchall()
print("Duplicate emails count:", len(emails))
conn.close()
