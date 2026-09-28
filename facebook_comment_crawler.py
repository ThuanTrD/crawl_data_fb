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
            "curl", "-sL", "-m", "8",
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
    """Extracts all public comments and commenter profiles from Facebook Comet SSR scripts.
    
    Two-pass approach:
      Pass 1: Find all comment blocks via legacy_fbid + body.text
      Pass 2: For each comment, scan a wide context window to extract author info:
              - author name
              - author pfbid or numeric ID
              - numeric media_id from profile_picture URI (most reliable for profile URL)
    """
    all_comments = []
    seen_ids = set()

    # Find all legacy_fbid positions first for non-greedy scanning
    fbid_positions = []
    for m in re.finditer(r'"legacy_fbid":"(\d+)"', html_text):
        fbid_positions.append((m.group(1), m.start()))

    for comment_id, start_pos in fbid_positions:
        if comment_id in seen_ids:
            continue

        # Extract a generous chunk after this legacy_fbid to find body.text, created_time, and author
        chunk_end = min(len(html_text), start_pos + 3000)
        chunk = html_text[start_pos:chunk_end]

        # Extract message text
        msg_m = re.search(r'"body":\{"text":"([^"]*)"', chunk)
        if not msg_m:
            continue

        raw_msg = msg_m.group(1)

        # Extract created_time
        time_m = re.search(r'"created_time":(\d+)', chunk)
        created_time = time_m.group(1) if time_m else str(int(time.time()))

        # Extract author name  
        name_m = re.search(r'"author":\{[^}]*?"name":"([^"]+)"', chunk)
        if not name_m:
            name_m = re.search(r'"name":"([^"]+)"', chunk[chunk.find('"author"'):] if '"author"' in chunk else chunk)
        author_name = name_m.group(1) if name_m else "Khach hang"

        # Extract author ID (can be pfbid... or numeric)
        author_id = ""
        aid_m = re.search(r'"author":\{"__typename":"User","id":"([^"]+)"', chunk)
        if aid_m:
            author_id = aid_m.group(1)

        # Extract numeric media_id from profile_picture URI (most reliable numeric profile ID)
        wide_start = max(0, start_pos - 200)
        wide_end = min(len(html_text), start_pos + 4000)
        wide_chunk = html_text[wide_start:wide_end]
        
        media_id = ""
        author_pos_in_wide = wide_chunk.find('"author"')
        if author_pos_in_wide >= 0:
            author_section = wide_chunk[author_pos_in_wide:author_pos_in_wide + 1500]
            mid_m = re.search(r'media_id(?:%3D|=)(\d{5,20})', author_section)
            if not mid_m:
                mid_m = re.search(r'media_id=(\d{5,20})', author_section)
            if mid_m:
                media_id = mid_m.group(1)

        if not media_id:
            mid_matches = re.findall(r'media_id(?:%3D|=)(\d{5,20})', wide_chunk)
            if not mid_matches:
                mid_matches = re.findall(r'media_id=(\d{5,20})', wide_chunk)
            if mid_matches:
                media_id = mid_matches[0]

        # Determine best user_id (prefer numeric media_id, then author_id)
        if media_id and media_id.isdigit():
            user_id = media_id
        elif author_id and author_id.isdigit():
            user_id = author_id
        else:
            user_id = author_id

        # Build profile URL
        if media_id and media_id.isdigit():
            profile_url = f"https://www.facebook.com/profile.php?id={media_id}"
        elif author_id and author_id.isdigit():
            profile_url = f"https://www.facebook.com/profile.php?id={author_id}"
        elif author_id:
            profile_url = f"https://www.facebook.com/{author_id}"
        else:
            profile_url = canonical_url

        seen_ids.add(comment_id)

        clean_msg = unescape_facebook_text(raw_msg)
        clean_author = unescape_facebook_text(author_name)

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
            "phone_status": "CONG KHAI (Tim thay trong binh luan)" if pm else "AN (Can nhan tin Messenger / Zalo)",
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
    title_m = re.search(r'<meta[^>]+property="og:title"[^>]+content="(.*?)"', html_text, re.IGNORECASE)
    desc_m = re.search(r'<meta[^>]+(?:property="og:description"|name="description")[^>]+content="(.*?)"', html_text, re.IGNORECASE)
    url_m = re.search(r'<meta[^>]+property="og:url"[^>]+content="(.*?)"', html_text, re.IGNORECASE)
    fallback_title_m = re.search(r'<title>(.*?)</title>', html_text, re.IGNORECASE)

    post_title = unescape_facebook_text(title_m.group(1)) if title_m else (unescape_facebook_text(fallback_title_m.group(1)) if fallback_title_m else "Bai Viet Facebook")
    post_desc = unescape_facebook_text(desc_m.group(1)) if desc_m else ""
    canonical_url = url_m.group(1) if url_m else url

    # Clean canonical URL
    if "122104083387417067" in url or "122104083387417067" in canonical_url:
        canonical_url = "https://www.facebook.com/techazcompany/posts/122104083387417067/"
        post_id = "122104083387417067"
        source_id = "techazcompany"
        source_name = "TECHAZ - Giai Phap CAD/BIM Doanh Nghiep"
    elif "CICTechnologyandConsultancyVN" in url or "CICTechnologyandConsultancyVN" in canonical_url:
        canonical_url = "https://www.facebook.com/CICTechnologyandConsultancyVN"
        post_id = f"post_{int(time.time())}"
        source_id = "CICTechnologyandConsultancyVN"
        source_name = "Cong ty CP Cong nghe va Tu van CIC"
    else:
        # Extract generic ID
        m_id = re.search(r'posts/([^/?]+)', url) or re.search(r'share/p/([^/?]+)', url)
        post_id = m_id.group(1)[:99] if m_id else f"post_{int(time.time())}"
        source_id = "adhoc_source"
        source_name = "Nguon Facebook Quet Truc Tiep"

    # 3. Extract all comments from HTML
    comments = extract_comments_from_html(html_text, canonical_url)

    # 4. If manual comments are passed, merge them
    if manual_comments:
        for idx, mc in enumerate(manual_comments):
            cid = mc.get("id") or f"manual_{idx+1}"
            if not any(c["comment_id"] == cid for c in comments):
                comments.append({
                    "comment_id": cid,
                    "author_name": mc.get("author") or f"Khach hang #{idx+1}",
                    "comment_text": mc.get("text") or "",
                    "created_time": int(time.time()),
                    "user_id": mc.get("fbid") or "",
                    "profile_url": mc.get("profile_url") or canonical_url,
                    "extracted_phone": mc.get("phone"),
                    "extracted_email": mc.get("email"),
                    "phone_status": "CONG KHAI" if mc.get("phone") else "AN",
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
                    "author_name": f"Khach hang {idx+1}",
                    "comment_text": line,
                    "created_time": int(time.time()),
                    "user_id": "",
                    "profile_url": canonical_url,
                    "extracted_phone": pm.group(1) if pm else None,
                    "extracted_email": em.group(1) if em else None,
                    "phone_status": "CONG KHAI" if pm else "AN",
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
        print(f"- {c['author_name']}: '{c['comment_text']}' (profile: {c['profile_url']}, user_id: {c['user_id']})")
