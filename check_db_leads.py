import psycopg2
import json

db_url = "postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def check():
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            l.id, l.full_name, l.company_name, l.primary_phone, l.primary_email,
            l.product_interest, l.lead_score, l.lead_tier, fs.name as source_name, s.origin_url
        FROM public.leads l
        LEFT JOIN public.lead_sources s ON l.id = s.lead_id
        LEFT JOIN public.facebook_sources fs ON s.source_id = fs.id
        ORDER BY l.created_at DESC;
    """)
    rows = cur.fetchall()
    print(f"=== TỔNG SỐ KHÁCH HÀNG TIỀM NĂNG TRONG SUPABASE ({len(rows)}) ===")
    for r in rows:
        print(f"ID: {r[0]}")
        print(f"  - Họ tên: {r[1]}")
        print(f"  - Công ty: {r[2]}")
        print(f"  - SĐT: {r[3]}")
        print(f"  - Email: {r[4]}")
        print(f"  - Sản phẩm quan tâm: {r[5]}")
        print(f"  - Điểm tiềm năng: {r[6]} ({r[7]})")
        print(f"  - Nguồn bài viết: {r[8]} | {r[9]}")
        print("-" * 50)
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    check()
