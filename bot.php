<?php
declare(strict_types=1);

/*
 * ================================================================
 *  Telegram-бот для скачивания видео из Instagram и TikTok
 *  без водяных знаков.
 *
 *  Один файл, без Composer / ffmpeg / exec / Redis.
 *  Работает через webhook. Требует: PHP 8.1+, MySQL, расширения
 *  curl, pdo_mysql, mbstring, json.
 *
 *  Режимы работы (определяются автоматически по запросу):
 *   - POST + заголовок X-Telegram-Bot-Api-Secret-Token -> webhook
 *   - GET ?cron=SECRET                                  -> cron (раз в минуту)
 *   - GET ?admin=1                                       -> админ-панель
 *   - GET ?setup=SECRET                                  -> установка (один раз)
 * ================================================================
 */

error_reporting(E_ALL);
ini_set('display_errors', '0');
date_default_timezone_set('Asia/Dushanbe');

/* ============================ КОНСТАНТЫ ============================ */
/* Заполните перед загрузкой на хостинг. Больше НИЧЕГО менять не нужно. */

define('BOT_TOKEN', '8530264507:AAG4UorWpm3GdBQTxMuhpeb0-aZmFAOTco0'); // токен от @BotFather
define('BOT_USERNAME', 'instasave26bot');                      // username бота без @

define('DB_HOST', 'localhost');
define('DB_NAME', 'u59_65ca5928');
define('DB_USER', 'u59_551cfd');
define('DB_PASS', '95eea88824de221ced5d');
define('DB_CHARSET', 'utf8mb4');

define('WEBHOOK_SECRET', 'a64ff491e116c872afa396e32e225add3784ee59375d7216'); // проверяется в заголовке Telegram
define('CRON_SECRET', '2dee9518cb1c92df129ad80c05364d84a20bb314adebd714');    // ?cron=...
define('SETUP_SECRET', '5105305027dd905ba5bf31c5ae27a5ed1c3c30ec7f41c94b');   // ?setup=...

define('ADMIN_LOGIN', 'admin');
define('ADMIN_PASSWORD_HASH', '$2y$12$wy4wuf9YBPGgbpHD7dhig.oEm3VMZDKtYH5kg0ZBGrl1LCXZ7zlHi'); // пароль: WvwJY2BcGPH7Fn (смените после первого входа)
define('ADMIN_TG_ID', 7664430907);                             // ваш Telegram ID (для алертов об ошибках)

define('MAX_FILE_MB', 50);
define('FLOOD_SECONDS', 5);
define('DEFAULT_DAILY_LIMIT', 10);
define('REF_BONUS', 3);
define('SUB_CHECK_CACHE_MINUTES', 10);

define('RAPIDAPI_KEY', 'PASTE_YOUR_RAPIDAPI_KEY_HERE');       // TODO: ключ RapidAPI для Instagram-провайдеров (rapidapi.com)
define('SCHEMA_VERSION', 1);

define('SELF_URL', 'https://codetj.somonhost.com/test/bot/bot.php'); // полный URL до этого файла на вашем хостинге

/* ============================ ИСКЛЮЧЕНИЯ ============================ */

class TelegramApiException extends RuntimeException
{
    public int $errorCode = 0;
    public int $retryAfter = 0;
}

/* ============================== РОУТЕР =============================== */

set_error_handler('app_error_handler');
set_exception_handler('app_exception_handler');
register_shutdown_function('app_shutdown_handler');

route_request();
exit;

function route_request(): void
{
    $secretHeader = $_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? '';

    if ($_SERVER['REQUEST_METHOD'] === 'POST' && $secretHeader !== '' && hash_equals(WEBHOOK_SECRET, (string)$secretHeader)) {
        run_webhook();
        return;
    }

    if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['cron']) && hash_equals(CRON_SECRET, (string)$_GET['cron'])) {
        run_cron();
        return;
    }

    if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['setup']) && hash_equals(SETUP_SECRET, (string)$_GET['setup'])) {
        run_setup();
        return;
    }

    if (isset($_GET['admin'])) {
        run_admin();
        return;
    }

    http_response_code(404);
    echo '404 Not Found';
}

/* ======================= ГЛОБАЛЬНАЯ ОБРАБОТКА ОШИБОК ======================= */

function app_error_handler(int $errno, string $errstr, string $errfile, int $errline): bool
{
    if (!(error_reporting() & $errno)) {
        return true;
    }
    $msg = sprintf('[%d] %s in %s:%d', $errno, $errstr, $errfile, $errline);
    safe_log_error('php_error', $msg);
    return true;
}

function app_exception_handler(Throwable $e): void
{
    $msg = sprintf('%s: %s in %s:%d', get_class($e), $e->getMessage(), $e->getFile(), $e->getLine());
    safe_log_error('exception', $msg, $e->getTraceAsString());
    if (!headers_sent()) {
        http_response_code(200);
    }
    echo 'OK';
}

function app_shutdown_handler(): void
{
    $err = error_get_last();
    if ($err !== null && in_array($err['type'], [E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR], true)) {
        $msg = sprintf('[FATAL %d] %s in %s:%d', $err['type'], $err['message'], $err['file'], $err['line']);
        safe_log_error('fatal', $msg);
    }
}

function safe_log_error(string $level, string $message, ?string $context = null): void
{
    try {
        log_error($level, $message, $context);
    } catch (Throwable $e) {
        error_log($message);
    }
}

/* ============================ ЯДРО: БАЗА ДАННЫХ ============================ */

function db(): PDO
{
    static $pdo = null;
    if ($pdo === null) {
        $dsn = 'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=' . DB_CHARSET;
        $pdo = new PDO($dsn, DB_USER, DB_PASS, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
        ]);
    }
    return $pdo;
}

