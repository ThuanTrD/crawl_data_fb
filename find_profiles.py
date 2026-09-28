import re
import json

with open('/home/ADMIN/script_decoded.txt', 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

names = ["Tran Huong Quang", "Thu Anh", "Trần Hà Sơn", "Trịnh Lê Hòa", "Chien Vu Duc"]
results = {}

for name in names:
    pos = text.find(f'"{name}"')
    if pos == -1:
        pos = text.find(name)
    if pos == -1:
        continue
        
    window = text[max(0, pos - 1000): min(len(text), pos + 1000)]
    
    # ID: pfbid... or numeric ID
    id_m = re.search(r'\"id\":\"(pfbid[^\"]+|\d{10,20})\"', window)
    pfb_id = id_m.group(1) if id_m else ""
    
    # Numeric ID from media_id (avatar)
    media_m = re.search(r'media_id=(\d{10,20})', window)
    num_id = media_m.group(1) if media_m else ""
    
    # URL
    url_m = re.search(r'\"url\":\"(https:[^\"]+)\"', window)
    raw_url = url_m.group(1).replace('\\/', '/') if url_m else ""
    if 'techaz' in raw_url.lower():
        raw_url = ""

    # Construct best profile URL
    if num_id:
        profile_url = f"https://www.facebook.com/profile.php?id={num_id}"
    elif pfb_id:
        profile_url = f"https://www.facebook.com/{pfb_id}"
    elif raw_url:
        profile_url = raw_url
    else:
        profile_url = f"https://www.facebook.com/search/top?q={name.replace(' ', '%20')}"

    results[name] = {
        "name": name,
        "pfb_id": pfb_id,
        "numeric_id": num_id,
        "profile_url": profile_url
    }
    print(f"Khách: {name}")
    print(f"  - Facebook ID: {num_id or pfb_id}")
    print(f"  - Profile Link: {profile_url}\n")

with open("/home/ADMIN/customer_profiles.json", "w", encoding="utf-8") as out:
    json.dump(results, out, ensure_ascii=False, indent=2)
