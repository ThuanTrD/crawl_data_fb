import psycopg2

db_url = "postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def check_counts():
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    tables = [
        "leads", "lead_sources", "lead_scores", "lead_events",
        "facebook_lead_signals", "facebook_raw_items", "facebook_posts", "facebook_sources"
    ]
    for t in tables:
        cur.execute(f"SELECT count(*) FROM public.{t};")
        cnt = cur.fetchone()[0]
        print(f"Table public.{t}: {cnt} rows")

    cur.execute("SELECT id, full_name, primary_phone, product_interest FROM public.leads LIMIT 5;")
    leads = cur.fetchall()
    print("\nLeads sample:")
    for l in leads:
        print(" ", l)

    cur.close()
    conn.close()

if __name__ == "__main__":
    check_counts()
