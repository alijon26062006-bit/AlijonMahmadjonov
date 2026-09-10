<?php
declare(strict_types=1);

namespace Hosting\Support;

/** Простой загрузчик .env (KEY=value, строки с # — комментарии). */
final class Env
{
    public static function load(string $path): void
    {
        foreach (self::parseFile($path) as $key => $value) {
            if (getenv($key) === false) {
                putenv("{$key}={$value}");
                $_ENV[$key] = $value;
            }
        }
    }

    /** @return array<string,string> */
    public static function parseFile(string $path): array
    {
        if (!is_readable($path)) {
            return [];
        }
        return self::parse((string) file_get_contents($path));
    }

    /** @return array<string,string> */
    public static function parse(string $contents): array
    {
        $result = [];

        foreach (preg_split('~\R~', $contents) ?: [] as $line) {
            $line = trim($line);
            if ($line === '' || str_starts_with($line, '#')) {
                continue;
            }
            $pair = explode('=', $line, 2);
            if (count($pair) !== 2) {
                continue;
            }
            $key = trim($pair[0]);
            $value = trim($pair[1]);
            if ($key === '') {
                continue;
            }
            $quote = $value[0] ?? '';
            if (($quote === '"' || $quote === "'") && str_ends_with($value, $quote) && strlen($value) > 1) {
                $value = substr($value, 1, -1);
            }
            $result[$key] = $value;
        }

        return $result;
    }
}
