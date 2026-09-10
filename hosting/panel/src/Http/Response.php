<?php
declare(strict_types=1);

namespace Hosting\Http;

final class Response
{
    private function __construct(
        public readonly int $status,
        public readonly array $headers,
        public readonly string $body,
    ) {
    }

    public static function html(string $body, int $status = 200): self
    {
        return new self($status, ['Content-Type' => 'text/html; charset=utf-8'], $body);
    }

    public static function json(array $data, int $status = 200): self
    {
        return new self(
            $status,
            ['Content-Type' => 'application/json; charset=utf-8'],
            (string) json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)
        );
    }

    public static function redirect(string $location, int $status = 302): self
    {
        return new self($status, ['Location' => $location], '');
    }

    public static function text(string $body, int $status = 200): self
    {
        return new self($status, ['Content-Type' => 'text/plain; charset=utf-8'], $body);
    }

    /**
     * Файл на скачивание. Имя уходит в заголовок в двух видах: ASCII-запасной и
     * filename* по RFC 5987 — без второго кириллические имена в браузере
     * превращаются в мусор.
     */
    public static function download(string $body, string $filename, string $type = 'application/octet-stream'): self
    {
        $ascii = preg_replace('~[^A-Za-z0-9._-]~', '_', $filename) ?: 'file';

        return new self(200, [
            'Content-Type'        => $type,
            'Content-Disposition' => 'attachment; filename="' . $ascii . '"; '
                . "filename*=UTF-8''" . rawurlencode($filename),
            'Content-Length'      => (string) strlen($body),
            'Cache-Control'       => 'no-store',
        ], $body);
    }

    public function send(): void
    {
        if (!headers_sent()) {
            http_response_code($this->status);
            foreach ($this->headers as $name => $value) {
                header($name . ': ' . $value);
            }
            // Панель отдаёт только свои страницы и открывается внутри Telegram.
            header('X-Content-Type-Options: nosniff');
            header('Referrer-Policy: same-origin');
        }
        echo $this->body;
    }
}
