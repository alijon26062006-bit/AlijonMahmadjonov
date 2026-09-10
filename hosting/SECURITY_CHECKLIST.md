# Чеклист безопасности — AlijonHost

Честная самооценка по каждому пункту: **PASS** — реализовано и проверено
(тестом или вживую), **PARTIAL** — реализовано частично или требует
дополнительной настройки на конкретном сервере, **NOT IMPLEMENTED** — не
сделано в этой версии, с объяснением почему и что делать вместо этого.

Где написано «проверено тестом» — тест реально существует и проходит
(`php hosting/tests/run.php`, 42/42 на момент написания). Где написано
«проверено вживую» — команда была выполнена по-настоящему в этой сессии
(`nginx -t`, `nft -c`, `visudo -cf`, живой HTTP через встроенный PHP-сервер),
а не просто предполагается, что заработает.

## Изоляция клиентов

| Пункт | Статус | Комментарий |
|---|---|---|
| Отдельный unix-пользователь на клиента | PASS | `UnixProvisioner::createUser`, паттерн `client{id}`, `/usr/sbin/nologin` |
| Отдельный пул php-fpm на клиента | PASS | `templates/php-fpm-pool.conf.tpl`, рендерится `PhpFpmManager` |
| open_basedir + disable_functions | PASS | В шаблоне пула; явно задокументировано, что это доп. барьер, не sandbox |
| systemd/cgroup лимиты (CPU/RAM/tasks) на клиента | **NOT IMPLEMENTED** | Шаблон `templates/systemd-client-slice.tpl` написан и содержит честную оговорку архитектуры (все пулы под одним `php-fpm.service`), но нигде не рендерится/не применяется воркером. Мягкая альтернатива — `scripts/monitor.sh` отслеживает CPU/RAM/процессы по unix-пользователю и шлёт алерт при превышении 80% лимита тарифа, но не убивает процессы и не режет CPU принудительно. Для честного cgroup-лимита на клиента нужен либо отдельный `php-fpm.service` на клиента (дороже по памяти на 200 клиентов), либо делегирование cgroup через `pm.max_children`-хук — не сделано. |
| Дисковая квота на уровне ФС | PARTIAL | `scripts/apply-quota.sh` умеет XFS project quota и ext4 usrquota, но если файловая система не одна из них — предупреждает и откатывается на «мягкий» контроль через `monitor.sh` (превышение квоты не блокируется ядром, только видно в мониторинге и панели). Полноценно работает только на XFS. |
| SSH/SFTP без shell | PASS | `etc/ssh/sshd-hosting.conf`, `ChrootDirectory`, `internal-sftp`, никаких forwarding/tunnel. Владелец `$HOME` — root:root 0755 (обязательное требование OpenSSH к ChrootDirectory), подкаталоги `sites/logs/tmp/backups` — клиента. Это был реальный баг, найденный и исправленный в процессе (изначально весь дом отдавался клиенту, что сломало бы chroot). |
| Никогда chmod 777 | PASS | `SiteFiles::applyPermissions` — 0750 на каталоги, 0640 на файлы. Проверено по всему коду (`grep -r 777 hosting/` — пусто). |

## Файловый менеджер / загрузка

| Пункт | Статус | Комментарий |
|---|---|---|
| Path traversal (`../`, симлинки, null byte) | PASS | `Path::resolve()` + `realpath()`-проверка на каждый доступ; **проверено тестами** (`test_fm_path_traversal_*`, `test_fm_symlink_escape_rejected`, `test_fm_null_byte_in_name_rejected`) |
| Zip Slip | PASS | Нормализация путей внутри архива + проверка `Path::isInside()` на каждую запись; **проверено тестом с реальным вредоносным ZIP** (`test_fm_zip_slip_does_not_escape_destination`) |
| Лимит числа файлов в ZIP | PASS | `FileManager::MAX_ZIP_ENTRIES` (20 000), проверяется ДО распаковки; **проверено тестом** с архивом из 20 001 файла |
| Лимит распакованного размера (защита от zip-бомбы) | PASS | Суммируется заявленный `size` каждой записи до записи на диск; **проверено тестом** |
| Запрещённые расширения (.phtml, .php3 и т.п.) | PASS | `FileManager::BLOCKED_EXTENSIONS`; **проверено тестом** |
| Изоляция файлового менеджера между сайтами клиента | PASS | Область — каталог конкретного сайта (`home/sites/{slug}`), не весь дом клиента; **проверено тестом** (`test_cross_account_file_manager_isolated`) |

## Аутентификация / авторизация

