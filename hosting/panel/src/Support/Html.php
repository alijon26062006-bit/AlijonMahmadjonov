<?php
declare(strict_types=1);

namespace Hosting\Support;

/** htmlspecialchars-обёртка на каждый вывод пользовательских данных в views. */
final class Html
{
    /**
     * Русское склонение по числу: 1 сайт, 2 сайта, 5 сайтов.
     *
     * Правило «одна форма для 1, другая для всего остального» даёт «1 баз
     * данных» и «2 сайтов» — на витрине с тарифами это видно сразу.
     */
    public static function plural(int $n, string $one, string $few, string $many): string
    {
        $n = abs($n) % 100;
        if ($n >= 11 && $n <= 14) {
            return $many;
        }
        return match ($n % 10) {
            1       => $one,
            2, 3, 4 => $few,
            default => $many,
        };
    }

    public static function e(mixed $value): string
    {
        return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
