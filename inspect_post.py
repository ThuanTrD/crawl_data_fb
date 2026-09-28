import urllib.request
import re
import json

def inspect_fb_post():
    url = "https://www.facebook.com/share/p/1QhxSWmYdP/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            final_url = resp.geturl()
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return

    print(f"Final URL: {final_url}")
    
    # Extract titles and descriptions
    titles = re.findall(r'<title>(.*?)</title>', html, re.IGNORECASE)
    og_title = re.findall(r'<meta[^>]+property=[\'"]og:title[\'"][^>]+content=[\'"](.*?)[\'"]', html, re.IGNORECASE)
    og_desc = re.findall(r'<meta[^>]+property=[\'"]og:description[\'"][^>]+content=[\'"](.*?)[\'"]', html, re.IGNORECASE)
    desc = re.findall(r'<meta[^>]+name=[\'"]description[\'"][^>]+content=[\'"](.*?)[\'"]', html, re.IGNORECASE)
    
    print("Page Title:", titles[0] if titles else "None")
    print("OG Title:", og_title[0] if og_title else "None")
    print("OG Description:", og_desc[0] if og_desc else (desc[0] if desc else "None"))
    
    # Check if there are JSON-LD or script tags with post message
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    print(f"Total script tags: {len(scripts)}")
    
    # Search for text mentions
    post_keywords = ["IntelliCAD", "Techaz", "bản quyền", "báo giá", "giá"]
    for kw in post_keywords:
        cnt = html.count(kw)
        print(f"Keyword '{kw}' count in HTML: {cnt}")

if __name__ == "__main__":
    inspect_fb_post()
