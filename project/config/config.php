<?php
/**
 * Active application configuration.
 *
 * ─────────────────────────────────────────────────────────────────────────
 *  ЧТО НУЖНО ОТРЕДАКТИРОВАТЬ (только этот блок «НАСТРОЙКИ АДМИНА» ниже):
 *    1) доступ к базе данных MySQL   (DB_*)
 *    2) токен бота от @BotFather      (BOT_TOKEN)
 *    3) ваш Telegram ID               (ADMIN_IDS)
 *    4) секрет вебхука — любая строка  (WEBHOOK_SECRET)
 *    5) (по желанию) ключ OpenAI       (OPENAI_API_KEY)
 *
 *  Адреса сайта (miniapp_url, webhook_url, uploads_url, base_url) определяются
 *  АВТОМАТИЧЕСКИ по домену, с которого открыт сайт. Ничего вписывать не нужно.
 *  При желании их можно переопределить через переменные окружения.
 * ─────────────────────────────────────────────────────────────────────────
 */

/* =========================  НАСТРОЙКИ АДМИНА  ========================= */

$DB_HOST = 'localhost';          // обычно localhost
$DB_PORT = 3306;
$DB_NAME = 'cinema';             // имя вашей базы данных
$DB_USER = 'root';              // пользователь MySQL
$DB_PASS = '';                  // пароль MySQL

$BOT_TOKEN      = 'PUT_YOUR_BOT_TOKEN_HERE';   // токен от @BotFather
$BOT_USERNAME   = '';                          // юзернейм бота БЕЗ @, напр. KinoMixPoiskBot
$ADMIN_IDS      = '123456789';                 // ваш Telegram ID (через запятую можно несколько)
$WEBHOOK_SECRET = 'change_me_random_secret';   // любая случайная строка

// Закрытый канал-архив: сюда бот публикует фильмы с кнопкой «Смотреть в боте».
// ID канала вида -1001234567890 (можно узнать: /admin -> 📡 Канал-архив).
$ARCHIVE_CHANNEL_ID = '';

$OPENAI_API_KEY = 'PUT_YOUR_OPENAI_KEY_HERE';  // ключ OpenAI (можно оставить пустым)

$APP_NAME = 'CineWave';         // название приложения

/* ==================  ДАЛЬШЕ МЕНЯТЬ НИЧЕГО НЕ НУЖНО  ================== */

$env = static function (string $key, $default = null) {
    $val = getenv($key);
    return ($val === false || $val === '') ? $default : $val;
};

/**
 * Auto-detect the public base URL of the project from the current request, so
 * it works on any host / any subfolder without manual configuration.
 * Falls back to a placeholder in CLI context (e.g. `php bot/set_webhook.php`),
 * where you should instead open set_webhook.php in a browser.
 */
$autoBase = static function (): string {
    $host = $_SERVER['HTTP_HOST'] ?? '';
    if ($host === '') {
        return '';
    }
    $https = (!empty($_SERVER['HTTPS']) && strtolower((string) $_SERVER['HTTPS']) !== 'off')
        || (int) ($_SERVER['SERVER_PORT'] ?? 0) === 443
        || strtolower((string) ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '')) === 'https';
    $scheme = $https ? 'https' : 'http';

    // Every entry point (api/, bot/, miniapp/) lives one level below the
    // project root, so the root path is dirname(dirname(SCRIPT_NAME)).
    $script = str_replace('\\', '/', (string) ($_SERVER['SCRIPT_NAME'] ?? ''));
    $root   = rtrim(dirname(dirname($script)), '/');
    if ($root === '.' || $root === '/') {
        $root = '';
    }
    return $scheme . '://' . $host . $root;
};

$base = $env('BASE_URL', $autoBase() ?: 'https://example.com/project');

return [
    'db' => [
        'host'    => $env('DB_HOST', $DB_HOST),
        'port'    => (int) $env('DB_PORT', $DB_PORT),
        'name'    => $env('DB_NAME', $DB_NAME),
        'user'    => $env('DB_USER', $DB_USER),
        'pass'    => $env('DB_PASS', $DB_PASS),
        'charset' => 'utf8mb4',
    ],

    'telegram' => [
        'bot_token'      => $env('BOT_TOKEN', $BOT_TOKEN),
        'bot_username'   => ltrim((string) $env('BOT_USERNAME', $BOT_USERNAME), '@'),
        'miniapp_url'    => $env('MINIAPP_URL', $base . '/miniapp/'),
        'webhook_url'    => $env('WEBHOOK_URL', $base . '/bot/webhook.php'),
        'webhook_secret' => $env('WEBHOOK_SECRET', $WEBHOOK_SECRET),
        'archive_channel_id' => (string) $env('ARCHIVE_CHANNEL_ID', $ARCHIVE_CHANNEL_ID),
        'admin_ids'      => array_filter(array_map(
            'intval',
            explode(',', (string) $env('ADMIN_IDS', $ADMIN_IDS))
        )),
    ],

    'app' => [
        'name'        => $env('APP_NAME', $APP_NAME),
        'base_url'    => $base,
        'uploads_url' => $env('UPLOADS_URL', $base . '/uploads'),
        'uploads_dir' => __DIR__ . '/../uploads',
        'debug'       => filter_var($env('APP_DEBUG', 'false'), FILTER_VALIDATE_BOOL),
        'auth_ttl'    => (int) $env('AUTH_TTL', 86400),
    ],

    // ---- OpenAI (server-side only — never sent to JS / Mini App) ----
    'openai' => [
        'api_key'      => $env('OPENAI_API_KEY', $OPENAI_API_KEY),
        'endpoint'     => $env('OPENAI_ENDPOINT', 'https://api.openai.com/v1'),
        'model_vision' => $env('OPENAI_MODEL_VISION', 'gpt-4o-mini'),
        'model_text'   => $env('OPENAI_MODEL_TEXT', 'gpt-4o-mini'),
        'timeout'      => (int) $env('OPENAI_TIMEOUT', 45),
    ],
];
