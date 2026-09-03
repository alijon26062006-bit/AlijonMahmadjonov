"""Собирает сайт в один HTML-файл: стили, скрипты и фото витрины внутри.
Такой файл можно просто открыть в браузере или отправить в мессенджере.

    python3 build-single.py            -> realphone.html
"""

import base64
import pathlib
import re
import sys

root = pathlib.Path(__file__).parent
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else root / 'realphone.html')

html = (root / 'index.html').read_text()
css = (root / 'css/style.css').read_text()
js = (root / 'js/products.js').read_text() + '\n' + (root / 'js/main.js').read_text()

photo = base64.b64encode((root / 'assets/shop.jpg').read_bytes()).decode()
photo_uri = 'data:image/jpeg;base64,' + photo

body = re.search(r'<body>(.*)</body>', html, re.S).group(1)
body = body.replace('assets/shop.jpg', photo_uri)
body = re.sub(r'<script src="[^"]+"></script>', '', body)

# карта грузится с внешнего сайта — в одном файле вместо неё ссылка на карты
body = re.sub(
    r'<iframe title="Карта".*?</iframe>',
    '<a class="contacts__pin" href="https://www.google.com/maps/search/Dushanbe" '
    'target="_blank" rel="noopener">'
    '<b data-ru="Душанбе, ул. Айни 24" data-tj="Душанбе, кӯчаи Айнӣ 24"></b>'
    '<span data-ru="Открыть на карте" data-tj="Дар харита кушодан"></span></a>',
    body, flags=re.S)

extra = """
.contacts__pin {
  display: flex; flex-direction: column; gap: 6px; justify-content: center;
  height: 320px; padding: 32px; border-radius: 16px; text-align: center;
  background: var(--blue-pale); border: 1px solid var(--line);
}
.contacts__pin b { font-size: 18px; }
.contacts__pin span { color: var(--blue); font-weight: 600; }
"""

out.write_text(
    '<title>RealPhone Душанбе</title>\n'
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">\n'
    f'<style>\n{css}\n{extra}</style>\n'
    f'{body}\n'
    f'<script>\n{js}\n</script>\n'
)
print(f'{out} — {out.stat().st_size // 1024} КБ')
