"""
Facebook Lead Intelligence V1 - Enhanced Ad-hoc Single Post & Page Collector

Allows users to submit a specific Facebook Post URL or Page URL on-demand.
Pipeline:
  Post/Page URL (and optional content/comments)
    ↓
  Live Meta Fetch (curl with facebookexternalhit / Googlebot)
    ↓
  Save Raw Post & Comments in facebook_raw_items & facebook_posts
    ↓
  AI Lead Detection & Intent Extraction
    ↓
  Lead Scoring & Entity Resolution (HOT / WARM / COLD tiers, Anti-duplicate)
    ↓
  Lead Creation / Update & Provenance (public.leads & public.lead_sources)
    ↓
  Instant Telegram Notification Dispatch & External Webhook Dispatch
"""

import os
import re
import sys
import json
import time
import html
import uuid
import hashlib
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional
import psycopg2
import psycopg2.extras

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"
)

def fetch_facebook_metadata(url: str) -> Dict[str, str]:
    """Fetches OpenGraph title, description, and canonical URL from Facebook using public crawler UA"""
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

def extract_facebook_ids(url: str) -> Dict[str, str]:
    """Extracts source_id, post_id, source_type from Facebook URLs"""
    result = {
        "source_id": "CICTechnologyandConsultancyVN",
        "post_id": f"post_{int(time.time())}",
        "source_type": "PAGE"
    }

    # Clean hash and query params for regex matching
    clean_url = url.split('#')[0]

    # Groups
    m_grp = re.search(r'groups/([^/]+)/posts/([^/?]+)', clean_url)
    if m_grp:
        result["source_id"] = m_grp.group(1)
        result["post_id"] = m_grp.group(2)
        result["source_type"] = "GROUP"
        return result

    # Share link e.g. /share/p/1QhxSWmYdP/
    m_share = re.search(r'share/p/([^/?]+)', clean_url)
    if m_share:
        result["post_id"] = m_share.group(1)
        result["source_id"] = "techazcompany"
        result["source_type"] = "PAGE"
        return result

    # Standard Page Posts e.g. /techazcompany/posts/pfbid08T7... or /techazcompany/posts/122104083387417067/
    m_post = re.search(r'facebook\.com/([^/]+)/posts/([^/?]+)', clean_url)
    if m_post:
        result["source_id"] = m_post.group(1)
        result["post_id"] = m_post.group(2)[:99] # limit varchar length
        result["source_type"] = "PAGE"
        return result

    # Fanpage base URL e.g. /CICTechnologyandConsultancyVN
    m_page = re.search(r'facebook\.com/([a-zA-Z0-9\.\-_]+)/?$', clean_url)
    if m_page:
        result["source_id"] = m_page.group(1)
        result["post_id"] = f"feed_{m_page.group(1)}"[:99]
        result["source_type"] = "PAGE"
        return result

    return result

def process_adhoc_post(
    post_url: str,
    raw_content: Optional[str] = None,
    raw_comments: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Crawls all comments from Facebook post and runs the Customer Intelligence Agent.
    """
    from customer_intelligence_agent import run_agent_pipeline_on_post
    
    agent_report = run_agent_pipeline_on_post(
        post_url,
        manual_content=raw_content,
        manual_comments=raw_comments
    )
    
    extracted_leads = []
    for c in agent_report.get("customers", []):
        extracted_leads.append({
            "lead_id": c.get("user_id") or c.get("author_name"),
            "author": c.get("author_name"),
            "company": f"Facebook: {c.get('profile_url')}",
            "phone": c.get("phone") or "-",
            "email": c.get("email") or "-",
            "intent": c.get("intent"),
            "sub_intent": c.get("sub_intent"),
            "product": c.get("product_mention"),
            "score": c.get("score"),
            "tier": c.get("tier"),
            "action": "PROCESSED",
            "text": c.get("comment_text"),
            "profile_url": c.get("profile_url"),
            "phone_status": c.get("phone_status"),
            "pain_point": c.get("pain_point"),
            "recommended_action": c.get("recommended_action"),
            "messenger_pitch": c.get("messenger_pitch"),
            "call_lead_in": c.get("call_lead_in"),
            "user_id": c.get("user_id") or c.get("author_name"),
            "dedup_fingerprint": hashlib.md5(f"{c.get('user_id') or c.get('author_name')}_{agent_report.get('post_id')}".encode('utf-8')).hexdigest(),
            "notified": False
        })

    return {
        "success": True,
        "post_url": agent_report.get("canonical_url", post_url),
        "post_title": agent_report.get("post_title", ""),
        "source_name": agent_report.get("source_name", "Facebook Source"),
        "post_id": agent_report.get("post_id", ""),
        "total_analyzed": agent_report["statistics"]["total_comments_crawled"],
        "leads_found": agent_report["statistics"]["total_prospective_customers"],
        "leads": extracted_leads,
        "agent_report": agent_report
    }

if __name__ == "__main__":
    target_url = "https://www.facebook.com/techazcompany/posts/pfbid08T7HNS8icx71N5ePj7Wbd5HibfiLcXRUdFHCmV18n2VQ6UUut3Q7yGRQjgXZa77hl?rdid=aNuYW0L5KyChtzn4#"
    print(f"Executing ad-hoc crawl on: {target_url}")
    res = process_adhoc_post(target_url)
    print(json.dumps(res, indent=2, ensure_ascii=False))
