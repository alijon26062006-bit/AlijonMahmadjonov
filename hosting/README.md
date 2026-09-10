# AlijonHost — shared-хостинг для PHP на одном VPS

Панель хостинга: регистрация (по e-mail и через Telegram Mini App), сайты с
поддоменами, файловый менеджер, базы MariaDB, phpMyAdmin, резервные копии,
собственные домены с SSL, мониторинг и firewall — всё для того, чтобы клиент
прошёл путь «зарегистрировался → создал сайт → залил файлы → открыл через
HTTPS → подключил базу» без вашего ручного вмешательства.

Это отдельный продукт внутри этого репозитория, независимый от
Telegram-бота учёта денег в корне репо (`bot/`) — у него свой `.env`
(`hosting/.env.example`, не путать с корневым `.env.example`).

## Архитектура в двух словах

```
Клиент → nginx → php-fpm (свой пул на клиента, свой unix-пользователь)
                              │
Панель (веб, www hosting-panel) ──> таблица jobs (MariaDB)
                                          │
                          root-воркер (systemd, только он трогает
                          useradd/nginx -t/systemctl reload/CREATE DATABASE)
```

Панель **никогда** не выполняет привилегированные операции сама — она
только кладёт задание в очередь. Подробности — `worker/src/JobHandler.php`
и `SECURITY_CHECKLIST.md`.

## Требования к серверу

- Ubuntu (22.04 и новее, включая 26.04) или Debian 12 — версия PHP определяется автоматически
  из репозиториев конкретной системы
- 4 vCPU / 8 GB RAM / NVMe — ориентир на ~200 hosting-аккаунтов, 200–400 сайтов
  (не 200 одновременно тяжёлых PHP-воркеров, см. SECURITY_CHECKLIST → CAPACITY)
- Root-доступ по SSH
- Свой домен (текущий — `diyorhost.com`, задаётся одной переменной в `.env`)

## Установка

Одна команда:

```bash
sudo bash hosting/go.sh
```

Она сама подтягивает нужную ветку репозитория, ставит и настраивает всё ПО,
спрашивает домен, токен бота и пароль администратора — и в конце проверяет
весь хостинг целиком. Запускать повторно безопасно.

Внутри это три шага, их можно вызывать и по отдельности:

```bash
sudo bash hosting/install.sh          # ПО и конфигурация сервера, без вопросов
sudo bash hosting/setup.sh            # домен, бот, администратор, SSL
sudo bash hosting/scripts/doctor.sh   # проверить всё и узнать, что именно чинить
```

`install.sh` идемпотентен — повторный запуск безопасен и ничего не затирает.
Что он делает по шагам: проверка root/ОС → `.env` (генерирует пароли сам) →
пакеты (nginx, php-fpm, mariadb-server, certbot, fail2ban, nftables) →
системные пользователи → каталоги → MariaDB (конфиг + БД панели) →
миграции → nginx + php-fpm для панели → systemd (воркер + таймеры) →
firewall → Fail2ban → `hostingctl` + sudoers → SFTP → тесты → итоговый статус.

`setup.sh` сам выпускает сертификат для панели по HTTP-01 — без единой ручной
записи в DNS: домен уже указывает на сервер, порт 80 открыт, certbot кладёт
файл проверки в `/var/www/html`. Сразу после этого панель переезжает на HTTPS
(vhost пересобирается скриптом `scripts/apply-panel-vhost.sh`), а `APP_URL`
меняется на `https://`. Это обязательное условие для Telegram: и Mini App, и
кнопку входа на сайте он принимает только по HTTPS. Wildcard `*.домен` нужен
лишь поддоменам клиентов и предлагается отдельным необязательным шагом — он
требует TXT-записи и не блокирует запуск.

`setup.sh` доделывает всё, что раньше приходилось руками: спрашивает домен и
проверяет, что A-запись и wildcard уже указывают на этот сервер; проверяет
токен бота через Telegram API и сам записывает имя бота; создаёт
администратора (пароль читается со STDIN, а не из аргументов — иначе он
остался бы в `ps` и в истории shell); при желании выпускает wildcard-сертификат;
в конце проверяет, что панель реально отвечает. Запускать его повторно
безопасно — все ответы подставляются из текущего `.env`.

