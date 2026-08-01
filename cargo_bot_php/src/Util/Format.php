<?php

namespace CargoBot\Util;

class Format
{
    /** Число без лишних нулей: 5.50 -> «5.5», 12.00 -> «12». */
    public static function num($value): string
    {
        if ($value === null || $value === '') {
            return '0';
        }
        $s = number_format((float) $value, 4, '.', '');
        $s = rtrim(rtrim($s, '0'), '.');
        return $s === '' || $s === '-' ? '0' : $s;
    }

    public static function money($value): string
    {
        return self::num(round((float) $value, 2));
    }

    /** Экранирование для HTML parse_mode Telegram. */
    public static function esc(?string $text): string
    {
        return htmlspecialchars((string) $text, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }

    /** Разбор числа из пользовательского ввода: «12,5» -> 12.5. Null если не число. */
    public static function parseNumber(?string $text): ?float
    {
        $text = trim(str_replace([',', ' '], ['.', ''], (string) $text));
        if ($text === '' || !is_numeric($text)) {
            return null;
        }
        $value = (float) $text;
        return $value < 0 ? null : $value;
    }

    public static function date(?string $sql, string $format = 'd.m.Y H:i'): string
    {
        if (!$sql) {
            return '—';
        }
        $ts = strtotime($sql);
        return $ts ? date($format, $ts) : '—';
    }

    public static function trunc(string $text, int $limit = 42): string
    {
        if (mb_strlen($text) <= $limit) {
            return $text;
        }
        return mb_substr($text, 0, $limit - 1) . '…';
    }

    /** «-» и пустая строка означают «пропустить». */
    public static function isSkip(?string $text): bool
    {
        return in_array(trim((string) $text), ['-', '—', ''], true);
    }
}
