import urllib.request
import json

url = 'http://127.0.0.1:5678/api/adhoc/crawl'
payload = {
    'post_url': 'https://www.facebook.com/techazcompany/posts/pfbid08T7HNS8icx71N5ePj7Wbd5HibfiLcXRUdFHCmV18n2VQ6UUut3Q7yGRQjgXZa77hl?rdid=aNuYW0L5KyChtzn4#',
    'content': '',
    'comments': []
}
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as resp:
    print('HTTP STATUS:', resp.status)
    print('RESPONSE:', resp.read().decode('utf-8'))
