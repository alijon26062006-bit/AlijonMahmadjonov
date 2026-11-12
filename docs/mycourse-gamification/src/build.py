# Собирает страницы в один HTML: python3 build.py
import pathlib

root = pathlib.Path(__file__).parent
import sys
pdir = sys.argv[1] if len(sys.argv) > 1 else "pages"
out = sys.argv[2] if len(sys.argv) > 2 else "presentation.html"
pages = sorted((root / pdir).glob("*.html"))
body = "\n".join(p.read_text(encoding="utf-8") for p in pages)
html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Py·Достон — игровая система mycourse.tj</title>
<link rel="stylesheet" href="style.css"></head><body>
{body}
<script src="app.js"></script></body></html>"""
(root / out).write_text(html, encoding="utf-8")
print(f"{len(pages)} pages -> {out}")
