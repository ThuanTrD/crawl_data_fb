import re

with open('/home/ADMIN/dashboard/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace api_leads implementation
new_api_leads = '''@app.route("/api/leads", methods=["GET"])
def api_leads():
    try:
        limit = int(request.args.get("limit", 50))
        tier_filter = request.args.get("tier", "")

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        query = """
            SELECT 
                l.id,
                l.full_name,
                l.company_name,
                l.primary_phone,
                l.primary_email,
                l.primary_intent,
                l.product_interest,
                l.lead_score,
                l.lead_tier,
                l.status,
                l.metadata,
                l.created_at,
                s.origin_url AS source_url,
                s.platform,
                fs.name AS source_name,
                fs.url AS group_url,
                fs.source_type
            FROM public.leads l
            LEFT JOIN (
                SELECT DISTINCT ON (lead_id) lead_id, source_id, origin_url, platform, created_at 
                FROM public.lead_sources 
                ORDER BY lead_id, created_at DESC
            ) s ON l.id = s.lead_id
            LEFT JOIN public.facebook_sources fs ON s.source_id = fs.id
        """
        params = []
        conditions = []
        if tier_filter:
            if tier_filter == 'HAS_PHONE':
                conditions.append("l.primary_phone IS NOT NULL AND l.primary_phone != ''")
            elif tier_filter == 'HOT':
                conditions.append("l.lead_score >= 60")
            elif tier_filter == 'INBOX':
                conditions.append("(l.primary_intent = 'URGENT_NEED' OR l.metadata->>'ai_intent' = 'DIRECT_INBOX_REQUEST' OR l.metadata->>'comment_text' ILIKE '%ib%')")
            elif tier_filter == 'PRICING':
                conditions.append("(l.primary_intent = 'REQUEST_QUOTE' OR l.metadata->>'ai_intent' = 'PRICING_LICENSING' OR l.metadata->>'comment_text' ILIKE '%giá%')")
            else:
                conditions.append("l.lead_tier = %s")
                params.append(tier_filter)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY l.lead_score DESC, l.created_at DESC LIMIT %s;"
        params.append(limit)

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        leads = []
        for r in rows:
            meta = r["metadata"] or {}
            if isinstance(meta, str):
                try: meta = json.loads(meta)
                except: meta = {}

            profile_url = meta.get("facebook_profile_url") or meta.get("profile_url")
            if not profile_url and r["company_name"] and r["company_name"].startswith("Facebook:"):
                profile_url = r["company_name"].replace("Facebook:", "").strip()

            leads.append({
                "id": str(r["id"]),
                "full_name": r["full_name"] or "-",
                "company_name": r["company_name"] or "-",
                "phone": r["primary_phone"] or "-",
                "phone_status": meta.get("phone_status") or ("CÔNG KHAI" if r["primary_phone"] else "ẨN (Bảo mật Facebook cá nhân)"),
                "email": r["primary_email"] or "-",
                "intent": meta.get("ai_intent") or r["primary_intent"] or "-",
                "db_intent": r["primary_intent"] or "-",
                "product": r["product_interest"] or "-",
                "score": r["lead_score"] if r["lead_score"] is not None else 0,
                "tier": r["lead_tier"] or "LOW",
                "status": r["status"] or "NEW",
                "source_name": r["source_name"] or "Facebook Source",
                "group_url": r["group_url"] or "-",
                "source_url": r["source_url"] or "-",
                "profile_url": profile_url or "#",
                "comment_text": meta.get("comment_text") or "-",
                "pain_point": meta.get("pain_point") or "-",
                "sales_action": meta.get("sales_action") or "-",
                "messenger_pitch": meta.get("messenger_pitch") or "-",
                "call_lead_in": meta.get("call_lead_in") or "-",
                "created_at": r["created_at"].strftime("%H:%M %d/%m/%Y") if r["created_at"] else "-"
            })

        cur.close()
        conn.close()
        return jsonify({"success": True, "data": leads})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/agent/latest", methods=["GET"])
def api_get_latest_agent_report():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
            SELECT post_id, metadata, message, permalink_url, comments_count, reactions_count, crawled_at
            FROM public.facebook_posts
            ORDER BY crawled_at DESC LIMIT 1;
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row or not row["metadata"]:
            return jsonify({"success": False, "error": "Chưa có bài viết nào được quét"}), 404
        
        meta = row["metadata"]
        if isinstance(meta, str):
            try: meta = json.loads(meta)
            except: meta = {}
        report = meta.get("ai_agent_report") or meta.get("ai_stats")
        return jsonify({
            "success": True, 
            "post_id": row["post_id"],
            "post_title": row["message"],
            "post_url": row["permalink_url"],
            "data": report
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
'''

# Replace from @app.route("/api/leads" to @app.route("/api/analytics/groups"
pattern = re.compile(r'@app\.route\("/api/leads", methods=\["GET"\]\).*?@app\.route\("/api/analytics/groups"', re.DOTALL)
text = pattern.sub(new_api_leads + '\n\n@app.route("/api/analytics/groups"', text)

with open('/home/ADMIN/dashboard/app.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated app.py with rich leads metadata and latest agent report endpoint!")
