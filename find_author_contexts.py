with open('/home/ADMIN/script_decoded.txt', 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

names = ['Tran Huong Quang', 'Thu Anh', 'Trần Hà Sơn', 'Trịnh Lê Hòa', 'Chien Vu Duc']
for n in names:
    pos = 0
    while True:
        pos = text.find(n, pos)
        if pos == -1:
            break
        print('=' * 60)
        print(f'NAME: {n} at position {pos}')
        snippet = text[max(0, pos - 200): min(len(text), pos + 400)]
        print(snippet)
        pos += len(n)
