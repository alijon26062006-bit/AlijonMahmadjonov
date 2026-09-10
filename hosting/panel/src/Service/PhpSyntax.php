<?php
declare(strict_types=1);

namespace Hosting\Service;

/**
 * Проверка синтаксиса PHP перед сохранением файла.
 *
 * Спецификация предполагала `php -l /path/to/file.php`. Здесь тот же разбор
 * делается прямо в процессе — token_get_all() с флагом TOKEN_PARSE запускает
 * настоящий парсер PHP и бросает ParseError ровно там же, где ругнулся бы php -l.
 *
 * Так лучше по трём причинам:
 *   1. Не нужен запуск процессов — веб-процессу панели shell-функции запрещены
 *      (disable_functions в php-fpm-panel.conf), и правильно запрещены.
 *   2. Нет ни временного файла, ни аргумента командной строки — значит, нет и
 *      места, где могла бы возникнуть shell-инъекция.
 *   3. Ответ мгновенный: не нужно гонять задание через очередь root-воркера.
 *
 * Код НЕ выполняется: парсер только разбирает текст на токены.
 */
final class PhpSyntax
{
    /**
     * @return array{ok:bool,line:int|null,message:string|null}
     */
    public static function check(string $code): array
    {
        // Файл без открывающего тега — это просто текст, разбирать нечего.
        if (!str_contains($code, '<?php') && !str_contains($code, '<?=')) {
            return ['ok' => true, 'line' => null, 'message' => null];
        }

        try {
            token_get_all($code, TOKEN_PARSE);
            return ['ok' => true, 'line' => null, 'message' => null];
        } catch (\ParseError $e) {
            return [
                'ok'      => false,
                'line'    => $e->getLine(),
                'message' => self::cleanMessage($e->getMessage()),
            ];
        } catch (\Throwable $e) {
            return ['ok' => false, 'line' => null, 'message' => 'Не удалось разобрать файл'];
        }
    }

    /** Человеческий текст ошибки для показа клиенту. */
    public static function describe(array $result): string
    {
        if ($result['ok']) {
            return '';
        }
        $where = $result['line'] !== null ? "Ошибка PHP в строке {$result['line']}: " : 'Ошибка PHP: ';

        return $where . ($result['message'] ?? 'синтаксическая ошибка');
    }

    /**
     * Убирает из сообщения парсера путь к файлу и хвост «in ... on line N».
     * Клиенту незачем видеть внутренние пути сервера, а строка показывается отдельно.
     */
    private static function cleanMessage(string $message): string
    {
        $message = preg_replace('~\s+in\s+/\S+\s+on line\s+\d+~', '', $message) ?? $message;
        $message = preg_replace('~\s*in\s+/\S+$~', '', $message) ?? $message;

        return trim($message);
    }
}
