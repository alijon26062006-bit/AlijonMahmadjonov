<?php

namespace CargoBot\Telegram;

/** Конструктор клавиатур Telegram. */
class Keyboard
{
    /**
     * Inline-клавиатура.
     * @param array<int,array<int,array{0:string,1:string}>> $rows [[текст, callback_data], ...]
     */
    public static function inline(array $rows): array
    {
        $kb = [];
        foreach ($rows as $row) {
            $line = [];
            foreach ($row as $btn) {
                $line[] = ['text' => $btn[0], 'callback_data' => $btn[1]];
            }
            if ($line) {
                $kb[] = $line;
            }
        }
        return ['inline_keyboard' => $kb];
    }

    /** Обычная клавиатура под полем ввода. */
    public static function reply(array $rows, bool $oneTime = false): array
    {
        $kb = [];
        foreach ($rows as $row) {
            $kb[] = array_map(fn($text) => ['text' => $text], $row);
        }
        return [
            'keyboard'          => $kb,
            'resize_keyboard'   => true,
            'one_time_keyboard' => $oneTime,
        ];
    }

    public static function remove(): array
    {
        return ['remove_keyboard' => true];
    }

    /**
     * Кнопки пагинации: «‹ 2/5 ›» + переданные строки сверху.
     * @param array<int,array<int,array{0:string,1:string}>> $extraRows
     */
    public static function paginate(string $prefix, int $page, int $pages, array $extraRows = [],
                                    string $backData = 'adm:menu', string $backText = '◀️ Админ-меню'): array
    {
        $rows = $extraRows;
        $nav = [];
        if ($page > 1) {
            $nav[] = ['⬅️', $prefix . ':' . ($page - 1)];
        }
        if ($pages > 1) {
            $nav[] = ["$page/$pages", 'noop'];
        }
        if ($page < $pages) {
            $nav[] = ['➡️', $prefix . ':' . ($page + 1)];
        }
        if ($nav) {
            $rows[] = $nav;
        }
        $rows[] = [[$backText, $backData]];
        return self::inline($rows);
    }
}
