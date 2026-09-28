import re
import json

with open("/home/ADMIN/script_decoded.txt", "r", encoding="utf-8", errors="replace") as f:
    text = f.read()

# Let's inspect the exact JSON structure around legacy_fbid
# e.g. "legacy_fbid":"1402187242091381"
fbids = [
    "1402187242091381",
    "2031927328198409",
    "27746288788362140",
    "998298839905179",
    "1625699959066326",
    "2217541085476041",
    "1741114150424551",
    "27824779367216406",
    "1671215511242213",
    "947397780994948"
]

results = []

for fbid in fbids:
    idx = text.find(fbid)
    if idx == -1:
        continue
    # Grab a window around this comment:
    # Look forwards and backwards 1500 chars
    window = text[max(0, idx - 1500): min(len(text), idx + 1500)]
    
    # Body text
    body_m = re.search(r'\"body\":\{\"text\":\"([^\"]+)\"', window)
    body = body_m.group(1) if body_m else ""
    
    # Author
    # Look for "author":{"__typename":"User","id":"...","name":"...","url":"..."}
    author_m = re.search(r'\"author\":\{[^\}]*?\"id\":\"([^\"]+)\"[^\}]*?\"name\":\"([^\"]+)\"[^\}]*?\"url\":\"([^\"]+)\"', window)
    if not author_m:
        author_m = re.search(r'\"author\":\{[^\}]*?\"name\":\"([^\"]+)\"[^\}]*?\"url\":\"([^\"]+)\"', window)
        if author_m:
            author_id = ""
            author_name = author_m.group(1)
            author_url = author_m.group(2).replace('\\/', '/')
        else:
            # fallback
            name_m = re.search(r'\"name\":\"([^\"]+)\"', window)
            author_name = name_m.group(1) if name_m else "Ẩn danh"
            author_id = ""
            author_url = ""
    else:
        author_id = author_m.group(1)
        author_name = author_m.group(2)
        author_url = author_m.group(3).replace('\\/', '/')
        
    print("=" * 60)
    print(f"COMMENT ID: {fbid}")
    print(f"BODY: {body}")
    print(f"AUTHOR NAME: {author_name}")
    print(f"AUTHOR ID: {author_id}")
    print(f"AUTHOR URL: {author_url}")

    results.append({
        "fbid": fbid,
        "body": body,
        "author_name": author_name,
        "author_id": author_id,
        "author_url": author_url
    })

with open("/home/ADMIN/extracted_real_fb_comments.json", "w", encoding="utf-8") as out:
    json.dump(results, out, ensure_ascii=False, indent=2)
