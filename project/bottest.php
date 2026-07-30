<?php
/**
 * Диагностика бота (временный файл).
 *   https://ваш-домен/kino/bottest.php?key=ВАШ_WEBHOOK_SECRET
 * После проверки — УДАЛИТЕ этот файл.
 */

declare(strict_types=1);
ini_set('display_errors', '1');
error_reporting(E_ALL);
header('Content-Type: text/plain; charset=utf-8');

$config = require __DIR__ . '/config/config.php';

if (($_GET['key'] ?? '') !== $config['telegram']['webhook_secret']) {
    http_response_code(403);
    exit("Dostup zapreshen. Otkroyte: bottest.php?key=WEBHOOK_SECRET\n");
}

require __DIR__ . '/bot/autoload.php';

use Bot\Bot;
use Bot\TelegramApi;
use Core\Database;

$ok = static fn (bool $c): string => $c ? 'OK' : 'OSHIBKA <<<';

echo "=== 1. KONFIG ===\n";
echo 'bot_token: ' . (strlen((string) $config['telegram']['bot_token']) > 20 ? 'est' : 'NET <<<') . "\n";
echo 'bot_username: ' . (($config['telegram']['bot_username'] ?? '') ?: 'NE ZADAN <<<') . "\n";
echo 'admin_ids: ' . implode(',', $config['telegram']['admin_ids']) . "\n";
echo 'miniapp_url: ' . $config['telegram']['miniapp_url'] . "\n";
echo 'webhook_url: ' . $config['telegram']['webhook_url'] . "\n\n";

echo "=== 2. FAYLY BOTA (versii) ===\n";
$files = [
    'bot/Bot.php', 'bot/AiFlow.php', 'bot/AdminFlow.php', 'bot/EpisodeFlow.php',
    'bot/ContentRepo.php', 'bot/TelegramApi.php', 'bot/Media.php', 'bot/StateStore.php',
    'bot/autoload.php', 'api/core/TelegramAuth.php', 'api/models/Episode.php',
];
foreach ($files as $f) {
    $p = __DIR__ . '/' . $f;
    echo str_pad($f, 30) . (is_file($p) ? date('d.m H:i', (int) filemtime($p)) . '  ' . filesize($p) . ' b' : 'NET FAYLA <<<') . "\n";
}

echo "\n=== 3. KLASSY I METODY ===\n";
$need = [
    'Bot\\Bot' => ['handleUpdate'],
    'Bot\\ContentRepo' => ['getSetting', 'setSetting', 'episodePlayable', 'createEpisode'],
    'Bot\\TelegramApi' => ['sendVideo', 'sendPhoto'],
    'Bot\\EpisodeFlow' => ['handle', 'handleCallback'],
    'Bot\\AiFlow' => ['handle', 'handleCallback'],
    'Models\\Episode' => ['forMovie', 'playable'],
];
$problems = [];
foreach ($need as $cls => $methods) {
    if (!class_exists($cls)) {
        echo str_pad($cls, 22) . "KLASS NE NAYDEN <<<\n";
        $problems[] = $cls;
        continue;
    }
    $miss = [];
    foreach ($methods as $m) {
        if (!method_exists($cls, $m)) {
            $miss[] = $m;
        }
    }
    echo str_pad($cls, 22) . ($miss ? 'NET METODOV: ' . implode(',', $miss) . ' <<< STARYY FAYL' : 'OK') . "\n";
    if ($miss) {
        $problems[] = $cls;
    }
}

echo "\n=== 4. BAZA ===\n";
try {
    Database::connect($config['db']);
    echo "podklyuchenie: OK\n";
    $tables = Database::pdo()->query('SHOW TABLES')->fetchAll(PDO::FETCH_COLUMN);
    foreach (['movies', 'episodes', 'settings', 'bot_states', 'users'] as $t) {
        echo str_pad($t, 14) . $ok(in_array($t, $tables, true)) . "\n";
    }
} catch (Throwable $e) {
    exit('BAZA OSHIBKA: ' . $e->getMessage() . "\n");
}

echo "\n=== 5. TELEGRAM API ===\n";
$api = new TelegramApi($config['telegram']['bot_token']);
$me  = $api->call('getMe');
if (!empty($me['ok'])) {
    echo 'getMe: OK -> @' . ($me['result']['username'] ?? '?') . "\n";
} else {
    echo "getMe: OSHIBKA <<< (token neverny ili net vyhoda v internet)\n";
    echo json_encode($me, JSON_UNESCAPED_UNICODE) . "\n";
}

$wh = $api->call('getWebhookInfo');
if (!empty($wh['ok'])) {
    $r = $wh['result'];
    echo 'webhook url: ' . ($r['url'] ?: 'NE USTANOVLEN <<<') . "\n";
    echo 'ozhidaet obnovleniy: ' . ($r['pending_update_count'] ?? 0) . "\n";
    if (!empty($r['last_error_message'])) {
        echo 'POSLEDNYAYA OSHIBKA: ' . $r['last_error_message'] . "\n";
        echo 'vremya: ' . date('d.m H:i', (int) ($r['last_error_date'] ?? 0)) . "\n";
    } else {
        echo "oshibok net\n";
    }
}

echo "\n=== 6. SIMULYATSIYA /start ===\n";
$admin = (int) ($config['telegram']['admin_ids'][0] ?? 0);
try {
    $bot = new Bot($config);
    echo "Bot sozdan: OK\n";
    $bot->handleUpdate([
        'message' => [
            'message_id' => 1,
            'chat' => ['id' => $admin, 'type' => 'private'],
            'from' => ['id' => $admin, 'first_name' => 'Test', 'is_bot' => false],
            'text' => '/start',
        ],
    ]);
    echo "/start obrabotan bez oshibok: OK\n";
    echo "Proverte Telegram - prishlo li privetstvie.\n";
} catch (Throwable $e) {
    echo "FATALNAYA OSHIBKA:\n";
    echo '  ' . $e->getMessage() . "\n";
    echo '  fayl: ' . $e->getFile() . ':' . $e->getLine() . "\n";
}

echo "\n=== ITOG ===\n";
echo $problems
    ? "Nuzhno perezalit fayly: " . implode(', ', $problems) . "\n"
    : "Vse fayly aktualny.\n";
echo "Posle proverki UDALITE bottest.php\n";