function migrate(): void
{
    $pdo = db();

    $pdo->exec("CREATE TABLE IF NOT EXISTS dl_meta (
        meta_key VARCHAR(64) NOT NULL PRIMARY KEY,
        meta_value VARCHAR(255) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS dl_users (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        tg_id BIGINT NOT NULL,
        username VARCHAR(255) NULL,
        first_name VARCHAR(255) NULL,
        lang VARCHAR(5) NOT NULL DEFAULT 'ru',
        is_banned TINYINT(1) NOT NULL DEFAULT 0,
        is_admin TINYINT(1) NOT NULL DEFAULT 0,
        ref_by BIGINT NULL,
        bonus_downloads INT NOT NULL DEFAULT 0,
        downloads_today INT NOT NULL DEFAULT 0,
        last_download_at DATETIME NULL,
        last_download_date DATE NULL,
        sub_checked_at DATETIME NULL,
        sub_ok TINYINT(1) NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        UNIQUE KEY uniq_tg_id (tg_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS dl_downloads (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        tg_id BIGINT NOT NULL,
        url TEXT NOT NULL,
        url_hash CHAR(40) NOT NULL,
        platform VARCHAR(20) NOT NULL,
        status VARCHAR(20) NOT NULL,
        created_at DATETIME NOT NULL,
        KEY idx_url_hash (url_hash),
        KEY idx_tg_id (tg_id),
        KEY idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS dl_cache (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        url_hash CHAR(40) NOT NULL,
        platform VARCHAR(20) NOT NULL,
        media_type VARCHAR(20) NOT NULL,
        file_id VARCHAR(255) NULL,
        payload MEDIUMTEXT NULL,
        created_at DATETIME NOT NULL,
        UNIQUE KEY uniq_url_hash (url_hash),
        KEY idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS dl_queue (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        tg_id BIGINT NOT NULL,
        chat_id BIGINT NOT NULL,
        message_id BIGINT NULL,
        url TEXT NOT NULL,
        platform VARCHAR(20) NOT NULL,
        lang VARCHAR(5) NOT NULL DEFAULT 'ru',
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        attempts INT UNSIGNED NOT NULL DEFAULT 0,
        error TEXT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        KEY idx_status (status),
        KEY idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS dl_settings (
        skey VARCHAR(64) NOT NULL PRIMARY KEY,
        svalue TEXT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS dl_channels (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        username VARCHAR(255) NULL,
        title VARCHAR(255) NULL,
        url VARCHAR(255) NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS dl_logs (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        level VARCHAR(20) NOT NULL,
        message TEXT NOT NULL,
        context MEDIUMTEXT NULL,
        created_at DATETIME NOT NULL,
        KEY idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $verStmt = $pdo->prepare("SELECT meta_value FROM dl_meta WHERE meta_key = 'schema_version'");
    $verStmt->execute();
    $ver = $verStmt->fetchColumn();
    if ($ver === false) {
        $ins = $pdo->prepare("INSERT INTO dl_meta (meta_key, meta_value) VALUES ('schema_version', :v)");
        $ins->execute([':v' => (string)SCHEMA_VERSION]);
    }

    $defaults = [
        'daily_limit' => (string)DEFAULT_DAILY_LIMIT,
        'ref_bonus' => (string)REF_BONUS,
        'flood_seconds' => (string)FLOOD_SECONDS,
        'require_subscription' => '0',
        'broadcast_active' => '0',
        'broadcast_offset' => '0',
        'broadcast_text' => '',
        'last_update_id' => '0',
    ];
    foreach ($defaults as $k => $v) {
        $stmt = $pdo->prepare("INSERT IGNORE INTO dl_settings (skey, svalue) VALUES (:k, :v)");
        $stmt->execute([':k' => $k, ':v' => $v]);
    }
}

/* ============================ ЛОГИ И УВЕДОМЛЕНИЯ ============================ */

function log_error(string $level, string $message, ?string $context = null): void
{
    $stmt = db()->prepare("INSERT INTO dl_logs (level, message, context, created_at) VALUES (:l, :m, :c, :d)");
    $stmt->execute([':l' => $level, ':m' => mb_substr($message, 0, 60000), ':c' => $context, ':d' => now()]);
    if (in_array($level, ['exception', 'fatal', 'php_error'], true) && ADMIN_TG_ID > 0) {
        notify_admin("⚠️ Ошибка [{$level}]:\n" . mb_substr($message, 0, 3000));
    }
}

function notify_admin(string $text): void
{
    try {
        tg_api('sendMessage', ['chat_id' => ADMIN_TG_ID, 'text' => $text]);
    } catch (Throwable $e) {
        error_log('notify_admin failed: ' . $e->getMessage());
    }
}

function now(): string
{
    return date('Y-m-d H:i:s');
}

function h(?string $s): string
{
    return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
}

/* ============================ TELEGRAM API ============================ */

function tg_api(string $method, array $params = [], bool $multipart = false)
{
    $params = array_filter($params, static fn ($v) => $v !== null);
    $url = 'https://api.telegram.org/bot' . BOT_TOKEN . '/' . $method;
    $ch = curl_init($url);
    $opts = [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_TIMEOUT => 25,
        CURLOPT_CONNECTTIMEOUT => 10,
        CURLOPT_SSL_VERIFYPEER => true,
    ];
    if ($multipart) {
        $opts[CURLOPT_POSTFIELDS] = $params;
    } else {
        $opts[CURLOPT_POSTFIELDS] = http_build_query($params);
        $opts[CURLOPT_HTTPHEADER] = ['Content-Type: application/x-www-form-urlencoded'];
    }
    curl_setopt_array($ch, $opts);
    $response = curl_exec($ch);
    $curlErrno = curl_errno($ch);
    $curlErr = curl_error($ch);
    curl_close($ch);

    if ($response === false) {
        throw new RuntimeException('Telegram cURL error (' . $method . '): ' . $curlErr, $curlErrno);
    }

    $data = json_decode((string)$response, true);
    if (!is_array($data) || empty($data['ok'])) {
        $ex = new TelegramApiException('Telegram API error (' . $method . '): ' . ($data['description'] ?? 'invalid response'));
        $ex->errorCode = (int)($data['error_code'] ?? 0);
        $ex->retryAfter = (int)($data['parameters']['retry_after'] ?? 0);
        throw $ex;
    }
    return $data['result'];
}

function tg_send_message(int|string $chatId, string $text, array $opts = [])
{
    $params = array_merge([
        'chat_id' => $chatId,
        'text' => $text,
        'parse_mode' => 'HTML',
        'disable_web_page_preview' => true,
    ], $opts);
    return tg_api('sendMessage', $params);
}

function tg_send_video(int|string $chatId, string $videoUrlOrFileId, array $opts = [])
{
    $params = array_merge([
        'chat_id' => $chatId,
        'video' => $videoUrlOrFileId,
        'supports_streaming' => true,
    ], $opts);
    return tg_api('sendVideo', $params);
}

function tg_send_media_group(int|string $chatId, array $items, array $opts = [])
{
    $params = array_merge([
        'chat_id' => $chatId,
        'media' => json_encode($items, JSON_UNESCAPED_UNICODE),
    ], $opts);
    return tg_api('sendMediaGroup', $params);
}

function tg_answer_callback(string $callbackId, string $text = '', bool $showAlert = false)
{
    return tg_api('answerCallbackQuery', [
        'callback_query_id' => $callbackId,
        'text' => $text,
        'show_alert' => $showAlert,
    ]);
}

function tg_get_chat_member(int|string $chatId, int $userId): ?array
{
    try {
        return tg_api('getChatMember', ['chat_id' => $chatId, 'user_id' => $userId]);
    } catch (TelegramApiException $e) {
        return null;
    }
}

function tg_set_webhook(): array
{
    return tg_api('setWebhook', [
        'url' => SELF_URL,
        'secret_token' => WEBHOOK_SECRET,
        'allowed_updates' => json_encode(['message', 'callback_query']),
        'drop_pending_updates' => false,
    ]);
}

function tg_delete_webhook(): array
{
    return tg_api('deleteWebhook', []);
}

/* ============================ НАСТРОЙКИ (dl_settings) ============================ */

function get_setting(string $key, ?string $default = null): ?string
{
    $stmt = db()->prepare("SELECT svalue FROM dl_settings WHERE skey = :k");
    $stmt->execute([':k' => $key]);
    $v = $stmt->fetchColumn();
    return $v === false ? $default : (string)$v;
}

function set_setting(string $key, string $value): void
{
    $stmt = db()->prepare("INSERT INTO dl_settings (skey, svalue) VALUES (:k, :v) ON DUPLICATE KEY UPDATE svalue = :v2");
    $stmt->execute([':k' => $key, ':v' => $value, ':v2' => $value]);
}

/* ============================ ЯЗЫКИ ============================ */

function lang_all(): array
{
    static $L = null;
    if ($L !== null) {
        return $L;
    }
    $L = [
        'ru' => [
            'start_greeting' => "👋 Привет, {name}!\nОтправь мне ссылку на видео из Instagram (Reels, пост, IGTV) или TikTok — я скачаю его без водяного знака.",
            'choose_lang' => 'Выберите язык:',
            'lang_set' => '✅ Язык установлен: Русский',
            'need_subscription' => "📢 Чтобы пользоваться ботом, подпишись на наши каналы, затем нажми «Я подписался».",
            'btn_check_sub' => '✅ Я подписался',
            'sub_ok' => '✅ Спасибо! Теперь можешь пользоваться ботом.',
            'sub_still_missing' => '❌ Вы подписались не на все каналы. Проверьте и попробуйте снова.',
            'send_link' => '🔗 Пришли ссылку на видео из Instagram или TikTok.',
            'invalid_link' => '❌ Не удалось распознать ссылку. Поддерживаются Instagram и TikTok.',
            'flood_wait' => '⏱ Подожди {sec} сек. перед следующей ссылкой.',
            'limit_reached' => "🚫 Ты исчерпал дневной лимит загрузок ({limit}).\nПригласи друга по своей ссылке, чтобы получить +{bonus} загрузок:\n{ref_link}",
            'banned' => '🚫 Ты заблокирован в этом боте.',
            'download_error' => '❌ Не удалось скачать видео. Попробуйте позже или проверьте ссылку.',
            'file_too_big' => "📦 Файл больше {mb} МБ, я не могу отправить его напрямую.\nСкачайте по прямой ссылке:",
            'btn_direct_link' => '⬇️ Прямая ссылка',
            'queued' => '⏳ Ссылка поставлена в очередь на обработку...',
            'ref_info' => "👥 Твоя реферальная ссылка:\n{ref_link}\n\nПриглашено друзей: {count}\nБонусных загрузок: {bonus}",
        ],
        'tj' => [
            'start_greeting' => "👋 Салом, {name}!\nПайванди видеоро аз Instagram (Reels, пост, IGTV) ё TikTok фирист — ман бе нишони об онро мекашам.",
            'choose_lang' => 'Забонро интихоб кунед:',
            'lang_set' => '✅ Забон танзим шуд: Тоҷикӣ',
            'need_subscription' => '📢 Барои истифодаи бот ба каналҳои мо обуна шавед, сипас "Ман обуна шудам"-ро пахш кунед.',
            'btn_check_sub' => '✅ Ман обуна шудам',
            'sub_ok' => '✅ Ташаккур! Акнун метавонед аз бот истифода баред.',
            'sub_still_missing' => '❌ Шумо ба ҳамаи каналҳо обуна нашудаед. Санҷед ва бори дигар кӯшиш кунед.',
            'send_link' => '🔗 Пайванди видеоро аз Instagram ё TikTok фиристед.',
            'invalid_link' => '❌ Пайванд шинохта нашуд. Instagram ва TikTok дастгирӣ мешаванд.',
            'flood_wait' => '⏱ {sec} сония пеш аз пайванди навбатӣ интизор шавед.',
            'limit_reached' => "🚫 Лимити рӯзонаи шумо тамом шуд ({limit}).\nДӯстро тавассути пайванди худ даъват кунед, то +{bonus} боргирӣ гиред:\n{ref_link}",
            'banned' => '🚫 Шумо дар ин бот баста шудаед.',
            'download_error' => '❌ Видео боргирӣ нашуд. Дертар кӯшиш кунед ё пайвандро санҷед.',
            'file_too_big' => "📦 Файл аз {mb} МБ калонтар аст, наметавонам мустақим фиристам.\nБо пайванди мустақим боргирӣ кунед:",
            'btn_direct_link' => '⬇️ Пайванди мустақим',
            'queued' => '⏳ Пайванд ба навбат гузошта шуд...',
            'ref_info' => "👥 Пайванди реферали шумо:\n{ref_link}\n\nДӯстони даъватшуда: {count}\nБоргирии бонусӣ: {bonus}",
        ],
        'uz' => [
            'start_greeting' => "👋 Salom, {name}!\nInstagram (Reels, post, IGTV) yoki TikTok'dan video havolasini yuboring — men uni suv belgisiz yuklab beraman.",
            'choose_lang' => 'Tilni tanlang:',
            'lang_set' => "✅ Til o'rnatildi: O'zbekcha",
            'need_subscription' => "📢 Botdan foydalanish uchun kanallarimizga obuna bo'ling, so'ng «Men obuna bo'ldim» tugmasini bosing.",
            'btn_check_sub' => "✅ Men obuna bo'ldim",
            'sub_ok' => "✅ Rahmat! Endi botdan foydalanishingiz mumkin.",
            'sub_still_missing' => "❌ Siz barcha kanallarga obuna bo'lmagansiz. Tekshirib qayta urinib ko'ring.",
            'send_link' => "🔗 Instagram yoki TikTok'dan video havolasini yuboring.",
            'invalid_link' => "❌ Havola aniqlanmadi. Instagram va TikTok qo'llab-quvvatlanadi.",
            'flood_wait' => "⏱ Keyingi havoladan oldin {sec} soniya kuting.",
            'limit_reached' => "🚫 Kunlik yuklab olish limitingiz tugadi ({limit}).\nDo'stingizni taklif qilib +{bonus} yuklab olish oling:\n{ref_link}",
            'banned' => '🚫 Siz botda bloklangansiz.',
            'download_error' => "❌ Videoni yuklab bo'lmadi. Keyinroq urinib ko'ring yoki havolani tekshiring.",
            'file_too_big' => "📦 Fayl {mb} MB dan katta, to'g'ridan-to'g'ri yubora olmayman.\nTo'g'ridan-to'g'ri havoladan yuklab oling:",
            'btn_direct_link' => "⬇️ To'g'ridan-to'g'ri havola",
            'queued' => "⏳ Havola navbatga qo'yildi...",
            'ref_info' => "👥 Sizning referal havolangiz:\n{ref_link}\n\nTaklif qilingan do'stlar: {count}\nBonus yuklab olishlar: {bonus}",
        ],
        'en' => [
            'start_greeting' => "👋 Hi, {name}!\nSend me a video link from Instagram (Reels, post, IGTV) or TikTok — I'll download it without a watermark.",
            'choose_lang' => 'Choose your language:',
            'lang_set' => '✅ Language set: English',
            'need_subscription' => '📢 To use the bot, subscribe to our channels, then press "I have subscribed".',
            'btn_check_sub' => '✅ I have subscribed',
            'sub_ok' => "✅ Thanks! You can now use the bot.",
            'sub_still_missing' => "❌ You haven't subscribed to all channels. Check and try again.",
            'send_link' => '🔗 Send a video link from Instagram or TikTok.',
            'invalid_link' => '❌ Could not recognize the link. Instagram and TikTok are supported.',
            'flood_wait' => '⏱ Wait {sec} sec. before the next link.',
            'limit_reached' => "🚫 You've reached the daily download limit ({limit}).\nInvite a friend via your link to get +{bonus} downloads:\n{ref_link}",
            'banned' => '🚫 You are banned in this bot.',
            'download_error' => '❌ Could not download the video. Try again later or check the link.',
            'file_too_big' => "📦 File is bigger than {mb} MB, I can't send it directly.\nDownload via direct link:",
            'btn_direct_link' => '⬇️ Direct link',
            'queued' => '⏳ Link queued for processing...',
            'ref_info' => "👥 Your referral link:\n{ref_link}\n\nInvited friends: {count}\nBonus downloads: {bonus}",
        ],
    ];
    return $L;
}

function t(string $lang, string $key, array $vars = []): string
{
    $L = lang_all();
    $text = $L[$lang][$key] ?? $L['ru'][$key] ?? $key;
    foreach ($vars as $k => $v) {
        $text = str_replace('{' . $k . '}', (string)$v, $text);
    }
    return $text;
}

function normalize_lang(?string $code): string
{
    $code = strtolower(substr((string)$code, 0, 2));
    return in_array($code, ['ru', 'tj', 'uz', 'en'], true) ? $code : 'ru';
}

/* ============================ HTTP-ПОМОЩНИКИ ============================ */

function http_get(string $url, array $headers = [], int $timeout = 8): ?string
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 5,
        CURLOPT_TIMEOUT => $timeout,
        CURLOPT_CONNECTTIMEOUT => 5,
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_USERAGENT => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
        CURLOPT_SSL_VERIFYPEER => true,
    ]);
    $resp = curl_exec($ch);
    curl_close($ch);
    return $resp === false ? null : (string)$resp;
}

function expand_short_url(string $url): string
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 5,
        CURLOPT_NOBODY => true,
        CURLOPT_TIMEOUT => 8,
        CURLOPT_CONNECTTIMEOUT => 5,
        CURLOPT_SSL_VERIFYPEER => true,
        CURLOPT_USERAGENT => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
    ]);
    curl_exec($ch);
    $finalUrl = curl_getinfo($ch, CURLINFO_EFFECTIVE_URL);
    curl_close($ch);
    return $finalUrl ?: $url;
}

function remote_file_size_mb(string $url): ?float
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_NOBODY => true,
        CURLOPT_HEADER => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_TIMEOUT => 8,
        CURLOPT_CONNECTTIMEOUT => 5,
    ]);
    curl_exec($ch);
    $size = curl_getinfo($ch, CURLINFO_CONTENT_LENGTH_DOWNLOAD);
    curl_close($ch);
    if ($size === false || $size <= 0) {
        return null;
    }
    return $size / 1024 / 1024;
}

