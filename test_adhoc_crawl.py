import urllib.request
import json

data = json.dumps({
    'post_url': 'https://facebook.com/groups/xd/posts/112233',
    'content': 'Em cần mua 10 tấn thép D18 và máy xoa nền, liên hệ SĐT: 0918889977 gấp với ạ!'
}).encode('utf-8')

req = urllib.request.Request('http://127.0.0.1:5678/api/adhoc/crawl', data=data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as res:
        print(res.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
