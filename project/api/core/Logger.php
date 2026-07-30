<?php
namespace Core;

/**
 * Minimal file logger. Writes to project/logs.
 */
final class Logger
{
    private static string $dir = __DIR__ . '/../../logs';

    public static function log(string $level, string $message): void
    {
        $line = sprintf("[%s] %s: %s%s", date('Y-m-d H:i:s'), strtoupper($level), $message, PHP_EOL);
        $file = self::$dir . '/' . date('Y-m-d') . '.log';
        @file_put_contents($file, $line, FILE_APPEND | LOCK_EX);
    }

    public static function error(string $message): void
    {
        self::log('error', $message);
    }

    public static function info(string $message): void
    {
        self::log('info', $message);
    }
}