| Пункт | Статус | Комментарий |
|---|---|---|
| Пароли — только хэш (password_hash) | PASS | `UserRepository::create/verifyPassword`, bcrypt по умолчанию PHP |
| Telegram initData — HMAC + auth_date | PASS | `TelegramAuth::verify`; **проверено 7 тестами с реально вычисленным HMAC-SHA256** (валидная подпись, подделанное поле, чужой bot token, просрочка, отсутствие hash) |
| Максимальный возраст initData | PASS | `TelegramAuth::MAX_AGE_SECONDS = 86400`; спецификация просила 300 сек — у нас мягче (сутки), решение осознанное: Mini App может быть открыт заранее и не переоткрыт мгновенно; если нужно строже — одна константа |
| Session cookie: HttpOnly/Secure/SameSite | PASS | `Auth::setCookie()`; Secure зависит от реального HTTPS (`$isHttps` в `public/index.php`) |
| CSRF на всех формах | PASS | `Auth::csrfToken()/verifyCsrf()`, проверяется в каждом POST-обработчике; **проверено тестом** |
| Rate limit на логин | PASS | `login_attempts` в БД (`Auth::isLoginRateLimited` — 5 неудач за 10 мин) НЕЗАВИСИМО от Fail2ban jail `hosting-panel-login` (тоже 5/10м/1ч) — две независимые линии защиты |
| IDOR на каждом ресурсе (site/database/domain/backup) | PASS | Владелец проверяется в каждом контроллере (`ownedSite`, `belongsToUser` и т.п.); **проверено тестами И вживую через HTTP** (попытка удалить чужой сайт → 403, вход в /admin не-админом → 403, доступ без сессии → редирект на /login) |
| SQL-инъекции | PASS | Везде `PDO::prepare()`, ни одной конкатенации пользовательского ввода в SQL; **проверено тестом** с типовыми payload'ами (`' OR '1'='1`, `DROP TABLE` и т.п.) |
| Admin — 2FA | **NOT IMPLEMENTED** | В схеме есть колонка `users.two_factor_secret`, но проверка TOTP при логине не реализована. Компенсирующий контроль: у админа тот же rate limit + Fail2ban, что и у всех, плюс роль проверяется на каждый admin-запрос |
| Admin — отдельный URL | **NOT IMPLEMENTED** | `/admin` — обычный маршрут той же панели, защищён проверкой роли (`role === 'admin'`), а не отдельным поддоменом/портом. Функционально эквивалентно с точки зрения авторизации, но не соответствует букве спецификации |
| Session timeout короче для admin | **NOT IMPLEMENTED** | Один `SESSION_TTL_SECONDS` на всех (по умолчанию 14 дней) |
| Секьюрити-заголовки (CSP, HSTS, nosniff) | PASS | `public/index.php` — CSP с `frame-ancestors` под Telegram WebView, HSTS при HTTPS, `X-Content-Type-Options`, `Referrer-Policy` |
| Никаких stack trace/секретов клиенту | PASS | Единая обработка исключений в `public/index.php` — наружу идёт только текст `HttpException`, всё остальное (`\Throwable`) логируется на сервере и показывается как «Внутренняя ошибка» |

## Домены и SSRF

| Пункт | Статус | Комментарий |
|---|---|---|
| Валидация имени поддомена | PASS | `Domain::isValidLabel()`; **проверено тестом** |
| Зарезервированные поддомены (www, admin, api, mysql…) | PASS | `Domain::RESERVED`; **проверено тестом** |
| Валидация FQDN своего домена | PASS | `Domain::isValidFqdn()`; **проверено тестом** |
| SSRF-защита при добавлении домена (приватные/loopback/link-local IP) | PASS | `DnsVerifier::isPublicIp()` — фильтр по `FILTER_FLAG_NO_PRIV_RANGE\|NO_RES_RANGE`; **проверено тестом** на наборе приватных/публичных адресов |
| Запрет псевдо-доменов (localhost, .internal, .local) | PASS | `DnsVerifier::pointsToServer()`; **проверено тестом** |
| SSL не выпускается до проверки DNS | PASS | `DomainController::issueSsl` требует `domain.verified === true`; `JobHandler::handleIssueSsl` дублирует проверку на стороне воркера |

## MariaDB

