<?php
/**
 * Регистрация webhook в Telegram.
 *
 * Консоль:  php bin/set_webhook.php https://ваш-домен/index.php
 * Браузер:  https://ваш-домен/bin/set_webhook.php?key=СЕКРЕТ&url=https://ваш-домен/index.php
 *
 * Проверить текущее состояние:  php bin/set_webhook.php --info
 */
declare(strict_types=1);

require dirname(__DIR__) . '/src/autoload.php';

use CargoBot\Config;
use CargoBot\Telegram\Api;

$isCli = (PHP_SAPI === 'cli');
if (!$isCli) {
    header('Content-Type: text/plain; charset=utf-8');
}

$config = Config::load();
$api = new Api($config->token());

if (!$isCli) {
    $key = $_GET['key'] ?? '';
    if ($config->webhookSecret() === '' || !hash_equals($config->webhookSecret(), (string) $key)) {
        http_response_code(403);
        exit("Доступ запрещён. Добавьте ?key=<webhook_secret из config.php>\n");
    }
}

$me = $api->getMe();
if (!$me) {
    exit("❌ Telegram не принял токен: " . $api->lastError() . "\n");
}
echo "✅ Токен рабочий. Бот: @" . ($me['username'] ?? '?') . "\n";

$url = $isCli ? ($argv[1] ?? '') : (string) ($_GET['url'] ?? '');

if ($url === '--info' || ($url === '' && $isCli && ($argv[1] ?? '') === '--info')) {
    $info = $api->call('getWebhookInfo');
    echo "Текущий webhook:\n" . json_encode($info, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
    exit;
}

if ($url === '') {
    exit("Укажите адрес webhook.\nПример: php bin/set_webhook.php https://ваш-домен/index.php\n");
}
if (strncmp($url, 'https://', 8) !== 0) {
    exit("❌ Telegram принимает только адреса https://\n");
}

$result = $api->setWebhook($url, $config->webhookSecret());
if ($result['ok']) {
    echo "✅ Webhook установлен: $url\n";
    echo "Откройте бота в Telegram и отправьте /start\n";
} else {
    echo "❌ Не удалось установить webhook: " . $result['error'] . "\n";
}
