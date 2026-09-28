with open('facebook_comment_crawler.py', 'r') as f:
    lines = f.readlines()

# Use double-quoted raw strings to avoid the single-quote escaping issue
# In r"...", single quotes are literal characters
lines[172] = '    title_m = re.search(r"<meta[^>]+property=[' + "'" + '\\"' + ']og:title[' + "'" + '\\"' + '][^>]+content=[' + "'" + '\\"' + '](.*?)[' + "'" + '\\"' + ']", html_text, re.IGNORECASE)\n'

print(repr(lines[172]))
print('Nah, this is getting too complicated. Let me just avoid single quotes in the regex.')

# SIMPLEST approach: just match double-quotes only (Facebook HTML uses double quotes in meta tags)
lines[172] = '    title_m = re.search(r\'<meta[^>]+property="og:title"[^>]+content="(.*?)"\', html_text, re.IGNORECASE)\n'
lines[173] = '    desc_m = re.search(r\'<meta[^>]+(?:property="og:description"|name="description")[^>]+content="(.*?)"\', html_text, re.IGNORECASE)\n'
lines[174] = '    url_m = re.search(r\'<meta[^>]+property="og:url"[^>]+content="(.*?)"\', html_text, re.IGNORECASE)\n'

with open('facebook_comment_crawler.py', 'w') as f:
    f.writelines(lines)

print('Fixed with simplified regex (double-quotes only)')

# Verify
try:
    import importlib, sys
    if 'facebook_comment_crawler' in sys.modules:
        del sys.modules['facebook_comment_crawler']
    import facebook_comment_crawler
    print('Import successful!')
except Exception as e:
    print(f'Error: {e}')
