import subprocess
import re
import json

def parse_page():
    url = "https://www.facebook.com/share/p/1QhxSWmYdP/"
    cmd = ["curl", "-sL", "-A", "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)", url]
    res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    html = res.stdout

    # Extract JSON or text
    print("Searching for post content and comments...")
    
    # Check meta tags
    meta_tags = re.findall(r'<meta[^>]+>', html)
    for m in meta_tags:
        if 'title' in m.lower() or 'desc' in m.lower() or 'author' in m.lower():
            print("META:", m)
            
    # Search for text around "IntelliCAD"
    idx = html.find("IntelliCAD")
    if idx != -1:
        snippet = html[max(0, idx - 200): min(len(html), idx + 800)]
        # clean tags
        clean_snippet = re.sub(r'<[^>]+>', ' ', snippet)
        clean_snippet = re.sub(r'\s+', ' ', clean_snippet)
        print("\nSnippet near IntelliCAD:\n", clean_snippet)

if __name__ == "__main__":
    parse_page()
