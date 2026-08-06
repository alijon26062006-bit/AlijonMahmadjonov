# EasySIM — интернет-магазин eSIM (Django, для VPS)

Python-версия магазина (Django) — та же функциональность, что и в PHP-версии
(`esim-store/`), но требует VPS с root-доступом: обычный shared-хостинг вроде
Somonhost Python-приложения не запускает (нет WSGI).

## Возможности

- Каталог направлений и тарифов eSIM (мок-данные «из коробки»; при наличии
  ключей Airalo — реальный каталог и реальная выдача eSIM).
- Корзина на сессиях Django.
- Оформление заказа: email + телефон → SMS-код подтверждения через Zadarma →
  инструкции по оплате переводом → загрузка скриншота/PDF чека.
- Страница статуса заказа для клиента (QR-код / ICCID после выдачи).
- Админ-панель — используется встроенная **Django admin** (`/admin/`):
  список заказов, превью чека, массовые действия «Подтвердить и выдать eSIM»
  / «Отклонить оплату».
- Виджет поддержки Zadarma WebRTC (опционально).

**Демо-режим:** пока ключи Zadarma/Airalo не заданы, сайт полностью работает —
код из SMS показывается прямо на странице, а вместо реального eSIM выдаётся
тестовый (явно помечено и клиенту, и админу).

## Быстрый локальный запуск

```bash
cd esim-store-django
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Откройте http://127.0.0.1:8000 — база данных (SQLite) уже готова после
`migrate`, ключи Zadarma/Airalo не нужны. Админка — http://127.0.0.1:8000/admin/.

## Деплой на VPS одной командой

На чистом Ubuntu VPS, под root:

```bash
curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/claude/esim-purchase-website-dcpuy3/esim-store-django/deploy/deploy.sh -o deploy.sh
sudo bash deploy.sh your-domain.tj
```

Скрипт `deploy/deploy.sh` сам: поставит системные пакеты, склонирует проект в
`/var/www/esim-store-django`, создаст venv, сгенерирует `.env` со случайным
`SECRET_KEY` (ключи Zadarma/Airalo туда всё равно нужно вписать вручную —
скрипт их не знает), применит миграции, предложит создать администратора и
настроит gunicorn (systemd) + nginx. Безопасно перезапускать повторно —
уже сделанные шаги пропускаются. После первого запуска:

```bash
nano /var/www/esim-store-django/.env      # впишите реальные ключи
sudo systemctl restart esim-store
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.tj    # HTTPS
```

### Деплой вручную (если нужен полный контроль)

1. Установите системные пакеты:
   ```bash
   sudo apt update
   sudo apt install python3-venv python3-pip nginx
   # для PostgreSQL: sudo apt install postgresql libpq-dev
   ```
2. Скопируйте проект на сервер, например в `/var/www/esim-store-django`.
3. Создайте виртуальное окружение и поставьте зависимости:
   ```bash
   cd /var/www/esim-store-django
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   # если DB_ENGINE=postgresql: pip install psycopg2-binary
   ```
4. Скопируйте `.env.example` в `.env` и заполните реальными значениями:
   - `DJANGO_SECRET_KEY` — длинная случайная строка;
   - `DJANGO_DEBUG=false`;
   - `DJANGO_ALLOWED_HOSTS` — ваш домен;
   - `DB_ENGINE=postgresql` (рекомендуется для продакшена) + данные подключения
     (создайте базу и пользователя в PostgreSQL заранее);
   - `ZADARMA_API_KEY` / `ZADARMA_API_SECRET` — со страницы **my.zadarma.com →
     Интеграции → Ключи и API**;
   - `ZADARMA_WIDGET_KEY` — со страницы **Интеграции → WebRTC**, если нужен
     виджет поддержки;
   - `AIRALO_CLIENT_ID` / `AIRALO_CLIENT_SECRET` — из личного кабинета Airalo
     Partner API;
   - `PAYMENT_INSTRUCTIONS` — реальные реквизиты для перевода оплаты.

   `.env` никогда не попадает в git (см. `.gitignore`), поэтому секреты
   остаются только на сервере.
5. Примените миграции, соберите статику, создайте администратора:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
   ```
6. Настройте gunicorn как systemd-сервис — пример в `deploy/gunicorn.service`
   (поправьте пути и пользователя под вашу систему):
   ```bash
   sudo cp deploy/gunicorn.service /etc/systemd/system/esim-store.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now esim-store
   ```
7. Настройте nginx как обратный прокси — пример в `deploy/nginx.conf.example`:
   ```bash
   sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/esim-store
   sudo ln -s /etc/nginx/sites-available/esim-store /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```
8. (Рекомендуется) выпустите HTTPS-сертификат через certbot:
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.tj
   ```

После деплоя при каждом обновлении кода:
```bash
git pull
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart esim-store
```

## Безопасность

- `.env` с реальными секретами никогда не коммитится (см. `.gitignore`).
- Загруженные чеки (`media/receipts/`) доступны напрямую по URL (как обычные
  медиа-файлы Django) — если это нежелательно, замените ссылку в шаблоне
  админки на защищённое представление с проверкой `request.user.is_staff`.
- Все формы защищены встроенным CSRF-механизмом Django.
- Вход в админку — через стандартную аутентификацию Django
  (`createsuperuser`), с полным набором стандартных защит (хэширование
  паролей, throttling через `django-axes` можно добавить дополнительно).

## Структура проекта

```
esim-store-django/
├── manage.py
├── requirements.txt
├── .env.example                # шаблон — скопировать в .env
├── esim_store/                 # настройки Django (settings.py читает .env)
├── store/                      # приложение: models, views, catalog, zadarma, airalo, admin
│   ├── templates/store/
│   └── migrations/
├── templates/base.html
├── static/css/style.css
└── deploy/
    ├── deploy.sh                # автодеплой на VPS одной командой
    ├── gunicorn.service         # шаблон systemd-сервиса
    └── nginx.conf.example       # шаблон конфига nginx
```

## Известные упрощения (что доделать при желании)

- Оплата — только вручную (чек + подтверждение админом), без онлайн-эквайринга.
- Поля каталога Airalo (`store/airalo.py`) написаны по документации API и не
  проверены на реальном аккаунте — при отличии полей в ответе API поправьте
  `fetch_plans()` / `create_order()`.
- Один загруженный чек может покрывать сразу несколько тарифов в корзине
  (создаётся заказ на каждый тариф, у каждого — свой файл чека).
