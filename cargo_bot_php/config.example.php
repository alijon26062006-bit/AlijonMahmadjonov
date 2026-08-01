<?php
/**
 * Настройки бота. Скопируйте этот файл в config.php и заполните.
 * config.php не должен попадать в git (он в .gitignore).
 */
return [
    // Токен от @BotFather
    'bot_token' => 'ВСТАВЬТЕ_ТОКЕН',

    // Telegram ID администраторов (узнать: @userinfobot)
    'admin_ids' => [123456789],

    // Секретное слово для защиты webhook (любая строка A-Z, a-z, 0-9, _, -).
    // Telegram будет присылать его в заголовке, чужие запросы отсекаются.
    'webhook_secret' => 'change_me_please',

    // База данных.
    // MySQL (обычный вариант на хостинге):
    'db' => [
        'dsn'  => 'mysql:host=localhost;dbname=cargo;charset=utf8mb4',
        'user' => 'cargo_user',
        'pass' => 'пароль_базы',
    ],
    // SQLite (если MySQL нет — файл создастся сам):
    // 'db' => ['dsn' => 'sqlite:' . __DIR__ . '/data/cargo.sqlite', 'user' => null, 'pass' => null],

    'timezone' => 'Asia/Dushanbe',

    // Писать ошибки в файл (полезно при отладке)
    'log_file' => __DIR__ . '/data/bot.log',
];
