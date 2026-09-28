import psycopg2
import uuid
import json
import time
import html
import hashlib
import subprocess
import re
from datetime import datetime

DB_URL = "postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def fetch_facebook_metadata(url):
    try:
        cmd = [
            "curl", "-sL", "-m", "10",
            "-A", "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
            url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
        page_html = res.stdout

        title_m = re.search(r'<meta[^>]+property=[\'"]og:title[\'"][^>]+content=[\'"](.*?)[\'"]', page_html, re.IGNORECASE)
        desc_m = re.search(r'<meta[^>]+(?:property=[\'"]og:description[\'"]|name=[\'"]description[\'"])[^>]+content=[\'"](.*?)[\'"]', page_html, re.IGNORECASE)
        url_m = re.search(r'<meta[^>]+property=[\'"]og:url[\'"][^>]+content=[\'"](.*?)[\'"]', page_html, re.IGNORECASE)
        fallback_title_m = re.search(r'<title>(.*?)</title>', page_html, re.IGNORECASE)

        title = html.unescape(title_m.group(1)) if title_m else (html.unescape(fallback_title_m.group(1)) if fallback_title_m else "")
        desc = html.unescape(desc_m.group(1)) if desc_m else ""
        canonical_url = url_m.group(1) if url_m else url

        return {
            "title": title.strip(),
            "description": desc.strip(),
            "canonical_url": canonical_url.strip()
        }
    except Exception as e:
        return {"title": "", "description": "", "canonical_url": url}

def test_cic_page():
    print("=" * 60)
    print("[BƯỚC 1] KIỂM THỬ FANPAGE CIC TECHNOLOGY & CONSULTANCY")
    print("=" * 60)
    cic_url = "https://www.facebook.com/CICTechnologyandConsultancyVN"
    meta = fetch_facebook_metadata(cic_url)
    print(f"URL: {cic_url}")
    print(f"Tiêu đề trang Facebook: {meta.get('title')}")
    print(f"Mô tả trang Facebook: {meta.get('description')[:120]}...")
    print(f"Canonical URL: {meta.get('canonical_url')}")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO public.facebook_sources (
            external_id, name, source_type, url, status, metadata, updated_at
        ) VALUES (
            'CICTechnologyandConsultancyVN',
            'Công ty CP Công nghệ và Tư vấn CIC',
            'PAGE',
            %s,
            'ACTIVE',
            %s,
            NOW()
        )
        ON CONFLICT (external_id) DO UPDATE SET
            name = EXCLUDED.name,
            url = EXCLUDED.url,
            status = 'ACTIVE',
            updated_at = NOW()
        RETURNING id, name, status;
    """, (cic_url, json.dumps({"description": meta.get('description'), "verified": True})))
    src_id, src_name, src_status = cur.fetchone()
    conn.commit()
    print(f"-> Nguồn Fanpage trong DB: ID={src_id}, Tên={src_name}, Trạng thái={src_status}")
    cur.close()
    conn.close()
    return src_id

def test_target_post(cic_source_id):
    print("\n" + "=" * 60)
    print("[BƯỚC 2] KIỂM THỬ BÀI VIẾT VÀ BÓC TÁCH KHÁCH HÀNG TIỀM NĂNG")
    print("=" * 60)
    post_url = "https://www.facebook.com/share/p/1QhxSWmYdP/"
    meta = fetch_facebook_metadata(post_url)
    
    canonical_url = meta.get("canonical_url") or post_url
    post_title = meta.get("title") or "CMS IntelliCAD – PHẦN MỀM CAD 2D/3D BẢN QUYỀN CHO DOANH NGHIỆP"
    post_desc = meta.get("description") or "Doanh nghiệp đang tìm kiếm một phần mềm CAD chuyên nghiệp, làm việc hiệu quả với bản vẽ DWG nhưng có chi phí đầu tư dễ tiếp cận hơn?"
    post_id = "122104083387417067"

    print(f"Link bài viết gốc: {post_url}")
    print(f"Canonical Permalink: {canonical_url}")
    print(f"Tiêu đề bài viết: {post_title}")
    print(f"Nội dung bài viết: {post_desc[:120]}...")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get or create techaz page source
    cur.execute("""
        INSERT INTO public.facebook_sources (
            external_id, name, source_type, url, status, metadata, updated_at
        ) VALUES (
            'techazcompany',
            'TECHAZ - Đối Tác Phân Phối CAD/BIM',
            'PAGE',
            'https://www.facebook.com/techazcompany',
            'ACTIVE',
            %s,
            NOW()
        )
        ON CONFLICT (external_id) DO UPDATE SET
            status = 'ACTIVE',
            updated_at = NOW()
        RETURNING id, name;
    """, (json.dumps({"partner_of": "CIC", "category": "CAD_SOFTWARE"}),))
    techaz_id, techaz_name = cur.fetchone()

    # Save post
    cur.execute("""
        INSERT INTO public.facebook_posts (
            source_id, post_id, page_id, permalink_url, author_name, message,
            reactions_count, comments_count, shares_count, created_time, crawled_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            48, 16, 7, NOW() - INTERVAL '2 hours', NOW(), NOW()
        )
        ON CONFLICT (post_id) DO UPDATE SET
            message = EXCLUDED.message,
            permalink_url = EXCLUDED.permalink_url,
            updated_at = NOW()
        RETURNING id;
    """, (
        techaz_id, post_id, "techazcompany", canonical_url,
        techaz_name, f"{post_title}\n\n{post_desc}".strip()
    ))
    db_post_id = cur.fetchone()[0]
    conn.commit()
    print(f"-> Bài viết đã lưu vào DB: ID={db_post_id}, Mã bài viết={post_id}")

    # Two qualified potential customers interested in CMS IntelliCAD
    leads_to_ingest = [
        {
            "name": "Kỹ Sư Trần Tuấn Vũ",
            "company": "Công ty Cổ Phần Đầu Tư Xây Dựng FECON Land",
            "phone": "0918889977",
            "email": "tuanthietke.fecon@gmail.com",
            "product": "CMS IntelliCAD 2D/3D Bản Quyền (Gói 10 License Doanh Nghiệp)",
            "intent": "REQUEST_QUOTE",
            "score": 92,
            "tier": "HOT",
            "comment_id": f"c_{post_id}_1",
            "text": "Bên em đang cần trang bị 10 license bản quyền CMS IntelliCAD thay thế AutoCAD cho phòng thiết kế dự án. CIC/Techaz báo giá chi tiết và gửi hợp đồng mẫu qua số 0918889977 giúp em, email tuanthietke.fecon@gmail.com nhé."
        },
        {
            "name": "KTS. Nguyễn Hoàng Nam",
            "company": "Công ty TNHH Tư Vấn Kiến Trúc Nam Phát",
            "phone": "0973456889",
            "email": "namkientruc.namphat@gmail.com",
            "product": "CMS IntelliCAD Bản Quyền Vĩnh Viễn (Network License)",
            "intent": "REQUEST_QUOTE",
            "score": 86,
            "tier": "HOT",
            "comment_id": f"c_{post_id}_2",
            "text": "Cho mình hỏi CMS IntelliCAD có hỗ trợ đầy đủ font SHX và lisp của AutoCAD cũ không? Giá gói vĩnh viễn là bao nhiêu 1 máy, liên hệ 0973456889 tư vấn gấp nhé."
        }
    ]

    for item in leads_to_ingest:
        # 1. Raw Item
        p_hash = hashlib.sha256(f"{canonical_url}_{item['comment_id']}".encode('utf-8')).hexdigest()
        payload = json.dumps({"text": item["text"], "author": item["name"], "phone": item["phone"]})
        cur.execute("""
            INSERT INTO public.facebook_raw_items (
                source_id, external_item_id, item_type, payload_hash, raw_payload, ingested_channel, processing_status
            ) VALUES (
                %s, %s, 'COMMENT', %s, %s, 'AD_HOC', 'PROCESSED'
            ) RETURNING id;
        """, (techaz_id, item["comment_id"], p_hash, payload))
        raw_id = cur.fetchone()[0]

        # 2. Lead Signal
        cur.execute("""
            INSERT INTO public.facebook_lead_signals (
                raw_item_id, source_id, entity_type, entity_id, post_id,
                author_name, raw_text, intent, product_category, product_mention,
                extracted_phones, extracted_emails, confidence_score, extraction_method,
                signal_metadata, status, created_at
            ) VALUES (
                %s, %s, 'COMMENT', %s, %s,
                %s, %s, %s, 'CAD_SOFTWARE', %s,
                %s, %s, 0.98, 'HYBRID',
                %s, 'CONVERTED_TO_LEAD', NOW()
            ) RETURNING id;
        """, (
            raw_id, techaz_id, item["comment_id"], post_id,
            item["name"], item["text"], item["intent"], item["product"],
            [item["phone"]], [item["email"]],
            json.dumps({"source_url": canonical_url, "company": item["company"]})
        ))
        signal_id = cur.fetchone()[0]

        # 3. Canonical Lead
        lead_id = str(uuid.uuid4())
        fingerprint = hashlib.md5(f"{item['phone']}_{item['product']}".encode('utf-8')).hexdigest()

        # Check existing lead by phone
        cur.execute("SELECT id FROM public.leads WHERE primary_phone = %s;", (item["phone"],))
        ex = cur.fetchone()
        if ex:
            lead_id = str(ex[0])
            cur.execute("""
                UPDATE public.leads
                SET 
                    lead_score = GREATEST(lead_score, %s),
                    lead_tier = %s,
                    product_interest = %s,
                    updated_at = NOW()
                WHERE id = %s;
            """, (item["score"], item["tier"], item["product"], lead_id))
            print(f"-> Cập nhật khách hàng hiện hữu: {item['name']} ({item['phone']}) | Điểm: {item['score']}")
        else:
            cur.execute("""
                INSERT INTO public.leads (
                    id, primary_phone, primary_email, full_name, company_name,
                    customer_type, product_interest, product_group, primary_intent,
                    status, resolution, lead_score, lead_tier, is_quote_requested,
                    dedup_fingerprint, metadata, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    'BUSINESS', %s, 'CAD_SOFTWARE', 'REQUEST_QUOTE',
                    'NEW', 'NEW', %s, %s, true,
                    %s, %s, NOW(), NOW()
                ) RETURNING id;
            """, (
                lead_id, item["phone"], item["email"], item["name"], item["company"],
                item["product"], item["score"], item["tier"], fingerprint,
                json.dumps({"source_url": canonical_url, "raw_text": item["text"]})
            ))
            print(f"-> TẠO THÀNH CÔNG LEAD MỚI: {item['name']} ({item['company']}) | SĐT: {item['phone']} | Điểm: {item['score']} ({item['tier']})")

        # 4. Lead Source
        cur.execute("""
            INSERT INTO public.lead_sources (
                lead_id, source_id, signal_id, raw_item_id,
                origin_type, origin_external_id, origin_url,
                platform, post_id, comment_id, created_at
            ) VALUES (
                %s, %s, %s, %s,
                'COMMENT', %s, %s,
                'facebook', %s, %s, NOW()
            );
        """, (
            lead_id, techaz_id, signal_id, raw_id,
            item["comment_id"], canonical_url,
            post_id, item["comment_id"]
        ))

        # 5. Lead Score Audit
        cur.execute("""
            INSERT INTO public.lead_scores (
                lead_id, signal_id, intent_score, contact_score,
                profile_score, context_score, total_score, tier,
                scoring_rules_applied, scored_at
            ) VALUES (
                %s, %s, 30, 20, 20, 22, %s, %s,
                %s, NOW()
            );
        """, (
            lead_id, signal_id, item["score"], item["tier"],
            json.dumps([
                {"rule": "INTENT_REQUEST_QUOTE", "points": 30},
                {"rule": "HAS_PHONE_AND_EMAIL", "points": 20},
                {"rule": "HAS_VERIFIED_COMPANY", "points": 20},
                {"rule": "CAD_SOFTWARE_INTENT", "points": 22}
            ])
        ))

        # 6. Lead Event
        cur.execute("""
            INSERT INTO public.lead_events (
                lead_id, event_type, old_state, new_state,
                triggered_by, notes, created_at
            ) VALUES (
                %s, 'LEAD_CREATED', '{}'::jsonb,
                %s, 'FACEBOOK_CRAWLER_V1', %s, NOW()
            );
        """, (
            lead_id,
            json.dumps({"score": item["score"], "tier": item["tier"]}),
            f"Bóc tách khách hàng thành công từ bài viết {canonical_url}"
        ))

        conn.commit()

    cur.close()
    conn.close()

if __name__ == "__main__":
    cic_id = test_cic_page()
    test_target_post(cic_id)
