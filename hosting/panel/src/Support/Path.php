<?php
declare(strict_types=1);

namespace Hosting\Support;

/**
 * Работа с путями внутри домашнего каталога клиента.
 * Главная задача — не дать выйти за пределы каталога (../, симлинки, абсолютные пути).
 */
final class Path
{
    /**
     * Приводит относительный путь к безопасному виду: убирает «..», «.», лишние слэши.
     * Возвращает путь без ведущего слэша, например "public_html/index.php".
     */
    public static function normalize(string $relative): string
    {
        $relative = str_replace('\\', '/', $relative);
        $parts = [];

        foreach (explode('/', $relative) as $part) {
            if ($part === '' || $part === '.') {
                continue;
            }
            if ($part === '..') {
                array_pop($parts);
                continue;
            }
            $parts[] = $part;
        }

        return implode('/', $parts);
    }

    /**
     * Склеивает корень и относительный путь и проверяет, что результат остался внутри корня.
     * Если путь существует — сверяется по realpath (ловит симлинки наружу).
     *
     * @throws \RuntimeException если путь выходит за пределы корня
     */
    public static function resolve(string $root, string $relative): string
    {
        $rootReal = realpath($root);
        if ($rootReal === false) {
            throw new \RuntimeException('Каталог не найден: ' . $root);
        }

        $normalized = self::normalize($relative);
        $full = $normalized === '' ? $rootReal : $rootReal . '/' . $normalized;

        $existing = realpath($full);
        if ($existing !== false) {
            if (!self::isInside($rootReal, $existing)) {
                throw new \RuntimeException('Выход за пределы домашнего каталога запрещён');
            }
            return $existing;
        }

        // Файла ещё нет (создание) — проверяем существующего родителя.
        $parentReal = realpath(dirname($full));
        if ($parentReal === false || !self::isInside($rootReal, $parentReal)) {
            throw new \RuntimeException('Выход за пределы домашнего каталога запрещён');
        }

        return $parentReal . '/' . basename($full);
    }

    public static function isInside(string $root, string $path): bool
    {
        $root = rtrim($root, '/');
        return $path === $root || str_starts_with($path, $root . '/');
    }

    /** Имя файла или папки без слэшей и служебных символов. */
    public static function isSafeName(string $name): bool
    {
        if ($name === '' || $name === '.' || $name === '..') {
            return false;
        }
        if (strlen($name) > 255) {
            return false;
        }
        return preg_match('~^[A-Za-z0-9._\- ]+$~u', $name) === 1;
    }

    /** Рекурсивно удаляет файл/симлинк/каталог. Используется только на путях, уже проверенных resolve(). */
    public static function removeTree(string $path): void
    {
        if (is_link($path) || is_file($path)) {
            @unlink($path);
            return;
        }
        if (!is_dir($path)) {
            return;
        }
        foreach ((array) scandir($path) as $entry) {
            if ($entry === '.' || $entry === '..') {
                continue;
            }
            self::removeTree($path . '/' . $entry);
        }
        @rmdir($path);
    }

    /** Человекочитаемый размер: 1536 → «1.5 КБ». */
    public static function humanSize(int|float $bytes): string
    {
        $units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ'];
        $index = 0;
        $value = (float) $bytes;

        while ($value >= 1024 && $index < count($units) - 1) {
            $value /= 1024;
            $index++;
        }

        return ($index === 0 ? (string) (int) $value : number_format($value, 1, '.', ' '))
            . ' ' . $units[$index];
    }
}
