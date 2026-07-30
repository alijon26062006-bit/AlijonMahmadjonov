<?php
/**
 * Диагностика кодировки (временный файл).
 *   https://ваш-домен/kino/enc.php?key=ВАШ_WEBHOOK_SECRET
 * После проверки — УДАЛИТЕ.
 */
declare(strict_types=1);
header('Content-Type: text/plain; charset=utf-8');

$config = require __DIR__ . '/config/config.php';
if (($_GET['key'] ?? '') !== $config['telegram']['webhook_secret']) {
    http_response_code(403);
    exit("forbidden\n");
}
require __DIR__ . '/bot/autoload.php';

use Bot\TelegramApi;

$api   = new TelegramApi($config['telegram']['bot_token']);
$admin = (int) ($config['telegram']['admin_ids'][0] ?? 0);

// «Привет» из кодовых точек — всегда правильно, не зависит от кодировки файла.
$fromEscape  = "\u{041f}\u{0440}\u{0438}\u{0432}\u{0435}\u{0442}";
// «Привет» литералом в ЭТОМ файле — зависит от кодировки enc.php на сервере.
$fromLiteral = "Привет";

$r1 = $api->sendMessage($admin, "TEST-1 (кодовые точки): {$fromEscape}");
$r2 = $api->sendMessage($admin, "TEST-2 (литерал в enc.php): {$fromLiteral}");

// Правильные UTF-8 байты слова «Привет»:
$needle = "\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82";
// Байты двойной кодировки (Ð…):
$mojibake = "\xc3\x90\xc2\x9f";

$check = static function (string $path) use ($needle, $mojibake): string {
    if (!is_file($path)) {
        return 'файл не найден';
    }
    $b = (string) file_get_contents($path);
    $utf8 = mb_check_encoding($b, 'UTF-8') ? 'UTF-8-ок' : 'НЕ-UTF-8';
    $correct = strpos($b, $needle) !== false ? 'да' : 'нет';
    $double  = strpos($b, $mojibake) !== false ? 'ДА ⚠️' : 'нет';
    return "{$utf8} | правильный «Привет»: {$correct} | двойная-кодировка: {$double}";
};

echo "=== ФАЙЛЫ НА СЕРВЕРЕ ===\n";
echo "enc.php          : " . $check(__DIR__ . '/enc.php') . "\n";
echo "bot/Bot.php      : " . $check(__DIR__ . '/bot/Bot.php') . "\n";
echo "assets/js/app.js : " . $check(__DIR__ . '/assets/js/app.js') . "\n\n";

echo "=== ОТПРАВКА ===\n";
echo "TEST-1 отправлен: " . (!empty($r1['ok']) ? 'да' : 'нет') . "\n";
echo "TEST-2 отправлен: " . (!empty($r2['ok']) ? 'да' : 'нет') . "\n\n";
echo "👉 Посмотрите в Telegram: какой из TEST-1 / TEST-2 стал кракозябрами?\n";
echo "После проверки удалите enc.php.\n";
