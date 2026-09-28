import subprocess
import re
import json

def fetch_with_curl(url):
    cmd = [
        "curl", "-sL",
        "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        url
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    return res.stdout

def analyze():
    url = "https://www.facebook.com/share/p/1QhxSWmYdP/"
    html = fetch_with_curl(url)
    print(f"Downloaded HTML size: {len(html)} bytes")
    
    # Title
    m_title = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    print("TITLE:", m_title.group(1) if m_title else "None")
    
    # Meta description / og:description
    for m in re.finditer(r'<meta[^>]+(?:property|name)=[\'"](?:og:description|description)[\'"][^>]+content=[\'"](.*?)[\'"]', html, re.IGNORECASE):
        print("DESCRIPTION:", m.group(1))

    # Meta og:url
    m_url = re.search(r'<meta[^>]+property=[\'"]og:url[\'"][^>]+content=[\'"](.*?)[\'"]', html, re.IGNORECASE)
    print("OG:URL:", m_url.group(1) if m_url else "None")

    # Meta og:title
    m_og_title = re.search(r'<meta[^>]+property=[\'"]og:title[\'"][^>]+content=[\'"](.*?)[\'"]', html, re.IGNORECASE)
    print("OG:TITLE:", m_og_title.group(1) if m_og_title else "None")

if __name__ == "__main__":
    analyze()
