#!/usr/bin/env python3
"""
Deep Acceptance Audit & Verification Script for Facebook Lead Crawler & Intelligence System
"""

import sys
import os
import json
import urllib.request
import urllib.parse
import psycopg2

BASE_URL = os.getenv("DASHBOARD_URL", "http://127.0.0.1:5678")
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"
)

results = []

def record(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    icon = "[OK]" if passed else "[FAIL]"
    print(f"{icon} {test_name}: {status} - {detail}")
    results.append({"test": test_name, "status": status, "detail": detail})

def http_get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.read().decode("utf-8")

def http_post(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, r.read().decode("utf-8")

print("="*70)
print("     NGHIEM THU CHUYEN SAU TOAN DIEN HE THONG (DEEP AUDIT)     ")
print("="*70)

# 1. Dashboard Homepage
try:
    status, html = http_get("/")
    has_escape = "function escapeHtml" in html
    has_kb_modal = "openKnowledgeModal" in html and "closeKnowledgeModal" in html
    has_copy = "copyToClipboard" in html and "execCommand" in html
    record("1. Dashboard Web UI Rendering", status == 200 and len(html) > 5000, f"Size: {len(html)} bytes")
    record("2. Client Script: escapeHtml Defined", has_escape, "No ReferenceError when searching posts")
    record("3. Client Script: Knowledge Base Modal Functions", has_kb_modal, "Modal open/close functions present")
    record("4. Client Script: HTTP-Safe Clipboard Copy", has_copy, "Fallback to execCommand for non-HTTPS")
except Exception as e:
    record("1-4. Web UI & Scripts Check", False, str(e))

# 5. /api/stats
try:
    status, text = http_get("/api/stats")
    data = json.loads(text)
    s_data = data.get("data", {})
    record("5. API /api/stats", data.get("success") is True, f"Total Leads: {s_data.get('total_leads')}, HOT: {s_data.get('hot_leads')}")
except Exception as e:
    record("5. API /api/stats", False, str(e))

# 6. /api/knowledge (278 CIC products in Supabase)
try:
    status, text = http_get("/api/knowledge")
    data = json.loads(text)
    items = data.get("data", [])
    record("6. API /api/knowledge", data.get("success") is True and len(items) >= 200, f"Products loaded: {len(items)}")
except Exception as e:
    record("6. API /api/knowledge", False, str(e))

# 7. Phase 1 Keyword Search: /api/keyword/search-posts
try:
    status, text = http_post("/api/keyword/search-posts", {"keyword": "enjicad", "top_k": 3})
    data = json.loads(text)
    posts = data.get("posts", [])
    record("7. Phase 1: Keyword Search Posts", data.get("success") is True and len(posts) > 0, f"Found {len(posts)} posts for 'enjicad'")
except Exception as e:
    record("7. Phase 1: Keyword Search Posts", False, str(e))

# 8. AI Sales Pitch Generation: POST /api/leads/<id>/pitch
try:
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, product_interest FROM public.leads ORDER BY updated_at DESC LIMIT 1;")
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        lead_id = str(row[0])
        status, text = http_post(f"/api/leads/{lead_id}/pitch", {})
        data = json.loads(text)
        pitch = data.get("pitch", {})
        messenger_pitch = pitch.get("messenger_pitch", "")
        agent = pitch.get("ai_agent", "")
        record("8. AI Sales Pitch Generation (/pitch)", data.get("success") is True and len(messenger_pitch) > 30, f"Lead: {row[1]}, Agent: {agent}")
    else:
        record("8. AI Sales Pitch Generation (/pitch)", False, "No leads in DB to test")
except Exception as e:
    record("8. AI Sales Pitch Generation (/pitch)", False, str(e))

# 9. Leads Listing & Grouping: /api/leads
try:
    status, text = http_get("/api/leads")
    data = json.loads(text)
    leads = data.get("data", [])
    has_pitches = sum(1 for l in leads if l.get("messenger_pitch") and not l.get("messenger_pitch").startswith("["))
    record("9. API /api/leads Enriched Data", data.get("success") is True and len(leads) > 0, f"Total: {len(leads)}, With Ready Pitch: {has_pitches}")
except Exception as e:
    record("9. API /api/leads Enriched Data", False, str(e))

# 10. UTF-8 Export: /api/export/leads
try:
    req = urllib.request.Request(f"{BASE_URL}/api/export/leads?scope=all")
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read()
        has_bom = raw.startswith(b'\xef\xbb\xbf')
        record("10. Excel CSV Export (UTF-8 BOM)", r.status == 200 and has_bom, f"Size: {len(raw)} bytes, UTF-8 BOM present: {has_bom}")
except Exception as e:
    record("10. Excel CSV Export (UTF-8 BOM)", False, str(e))

# 11. System Terminal Logs: /api/logs
try:
    status, text = http_get("/api/logs")
    data = json.loads(text)
    logs = data.get("logs", [])
    record("11. Real-time System Logs Buffer", data.get("success") is True and len(logs) > 0, f"Active log entries: {len(logs)}")
except Exception as e:
    record("11. Real-time System Logs Buffer", False, str(e))

print("="*70)
total_tests = len(results)
passed_tests = sum(1 for r in results if r["status"] == "PASS")
print(f"KET QUA NGHIEM THU: {passed_tests}/{total_tests} DAT YEU CAU ({(passed_tests/total_tests)*100:.1f}%)")
print("="*70)

if passed_tests == total_tests:
    print(">>> TOAN BO HE THONG HOAT DONG HOAN HAO, SAN SANG SU DUNG! <<<")
    sys.exit(0)
else:
    print(">>> PHAT HIEN LOI CHUA DAT, CAN KIEM TRA TIEP! <<<")
    sys.exit(1)
