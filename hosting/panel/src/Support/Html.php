<?php
declare(strict_types=1);

namespace Hosting\Support;

/** htmlspecialchars-обёртка на каждый вывод пользовательских данных в views. */
final class Html
{
    public static function e(mixed $value): string
    {
        return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
