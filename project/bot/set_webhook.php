<?php
declare(strict_types=1);

/**
 * One-off helper to register the Telegram webhook.
 * Run from CLI:   php bot/set_webhook.php
 * Or open in a browser once:  https://your-domain/project/bot/set_webhook.php?key=SECRET
 *
 * Uses WEBHOOK_URL and WEBHOOK_SECRET from config.
 */

use Bot\TelegramApi;

require __DIR__ . '/autoload.php';
$config = require __DIR__ . '/../config/config.php';

// Simple guard when invoked over HTTP
if (PHP_SAPI !== 'cli') {
    header('Content-Type: text/plain; charset=utf-8');
    if (($_GET['key'] ?? '') !== $config['telegram']['webhook_secret']) {
        http_response_code(403);
        exit("Forbidden: append ?key=<webhook_secret>\n");
    }
}

$api = new TelegramApi($config['telegram']['bot_token']);
$res = $api->setWebhook(
    $config['telegram']['webhook_url'],
    $config['telegram']['webhook_secret']
);

echo json_encode($res, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE), PHP_EOL;