/* ============================ РАСПОЗНАВАНИЕ ССЫЛОК ============================ */

function extract_links(string $text): array
{
    preg_match_all('~https?://[^\s]+~i', $text, $m);
    return $m[0] ?? [];
}

function detect_platform(string $url): ?string
{
    if (preg_match('~instagram\.com/(reel|reels|p|tv|share)/~i', $url)) {
        return 'instagram';
    }
    if (preg_match('~tiktok\.com/@[\w.\-]+/video/\d+~i', $url)) {
        return 'tiktok';
    }
    if (preg_match('~(vm|vt)\.tiktok\.com/~i', $url)) {
        return 'tiktok';
    }
    if (preg_match('~tiktok\.com/t/~i', $url)) {
        return 'tiktok';
    }
    return null;
}

function normalize_url(string $url): string
{
    $url = trim($url);
    $parts = parse_url($url);
    if ($parts === false || empty($parts['host'])) {
        return $url;
    }
    $host = strtolower($parts['host']);
    $path = rtrim($parts['path'] ?? '', '/');
    return $host . $path;
}

/* ============================ ПРОВАЙДЕРЫ ЗАГРУЗКИ ============================ */
/*
 * resolve_media() — единая точка входа. Перебирает провайдеров по очереди,
 * при ошибке/пустом ответе переходит к следующему.
 * Добавление нового провайдера = одна строка в массиве $providers.
 * Формат результата: ['items' => [['type'=>'video'|'photo','url'=>...], ...], 'caption' => string|null]
 */

function resolve_media(string $url, string $platform): ?array
{
    $providers = [
        'provider_tikwm',
        'provider_rapidapi_ig',
        'provider_rapidapi_universal',
    ];
    foreach ($providers as $providerFn) {
        try {
            $result = $providerFn($url, $platform);
            if ($result !== null && !empty($result['items'])) {
                return $result;
            }
        } catch (Throwable $e) {
            log_error('provider', $providerFn . ' failed: ' . $e->getMessage());
            continue;
        }
    }
    return null;
}

function provider_tikwm(string $url, string $platform): ?array
{
    if ($platform !== 'tiktok') {
        return null;
    }
    $resp = http_get('https://www.tikwm.com/api/?url=' . urlencode($url) . '&hd=1', [], 8);
    if ($resp === null) {
        return null;
    }
    $data = json_decode($resp, true);
    if (!is_array($data) || (int)($data['code'] ?? 1) !== 0 || empty($data['data'])) {
        return null;
    }
    $d = $data['data'];
    $videoUrl = $d['hdplay'] ?? $d['play'] ?? null;
    if (!$videoUrl) {
        return null;
    }
    if (str_starts_with($videoUrl, '/')) {
        $videoUrl = 'https://www.tikwm.com' . $videoUrl;
    }
    return [
        'items' => [['type' => 'video', 'url' => $videoUrl]],
        'caption' => $d['title'] ?? null,
    ];
}

function provider_rapidapi_ig(string $url, string $platform): ?array
{
    if ($platform !== 'instagram') {
        return null;
    }
    if (RAPIDAPI_KEY === '' || RAPIDAPI_KEY === 'PASTE_YOUR_RAPIDAPI_KEY_HERE') {
        return null;
    }
    $host = 'instagram-scraper-api2.p.rapidapi.com';
    $endpoint = 'https://' . $host . '/v1/post_info?code_or_id_or_url=' . urlencode($url);
    $resp = http_get($endpoint, [
        'X-RapidAPI-Key: ' . RAPIDAPI_KEY,
        'X-RapidAPI-Host: ' . $host,
    ], 8);
    if ($resp === null) {
        return null;
    }
    $data = json_decode($resp, true);
    if (!is_array($data) || empty($data['data'])) {
        return null;
    }
    $post = $data['data'];
    $items = [];
    if (!empty($post['carousel_media']) && is_array($post['carousel_media'])) {
        foreach ($post['carousel_media'] as $node) {
            if (!empty($node['video_versions'][0]['url'])) {
                $items[] = ['type' => 'video', 'url' => $node['video_versions'][0]['url']];
            } elseif (!empty($node['image_versions2']['candidates'][0]['url'])) {
                $items[] = ['type' => 'photo', 'url' => $node['image_versions2']['candidates'][0]['url']];
            }
        }
    } elseif (!empty($post['video_versions'][0]['url'])) {
        $items[] = ['type' => 'video', 'url' => $post['video_versions'][0]['url']];
    } elseif (!empty($post['image_versions2']['candidates'][0]['url'])) {
        $items[] = ['type' => 'photo', 'url' => $post['image_versions2']['candidates'][0]['url']];
    }
    if (empty($items)) {
        return null;
    }
    return ['items' => $items, 'caption' => $post['caption']['text'] ?? null];
}