## Окружение (`.env`)

`hosting/.env.example` → копируется в **`hosting/.env`** при установке.

Файл именно свой, а не общий с корнем репозитория: в корне лежит `.env`
Telegram-бота учёта денег (`bot/`), и обе программы читают из него переменную
с одним именем — `TELEGRAM_BOT_TOKEN`. Пока файл был общий, хостинг работал с
токеном чужого бота, а два процесса одновременно опрашивали `getUpdates` одного
бота и перехватывали сообщения друг у друга: на `/start` ответ приходил через
раз. `install.sh` переносит значения настроек хостинга в свой файл сам, чужой
не трогает и токен намеренно не наследует.

### Telegram: одна команда

```bash
sudo bash hosting/scripts/telegram.sh <токен от @BotFather>
```

Скрипт сам спрашивает у Telegram, чей это токен (`getMe`), записывает имя бота,
настраивает кнопку Mini App, команды и описание, перезапускает службу бота и
проверяет, что бота действительно кто-то опрашивает. Имя бота никогда не
вводится руками: после смены токена старое имя оставалось в настройках, кнопка
входа вела к прошлому боту, и заметить это было нельзя — токен-то валидный.

У хостинга должен быть **отдельный** бот: Telegram отдаёт сообщения бота только
одному читателю.

Единственная переменная, которую обязательно менять — домен:

```bash
# hosting/.env.example (после install.sh — файл .env в корне репозитория)
HOSTING_ROOT_DOMAIN=diyorhost.com   # базовый домен, от него идут поддомены клиентов
HOSTING_SERVER_IP=2.29.11.118       # IP этого сервера — по нему проверяются чужие домены
```

Секреты root-воркера (`MYSQL_ADMIN_PASSWORD` и т.п.) — отдельно, в
`/etc/hosting/worker.env` (0600, только root). Панель этот файл не читает.

Домен указан **в одном месте**. Сменить его — поменять `HOSTING_ROOT_DOMAIN`
в `.env` и перезапустить `install.sh`, больше нигде править не нужно.

## Миграции базы данных

```bash
php hosting/panel/bin/migrate.php            # применить все новые миграции
php hosting/panel/bin/migrate.php --status   # что уже применено
```

Миграции — обычные `.sql`-файлы в `hosting/migrations/*.sql`, применяются по
имени файла, повторное применение безопасно (таблица `schema_migrations`).

## Запуск / перезапуск сервисов

```bash
# вместо 8.3 подставьте свою версию: она печатается установщиком и лежит в .env (PHP_VERSIONS)
systemctl status  nginx php8.3-fpm mariadb hosting-worker fail2ban nftables
systemctl restart nginx php8.3-fpm hosting-worker
systemctl status  hosting-monitor.timer hosting-backup.timer hosting-ssl-renew.timer
```

## Проверка конфигурации перед применением

```bash
nginx -t
php-fpm8.3 -t
nft -c -f /etc/nftables-hosting.conf
visudo -cf /etc/sudoers.d/hosting-admin
```

Панель и воркер сами прогоняют `nginx -t`/`php-fpm -t` перед каждым
применением конфига (см. `worker/src/Provisioning/NginxManager.php`) — если
не проходит, старый конфиг остаётся, а не ломается.

## Логи

```bash
journalctl -u hosting-worker -f          # что делает root-воркер
journalctl -u hosting-monitor.service    # последний прогон мониторинга
tail -f /var/log/hosting/panel-error.log         # ошибки самой панели
tail -f /var/log/hosting/<домен>/error.log       # ошибки PHP конкретного сайта
tail -f /var/log/hosting/<домен>/access.log      # nginx access конкретного сайта
```

Клиент смотрит логи своих сайтов прямо в панели (`/sites/{id}/logs`) — это
тот же файл, без прямого доступа к `/var/log`.

## Очередь заданий воркера

```bash
hostingctl status                                  # сводка: очередь, диск, упавшие юниты
mysql hosting_panel -e "SELECT id,type,status,error_text FROM jobs ORDER BY id DESC LIMIT 20"
```

## hostingctl — ручное управление из консоли

