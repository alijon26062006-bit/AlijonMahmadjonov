<?php
declare(strict_types=1);

namespace Hosting\Service;

/**
 * Файл .env конкретного сайта — единственное место, где живут его секреты
 * (токен Telegram-бота, секрет webhook).
 *
 * Лежит НАД каталогом public/, поэтому веб-сервер его не отдаёт: document root
 * указывает на public/, а из него в родительский каталог не выйти. Плюс сам
 * nginx отдельно запрещает точечные пути и *.env (см. templates/nginx-site-*.tpl).
 *
 * Права: 0644, группа — hosting-web. Спецификация просила 0600, но файл нужен
 * трём разным пользователям: панель (hosting-panel) записывает в него токен,
 * php-fpm клиента читает секрет из webhook.php, и владельцем при этом может
 * оказаться любой из них. Секрет защищает не режим файла, а КАТАЛОГ: он имеет
 * права 2770 client:hosting-web, и посторонний в него просто не заходит.
 * Из браузера файл тоже недоступен — он лежит над public/, и nginx отдельно
 * запрещает *.env.
 */
final class SiteEnv
{
    public function __construct(private string $siteDir)
    {
    }

    public function path(): string
    {
        return $this->siteDir . '/.env';
    }

    public function exists(): bool
    {
        return is_file($this->path());
    }

    /** @return array<string,string> */
    public function all(): array
    {
        if (!$this->exists()) {
            return [];
        }
        $contents = @file_get_contents($this->path());

        return $contents === false ? [] : \Hosting\Support\Env::parse($contents);
    }

    public function get(string $key, string $default = ''): string
    {
        return $this->all()[$key] ?? $default;
    }

    /**
     * Записывает значения, сохраняя остальные строки файла как есть — чтобы не
     * затирать переменные, которые клиент добавил сам.
     *
     * @param array<string,string> $values
     */
    public function set(array $values): void
    {
        $lines = $this->exists() ? explode("\n", (string) @file_get_contents($this->path())) : [];
        $written = [];

        foreach ($lines as $i => $line) {
            foreach ($values as $key => $value) {
                if (preg_match('~^' . preg_quote($key, '~') . '\s*=~', $line) === 1) {
                    $lines[$i] = $key . '=' . $value;
                    $written[$key] = true;
                }
            }
        }

        foreach ($values as $key => $value) {
            if (!isset($written[$key])) {
                $lines[] = $key . '=' . $value;
            }
        }

        $body = rtrim(implode("\n", $lines), "\n") . "\n";
        if (@file_put_contents($this->path(), $body) === false) {
            throw new \RuntimeException('Не удалось сохранить настройки сайта (.env)');
        }
        @chmod($this->path(), 0o644);
    }

    public function remove(string ...$keys): void
    {
        if (!$this->exists()) {
            return;
        }
        $lines = explode("\n", (string) @file_get_contents($this->path()));
        $kept = [];

        foreach ($lines as $line) {
            $drop = false;
            foreach ($keys as $key) {
                if (preg_match('~^' . preg_quote($key, '~') . '\s*=~', $line) === 1) {
                    $drop = true;
                }
            }
            if (!$drop) {
                $kept[] = $line;
            }
        }

        @file_put_contents($this->path(), rtrim(implode("\n", $kept), "\n") . "\n");
        @chmod($this->path(), 0o644);
    }

    /**
     * Токен для показа в панели: 123456789:ABCD************
     *
     * Полный токен не показываем никогда и после сохранения — тот, кто получил
     * доступ к чужой сессии, не должен уносить с собой рабочий токен бота.
     */
    public static function maskToken(string $token): string
    {
        if ($token === '') {
            return '';
        }
        $parts = explode(':', $token, 2);
        if (count($parts) !== 2) {
            return str_repeat('*', min(16, strlen($token)));
        }
        $tail = substr($parts[1], 0, 4);

        return $parts[0] . ':' . $tail . str_repeat('*', 12);
    }
}
