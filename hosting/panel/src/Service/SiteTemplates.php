<?php
declare(strict_types=1);

namespace Hosting\Service;

/**
 * Готовые заготовки файлов: клиент выбирает «PHP-сайт» или «Telegram-бот» и
 * получает рабочий файл, а не пустую страницу редактора.
 *
 * Шаблоны намеренно живут в коде, а не в отдельных файлах на диске: их надо
 * подставлять в каталог клиента с его правами, и лишний слой чтения файлов
 * добавил бы ещё один путь, который пришлось бы проверять.
 */
final class SiteTemplates
{
    /** @return array<string,array{title:string,description:string,files:array<string,string>,env?:array<string,string>}> */
    public static function all(): array
    {
        return [
            'site' => [
                'title'       => 'Обычный PHP-сайт',
                'description' => 'Страница на PHP: index.php в public/',
                'files'       => ['public/index.php' => self::phpSite()],
            ],
            'telegram' => [
                'title'       => 'Telegram-бот (webhook)',
                'description' => 'webhook.php с проверкой секрета Telegram и .env для токена',
                'files'       => ['public/webhook.php' => self::telegramWebhook()],
                'env'         => ['TELEGRAM_BOT_TOKEN' => '', 'TELEGRAM_WEBHOOK_SECRET' => ''],
            ],
            'api' => [
                'title'       => 'JSON API',
                'description' => 'Ответ application/json в public/index.php',
                'files'       => ['public/index.php' => self::jsonApi()],
            ],
            'landing' => [
                'title'       => 'HTML-страница',
                'description' => 'Простая статическая страница index.html',
                'files'       => ['public/index.html' => self::landing()],
            ],
        ];
    }

    public static function get(string $key): ?array
    {
        return self::all()[$key] ?? null;
    }

    /** Стартовая страница нового сайта — её кладёт провижининг сразу после создания. */
    public static function defaultIndex(): string
    {
        return <<<'PHP'
<?php
// Стартовая страница сайта. Замените её своим кодом через файловый менеджер панели.
echo "Сайт успешно создан и работает";

PHP;
    }

    private static function phpSite(): string
    {
        return <<<'PHP'
<?php

$host = $_SERVER['HTTP_HOST'] ?? 'сайт';

?><!doctype html>
<html lang="ru">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= htmlspecialchars($host, ENT_QUOTES) ?></title>
<body style="font:16px/1.6 system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem">
  <h1>Сайт работает</h1>
  <p>Это <code>public/index.php</code>. Отредактируйте его в панели — изменения видны сразу.</p>
  <p>Время на сервере: <?= date('H:i:s') ?></p>
</body>
</html>

PHP;
    }

    /**
     * Шаблон Telegram-webhook.
     *
     * Секрет читается из .env НАД public/ — токен и секрет никогда не лежат в
     * файле, который отдаёт веб-сервер. Проверка заголовка обязательна: без неё
     * webhook примет запрос от кого угодно, кто узнал адрес.
     */
    private static function telegramWebhook(): string
    {
        return <<<'PHP'
<?php

// ── Настройки берём из .env, который лежит НАД public/ и недоступен из браузера ──
$env = [];
$envFile = dirname(__DIR__) . '/.env';
if (is_file($envFile)) {
    foreach (file($envFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        if ($line === '' || $line[0] === '#' || !str_contains($line, '=')) {
            continue;
        }
        [$key, $value] = explode('=', $line, 2);
        $env[trim($key)] = trim($value, " \t\"'");
    }
}

$secret = $env['TELEGRAM_WEBHOOK_SECRET'] ?? '';
$received = $_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? '';

// hash_equals, а не ==: сравнение за постоянное время не даёт подобрать секрет по таймингу.
if ($secret === '' || !hash_equals($secret, $received)) {
    http_response_code(403);
    exit('Forbidden');
}

$input = file_get_contents('php://input');
if ($input === false || $input === '') {
    http_response_code(400);
    exit('Bad Request');
}

$update = json_decode($input, true);
if (!is_array($update)) {
    http_response_code(400);
    exit('Invalid JSON');
}

// ── Ваша логика ──────────────────────────────────────────────────────────────
// Пример: ответить «Привет» на любое сообщение.
//
// $token  = $env['TELEGRAM_BOT_TOKEN'] ?? '';
// $chatId = $update['message']['chat']['id'] ?? null;
// if ($token !== '' && $chatId !== null) {
//     file_get_contents('https://api.telegram.org/bot' . $token . '/sendMessage?' . http_build_query([
//         'chat_id' => $chatId,
//         'text'    => 'Привет!',
//     ]));
// }

// Telegram повторяет запрос, пока не получит 200 — отвечаем сразу.
http_response_code(200);
echo 'OK';

PHP;
    }

    private static function jsonApi(): string
    {
        return <<<'PHP'
<?php

header('Content-Type: application/json; charset=utf-8');

$response = [
    'ok'   => true,
    'time' => date('c'),
    'path' => $_SERVER['REQUEST_URI'] ?? '/',
];

echo json_encode($response, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);

PHP;
    }

    private static function landing(): string
    {
        return <<<'HTML'
<!doctype html>
<html lang="ru">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Новый сайт</title>
<body style="font:16px/1.6 system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem">
  <h1>Здравствуйте!</h1>
  <p>Это статическая страница. Отредактируйте <code>public/index.html</code> в панели.</p>
</body>
</html>

HTML;
    }
}
