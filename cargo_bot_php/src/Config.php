<?php

namespace CargoBot;

/** Доступ к настройкам из config.php. */
class Config
{
    /** @var array<string,mixed> */
    private array $data;

    public function __construct(array $data)
    {
        $this->data = $data;
    }

    public static function load(?string $path = null): self
    {
        $path = $path ?: dirname(__DIR__) . '/config.php';
        if (!is_file($path)) {
            throw new \RuntimeException(
                "Файл настроек не найден: $path\n" .
                "Скопируйте config.example.php в config.php и заполните его."
            );
        }
        $data = require $path;
        if (!is_array($data)) {
            throw new \RuntimeException('config.php должен возвращать массив.');
        }
        return new self($data);
    }

    /** @return mixed */
    public function get(string $key, $default = null)
    {
        return $this->data[$key] ?? $default;
    }

    public function token(): string
    {
        $token = (string) $this->get('bot_token', '');
        if ($token === '' || strpos($token, 'ВСТАВЬТЕ') !== false) {
            throw new \RuntimeException('Не задан bot_token в config.php');
        }
        return $token;
    }

    /** @return int[] */
    public function adminIds(): array
    {
        return array_map('intval', (array) $this->get('admin_ids', []));
    }

    public function webhookSecret(): string
    {
        return (string) $this->get('webhook_secret', '');
    }

    public function db(): array
    {
        $db = (array) $this->get('db', []);
        if (empty($db['dsn'])) {
            throw new \RuntimeException('Не задан db.dsn в config.php');
        }
        return $db;
    }
}
