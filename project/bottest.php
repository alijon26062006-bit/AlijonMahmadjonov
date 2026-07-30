<?php
/**
 * Диагностика бота (временный файл). Откройте в браузере:
 *   https://ваш-домен/kino/bottest.php?key=ВАШ_WEBHOOK_SECRET
 * ПОСЛЕ проверки — УДАЛИТЕ этот файл.
 */

declare(strict_types=1);
ini_set('display_errors', '1');
error_reporting(E_ALL);
header('Content-Type: text/plain; charset=utf-8');

$config = require __DIR__ . '/config/config.php';

if (($_GET['key'] ?? '') !== $config['telegram']['webhook_secret']) {
    http_response_code(403);
    exit("Доступ запрещён. Откройте: bottest.php?key=ВАШ_WEBHOOK_SECRET\n");
}

require __DIR__ . '/bot/autoload.php';

use Bot\TelegramApi;
use Bot\Bot;
use Core\Database;

echo "=== НАСТРОЙКИ ===\n";
echo "miniapp_url: " . $config['telegram']['miniapp_url'] . "\n";
echo "webhook_url: " . $config['telegram']['webhook_url'] . "\n";
echo "admin_ids:   " . implode(',', $config['telegram']['admin_ids']) . "\n";
echo "webhook_secret: " . $config['telegram']['webhook_secret'] . "\n\n";

echo "=== БАЗА ===\n";
try {
    Database::connect($config['db']);
    echo "Подключение к базе: OK\n\n";
} catch (Throwable $e) {
    exit("Подключение к базе: ОШИБКА — " . $e->getMessage() . "\n");
}

$api   = new TelegramApi($config['telegram']['bot_token']);
$admin = (int) ($config['telegram']['admin_ids'][0] ?? 0);

echo "=== 1) ОБЫЧНОЕ СООБЩЕНИЕ ===\n";
$r1 = $api->sendMessage($admin, "✅ Тест 1: обычное сообщение работает.");
echo json_encode($r1, JSON_UNESCAPED_UNICODE) . "\n\n";

echo "=== 2) КНОПКА MINI APP (как в /start) ===\n";
$r2 = $api->sendMessage($admin, "✅ Тест 2: кнопка «Открыть кино».", [
    'reply_markup' => json_encode(['inline_keyboard' => [[
        ['text' => '🎬 Открыть кино', 'web_app' => ['url' => $config['telegram']['miniapp_url']]],
    ]]]),
]);
echo json_encode($r2, JSON_UNESCAPED_UNICODE) . "\n\n";

echo "=== 3) СИМУЛЯЦИЯ /start ===\n";
try {
    $bot = new Bot($config);
    $bot->handleUpdate([
        'message' => [
            'message_id' => 1,
            'chat' => ['id' => $admin, 'type' => 'private'],
            'from' => ['id' => $admin, 'first_name' => 'Test', 'is_bot' => false],
            'text' => '/start',
        ],
    ]);
    echo "Обработано без фатальных ошибок. Проверьте Telegram — пришло ли приветствие.\n";
} catch (Throwable $e) {
    echo "ОШИБКА при /start: " . $e->getMessage() . "\n";
    echo "  файл: " . $e->getFile() . ":" . $e->getLine() . "\n";
}

echo "\nГотово. После проверки УДАЛИТЕ bottest.php.\n";
