<?php
declare(strict_types=1);

namespace Core;

/**
 * JSON response helpers.
 */
final class Response
{
    public static function json($data, int $status = 200): void
    {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        exit;
    }

    public static function ok($data = null, array $meta = []): void
    {
        $payload = ['success' => true, 'data' => $data];
        if ($meta) {
            $payload['meta'] = $meta;
        }
        self::json($payload, 200);
    }

    public static function error(string $message, int $status = 400): void
    {
        self::json(['success' => false, 'error' => $message], $status);
    }
}
