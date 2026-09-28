import psycopg2

conn = psycopg2.connect('postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres')
cur = conn.cursor()
cur.execute("UPDATE public.lead_sources SET origin_url = 'https://www.facebook.com/techazcompany/posts/122104083387417067/' WHERE post_id = '122104083387417067';")
conn.commit()
print('Updated post_url successfully')
cur.close()
conn.close()
