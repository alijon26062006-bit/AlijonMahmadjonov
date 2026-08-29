# AVERIX — лендинг

Статический сайт: HTML + CSS + JS. Без сборки, без npm, без зависимостей —
даже шрифты лежат в репозитории, а не тянутся с чужих серверов.
Открывается двойным кликом по `index.html`.

```
index.html          разметка и весь текст
styles.css          токены и стили (цвета меняются только в :root)
fonts.css           подключение локальных шрифтов
app.js              звёздный фон, меню, появление блоков, форма
fonts/              Unbounded и Manrope, woff2, кириллица + латиница
img/alijon.webp     фото (+ .jpg как запасной вариант)
favicon.svg         иконка вкладки
```

**Вес страницы: 129 КБ по сети** (с gzip). Первый экран — около 87 КБ:
фото грузится лениво, ниже по странице.

## Дизайн

Тема одна — тёмная, светлой версии нет намеренно.

| | |
|---|---|
| Фон | `#07060D` — почти чёрный с фиолетовым подтоном |
| Фиолетовый | `#A472E8` — осветлённый `#7021C1` из логотипа, 5.91:1 |
| Зелёный | `#34C97D` — осветлённый `#038D47` из логотипа, 9.41:1 |
| Текст | `#EDEBF5` (17.1:1) и `#A9A3BE` (8.33:1) |
| Заголовки | Unbounded 600 |
| Текст | Manrope 400–700 |

Градиент фиолетовый → зелёный собран из двух цветов знака.
На нём **тёмный текст `#0A0713`**, а не белый: тёмный даёт 5.84–9.31:1,
белый дал бы 2.14–3.41:1 и провалил бы норму доступности.

Звёздное поле рисуется на canvas один раз при загрузке и дальше не тратит
процессор. Туманности — в исходных цветах логотипа `#7021C1` и `#038D47`.

## Что править чаще всего

| Что | Где |
|---|---|
| Тексты, услуги, FAQ | `index.html` |
| Цвета, отступы | `styles.css` → блок `:root` |
| Telegram для заявок | `app.js` → `TELEGRAM_USER` |
| Домен в мета-тегах | `index.html` → `canonical`, `og:*` |
| Фото | `img/alijon.webp` + `img/alijon.jpg` |

## Деплой на VPS

```bash
rsync -av --delete ./ user@SERVER:/var/www/averix/
```

```nginx
server {
  listen 80;
  server_name averix.tj www.averix.tj;
  root /var/www/averix;
  index index.html;

  gzip on;
  gzip_types text/css application/javascript image/svg+xml;

  # шрифты и картинки не меняются — кешируем надолго
  location ~* \.(woff2|webp|jpg|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
  }
  location ~* \.(css|js)$ {
    expires 7d;
    add_header Cache-Control "public";
  }
  location / {
    try_files $uri $uri/ =404;
  }
}
```

```bash
ln -s /etc/nginx/sites-available/averix /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d averix.tj -d www.averix.tj
```

При 129 КБ на страницу 10 000 посетителей дают около 1,3 ГБ трафика —
это выдержит самый дешёвый VPS. Cloudflare перед сервером снимет и это.

## Перед публикацией

- [ ] Заменить `averix.tj` в `canonical` и `og:url` на реальный домен
- [ ] Положить `og.png` (1200×630) в корень — превью в Telegram и соцсетях
- [ ] Проверить, что заявка из формы доходит в Telegram
- [ ] Проверить на телефоне, а не только в узком окне браузера
