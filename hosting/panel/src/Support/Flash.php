<?php
declare(strict_types=1);

namespace Hosting\Support;

/** Одноразовые сообщения между редиректом и следующей страницей (session-based). */
final class Flash
{
    private const KEY = '_flash';

    public static function add(string $type, string $text): void
    {
        self::ensureSession();
        $_SESSION[self::KEY][] = ['type' => $type, 'text' => $text];
    }

    /** @return list<array{type:string,text:string}> */
    public static function pull(): array
    {
        self::ensureSession();
        $flashes = $_SESSION[self::KEY] ?? [];
        $_SESSION[self::KEY] = [];
        return $flashes;
    }

    private static function ensureSession(): void
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            session_start();
        }
    }
}