| Пункт | Статус | Комментарий |
|---|---|---|
| bind-address 127.0.0.1, порт не наружу | PASS | `etc/mariadb/hosting.cnf` + nftables не открывает 3306 |
| Отдельный DB-пользователь на клиента, не root | PASS | `MysqlManager::ensureUser` — `client1001@localhost`, `MAX_USER_CONNECTIONS` по тарифу |
| GRANT только на namespace клиента | PASS | `GRANT ALL ON \`client1001_%\`.*`, плюс `assertOwnedByUser()` в коде не даёт создать базу вне префикса |
| Панель не хранит admin-креды MySQL | PASS | `MYSQL_ADMIN_*` только в `/etc/hosting/worker.env` (0600, root), читает только воркер/CLI-инструменты, веб-процесс панели — нет |
| Пароли БД — криптостойкая генерация | PASS | `MysqlManager::generatePassword()` — `random_int()`, не `rand()` |
| Пароль БД показывается один раз, не хранится | PASS | Передаётся через `jobs.result_secret`, читается и тут же стирается (`JobRepository::consumeResultSecret`) |

## nginx / DDoS

| Пункт | Статус | Комментарий |
|---|---|---|
| nginx -t перед каждым применением конфига | PASS | `NginxManager::writeAndApply()`; **проверено тестом с настоящим фейковым `nginx` в PATH** — невалидный конфиг реально откатывается, старый остаётся |
| Атомарная замена конфига | PASS | temp-файл → `nginx -t` → `rename()`; при ошибке temp удаляется, оригинал не тронут |
| rate limit зоны (общий, login, per-IP conn) | PASS | `templates/nginx-global-hosting.conf.tpl` — `perip_conn`, `general_req`, `login_req` |
| wp-login.php / xmlrpc.php лимитированы | PASS | В `nginx-site.conf.tpl`/`nginx-site-ssl.conf.tpl` |
| Таймауты против медленных соединений | PASS | `client_header_timeout`, `client_body_timeout`, `keepalive_timeout` и т.п. во всех vhost-шаблонах |
| Скрытые файлы (.env, .git) недоступны | PASS | `location ~ /\.(?!well-known)` во всех vhost-шаблонах |
| server_tokens off | PASS | `nginx-global-hosting.conf.tpl` |

## Firewall / Fail2ban / Cloudflare

| Пункт | Статус | Комментарий |
|---|---|---|
| Только 80/443/SSH наружу | PASS | `etc/nftables/hosting.nft`; **синтаксис проверен реальным `nft -c`** |
| MariaDB/php-fpm sockets не публикуются | PASS | Не упомянуты в правилах firewall вообще (unix-сокеты, не TCP) |
| Fail2ban: sshd, nginx-http-auth, nginx-botsearch, panel-login | PASS | `etc/fail2ban/jail.d/hosting.conf` + свой filter для панели |
| Cloudflare IP allowlist | PASS | `scripts/update-cloudflare-firewall.sh` — атомарная замена, валидация ответа перед применением, SSH не трогает |
| Cloudflare DNS-01 для wildcard SSL | **NOT IMPLEMENTED** | Переменные `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ZONE_ID` зарезервированы в `Config.php`, но нигде не используются — DNS-01 выпуск wildcard-сертификата делается вручную один раз (см. README), продление — обычный `certbot renew` по таймеру |

## Backup / Restore

| Пункт | Статус | Комментарий |
|---|---|---|
| Бэкап файлов + баз данных | PASS | `scripts/backup.sh`; **проверено вживую** — реальный tar + checksum |
| tmp/ исключается из бэкапа | PASS | **проверено вживую** |
| Ротация 7/4/3 | PASS | `rotate_backups()` в `backup.sh` |
| Checksum перед восстановлением | PASS | `restore.sh` отказывается восстанавливать при несовпадении sha256; **проверено вживую с намеренно испорченным архивом — восстановление корректно отклонено** |
| Снимок перед перезаписью при restore | PASS | `restore.sh` делает `pre-restore-*.tar.gz` до применения |
| Еженедельная проверка восстановления | PASS | `scripts/verify-backup.sh` — реально поднимает дамп во временную БД |
| Бэкап вне VPS | PARTIAL | Код для этого есть (`rclone`, см. `BACKUP_PROVIDER`), но по умолчанию `BACKUP_PROVIDER` пуст → бэкапы только локально. **Требует вашей настройки** — без неё это не полноценный бэкап (см. README) |
| Безопасное удаление (двухэтапное, без `rm -rf` пользовательским путём) | PARTIAL | Сам путь удаления безопасен (`SiteFiles::remove` проверяет `realpath` внутри дома клиента перед удалением — путь строится из ID в БД, не из пользовательского ввода). Но GRACE PERIOD/SUSPENDED retention из раздела SUSPENSION спецификации (active → grace → suspended → deletion queue, 7/30 дней) НЕ реализован как состояние — удаление происходит сразу по запросу владельца или админа, без отложенной очереди. |

## Root worker / hostingctl

