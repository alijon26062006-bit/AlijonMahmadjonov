"""Собирает сайт в один HTML-файл: стили, скрипты и логотип внутри.
Такой файл открывается двойным кликом и его можно отправить в мессенджере.

    python3 build-single.py            -> theburger.html
"""

import base64
import pathlib
import re
import sys

root = pathlib.Path(__file__).parent
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else root / 'theburger.html')

html = (root / 'index.html').read_text()
css = (root / 'css/style.css').read_text()
js = (root / 'js/menu.js').read_text() + '\n' + (root / 'js/main.js').read_text()

logo = base64.b64encode((root / 'assets/logo.jpg').read_bytes()).decode()

body = re.search(r'<body>(.*)</body>', html, re.S).group(1)
body = body.replace('assets/logo.jpg', 'data:image/jpeg;base64,' + logo)
body = re.sub(r'<script src="[^"]+"></script>', '', body)

# фото блюд остаются ссылками на assets/dishes/: если файла нет,
# карточка сама подставит знак заведения

out.write_text(
    '<title>The Burger Душанбе</title>\n'
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Manrope:wght@400;500;600;700'
    '&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">\n'
    f'<style>\n{css}</style>\n'
    f'{body}\n'
    f'<script>\n{js}\n</script>\n'
)
print(f'{out} — {out.stat().st_size // 1024} КБ')
