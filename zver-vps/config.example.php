<?php
/**
 * ZVER TAJ — шаблон конфигурации
 * Скопируйте в config.php и заполните своими значениями:
 *   cp config.example.php config.php
 */

return [

    // ---------- Telegram ----------
    'bot_token' => 'ТОКЕН_ОТ_BOTFATHER',
    'admins'    => [123456789],          // ваши Telegram ID

    // ---------- База данных ----------
    'db_host'   => 'localhost',
    'db_name'   => 'zver',
    'db_user'   => 'zver',
    'db_pass'   => 'ПАРОЛЬ_БД',

    // ---------- Секрет для служебных ссылок ----------
    'secret'    => 'ПРИДУМАЙТЕ_ДЛИННЫЙ_СЕКРЕТ',

    // ---------- FazerCards ----------
    'fz_key'    => 'fc_...',
    'fz_hook'   => 'whsec_...',
    'fz_base'   => 'https://api.fzr.cards/api/v2',

    // ---------- gameskinbo (ники Free Fire) ----------
    'gs_key'    => '',

    // ---------- FlashTopup (опционально) ----------
    'ft_id'     => '',
    'ft_key'    => '',
    'ft_base'   => 'https://api.flashtopup.com/api/reseller/v2',
    'ft_path'   => '/api/reseller/v2',

    'debug'     => false,
];
