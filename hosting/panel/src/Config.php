<?php
declare(strict_types=1);

namespace Hosting;

/**
 * Настройки панели. Читаются из окружения (.env или переменные системы).
 * Ничего секретного в коде — только значения по умолчанию для локального запуска.
 */
final class Config
{
    private array $values;

    private function __construct(array $values)
    {
        $this->values = $values;
    }

    public static function fromEnv(array $env = null): self
    {
        $env = $env ?? array_merge($_ENV, $_SERVER, getenv());

        $get = static function (string $key, string $default) use ($env): string {
            $value = $env[$key] ?? '';
            $value = is_string($value) ? trim($value) : '';
            return $value !== '' ? $value : $default;
        };

        $root = rtrim($get('HOSTING_ROOT', '/srv/hosting'), '/');

        return new self([
            // Базовый домен: сайты клиентов получают <имя>.<BASE_DOMAIN>
            'base_domain'     => strtolower($get('BASE_DOMAIN', 'localhost')),
            'panel_name'      => $get('PANEL_NAME', 'AlijonHost'),
            'hosting_root'    => $root,
            'users_dir'       => $root . '/users',
            'state_dir'       => $get('STATE_DIR', $root . '/var'),
            'db_path'         => $get('PANEL_DB', $root . '/var/panel.sqlite'),
            // Куда генератор кладёт конфиги. На сервере — реальные каталоги nginx/php-fpm.
            'nginx_conf_dir'  => $get('NGINX_CONF_DIR', $root . '/var/nginx'),
            'fpm_pool_dir'    => $get('FPM_POOL_DIR', $root . '/var/php-fpm'),
            'apply_command'   => $get('APPLY_COMMAND', 'sudo -n /usr/local/bin/hosting-apply'),
            // MySQL/MariaDB для баз клиентов
            'mysql_host'      => $get('MYSQL_HOST', '127.0.0.1'),
            'mysql_port'      => (int) $get('MYSQL_PORT', '3306'),
            'mysql_admin'     => $get('MYSQL_ADMIN_USER', 'root'),
            'mysql_password'  => $get('MYSQL_ADMIN_PASSWORD', ''),
            // Доступные версии PHP (первая — по умолчанию)
            'php_versions'    => array_values(array_filter(array_map(
                'trim',
                explode(',', $get('PHP_VERSIONS', '8.3'))
            ))),
            'fpm_listen_tpl'  => $get('FPM_LISTEN', '/run/php/hosting-{user}.sock'),
            // Тариф по умолчанию для новой регистрации
            'default_plan'    => $get('DEFAULT_PLAN', 'start'),
            'registration'    => $get('REGISTRATION', 'open') === 'open',
            'upload_max_mb'   => (int) $get('UPLOAD_MAX_MB', '64'),
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