function provider_rapidapi_universal(string $url, string $platform): ?array
{
    if (RAPIDAPI_KEY === '' || RAPIDAPI_KEY === 'PASTE_YOUR_RAPIDAPI_KEY_HERE') {
        return null;
    }
    $host = 'social-media-video-downloader.p.rapidapi.com';
    $endpoint = 'https://' . $host . '/smvd/get/all?url=' . urlencode($url);
    $resp = http_get($endpoint, [
        'X-RapidAPI-Key: ' . RAPIDAPI_KEY,
        'X-RapidAPI-Host: ' . $host,
    ], 8);
    if ($resp === null) {
        return null;
    }
    $data = json_decode($resp, true);
    if (!is_array($data) || empty($data['links']) || !is_array($data['links'])) {
        return null;
    }
    $best = null;
    foreach ($data['links'] as $link) {
        if (($link['quality'] ?? '') === 'hd' || $best === null) {
            $best = $link;
        }
    }
    if (empty($best['link'])) {
        return null;
    }
    return [
        'items' => [['type' => 'video', 'url' => $best['link']]],
        'caption' => $data['title'] ?? null,
    ];
}

/* ============================ КЭШ ЗАГРУЗОК ============================ */

function cache_get(string $hash): ?array
{
    $stmt = db()->prepare("SELECT * FROM dl_cache WHERE url_hash = :h LIMIT 1");
    $stmt->execute([':h' => $hash]);
    $row = $stmt->fetch();
    return $row ?: null;
}

