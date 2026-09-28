import subprocess
import re
import json

def parse_exact_comments():
    url = "https://www.facebook.com/techazcompany/posts/122104083387417067/"
    cmd = ["curl", "-sL", "-A", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", url]
    res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    html = res.stdout

    # Find the script containing comments
    scripts = re.findall(r'<script[^>]*type=[\'"]application/json[\'"][^>]*>(.*?)</script>', html, re.DOTALL)
    
    target_script = None
    for sc in scripts:
        if 'Trần Hà Sơn' in sc or 'Dùng có được mượt mà k bạn' in sc:
            target_script = sc
            break

    if not target_script:
        print("Could not find script with target comments")
        return

    print(f"Target script found! Length: {len(target_script)}")
    
    # Save script to inspect JSON structure
    with open("/home/ADMIN/comments_dump.json", "w", encoding="utf-8") as f:
        f.write(target_script)

    # Let's search for comment patterns in this script
    # Look for comment objects:
    # "legacy_fbid":"...", "body":{"text":"..."}, "author":{"name":"...","url":"..."}
    # Let's find matches
    items = []
    
    # Regex search for comment blocks
    # In Facebook Comet comments:
    # {"__typename":"Comment", ... "body":{"text":"..."}, ... "author":{"__typename":"User","id":"...","name":"...","url":"..."}}
    
    # Find all author names and their URLs
    author_matches = re.findall(r'\"author\":\{\"__typename\":[\"\']User[\"\'],\"id\":[\"\']([^\"\']+)[\"\'],\"name\":[\"\']([^\"\']+)[\"\'],\"url\":[\"\']([^\"\']+)[\"\']', target_script)
    print(f"Found {len(author_matches)} author matches:")
    for a in author_matches:
        print("  Author:", a[1].encode().decode('unicode-escape', errors='ignore'), "| ID:", a[0], "| URL:", a[2].replace('\\/', '/'))

    # Let's inspect snippet around each author
    for a_id, a_name, a_url in author_matches:
        clean_name = a_name.encode().decode('unicode-escape', errors='ignore')
        pos = target_script.find(a_name)
        snippet = target_script[max(0, pos - 500): min(len(target_script), pos + 500)]
        
        # Find text
        text_m = re.findall(r'\"text\":[\"\']([^\"\']+)[\"\']', snippet)
        print(f"\n--- Author: {clean_name} ---")
        print(f"URL: {a_url.replace(chr(92) + '/', '/')}")
        texts = [t.encode().decode('unicode-escape', errors='ignore') for t in text_m if t not in ('COMMENT', 'REACTION', clean_name)]
        print(f"Texts near author: {texts}")

if __name__ == "__main__":
    parse_exact_comments()