```bash
hostingctl create-site <site_id>        hostingctl delete-site <site_id>
hostingctl suspend-site <site_id>       hostingctl unsuspend-site <site_id>
hostingctl create-database <db_id>      hostingctl delete-database <db_id>
hostingctl apply-nginx <user_id>        hostingctl apply-php-fpm <user_id>
hostingctl suspend-user <user_id>       hostingctl unsuspend-user <user_id>
hostingctl status
```

Не-root администратор (в группе `hosting-admins`) вызывает это через
`sudo hostingctl ...` — см. `etc/sudoers/hosting-admin`.

## Резервные копии

```bash
# Ручной бэкап одного клиента
bash hosting/scripts/backup.sh --user client1001

# Бэкап всех клиентов (то же самое, что и ночной таймер)
sudo systemctl start hosting-backup.service

# Восстановление
bash hosting/scripts/restore.sh --user client1001 --backup-id 42

# Еженедельная проверка, что бэкапы реально восстанавливаются
bash hosting/scripts/verify-backup.sh
```

Ротация: 7 daily / 4 weekly / 3 monthly (`scripts/backup.sh`). Чтобы бэкапы
уходили не только на этот же VPS — задайте `BACKUP_PROVIDER` (имя
[rclone](https://rclone.org/) remote) и `BACKUP_BUCKET` в `.env`.

## Первый админ

```bash
# 1. Зарегистрируйтесь как обычный клиент через панель (https://panel.<домен>/register)
# 2. Сделайте себя админом:
mysql -uroot -p -e "UPDATE hosting_panel.users SET role='admin' WHERE email='вы@example.com'"
```

## Cloudflare

Два независимых применения, не путать:

1. **Allowlist firewall** (`HOSTING_BEHIND_CLOUDFLARE=true` в `.env`) — держит
   в nftables актуальные IP-диапазоны Cloudflare, чтобы 80/443 принимали
   соединения только через них. Токен не нужен, диапазоны публичные:
   ```bash
   bash hosting/scripts/update-cloudflare-firewall.sh          # разово
   bash hosting/scripts/update-cloudflare-firewall.sh --dry-run  # проверка без применения
   ```
2. **DNS-01 для wildcard-сертификата** (см. ниже) — сейчас выполняется
   вручную, автоматизация через API Cloudflare помечена NOT IMPLEMENTED в
   `SECURITY_CHECKLIST.md` (переменные `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ZONE_ID`
   зарезервированы под неё на будущее).

## Wildcard DNS

У вашего DNS-провайдера (Cloudflare или другой):

```
A     diyorhost.com        <IP сервера>
A     *.diyorhost.com       <IP сервера>
```

Новые поддомены клиентов (`shop.diyorhost.com`) не требуют отдельной DNS-записи —
это и есть смысл wildcard-записи.

## SSL

**Wildcard для системных поддоменов** — выпускается один раз вручную (DNS-01,
автоматизировать HTTP-01 для wildcard нельзя в принципе):

```bash
certbot certonly --manual --preferred-challenges dns \
  -d diyorhost.com -d '*.diyorhost.com' \
  --email вы@example.com --agree-tos
# certbot попросит добавить TXT-запись _acme-challenge.diyorhost.com — добавьте
# её у DNS-провайдера, дождитесь распространения, подтвердите в certbot.
```

После этого все НОВЫЕ поддомены автоматически получают HTTPS при создании
сайта (worker проверяет наличие `/etc/letsencrypt/live/<домен>/fullchain.pem`
и сразу генерирует HTTPS-vhost, см. `JobHandler::applySiteNginxConf`).
Продление — автоматически по таймеру `hosting-ssl-renew.timer`
(`certbot renew`, но у wildcard DNS-01 автопродление требует hook для вашего
DNS-провайдера — для Cloudflare добавьте `certbot-dns-cloudflare` отдельно).

**Свои домены клиентов** — полностью автоматически через панель
(HTTP-01 + webroot), см. `/sites/{id}/domains` → «Проверить DNS» → «Выпустить SSL».

## SFTP

Включено из коробки: у каждого клиента `chroot` в свой домашний каталог,
только `internal-sftp`, без shell/forwarding/tunnel (`etc/ssh/sshd-hosting.conf`).

```
Хост:       <IP сервера>
Порт:       22 (или ваш HOSTING_SSH_PORT)
Логин:      client1001 (unix-имя, видно в панели)
Пароль:     не задан — только по ключу (добавьте вручную:
            ssh-copy-id -p 22 client1001@<IP>, либо положите публичный ключ
            в /home/hosting/client1001/.ssh/authorized_keys от имени root)
```

Полноценный логин по паролю сознательно не включён — только по ключу
(добавление UI для управления SSH-ключами клиентов из панели — TODO следующей версии).

## Тесты

```bash
php hosting/tests/run.php                                     # быстро, на SQLite-зеркале схемы

# На настоящей MariaDB — так ловятся различия диалектов (зарезервированные слова,
# повторные :параметры в prepared statements, ANSI_QUOTES). Пользователю нужны
# права на CREATE/DROP DATABASE; тестовая база пересоздаётся при каждом прогоне.
HOSTING_TEST_MYSQL_DB=hosting_panel_test \
HOSTING_TEST_MYSQL_USER=hosting_test HOSTING_TEST_MYSQL_PASSWORD=... \
  php hosting/tests/run.php
```

Без внешних зависимостей (без PHPUnit) — свой минимальный runner. 59 тестов:
path traversal, Zip Slip, IDOR по сайтам и базам, откат невалидного
nginx-конфига (с настоящим `nginx -t` через поддельный бинарник в PATH),
Telegram initData и Login Widget (настоящий HMAC-SHA256, два разных
алгоритма), CSRF, SQL-инъекции, SSRF-защита при добавлении домена,
зарезервированные поддомены, квота, провал задания в очереди и живучесть
воркера (реально запускает его с недоступной базой и проверяет, что он не
падает, а объясняет причину).

## Диагностика

Сначала — одна команда, которая проверяет всё сразу:

```bash
sudo bash hosting/scripts/doctor.sh
```

Она проходит по службам, конфигам, базе, очереди заданий (кладёт настоящее
тестовое задание `ping` и смотрит, заберёт ли его воркер), DNS, ответам панели,
сертификатам и месту на диске. Для каждой проблемы печатает причину (кусок
`journalctl`, вывод `nginx -t`) и команду, которой это чинится. Код возврата
ненулевой, если есть хотя бы одна `[ПРОБЛЕМА]`, — можно вешать в cron.

Если нужно копать руками:

| Симптом | Что проверить |
|---|---|
| Сайт клиента не открывается | `journalctl -u hosting-worker` — job `create_site` мог провалиться на `nginx -t` |
| Панель отдаёт 500 | `tail /var/log/hosting/panel-php-error.log`, `journalctl -u php8.3-fpm` |
| Воркер не забирает задания | `systemctl status hosting-worker`, проверьте `DB_*` в `.env` |
| `hosting-worker` в состоянии `activating` | Он перезапускается по кругу: `journalctl -u hosting-worker -n 50` покажет причину. Если он не может подключиться к базе, он больше не падает, а ждёт и пишет об этом в журнал каждые несколько секунд |
| SSL не выпускается | `journalctl -u hosting-worker` (job `issue_ssl`) — обычно домен ещё не указывает на сервер |
| Клиент не может зайти по SFTP | проверьте, что он в группе `hosting-sftp` (`id client1001`), `sshd -T \| grep -i chroot` |
| Бэкап не создаётся | `journalctl -u hosting-backup.service`, `bash hosting/scripts/backup.sh --user <имя>` руками для деталей |
| Много неудачных входов с одного IP | `fail2ban-client status hosting-panel-login` |

## Структура каталогов

```
hosting/
├── panel/            веб-панель (public/index.php — точка входа, src/, views/)
├── worker/            root-воркер и провижининг (JobHandler + Provisioning/*)
├── migrations/        SQL-миграции MariaDB (канонiчная схема)
├── templates/          nginx/php-fpm/systemd конфиги-шаблоны + skel/ для новых сайтов
├── scripts/            bash: backup/restore/monitor/hostingctl/firewall
├── etc/                образцы системных конфигов (nftables/fail2ban/mariadb/ssh/sudoers)
├── systemd/            (зарезервировано; юниты сейчас рендерятся из templates/systemd-*.tpl)
├── tests/              тесты без внешних зависимостей + SQLite-зеркало схемы
└── install.sh          установщик
```
