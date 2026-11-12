# Py·Достон — игровая система для mycourse.tj

Визуальная презентация (25 страниц, 1600×900) с концепцией геймификации курса Python:
11 игровых миров, 38 достижений (RU/TJ), ежедневное возвращение, экономика, соревнования,
путь ученика, макеты интерфейса, техническая реализация и план разработки.

- **PDF:** `PyDoston-mycourse-gamification.pdf`
- **Исходники:** `src/` — HTML/CSS-страницы (`src/pages/p*.html`), графика генерируется в `src/app.js`
  (значки, маскот Пайко, существа Бестиария, радар навыков, каталог достижений, таблица реализации).

## Пересобрать PDF

```bash
cd docs/mycourse-gamification/src
python3 build.py          # склеивает pages/*.html в presentation.html
node render.js            # рендерит ../PyDoston-mycourse-gamification.pdf через Playwright/Chromium
node render.js out.pdf shots 5,6   # плюс PNG-скриншоты выбранных страниц
```

Шрифты: Inter и JetBrains Mono (должны быть установлены в системе).
Таджикские названия — рабочие варианты, перед запуском их стоит вычитать носителю языка.