function cache_set(string $hash, string $platform, string $mediaType, ?string $fileId, ?array $payload): void
{
    $json = $payload !== null ? json_encode($payload, JSON_UNESCAPED_UNICODE) : null;
    $stmt = db()->prepare("INSERT INTO dl_cache (url_hash, platform, media_type, file_id, payload, created_at)
        VALUES (:h, :p, :mt, :fid, :pl, :d)
        ON DUPLICATE KEY UPDATE platform = :p2, media_type = :mt2, file_id = :fid2, payload = :pl2, created_at = :d2");
    $stmt->execute([
        ':h' => $hash, ':p' => $platform, ':mt' => $mediaType, ':fid' => $fileId, ':pl' => $json, ':d' => now(),
        ':p2' => $platform, ':mt2' => $mediaType, ':fid2' => $fileId, ':pl2' => $json, ':d2' => now(),
    ]);
}

/* ============================ ПОЛЬЗОВАТЕЛИ ============================ */

function get_or_create_user(array $tgUser, ?int $refBy = null): array
{
    $tgId = (int)$tgUser['id'];
    $stmt = db()->prepare("SELECT * FROM dl_users WHERE tg_id = :id LIMIT 1");
    $stmt->execute([':id' => $tgId]);
    $user = $stmt->fetch();
    if ($user) {
        $upd = db()->prepare("UPDATE dl_users SET username = :u, first_name = :f WHERE tg_id = :id");
        $upd->execute([':u' => $tgUser['username'] ?? null, ':f' => $tgUser['first_name'] ?? null, ':id' => $tgId]);
        return $user;
    }
    $lang = normalize_lang($tgUser['language_code'] ?? 'ru');
    $ins = db()->prepare("INSERT INTO dl_users (tg_id, username, first_name, lang, ref_by, is_admin, created_at)
        VALUES (:id, :u, :f, :lang, :ref, :adm, :d)");
    $ins->execute([
        ':id' => $tgId,
        ':u' => $tgUser['username'] ?? null,
        ':f' => $tgUser['first_name'] ?? null,
        ':lang' => $lang,
        ':ref' => ($refBy !== null && $refBy !== $tgId) ? $refBy : null,
        ':adm' => ($tgId === (int)ADMIN_TG_ID && ADMIN_TG_ID > 0) ? 1 : 0,
        ':d' => now(),
    ]);
    if ($refBy !== null && $refBy !== $tgId) {
        $bonus = (int)get_setting('ref_bonus', (string)REF_BONUS);
        $b = db()->prepare("UPDATE dl_users SET bonus_downloads = bonus_downloads + :b WHERE tg_id = :rid");
        $b->execute([':b' => $bonus, ':rid' => $refBy]);
    }
    $stmt->execute([':id' => $tgId]);
    return $stmt->fetch();
}

function get_user(int $tgId): ?array
{
    $stmt = db()->prepare("SELECT * FROM dl_users WHERE tg_id = :id LIMIT 1");
    $stmt->execute([':id' => $tgId]);
    $row = $stmt->fetch();
    return $row ?: null;
}

function set_user_lang(int $tgId, string $lang): void
{
    $stmt = db()->prepare("UPDATE dl_users SET lang = :l WHERE tg_id = :id");
    $stmt->execute([':l' => $lang, ':id' => $tgId]);
}

function touch_last_attempt(int $tgId): void
{
    $stmt = db()->prepare("UPDATE dl_users SET last_download_at = :dt WHERE tg_id = :id");
    $stmt->execute([':dt' => now(), ':id' => $tgId]);
}

function check_flood(int $tgId): bool
{
    $user = get_user($tgId);
    if (!$user || empty($user['last_download_at'])) {
        return true;
    }
    $floodSec = (int)get_setting('flood_seconds', (string)FLOOD_SECONDS);
    $last = strtotime($user['last_download_at']);
    return (time() - $last) >= $floodSec;
}

function seconds_until_flood_ok(int $tgId): int
{
    $user = get_user($tgId);
    if (!$user || empty($user['last_download_at'])) {
        return 0;
    }
    $floodSec = (int)get_setting('flood_seconds', (string)FLOOD_SECONDS);
    $last = strtotime($user['last_download_at']);
    $left = $floodSec - (time() - $last);
    return max(0, $left);
}

function check_daily_limit(int $tgId): bool
{
    $user = get_user($tgId);
    if (!$user) {
        return false;
    }
    $limit = (int)get_setting('daily_limit', (string)DEFAULT_DAILY_LIMIT) + (int)$user['bonus_downloads'];
    $today = date('Y-m-d');
    $count = ($user['last_download_date'] === $today) ? (int)$user['downloads_today'] : 0;
    return $count < $limit;
}

function increment_download_count(int $tgId): void
{
    $today = date('Y-m-d');
    $user = get_user($tgId);
    $count = ($user && $user['last_download_date'] === $today) ? (int)$user['downloads_today'] + 1 : 1;
    $stmt = db()->prepare("UPDATE dl_users SET downloads_today = :c, last_download_date = :d WHERE tg_id = :id");
    $stmt->execute([':c' => $count, ':d' => $today, ':id' => $tgId]);
}

function log_download(int $tgId, string $url, string $platform, string $status): void
{
    $stmt = db()->prepare("INSERT INTO dl_downloads (tg_id, url, url_hash, platform, status, created_at)
        VALUES (:tg, :url, :h, :pl, :st, :d)");
    $stmt->execute([
        ':tg' => $tgId, ':url' => $url, ':h' => sha1(normalize_url($url)), ':pl' => $platform, ':st' => $status, ':d' => now(),
    ]);
}

/* ============================ ОБЯЗАТЕЛЬНАЯ ПОДПИСКА ============================ */

function get_required_channels(): array
{
    return db()->query("SELECT * FROM dl_channels WHERE is_active = 1 ORDER BY id ASC")->fetchAll();
}

function check_subscription(int $tgId): bool
{
    if (get_setting('require_subscription', '0') !== '1') {
        return true;
    }
    $user = get_user($tgId);
    if ($user && !empty($user['sub_checked_at'])) {
        $checkedAgo = time() - strtotime($user['sub_checked_at']);
        if ($checkedAgo < SUB_CHECK_CACHE_MINUTES * 60 && (int)$user['sub_ok'] === 1) {
            return true;
        }
    }
    $channels = get_required_channels();
    if (empty($channels)) {
        return true;
    }
    $ok = true;
    foreach ($channels as $ch) {
        $member = tg_get_chat_member((int)$ch['chat_id'], $tgId);
        $status = $member['status'] ?? 'left';
        if (!in_array($status, ['member', 'administrator', 'creator'], true)) {
            $ok = false;
            break;
        }
    }
    $stmt = db()->prepare("UPDATE dl_users SET sub_checked_at = :d, sub_ok = :ok WHERE tg_id = :id");
    $stmt->execute([':d' => now(), ':ok' => $ok ? 1 : 0, ':id' => $tgId]);
    return $ok;
}

function build_subscribe_keyboard(string $lang): array
{
    $channels = get_required_channels();
    $rows = [];
    foreach ($channels as $ch) {
        $url = $ch['url'] ?: ('https://t.me/' . ltrim((string)$ch['username'], '@'));
        $rows[] = [['text' => $ch['title'] ?: $ch['username'], 'url' => $url]];
    }
    $rows[] = [['text' => t($lang, 'btn_check_sub'), 'callback_data' => 'check_sub']];
    return ['inline_keyboard' => $rows];
}

/* ============================ ОБРАБОТКА ОБНОВЛЕНИЙ TELEGRAM ============================ */

function run_webhook(): void
{
    migrate();
    $raw = file_get_contents('php://input');
    $update = json_decode((string)$raw, true);

    http_response_code(200);
    echo 'OK';
    if (function_exists('fastcgi_finish_request')) {
        fastcgi_finish_request();
    }

    if (!is_array($update)) {
        return;
    }

    $updateId = (int)($update['update_id'] ?? 0);
    if ($updateId > 0) {
        $last = (int)get_setting('last_update_id', '0');
        if ($updateId <= $last) {
            return;
        }
        set_setting('last_update_id', (string)$updateId);
    }

    try {
        handle_update($update);
    } catch (Throwable $e) {
        log_error('handle_update', $e->getMessage(), $e->getTraceAsString());
    }
}

function handle_update(array $update): void
{
    if (isset($update['message'])) {
        handle_message($update['message']);
    } elseif (isset($update['callback_query'])) {
        handle_callback_query($update['callback_query']);
    }
}

function handle_message(array $message): void
{
    $from = $message['from'] ?? null;
    if (!$from || !empty($from['is_bot'])) {
        return;
    }
    $chat = $message['chat'] ?? [];
    $chatId = (int)($chat['id'] ?? 0);
    $chatType = $chat['type'] ?? 'private';
    $text = (string)($message['text'] ?? $message['caption'] ?? '');
    $messageId = $message['message_id'] ?? null;

    $refBy = null;
    if (str_starts_with($text, '/start') && preg_match('~/start\s+ref_(\d+)~', $text, $m)) {
        $refBy = (int)$m[1];
    }

    $user = get_or_create_user($from, $refBy);
    $tgId = (int)$user['tg_id'];
    $lang = $user['lang'];

    if ((int)$user['is_banned'] === 1) {
        tg_send_message($chatId, t($lang, 'banned'), ['reply_to_message_id' => $messageId]);
        return;
    }

    if (str_starts_with($text, '/start')) {
        handle_command_start($message, $user);
        return;
    }
    if (str_starts_with($text, '/lang')) {
        send_lang_menu($chatId, $lang);
        return;
    }
    if (str_starts_with($text, '/ref') || str_starts_with($text, '/invite')) {
        send_ref_info($chatId, $user);
        return;
    }
    if (str_starts_with($text, '/help')) {
        tg_send_message($chatId, t($lang, 'send_link'));
        return;
    }

    $links = extract_links($text);
    if (empty($links)) {
        if ($chatType === 'private') {
            tg_send_message($chatId, t($lang, 'send_link'));
        }
        return;
    }

    handle_link_message($message, $links[0], $user);
}

function handle_command_start(array $message, array $user): void
{
    $chatId = (int)$message['chat']['id'];
    $lang = $user['lang'];
    $name = $message['from']['first_name'] ?? 'friend';
    tg_send_message($chatId, t($lang, 'start_greeting', ['name' => $name]));
    if (!check_subscription((int)$user['tg_id'])) {
        tg_send_message($chatId, t($lang, 'need_subscription'), ['reply_markup' => json_encode(build_subscribe_keyboard($lang))]);
    }
}

function send_lang_menu(int $chatId, string $lang): void
{
    $kb = [
        'inline_keyboard' => [
            [['text' => '🇷🇺 Русский', 'callback_data' => 'lang_ru'], ['text' => '🇹🇯 Тоҷикӣ', 'callback_data' => 'lang_tj']],
            [['text' => "🇺🇿 O'zbekcha", 'callback_data' => 'lang_uz'], ['text' => '🇬🇧 English', 'callback_data' => 'lang_en']],
        ],
    ];
    tg_send_message($chatId, t($lang, 'choose_lang'), ['reply_markup' => json_encode($kb)]);
}

function send_ref_info(int $chatId, array $user): void
{
    $lang = $user['lang'];
    $refLink = 'https://t.me/' . BOT_USERNAME . '?start=ref_' . $user['tg_id'];
    $stmt = db()->prepare("SELECT COUNT(*) FROM dl_users WHERE ref_by = :id");
    $stmt->execute([':id' => $user['tg_id']]);
    $count = (int)$stmt->fetchColumn();
    tg_send_message($chatId, t($lang, 'ref_info', [
        'ref_link' => $refLink,
        'count' => $count,
        'bonus' => $user['bonus_downloads'],
    ]));
}

function handle_callback_query(array $cb): void
{
    $from = $cb['from'] ?? null;
    if (!$from) {
        return;
    }
    $user = get_or_create_user($from);
    $tgId = (int)$user['tg_id'];
    $lang = $user['lang'];
    $data = (string)($cb['data'] ?? '');
    $chatId = (int)($cb['message']['chat']['id'] ?? $tgId);

    if ($data === 'check_sub') {
        if (check_subscription($tgId)) {
            tg_answer_callback($cb['id'], t($lang, 'sub_ok'));
            tg_send_message($chatId, t($lang, 'sub_ok'));
        } else {
            tg_answer_callback($cb['id'], t($lang, 'sub_still_missing'), true);
        }
        return;
    }

    if (str_starts_with($data, 'lang_')) {
        $newLang = substr($data, 5);
        if (in_array($newLang, ['ru', 'tj', 'uz', 'en'], true)) {
            set_user_lang($tgId, $newLang);
            tg_answer_callback($cb['id']);
            tg_send_message($chatId, t($newLang, 'lang_set'));
        }
        return;
    }

    tg_answer_callback($cb['id']);
}

/* ============================ ОБРАБОТКА ССЫЛОК ============================ */

function handle_link_message(array $message, string $rawUrl, array $user): void
{
    $chatId = (int)$message['chat']['id'];
    $messageId = $message['message_id'] ?? null;
    $tgId = (int)$user['tg_id'];
    $lang = $user['lang'];

    if (!check_flood($tgId)) {
        $sec = seconds_until_flood_ok($tgId);
        tg_send_message($chatId, t($lang, 'flood_wait', ['sec' => $sec]), ['reply_to_message_id' => $messageId]);
        return;
    }

    if (!check_subscription($tgId)) {
        tg_send_message($chatId, t($lang, 'need_subscription'), [
            'reply_markup' => json_encode(build_subscribe_keyboard($lang)),
            'reply_to_message_id' => $messageId,
        ]);
        return;
    }

    if (!check_daily_limit($tgId)) {
        $limit = (int)get_setting('daily_limit', (string)DEFAULT_DAILY_LIMIT) + (int)$user['bonus_downloads'];
        $bonus = (int)get_setting('ref_bonus', (string)REF_BONUS);
        $refLink = 'https://t.me/' . BOT_USERNAME . '?start=ref_' . $tgId;
        tg_send_message($chatId, t($lang, 'limit_reached', ['limit' => $limit, 'bonus' => $bonus, 'ref_link' => $refLink]), ['reply_to_message_id' => $messageId]);
        return;
    }

    $url = trim($rawUrl);
    if (preg_match('~(vm|vt)\.tiktok\.com/|tiktok\.com/t/|instagram\.com/share/~i', $url)) {
        $url = expand_short_url($url);
    }
    $platform = detect_platform($url);
    if ($platform === null) {
        tg_send_message($chatId, t($lang, 'invalid_link'), ['reply_to_message_id' => $messageId]);
        return;
    }

    touch_last_attempt($tgId);

    $hash = sha1(normalize_url($url));
    $cached = cache_get($hash);
    if ($cached !== null && deliver_cached_media($chatId, $cached, $lang, $messageId)) {
        increment_download_count($tgId);
        log_download($tgId, $url, $platform, 'ok');
        return;
    }

    tg_send_message($chatId, t($lang, 'queued'), ['reply_to_message_id' => $messageId]);
    enqueue_download($tgId, $chatId, $messageId, $url, $platform, $lang);
}

function deliver_cached_media(int $chatId, array $cached, string $lang, ?int $replyTo): bool
{
    try {
        if ($cached['media_type'] === 'video' && !empty($cached['file_id'])) {
            tg_send_video($chatId, $cached['file_id'], ['reply_to_message_id' => $replyTo]);
            return true;
        }
        if ($cached['media_type'] === 'photo' && !empty($cached['file_id'])) {
            tg_api('sendPhoto', ['chat_id' => $chatId, 'photo' => $cached['file_id'], 'reply_to_message_id' => $replyTo]);
            return true;
        }
        if ($cached['media_type'] === 'album' && !empty($cached['payload'])) {
            $items = json_decode((string)$cached['payload'], true);
            if (is_array($items) && !empty($items)) {
                send_album_by_file_ids($chatId, $items, $replyTo);
                return true;
            }
        }
        return false;
    } catch (Throwable $e) {
        log_error('deliver_cached', $e->getMessage());
        return false;
    }
}

function send_album_by_file_ids(int $chatId, array $items, ?int $replyTo = null): void
{
    $chunks = array_chunk($items, 10);
    $first = true;
    foreach ($chunks as $chunk) {
        $media = [];
        foreach ($chunk as $it) {
            $media[] = ['type' => $it['type'], 'media' => $it['file_id']];
        }
        $opts = ($first && $replyTo) ? ['reply_to_message_id' => $replyTo] : [];
        if (count($media) === 1) {
            if ($media[0]['type'] === 'video') {
                tg_send_video($chatId, $media[0]['media'], $opts);
            } else {
                tg_api('sendPhoto', array_merge(['chat_id' => $chatId, 'photo' => $media[0]['media']], $opts));
            }
        } else {
            tg_send_media_group($chatId, $media, $opts);
        }
        $first = false;
    }
}

function enqueue_download(int $tgId, int $chatId, ?int $messageId, string $url, string $platform, string $lang): void
{
    $stmt = db()->prepare("INSERT INTO dl_queue (tg_id, chat_id, message_id, url, platform, lang, status, created_at, updated_at)
        VALUES (:tg, :ch, :mid, :url, :pl, :lang, 'pending', :d, :d2)");
    $stmt->execute([
        ':tg' => $tgId, ':ch' => $chatId, ':mid' => $messageId, ':url' => $url,
        ':pl' => $platform, ':lang' => $lang, ':d' => now(), ':d2' => now(),
    ]);
}

/* ============================ CRON: ОЧЕРЕДЬ, КЭШ, РАССЫЛКА ============================ */

function run_cron(): void
{
    migrate();
    try {
        process_queue();
    } catch (Throwable $e) {
        log_error('cron_queue', $e->getMessage());
    }
    try {
        process_broadcast_batch();
    } catch (Throwable $e) {
        log_error('cron_broadcast', $e->getMessage());
    }
    try {
        cleanup_cache();
        cleanup_logs();
    } catch (Throwable $e) {
        log_error('cron_cleanup', $e->getMessage());
    }
    echo 'OK';
}

function process_queue(): void
{
    $stmt = db()->query("SELECT * FROM dl_queue WHERE status = 'pending' ORDER BY id ASC LIMIT 20");
    $jobs = $stmt->fetchAll();
    foreach ($jobs as $job) {
        $upd = db()->prepare("UPDATE dl_queue SET status = 'processing', attempts = attempts + 1, updated_at = :d WHERE id = :id");
        $upd->execute([':d' => now(), ':id' => $job['id']]);
        process_single_job($job);
    }
}

function process_single_job(array $job): void
{
    $lang = $job['lang'] ?: 'ru';
    $chatId = (int)$job['chat_id'];
    $tgId = (int)$job['tg_id'];
    $url = $job['url'];
    $platform = $job['platform'];
    $replyTo = $job['message_id'] !== null ? (int)$job['message_id'] : null;

    try {
        $media = resolve_media($url, $platform);
        if ($media === null || empty($media['items'])) {
            throw new RuntimeException('no provider returned media for this link');
        }
        deliver_media($chatId, $url, $platform, $media, $lang, $replyTo);
        $done = db()->prepare("UPDATE dl_queue SET status = 'done', updated_at = :d WHERE id = :id");
        $done->execute([':d' => now(), ':id' => $job['id']]);
        increment_download_count($tgId);
        log_download($tgId, $url, $platform, 'ok');
    } catch (Throwable $e) {
        $err = db()->prepare("UPDATE dl_queue SET status = 'error', error = :e, updated_at = :d WHERE id = :id");
        $err->execute([':e' => mb_substr($e->getMessage(), 0, 3000), ':d' => now(), ':id' => $job['id']]);
        log_error('queue_job', 'job #' . $job['id'] . ': ' . $e->getMessage());
        log_download($tgId, $url, $platform, 'error');
        tg_send_message($chatId, t($lang, 'download_error'), ['reply_to_message_id' => $replyTo]);
    }
}

function deliver_media(int $chatId, string $url, string $platform, array $media, string $lang, ?int $replyTo): void
{
    $items = $media['items'];
    $hash = sha1(normalize_url($url));

    if (count($items) === 1) {
        $item = $items[0];
        $sizeMb = remote_file_size_mb($item['url']);
        if ($sizeMb !== null && $sizeMb > MAX_FILE_MB) {
            $kb = ['inline_keyboard' => [[['text' => t($lang, 'btn_direct_link'), 'url' => $item['url']]]]];
            tg_send_message($chatId, t($lang, 'file_too_big', ['mb' => MAX_FILE_MB]), [
                'reply_markup' => json_encode($kb),
                'reply_to_message_id' => $replyTo,
            ]);
            cache_set($hash, $platform, 'link_only', null, ['url' => $item['url'], 'type' => $item['type']]);
            return;
        }
        if ($item['type'] === 'video') {
            $result = tg_send_video($chatId, $item['url'], ['reply_to_message_id' => $replyTo]);
            $fileId = $result['video']['file_id'] ?? null;
            if ($fileId) {
                cache_set($hash, $platform, 'video', $fileId, null);
            }
        } else {
            $result = tg_api('sendPhoto', ['chat_id' => $chatId, 'photo' => $item['url'], 'reply_to_message_id' => $replyTo]);
            $photos = $result['photo'] ?? [];
            $fileId = !empty($photos) ? $photos[count($photos) - 1]['file_id'] : null;
            if ($fileId) {
                cache_set($hash, $platform, 'photo', $fileId, null);
            }
        }
        return;
    }

    // карусель Instagram - отправляем пачками по 10
    $chunks = array_chunk($items, 10);
    $allFileIds = [];
    $first = true;
    foreach ($chunks as $chunk) {
        $mediaGroup = [];
        foreach ($chunk as $it) {
            $mediaGroup[] = ['type' => $it['type'], 'media' => $it['url']];
        }
        $opts = ($first && $replyTo) ? ['reply_to_message_id' => $replyTo] : [];
        $sent = tg_send_media_group($chatId, $mediaGroup, $opts);
        foreach ($sent as $i => $sentItem) {
            $fid = null;
            if (isset($sentItem['video']['file_id'])) {
                $fid = $sentItem['video']['file_id'];
            } elseif (!empty($sentItem['photo'])) {
                $photos = $sentItem['photo'];
                $fid = $photos[count($photos) - 1]['file_id'] ?? null;
            }
            if ($fid) {
                $allFileIds[] = ['type' => $chunk[$i]['type'], 'file_id' => $fid];
            }
        }
        $first = false;
    }
    if (!empty($allFileIds)) {
        cache_set($hash, $platform, 'album', null, $allFileIds);
    }
}

function cleanup_cache(): void
{
    db()->exec("DELETE FROM dl_cache WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY)");
    db()->exec("DELETE FROM dl_queue WHERE status IN ('done','error') AND updated_at < DATE_SUB(NOW(), INTERVAL 3 DAY)");
}

function cleanup_logs(): void
{
    db()->exec("DELETE FROM dl_logs WHERE level != 'admin_login_fail' AND created_at < DATE_SUB(NOW(), INTERVAL 14 DAY)");
    db()->exec("DELETE FROM dl_logs WHERE level = 'admin_login_fail' AND created_at < DATE_SUB(NOW(), INTERVAL 1 DAY)");
}

function process_broadcast_batch(): void
{
    if (get_setting('broadcast_active', '0') !== '1') {
        return;
    }
    $text = (string)get_setting('broadcast_text', '');
    if ($text === '') {
        set_setting('broadcast_active', '0');
        return;
    }
    $offset = (int)get_setting('broadcast_offset', '0');
    $stmt = db()->prepare("SELECT tg_id FROM dl_users WHERE is_banned = 0 ORDER BY id ASC LIMIT 25 OFFSET :off");
    $stmt->bindValue(':off', $offset, PDO::PARAM_INT);
    $stmt->execute();
    $rows = $stmt->fetchAll();

    if (empty($rows)) {
        set_setting('broadcast_active', '0');
        set_setting('broadcast_offset', '0');
        if (ADMIN_TG_ID > 0) {
            notify_admin('✅ Рассылка завершена.');
        }
        return;
    }

    foreach ($rows as $row) {
        $tgId = (int)$row['tg_id'];
        $sent = false;
        $attempts = 0;
        while (!$sent && $attempts < 2) {
            $attempts++;
            try {
                tg_send_message($tgId, $text);
                $sent = true;
            } catch (TelegramApiException $e) {
                if ($e->errorCode === 429 && $e->retryAfter > 0) {
                    sleep(min($e->retryAfter, 5));
                    continue;
                }
                log_error('broadcast', 'tg_id ' . $tgId . ': ' . $e->getMessage());
                break;
            } catch (Throwable $e) {
                log_error('broadcast', 'tg_id ' . $tgId . ': ' . $e->getMessage());
                break;
            }
        }
        usleep(60000);
    }

    set_setting('broadcast_offset', (string)($offset + 25));
}

/* ============================ УСТАНОВКА (?setup=) ============================ */

function run_setup(): void
{
    header('Content-Type: text/html; charset=utf-8');
    echo "<h2>Установка бота</h2><pre>";
    if (isset($_GET['reset']) && $_GET['reset'] === '1') {
        try {
            db()->exec("DROP TABLE IF EXISTS dl_cache, dl_channels, dl_downloads, dl_logs, dl_meta, dl_queue, dl_settings, dl_users");
            echo "🗑 Старые таблицы dl_* удалены (сброс структуры).\n";
        } catch (Throwable $e) {
            echo "❌ Ошибка при удалении старых таблиц: " . h($e->getMessage()) . "\n</pre>";
            return;
        }
    }
    try {
        migrate();
        echo "✅ Таблицы базы данных созданы/обновлены.\n";
    } catch (Throwable $e) {
        echo "❌ Ошибка миграции БД: " . h($e->getMessage()) . "\n</pre>";
        return;
    }
    try {
        tg_set_webhook();
        echo "✅ Webhook установлен: " . h(SELF_URL) . "\n";
    } catch (Throwable $e) {
        echo "❌ Ошибка установки webhook: " . h($e->getMessage()) . "\n";
    }
    echo "\nCron-строка (раз в минуту):\n";
    echo "* * * * * curl -s \"" . h(SELF_URL) . "?cron=" . h(CRON_SECRET) . "\" >/dev/null 2>&1\n";
    echo "\nАдмин-панель: " . h(SELF_URL) . "?admin=1\n";
    echo "</pre>";
}

/* ============================ АДМИН-ПАНЕЛЬ ============================ */

function admin_csrf_token(): string
{
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_start();
    }
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf'];
}

function admin_csrf_check(string $token): bool
{
    return !empty($_SESSION['csrf']) && $token !== '' && hash_equals($_SESSION['csrf'], $token);
}

function admin_recent_fail_count(string $ip): int
{
    $stmt = db()->prepare("SELECT COUNT(*) FROM dl_logs WHERE level = 'admin_login_fail' AND context = :ip AND created_at > DATE_SUB(NOW(), INTERVAL 15 MINUTE)");
    $stmt->execute([':ip' => $ip]);
    return (int)$stmt->fetchColumn();
}

function admin_register_fail(string $ip): void
{
    $stmt = db()->prepare("INSERT INTO dl_logs (level, message, context, created_at) VALUES ('admin_login_fail', 'failed admin login attempt', :ip, :d)");
    $stmt->execute([':ip' => $ip, ':d' => now()]);
}

function run_admin(): void
{
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_start();
    }
    migrate();
    header('Content-Type: text/html; charset=utf-8');

    if (isset($_GET['logout'])) {
        $_SESSION = [];
        session_destroy();
        header('Location: ?admin=1');
        return;
    }

    if (empty($_SESSION['admin_logged'])) {
        admin_handle_login();
        return;
    }

    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        admin_handle_post();
    }

    $page = $_GET['page'] ?? 'dashboard';
    $content = match ($page) {
        'users' => admin_users_html(),
        'channels' => admin_channels_html(),
        'settings' => admin_settings_html(),
        'logs' => admin_logs_html(),
        'broadcast' => admin_broadcast_html(),
        default => admin_dashboard_html(),
    };
    echo admin_layout($content, $page);
}

function admin_handle_login(): void
{
    $ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
    $error = '';
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        if (admin_recent_fail_count($ip) >= 5) {
            $error = 'Слишком много попыток входа. Подождите 15 минут.';
        } elseif (!admin_csrf_check((string)($_POST['csrf'] ?? ''))) {
            $error = 'Сессия истекла, обновите страницу.';
        } else {
            $login = (string)($_POST['login'] ?? '');
            $password = (string)($_POST['password'] ?? '');
            if (hash_equals(ADMIN_LOGIN, $login) && password_verify($password, ADMIN_PASSWORD_HASH)) {
                $_SESSION['admin_logged'] = true;
                session_regenerate_id(true);
                header('Location: ?admin=1');
                return;
            }
            admin_register_fail($ip);
            $error = 'Неверный логин или пароль.';
        }
    }
    echo admin_login_html($error);
}

