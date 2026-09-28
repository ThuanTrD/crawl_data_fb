"""
Facebook Comment Crawler - Live Deep Comment Extraction Engine

Crawls all public comments and customer profile metadata from a given Facebook post URL:
- Canonical post ID and source resolution
- Server-Side Rendered (SSR) Comet GraphQL script payload extraction via Googlebot/public crawler UA
- Complete Unicode and HTML entity unescaping
- Extracts: comment_id, message, author_name, author_fbid/user_id, profile_url, created_time, parent_comment_id
- Merges user-supplied manual comments/text if provided
"""

import re
import json
import html
import time
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional

def unescape_facebook_text(text: str) -> str:
    """Decodes all Facebook Javascript and Unicode escapes."""
    if not text:
        return ""
    try:
        text = text.replace('\\"', '"').replace('\\/', '/')
        text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
        text = html.unescape(text)
        return text.strip()
    except Exception:
        return text.strip()

def fetch_facebook_post_raw_payload(url: str) -> str:
    """Fetches full HTML with public crawler User-Agent to bypass login blocks and retrieve SSR payload"""
    try:
        cmd = [
            "curl", "-sL", "-m", "15",
            "-A", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "-H", "Accept-Language: vi,en;q=0.9",
            url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
        return res.stdout or ""
    except Exception as e:
        print(f"Error fetching Facebook payload: {e}")
        return ""

def extract_comments_from_html(html_text: str, canonical_url: str) -> List[Dict[str, Any]]:
    """Extracts all public comments and commenter profiles from Facebook Comet SSR scripts"""
    all_comments = []
    seen_ids = set()

    # Pattern for comment nodes inside ScheduledServerJS
    matches = re.finditer(
        r'\"legacy_fbid\":\"(\d+)\",\"body\":\{\"text\":\"([^\"]+)\"\},\"created_time\":(\d+),\"author\":\{\"__typename\":[\"\']User[\"\'],\"name\":[\"\']([^\"\']+)[\"\'](?:,[^}]*?\"id\":[\"\']([^\"\']+)[\"\'])?',
        html_text
    )

    for m in matches:
        comment_id = m.group(1)
        raw_msg = m.group(2)
        created_time = m.group(3)
        author_name = m.group(4)
        author_id = m.group(5) or ""

        if comment_id in seen_ids:
            continue
        seen_ids.add(comment_id)

        clean_msg = unescape_facebook_text(raw_msg)
        clean_author = unescape_facebook_text(author_name)

        # Search nearby text for numeric media_id (profile ID)
        fbid_pos = html_text.find(comment_id)
        snippet = html_text[max(0, fbid_pos - 600): min(len(html_text), fbid_pos + 900)]
        uid_m = re.search(r'media_id=(\d{10,20})', snippet)
        user_id = uid_m.group(1) if uid_m else author_id

        # Profile URL
        if user_id:
            profile_url = f"https://www.facebook.com/profile.php?id={user_id}"
        elif author_id:
            profile_url = f"https://www.facebook.com/{author_id}"
        else:
            profile_url = canonical_url

        # Check for phone and email in comment text
        pm = re.search(r'(0[3|5|7|8|9][0-9]{8})', clean_msg)
        em = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', clean_msg)

        all_comments.append({
            "comment_id": comment_id,
            "author_name": clean_author,
            "comment_text": clean_msg,
            "created_time": int(created_time) if created_time.isdigit() else int(time.time()),
            "user_id": user_id,
            "profile_url": profile_url,
            "extracted_phone": pm.group(1) if pm else None,
            "extracted_email": em.group(1) if em else None,
            "phone_status": "CÔNG KHAI (Tìm thấy trong bình luận)" if pm else "ẨN (Cần nhắn tin Messenger / Zalo)",
            "source": "FACEBOOK_LIVE_CRAWLER"
        })

    return all_comments

def crawl_facebook_post_and_all_comments(
    url: str,
    manual_content: Optional[str] = None,
    manual_comments: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Crawls a Facebook post and all of its comments, merging manual inputs if provided.
    """
    # 1. Fetch raw page
    html_text = fetch_facebook_post_raw_payload(url)

    # 2. Extract OpenGraph post metadata
    title_m = re.search(r'<meta[^>]+property=[\'"]og:title[\'"][^>]+content=[\'"](.*?)[\'"]', html_text, re.IGNORECASE)
    desc_m = re.search(r'<meta[^>]+(?:property=[\'"]og:description[\'"]|name=[\'"]description[\'"])[^>]+content=[\'"](.*?)[\'"]', html_text, re.IGNORECASE)
    url_m = re.search(r'<meta[^>]+property=[\'"]og:url[\'"][^>]+content=[\'"](.*?)[\'"]', html_text, re.IGNORECASE)
    fallback_title_m = re.search(r'<title>(.*?)</title>', html_text, re.IGNORECASE)

    post_title = unescape_facebook_text(title_m.group(1)) if title_m else (unescape_facebook_text(fallback_title_m.group(1)) if fallback_title_m else "Bài Viết Facebook")
    post_desc = unescape_facebook_text(desc_m.group(1)) if desc_m else ""
    canonical_url = url_m.group(1) if url_m else url

    # Clean canonical URL
    if "122104083387417067" in url or "122104083387417067" in canonical_url:
        canonical_url = "https://www.facebook.com/techazcompany/posts/122104083387417067/"
        post_id = "122104083387417067"
        source_id = "techazcompany"
        source_name = "TECHAZ - Giải Pháp CAD/BIM Doanh Nghiệp"
    elif "CICTechnologyandConsultancyVN" in url or "CICTechnologyandConsultancyVN" in canonical_url:
        canonical_url = "https://www.facebook.com/CICTechnologyandConsultancyVN"
        post_id = f"post_{int(time.time())}"
        source_id = "CICTechnologyandConsultancyVN"
        source_name = "Công ty CP Công nghệ và Tư vấn CIC"
    else:
        # Extract generic ID
        m_id = re.search(r'posts/([^/?]+)', url) or re.search(r'share/p/([^/?]+)', url)
        post_id = m_id.group(1)[:99] if m_id else f"post_{int(time.time())}"
        source_id = "adhoc_source"
        source_name = "Nguồn Facebook Quét Trực Tiếp"

    # 3. Extract all comments from HTML
    comments = extract_comments_from_html(html_text, canonical_url)

    # 4. If manual comments are passed, merge them
    if manual_comments:
        for idx, mc in enumerate(manual_comments):
            cid = mc.get("id") or f"manual_{idx+1}"
            if not any(c["comment_id"] == cid for c in comments):
                comments.append({
                    "comment_id": cid,
                    "author_name": mc.get("author") or f"Khách hàng #{idx+1}",
                    "comment_text": mc.get("text") or "",
                    "created_time": int(time.time()),
                    "user_id": mc.get("fbid") or "",
                    "profile_url": mc.get("profile_url") or canonical_url,
                    "extracted_phone": mc.get("phone"),
                    "extracted_email": mc.get("email"),
                    "phone_status": "CÔNG KHAI" if mc.get("phone") else "ẨN",
                    "source": "MANUAL_INPUT"
                })

    # 5. If manual content (raw text lines) is passed, parse each line
    if manual_content and manual_content.strip():
        lines = [l.strip() for l in manual_content.split('\n') if l.strip()]
        for idx, line in enumerate(lines):
            pm = re.search(r'(0[3|5|7|8|9][0-9]{8})', line)
            em = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', line)
            cid = f"text_line_{idx+1}"
            if not any(c["comment_text"] == line for c in comments):
                comments.append({
                    "comment_id": cid,
                    "author_name": f"Khách hàng {idx+1}",
                    "comment_text": line,
                    "created_time": int(time.time()),
                    "user_id": "",
                    "profile_url": canonical_url,
                    "extracted_phone": pm.group(1) if pm else None,
                    "extracted_email": em.group(1) if em else None,
                    "phone_status": "CÔNG KHAI" if pm else "ẨN",
                    "source": "MANUAL_TEXT"
                })

    return {
        "post_info": {
            "post_id": post_id,
            "source_id": source_id,
            "source_name": source_name,
            "canonical_url": canonical_url,
            "post_title": post_title,
            "post_description": post_desc,
            "total_crawled_comments": len(comments),
            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "comments": comments
    }

if __name__ == "__main__":
    target = "https://www.facebook.com/share/p/1QhxSWmYdP/"
    print(f"Crawling comments for: {target}")
    res = crawl_facebook_post_and_all_comments(target)
    print(f"Total Comments Crawled: {res['post_info']['total_crawled_comments']}")
    for c in res["comments"]:
        print(f"- {c['author_name']}: '{c['comment_text']}' ({c['profile_url']})")
