# AVERIX — лендинг

Статический сайт: HTML + CSS + JS, без сборки и без зависимостей.
Открывается двойным кликом по `index.html` — ничего устанавливать не нужно.

```
index.html    разметка и весь текст
styles.css    токены и стили (цвета меняются только в :root)
app.js        меню, появление блоков, отправка формы
favicon.svg   иконка вкладки
```

## Что править чаще всего

| Что | Где |
|---|---|
| Тексты, услуги, FAQ | `index.html` |
| Цвета, отступы, шрифты | `styles.css` → блок `:root` |
| Telegram для заявок | `app.js` → `TELEGRAM_USER` |
| Домен в мета-тегах | `index.html` → `canonical`, `og:*` |

Цвета сняты пипеткой с логотипа: фиолетовый `#7021C1`, зелёный `#038D47`.
Зелёный даёт 4.28:1 на белом — для мелкого текста используйте `#04703A`.

## Деплой на VPS

```bash
# 1. загрузить файлы
rsync -av --delete ./ user@SERVER:/var/www/averix/

# 2. конфиг Nginx: /etc/nginx/sites-available/averix
```

```nginx
server {
  listen 80;
  server_name averix.tj www.averix.tj;
  root /var/www/averix;
  index index.html;

  gzip on;
  gzip_types text/css application/javascript image/svg+xml;

  location ~* \.(css|js|svg|webp|avif|woff2)$ {
    expires 30d;
    add_header Cache-Control "public";
  }
  location / {
    try_files $uri $uri/ =404;
  }
}
```

```bash
# 3. включить и получить сертификат
ln -s /etc/nginx/sites-available/averix /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d averix.tj -d www.averix.tj
```

Страница весит меньше 100 КБ, поэтому 10 000 посетителей — обычная нагрузка
даже для самого дешёвого VPS. Если пойдёт трафик из других стран, поставьте
перед сервером Cloudflare: бесплатно и снимет почти весь исходящий трафик.

## Перед публикацией

- [ ] Заменить `averix.tj` в `canonical` и `og:url` на реальный домен
- [ ] Положить `og.png` (1200×630) в корень — превью в Telegram и соцсетях
- [ ] Проверить, что заявка из формы доходит в Telegram
- [ ] Проверить на телефоне, а не только в узком окне браузера
