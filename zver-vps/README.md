# ZVER TAJ — Telegram-бот пополнения игр + Mini App

`zbot.php` 13.1 · `zapp.php` 6.5

Установка на чистый VPS одной командой: ставит nginx, PHP-FPM, MariaDB,
выпускает SSL-сертификат, поднимает домен на DuckDNS, создаёт таблицы,
подключает webhook Telegram и настраивает cron.

---

## Что нужно

- VPS с **Ubuntu 22.04 / 24.04** или **Debian 11 / 12**, root-доступ
- Токен бота от [@BotFather](https://t.me/BotFather)
- Ваш Telegram ID (узнать у [@userinfobot](https://t.me/userinfobot))
- Домен. Своего нет — установщик сделает бесплатный на [DuckDNS](https://www.duckdns.org)

---

## Установка одной командой

Выполните на сервере под root:

```bash
curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/claude/zver-taj-server-deploy-gom4he/zver-vps/install.sh -o i.sh && sudo bash i.sh
```

Если репозиторий закрыт — добавьте токен с правом `repo`:

```bash
T=ВАШ_ТОКЕН; curl -fsSL -H "Authorization: Bearer $T" \
  https://raw.githubusercontent.com/ВЛАДЕЛЕЦ/РЕПО/ВЕТКА/zver-vps/install.sh \
  -o i.sh && sudo GH_TOKEN=$T RAW=https://raw.githubusercontent.com/ВЛАДЕЛЕЦ/РЕПО/ВЕТКА/zver-vps bash i.sh
```

Дальше скрипт спросит:

| Вопрос | Что вводить |
|---|---|
| Домен | свой домен, либо **Enter** → перейдёт к DuckDNS |
| Имя поддомена DuckDNS | например `zvertaj` → получится `zvertaj.duckdns.org` |
| Токен DuckDNS | со страницы duckdns.org после входа |
| Токен бота | из @BotFather |
| Telegram ID | ваш ID, через запятую если админов несколько |
| Ключи FazerCards / gameskinbo | можно пропустить, добавить позже |

Пароль базы и `secret` генерируются автоматически.

### Если config.php уже есть

Загрузите его на сервер **до** запуска — установщик подхватит секреты
оттуда и ничего спрашивать не станет:

```bash
scp config.php root@IP_СЕРВЕРА:/root/
```

Ищет он в таком порядке: `/var/www/zver/config.php` → рядом со скриптом → `/root/`.

### Без вопросов вообще

```bash
sudo GH_TOKEN=... DUCKDNS_NAME=zvertaj DUCKDNS_TOKEN=... \
     BOT_TOKEN=123456:AAE... ADMINS=123456789 \
     FZ_KEY=fc_... FZ_HOOK=whsec_... \
     bash i.sh
```

---

## После установки — один шаг вручную

@BotFather → `/mybots` → ваш бот → **Bot Settings** → **Menu Button** → вставить:

```
https://ВАШ-ДОМЕН/zapp.php
```

Всё остальное — таблицы, webhook Telegram, webhook FazerCards, cron,
автопродление сертификата — установщик делает сам.

---

## Проверка

| Что | Ссылка |
|---|---|
| Состояние бота | `https://ДОМЕН/zbot.php?diag=1&secret=СЕКРЕТ` |
| Mini App | `https://ДОМЕН/zapp.php` |
| Webhook FazerCards | `?hookset=1&secret=СЕКРЕТ` |
| Проверка ника | `?nickdiag=1&secret=СЕКРЕТ&game=Free Fire&id=123456789` |
| Лимит ключа ников | `?gskey=show&secret=СЕКРЕТ` |
| Запустить cron вручную | `?cron=1&secret=СЕКРЕТ` |

Секрет лежит в `/var/www/zver/config.php`:

```bash
sudo grep secret /var/www/zver/config.php
```

---

## Повторный запуск

Скрипт идемпотентный — можно запускать сколько угодно раз.
Существующий `config.php` он не перетирает, а переиспользует
(включая пароль базы), так что данные не теряются.

Обновить только код бота:

```bash
sudo GH_TOKEN=... bash i.sh
```

---

## Перенос со старого хостинга

На старом сервере:

```bash
mysqldump -u СТАРЫЙ_ЮЗЕР -p СТАРАЯ_БАЗА > dump.sql
```

На новом — **до** запуска установщика или сразу после:

```bash
mysql -u zver -p zver < dump.sql
sudo bash i.sh          # обновит структуру и переставит webhook
```

> **Важно:** у одного бот-токена может быть только один webhook.
> Как только новый сервер его заберёт, старая копия бота перестанет
> получать сообщения. Хотите протестировать без простоя — заведите
> отдельного тестового бота и укажите его токен.

---

## Настройки после установки

| Команда | Что делает |
|---|---|
| `?gskey=КЛЮЧ&secret=...` | сменить ключ для ников |
| `?gskey=0&secret=...` | выключить ники через gameskinbo |
| `?ffclear=1&secret=...` | очистить кэш ников |
| `?nickset=0&secret=...` | выключить FlashTopup |
| `?hookset=1&off=1&secret=...` | отключить webhook FazerCards |

---

## Ручная установка

Если хочется всё руками — установщик читаемый, шаги в нём
пронумерованы по порядку: пакеты → база → файлы → nginx → PHP →
фаервол → DNS → SSL → cron → инициализация.

---

## Безопасность

- `config.php` **не хранится в git** (см. `.gitignore`) и отдаётся наружу с 404
- права на него `640`, владелец `www-data`
- пароль базы и `secret` генерируются случайно при установке
- если токен бота где-то засветился — отзовите его: @BotFather → `/revoke`
- GitHub-токен из команды установки после развёртывания лучше удалить
