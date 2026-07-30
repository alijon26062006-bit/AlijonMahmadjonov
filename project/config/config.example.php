<?php
/**
 * Application configuration — example file.
 *
 * Copy this file to `config.php` and fill in real values.
 * `config.php` must NOT be committed to version control.
 */

return [
    // ---- Database (MySQL 8 / PDO) ----
    'db' => [
        'host'    => '127.0.0.1',
        'port'    => 3306,
        'name'    => 'cinema',
        'user'    => 'cinema_user',
        'pass'    => 'change_me',
        'charset' => 'utf8mb4',
    ],

    // ---- Telegram ----
    'telegram' => [
        // BotFather token, e.g. 123456:AAH...
        'bot_token'   => 'PUT_YOUR_BOT_TOKEN_HERE',
        // Public https URL to the mini app entry point
        'miniapp_url' => 'https://example.com/project/miniapp/',
        // Public https URL to the bot webhook entry point
        'webhook_url' => 'https://example.com/project/bot/webhook.php',
        // Secret token echoed back by Telegram in X-Telegram-Bot-Api-Secret-Token
        'webhook_secret' => 'change_me_random_secret',
        // Numeric Telegram user IDs that are allowed to manage content
        'admin_ids'   => [123456789],
    ],

    // ---- Application ----
    'app' => [
        'name'        => 'CineWave',
        'base_url'    => 'https://example.com/project',
        'uploads_url' => 'https://example.com/project/uploads',
        'uploads_dir' => __DIR__ . '/../uploads',
        'debug'       => false,
        // How long (seconds) a Telegram initData signature stays valid
        'auth_ttl'    => 86400,
    ],
];
