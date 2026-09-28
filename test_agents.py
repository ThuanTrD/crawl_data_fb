import subprocess
import re

agents = [
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
]

url = "https://www.facebook.com/share/p/1QhxSWmYdP/"

for ua in agents:
    cmd = ["curl", "-sL", "-A", ua, url]
    res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    html = res.stdout
    title = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    og_desc = re.search(r'<meta[^>]+property=[\'"]og:description[\'"][^>]+content=[\'"](.*?)[\'"]', html, re.IGNORECASE)
    og_url = re.search(r'<meta[^>]+property=[\'"]og:url[\'"][^>]+content=[\'"](.*?)[\'"]', html, re.IGNORECASE)
    print("--- UA:", ua[:30], "---")
    print("Length:", len(html))
    print("Title:", title.group(1) if title else "None")
    print("OG URL:", og_url.group(1) if og_url else "None")
    print("OG Desc:", og_desc.group(1)[:150] if og_desc else "None")