function admin_handle_post(): void
{
    if (!admin_csrf_check((string)($_POST['csrf'] ?? ''))) {
        return;
    }
    $action = (string)($_POST['action'] ?? '');
    switch ($action) {
        case 'ban_user':
            $stmt = db()->prepare("UPDATE dl_users SET is_banned = 1 WHERE tg_id = :id");
            $stmt->execute([':id' => (int)($_POST['tg_id'] ?? 0)]);
            break;
        case 'unban_user':
            $stmt = db()->prepare("UPDATE dl_users SET is_banned = 0 WHERE tg_id = :id");
            $stmt->execute([':id' => (int)($_POST['tg_id'] ?? 0)]);
            break;
        case 'add_channel':
            $stmt = db()->prepare("INSERT INTO dl_channels (chat_id, username, title, url, is_active, created_at) VALUES (:cid, :u, :t, :url, 1, :d)");
            $stmt->execute([
                ':cid' => (int)($_POST['chat_id'] ?? 0),
                ':u' => trim((string)($_POST['username'] ?? '')) ?: null,
                ':t' => trim((string)($_POST['title'] ?? '')) ?: null,
                ':url' => trim((string)($_POST['url'] ?? '')) ?: null,
                ':d' => now(),
            ]);
            break;
        case 'toggle_channel':
            $stmt = db()->prepare("UPDATE dl_channels SET is_active = 1 - is_active WHERE id = :id");
            $stmt->execute([':id' => (int)($_POST['id'] ?? 0)]);
            break;
        case 'delete_channel':
            $stmt = db()->prepare("DELETE FROM dl_channels WHERE id = :id");
            $stmt->execute([':id' => (int)($_POST['id'] ?? 0)]);
            break;
        case 'save_settings':
            set_setting('daily_limit', (string)max(1, (int)($_POST['daily_limit'] ?? DEFAULT_DAILY_LIMIT)));
            set_setting('ref_bonus', (string)max(0, (int)($_POST['ref_bonus'] ?? REF_BONUS)));
            set_setting('flood_seconds', (string)max(0, (int)($_POST['flood_seconds'] ?? FLOOD_SECONDS)));
            set_setting('require_subscription', isset($_POST['require_subscription']) ? '1' : '0');
            break;
        case 'start_broadcast':
            $text = trim((string)($_POST['broadcast_text'] ?? ''));
            if ($text !== '') {
                set_setting('broadcast_text', $text);
                set_setting('broadcast_offset', '0');
                set_setting('broadcast_active', '1');
            }
            break;
        case 'stop_broadcast':
            set_setting('broadcast_active', '0');
            break;
    }
    $page = $_GET['page'] ?? 'dashboard';
    header('Location: ?admin=1&page=' . urlencode((string)$page));
    exit;
}

