import subprocess
import re
import json
import time

customers = [
    {
        "name": "Tran Huong Quang",
        "comment": "Ib",
        "url": "https://www.facebook.com/profile.php?id=100001466644991",
        "fbid": "100001466644991"
    },
    {
        "name": "Thu Anh",
        "comment": "Inbox",
        "url": "https://www.facebook.com/profile.php?id=100025221011129",
        "fbid": "100025221011129"
    },
    {
        "name": "Trần Hà Sơn",
        "comment": "Dùng có được mượt mà k bạn? Mình dùng vinacad thấy bị giật giật",
        "url": "https://www.facebook.com/1635855486666999",
        "fbid": "1635855486666999"
    },
    {
        "name": "Trịnh Lê Hòa",
        "comment": "Hay quá !",
        "url": "https://www.facebook.com/pfbid0CkmETjTWsfRVJ8mByPctYg7SFfGL596M6VjtPT76Dpak6k8XoEUsZhFP2UFd3F9xl",
        "fbid": "pfbid0CkmETjTWsfRVJ8mByPctYg7SFfGL596M6VjtPT76Dpak6k8XoEUsZhFP2UFd3F9xl"
    },
    {
        "name": "Chien Vu Duc",
        "comment": "Trả theo năm thì kinh phí tính thế nào ADD",
        "url": "https://www.facebook.com/profile.php?id=100004173033013",
        "fbid": "100004173033013"
    }
]

headers = [
    ("Googlebot", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
    ("Mobile", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
]

inspected_leads = []

for c in customers:
    print("=" * 60)
    print(f"Kiểm tra Facebook khách: {c['name']}")
    print(f"Profile URL: {c['url']}")
    
    # Try fetching public page
    phone_found = None
    email_found = None
    bio_text = ""

    # Fetch with googlebot
    cmd = ["curl", "-sL", "-m", "10", "-A", headers[0][1], c['url']]
    res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    html = res.stdout

    # Search for phone numbers in profile
    phones = re.findall(r'(?:0|\+84)[3|5|7|8|9][0-9]{8}', html)
    # filter out fb tracking numbers if any
    clean_phones = [p for p in phones if not p.startswith('00')]
    if clean_phones:
        phone_found = clean_phones[0]

    # Search for emails
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html)
    clean_emails = [e for e in emails if not any(x in e for x in ('facebook.com', 'fb.com', 'w3.org'))]
    if clean_emails:
        email_found = clean_emails[0]

    # Search for title / bio
    title_m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    og_desc = re.search(r'<meta[^>]+property=[\'"]og:description[\'"][^>]+content=[\'"](.*?)[\'"]', html, re.IGNORECASE)
    if og_desc:
        bio_text = og_desc.group(1)

    print(f"  - Title trang FB: {title_m.group(1) if title_m else 'N/A'}")
    print(f"  - Mô tả Bio: {bio_text if bio_text else 'Không công khai (Private/Ẩn)'}")
    print(f"  - Số điện thoại công khai: {phone_found if phone_found else 'Không để công khai (Ẩn)'}")
    print(f"  - Email công khai: {email_found if email_found else 'Không để công khai (Ẩn)'}")

    c['phone'] = phone_found
    c['email'] = email_found
    c['bio'] = bio_text
    inspected_leads.append(c)

with open("/home/ADMIN/inspected_leads.json", "w", encoding="utf-8") as out:
    json.dump(inspected_leads, out, ensure_ascii=False, indent=2)
