import sys
sys.path.append('/home/ADMIN/dashboard')
from adhoc_collector import process_adhoc_post

url = 'https://www.facebook.com/techazcompany/posts/pfbid08T7HNS8icx71N5ePj7Wbd5HibfiLcXRUdFHCmV18n2VQ6UUut3Q7yGRQjgXZa77hl?rdid=aNuYW0L5KyChtzn4#'
comment_text = "Em chào anh, bên em công ty xây dựng cần mua 5 bản quyền CMS IntelliCAD, bên mình báo giá qua số 0988776655 giúp em nhé."

print("Testing with customer comment...")
res = process_adhoc_post(url, raw_content=comment_text)
print("RESULT:")
print(res)
