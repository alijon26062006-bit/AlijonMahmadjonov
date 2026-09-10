<?php
declare(strict_types=1);

namespace Hosting\Http;

final class Request
{
    public function __construct(
        public readonly string $method,
        public readonly string $path,
        public readonly array $query,
        public readonly array $post,
        public readonly array $files,
        public readonly array $server,
    ) {
    }

    public static function fromGlobals(): self
    {
        $uri = (string) ($_SERVER['REQUEST_URI'] ?? '/');
        $path = parse_url($uri, PHP_URL_PATH);

        return new self(
            strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET')),
            is_string($path) && $path !== '' ? rtrim($path, '/') ?: '/' : '/',
            $_GET,
            $_POST,
            $_FILES,
            $_SERVER,
        );
    }

    public function isPost(): bool
    {
        return $this->method === 'POST';
    }

    public function input(string $key, string $default = ''): string
    {
        $value = $this->post[$key] ?? $this->query[$key] ?? $default;
        return is_string($value) ? trim($value) : $default;
    }

    /** Значение без обрезки пробелов — для содержимого файлов в редакторе. */
    public function raw(string $key, string $default = ''): string
    {
        $value = $this->post[$key] ?? $default;
        return is_string($value) ? $value : $default;
    }

    public function intInput(string $key, int $default = 0): int
    {
        $value = $this->post[$key] ?? $this->query[$key] ?? null;
        return is_numeric($value) ? (int) $value : $default;
    }

    public function header(string $name, string $default = ''): string
    {
        $key = 'HTTP_' . strtoupper(str_replace('-', '_', $name));
        $value = $this->server[$key] ?? $default;
        return is_string($value) ? $value : $default;
    }

    public function wantsJson(): bool
    {
        return str_contains($this->header('accept'), 'application/json')
            || $this->header('x-requested-with') === 'XMLHttpRequest';
    }
}