/* ============================ HTML АДМИН-ПАНЕЛИ ============================ */

function admin_layout(string $content, string $activePage): string
{
    $nav = [
        'dashboard' => 'Статистика',
        'users' => 'Пользователи',
        'channels' => 'Каналы',
        'settings' => 'Настройки',
        'broadcast' => 'Рассылка',
        'logs' => 'Логи',
    ];
    $navHtml = '';
    foreach ($nav as $key => $label) {
        $cls = $key === $activePage ? 'active' : '';
        $navHtml .= '<a class="' . $cls . '" href="?admin=1&page=' . $key . '">' . h($label) . '</a>';
    }
    return <<<HTML
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Админ-панель бота</title>
<style>
* { box-sizing: border-box; }
body { margin:0; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:#0f1117; color:#e6e6e6; }
header { background:#161925; padding:16px 24px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #262a3a; }
header h1 { font-size:18px; margin:0; }
header a.logout { color:#ff6b6b; text-decoration:none; font-size:14px; }
nav { display:flex; gap:4px; padding:12px 24px; background:#12141c; border-bottom:1px solid #262a3a; flex-wrap:wrap; }
nav a { color:#a9b0c3; text-decoration:none; padding:8px 14px; border-radius:8px; font-size:14px; }
nav a.active, nav a:hover { background:#2d3348; color:#fff; }
main { padding:24px; max-width:1100px; margin:0 auto; }
.card { background:#161925; border:1px solid #262a3a; border-radius:12px; padding:20px; margin-bottom:20px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:16px; }
.stat { background:#161925; border:1px solid #262a3a; border-radius:12px; padding:18px; }
.stat .num { font-size:28px; font-weight:700; color:#7dd3fc; }
.stat .label { color:#a9b0c3; font-size:13px; margin-top:4px; }
table { width:100%; border-collapse:collapse; font-size:14px; }
th, td { text-align:left; padding:10px 8px; border-bottom:1px solid #262a3a; }
th { color:#a9b0c3; font-weight:600; }
input[type=text], input[type=password], input[type=number], textarea { width:100%; padding:10px; border-radius:8px; border:1px solid #2d3348; background:#0f1117; color:#e6e6e6; margin-bottom:12px; font-size:14px; }
label { display:block; font-size:13px; color:#a9b0c3; margin-bottom:6px; }
button, .btn { background:#4f6bff; color:#fff; border:none; padding:9px 16px; border-radius:8px; cursor:pointer; font-size:14px; text-decoration:none; display:inline-block; }
button.danger { background:#ff4d4f; }
button.ghost { background:#2d3348; }
.badge { padding:3px 8px; border-radius:6px; font-size:12px; }
.badge.ok { background:#14532d; color:#86efac; }
.badge.bad { background:#5c1a1a; color:#fca5a5; }
form.inline { display:inline; }
.row { display:flex; gap:10px; flex-wrap:wrap; align-items:end; }
.row > div { flex:1; min-width:160px; }
.check { display:flex; align-items:center; gap:8px; }
.check input { width:auto; margin:0; }
pre.log { white-space:pre-wrap; word-break:break-all; background:#0f1117; padding:10px; border-radius:8px; font-size:12px; max-height:120px; overflow:auto; }
</style>
</head>
<body>
<header>
<h1>🤖 Панель управления ботом</h1>
<a class="logout" href="?admin=1&logout=1">Выход</a>
</header>
<nav>{$navHtml}</nav>
<main>
{$content}
</main>
</body>
</html>
HTML;
}

function admin_login_html(string $error): string
{
    $csrf = admin_csrf_token();
    $errHtml = $error !== '' ? '<div class="card" style="border-color:#ff4d4f;color:#fca5a5;">' . h($error) . '</div>' : '';
    return <<<HTML
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Вход в админ-панель</title>
<style>
body { margin:0; background:#0f1117; color:#e6e6e6; font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; }
.box { background:#161925; padding:32px; border-radius:14px; width:320px; border:1px solid #262a3a; }
.box h2 { margin-top:0; }
input { width:100%; padding:10px; margin-bottom:14px; border-radius:8px; border:1px solid #2d3348; background:#0f1117; color:#fff; }
button { width:100%; padding:11px; border:none; border-radius:8px; background:#4f6bff; color:#fff; font-size:15px; cursor:pointer; }
</style>
</head>
<body>
<div class="box">
<h2>Вход</h2>
{$errHtml}
<form method="post">
<input type="hidden" name="csrf" value="{$csrf}">
<label>Логин</label>
<input type="text" name="login" required autofocus>
<label>Пароль</label>
<input type="password" name="password" required>
<button type="submit">Войти</button>
</form>
</div>
</body>
</html>
HTML;
}

function admin_dashboard_html(): string
{
    $pdo = db();
    $totalUsers = (int)$pdo->query("SELECT COUNT(*) FROM dl_users")->fetchColumn();
    $bannedUsers = (int)$pdo->query("SELECT COUNT(*) FROM dl_users WHERE is_banned=1")->fetchColumn();
    $todayUsers = (int)$pdo->query("SELECT COUNT(*) FROM dl_users WHERE DATE(created_at) = CURDATE()")->fetchColumn();
    $totalDownloads = (int)$pdo->query("SELECT COUNT(*) FROM dl_downloads WHERE status='ok'")->fetchColumn();
    $todayDownloads = (int)$pdo->query("SELECT COUNT(*) FROM dl_downloads WHERE status='ok' AND DATE(created_at) = CURDATE()")->fetchColumn();
    $errorDownloads = (int)$pdo->query("SELECT COUNT(*) FROM dl_downloads WHERE status='error' AND DATE(created_at) = CURDATE()")->fetchColumn();
    $queuePending = (int)$pdo->query("SELECT COUNT(*) FROM dl_queue WHERE status='pending'")->fetchColumn();
    $cacheSize = (int)$pdo->query("SELECT COUNT(*) FROM dl_cache")->fetchColumn();

    return <<<HTML
<div class="grid">
<div class="stat"><div class="num">{$totalUsers}</div><div class="label">Всего пользователей</div></div>
<div class="stat"><div class="num">{$todayUsers}</div><div class="label">Новых сегодня</div></div>
<div class="stat"><div class="num">{$bannedUsers}</div><div class="label">Заблокировано</div></div>
<div class="stat"><div class="num">{$totalDownloads}</div><div class="label">Скачано всего</div></div>
<div class="stat"><div class="num">{$todayDownloads}</div><div class="label">Скачано сегодня</div></div>
<div class="stat"><div class="num">{$errorDownloads}</div><div class="label">Ошибок сегодня</div></div>
<div class="stat"><div class="num">{$queuePending}</div><div class="label">В очереди</div></div>
<div class="stat"><div class="num">{$cacheSize}</div><div class="label">В кэше</div></div>
</div>
HTML;
}

function admin_users_html(): string
{
    $csrf = admin_csrf_token();
    $search = trim((string)($_GET['q'] ?? ''));
    if ($search !== '') {
        $stmt = db()->prepare("SELECT * FROM dl_users WHERE tg_id = :q OR username LIKE :q2 ORDER BY id DESC LIMIT 50");
        $stmt->execute([':q' => (int)$search, ':q2' => '%' . $search . '%']);
    } else {
        $stmt = db()->query("SELECT * FROM dl_users ORDER BY id DESC LIMIT 50");
    }
    $users = $stmt->fetchAll();
    $rows = '';
    foreach ($users as $u) {
        $badge = $u['is_banned'] ? '<span class="badge bad">забанен</span>' : '<span class="badge ok">активен</span>';
        $uname = $u['username'] ? '@' . h($u['username']) : '—';
        $btn = $u['is_banned']
            ? '<form class="inline" method="post"><input type="hidden" name="csrf" value="' . h($csrf) . '"><input type="hidden" name="action" value="unban_user"><input type="hidden" name="tg_id" value="' . (int)$u['tg_id'] . '"><button class="ghost" type="submit">Разбанить</button></form>'
            : '<form class="inline" method="post"><input type="hidden" name="csrf" value="' . h($csrf) . '"><input type="hidden" name="action" value="ban_user"><input type="hidden" name="tg_id" value="' . (int)$u['tg_id'] . '"><button class="danger" type="submit">Забанить</button></form>';
        $rows .= '<tr><td>' . (int)$u['tg_id'] . '</td><td>' . $uname . '</td><td>' . h((string)$u['lang']) . '</td><td>' . (int)$u['downloads_today'] . '</td><td>' . (int)$u['bonus_downloads'] . '</td><td>' . $badge . '</td><td>' . $btn . '</td></tr>';
    }
    $searchH = h($search);
    return <<<HTML
<div class="card">
<form method="get">
<input type="hidden" name="admin" value="1">
<input type="hidden" name="page" value="users">
<div class="row">
<div><label>Поиск по ID или username</label><input type="text" name="q" value="{$searchH}"></div>
<div style="flex:0"><button type="submit">Найти</button></div>
</div>
</form>
</div>
<div class="card">
<table>
<tr><th>Telegram ID</th><th>Username</th><th>Язык</th><th>Скачано сегодня</th><th>Бонус</th><th>Статус</th><th></th></tr>
{$rows}
</table>
</div>
HTML;
}

function admin_channels_html(): string
{
    $csrf = admin_csrf_token();
    $channels = db()->query("SELECT * FROM dl_channels ORDER BY id DESC")->fetchAll();
    $rows = '';
    foreach ($channels as $c) {
        $badge = $c['is_active'] ? '<span class="badge ok">активен</span>' : '<span class="badge bad">выключен</span>';
        $rows .= '<tr><td>' . (int)$c['chat_id'] . '</td><td>' . h((string)$c['title']) . '</td><td>' . h((string)$c['username']) . '</td><td>' . $badge . '</td><td>
        <form class="inline" method="post"><input type="hidden" name="csrf" value="' . h($csrf) . '"><input type="hidden" name="action" value="toggle_channel"><input type="hidden" name="id" value="' . (int)$c['id'] . '"><button class="ghost" type="submit">Вкл/Выкл</button></form>
        <form class="inline" method="post" onsubmit="return confirm(\'Удалить канал?\')"><input type="hidden" name="csrf" value="' . h($csrf) . '"><input type="hidden" name="action" value="delete_channel"><input type="hidden" name="id" value="' . (int)$c['id'] . '"><button class="danger" type="submit">Удалить</button></form>
        </td></tr>';
    }
    return <<<HTML
<div class="card">
<h3>Добавить канал</h3>
<form method="post">
<input type="hidden" name="csrf" value="{$csrf}">
<input type="hidden" name="action" value="add_channel">
<div class="row">
<div><label>Chat ID (например -1001234567890)</label><input type="text" name="chat_id" required></div>
<div><label>Username (без @, необязательно)</label><input type="text" name="username"></div>
<div><label>Название</label><input type="text" name="title"></div>
<div><label>Ссылка (t.me/...)</label><input type="text" name="url"></div>
</div>
<button type="submit">Добавить</button>
</form>
</div>
<div class="card">
<table>
<tr><th>Chat ID</th><th>Название</th><th>Username</th><th>Статус</th><th></th></tr>
{$rows}
</table>
</div>
HTML;
}

function admin_settings_html(): string
{
    $csrf = admin_csrf_token();
    $dailyLimit = h(get_setting('daily_limit', (string)DEFAULT_DAILY_LIMIT));
    $refBonus = h(get_setting('ref_bonus', (string)REF_BONUS));
    $floodSeconds = h(get_setting('flood_seconds', (string)FLOOD_SECONDS));
    $requireSub = get_setting('require_subscription', '0') === '1' ? 'checked' : '';
    return <<<HTML
<div class="card">
<form method="post">
<input type="hidden" name="csrf" value="{$csrf}">
<input type="hidden" name="action" value="save_settings">
<div class="row">
<div><label>Лимит загрузок в сутки</label><input type="number" name="daily_limit" value="{$dailyLimit}" min="1"></div>
<div><label>Бонус за приглашённого друга</label><input type="number" name="ref_bonus" value="{$refBonus}" min="0"></div>
<div><label>Антифлуд, секунд</label><input type="number" name="flood_seconds" value="{$floodSeconds}" min="0"></div>
</div>
<div class="check"><input type="checkbox" name="require_subscription" id="rs" {$requireSub}><label for="rs" style="margin:0;">Обязательная подписка на каналы</label></div>
<br><button type="submit">Сохранить</button>
</form>
</div>
HTML;
}

function admin_broadcast_html(): string
{
    $csrf = admin_csrf_token();
    $active = get_setting('broadcast_active', '0') === '1';
    $offset = (int)get_setting('broadcast_offset', '0');
    $total = (int)db()->query("SELECT COUNT(*) FROM dl_users WHERE is_banned = 0")->fetchColumn();
    $status = $active ? "<p>🟢 Рассылка идёт: отправлено ~{$offset} из {$total}</p>" : '<p>⚪ Рассылка не запущена.</p>';
    $stopBtn = $active ? '<form method="post"><input type="hidden" name="csrf" value="' . h($csrf) . '"><input type="hidden" name="action" value="stop_broadcast"><button class="danger" type="submit">Остановить</button></form>' : '';
    return <<<HTML
<div class="card">
<h3>Массовая рассылка</h3>
{$status}
{$stopBtn}
<form method="post">
<input type="hidden" name="csrf" value="{$csrf}">
<input type="hidden" name="action" value="start_broadcast">
<label>Текст сообщения</label>
<textarea name="broadcast_text" rows="6" required></textarea>
<button type="submit">Запустить рассылку</button>
</form>
<p style="color:#a9b0c3;font-size:13px;">Рассылка отправляется пачками по 25 пользователей раз в минуту через cron.</p>
</div>
HTML;
}

function admin_logs_html(): string
{
    $logs = db()->query("SELECT * FROM dl_logs WHERE level != 'admin_login_fail' ORDER BY id DESC LIMIT 100")->fetchAll();
    $rows = '';
    foreach ($logs as $l) {
        $rows .= '<tr><td>' . h((string)$l['created_at']) . '</td><td>' . h((string)$l['level']) . '</td><td><pre class="log">' . h((string)$l['message']) . '</pre></td></tr>';
    }
    return <<<HTML
<div class="card">
<table>
<tr><th>Дата</th><th>Уровень</th><th>Сообщение</th></tr>
{$rows}
</table>
</div>
HTML;
}