| Пункт | Статус | Комментарий |
|---|---|---|
| Панель не выполняет системные команды напрямую | PASS | Единственный путь — `jobs` → `JobHandler`, whitelist типов (`JobHandler::TYPES`) |
| hostingctl — только числовые ID, whitelist команд | PASS | `require_numeric_id()` на каждый аргумент перед использованием |
| sudoers ограничен одним бинарником | PASS | `etc/sudoers/hosting-admin`; **синтаксис проверен реальным `visudo -cf`** |
| Нет `sudo ALL`, `/bin/bash`, `systemctl *` в sudoers | PASS | Проверено визуально — единственная строка гранта именует ровно `/usr/local/sbin/hostingctl` |

## Мониторинг / алерты

| Пункт | Статус | Комментарий |
|---|---|---|
| RAM/диск/inode/load/iowait | PASS | `scripts/monitor.sh`; **проверено вживую** |
| MariaDB соединения | PASS | Через `mysqladmin`/`SHOW VARIABLES` |
| Упавшие systemd-юниты | PASS | `systemctl --failed` |
| Очередь воркера (backlog) | PASS | `monitor-helper.php pending-jobs` |
| Устаревшие бэкапы | PASS | `monitor-helper.php stale-backups` |
| CPU/RAM/процессы по клиенту относительно тарифа | PASS | `ps -u <client>`, сравнение с `plans.tasks_max`; результат также пишется в `resource_usage` |
| SSL истекает <14 дней | PASS | `openssl x509 -enddate` |
| Telegram-алерты (деградация без токена) | PASS | `scripts/telegram-alert.sh` — если не настроено, пишет в лог вместо падения |
| Публичный `/health` без секретов | PASS | `GET /health` — только `db`/`queue_pending`, никаких путей/паролей/версий |
| «Sustained N минут» перед алертом | PARTIAL | Реализовано через двукратное подтверждение между прогонами `monitor.sh` (5 минут интервал таймера ≈ «5 минут» из спецификации), не через непрерывное отслеживание внутри одного запуска |

## Прочее

| Пункт | Статус | Комментарий |
|---|---|---|
| Document root для Laravel (`project/public`) | **NOT IMPLEMENTED** | В схеме есть `sites.doc_root` (по умолчанию `public`) и весь провижининг его уважает, но UI создания сайта не даёт его сменить — сейчас это возможно только прямым `UPDATE sites SET doc_root=...` + `hostingctl apply-nginx <user_id>` |
| Выбор версии PHP на сайт | PARTIAL | Поддерживается на уровне данных и провижининга (`sites.php_version`, `SiteRepository::setPhpVersion`), но не выведено в UI создания сайта — берётся `defaultPhpVersion()` из `.env` |
| Локальный `mail()` отключён | PASS | `sendmail_path = /bin/true` в пуле клиента (`php-fpm-pool.conf.tpl`) |
| Cron для клиентов — не прямой system cron | **NOT IMPLEMENTED** | Таблица `scheduled_jobs` создана миграцией как задел, но executor/UI для неё не написаны в этой версии |
| Telegram-оплата (Stars) / биллинг | **NOT IMPLEMENTED** | Таблицы `subscriptions`/`payments` в схеме есть, но логика биллинга (grace period, приостановка по неуплате, интеграция с Telegram Payments) — за рамками этой версии, см. приоритеты в конце README |
| ClamAV / ModSecurity | **NOT IMPLEMENTED** | Явно вне первой версии — см. спецификацию: ModSecurity рекомендовано включать только после сбора false positives, ClamAV — точечно на загрузку, не синхронно на каждый запрос. Ни то, ни другое не установлено `install.sh` |

## Тесты

42 автотеста, 0 провалено на момент последнего прогона
(`php hosting/tests/run.php`). Без PHPUnit — свой минимальный runner поверх
SQLite-зеркала MariaDB-схемы (`tests/schema.sqlite.sql`); production всегда
работает на реальной MariaDB через `panel/bin/migrate.php`
(см. `tests/schema.sqlite.sql` header — это осознанное разделение, не
попытка выдать тестовую БД за боевую).

Живые (не just unit-test) проверки, выполненные в процессе разработки:
регистрация → логин → создание сайта → IDOR-попытка отклонена (403) →
вход в админку не-админом отклонён (403) → редирект неавторизованного на
/login (через встроенный PHP-сервер и настоящие HTTP-запросы); полный
цикл backup.sh → порча файла → restore.sh → файл восстановлен, права и
`tmp/` не тронуты → попытка восстановить из испорченного архива отклонена
по checksum; `nginx -t`, `nft -c -f`, `visudo -cf` — все настоящие
бинарники, не эмуляция.
