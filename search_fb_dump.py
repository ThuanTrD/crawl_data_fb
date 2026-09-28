import subprocess
import re
import json

def search_fb_dump():
    url = "https://www.facebook.com/techazcompany/posts/122104083387417067/"
    cmd = ["curl", "-sL", "-A", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", url]
    res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    html = res.stdout
    print(f"Downloaded desktop HTML size: {len(html)} bytes")

    # Search for script tags containing JSON data
    scripts = re.findall(r'<script[^>]*type=[\'"]application/json[\'"][^>]*>(.*?)</script>', html, re.DOTALL)
    print(f"Found {len(scripts)} JSON script blocks")
    
    found_comments = []
    keywords = ["ib", "inbox", "báo giá", "quan tâm", "giá", "tư vấn", "lisp"]

    for idx, sc in enumerate(scripts):
        for kw in keywords:
            if kw in sc.lower():
                print(f"Script #{idx} contains keyword '{kw}' (length {len(sc)})")
                # Look for feedback or comment objects
                # e.g. "body":{"text":"..."} or "comment" or "author"
                matches = re.findall(r'\"body\":\{\"text\":[\"\']([^\"\']+)[\"\']\}', sc)
                if matches:
                    print(f"  -> Found body texts: {matches}")
                # Look for actor/author names
                actors = re.findall(r'\"author\":\{\"__typename\":\"User\",\"name\":[\"\']([^\"\']+)[\"\']', sc)
                if actors:
                    print(f"  -> Found User authors: {actors}")

    # Also search directly in raw html
    for kw in ["ib", "inbox"]:
        matches = [m.start() for m in re.finditer(r'\b' + kw + r'\b', html, re.IGNORECASE)]
        print(f"Direct raw HTML mentions of '{kw}': {len(matches)}")
        for pos in matches[:5]:
            snippet = html[max(0, pos - 100):min(len(html), pos + 100)]
            print(f"   Snippet: {snippet.strip()}")

if __name__ == "__main__":
    search_fb_dump()
