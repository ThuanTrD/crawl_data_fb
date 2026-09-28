import subprocess
import re
import json

def parse_exact_comments():
    url = "https://www.facebook.com/techazcompany/posts/122104083387417067/"
    cmd = ["curl", "-sL", "-A", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", url]
    res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    html = res.stdout

    scripts = re.findall(r'<script[^>]*type=[\'"]application/json[\'"][^>]*>(.*?)</script>', html, re.DOTALL)
    
    target_script = None
    for idx, sc in enumerate(scripts):
        if 'Tran Huong Quang' in sc or 'vinacad' in sc:
            target_script = sc
            print(f"Matched script #{idx}")
            break

    if not target_script:
        print("Script not found")
        return

    # Unescape unicode
    decoded = target_script.encode().decode('unicode-escape', errors='ignore')

    decoded = decoded.encode('utf-8', 'replace').decode('utf-8', 'ignore')
    with open("/home/ADMIN/script_decoded.txt", "w", encoding="utf-8", errors="replace") as f:
        f.write(decoded)

    print(f"Decoded length: {len(decoded)}")

    # Extract all comments and authors
    # In Comet comments, find: "feedback":... or "comment":...
    # Let's find patterns where author name and text are adjacent
    pattern = r'\"author\":\{[^\}]*\"name\":\"([^\"]+)\"[^\}]*\"url\":\"([^\"]+)\"[^\}]*\}.*?\"body\":\{\"text\":\"([^\"]+)\"'
    
    # Or search for comment blocks
    # Each comment has "legacy_fbid":"...", "body":{"text":"..."}, "author":{...}
    comments = re.findall(r'\"legacy_fbid\":\"(\d+)\"[^\{]*\"body\":\{\"text\":\"([^\"]+)\"', decoded)
    print(f"\nFound {len(comments)} comments by legacy_fbid:")
    for c in comments:
        print(f"  Comment ID: {c[0]} | Text: {c[1]}")

    # Now let's extract each comment with its author
    # We can split by "__typename":"Comment"
    blocks = decoded.split('"__typename":"Comment"')
    print(f"\nTotal Comment Blocks: {len(blocks) - 1}")
    
    real_leads = []
    for b in blocks[1:]:
        # text
        text_m = re.search(r'\"body\":\{\"text\":\"([^\"]+)\"', b)
        text = text_m.group(1) if text_m else ""
        
        # author
        author_m = re.search(r'\"author\":\{[^\}]*?\"name\":\"([^\"]+)\"[^\}]*?\"url\":\"([^\"]+)\"', b)
        if not author_m:
            author_m = re.search(r'\"author\":\{[^\}]*?\"name\":\"([^\"]+)\"', b)
            author_name = author_m.group(1) if author_m else "Ẩn danh"
            author_url = ""
        else:
            author_name = author_m.group(1)
            author_url = author_m.group(2).replace('\\/', '/')

        # skip Techaz page comments (author replying to clients)
        if "Techaz" in author_name:
            continue

        print(f"\n[KHÁCH HÀNG THẬT]")
        print(f"  Họ tên: {author_name}")
        print(f"  Nội dung cmt: {text}")
        print(f"  Profile URL: {author_url}")
        real_leads.append({
            "name": author_name,
            "comment": text,
            "profile_url": author_url
        })

    with open("/home/ADMIN/real_leads.json", "w", encoding="utf-8") as f:
        json.dump(real_leads, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    parse_exact_comments()
