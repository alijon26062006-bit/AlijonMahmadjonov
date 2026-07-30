<?php
declare(strict_types=1);

/**
 * Telegram webhook entry point. Point BotFather's webhook here:
 *   https://your-domain/project/bot/webhook.php
 */

use Bot\Bot;
use Core\Database;
use Core\Logger;

require __DIR__ . '/autoload.php';

$config = require __DIR__ . '/../config/config.php';
$GLOBALS['APP_CONFIG'] = $config;

// Verify Telegram's secret token to reject forged requests
$expected = $config['telegram']['webhook_secret'];
$received = $_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? '';
if ($expected !== '' && !hash_equals($expected, $received)) {
    http_response_code(403);
    exit('forbidden');
}

$raw    = file_get_contents('php://input') ?: '';
$update = json_decode($raw, true);
if (!is_array($update)) {
    http_response_code(400);
    exit('bad request');
}

try {
    Database::connect($config['db']);
    (new Bot($config))->handleUpdate($update);
} catch (Throwable $e) {
    Logger::error('Webhook error: ' . $e->getMessage() . ' @ ' . $e->getLine());
}

// Always 200 so Telegram doesn't retry endlessly
http_response_code(200);
echo 'ok';
