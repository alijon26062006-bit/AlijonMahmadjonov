<?php
/**
 * Active application configuration.
 *
 * On a real host you would keep this out of version control. It is provided
 * here with placeholder values so the project is runnable out of the box.
 * Environment variables (if present) always override the placeholders, which
 * lets you configure the app without editing this file.
 */

$env = static function (string $key, $default = null) {
    $val = getenv($key);
    return ($val === false || $val === '') ? $default : $val;
};

return [
    'db' => [
        'host'    => $env('DB_HOST', '127.0.0.1'),
        'port'    => (int) $env('DB_PORT', 3306),
        'name'    => $env('DB_NAME', 'cinema'),
        'user'    => $env('DB_USER', 'root'),
        'pass'    => $env('DB_PASS', ''),
        'charset' => 'utf8mb4',
    ],

    'telegram' => [
        'bot_token'      => $env('BOT_TOKEN', 'PUT_YOUR_BOT_TOKEN_HERE'),
        'miniapp_url'    => $env('MINIAPP_URL', 'https://example.com/project/miniapp/'),
        'webhook_url'    => $env('WEBHOOK_URL', 'https://example.com/project/bot/webhook.php'),
        'webhook_secret' => $env('WEBHOOK_SECRET', 'change_me_random_secret'),
        'admin_ids'      => array_filter(array_map(
            'intval',
            explode(',', (string) $env('ADMIN_IDS', '123456789'))
        )),
    ],

    'app' => [
        'name'        => $env('APP_NAME', 'CineWave'),
        'base_url'    => $env('BASE_URL', 'https://example.com/project'),
        'uploads_url' => $env('UPLOADS_URL', 'https://example.com/project/uploads'),
        'uploads_dir' => __DIR__ . '/../uploads',
        'debug'       => filter_var($env('APP_DEBUG', 'false'), FILTER_VALIDATE_BOOL),
        'auth_ttl'    => (int) $env('AUTH_TTL', 86400),
    ],

    // ---- OpenAI (server-side only — never sent to JS / Mini App) ----
    'openai' => [
        'api_key'      => $env('OPENAI_API_KEY', 'PUT_YOUR_OPENAI_KEY_HERE'),
        'endpoint'     => $env('OPENAI_ENDPOINT', 'https://api.openai.com/v1'),
        'model_vision' => $env('OPENAI_MODEL_VISION', 'gpt-4o-mini'),
        'model_text'   => $env('OPENAI_MODEL_TEXT', 'gpt-4o-mini'),
        'timeout'      => (int) $env('OPENAI_TIMEOUT', 45),
    ],
];
