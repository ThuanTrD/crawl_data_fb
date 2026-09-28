import sys
import traceback

sys.path.append('/home/ADMIN/dashboard')
from adhoc_collector import process_adhoc_post

url = 'https://www.facebook.com/techazcompany/posts/pfbid08T7HNS8icx71N5ePj7Wbd5HibfiLcXRUdFHCmV18n2VQ6UUut3Q7yGRQjgXZa77hl?rdid=aNuYW0L5KyChtzn4#'

print(f"Testing URL: {url}")
try:
    res = process_adhoc_post(url)
    print("SUCCESS:", res)
except Exception as e:
    print("FAILED WITH ERROR:")
    traceback.print_exc()
