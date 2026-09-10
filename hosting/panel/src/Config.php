<?php
declare(strict_types=1);

namespace Hosting;

/**
 * Настройки панели и воркера. Читаются из окружения (.env или переменные системы).
 * Ничего секретного в коде — только значения по умолчанию для локального запуска.
 *
 * Важное разделение прав: PANEL_DB_* — учётка веб-панели, у неё нет доступа к чужим
 * базам и нет прав CREATE USER. MYSQL_ADMIN_* — учётка root-воркера (systemd, не веб-процесс),
 * ею создаются и удаляются клиентские базы. Веб-процесс панели эти переменные не должен
 * даже читать в проде — см. worker/.
 */
final class Config
{
    private array $values;

    private function __construct(array $values)
    {
        $this->values = $values;
    }

    public static function fromEnv(?array $env = null): self
    {
        $env = $env ?? array_merge($_ENV, $_SERVER, getenv());

        $get = static function (string $key, string $default) use ($env): string {
            $value = $env[$key] ?? '';
            $value = is_string($value) ? trim($value) : '';
            return $value !== '' ? $value : $default;
        };

        $root = rtrim($get('HOSTING_ROOT', '/srv/hosting'), '/');
        $usersRoot = rtrim($get('HOSTING_USERS_ROOT', '/home/hosting'), '/');

        return new self([
            'app_env'         => $get('APP_ENV', 'production'),
            'app_url'         => rtrim($get('APP_URL', 'https://panel.myhost.tj'), '/'),
            'panel_name'      => $get('PANEL_NAME', 'AlijonHost'),

            // Единственное место, откуда домен клиентов берётся во всей кодовой базе.
            'root_domain'     => strtolower($get('HOSTING_ROOT_DOMAIN', 'myhost.tj')),
            'server_ip'       => $get('HOSTING_SERVER_IP', ''),

            'hosting_root'    => $root,
            'users_root'      => $usersRoot,
            'state_dir'       => $get('STATE_DIR', $root . '/var'),

            // Панельная БД (MariaDB) — учётка с обычными правами, БЕЗ доступа к чужим базам.
            'db_host'         => $get('DB_HOST', '127.0.0.1'),
            'db_port'         => (int) $get('DB_PORT', '3306'),
            'db_database'     => $get('DB_DATABASE', 'hosting_panel'),
            'db_username'     => $get('DB_USERNAME', 'hosting_panel'),
            'db_password'     => $get('DB_PASSWORD', ''),

            // Тестовый режим: SQLite вместо MariaDB (см. tests/). В production не используется.
            'db_driver'       => $get('DB_DRIVER', 'mysql'),
            'db_sqlite_path'  => $get('DB_SQLITE_PATH', ':memory:'),

            // Куда генератор кладёт конфиги веб-сервера.
            'nginx_available_dir' => $get('NGINX_AVAILABLE_DIR', '/etc/nginx/sites-available'),
            'nginx_enabled_dir'   => $get('NGINX_ENABLED_DIR', '/etc/nginx/sites-enabled'),
            'fpm_pool_dir'        => $get('FPM_POOL_DIR', '/etc/php/8.3/fpm/pool.d'),
            'log_dir'             => $get('LOG_DIR', '/var/log/hosting'),

            // Данные для root-воркера (create_database/delete_database). Пусты для веб-панели.
            'mysql_host'      => $get('MYSQL_HOST', '127.0.0.1'),
            'mysql_port'      => (int) $get('MYSQL_PORT', '3306'),
            'mysql_admin'     => $get('MYSQL_ADMIN_USER', 'root'),
            'mysql_password'  => $get('MYSQL_ADMIN_PASSWORD', ''),

            'php_versions'    => array_values(array_filter(array_map(
                'trim',
                explode(',', $get('PHP_VERSIONS', '8.3'))
            ))),
            'fpm_listen_tpl'  => $get('FPM_LISTEN', '/run/php/{user}.sock'),

            'default_plan'    => $get('DEFAULT_PLAN', 'start'),
            'registration'    => $get('REGISTRATION', 'open') === 'open',
            'upload_max_mb'   => (int) $get('UPLOAD_MAX_MB', '64'),

            // Telegram Mini App
            'telegram_bot_token' => $get('TELEGRAM_BOT_TOKEN', ''),

            // Cloudflare (wildcard DNS-01 + firewall allowlist)
            'cloudflare_api_token' => $get('CLOUDFLARE_API_TOKEN', ''),
            'cloudflare_zone_id'   => $get('CLOUDFLARE_ZONE_ID', ''),

            // Резервные копии
            'backup_provider' => $get('BACKUP_PROVIDER', ''), // rclone remote name, пусто = только локально
            'backup_bucket'   => $get('BACKUP_BUCKET', ''),
            'backup_dir'      => $get('BACKUP_DIR', $root . '/backups'),

            // Сессии панели
            'session_secret'  => $get('SESSION_SECRET', ''),
            'session_ttl'     => (int) $get('SESSION_TTL_SECONDS', '1209600'), // 14 дней

            'acme_email'      => $get('ACME_EMAIL', ''),
        ]);
    }

    public static function fromArray(array $values): self
    {
        return new self($values);
    }

    public function get(string $key): mixed
    {
        if (!array_key_exists($key, $this->values)) {
            throw new \InvalidArgumentException("Неизвестная настройка: {$key}");
        }
        return $this->values[$key];
    }

    public function str(string $key): string
    {
        return (string) $this->get($key);
    }

    public function int(string $key): int
    {
        return (int) $this->get($key);
    }

    public function bool(string $key): bool
    {
        return (bool) $this->get($key);
    }

    public function defaultPhpVersion(): string
    {
        $versions = $this->get('php_versions');
        return $versions[0] ?? '8.3';
    }

    public function withOverrides(array $overrides): self
    {
        return new self(array_merge($this->values, $overrides));
    }

    public function all(): array
    {
        return $this->values;
    }
}
