<?php
namespace Core;

/**
 * JSON response helpers.
 */
final class Response
{
    public static function json($data, int $status = 200): void
    {
        // Discard anything already emitted (a stray BOM or warning from an
        // included file would otherwise precede the JSON and break parsing).
        while (ob_get_level() > 0) {
            ob_end_clean();
        }

        if (!headers_sent()) {
            http_response_code($status);
            header('Content-Type: application/json; charset=utf-8');
        }

        $json = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        if ($json === false) {
            // Invalid UTF-8 somewhere in the data: escape it rather than fail.
            $json = json_encode($data, JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
        }
        echo $json;
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
