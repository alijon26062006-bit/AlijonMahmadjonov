<?php
/**
 * Точка входа webhook. Этот адрес указывается Telegram
 * (см. bin/set_webhook.php).
 */
declare(strict_types=1);

// Работает при двух схемах размещения:
//  1) public/ — корень сайта, остальное уровнем выше (надёжнее);
//  2) все файлы лежат прямо в public_html (частый случай на хостингах).
$autoload = is_file(dirname(__DIR__) . '/src/autoload.php')
    ? dirname(__DIR__) . '/src/autoload.php'
    : __DIR__ . '/src/autoload.php';
require $autoload;

use CargoBot\Bot;
use CargoBot\Config;
use CargoBot\Handler\Router;

// Telegram не читает тело ответа — отвечаем 200 сразу, чтобы не было повторов.
http_response_code(200);
header('Content-Type: text/plain; charset=utf-8');

try {
    $config = Config::load();
} catch (\Throwable $e) {
    error_log('CargoBot config: ' . $e->getMessage());
    echo 'config error';
    exit;
}

if (($tz = $config->get('timezone')) && is_string($tz)) {
    date_default_timezone_set($tz);
}

// Защита webhook: Telegram присылает секрет в заголовке.
$secret = $config->webhookSecret();
if ($secret !== '') {
    $got = $_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? '';
    if (!hash_equals($secret, (string) $got)) {
        http_response_code(403);
        echo 'forbidden';
        exit;
    }
}

$raw = file_get_contents('php://input');
$update = json_decode((string) $raw, true);
if (!is_array($update)) {
    echo 'no update';
    exit;
}

try {
    $bot = new Bot($config);
    (new Router($bot))->handle($update);
    echo 'ok';
} catch (\Throwable $e) {
    $message = 'ОШИБКА: ' . $e->getMessage() . ' @ ' . $e->getFile() . ':' . $e->getLine();
    error_log('CargoBot: ' . $message);
    if (isset($bot)) {
        $bot->log($message);
        // сообщаем администраторам, чтобы сбой не остался незамеченным
        try {
            foreach ($config->adminIds() as $adminId) {
                $bot->api->sendMessage($adminId, "⚠️ Сбой в боте:\n<code>"
                    . htmlspecialchars($e->getMessage(), ENT_QUOTES, 'UTF-8') . '</code>');
            }
        } catch (\Throwable $ignored) {
        }
    }
    echo 'error';
}
