import json
import re

with open('/home/ADMIN/script_decoded.txt', 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

# Search for the comments array or edges:
# "node":{"id":..., "legacy_fbid":"...", "body":{"text":"..."}, "author":{"__typename":"User","name":"...","id":"..."}}
pattern = r'\{\"node\":\{\"id\":[^\}]*?\"legacy_fbid\":\"(\d+)\",\"body\":\{\"text\":\"([^\"]+)\"\},\"created_time\":(\d+),\"author\":\{\"__typename\":\"User\",\"name\":\"([^\"]+)\"(?:,[^}]*?\"id\":\"([^\"]+)\")?'

# Also search with broader regex
matches = re.finditer(r'\"legacy_fbid\":\"(\d+)\",\"body\":\{\"text\":\"([^\"]+)\"\},\"created_time\":(\d+),\"author\":\{\"__typename\":[\"\']User[\"\'],\"name\":[\"\']([^\"\']+)[\"\'](?:,[^}]*?\"id\":[\"\']([^\"\']+)[\"\'])?', text)

all_commenters = []
seen_ids = set()

for m in matches:
    fbid, comment_text, created_time, author_name = m.group(1), m.group(2), m.group(3), m.group(4)
    author_id = m.group(5) or ""
    
    if fbid in seen_ids:
        continue
    seen_ids.add(fbid)
    
    # Try to find numeric Facebook ID from avatar or context
    # e.g. media_id=100004173033013
    fbid_pos = text.find(fbid)
    snippet = text[max(0, fbid_pos - 500): min(len(text), fbid_pos + 800)]
    
    uid_m = re.search(r'media_id=(\d{10,20})', snippet)
    user_id = uid_m.group(1) if uid_m else ""
    
    # User profile URL
    profile_url = f"https://www.facebook.com/profile.php?id={user_id}" if user_id else f"https://www.facebook.com/{author_id}" if author_id else ""

    all_commenters.append({
        "comment_id": fbid,
        "author_name": author_name,
        "comment_text": comment_text,
        "created_time": int(created_time),
        "user_id": user_id,
        "profile_url": profile_url
    })

print(f"TOTAL REAL COMMENTERS EXTRACTED: {len(all_commenters)}\n")
for idx, c in enumerate(all_commenters):
    print(f"[{idx+1}] Khách hàng: {c['author_name']}")
    print(f"    - Bình luận: {c['comment_text']}")
    print(f"    - Mã cmt Facebook: {c['comment_id']}")
    print(f"    - User ID Facebook: {c['user_id']}")
    print(f"    - Link Profile: {c['profile_url']}")
    print("-" * 50)

with open("/home/ADMIN/real_facebook_leads_extracted.json", "w", encoding="utf-8") as f:
    json.dump(all_commenters, f, ensure_ascii=False, indent=2)
