<?php
/**
 * ==========================================================================
 *  ZVER TAJ — Telegram bot + Mini App backend
 *  Як файл. PHP 8 + MySQL. Ҷадвалҳо бо префикси z_
 *
 *  НАСБ:
 *   1) CONFIG-ро пур кунед
 *   2) Файлро дар /zver/zbot.php гузоред, zapp.php дар ҳамон папка
 *   3) Кушоед: ?setup=1&secret=SECRET
 *   4) Дар @BotFather → Menu Button → https://SITE/zver/zapp.php
 *   5) Cron ҳар 5 дақиқа: ?cron=1&secret=SECRET
 * ==========================================================================
 */

declare(strict_types=1);
@set_time_limit(0);
@ini_set('display_errors', '0');
date_default_timezone_set('Asia/Dushanbe');
mb_internal_encoding('UTF-8');

/** Эҷоди const аз тағйирёбанда (барои config.php) */
function const_define(string $name, $value): void {
    if (!defined($name)) define($name, $value);
}


/* ======================= CONFIG ======================= */
/* Ҳамаи калидҳо дар config.php — ин файлро дар git нагузоред!
   Намуна: config.example.php → нусха бардоред ба config.php */

$__cfgFile = __DIR__ . '/config.php';
if (!is_file($__cfgFile)) {
    http_response_code(500);
    exit("config.php ёфт нашуд. config.example.php-ро ба config.php нусха бардоред ва пур кунед.");
}
$C = require $__cfgFile;

const_define('BOT_TOKEN', $C['bot_token'] ?? '');
const_define('ADMINS',    $C['admins']    ?? []);
const_define('DB_HOST',   $C['db_host']   ?? 'localhost');
const_define('DB_NAME',   $C['db_name']   ?? '');
const_define('DB_USER',   $C['db_user']   ?? '');
const_define('DB_PASS',   $C['db_pass']   ?? '');
const_define('SECRET',    $C['secret']    ?? '');
const_define('GS_KEY_DEFAULT', $C['gs_key'] ?? '');
const_define('FZ_KEY',    $C['fz_key']    ?? '');
const_define('FZ_HOOK',   $C['fz_hook']   ?? '');
const_define('FZ_BASE',   $C['fz_base']   ?? 'https://api.fzr.cards/api/v2');
const_define('FT_ID',     $C['ft_id']     ?? '');
const_define('FT_KEY',    $C['ft_key']    ?? '');
const_define('FT_BASE',   $C['ft_base']   ?? 'https://api.flashtopup.com/api/reseller/v2');
const_define('FT_PATH',   $C['ft_path']   ?? '/api/reseller/v2');
const_define('VERSION',   'zver-13.1-nickfix');
const_define('DEBUG',     (bool)($C['debug'] ?? false));

/* ======================= BOOT ======================= */

if (!function_exists('str_contains')) {
    function str_contains($h, $n) { return $n === '' || strpos((string)$h, (string)$n) !== false; }
}
if (!function_exists('str_starts_with')) {
    function str_starts_with($h, $n) { return strncmp((string)$h, (string)$n, strlen((string)$n)) === 0; }
}

define('ZLOG', __DIR__ . '/zver_error.log');
@ini_set('log_errors', '1');
@ini_set('error_log', ZLOG);

function flog(string $m): void {
    @file_put_contents(ZLOG, date('Y-m-d H:i:s') . ' | ' . $m . "\n", FILE_APPEND);
}

set_exception_handler(function ($e) {
    $msg = $e->getMessage() . ' @' . basename($e->getFile()) . ':' . $e->getLine();
    flog('EX: ' . $msg);
    if (isset($_GET['api'])) {
        if (!headers_sent()) {
            http_response_code(200);
            header('Content-Type: application/json; charset=utf-8');
        }
        echo json_encode(['ok' => false, 'error' => 'SERVER', 'detail' => mb_substr($msg, 0, 300)],
                         JSON_UNESCAPED_UNICODE);
        exit;
    }
    if (!headers_sent()) http_response_code(200);
    echo 'ok';
});
register_shutdown_function(function () {
    $e = error_get_last();
    if ($e && in_array($e['type'], [E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR], true)
        && isset($_GET['api'])) {
        if (!headers_sent()) header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['ok' => false, 'error' => 'FATAL',
                          'detail' => mb_substr($e['message'] . ' @' . basename($e['file'])
                                     . ':' . $e['line'], 0, 300)], JSON_UNESCAPED_UNICODE);
    }
});
register_shutdown_function(function () {
    $e = error_get_last();
    if ($e && in_array($e['type'], [E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR], true)) {
        flog('FATAL: ' . $e['message'] . ' @' . $e['file'] . ':' . $e['line']);
    }
});

function db(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $pdo = new PDO('mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4',
            DB_USER, DB_PASS, [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
                PDO::ATTR_TIMEOUT => 8,            // зери сарборӣ — интизори дароз накунем
                PDO::ATTR_PERSISTENT => false,     // shared-хостинг: пайвасти доимӣ хатарнок
            ]);
    }
    return $pdo;
}
function q(string $sql, array $p = []): PDOStatement { $st = db()->prepare($sql); $st->execute($p); return $st; }
function one(string $sql, array $p = []): ?array { $r = q($sql, $p)->fetch(); return $r === false ? null : $r; }
function all(string $sql, array $p = []): array { return q($sql, $p)->fetchAll(); }

function migrate(): void {
    // якбор дар як версия — на дар ҳар дархост
    static $ran = false;
    if ($ran) return;
    $ran = true;

    try {
        $r = db()->query("SELECT v FROM z_settings WHERE k='db_ver'")->fetch();
        if ($r && (string)$r['v'] === VERSION) return;      // аллакай нав аст
    } catch (Throwable $e) { /* ҷадвал ҳанӯз нест — идома медиҳем */ }

    $t = [
"CREATE TABLE IF NOT EXISTS z_settings (k VARCHAR(64) PRIMARY KEY, v TEXT)
 ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_users (
 id BIGINT PRIMARY KEY, username VARCHAR(64) NULL, name VARCHAR(128) NULL,
 phone VARCHAR(32) NULL, lang VARCHAR(4) DEFAULT 'tj',
 balance DECIMAL(14,2) DEFAULT 0, spent DECIMAL(14,2) DEFAULT 0,
 orders_cnt INT DEFAULT 0, blocked TINYINT DEFAULT 0,
 ref_by BIGINT NULL, ref_paid TINYINT DEFAULT 0,
 ref_cnt INT DEFAULT 0, ref_sum DECIMAL(14,2) DEFAULT 0,
 created_at INT, seen_at INT) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_state (
 uid BIGINT PRIMARY KEY, st VARCHAR(64) NULL, data MEDIUMTEXT NULL, at INT)
 ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_games (
 id INT AUTO_INCREMENT PRIMARY KEY,
 name VARCHAR(120), image VARCHAR(255) NULL,
 need_server TINYINT DEFAULT 0,
 id_label VARCHAR(60) DEFAULT 'ID',
 server_label VARCHAR(60) DEFAULT 'Server',
 hint VARCHAR(191) NULL,
 sort INT DEFAULT 0, active TINYINT DEFAULT 1,
 created_at INT) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_packs (
 id INT AUTO_INCREMENT PRIMARY KEY,
 game_id INT, name VARCHAR(120), price DECIMAL(12,2),
 old_price DECIMAL(12,2) NULL, tag VARCHAR(24) NULL,
 sort INT DEFAULT 0, active TINYINT DEFAULT 1,
 INDEX (game_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_orders (
 id INT AUTO_INCREMENT PRIMARY KEY,
 uid BIGINT, game_id INT, pack_id INT,
 game_name VARCHAR(120), pack_name VARCHAR(120),
 player_id VARCHAR(64), server_id VARCHAR(64) NULL,
 qty INT DEFAULT 1, price DECIMAL(12,2),
 status VARCHAR(16) DEFAULT 'new',
 code VARCHAR(191) NULL, note VARCHAR(191) NULL,
 admin_id BIGINT NULL, refunded TINYINT DEFAULT 0,
 created_at INT, done_at INT NULL,
 INDEX (uid), INDEX (status)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_topups (
 id INT AUTO_INCREMENT PRIMARY KEY,
 uid BIGINT, amount DECIMAL(12,2), req_id INT NULL,
 file_id VARCHAR(191) NULL, status VARCHAR(16) DEFAULT 'new',
 admin_id BIGINT NULL, created_at INT, done_at INT NULL,
 INDEX (uid), INDEX (status)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_reqs (
 id INT AUTO_INCREMENT PRIMARY KEY,
 bank VARCHAR(80), owner VARCHAR(120), number VARCHAR(80),
 kind VARCHAR(12) DEFAULT 'card', pay_url VARCHAR(255) NULL,
 active TINYINT DEFAULT 1, sort INT DEFAULT 0)
 ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_subs (
 id INT AUTO_INCREMENT PRIMARY KEY,
 chat VARCHAR(120),
 title VARCHAR(120),
 link VARCHAR(255) NULL,
 active TINYINT DEFAULT 1, sort INT DEFAULT 0,
 created_at INT DEFAULT 0)
 ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_bank (
 id INT AUTO_INCREMENT PRIMARY KEY,
 op_no VARCHAR(64) NULL, amount DECIMAL(12,2), top_id INT NULL,
 comment VARCHAR(120) NULL, op_date VARCHAR(24) NULL, op_time VARCHAR(16) NULL,
 card VARCHAR(40) NULL, sender VARCHAR(120) NULL,
 matched INT NULL, raw TEXT NULL, created_at INT,
 UNIQUE KEY uq_op (op_no), INDEX (amount), INDEX (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_checks (
 id INT AUTO_INCREMENT PRIMARY KEY, topup_id INT NULL, uid BIGINT,
 img_hash VARCHAR(40) NULL, op_no VARCHAR(64) NULL,
 amount DECIMAL(12,2) NULL, op_date VARCHAR(24) NULL, op_time VARCHAR(16) NULL,
 bank VARCHAR(80) NULL, receiver VARCHAR(120) NULL, sender VARCHAR(120) NULL,
 verdict VARCHAR(16) DEFAULT 'ok', reason VARCHAR(191) NULL,
 raw MEDIUMTEXT NULL, created_at INT,
 INDEX (uid), INDEX (img_hash), INDEX (op_no)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_tx (
 id INT AUTO_INCREMENT PRIMARY KEY, uid BIGINT,
 kind VARCHAR(16), amount DECIMAL(12,2), balance DECIMAL(14,2) DEFAULT 0,
 title VARCHAR(160) NULL, ref_id INT NULL, created_at INT,
 INDEX (uid, id), INDEX (created_at)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_queue (
 id INT AUTO_INCREMENT PRIMARY KEY, order_id INT UNIQUE, uid BIGINT,
 tries INT DEFAULT 0, last_err VARCHAR(191) NULL, created_at INT,
 INDEX (uid)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_reviews (
 id INT AUTO_INCREMENT PRIMARY KEY, uid BIGINT, order_id INT, stars TINYINT,
 txt TEXT NULL, posted TINYINT DEFAULT 0, created_at INT,
 UNIQUE KEY uq_rev (order_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_promo (
 id INT AUTO_INCREMENT PRIMARY KEY, code VARCHAR(32) UNIQUE,
 kind VARCHAR(8) DEFAULT 'pct', val DECIMAL(10,2),
 min_sum DECIMAL(12,2) DEFAULT 0, max_uses INT DEFAULT 0, per_user INT DEFAULT 1,
 used INT DEFAULT 0, saved DECIMAL(14,2) DEFAULT 0, until INT NULL,
 active TINYINT DEFAULT 1, created_at INT) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_promo_use (
 id INT AUTO_INCREMENT PRIMARY KEY, promo_id INT, uid BIGINT, order_id INT NULL,
 sum_off DECIMAL(12,2), at INT,
 INDEX (promo_id), INDEX (uid)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_rate (k VARCHAR(80) PRIMARY KEY, cnt INT DEFAULT 0, win INT DEFAULT 0)
 ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_bans (ip VARCHAR(64) PRIMARY KEY, until INT, why VARCHAR(64) NULL)
 ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",

"CREATE TABLE IF NOT EXISTS z_log (id INT AUTO_INCREMENT PRIMARY KEY,
 tag VARCHAR(32), txt MEDIUMTEXT, at INT) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
    ];
    foreach ($t as $sql) db()->exec($sql);

    // сутунҳо барои FlashTopup
    foreach ([
      "ALTER TABLE z_games ADD COLUMN ft_code VARCHAR(128) NULL",
      "ALTER TABLE z_games ADD COLUMN ft_type VARCHAR(32) NULL",
      "ALTER TABLE z_games ADD COLUMN vcode VARCHAR(64) NULL",
      "ALTER TABLE z_games ADD COLUMN can_chk TINYINT DEFAULT 0",
      "ALTER TABLE z_games ADD COLUMN fields MEDIUMTEXT NULL",
      "ALTER TABLE z_reqs ADD COLUMN fname VARCHAR(80) NULL",
      "ALTER TABLE z_reqs ADD COLUMN lname VARCHAR(80) NULL",
      "ALTER TABLE z_reqs ADD COLUMN note VARCHAR(160) NULL",
      "ALTER TABLE z_games ADD COLUMN hidden TINYINT DEFAULT 0",
      "ALTER TABLE z_orders ADD COLUMN promo VARCHAR(32) NULL",
      "ALTER TABLE z_orders ADD COLUMN discount DECIMAL(12,2) DEFAULT 0",
      "ALTER TABLE z_topups ADD COLUMN comment VARCHAR(64) NULL",
      "ALTER TABLE z_reqs ADD COLUMN logo VARCHAR(191) NULL",
      "ALTER TABLE z_packs ADD COLUMN title VARCHAR(120) NULL",
      "ALTER TABLE z_packs ADD COLUMN fixed TINYINT DEFAULT 0",
      "ALTER TABLE z_games ADD COLUMN title VARCHAR(120) NULL",
      "ALTER TABLE z_games ADD COLUMN cat_order VARCHAR(255) NULL",
      "ALTER TABLE z_settings ADD COLUMN v2 TEXT NULL",
      "ALTER TABLE z_games ADD COLUMN base VARCHAR(120) NULL",
      "ALTER TABLE z_games ADD COLUMN region VARCHAR(16) NULL",
      "ALTER TABLE z_games ADD COLUMN flag VARCHAR(8) NULL",
      "ALTER TABLE z_games ADD INDEX idx_base (base)",
      "ALTER TABLE z_packs ADD COLUMN cat VARCHAR(16) DEFAULT 'main'",
      "ALTER TABLE z_games ADD UNIQUE KEY uq_ft (ft_code)",
      "ALTER TABLE z_packs ADD COLUMN ft_code VARCHAR(160) NULL",
      "ALTER TABLE z_packs ADD COLUMN cost DECIMAL(12,4) DEFAULT 0",
      "ALTER TABLE z_packs ADD UNIQUE KEY uq_ftp (ft_code)",
      "ALTER TABLE z_orders ADD COLUMN ft_id VARCHAR(64) NULL",
      "ALTER TABLE z_orders ADD COLUMN ref VARCHAR(64) NULL",
      "ALTER TABLE z_orders ADD COLUMN nick VARCHAR(191) NULL",
      "ALTER TABLE z_orders ADD UNIQUE KEY uq_ref (ref)",
      // --- индексҳо барои сарборӣ (10k корбар) ---
      "ALTER TABLE z_orders ADD INDEX idx_uid_id (uid, id)",
      "ALTER TABLE z_orders ADD INDEX idx_status_created (status, created_at)",
      "ALTER TABLE z_orders ADD INDEX idx_status_ref (status, refunded)",
      "ALTER TABLE z_topups ADD INDEX idx_uid_status (uid, status)",
      "ALTER TABLE z_topups ADD INDEX idx_status_created (status, created_at)",
      "ALTER TABLE z_packs ADD INDEX idx_game_active (game_id, active)",
      "ALTER TABLE z_reviews ADD INDEX idx_posted (posted)",
      "ALTER TABLE z_rate ADD INDEX idx_win (win)",
      "ALTER TABLE z_users ADD COLUMN sub_ok_at INT DEFAULT 0",
    ] as $a) { try { db()->exec($a); } catch (Throwable $e) {} }

    db()->exec("CREATE TABLE IF NOT EXISTS z_hooks (eid VARCHAR(80) PRIMARY KEY, at INT)
                ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $def = [
        'shop'      => 'ZVER TAJ',
        'markup'    => '20',
        'rate'      => '11',
        'round'     => '0.5',
        'sandbox'   => '0',
        'lowbal'    => '5',
        'lownote'   => '0',
        'ft_nick'   => '1',
        'sub_ch'    => '',
        'ask_rev'   => '1',
        'rev_ch'    => '',
        'rev_min'   => '4',
        'rev_anon'  => '0',
        'live_base' => '0',
        'live_add'  => '0',
        'pay_tpl'   => 'https://pay.dc.tj/?a={NUM}&c={COMMENT}&f1=133&s={SUM}',
        'bank_wait'   => '20',
        'bank_reject' => '0',
        'top'       => 'free fire,pubg,mobile legends,call of duty,standoff,genshin,'
                     . 'delta force,roblox,brawl stars,clash of clans,valorant,efootball',
        'auto'      => '1',
        'cur'       => 'TJS',
        'support'   => '@rutsiyax',
        'wa'        => '79667592770',
        'channel'   => '',
        'reviews'   => '',
        'ref_bonus' => '0.50',
        'welcome'   => '',
    ];
    foreach ($def as $k => $v) q("INSERT IGNORE INTO z_settings (k,v) VALUES (?,?)", [$k, $v]);

    // қайд мекунем: барои ин версия база тайёр аст
    try {
        q("INSERT INTO z_settings (k,v) VALUES ('db_ver',?)
           ON DUPLICATE KEY UPDATE v=VALUES(v)", [VERSION]);
    } catch (Throwable $e) {}

    try { tx_backfill(); } catch (Throwable $e) {}
}

function &scache(): array { static $c = []; return $c; }
function cfg(string $k, string $d = ''): string {
    $c = &scache();
    // Бори аввал ҲАМА танзимотро якбора мегирем (як SELECT ба ҷои даҳҳо)
    if (!isset($c['__loaded'])) {
        $c['__loaded'] = '1';
        try {
            foreach (all("SELECT k, v FROM z_settings WHERE k NOT LIKE 'ffn:%' AND k NOT LIKE 'gsn:%'") as $row) {
                $c[(string)$row['k']] = (string)$row['v'];
            }
        } catch (Throwable $e) {}
    }
    if (!array_key_exists($k, $c)) return $d;
    return $c[$k] === '' ? $d : $c[$k];
}
function setcfg(string $k, string $v): void {
    q("INSERT INTO z_settings (k,v) VALUES (?,?) ON DUPLICATE KEY UPDATE v=VALUES(v)", [$k, $v]);
    $c = &scache(); $c[$k] = $v;
}
function zlog(string $tag, string $txt): void {
    try { q("INSERT INTO z_log (tag,txt,at) VALUES (?,?,?)", [$tag, mb_substr($txt, 0, 4000), time()]); }
    catch (Throwable $e) {}
}

/* ======================= ҲИФЗ ======================= */

function ip(): string {
    foreach (['HTTP_CF_CONNECTING_IP', 'HTTP_X_REAL_IP', 'HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'] as $k) {
        if (!empty($_SERVER[$k])) {
            $v = trim(explode(',', (string)$_SERVER[$k])[0]);
            if (filter_var($v, FILTER_VALIDATE_IP)) return $v;
        }
    }
    return '0.0.0.0';
}
function rate(string $key, int $lim, int $win): bool {
    try {
        $k = mb_substr($key, 0, 78);
        $w = time() - (time() % $win);
        q("INSERT INTO z_rate (k,cnt,win) VALUES (?,1,?)
           ON DUPLICATE KEY UPDATE cnt=IF(win=VALUES(win),cnt+1,1), win=VALUES(win)",
          [$k, $w]);
        // танҳо ҳисоби тирезаи ҷорӣ — кӯҳнаҳо халал намерасонанд
        $r = one("SELECT cnt FROM z_rate WHERE k=? AND win=?", [$k, $w]);
        return ((int)($r['cnt'] ?? 1)) <= $lim;
    } catch (Throwable $e) { return true; }
}
function banned(string $i): bool {
    try { $r = one("SELECT until FROM z_bans WHERE ip=?", [$i]); return $r && (int)$r['until'] > time(); }
    catch (Throwable $e) { return false; }
}
function ban(string $i, int $min, string $why = ''): void {
    try {
        q("INSERT INTO z_bans (ip,until,why) VALUES (?,?,?)
           ON DUPLICATE KEY UPDATE until=GREATEST(until,VALUES(until)), why=VALUES(why)",
          [$i, time() + $min * 60, mb_substr($why, 0, 60)]);
    } catch (Throwable $e) {}
}
function guard_page(): void {
    $i = ip();
    if (banned($i)) { http_response_code(403); exit('banned'); }
    if (($_GET['secret'] ?? '') !== SECRET) {
        if (!rate('bad:' . $i, 25, 600)) ban($i, 20, 'bad secret');
        http_response_code(403);
        exit('forbidden — секрет нодуруст');
    }
}

/* ======================= TELEGRAM ======================= */

function tg(string $m, array $p = []): array {
    $ch = curl_init('https://api.telegram.org/bot' . BOT_TOKEN . '/' . $m);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true, CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($p, JSON_UNESCAPED_UNICODE),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'], CURLOPT_TIMEOUT => 25,
    ]);
    $r = curl_exec($ch); curl_close($ch);
    $d = json_decode((string)$r, true);
    return is_array($d) ? $d : ['ok' => false];
}
function h($s): string {
    if (is_array($s) || is_object($s)) $s = json_encode($s, JSON_UNESCAPED_UNICODE);
    return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
function say($chat, string $t, ?array $kb = null): array {
    $p = ['chat_id' => $chat, 'text' => $t, 'parse_mode' => 'HTML', 'disable_web_page_preview' => true];
    if ($kb) $p['reply_markup'] = ['inline_keyboard' => $kb];
    $r = tg('sendMessage', $p);

    // агар тугмаҳо нодуруст бошанд — бе тугмаҳо мефиристем, то паём гум нашавад
    if (empty($r['ok']) && $kb) {
        $d = mb_strtolower((string)($r['description'] ?? ''));
        if (str_contains($d, 'button') || str_contains($d, 'url') || str_contains($d, 'markup')) {
            flog('KB bad: ' . ($r['description'] ?? ''));
            unset($p['reply_markup']);
            $r = tg('sendMessage', $p);
        }
    }
    return $r;
}
function ed($chat, $mid, string $t, ?array $kb = null): array {
    $p = ['chat_id' => $chat, 'message_id' => $mid, 'text' => $t,
          'parse_mode' => 'HTML', 'disable_web_page_preview' => true];
    if ($kb) $p['reply_markup'] = ['inline_keyboard' => $kb];
    $r = tg('editMessageText', $p);
    if (!empty($r['ok'])) return $r;

    $d = mb_strtolower((string)($r['description'] ?? ''));
    if ($kb && (str_contains($d, 'button') || str_contains($d, 'url')
                || str_contains($d, 'markup'))) {
        flog('KB bad (edit): ' . ($r['description'] ?? ''));
        unset($p['reply_markup']);
        $r = tg('editMessageText', $p);
        if (!empty($r['ok'])) return $r;
        return say($chat, $t, null);
    }
    return say($chat, $t, $kb);
}
/** Ислоҳи паём — фарқ надорад расм аст ё матн */
function ed_any($chat, $mid, string $t, ?array $kb = null): array {
    $p = ['chat_id' => $chat, 'message_id' => $mid, 'parse_mode' => 'HTML'];
    if ($kb) $p['reply_markup'] = ['inline_keyboard' => $kb];

    $r = tg('editMessageCaption', $p + ['caption' => mb_substr($t, 0, 1000)]);
    if (!empty($r['ok'])) return $r;

    $r2 = tg('editMessageText', $p + ['text' => $t, 'disable_web_page_preview' => true]);
    if (!empty($r2['ok'])) return $r2;

    return say($chat, $t, $kb);
}
function toast($id, string $t = '', bool $big = false): void {
    tg('answerCallbackQuery', ['callback_query_id' => $id, 'text' => $t, 'show_alert' => $big]);
}
function photo_file($chat, string $path, string $cap, ?array $kb = null): array {
    $p = ['chat_id' => $chat, 'caption' => mb_substr($cap, 0, 1000), 'parse_mode' => 'HTML',
          'photo' => new CURLFile($path, 'image/jpeg', 'r.jpg')];
    if ($kb) $p['reply_markup'] = json_encode(['inline_keyboard' => $kb], JSON_UNESCAPED_UNICODE);
    $ch = curl_init('https://api.telegram.org/bot' . BOT_TOKEN . '/sendPhoto');
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $p, CURLOPT_TIMEOUT => 60]);
    $r = curl_exec($ch); curl_close($ch);
    $d = json_decode((string)$r, true);
    return is_array($d) ? $d : ['ok' => false];
}
function is_admin($id): bool { return in_array((int)$id, ADMINS, true); }
function money(float $v): string { return number_format($v, 2, '.', ' ') . ' ' . cfg('cur', 'TJS'); }

/* ======================= ЗАБОН ======================= */

const LNGS = ['tj', 'ru', 'uz', 'ky', 'en', 'kk'];

function lang_list(): array {
    return ['tj' => 'Тоҷикӣ', 'ru' => 'Русский', 'uz' => "O'zbekcha",
            'ky' => 'Кыргызча', 'en' => 'English', 'kk' => 'Қазақша'];
}
function ulang($uid): string {
    static $c = [];
    if (isset($c[$uid])) return $c[$uid];
    $r = one("SELECT lang FROM z_users WHERE id=?", [$uid]);
    return $c[$uid] = ($r && in_array($r['lang'], LNGS, true)) ? $r['lang'] : 'tj';
}
function TXT(): array {
    return [
'tj' => ['subT'=>'ОБУНА ШАВЕД','subGo'=>'Ба канал ворид шудан','subChk'=>'Ман обуна шудам',
 'subTxt'=>'Барои истифодаи бот аввал ба канали мо обуна шавед.',
 'subWhy'=>'Дар канал: тахфифҳо, бозиҳои нав, хабарҳо ва ҷавоб ба саволҳо.',
 'subNo'=>'Шумо ҳанӯз обуна нашудаед',
 'skip'=>'Гузаштан','revPub'=>'Шарҳи шумо дар канал ҷой гирифт — сипос!','revQ'=>'Хизматрасонӣ чӣ гуна буд?','revTh'=>'Сипос барои баҳо!',
 'revAsk'=>'Чанд калима нависед — шарҳи шумо дар канал ҷой мегирад.',
 'revBad'=>'Бубахшед! Чӣ хато шуд? Нависед — ислоҳ мекунем.','revOk'=>'Сипос барои шарҳ!',
 'app'=>'▸ КУШОДАНИ БАРНОМА','shop'=>'КАТАЛОГ','wallet'=>'ҲАМЁН','ord'=>'ФАРМОИШҲО',
 'ref'=>'ДӮСТОН','help'=>'КӮМАК','lang'=>'ЗАБОН','rev'=>'ШАРҲҲО','adm'=>'АДМИН','back'=>'‹ Бозгашт',
 'hi'=>'Хуш омадед','sub'=>'Донати бозиҳо — зуд, арзон, шабонарӯзӣ.','tap'=>'Барномаро кушоед',
 'phone'=>'Барои сабти ном рақами телефонро фиристед','phb'=>'Фиристодани рақам',
 'reg'=>'Сабти ном анҷом ёфт','own'=>'Рақами худатонро фиристед',
 'bal'=>'Баланс','spent'=>'Хароҷот','cnt'=>'Фармоишҳо','topup'=>'Барои пур кардан барномаро кушоед',
 'noord'=>'Фармоиш нест','myord'=>'ФАРМОИШҲОИ ШУМО','lng'=>'Забонро интихоб кунед','lok'=>'Забон иваз шуд',
 'fast'=>'Хеле зуд, сабр кунед','blk'=>'Дастрасӣ баста','q'=>'Савол доред?',
 'hlp'=>"КӮМАК\n\n1 · Бозиро интихоб кунед\n2 · ID нависед\n3 · Пакетро интихоб кунед\n4 · Ҳамёнро пур кунед\n5 · Донат меояд",
 'rf'=>'ДАЪВАТИ ДӮСТОН','rfg'=>'Барои ҳар дӯст %s','rfa'=>'Баъди хариди аввали дӯст',
 'rfi'=>'Даъватшуда','rfs'=>'Бонус','rfl'=>'Линки шумо','rfb'=>'Фиристодан',
 'rfp'=>'Донати бозиҳо арзон'],
'ru' => ['subT'=>'ПОДПИШИТЕСЬ','subGo'=>'Перейти в канал','subChk'=>'Я подписался',
 'subTxt'=>'Чтобы пользоваться ботом, подпишитесь на наш канал.',
 'subWhy'=>'В канале: скидки, новые игры, новости и ответы на вопросы.',
 'subNo'=>'Вы ещё не подписаны',
 'skip'=>'Пропустить','revPub'=>'Ваш отзыв опубликован в канале — спасибо!','revQ'=>'Как прошло обслуживание?','revTh'=>'Спасибо за оценку!',
 'revAsk'=>'Напишите пару слов — отзыв попадёт в канал.',
 'revBad'=>'Извините! Что пошло не так? Напишите — исправим.','revOk'=>'Спасибо за отзыв!',
 'app'=>'▸ ОТКРЫТЬ ПРИЛОЖЕНИЕ','shop'=>'КАТАЛОГ','wallet'=>'КОШЕЛЁК','ord'=>'ЗАКАЗЫ',
 'ref'=>'ДРУЗЬЯ','help'=>'ПОМОЩЬ','lang'=>'ЯЗЫК','rev'=>'ОТЗЫВЫ','adm'=>'АДМИН','back'=>'‹ Назад',
 'hi'=>'Добро пожаловать','sub'=>'Донат игр — быстро, дёшево, круглосуточно.','tap'=>'Откройте приложение',
 'phone'=>'Для регистрации отправьте номер телефона','phb'=>'Отправить номер',
 'reg'=>'Регистрация завершена','own'=>'Отправьте свой номер',
 'bal'=>'Баланс','spent'=>'Потрачено','cnt'=>'Заказы','topup'=>'Для пополнения откройте приложение',
 'noord'=>'Заказов нет','myord'=>'ВАШИ ЗАКАЗЫ','lng'=>'Выберите язык','lok'=>'Язык изменён',
 'fast'=>'Слишком быстро, подождите','blk'=>'Доступ закрыт','q'=>'Есть вопрос?',
 'hlp'=>"ПОМОЩЬ\n\n1 · Выберите игру\n2 · Введите ID\n3 · Выберите пакет\n4 · Пополните кошелёк\n5 · Донат придёт",
 'rf'=>'ПРИГЛАШЕНИЕ ДРУЗЕЙ','rfg'=>'За каждого друга %s','rfa'=>'После первой покупки друга',
 'rfi'=>'Приглашено','rfs'=>'Бонус','rfl'=>'Ваша ссылка','rfb'=>'Отправить',
 'rfp'=>'Дешёвый донат игр'],
'uz' => ['subT'=>'OBUNA BOʻLING','subGo'=>'Kanalga oʻtish','subChk'=>'Men obuna boʻldim',
 'subTxt'=>'Botdan foydalanish uchun kanalimizga obuna boʻling.',
 'subWhy'=>'Kanalda: chegirmalar, yangi oʻyinlar, yangiliklar.',
 'subNo'=>'Siz hali obuna boʻlmagansiz',
 'skip'=>'Oʻtkazish','revPub'=>'Sharhingiz kanalga joylandi — rahmat!','revQ'=>'Xizmat qanday boʻldi?','revTh'=>'Baho uchun rahmat!',
 'revAsk'=>'Ikki ogʻiz yozing — sharh kanalga chiqadi.',
 'revBad'=>'Kechirasiz! Nima notoʻgʻri boʻldi?','revOk'=>'Sharh uchun rahmat!',
 'app'=>'▸ ILOVANI OCHISH','shop'=>'KATALOG','wallet'=>'HAMYON','ord'=>'BUYURTMALAR',
 'ref'=>"DO'STLAR",'help'=>'YORDAM','lang'=>'TIL','rev'=>'SHARHLAR','adm'=>'ADMIN','back'=>'‹ Orqaga',
 'hi'=>'Xush kelibsiz','sub'=>"O'yin donati — tez, arzon, 24/7.",'tap'=>'Ilovani oching',
 'phone'=>"Ro'yxatdan o'tish uchun raqamingizni yuboring",'phb'=>'Raqamni yuborish',
 'reg'=>"Ro'yxatdan o'tish tugadi",'own'=>"O'z raqamingizni yuboring",
 'bal'=>'Balans','spent'=>'Sarflandi','cnt'=>'Buyurtmalar','topup'=>"To'ldirish uchun ilovani oching",
 'noord'=>"Buyurtma yo'q",'myord'=>'BUYURTMALARINGIZ','lng'=>'Tilni tanlang','lok'=>"Til o'zgardi",
 'fast'=>'Juda tez, kuting','blk'=>'Kirish yopiq','q'=>'Savolingiz bormi?',
 'hlp'=>"YORDAM\n\n1 · O'yinni tanlang\n2 · ID kiriting\n3 · Paketni tanlang\n4 · Hamyonni to'ldiring\n5 · Donat keladi",
 'rf'=>"DO'STLARNI TAKLIF QILISH",'rfg'=>"Har bir do'st uchun %s",'rfa'=>"Do'stning birinchi xarididan keyin",
 'rfi'=>'Taklif qilingan','rfs'=>'Bonus','rfl'=>'Havolangiz','rfb'=>'Yuborish',
 'rfp'=>"Arzon o'yin donati"],
'ky' => ['subT'=>'ЖАЗЫЛЫҢЫЗ','subGo'=>'Каналга өтүү','subChk'=>'Мен жазылдым',
 'subTxt'=>'Ботту колдонуу үчүн каналыбызга жазылыңыз.',
 'subWhy'=>'Каналда: арзандатуулар, жаңы оюндар, жаңылыктар.',
 'subNo'=>'Сиз азырынча жазылган жоксуз',
 'skip'=>'Өткөрүү','revPub'=>'Пикириңиз каналга жарыяланды — рахмат!','revQ'=>'Тейлөө кандай болду?','revTh'=>'Баа үчүн рахмат!',
 'revAsk'=>'Бир нече сөз жазыңыз — пикир каналга чыгат.',
 'revBad'=>'Кечиресиз! Эмне туура эмес болду?','revOk'=>'Пикир үчүн рахмат!',
 'app'=>'▸ КОЛДОНМОНУ АЧУУ','shop'=>'КАТАЛОГ','wallet'=>'КАПЧЫК','ord'=>'БУЙРУТМАЛАР',
 'ref'=>'ДОСТОР','help'=>'ЖАРДАМ','lang'=>'ТИЛ','rev'=>'ПИКИРЛЕР','adm'=>'АДМИН','back'=>'‹ Артка',
 'hi'=>'Кош келиңиз','sub'=>'Оюн донаты — тез, арзан, 24/7.','tap'=>'Колдонмону ачыңыз',
 'phone'=>'Катталуу үчүн номериңизди жөнөтүңүз','phb'=>'Номерди жөнөтүү',
 'reg'=>'Катталуу аяктады','own'=>'Өз номериңизди жөнөтүңүз',
 'bal'=>'Баланс','spent'=>'Жумшалды','cnt'=>'Буйрутмалар','topup'=>'Толтуруу үчүн колдонмону ачыңыз',
 'noord'=>'Буйрутма жок','myord'=>'СИЗДИН БУЙРУТМАЛАР','lng'=>'Тилди тандаңыз','lok'=>'Тил өзгөрдү',
 'fast'=>'Өтө тез, күтө туруңуз','blk'=>'Кирүү жабык','q'=>'Сурооңуз барбы?',
 'hlp'=>"ЖАРДАМ\n\n1 · Оюнду тандаңыз\n2 · ID киргизиңиз\n3 · Пакетти тандаңыз\n4 · Капчыкты толтуруңуз\n5 · Донат келет",
 'rf'=>'ДОСТОРДУ ЧАКЫРУУ','rfg'=>'Ар бир дос үчүн %s','rfa'=>'Достун биринчи сатып алуусунан кийин',
 'rfi'=>'Чакырылган','rfs'=>'Бонус','rfl'=>'Шилтемеңиз','rfb'=>'Жөнөтүү',
 'rfp'=>'Арзан оюн донаты'],
'en' => ['subT'=>'SUBSCRIBE','subGo'=>'Open channel','subChk'=>'I subscribed',
 'subTxt'=>'To use the bot, please subscribe to our channel.',
 'subWhy'=>'In the channel: discounts, new games, news and answers.',
 'subNo'=>'You are not subscribed yet',
 'skip'=>'Skip','revPub'=>'Your review is now in our channel — thank you!','revQ'=>'How was the service?','revTh'=>'Thanks for the rating!',
 'revAsk'=>'Write a few words — your review goes to the channel.',
 'revBad'=>'Sorry! What went wrong? Tell us and we will fix it.','revOk'=>'Thanks for your review!',
 'app'=>'▸ OPEN APP','shop'=>'CATALOG','wallet'=>'WALLET','ord'=>'ORDERS',
 'ref'=>'FRIENDS','help'=>'HELP','lang'=>'LANGUAGE','rev'=>'REVIEWS','adm'=>'ADMIN','back'=>'‹ Back',
 'hi'=>'Welcome','sub'=>'Game top-ups — fast, cheap, 24/7.','tap'=>'Open the app',
 'phone'=>'Share your phone number to register','phb'=>'Share phone number',
 'reg'=>'Registration complete','own'=>'Please share your own number',
 'bal'=>'Balance','spent'=>'Spent','cnt'=>'Orders','topup'=>'Open the app to top up',
 'noord'=>'No orders','myord'=>'YOUR ORDERS','lng'=>'Choose language','lok'=>'Language changed',
 'fast'=>'Too fast, please wait','blk'=>'Access denied','q'=>'Have a question?',
 'hlp'=>"HELP\n\n1 · Choose a game\n2 · Enter your ID\n3 · Choose a package\n4 · Top up wallet\n5 · Delivery is automatic",
 'rf'=>'INVITE FRIENDS','rfg'=>'Get %s per friend','rfa'=>"After your friend's first purchase",
 'rfi'=>'Invited','rfs'=>'Bonus','rfl'=>'Your link','rfb'=>'Share',
 'rfp'=>'Cheap game top-ups'],
'kk' => ['subT'=>'ЖАЗЫЛЫҢЫЗ','subGo'=>'Арнаға өту','subChk'=>'Мен жазылдым',
 'subTxt'=>'Ботты пайдалану үшін арнамызға жазылыңыз.',
 'subWhy'=>'Арнада: жеңілдіктер, жаңа ойындар, жаңалықтар.',
 'subNo'=>'Сіз әлі жазылмағансыз',
 'skip'=>'Өткізу','revPub'=>'Пікіріңіз арнада жарияланды — рахмет!','revQ'=>'Қызмет қалай болды?','revTh'=>'Баға үшін рахмет!',
 'revAsk'=>'Бірнеше сөз жазыңыз — пікір арнаға шығады.',
 'revBad'=>'Кешіріңіз! Не дұрыс болмады?','revOk'=>'Пікір үшін рахмет!',
 'app'=>'▸ ҚОЛДАНБАНЫ АШУ','shop'=>'КАТАЛОГ','wallet'=>'ӘМИЯН','ord'=>'ТАПСЫРЫСТАР',
 'ref'=>'ДОСТАР','help'=>'КӨМЕК','lang'=>'ТІЛ','rev'=>'ПІКІРЛЕР','adm'=>'АДМИН','back'=>'‹ Артқа',
 'hi'=>'Қош келдіңіз','sub'=>'Ойын донаты — жылдам, арзан, 24/7.','tap'=>'Қолданбаны ашыңыз',
 'phone'=>'Тіркелу үшін нөміріңізді жіберіңіз','phb'=>'Нөмірді жіберу',
 'reg'=>'Тіркелу аяқталды','own'=>'Өз нөміріңізді жіберіңіз',
 'bal'=>'Баланс','spent'=>'Жұмсалды','cnt'=>'Тапсырыстар','topup'=>'Толтыру үшін қолданбаны ашыңыз',
 'noord'=>'Тапсырыс жоқ','myord'=>'СІЗДІҢ ТАПСЫРЫСТАР','lng'=>'Тілді таңдаңыз','lok'=>'Тіл өзгерді',
 'fast'=>'Тым жылдам, күте тұрыңыз','blk'=>'Кіру жабық','q'=>'Сұрағыңыз бар ма?',
 'hlp'=>"КӨМЕК\n\n1 · Ойынды таңдаңыз\n2 · ID енгізіңіз\n3 · Пакетті таңдаңыз\n4 · Әмиянды толтырыңыз\n5 · Донат келеді",
 'rf'=>'ДОСТАРДЫ ШАҚЫРУ','rfg'=>'Әр дос үшін %s','rfa'=>'Достың алғашқы сатып алуынан кейін',
 'rfi'=>'Шақырылған','rfs'=>'Бонус','rfl'=>'Сілтемеңіз','rfb'=>'Жіберу',
 'rfp'=>'Арзан ойын донаты'],
    ];
}
function T(string $k, $uid = null, string $l = ''): string {
    static $t = null;
    if ($t === null) $t = TXT();
    if ($l === '' && $uid !== null) $l = ulang($uid);
    if (!isset($t[$l])) $l = 'tj';
    return $t[$l][$k] ?? ($t['tj'][$k] ?? $k);
}

/* ======================= HELPERS ======================= */

/** Ҳар навъ ишора ба канал → линки дурусти https:// */
function tg_url(string $v): string {
    $v = trim($v);
    if ($v === '') return '';
    if (preg_match('~^https?://~i', $v)) return $v;
    if (str_starts_with($v, 't.me/')) return 'https://' . $v;
    if (str_starts_with($v, '@')) return 'https://t.me/' . substr($v, 1);
    if (preg_match('~^[A-Za-z][A-Za-z0-9_]{3,}$~', $v)) return 'https://t.me/' . $v;
    return '';   // -100... ва ғайра — тугма намесозем
}

/** Линки WhatsApp бо матни тайёр */
function wa_link($uid = null): string {
    $ph = preg_replace('/\D/', '', cfg('wa', ''));
    if ($ph === '') return '';
    $shop = cfg('shop', 'ZVER TAJ');
    $txt  = "Салом! Ман аз бот «{$shop}» менависам.";
    if ($uid) $txt .= "\nID: {$uid}";
    $txt .= "\n\nСаволам: ";
    return 'https://wa.me/' . $ph . '?text=' . rawurlencode($txt);
}

/** Рӯйхати админҳо — асосӣ якум */
function admins_list(): array {
    $l = ADMINS;
    $extra = trim(cfg('admins', ''));
    if ($extra !== '') {
        foreach (preg_split('~[,\s]+~', $extra) as $a) {
            $a = (int)trim($a);
            if ($a > 0 && !in_array($a, $l, true)) $l[] = $a;
        }
    }
    return $l;
}

/** Линки WhatsApp барои чеки радшуда */
function wa_reject($uid, int $tid, string $why = ''): string {
    $ph = preg_replace('/\D/', '', cfg('wa', ''));
    if ($ph === '') return '';
    $shop = cfg('shop', 'ZVER TAJ');
    $txt  = "Салом! «{$shop}» — пардохти ман тасдиқ нашуд.\n"
          . "Дархост: #{$tid}\nID: {$uid}\n"
          . ($why !== '' ? "Сабаб: {$why}\n" : '')
          . "\nЧекро мефиристам:";
    return 'https://wa.me/' . $ph . '?text=' . rawurlencode($txt);
}

function app_url(): string {
    $host = $_SERVER['HTTP_HOST'] ?? '';
    $dir  = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/');
    $v    = (int)@filemtime(__DIR__ . '/zapp.php');
    return 'https://' . $host . $dir . '/zapp.php' . ($v ? '?v=' . $v : '');
}
function bot_user(): string {
    $u = cfg('bot_user', '');
    if ($u !== '') return $u;
    $r = tg('getMe');
    $u = (string)($r['result']['username'] ?? '');
    if ($u !== '') setcfg('bot_user', $u);
    return $u;
}
function set_st($uid, ?string $st, array $d = []): void {
    q("INSERT INTO z_state (uid,st,data,at) VALUES (?,?,?,?)
       ON DUPLICATE KEY UPDATE st=VALUES(st), data=VALUES(data), at=VALUES(at)",
      [$uid, $st, json_encode($d, JSON_UNESCAPED_UNICODE), time()]);
}
function get_st($uid): array {
    $r = one("SELECT st,data FROM z_state WHERE uid=?", [$uid]);
    return $r ? ['st' => $r['st'], 'data' => json_decode((string)$r['data'], true) ?: []]
              : ['st' => null, 'data' => []];
}
function clr_st($uid): void { set_st($uid, null, []); }

function verify_init(string $init): ?array {
    if ($init === '') return null;
    parse_str($init, $d);
    if (empty($d['hash'])) return null;
    $hash = (string)$d['hash']; unset($d['hash']);
    ksort($d);
    $pairs = [];
    foreach ($d as $k => $v) $pairs[] = $k . '=' . $v;
    $sec  = hash_hmac('sha256', BOT_TOKEN, 'WebAppData', true);
    $calc = hash_hmac('sha256', implode("\n", $pairs), $sec);
    if (!hash_equals($calc, $hash)) return null;
    if (isset($d['auth_date']) && (time() - (int)$d['auth_date']) > 86400) return null;
    $u = json_decode((string)($d['user'] ?? ''), true);
    return is_array($u) ? $u : null;
}
function jout(array $d, int $code = 200): void {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($d, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

/**
 * Ҷавобро фавран ба муштарӣ медиҳем, вале скрипт кор мекунад.
 * Танҳо дар серверҳое ки инро дастгирӣ мекунанд (FastCGI / LiteSpeed).
 * Дар ҷои дигар false бармегардонад — он гоҳ ҷавоби оддӣ дода мешавад.
 */
function jflush(array $d, int $code = 200): bool {
    $fn = function_exists('fastcgi_finish_request') ? 'fastcgi_finish_request'
        : (function_exists('litespeed_finish_request') ? 'litespeed_finish_request' : '');
    if ($fn === '') return false;

    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($d, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

    @ignore_user_abort(true);
    while (ob_get_level() > 0) { @ob_end_flush(); }
    @flush();
    try { @$fn(); } catch (Throwable $e) {}
    return true;
}

/** file_id → доимии URL (кэш дар z_settings) */
function tg_file_url(?string $fid): ?string {
    $fid = trim((string)$fid);
    if ($fid === '') return null;
    $key = 'furl_' . substr(md5($fid), 0, 20);
    $u = cfg($key, '');
    if ($u !== '') return $u;
    $r = tg('getFile', ['file_id' => $fid]);
    $path = (string)($r['result']['file_path'] ?? '');
    if ($path === '') return null;
    $u = 'https://api.telegram.org/file/bot' . BOT_TOKEN . '/' . $path;
    setcfg($key, $u);
    return $u;
}

/* ======================= МЕНЮ ======================= */

function kb_main($uid): array {
    $r = [
        [['text' => T('app', $uid), 'web_app' => ['url' => app_url()]]],
        [['text' => T('wallet', $uid), 'callback_data' => 'w'],
         ['text' => T('ord', $uid), 'callback_data' => 'o:0']],
        [['text' => T('ref', $uid), 'callback_data' => 'r'],
         ['text' => T('lang', $uid), 'callback_data' => 'l']],
    ];
    $rev = tg_url(cfg('reviews', ''));
    if ($rev !== '') $r[] = [['text' => T('rev', $uid), 'url' => $rev],
                             ['text' => T('help', $uid), 'callback_data' => 'h']];
    else $r[] = [['text' => T('help', $uid), 'callback_data' => 'h']];

    $wa = wa_link($uid);
    if ($wa !== '') $r[] = [['text' => '✆ WHATSAPP', 'url' => $wa]];
    if (is_admin($uid)) $r[] = [['text' => T('adm', $uid), 'callback_data' => 'a']];
    return $r;
}
function kb_langs(string $cur = ''): array {
    $rows = []; $line = [];
    foreach (lang_list() as $c => $n) {
        $line[] = ['text' => ($c === $cur ? '● ' : '') . $n, 'callback_data' => 'lang:' . $c];
        if (count($line) === 2) { $rows[] = $line; $line = []; }
    }
    if ($line) $rows[] = $line;
    return $rows;
}
function main_text($uid): string {
    $w = trim(cfg('welcome', ''));
    return "<b>" . h(cfg('shop', 'ZVER TAJ')) . "</b>\n"
         . "<code>───────────────</code>\n"
         . h(T('hi', $uid)) . ". " . h($w !== '' ? $w : T('sub', $uid)) . "\n\n"
         . "▸ " . h(T('tap', $uid));
}
function show_main($chat, $mid, $uid): void {
    $t = main_text($uid);
    $mid ? ed($chat, $mid, $t, kb_main($uid)) : say($chat, $t, kb_main($uid));
}



/* ============ МИНТАҚА ва КАТЕГОРИЯ ============ */

function reg_dict(): array {
    return [
        'global'=>['GLOBAL','Global','🌐'],  'world'=>['GLOBAL','Global','🌐'],
        'indonesia'=>['ID','Indonesia','🇮🇩'], 'brazil'=>['BR','Brazil','🇧🇷'],
        'brasil'=>['BR','Brazil','🇧🇷'],      'india'=>['IN','India','🇮🇳'],
        'bangladesh'=>['BD','Bangladesh','🇧🇩'],'pakistan'=>['PK','Pakistan','🇵🇰'],
        'sgmy'=>['SGMY','SG / MY','🇸🇬'],      'singapore'=>['SG','Singapore','🇸🇬'],
        'malaysia'=>['MY','Malaysia','🇲🇾'],   'thailand'=>['TH','Thailand','🇹🇭'],
        'vietnam'=>['VN','Vietnam','🇻🇳'],     'philippines'=>['PH','Philippines','🇵🇭'],
        'russia'=>['RU','Russia','🇷🇺'],       'turkey'=>['TR','Turkey','🇹🇷'],
        'egypt'=>['EG','Egypt','🇪🇬'],         'mena'=>['MENA','MENA','🌍'],
        'middle east'=>['MENA','MENA','🌍'],   'europe'=>['EU','Europe','🇪🇺'],
        'latam'=>['LATAM','LATAM','🌎'],       'taiwan'=>['TW','Taiwan','🇹🇼'],
        'korea'=>['KR','Korea','🇰🇷'],         'japan'=>['JP','Japan','🇯🇵'],
        'china'=>['CN','China','🇨🇳'],         'usa'=>['US','USA','🇺🇸'],
        'uae'=>['AE','UAE','🇦🇪'],             'saudi'=>['SA','Saudi','🇸🇦'],
        'nepal'=>['NP','Nepal','🇳🇵'],         'myanmar'=>['MM','Myanmar','🇲🇲'],
        'cambodia'=>['KH','Cambodia','🇰🇭'],   'kazakhstan'=>['KZ','Kazakhstan','🇰🇿'],
        'tajikistan'=>['TJ','Tajikistan','🇹🇯'],
        'cis'=>['CIS','СНГ','🌍'],  'снг'=>['CIS','СНГ','🌍'],
        'my/sg'=>['MYSG','MY / SG','🇲🇾'], 'my sg'=>['MYSG','MY / SG','🇲🇾'],
        'sg/my'=>['SGMY','SG / MY','🇸🇬'], 'sg my'=>['SGMY','SG / MY','🇸🇬'],
        'ru/kz'=>['CIS','СНГ','🌍'],       'na/eu'=>['NAEU','NA / EU','🌎'],
        'sea'=>['SEA','SEA','🌏'],         'apac'=>['APAC','APAC','🌏'],
        'ru/cis'=>['CIS','СНГ','🌍'], 'ru cis'=>['CIS','СНГ','🌍'],
        'asia'=>['ASIA','Asia','🌏'],  'africa'=>['AF','Africa','🌍'],
        'north america'=>['NA','North America','🌎'],
        'south america'=>['SA2','South America','🌎'],
        // кӯтоҳ (Free Fire Sg, PUBG BR ва ғ.)
        'sg'=>['SG','Singapore','🇸🇬'],   'my'=>['MY','Malaysia','🇲🇾'],
        'br'=>['BR','Brazil','🇧🇷'],      'bd'=>['BD','Bangladesh','🇧🇩'],
        'id'=>['ID','Indonesia','🇮🇩'],   'in'=>['IN','India','🇮🇳'],
        'pk'=>['PK','Pakistan','🇵🇰'],    'th'=>['TH','Thailand','🇹🇭'],
        'vn'=>['VN','Vietnam','🇻🇳'],     'ph'=>['PH','Philippines','🇵🇭'],
        'ru'=>['RU','Russia','🇷🇺'],      'tr'=>['TR','Turkey','🇹🇷'],
        'eg'=>['EG','Egypt','🇪🇬'],       'eu'=>['EU','Europe','🇪🇺'],
        'tw'=>['TW','Taiwan','🇹🇼'],      'kr'=>['KR','Korea','🇰🇷'],
        'jp'=>['JP','Japan','🇯🇵'],       'cn'=>['CN','China','🇨🇳'],
        'us'=>['US','USA','🇺🇸'],         'ae'=>['AE','UAE','🇦🇪'],
        'sa'=>['SA','Saudi','🇸🇦'],       'np'=>['NP','Nepal','🇳🇵'],
        'mm'=>['MM','Myanmar','🇲🇲'],     'kh'=>['KH','Cambodia','🇰🇭'],
        'kz'=>['KZ','Kazakhstan','🇰🇿'],  'tj'=>['TJ','Tajikistan','🇹🇯'],
        'gl'=>['GLOBAL','Global','🌐'],
    ];
}
function split_reg(string $name): array {
    $d = reg_dict();
    $low = mb_strtolower(trim($name));

    // "Free Fire (MY/SG)" → база "free fire", минтақа "my/sg"
    if (preg_match('~^(.*?)\s*\(([^)]+)\)\s*$~u', $low, $mm)) {
        $b = trim($mm[1]);
        $inside = trim($mm[2]);
        if ($b !== '' && mb_strlen($b) >= 3) {
            if (isset($d[$inside])) {
                return ['base' => $b, 'code' => $d[$inside][0],
                        'flag' => $d[$inside][2], 'label' => $d[$inside][1]];
            }
            // номаълум — худи матнро код мегирем
            $code = mb_strtoupper(preg_replace('~[^a-z0-9]+~', '', $inside));
            if ($code !== '' && mb_strlen($code) <= 8) {
                return ['base' => $b, 'code' => $code, 'flag' => '🌍', 'label' => mb_strtoupper($inside)];
            }
        }
    }
    $keys = array_keys($d);
    usort($keys, fn($a, $b) => mb_strlen($b) <=> mb_strlen($a));
    foreach ($keys as $k) {
        if (preg_match('~^(.*?)[\s\-\(]+' . preg_quote($k, '~') . '\)?\s*$~iu', $low, $m)) {
            $b = trim($m[1], " -()\t");
            if ($b !== '') return ['base' => $b, 'code' => $d[$k][0], 'flag' => $d[$k][2]];
        }
    }
    return ['base' => $low, 'code' => 'GLOBAL', 'flag' => '🌐', 'label' => 'Global'];
}
function reg_label(string $code): string {
    foreach (reg_dict() as $v) if ($v[0] === $code) return $v[1];
    return $code;
}
function nicebase(string $b): string { return mb_convert_case(trim($b), MB_CASE_TITLE, 'UTF-8'); }

/**
 * Категорияи пакет. Тартиб қатъӣ:
 * 1) ваучер  2) обуна  3) пропуск  4) набор  5) асъор (алмос/UC/танга...)
 */
function pack_cat(string $n): string {
    $x = ' ' . mb_strtolower(trim($n)) . ' ';

    // --- 1. ВАУЧЕР / КОРТИ ТӮҲФА ---
    if (preg_match('~\b(voucher|vouchers|gift ?card|redeem|coupon|promo ?code)\b~', $x)) return 'voucher';

    // --- 2. ОБУНА (вақт дорад: моҳона, ҳафтаина) ---
    if (preg_match('~\b(membership|member|subscription|subscribe|prime|plus)\b~', $x)
        || preg_match('~\b(monthly|weekly|daily|yearly|annual)\b~', $x)
        || preg_match('~\b(evo ?access|access)\b~', $x)
        || preg_match('~\b\d+\s*(day|days|month|months|week|weeks)\b~', $x)) return 'sub';

    // --- 3. ПРОПУСК ---
    if (preg_match('~\b(pass|passes|elite|royale|royal|booyah|level ?up|battle ?pass)\b~', $x))
        return 'pass';

    // --- 4. НАБОР ---
    if (preg_match('~\b(pack|packs|bundle|box|crate|kit|chest|combo|set)\b~', $x)) return 'pack';

    // --- 5. АСЪОР ---
    if (preg_match('~\b(diamond|diamonds|алмаз|алмос|elmas|berlian|kim cương|💎)~u', $x)
        || preg_match('~\bdm\b~', $x)) return 'diamond';
    if (preg_match('~\buc\b~', $x) || str_contains($x, 'unknown cash')) return 'uc';
    if (preg_match('~\b(gem|gems|crystal|crystals)\b~', $x)) return 'gem';
    if (preg_match('~\b(coin|coins|gold)\b~', $x)) return 'coin';
    if (preg_match('~\b(star|stars)\b~', $x)) return 'star';
    if (preg_match('~\b(token|tokens|shard|shards)\b~', $x)) return 'token';
    if (preg_match('~\b(credit|credits|cash|wallet|balance|topup|top ?up)\b~', $x)) return 'credit';

    return 'main';
}

/**
 * Пакетҳои бе калидвожа (масалан танҳо "110") ба асъори асосии
 * ҳамон бозӣ дода мешаванд — то ки дар «ДИГАР» намонанд.
 */
function fix_game_cats(int $gameId): void {
    $rows = all("SELECT id,name,cat FROM z_packs WHERE game_id=?", [$gameId]);
    if (!$rows) return;

    $cur = ['diamond' => 0, 'uc' => 0, 'coin' => 0, 'gem' => 0,
            'star' => 0, 'token' => 0, 'credit' => 0];
    foreach ($rows as $r) if (isset($cur[$r['cat']])) $cur[$r['cat']]++;
    arsort($cur);
    $main = key($cur);
    if (($cur[$main] ?? 0) === 0) $main = null;

    foreach ($rows as $r) {
        if ($r['cat'] !== 'main') continue;
        // танҳо рақам ё рақам + матни кӯтоҳ → асъори асосӣ
        $isNum = preg_match('~^\s*[\d\s.,+]+~', (string)$r['name']);
        $to = ($isNum && $main) ? $main : 'pack';
        q("UPDATE z_packs SET cat=? WHERE id=?", [$to, $r['id']]);
    }
}

function cat_name(string $c, string $l = 'tj'): string {
    $m = [
     'diamond'=>['tj'=>'АЛМОСҲО','ru'=>'АЛМАЗЫ','uz'=>'OLMOSLAR','ky'=>'АЛМАЗДАР','en'=>'DIAMONDS','kk'=>'АЛМАЗДАР'],
     'uc'     =>['tj'=>'UC','ru'=>'UC','uz'=>'UC','ky'=>'UC','en'=>'UC','kk'=>'UC'],
     'coin'   =>['tj'=>'ТАНГАҲО','ru'=>'МОНЕТЫ','uz'=>'TANGALAR','ky'=>'МОНЕТАЛАР','en'=>'COINS','kk'=>'МОНЕТАЛАР'],
     'gem'    =>['tj'=>'ГАВҲАРҲО','ru'=>'КРИСТАЛЛЫ','uz'=>'GAVHARLAR','ky'=>'КРИСТАЛЛДАР','en'=>'GEMS','kk'=>'КРИСТАЛДАР'],
     'star'   =>['tj'=>'СИТОРАҲО','ru'=>'ЗВЁЗДЫ','uz'=>'YULDUZLAR','ky'=>'ЖЫЛДЫЗДАР','en'=>'STARS','kk'=>'ЖҰЛДЫЗДАР'],
     'token'  =>['tj'=>'ЖЕТОНҲО','ru'=>'ЖЕТОНЫ','uz'=>'JETONLAR','ky'=>'ЖЕТОНДОР','en'=>'TOKENS','kk'=>'ЖЕТОНДАР'],
     'credit' =>['tj'=>'БАЛАНС','ru'=>'БАЛАНС','uz'=>'BALANS','ky'=>'БАЛАНС','en'=>'CREDITS','kk'=>'БАЛАНС'],
     'pass'   =>['tj'=>'ПРОПУСКҲО','ru'=>'ПРОПУСКИ','uz'=>'PASSLAR','ky'=>'ПРОПУСКТАР','en'=>'PASSES','kk'=>'ПРОПУСКТАР'],
     'pack'   =>['tj'=>'НАБОРҲО','ru'=>'НАБОРЫ','uz'=>"TO'PLAMLAR",'ky'=>'ТОПТОМДОР','en'=>'PACKS','kk'=>'ЖИЫНТЫҚТАР'],
     'sub'    =>['tj'=>'ОБУНА','ru'=>'ПОДПИСКА','uz'=>'OBUNA','ky'=>'ЖАЗЫЛУУ','en'=>'SUBS','kk'=>'ЖАЗЫЛЫМ'],
     'voucher'=>['tj'=>'ВАУЧЕРҲО','ru'=>'ВАУЧЕРЫ','uz'=>'VAUCHERLAR','ky'=>'ВАУЧЕРЛЕР','en'=>'VOUCHERS','kk'=>'ВАУЧЕРЛЕР'],
     'main'   =>['tj'=>'ДИГАР','ru'=>'ДРУГОЕ','uz'=>'BOSHQA','ky'=>'БАШКА','en'=>'OTHER','kk'=>'БАСҚА'],
    ];
    return $m[$c][$l] ?? ($m[$c]['tj'] ?? mb_strtoupper($c));
}


/* ---- ёрирасонҳои ҳатмӣ ---- */

function reg_rank(string $code): int {
    $top = ['CIS' => 0, 'RU' => 1, 'KZ' => 2, 'GLOBAL' => 3, 'EU' => 4];
    return $top[$code] ?? 50;
}
function sort_regs(array &$rows): void {
    usort($rows, function ($a, $b) {
        $ra = reg_rank((string)($a['code'] ?? ''));
        $rb = reg_rank((string)($b['code'] ?? ''));
        if ($ra !== $rb) return $ra <=> $rb;
        return strcmp((string)($a['code'] ?? ''), (string)($b['code'] ?? ''));
    });
}

function pack_disable_if_gone(int $packId, string $msg): bool {
    $m = mb_strtolower($msg);
    $gone = str_contains($m, 'not available') || str_contains($m, 'not_available')
         || str_contains($m, 'out of stock') || str_contains($m, 'unavailable')
         || str_contains($m, 'offer_not_found');
    if (!$gone || $packId <= 0) return false;
    q("UPDATE z_packs SET active=0 WHERE id=?", [$packId]);
    $p = one("SELECT p.name, g.name gname FROM z_packs p
              LEFT JOIN z_games g ON g.id=p.game_id WHERE p.id=?", [$packId]);
    foreach (ADMINS as $a) {
        say($a, "⚠︎ <b>ПАКЕТ ХОМӮШ ШУД</b>\n" . h((string)($p['gname'] ?? ''))
            . " · " . h((string)($p['name'] ?? '')));
    }
    return true;
}

function regroup(): array {
    $n = 0; $groups = [];
    foreach (all("SELECT id,name FROM z_games") as $g) {
        $r = split_reg((string)$g['name']);
        q("UPDATE z_games SET base=?, region=?, flag=? WHERE id=?",
          [mb_substr($r['base'], 0, 110), $r['code'], $r['flag'], $g['id']]);
        $groups[$r['base']] = true;
        $n++;
    }
    $c = 0;
    foreach (all("SELECT id,name FROM z_packs") as $p) {
        q("UPDATE z_packs SET cat=? WHERE id=?", [pack_cat((string)$p['name']), $p['id']]);
        $c++;
    }
    foreach (all("SELECT id FROM z_games") as $g) {
        try { fix_game_cats((int)$g['id']); } catch (Throwable $e) {}
    }
    return ['games' => $n, 'groups' => count($groups), 'packs' => $c];
}








/* ============ АВТОҚАБУЛИ ПАРДОХТ (аз бонк) ============ */

function bankpay(): void {
    ensure_tables();
    header('Content-Type: application/json; charset=utf-8');
    $raw = (string)file_get_contents('php://input');
    $in  = json_decode($raw, true) ?: [];

    if (($in['secret'] ?? '') !== SECRET) {
        http_response_code(403);
        echo json_encode(['ok' => false, 'error' => 'FORBIDDEN']);
        exit;
    }

    $amount = round((float)($in['amount'] ?? 0), 2);
    $opNo   = trim((string)($in['op_no'] ?? ''));
    $topId  = (int)($in['top_id'] ?? 0);
    $cmt    = trim((string)($in['comment'] ?? ''));

    if ($amount <= 0) { echo json_encode(['ok' => false, 'error' => 'NO_AMOUNT']); exit; }

    // 1) такрор?
    if ($opNo !== '') {
        $old = one("SELECT id, matched FROM z_bank WHERE op_no=?", [$opNo]);
        if ($old) { echo json_encode(['ok' => false, 'error' => 'DUPLICATE']); exit; }
    }

    // сабти уведомление
    q("INSERT INTO z_bank (op_no,amount,top_id,comment,op_date,op_time,card,sender,raw,created_at)
       VALUES (?,?,?,?,?,?,?,?,?,?)",
      [$opNo !== '' ? $opNo : null, $amount, $topId ?: null,
       mb_substr($cmt, 0, 110) ?: null,
       mb_substr((string)($in['date'] ?? ''), 0, 20) ?: null,
       mb_substr((string)($in['time'] ?? ''), 0, 12) ?: null,
       mb_substr((string)($in['card'] ?? ''), 0, 36) ?: null,
       mb_substr((string)($in['sender'] ?? ''), 0, 110) ?: null,
       mb_substr((string)($in['raw'] ?? ''), 0, 1400), time()]);
    $bankId = (int)db()->lastInsertId();

    // 2) ҷустуҷӯи дархост
    $t = null;

    // 2a) аз рӯи TOP-рақам — дақиқтарин
    if ($topId > 0) {
        $t = one("SELECT * FROM z_topups WHERE id=? AND status IN ('new','pending')", [$topId]);
        if ($t && abs((float)$t['amount'] - $amount) > 0.5) $t = null;   // маблағ мувофиқ нест
    }

    // 2b) аз рӯи шарҳ (@nick TOP123)
    if (!$t && $cmt !== '' && preg_match('~TOP\s*(\d+)~i', $cmt, $m)) {
        $t = one("SELECT * FROM z_topups WHERE id=? AND status IN ('new','pending')",
                 [(int)$m[1]]);
        if ($t && abs((float)$t['amount'] - $amount) > 0.5) $t = null;
    }

    // 2c) аз рӯи маблағ дар 2 соати охир — аввал онҳое ки чек фиристоданд
    if (!$t) {
        $rows = all("SELECT * FROM z_topups
                     WHERE status IN ('new','pending') AND ABS(amount-?) < 0.01
                       AND created_at > ?
                     ORDER BY (status='pending') DESC, id DESC", [$amount, time() - 7200]);
        if (count($rows) === 1) $t = $rows[0];
        elseif (count($rows) > 1) {
            foreach (ADMINS as $a) {
                say($a, "⚠️ <b>ПАРДОХТ · " . money($amount) . "</b>\n"
                    . "<code>───────────────</code>\n"
                    . count($rows) . " дархост бо ҳамин маблағ.\n"
                    . "Дастӣ тасдиқ кунед.");
            }
            echo json_encode(['ok' => false, 'error' => 'MANY', 'count' => count($rows)]);
            exit;
        }
    }

    if (!$t) {
        foreach (ADMINS as $a) {
            say($a, "💰 <b>ПУЛ ОМАД · " . money($amount) . "</b>\n"
                . "<code>───────────────</code>\n"
                . ($cmt !== '' ? "Шарҳ · <code>" . h($cmt) . "</code>\n" : '')
                . ($opNo !== '' ? "№ " . h($opNo) . "\n" : '')
                . "\n<i>Дархости мувофиқ ёфт нашуд.</i>");
        }
        echo json_encode(['ok' => false, 'error' => 'NO_MATCH']);
        exit;
    }

    // 3) зачисление
    $tid = (int)$t['id'];
    if (!topup_credit($tid, 0, $bankId, true)) {
        echo json_encode(['ok' => false, 'error' => 'ALREADY']);
        exit;
    }

    echo json_encode(['ok' => true, 'topup_id' => $tid, 'uid' => (int)$t['uid'],
                      'amount' => (float)$t['amount']]);
    exit;
}


/**
 * Ҷустуҷӯи уведомленияи бонк барои ин дархост.
 * Агар ёфт шавад — ҳамён худкор пур мешавад.
 */
function bank_match(array $t): ?array {
    ensure_tables();
    $amount = (float)$t['amount'];
    $tid    = (int)$t['id'];
    $since  = (int)$t['created_at'] - 900;   // 15 дақиқа пеш аз дархост

    // 1) шарҳ бо рақами дархост — дақиқтарин
    $r = one("SELECT * FROM z_bank
              WHERE matched IS NULL AND (top_id=? OR comment LIKE ?)
                AND ABS(amount-?) < 0.51 AND created_at > ?
              ORDER BY id DESC LIMIT 1",
             [$tid, '%TOP' . $tid . '%', $amount, $since]);
    if ($r) return $r;

    // 2) танҳо маблағ — агар ягона бошад
    $rows = all("SELECT * FROM z_bank
                 WHERE matched IS NULL AND ABS(amount-?) < 0.01 AND created_at > ?
                 ORDER BY id DESC LIMIT 3", [$amount, $since]);
    if (count($rows) === 1) return $rows[0];

    return null;
}

/** Пур кардани ҳамён — як ҷои ягона барои ҳама роҳҳо */
function topup_credit(int $tid, $adminId, ?int $bankId = null, bool $auto = false,
                      bool $force = false): bool {
    $t = one("SELECT * FROM z_topups WHERE id=?", [$tid]);
    if (!$t) return false;

    // $force = админ дастӣ тасдиқ мекунад — ҳатто агар ИИ ё бонк рад карда бошад.
    // Танҳо 'ok' ҳимоя мешавад, то ки пул ду бор гузошта нашавад.
    if ($force) {
        if ($t['status'] === 'ok') return false;
        $upd = q("UPDATE z_topups SET status='ok', admin_id=?, done_at=?
                  WHERE id=? AND status<>'ok'", [$adminId, time(), $tid]);
    } else {
        if (!in_array($t['status'], ['new', 'pending'], true)) return false;
        $upd = q("UPDATE z_topups SET status='ok', admin_id=?, done_at=?
                  WHERE id=? AND status IN ('new','pending')", [$adminId, time(), $tid]);
    }
    if ($upd->rowCount() === 0) return false;

    q("UPDATE z_users SET balance=balance+? WHERE id=?", [$t['amount'], $t['uid']]);
    tx($t['uid'], 'topup', (float)$t['amount'], 'Пур кардани ҳамён #' . $tid, $tid);
    if ($bankId) { try { q("UPDATE z_bank SET matched=? WHERE id=?", [$tid, $bankId]); }
                   catch (Throwable $e) {} }

    $nb = (float)(one("SELECT balance FROM z_users WHERE id=?", [$t['uid']])['balance'] ?? 0);

    say($t['uid'], "<b>◆ ҲАМЁН ПУР ШУД</b>\n<code>───────────────</code>\n"
        . "+ <b>" . money((float)$t['amount']) . "</b>\n"
        . "Баланс · <b>" . money($nb) . "</b>"
        . ($auto ? "\n\n<i>Пардохти шумо худкор тасдиқ шуд ⚡️</i>" : ''),
        [[['text' => T('app', $t['uid']), 'web_app' => ['url' => app_url()]]]]);

    if ($auto) {
        $u = one("SELECT name, username FROM z_users WHERE id=?", [$t['uid']]);
        foreach (ADMINS as $a) {
            say($a, "⚡️ <b>ХУДКОР ТАСДИҚ ШУД</b>\n<code>───────────────</code>\n"
                . "Дархост · #{$tid}\n"
                . "Муштарӣ · " . h((string)($u['name'] ?? $t['uid']))
                . (!empty($u['username']) ? " @" . h($u['username']) : '') . "\n"
                . "Маблағ · <b>" . money((float)$t['amount']) . "</b>\n"
                . "Баланси муштарӣ · " . money($nb) . "\n\n"
                . "<i>Чек бо уведомленияи бонк мувофиқ омад.</i>");
        }
    }
    return true;
}

/** Дархостҳои интизор — шояд уведомление баъдтар омад */
function bank_recheck(int $limit = 30): array {
    ensure_tables();
    $ok = 0; $rej = 0;
    $wait = max(5, (int)cfg('bank_wait', '20')) * 60;   // чанд дақиқа мунтазир

    foreach (all("SELECT * FROM z_topups WHERE status='pending' AND created_at > ?
                  ORDER BY id DESC LIMIT ?", [time() - 86400, $limit]) as $t) {
        $b = bank_match($t);
        if ($b) {
            if (topup_credit((int)$t['id'], 0, (int)$b['id'], true)) $ok++;
            continue;
        }
        // мӯҳлат гузашт — рад
        if (cfg('bank_reject', '1') === '1'
            && (time() - (int)$t['created_at']) > $wait) {
            if (topup_reject((int)$t['id'], 0, 'no_bank')) $rej++;
        }
        usleep(50000);
    }
    return ['ok' => $ok, 'rej' => $rej];
}

/** Рад кардани дархост бо сабаб */
function topup_reject(int $tid, $adminId, string $why = ''): bool {
    $t = one("SELECT * FROM z_topups WHERE id=?", [$tid]);
    if (!$t || !in_array($t['status'], ['new', 'pending'], true)) return false;

    $upd = q("UPDATE z_topups SET status='no', admin_id=?, done_at=?
              WHERE id=? AND status IN ('new','pending')", [$adminId, time(), $tid]);
    if ($upd->rowCount() === 0) return false;

    $uid = (int)$t['uid'];
    $l = ulang($uid);
    $msg = [
      'tj' => "Мо пардохти шуморо дар бонк наёфтем.\nАгар пул фиристода бошед — ба дастгирӣ нависед.",
      'ru' => "Мы не нашли ваш платёж в банке.\nЕсли вы отправляли деньги — напишите в поддержку.",
      'uz' => "To'lovingiz bankda topilmadi.\nAgar pul yuborgan bo'lsangiz — yordamga yozing.",
      'ky' => "Төлөмүңүз банктан табылган жок.\nАкча жөнөткөн болсоңуз — колдоого жазыңыз.",
      'en' => "We could not find your payment in the bank.\nIf you did send money — contact support.",
      'kk' => "Төлеміңіз банктен табылмады.\nАқша жіберген болсаңыз — қолдауға жазыңыз.",
    ][$l] ?? '';

    $kb = [];
    $wa = wa_reject($uid, $tid, 'bank');
    if ($wa !== '') $kb[] = [['text' => '✆ WHATSAPP', 'url' => $wa]];
    $sup = tg_url(cfg('support', ''));
    if ($sup !== '') $kb[] = [['text' => '✈ TELEGRAM', 'url' => $sup]];

    say($uid, "<b>× ПАРДОХТ ТАСДИҚ НАШУД</b>\n<code>───────────────</code>\n"
        . "Дархост · #{$tid}\n"
        . "Маблағ · <b>" . money((float)$t['amount']) . "</b>\n\n"
        . $msg, $kb ?: null);

    $u = one("SELECT name, username FROM z_users WHERE id=?", [$uid]);
    foreach (ADMINS as $a) {
        say($a, "× <b>ДАРХОСТ РАД ШУД</b> · #{$tid}\n<code>───────────────</code>\n"
            . "Муштарӣ · " . h((string)($u['name'] ?? $uid))
            . (!empty($u['username']) ? " @" . h($u['username']) : '') . "\n"
            . "Маблағ · " . money((float)$t['amount']) . "\n\n"
            . "<i>Дар бонк пардохт ёфт нашуд.</i>",
            [[['text' => '● Ба ҳар ҳол тасдиқ', 'callback_data' => 'at:d:' . $tid]]]);
    }
    return true;
}

/* ============ НАВБАТ (баланси провайдер кам) ============ */

function is_nobalance(string $msg): bool {
    $m = mb_strtolower($msg);
    return str_contains($m, 'insufficient') || str_contains($m, 'not enough')
        || str_contains($m, 'balance') && str_contains($m, 'low')
        || str_contains($m, 'no funds') || str_contains($m, 'недостаточно');
}

function ensure_tables(): void {
    static $done = false;
    if ($done) return;
    $done = true;
    if (cfg('db_ver', '') === VERSION) return;
    foreach ([
      "CREATE TABLE IF NOT EXISTS z_tx (id INT AUTO_INCREMENT PRIMARY KEY,
        uid BIGINT, kind VARCHAR(16), amount DECIMAL(12,2), balance DECIMAL(14,2) DEFAULT 0,
        title VARCHAR(160) NULL, ref_id INT NULL, created_at INT,
        INDEX (uid, id), INDEX (created_at)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
      "CREATE TABLE IF NOT EXISTS z_queue (id INT AUTO_INCREMENT PRIMARY KEY,
        order_id INT UNIQUE, uid BIGINT, tries INT DEFAULT 0,
        last_err VARCHAR(191) NULL, created_at INT, INDEX (uid))
        ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
      "CREATE TABLE IF NOT EXISTS z_checks (id INT AUTO_INCREMENT PRIMARY KEY,
        topup_id INT NULL, uid BIGINT, img_hash VARCHAR(40) NULL, op_no VARCHAR(64) NULL,
        amount DECIMAL(12,2) NULL, op_date VARCHAR(24) NULL, op_time VARCHAR(16) NULL,
        bank VARCHAR(80) NULL, receiver VARCHAR(120) NULL, sender VARCHAR(120) NULL,
        verdict VARCHAR(16) DEFAULT 'ok', reason VARCHAR(191) NULL, raw MEDIUMTEXT NULL,
        created_at INT, INDEX (uid), INDEX (img_hash), INDEX (op_no))
        ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
      "CREATE TABLE IF NOT EXISTS z_bank (id INT AUTO_INCREMENT PRIMARY KEY,
        op_no VARCHAR(64) NULL, amount DECIMAL(12,2), top_id INT NULL,
        comment VARCHAR(120) NULL, op_date VARCHAR(24) NULL, op_time VARCHAR(16) NULL,
        card VARCHAR(40) NULL, sender VARCHAR(120) NULL, matched INT NULL,
        raw TEXT NULL, created_at INT, UNIQUE KEY uq_op (op_no), INDEX (amount))
        ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
      "CREATE TABLE IF NOT EXISTS z_reviews (id INT AUTO_INCREMENT PRIMARY KEY,
        uid BIGINT, order_id INT, stars TINYINT, txt TEXT NULL,
        posted TINYINT DEFAULT 0, created_at INT, UNIQUE KEY uq_rev (order_id))
        ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
      "CREATE TABLE IF NOT EXISTS z_promo (id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(32) UNIQUE, kind VARCHAR(8) DEFAULT 'pct', val DECIMAL(10,2),
        min_sum DECIMAL(12,2) DEFAULT 0, max_uses INT DEFAULT 0, per_user INT DEFAULT 1,
        used INT DEFAULT 0, saved DECIMAL(14,2) DEFAULT 0, until INT NULL,
        active TINYINT DEFAULT 1, created_at INT) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
      "CREATE TABLE IF NOT EXISTS z_promo_use (id INT AUTO_INCREMENT PRIMARY KEY,
        promo_id INT, uid BIGINT, order_id INT NULL, sum_off DECIMAL(12,2), at INT,
        INDEX (promo_id), INDEX (uid)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
    ] as $sql) { try { db()->exec($sql); } catch (Throwable $e) {} }

    tx_backfill();
}

/* ======================= ТАЪРИХИ ҲАМЁН ======================= */

/**
 * Сабти ҳар тағйироти баланс.
 * $amount: + пур кардан / баргардонидан, − харид
 */
function tx($uid, string $kind, float $amount, string $title = '', ?int $refId = null): void {
    try {
        $bal = (float)(one("SELECT balance FROM z_users WHERE id=?", [$uid])['balance'] ?? 0);
        q("INSERT INTO z_tx (uid,kind,amount,balance,title,ref_id,created_at)
           VALUES (?,?,?,?,?,?,?)",
          [$uid, $kind, round($amount, 2), $bal, mb_substr($title, 0, 150), $refId, time()]);
    } catch (Throwable $e) { zlog('tx', $e->getMessage()); }
}

/** Як маротиба — таърихи кӯҳна аз z_topups ва z_orders кӯчонида мешавад */
function tx_backfill(): void {
    if (cfg('tx_fill', '') === '1') return;
    try {
        db()->exec("CREATE TABLE IF NOT EXISTS z_tx (id INT AUTO_INCREMENT PRIMARY KEY,
            uid BIGINT, kind VARCHAR(16), amount DECIMAL(12,2), balance DECIMAL(14,2) DEFAULT 0,
            title VARCHAR(160) NULL, ref_id INT NULL, created_at INT,
            INDEX (uid, id), INDEX (created_at)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

        $c = (int)(one("SELECT COUNT(*) c FROM z_tx")['c'] ?? 0);
        if ($c > 0) { setcfg('tx_fill', '1'); return; }

        db()->exec("INSERT INTO z_tx (uid,kind,amount,balance,title,ref_id,created_at)
                    SELECT uid, 'topup', amount, 0, CONCAT('Пур кардан #', id), id,
                           COALESCE(done_at, created_at)
                    FROM z_topups WHERE status='ok'");

        db()->exec("INSERT INTO z_tx (uid,kind,amount,balance,title,ref_id,created_at)
                    SELECT uid, 'buy', -price, 0,
                           CONCAT(game_name, ' · ', pack_name), id, created_at
                    FROM z_orders WHERE status IN ('new','done','wait')");

        db()->exec("INSERT INTO z_tx (uid,kind,amount,balance,title,ref_id,created_at)
                    SELECT uid, 'refund', price, 0,
                           CONCAT('Баргашт · ', pack_name), id, COALESCE(done_at, created_at)
                    FROM z_orders WHERE status='refund'");

        setcfg('tx_fill', '1');
    } catch (Throwable $e) { zlog('tx', 'backfill: ' . $e->getMessage()); }
}

function queue_add(int $orderId, $uid, string $err): void {
    ensure_tables();
    try {
        q("INSERT IGNORE INTO z_queue (order_id,uid,tries,last_err,created_at)
           VALUES (?,?,0,?,?)", [$orderId, $uid, mb_substr($err, 0, 180), time()]);
        q("UPDATE z_orders SET status='wait', note=NULL WHERE id=?", [$orderId]);
    } catch (Throwable $e) { zlog('queue', $e->getMessage()); }
}

function queue_size(): int {
    ensure_tables();
    try { return (int)(one("SELECT COUNT(*) c FROM z_queue")['c'] ?? 0); }
    catch (Throwable $e) { return 0; }
}

/** Навбатро иҷро мекунад. Бармегардонад: [иҷрошуда, боқимонда] */
function queue_run(int $limit = 25): array {
    $rows = all("SELECT q.*, o.status FROM z_queue q
                 JOIN z_orders o ON o.id=q.order_id
                 ORDER BY q.id LIMIT $limit");
    if (!$rows) return [0, 0];

    // аввал баланси провайдерро мебинем
    $b = fz('GET', '/balance');
    $bal = !empty($b['ok']) ? (float)str_replace(',', '.', (string)($b['balance'] ?? '0')) : 0;
    if ($bal <= 0.05) return [0, count($rows)];

    $done = 0;
    foreach ($rows as $r) {
        $oid = (int)$r['order_id'];
        $o = one("SELECT * FROM z_orders WHERE id=?", [$oid]);
        if (!$o) { q("DELETE FROM z_queue WHERE order_id=?", [$oid]); continue; }
        if (!in_array($o['status'], ['wait', 'new'], true)) {
            q("DELETE FROM z_queue WHERE order_id=?", [$oid]);
            continue;
        }

        q("UPDATE z_orders SET status='new' WHERE id=?", [$oid]);
        $res = fz_place($oid);

        if (!empty($res['ok'])) {
            q("DELETE FROM z_queue WHERE order_id=?", [$oid]);
            $done++;
            say($o['uid'], "<b>● ФАРМОИШИ ШУМО ИҶРО ШУД</b>\n<code>───────────────</code>\n"
                . h($o['game_name']) . " · " . h($o['pack_name']) . "\n"
                . "ID · <code>" . h($o['player_id']) . "</code>\n\n"
                . "<i>Мағоза дубора пур шуд — фармоиш худкор иҷро гардид.</i>");
        } else {
            $msg = (string)($res['msg'] ?? '');
            if (is_nobalance($msg)) {
                q("UPDATE z_orders SET status='wait' WHERE id=?", [$oid]);
                q("UPDATE z_queue SET tries=tries+1, last_err=? WHERE order_id=?",
                  [mb_substr($msg, 0, 180), $oid]);
                break;   // пул тамом — истодан
            }
            // хатои дигар — бекор ва бозгашт
            q("DELETE FROM z_queue WHERE order_id=?", [$oid]);
            order_fail($oid, 0, $msg);
        }
        usleep(250000);
    }
    return [$done, queue_size()];
}

/* ============ РАД КАРДАНИ ПУР КАРДАН ============ */

/** Сабабҳои тайёр — барои админ (русӣ) */
function rej_reasons(): array {
    return [
        'nopay' => '💸 Пул наомад',
        'sum'   => '≠ Маблағ мувофиқ нест',
        'dup'   => '⧉ Чек такрорӣ',
        'fake'  => '⚠️ Чеки қалбакӣ',
        'nocmt' => '# Бе шарҳ — ёфт нашуд',
    ];
}

/** Ҳамон сабабҳо бо забони муштарӣ */
function rej_text(string $code, $uid): string {
    $l = ulang($uid);
    $m = [
      'nopay' => ['tj'=>'Пул ба ҳисоби мо наомад.',
                  'ru'=>'Деньги не поступили на наш счёт.',
                  'uz'=>'Pul hisobimizga tushmadi.',
                  'ky'=>'Акча эсебибизге түшкөн жок.',
                  'en'=>'The money did not arrive in our account.',
                  'kk'=>'Ақша шотымызға түспеді.'],
      'sum'   => ['tj'=>'Маблағи чек ба дархост мувофиқ нест.',
                  'ru'=>'Сумма в чеке не совпадает с заявкой.',
                  'uz'=>'Chekdagi summa arizaga mos kelmaydi.',
                  'ky'=>'Чектеги сумма арызга дал келбейт.',
                  'en'=>'The receipt amount does not match the request.',
                  'kk'=>'Чектегі сома өтінімге сәйкес келмейді.'],
      'dup'   => ['tj'=>'Ин чек аллакай истифода шудааст.',
                  'ru'=>'Этот чек уже был использован.',
                  'uz'=>'Bu chek allaqachon ishlatilgan.',
                  'ky'=>'Бул чек мурун колдонулган.',
                  'en'=>'This receipt has already been used.',
                  'kk'=>'Бұл чек бұрын пайдаланылған.'],
      'fake'  => ['tj'=>'Чек боварибахш нест.',
                  'ru'=>'Чек не вызывает доверия.',
                  'uz'=>'Chek ishonchli emas.',
                  'ky'=>'Чек ишенимдүү эмес.',
                  'en'=>'The receipt could not be trusted.',
                  'kk'=>'Чек сенімсіз.'],
      'nocmt' => ['tj'=>'Дар шарҳи пардохт рақами дархост набуд — пулро ёфта натавонистем.',
                  'ru'=>'В комментарии к платежу не было номера заявки — мы не смогли найти деньги.',
                  'uz'=>'Toʻlov izohida ariza raqami yoʻq — pulni topa olmadik.',
                  'ky'=>'Төлөм комментарийинде арыз номери жок — акчаны таба алган жокпуз.',
                  'en'=>'The payment comment had no request number — we could not find the money.',
                  'kk'=>'Төлем түсініктемесінде өтінім нөмірі жоқ — ақшаны таба алмадық.'],
    ];
    return $m[$code][$l] ?? ($m[$code]['ru'] ?? '');
}

/**
 * Рад кардани дархост бо сабаб.
 * $why: коди тайёр ('nopay'...), матни озод, ё '' = бе сабаб.
 */
function topup_deny(int $tid, $adminId, string $why = ''): bool {
    $t = one("SELECT * FROM z_topups WHERE id=?", [$tid]);
    if (!$t || $t['status'] === 'ok') return false;

    $upd = q("UPDATE z_topups SET status='no', admin_id=?, done_at=?
              WHERE id=? AND status<>'ok' AND status<>'no'", [$adminId, time(), $tid]);
    $first = $upd->rowCount() > 0;

    $uid = (int)$t['uid'];
    $txt = '';
    if ($why !== '') {
        $txt = array_key_exists($why, rej_reasons()) ? rej_text($why, $uid) : $why;
    }

    $l = ulang($uid);
    $head = ['tj'=>'× ПАРДОХТ ТАСДИҚ НАШУД','ru'=>'× ПЛАТЁЖ НЕ ПОДТВЕРЖДЁН',
             'uz'=>'× TOʻLOV TASDIQLANMADI','ky'=>'× ТӨЛӨМ ТАСТЫКТАЛГАН ЖОК',
             'en'=>'× PAYMENT NOT CONFIRMED','kk'=>'× ТӨЛЕМ РАСТАЛМАДЫ'][$l] ?? '× ПАРДОХТ ТАСДИҚ НАШУД';
    $tail = ['tj'=>'Агар пул фиристода бошед — ба дастгирӣ нависед.',
             'ru'=>'Если вы отправляли деньги — напишите в поддержку.',
             'uz'=>'Agar pul yuborgan boʻlsangiz — yordamga yozing.',
             'ky'=>'Акча жөнөткөн болсоңуз — колдоого жазыңыз.',
             'en'=>'If you did send money — contact support.',
             'kk'=>'Ақша жіберген болсаңыз — қолдауға жазыңыз.'][$l] ?? '';

    $kb = [];
    $wa = wa_reject($uid, $tid, $txt);
    if ($wa !== '') $kb[] = [['text' => '✆ WHATSAPP', 'url' => $wa]];
    $sup = tg_url(cfg('support', ''));
    if ($sup !== '') $kb[] = [['text' => '✈ TELEGRAM', 'url' => $sup]];

    say($uid, "<b>{$head}</b>\n<code>───────────────</code>\n"
        . "Дархост · #{$tid}\n"
        . "Маблағ · <b>" . money((float)$t['amount']) . "</b>\n\n"
        . ($txt !== '' ? h($txt) . "\n\n" : '')
        . $tail, $kb ?: null);

    return $first;
}

/* ИИ-санҷиши чек нест карда шуд — чек фавран ба админ меравад (v9.5) */

/* ============ ПРОМОКОДҲО ============ */

/**
 * Санҷиши промокод.
 * ['ok'=>true,'promo'=>row,'off'=>маблағи тахфиф,'total'=>нархи нав]
 */
function promo_check(string $code, $uid, float $sum): array {
    ensure_tables();
    $code = mb_strtoupper(trim($code));
    if ($code === '') return ['ok' => false, 'err' => 'EMPTY'];

    $p = one("SELECT * FROM z_promo WHERE code=?", [$code]);
    if (!$p) return ['ok' => false, 'err' => 'NOT_FOUND'];
    if ((int)$p['active'] !== 1) return ['ok' => false, 'err' => 'OFF'];
    if (!empty($p['until']) && (int)$p['until'] < time()) return ['ok' => false, 'err' => 'EXPIRED'];
    if ((int)$p['max_uses'] > 0 && (int)$p['used'] >= (int)$p['max_uses']) {
        return ['ok' => false, 'err' => 'LIMIT'];
    }
    if ((float)$p['min_sum'] > 0 && $sum < (float)$p['min_sum']) {
        return ['ok' => false, 'err' => 'MIN', 'min' => (float)$p['min_sum']];
    }
    if ((int)$p['per_user'] > 0) {
        $n = (int)(one("SELECT COUNT(*) c FROM z_promo_use WHERE promo_id=? AND uid=?",
                       [$p['id'], $uid])['c'] ?? 0);
        if ($n >= (int)$p['per_user']) return ['ok' => false, 'err' => 'USED'];
    }

    $off = $p['kind'] === 'fix' ? (float)$p['val'] : round($sum * (float)$p['val'] / 100, 2);
    if ($off > $sum) $off = $sum;
    $off = round($off, 2);
    return ['ok' => true, 'promo' => $p, 'off' => $off, 'total' => round($sum - $off, 2)];
}

function promo_use(array $p, $uid, int $orderId, float $off): void {
    q("INSERT INTO z_promo_use (promo_id,uid,order_id,sum_off,at) VALUES (?,?,?,?,?)",
      [$p['id'], $uid, $orderId, $off, time()]);
    q("UPDATE z_promo SET used=used+1, saved=saved+? WHERE id=?", [$off, $p['id']]);
}

function promo_err(string $e, $uid, float $min = 0): string {
    $l = ulang($uid);
    $m = [
      'NOT_FOUND'=>['tj'=>'Чунин промокод нест','ru'=>'Такого промокода нет','uz'=>'Bunday promokod yoʻq',
                    'ky'=>'Мындай промокод жок','en'=>'Promo code not found','kk'=>'Мұндай промокод жоқ'],
      'OFF'      =>['tj'=>'Промокод хомӯш аст','ru'=>'Промокод отключён','uz'=>'Promokod oʻchirilgan',
                    'ky'=>'Промокод өчүрүлгөн','en'=>'Promo code is disabled','kk'=>'Промокод өшірілген'],
      'EXPIRED'  =>['tj'=>'Мӯҳлати промокод гузашт','ru'=>'Срок промокода истёк',
                    'uz'=>'Promokod muddati tugagan','ky'=>'Промокоддун мөөнөтү бүттү',
                    'en'=>'Promo code expired','kk'=>'Промокод мерзімі бітті'],
      'LIMIT'    =>['tj'=>'Промокод тамом шуд','ru'=>'Промокод исчерпан','uz'=>'Promokod tugadi',
                    'ky'=>'Промокод түгөндү','en'=>'Promo code limit reached','kk'=>'Промокод бітті'],
      'USED'     =>['tj'=>'Шумо аллакай истифода кардед','ru'=>'Вы уже использовали его',
                    'uz'=>'Siz allaqachon ishlatgansiz','ky'=>'Сиз буга чейин колдонгонсуз',
                    'en'=>'You already used it','kk'=>'Сіз оны қолданғансыз'],
      'MIN'      =>['tj'=>'Ҳадди ақали харид: %s','ru'=>'Минимальная сумма: %s',
                    'uz'=>'Eng kam summa: %s','ky'=>'Эң аз сумма: %s',
                    'en'=>'Minimum amount: %s','kk'=>'Ең аз сома: %s'],
      'EMPTY'    =>['tj'=>'Рамзро нависед','ru'=>'Введите код','uz'=>'Kodni kiriting',
                    'ky'=>'Кодду киргизиңиз','en'=>'Enter the code','kk'=>'Кодты енгізіңіз'],
    ];
    $t = $m[$e][$l] ?? ($m[$e]['tj'] ?? $e);
    return $e === 'MIN' ? sprintf($t, money($min)) : $t;
}

/* ============ ОБУНА БА КАНАЛ ============ */

function sub_channel(): string {
    $c = trim(cfg('sub_ch', ''));
    if ($c === '') return '';
    if (str_starts_with($c, 'https://t.me/')) $c = '@' . substr($c, 13);
    if (str_starts_with($c, 't.me/')) $c = '@' . substr($c, 5);
    if ($c !== '' && $c[0] !== '@' && $c[0] !== '-') $c = '@' . $c;
    return $c;
}
function sub_link(): string {
    $c = sub_channel();
    if ($c === '') return '';
    $u = tg_url($c);
    return $u !== '' ? $u : tg_url(cfg('sub_url', ''));
}

/** Рӯйхати каналҳои ОП (обязательная подписка). Кэш 60 сония. */
function subs_list(bool $onlyActive = true): array {
    $w = $onlyActive ? "WHERE active=1" : "";
    // ҲИМОЯ: агар ҷадвал ҳанӯз сохта нашуда бошад (setup нашуд) — бот наафтад
    try { return all("SELECT * FROM z_subs $w ORDER BY sort DESC, id ASC"); }
    catch (Throwable $e) { return []; }
}

/** Рӯйхати каналҳо барои Mini App (title + link) */
function subs_public(): array {
    $out = [];
    foreach (subs_list(true) as $c) {
        $ln = sub_btn_link($c);
        $out[] = [
            'title' => trim((string)$c['title']) !== '' ? (string)$c['title'] : (string)$c['chat'],
            'link'  => $ln,
        ];
    }
    return $out;
}

/** true — иҷозат ҳаст (ба ҲАМАИ каналҳо обуна аст ё канал нест) */
function sub_ok($uid): bool {
    try {
        if (is_admin($uid)) return true;
        $chs = subs_list(true);
        if (!$chs) return true;                       // ягон канал нест — озод

        static $cache = [];
        if (isset($cache[$uid]) && (time() - $cache[$uid][1]) < 90) return $cache[$uid][0];

        // Кэш дар БД: агар корбар 5 дақ пеш обуна тасдиқ шуда бошад — Telegram-ро аз нав намепурсем
        try {
            $urow = one("SELECT sub_ok_at FROM z_users WHERE id=?", [$uid]);
            if ($urow && (int)($urow['sub_ok_at'] ?? 0) > time() - 300) {
                $cache[$uid] = [true, time()];
                return true;
            }
        } catch (Throwable $e) {}

        $ok = true;
        foreach ($chs as $c) {
            $chat = sub_norm((string)$c['chat']);
            if ($chat === '') continue;
            $r = tg('getChatMember', ['chat_id' => $chat, 'user_id' => $uid]);
            if (empty($r['ok'])) continue;            // бот админ нест ё канал нодуруст — сарфи назар
            $st = (string)($r['result']['status'] ?? '');
            if (!in_array($st, ['creator', 'administrator', 'member'], true)) { $ok = false; break; }
        }
        $cache[$uid] = [$ok, time()];
        if ($ok) { try { q("UPDATE z_users SET sub_ok_at=? WHERE id=?", [time(), $uid]); } catch (Throwable $e) {} }
        return $ok;
    } catch (Throwable $e) {
        // ҲАР хатои ғайричашмдошт — клиентро мегузаронем, ботро намеафтонем
        zlog('sub', 'sub_ok: ' . $e->getMessage());
        return true;
    }
}

/** кадом каналҳо ҳанӯз обуна нашуда (барои нишон додан) */
function subs_missing($uid): array {
    if (is_admin($uid)) return [];
    $out = [];
    foreach (subs_list(true) as $c) {
        $chat = sub_norm((string)$c['chat']);
        if ($chat === '') continue;
        $r = tg('getChatMember', ['chat_id' => $chat, 'user_id' => $uid]);
        if (empty($r['ok'])) continue;
        $st = (string)($r['result']['status'] ?? '');
        if (!in_array($st, ['creator', 'administrator', 'member'], true)) $out[] = $c;
    }
    return $out;
}

/** chat-ро ба формати getChatMember меорад: @username ё -100... */
function sub_norm(string $c): string {
    $c = trim($c);
    if ($c === '') return '';
    if (str_starts_with($c, 'https://t.me/')) $c = substr($c, 13);
    if (str_starts_with($c, 'http://t.me/'))  $c = substr($c, 12);
    if (str_starts_with($c, 't.me/'))         $c = substr($c, 5);
    // ссылкаи даъватӣ (+xxxx ё joinchat) — getChatMember кор намекунад, chat-и холӣ бармегардонем
    if ($c !== '' && ($c[0] === '+' || str_contains($c, 'joinchat'))) return '';
    if ($c !== '' && $c[0] !== '@' && $c[0] !== '-') $c = '@' . $c;
    return $c;
}

/** ссылкаи тугма барои канал (аз link ё аз chat месозад) */
function sub_btn_link(array $c): string {
    $ln = trim((string)($c['link'] ?? ''));
    if ($ln !== '') return tg_url($ln) ?: $ln;    // ссылкаи даъватӣ +xxx-ро ҳамон тавр мемонем
    return tg_url((string)$c['chat']);
}

function ask_sub($chat, $uid, $mid = null): void {
    $chs = subs_list(true);
    $t  = "<b>" . T('subT', $uid) . "</b>\n<code>───────────────</code>\n"
        . T('subTxt', $uid) . "\n\n" . T('subWhy', $uid);
    $kb = [];
    foreach ($chs as $c) {
        $ln = sub_btn_link($c);
        $tt = trim((string)$c['title']) !== '' ? (string)$c['title'] : (string)$c['chat'];
        if ($ln !== '') $kb[] = [['text' => '▸ ' . mb_substr($tt, 0, 40), 'url' => $ln]];
    }
    $kb[] = [['text' => '✓ ' . T('subChk', $uid), 'callback_data' => 'subchk']];
    $mid ? ed($chat, $mid, $t, $kb) : say($chat, $t, $kb);
}

/* ============ FLASHTOPUP — танҳо санҷиши ном ============ */

function ft(string $method, string $path, array $qy = [], ?array $body = null): array {
    $method = strtoupper($method);
    $raw = $body === null ? '' : json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    $ts = (string)time();
    $nc = bin2hex(random_bytes(16));
    $canon = implode("\n", [$method, FT_PATH . $path, $ts, $nc, hash('sha256', $raw)]);
    $sig = hash_hmac('sha256', $canon, FT_KEY);

    $hdr = ['X-FT-API-ID: ' . FT_ID, 'X-FT-Timestamp: ' . $ts, 'X-FT-Nonce: ' . $nc,
            'X-FT-Signature: ' . $sig, 'Accept: application/json'];
    if ($raw !== '') $hdr[] = 'Content-Type: application/json';

    $ch = curl_init(FT_BASE . $path . ($qy ? '?' . http_build_query($qy) : ''));
    $o = [CURLOPT_RETURNTRANSFER => true, CURLOPT_CUSTOMREQUEST => $method,
          CURLOPT_HTTPHEADER => $hdr, CURLOPT_TIMEOUT => 20];
    if (defined('CURL_IPRESOLVE_V4')) $o[CURLOPT_IPRESOLVE] = CURL_IPRESOLVE_V4;
    curl_setopt_array($ch, $o);
    if ($raw !== '') curl_setopt($ch, CURLOPT_POSTFIELDS, $raw);
    $res = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    $d = json_decode((string)$res, true);
    if (!is_array($d)) return ['success' => false, 'http' => $code];
    $d['http'] = $code;
    return $d;
}

/** Рӯйхати validation_code-ҳои FlashTopup (кэш 12 соат) */
function ftv_list(bool $force = false): array {
    $j = cfg('ftv', '');
    $at = (int)cfg('ftv_at', '0');
    if (!$force && $j !== '' && (time() - $at) < 43200) {
        $d = json_decode($j, true);
        if (is_array($d) && $d) return $d;
    }
    $out = []; $page = 1; $cur = null; $items = [];
    do {
        $qy = $cur ? ['cursor' => $cur, 'per_page' => 500] : ['page' => $page, 'per_page' => 500];
        $r = ft('GET', '/products', $qy);
        if (empty($r['success'])) break;
        $d = $r['data'] ?? [];
        $items = [];
        foreach (['products', 'items'] as $k) if (isset($d[$k]) && is_array($d[$k])) $items = $d[$k];
        if (!$items && is_array($d) && array_is_list($d)) $items = $d;
        foreach ($items as $p) {
            if (!is_array($p)) continue;
            $vc = (string)($p['validation_code'] ?? '');
            if ($vc === '' || ($p['check_id_status'] ?? '') !== 'active') continue;
            $out[] = ['vc' => $vc, 'name' => (string)($p['name'] ?? $vc),
                      'srv' => 0];
        }
        $cur = $r['meta']['next_cursor'] ?? null;
        $page++;
    } while (($cur || count($items) >= 500) && $page < 25);

    if ($out) { setcfg('ftv', json_encode($out, JSON_UNESCAPED_UNICODE));
                setcfg('ftv_at', (string)time()); }
    return $out ?: (json_decode($j ?: '[]', true) ?: []);
}

/** Калимаҳои минтақа дар номи FlashTopup */
function ftv_region_words(string $code): array {
    $m = [
        'GLOBAL' => ['global'],
        'CIS'    => ['global'],          // FlashTopup CIS надорад — global кор мекунад
        'RU'     => ['russia', 'ru', 'global'],
        'KZ'     => ['global'],
        'EU'     => ['europe'],
        'ID'     => ['indonesia'],
        'BR'     => ['brazil'],
        'BD'     => ['bangladesh'],
        'SG'     => ['sg', 'singapore'],
        'MYSG'   => ['sgmy', 'sg my'],
        'SGMY'   => ['sgmy', 'sg my'],
        'MY'     => ['malaysia', 'sgmy'],
        'TW'     => ['taiwan'],
        'VN'     => ['vietnam'],
        'TH'     => ['thailand'],
        'PH'     => ['philippines'],
        'KH'     => ['cambodia'],
        'LATAM'  => ['latam'],
        'MENA'   => ['middle east', 'me'],
        'TR'     => ['turkey'],
        'PK'     => ['pakistan'],
        'IN'     => ['india'],
    ];
    return $m[mb_strtoupper($code)] ?? [];
}

/** Мувофиқи бозиро дар FlashTopup меёбад (минтақа қатъӣ) */
function ftv_match(array $g): ?array {
    $list = ftv_list();
    if (!$list) return null;

    $norm = function ($x) {
        $x = mb_strtolower(trim((string)$x));
        $x = preg_replace('~\((.*?)\)~', ' $1 ', $x);
        $x = preg_replace('~[^a-z0-9]+~', ' ', $x);
        return trim(preg_replace('~\s+~', ' ', $x));
    };
    $base = $norm($g['base'] ?? '');
    if ($base === '') $base = $norm($g['name'] ?? '');
    $reg  = mb_strtoupper((string)($g['region'] ?? ''));
    $words = ftv_region_words($reg);

    // танҳо ҳамон бозӣ (номаш бо base сар мешавад)
    $same = [];
    foreach ($list as $v) {
        $vn = $norm($v['name']);
        if ($vn === $base || str_starts_with($vn, $base . ' ')) $same[] = ['v' => $v, 'n' => $vn];
    }
    if (!$same) return null;

    // 1) минтақаи дақиқ
    foreach ($words as $w) {
        foreach ($same as $x) {
            $tail = trim(mb_substr($x['n'], mb_strlen($base)));
            if ($tail === $w) return $x['v'];
        }
    }
    // 2) минтақа дар ягон ҷои ном
    foreach ($words as $w) {
        foreach ($same as $x) {
            if (str_contains($x['n'], ' ' . $w) || $x['n'] === $base . ' ' . $w) return $x['v'];
        }
    }
    // 3) global
    foreach ($same as $x) {
        $tail = trim(mb_substr($x['n'], mb_strlen($base)));
        if ($tail === 'global') return $x['v'];
    }
    // 4) номи тоза бе минтақа (мисол "Mobile Legends", "PUBG Mobile")
    foreach ($same as $x) if ($x['n'] === $base) return $x['v'];

    return null;
}

/** Санҷиши ном тавассути FlashTopup */
function ft_nick(array $g, array $vals): ?array {
    $m = ftv_match($g);
    if (!$m) return null;

    $v = array_values(array_filter(array_map(fn($x) => trim((string)$x), $vals),
                                   fn($x) => $x !== ''));
    if (!$v) return null;

    $body = ['user_id' => $v[0], 'validation_code' => $m['vc']];
    if (count($v) > 1) $body['server_id'] = $v[1];

    $r = ft('POST', '/check-id', [], $body);
    zlog('ftchk', json_encode(['vc' => $m['vc'], 'uid' => $v[0],
        'ok' => $r['success'] ?? false, 'd' => $r['data'] ?? null], JSON_UNESCAPED_UNICODE));

    if (empty($r['success'])) return null;
    $d = is_array($r['data'] ?? null) ? $r['data'] : [];
    if (isset($d['valid']) && !$d['valid']) return ['invalid' => true];

    $nick = '';
    foreach (['account_name', 'username', 'nickname', 'name', 'player_name'] as $k) {
        if (!empty($d[$k]) && is_string($d[$k])) { $nick = $d[$k]; break; }
    }
    if ($nick === '' || $nick === $v[0]) return null;
    return ['nick' => $nick, 'region' => (string)($d['region'] ?? '')];
}

/* ======================= FAZERCARDS API ======================= */

/**
 * Ники Free Fire аз gameskinbo API (бо калид — устувортар, хоб намеравад).
 * Калид: cfg('gs_key'). Хомӯш: gs_nick=0.
 */
function gs_nick(array $g, array $vals): ?array {
    if (cfg('gs_nick', '1') !== '1') return null;
    $key = trim(cfg('gs_key', defined('GS_KEY_DEFAULT') ? GS_KEY_DEFAULT : ''));
    if ($key === '') return null;

    $nm = mb_strtolower((string)($g['name'] ?? '') . ' ' . (string)($g['ft_code'] ?? ''));
    if (!str_contains($nm, 'free fire') && !str_contains($nm, 'free_fire')
        && !str_contains($nm, 'freefire')) return null;

    $uid = '';
    foreach (['user_id', 'player_id', 'uid', 'id'] as $k)
        if (!empty($vals[$k])) { $uid = trim((string)$vals[$k]); break; }
    if ($uid === '') foreach ($vals as $v)
        if (is_scalar($v) && trim((string)$v) !== '') { $uid = trim((string)$v); break; }
    if ($uid === '' || !ctype_digit($uid)) return null;

    // КЭШ 24 соат — лимити дархостҳо маҳдуд аст, беҳуда сарф намекунем
    $ck = 'gsn:' . $uid;
    try {
        $cr = one("SELECT v FROM z_settings WHERE k=?", [$ck]);
        if ($cr) {
            $cv = json_decode((string)$cr['v'], true);
            if (is_array($cv) && !empty($cv['nick'])
                && (time() - (int)($cv['at'] ?? 0)) < (int)cfg('nick_ttl', '1800'))
                return ['nick' => $cv['nick'], 'region' => (string)($cv['reg'] ?? '')];
        }
    } catch (Throwable $e) {}

    $base = rtrim(cfg('gs_api', 'https://api.gameskinbo.com'), '/');
    $qy   = ['uid' => $uid];
    $reg  = mb_strtoupper(trim((string)($g['region'] ?? '')));
    $sup  = ['BD','IND','BR','US','SAC','NA','ID','SG','PK'];
    if ($reg !== '' && in_array($reg, $sup, true)) $qy['region'] = $reg;

    $ch = curl_init($base . '/ff-info/get?' . http_build_query($qy));
    $o = [CURLOPT_RETURNTRANSFER => true,
          CURLOPT_TIMEOUT => (int)cfg('gs_to', '8'),
          CURLOPT_CONNECTTIMEOUT => 4,
          CURLOPT_HTTPHEADER => ['x-api-key: ' . $key, 'Accept: application/json']];
    if (defined('CURL_IPRESOLVE_V4')) $o[CURLOPT_IPRESOLVE] = CURL_IPRESOLVE_V4;
    curl_setopt_array($ch, $o);
    $res  = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($code === 401) { zlog('gs', 'калиди API нодуруст (401)'); return null; }
    if ($code === 429) { zlog('gs', 'лимит ё суръат (429)');      return null; }
    if ($code !== 200 || !$res) return null;

    $d = json_decode((string)$res, true);
    if (!is_array($d)) return null;
    $ai   = is_array($d['AccountInfo'] ?? null) ? $d['AccountInfo'] : [];
    $nick = (string)($ai['AccountName'] ?? '');
    if ($nick === '') return null;

    $out = ['nick' => $nick, 'region' => mb_strtoupper((string)($ai['AccountRegion'] ?? ''))];
    try { setcfg($ck, json_encode(['nick' => $out['nick'], 'reg' => $out['region'], 'at' => time()],
                                  JSON_UNESCAPED_UNICODE)); } catch (Throwable $e) {}
    return $out;
}

/**
 * Ники Free Fire аз API-и кушод (jinix6/free-ff-api).
 * Калид лозим нест — танҳо region + uid.
 * Бозгашт: ['nick'=>..., 'region'=>...] ё null (натавонист) ё ['invalid'=>true] (ID нест).
 */
function ff_nick(array $g, array $vals): ?array {
    if (cfg('ff_nick', '1') !== '1') return null;

    // танҳо барои Free Fire
    $nm = mb_strtolower((string)($g['name'] ?? '') . ' ' . (string)($g['ft_code'] ?? ''));
    if (!str_contains($nm, 'free fire') && !str_contains($nm, 'free_fire')
        && !str_contains($nm, 'freefire') && !str_contains($nm, 'ff ')) return null;

    // ID-и бозигар
    $uid = '';
    foreach (['user_id', 'player_id', 'uid', 'id'] as $k) {
        if (!empty($vals[$k])) { $uid = trim((string)$vals[$k]); break; }
    }
    if ($uid === '') { foreach ($vals as $v) { if (is_scalar($v) && trim((string)$v) !== '') { $uid = trim((string)$v); break; } } }
    if ($uid === '' || !ctype_digit($uid)) return null;

    $base = rtrim(cfg('ff_api', 'https://free-ff-api-src-5plp.onrender.com'), '/');
    $sup  = ['IND','BR','SG','RU','ID','TW','US','VN','TH','ME','PK','CIS','BD'];

    // КЭШ: ҳамон ID-ро дубора напурсем (сервиси ройгон суст аст)
    $ck = 'ffn:' . $uid;
    try {
        $cr = one("SELECT v FROM z_settings WHERE k=?", [$ck]);
        if ($cr) {
            $cv = json_decode((string)$cr['v'], true);
            if (is_array($cv) && !empty($cv['nick'])
                && (time() - (int)($cv['at'] ?? 0)) < (int)cfg('nick_ttl', '1800')) {
                return ['nick' => $cv['nick'], 'region' => (string)($cv['reg'] ?? '')];
            }
        }
    } catch (Throwable $e) {}

    // минтақаи бозӣ (аз номаш: "Free Fire (BR)" → BR)
    $reg = mb_strtoupper(trim((string)($g['region'] ?? '')));
    $try = [];
    if ($reg !== '' && in_array($reg, $sup, true)) $try[] = $reg;
    foreach (['SG','IND','BR','ID','TH','VN','ME','PK','BD','RU','TW','US','CIS'] as $r)
        if (!in_array($r, $try, true)) $try[] = $r;
    $try = array_slice($try, 0, (int)cfg('ff_try', '3'));

    $deadline = microtime(true) + (float)cfg('ff_max', '9');   // ҲАМАГӢ на бештар аз 9 сония
    foreach ($try as $r) {
        if (microtime(true) >= $deadline) break;               // вақт тамом — бас мекунем
        $url = $base . '/api/v1/account?' . http_build_query(['region' => $r, 'uid' => $uid]);
        $ch = curl_init($url);
        $o = [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => (int)cfg('ff_to', '4'),
              CURLOPT_CONNECTTIMEOUT => 3, CURLOPT_HTTPHEADER => ['Accept: application/json']];
        if (defined('CURL_IPRESOLVE_V4')) $o[CURLOPT_IPRESOLVE] = CURL_IPRESOLVE_V4;
        curl_setopt_array($ch, $o);
        $res  = curl_exec($ch);
        $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        if ($code !== 200 || !$res) continue;

        $d = json_decode((string)$res, true);
        if (!is_array($d)) continue;
        $nick = (string)($d['basicInfo']['nickname'] ?? '');
        if ($nick !== '') {
            $out = ['nick' => $nick, 'region' => (string)($d['basicInfo']['region'] ?? $r)];
            try { setcfg($ck, json_encode(['nick' => $nick, 'reg' => $out['region'], 'at' => time()],
                                          JSON_UNESCAPED_UNICODE)); } catch (Throwable $e) {}
            return $out;
        }
    }
    // натиҷаи манфиро КЭШ НАМЕКУНЕМ: сервиси ройгон хоб меравад ва
    // баъди бедор шудан бояд дубора кӯшиш кунем.
    return null;
}

function fz(string $method, string $path, array $qy = [], ?array $body = null, ?string $idem = null): array {
    $method = strtoupper($method);
    $url = FZ_BASE . $path . ($qy ? '?' . http_build_query($qy) : '');
    $raw = $body === null ? '' : json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

    $hdr = ['X-API-Key: ' . FZ_KEY, 'Accept: application/json'];
    if ($raw !== '') $hdr[] = 'Content-Type: application/json';
    if ($idem !== null) $hdr[] = 'Idempotency-Key: ' . $idem;

    $ch = curl_init($url);
    $o = [CURLOPT_RETURNTRANSFER => true, CURLOPT_CUSTOMREQUEST => $method,
          CURLOPT_HTTPHEADER => $hdr, CURLOPT_TIMEOUT => 45];
    if (defined('CURL_IPRESOLVE_V4')) $o[CURLOPT_IPRESOLVE] = CURL_IPRESOLVE_V4;
    curl_setopt_array($ch, $o);
    if ($raw !== '') curl_setopt($ch, CURLOPT_POSTFIELDS, $raw);
    $res = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err = curl_error($ch);
    curl_close($ch);

    if ($res === false) return ['ok' => false, 'http' => 0, 'error' => $err];
    $d = json_decode((string)$res, true);
    if (!is_array($d)) return ['ok' => false, 'http' => $code,
                               'error' => mb_substr((string)$res, 0, 200)];
    $d['http'] = $code;
    return $d;
}
function fzerr(array $r): string {
    $e = (string)($r['error'] ?? '');
    $c = (string)($r['code'] ?? '');
    if ($e !== '' || $c !== '') return trim(($c !== '' ? "[$c] " : '') . $e);
    return 'HTTP ' . ($r['http'] ?? '?');
}
function pick2(array $a, array $keys, $def = null) {
    foreach ($keys as $k) if (isset($a[$k]) && $a[$k] !== '' && $a[$k] !== null) return $a[$k];
    return $def;
}
function deepv(array $a, array $keys) {
    foreach ($keys as $k) if (isset($a[$k]) && is_scalar($a[$k]) && (string)$a[$k] !== '') return $a[$k];
    foreach ($a as $v) if (is_array($v)) { $r = deepv($v, $keys); if ($r !== null) return $r; }
    return null;
}
function sell_of(float $cost): float {
    $r = (float)cfg('rate', '11');
    $m = (float)cfg('markup', '20');
    $st = (float)cfg('round', '0.5');
    $p = $cost * $r * (1 + $m / 100);
    if ($st > 0) $p = ceil($p / $st) * $st;
    return round($p, 2);
}
function img_url(?string $u): ?string {
    if (!$u) return null;
    if (preg_match('~^https?://~i', $u)) return $u;
    return 'https://api.fzr.cards' . (str_starts_with($u, '/') ? '' : '/') . $u;
}

/** Синхронизатсияи каталог аз FazerCards */
function fz_sync(?callable $pg = null): array {
    $stat = ['g' => 0, 'p' => 0, 'off' => 0, 'offg' => 0, 'err' => []];

    // бозиҳое ки санҷиши ID доранд
    $canChk = [];
    foreach (vlist(true) as $v) $canChk[$v['id']] = $v['fields'];

    // категорияҳо
    $cats = []; $cursor = null; $guard = 0;
    do {
        $qy = ['limit' => 200, 'include_ui' => 1];
        if ($cursor) $qy['cursor'] = $cursor;
        $r = fz('GET', '/topups', $qy);
        if (empty($r['ok'])) { $stat['err'][] = '/topups: ' . fzerr($r); break; }
        foreach (($r['items'] ?? []) as $c) {
            if (!empty($c['category_id'])) $cats[] = $c;
        }
        $cursor = $r['meta']['next_cursor'] ?? null;
        $guard++;
    } while ($cursor && $guard < 30);

    if (!$cats) { $stat['err'][] = 'категория нест'; return $stat; }
    if ($pg) $pg(0, count($cats), 0);

    $seenG = [];
    $i = 0;
    foreach ($cats as $c) {
        $i++;
        $cid  = (string)$c['category_id'];
        $name = (string)pick2($c, ['name'], $cid);
        $img  = img_url(pick2($c, ['imageurl'], null));

        $of = fz('GET', '/topups/offers', ['category_id' => $cid, 'include_ui' => 1]);
        if (empty($of['ok'])) { $stat['err'][] = $name . ': ' . fzerr($of); continue; }

        $offers = $of['offers'] ?? [];
        $fields = $of['fields'] ?? ($canChk[$cid] ?? []);
        if (!$offers) continue;

        // майдонҳо
        $srv = 0; $idLabel = 'ID'; $srvLabel = 'Server';
        $fl = [];
        foreach ($fields as $f) {
            if (!is_array($f) || empty($f['key'])) continue;
            $fl[] = ['key' => (string)$f['key'], 'label' => (string)pick2($f, ['label'], $f['key']),
                     'type' => (string)pick2($f, ['type'], 'text'),
                     'options' => array_values(array_map(fn($o) => is_array($o)
                        ? ['value' => (string)pick2($o, ['value', 'code', 'id'], ''),
                           'label' => (string)pick2($o, ['label', 'name'], '')]
                        : ['value' => (string)$o, 'label' => (string)$o], $f['options'] ?? []))];
        }
        if (count($fl) > 1) { $srv = 1; $srvLabel = $fl[1]['label']; }
        if ($fl) $idLabel = $fl[0]['label'];

        $rg = split_reg($name);

        // санҷиши ID: мувофиқат бо рӯйхати расмии провайдер
        $vm = vmatch(['ft_code' => $cid, 'name' => $name, 'base' => $rg['base']]);
        $vId = $vm ? $vm['id'] : '';
        $vOk = $vm ? 1 : 0;

        q("INSERT INTO z_games (name,image,need_server,id_label,server_label,ft_code,ft_type,
             vcode,can_chk,fields,base,region,flag,active,created_at)
           VALUES (?,?,?,?,?,?, 'topup', ?,?,?,?,?,?,1,?)
           ON DUPLICATE KEY UPDATE name=VALUES(name), image=VALUES(image),
             need_server=VALUES(need_server), id_label=VALUES(id_label),
             server_label=VALUES(server_label), vcode=VALUES(vcode), can_chk=VALUES(can_chk),
             fields=VALUES(fields), base=VALUES(base), region=VALUES(region), flag=VALUES(flag),
             active=IF(hidden=1, 0, 1)",
          [mb_substr($name, 0, 110), $img, $srv, mb_substr($idLabel, 0, 55),
           mb_substr($srvLabel, 0, 55), $cid, $vId, $vOk,
           json_encode($fl, JSON_UNESCAPED_UNICODE),
           mb_substr($rg['base'], 0, 110), $rg['code'], $rg['flag'], time()]);
        $stat['g']++;

        $gid = (int)(one("SELECT id FROM z_games WHERE ft_code=?", [$cid])['id'] ?? 0);
        if (!$gid) continue;

        $seen = [];
        foreach ($offers as $o) {
            if (!is_array($o) || empty($o['offer_id'])) continue;
            $oid  = (string)$o['offer_id'];
            $pn   = mb_substr((string)pick2($o, ['name'], $oid), 0, 110);
            $cost = (float)str_replace(',', '.', (string)pick2($o, ['price_usd'], 0));
            if ($cost <= 0) continue;
            q("INSERT INTO z_packs (game_id,name,price,cost,ft_code,cat,active)
               VALUES (?,?,?,?,?,?,1)
               ON DUPLICATE KEY UPDATE game_id=VALUES(game_id), name=VALUES(name),
                 cost=VALUES(cost),
                 price=IF(fixed=1, price, VALUES(price)),
                 cat=VALUES(cat), active=1",
              [$gid, $pn, sell_of($cost), $cost, $cid . '|' . $oid, pack_cat($pn)]);
            $seen[] = $cid . '|' . $oid;
            $stat['p']++;
        }
        try { fix_game_cats($gid); } catch (Throwable $e) {}

        if (count($seen) >= 2) {
            $ph = implode(',', array_fill(0, count($seen), '?'));
            $stat['off'] += q("UPDATE z_packs SET active=0
                               WHERE game_id=? AND ft_code IS NOT NULL AND ft_code NOT IN ($ph)",
                              array_merge([$gid], $seen))->rowCount();
        }
        $seenG[] = $cid;
        if ($pg) $pg($i, count($cats), $stat['p']);
        usleep(80000);
    }

    if (count($seenG) >= 5 && empty($stat['err'])) {
        $ph = implode(',', array_fill(0, count($seenG), '?'));
        $stat['offg'] = q("UPDATE z_games SET active=0
                           WHERE ft_code IS NOT NULL AND ft_code NOT IN ($ph)", $seenG)->rowCount();
    }
    // пакетҳои провайдери қаблӣ
    try {
        $stat['old'] = q("DELETE FROM z_packs WHERE ft_code IS NOT NULL
                          AND ft_code NOT LIKE '%|%'")->rowCount();
        q("DELETE FROM z_games WHERE id NOT IN
           (SELECT game_id FROM (SELECT DISTINCT game_id FROM z_packs) x)");
    } catch (Throwable $e) {}

    setcfg('sync_at', (string)time());
    return $stat;
}

function fz_reprice(): int {
    $n = 0;
    foreach (all("SELECT id,cost FROM z_packs WHERE cost>0 AND fixed=0") as $p) {
        q("UPDATE z_packs SET price=? WHERE id=?", [sell_of((float)$p['cost']), $p['id']]);
        $n++;
    }
    return $n;
}

/** Майдонҳои бозӣ */
function game_fields(array $g): array {
    $f = json_decode((string)($g['fields'] ?? ''), true);
    if (is_array($f) && $f) return $f;
    return [['key' => 'user_id', 'label' => $g['id_label'] ?: 'ID', 'type' => 'text', 'options' => []]];
}

/** Рӯйхати бозиҳое ки санҷиши ID доранд (кэш 6 соат) */
function vlist(bool $force = false): array {
    $j = cfg('vlist', '');
    $at = (int)cfg('vlist_at', '0');
    if (!$force && $j !== '' && (time() - $at) < 21600) {
        $d = json_decode($j, true);
        if (is_array($d) && $d) return $d;
    }
    $r = fz('GET', '/topups/validate-id');
    if (empty($r['ok']) || empty($r['items']) || !is_array($r['items']))
        return json_decode($j ?: '[]', true) ?: [];
    $out = [];
    foreach ($r['items'] as $it) {
        if (!is_array($it) || empty($it['category_id'])) continue;
        $out[] = ['id' => (string)$it['category_id'],
                  'name' => (string)($it['name'] ?? ''),
                  'fields' => is_array($it['fields'] ?? null) ? $it['fields'] : []];
    }
    setcfg('vlist', json_encode($out, JSON_UNESCAPED_UNICODE));
    setcfg('vlist_at', (string)time());
    return $out;
}

/** Мувофиқи бозиро дар рӯйхати санҷиш меёбад */
function vmatch(array $g): ?array {
    $list = vlist();
    if (!$list) return null;
    $cid = (string)($g['ft_code'] ?? '');

    // мувофиқати ДАҚИҚ аз рӯи код — ин бехавф аст
    foreach ($list as $v) if ($v['id'] === $cid) return $v;

    // ХАВФ: мувофиқат аз рӯи НОМ минтақаро ба назар намегирад.
    // "Free Fire (BR)" метавонад ба "Free Fire" (RU) мувофиқ шавад
    // ва ники бозигари ДИГАР бо ҳамон ID баргардад.
    // Бинобар ин: агар бозӣ минтақа дошта бошад — мувофиқати номӣ МАНЪ аст.
    $reg = trim((string)($g['region'] ?? ''));
    if ($reg !== '' && cfg('v_namematch', '0') !== '1') return null;

    $norm = function ($x) {
        $x = mb_strtolower(trim((string)$x));
        $x = preg_replace('~\((.*?)\)~', ' $1 ', $x);      // қавсҳо
        $x = preg_replace('~[^a-z0-9]+~', ' ', $x);
        return trim(preg_replace('~\s+~', ' ', $x));
    };

    $gn = $norm($g['base'] ?? '') ?: $norm($g['name'] ?? '');
    $full = $norm($g['name'] ?? '');
    $best = null; $bl = 0;
    foreach ($list as $v) {
        $vn = $norm($v['name']);
        if ($vn === '') continue;
        if ($vn === $gn || $vn === $full) return $v;
        foreach ([$gn, $full] as $cand) {
            if ($cand === '') continue;
            if (str_starts_with($cand, $vn . ' ') || str_starts_with($vn, $cand . ' ')) {
                if (mb_strlen($vn) > $bl) { $best = $v; $bl = mb_strlen($vn); }
            }
        }
    }
    return $best;
}

/** Як кӯшиши санҷиш бо категорияи мушаххас */
function try_validate(string $cid, array $keys, array $vals): array {
    if (!$keys) $keys = ['user_id'];
    $mine = array_values(array_filter(array_map(fn($x) => trim((string)$x), $vals),
                                      fn($x) => $x !== ''));
    $f = [];
    foreach ($keys as $i => $k) {
        $val = '';
        foreach ($vals as $vk => $vv) {
            if ((string)$vk === $k && trim((string)$vv) !== '') { $val = trim((string)$vv); break; }
        }
        if ($val === '' && isset($mine[$i])) $val = $mine[$i];
        if ($val !== '') $f[$k] = $val;
    }
    if (!$f) return ['state' => 'empty'];

    $r = fz('POST', '/topups/validate-id', [], ['category_id' => $cid, 'fields' => (object)$f]);
    zlog('chk', json_encode(['cat' => $cid, 'f' => $f, 'http' => $r['http'] ?? 0,
                             'ok' => $r['ok'] ?? false, 'valid' => $r['valid'] ?? null,
                             'name' => $r['player_name'] ?? null,
                             'err' => $r['error'] ?? null], JSON_UNESCAPED_UNICODE));

    if (!empty($r['ok'])) {
        if (empty($r['valid'])) return ['state' => 'invalid'];
        $nick = (string)($r['player_name'] ?? '');
        if ($nick === '') return ['state' => 'invalid'];
        return ['state' => 'ok', 'nick' => $nick, 'region' => (string)($r['region'] ?? '')];
    }

    $http = (int)($r['http'] ?? 0);
    $em = mb_strtolower(fzerr($r));
    if ($http === 422) return ['state' => 'invalid'];
    if (str_contains($em, 'invalid player') || str_contains($em, 'player not')
        || str_contains($em, 'не найден')) return ['state' => 'invalid'];
    if ($http === 404 || str_contains($em, 'not support') || str_contains($em, 'unsupported')
        || str_contains($em, 'category') || str_contains($em, 'not found')) {
        return ['state' => 'unsupported'];
    }
    return ['state' => 'error', 'msg' => fzerr($r)];
}

/** Санҷиши ID — аввал FlashTopup (номи дуруст), баъд FazerCards */
function fz_check(array $g, array $vals): array {
    $gid = (int)($g['id'] ?? 0);

    // 0a) Free Fire — gameskinbo (бо калид, устувор)
    try {
        $gs = gs_nick($g, $vals);
        if ($gs !== null && !empty($gs['nick'])) {
            $gr = mb_strtoupper(trim((string)($g['region'] ?? '')));
            $nr = mb_strtoupper(trim((string)($gs['region'] ?? '')));
            // Эзоҳ: минтақаи БОЗӢ (маҳсулот) ва минтақаи АККАУНТ фарқ мекунанд.
            // ID дар Free Fire ҷаҳонӣ ягона аст, бинобар ин муқоиса ХОМӮШ аст (v_regchk=0).
            if ($gr === '' || $nr === '' || $gr === $nr || cfg('v_regchk', '0') !== '1') {
                q("UPDATE z_games SET can_chk=1 WHERE id=?", [$gid]);
                return ['ok' => true, 'nick' => $gs['nick'], 'region' => $gs['region'], 'src' => 'gs'];
            }
            zlog('chk', "gs region mismatch: бозӣ=$gr ник=$nr");
        }
    } catch (Throwable $e) { zlog('gschk', 'ERR ' . $e->getMessage()); }

    // 0b) Free Fire — API-и кушод (захиравӣ, калид лозим нест)
    try {
        $ff = ff_nick($g, $vals);
        if ($ff !== null && !empty($ff['nick'])) {
            q("UPDATE z_games SET can_chk=1 WHERE id=?", [$gid]);
            return ['ok' => true, 'nick' => $ff['nick'], 'region' => $ff['region'], 'src' => 'ff'];
        }
    } catch (Throwable $e) { zlog('ffchk', 'ERR ' . $e->getMessage()); }

    // 1) FlashTopup — танҳо агар махсус фаъол карда шавад (пешфарз ХОМӮШ).
    //    Сервиси кӯҳна буд ва ники нодуруст бармегардонд — бинобар ин хомӯш аст.
    if (cfg('ft_nick', '0') === '1') {
        try {
            $f = ft_nick($g, $vals);
            if ($f !== null) {
                if (!empty($f['invalid'])) {
                    q("UPDATE z_games SET can_chk=1 WHERE id=?", [$gid]);
                    return ['ok' => false, 'msg' => 'INVALID'];
                }
                q("UPDATE z_games SET can_chk=1 WHERE id=?", [$gid]);
                return ['ok' => true, 'nick' => $f['nick'], 'region' => $f['region'],
                        'src' => 'ft'];
            }
        } catch (Throwable $e) { zlog('ftchk', 'ERR ' . $e->getMessage()); }
    }

    // 1) роҳи қаблан кориро аввал месанҷем
    $saved = trim((string)($g['vcode'] ?? ''));
    $cands = [];
    if ($saved !== '') {
        $sk = [];
        foreach (vlist() as $v) if ($v['id'] === $saved) {
            foreach (($v['fields'] ?? []) as $f) if (!empty($f['key'])) $sk[] = (string)$f['key'];
        }
        $cands[] = ['id' => $saved, 'keys' => $sk];
    }

    // 2) худи категорияи бозӣ бо майдонҳои худаш
    $own = [];
    foreach (game_fields($g) as $f) if (!empty($f['key'])) $own[] = (string)$f['key'];
    $cands[] = ['id' => (string)$g['ft_code'], 'keys' => $own];

    // 3) мувофиқат аз рӯйхати расмии санҷиш
    $m = vmatch($g);
    if ($m) {
        $mk = [];
        foreach (($m['fields'] ?? []) as $f) if (!empty($f['key'])) $mk[] = (string)$f['key'];
        $cands[] = ['id' => $m['id'], 'keys' => $mk];
    }

    // 4) вариантҳои маъмули калидҳо барои ҳамон категория
    $cands[] = ['id' => (string)$g['ft_code'], 'keys' => ['user_id']];
    if ((int)($g['need_server'] ?? 0) === 1) {
        $cands[] = ['id' => (string)$g['ft_code'], 'keys' => ['user_id', 'server_id']];
        $cands[] = ['id' => (string)$g['ft_code'], 'keys' => ['user_id', 'zone_id']];
    }

    $seen = []; $lastErr = ''; $sawInvalid = false;
    foreach ($cands as $c) {
        $cid = trim((string)$c['id']);
        if ($cid === '') continue;
        $sig = $cid . '|' . implode(',', $c['keys']);
        if (isset($seen[$sig])) continue;
        $seen[$sig] = 1;

        $r = try_validate($cid, $c['keys'], $vals);

        if ($r['state'] === 'ok') {
            // Муқоисаи минтақа — танҳо агар админ махсус фаъол кунад (v_regchk=1).
            $gr = mb_strtoupper(trim((string)($g['region'] ?? '')));
            $nr = mb_strtoupper(trim((string)($r['region'] ?? '')));
            if ($gr !== '' && $nr !== '' && $gr !== $nr && cfg('v_regchk', '0') === '1') {
                zlog('chk', "region mismatch: бозӣ=$gr ник=$nr — рад шуд");
                continue;
            }
            q("UPDATE z_games SET can_chk=1, vcode=? WHERE id=?", [$cid, $gid]);
            return ['ok' => true, 'nick' => $r['nick'], 'region' => $r['region']];
        }
        if ($r['state'] === 'invalid') { $sawInvalid = true; continue; }
        if ($r['state'] === 'error')   { $lastErr = $r['msg'] ?? ''; continue; }
        if ($r['state'] === 'empty')   return ['ok' => false, 'msg' => 'ID_EMPTY'];
    }

    // санҷиш кор кард, вале бозингар ёфт нашуд
    if ($sawInvalid) {
        q("UPDATE z_games SET can_chk=1 WHERE id=?", [$gid]);
        return ['ok' => false, 'msg' => 'INVALID'];
    }
    if ($lastErr !== '') return ['ok' => false, 'msg' => $lastErr];

    q("UPDATE z_games SET can_chk=0 WHERE id=?", [$gid]);
    return ['skip' => true];
}

/** Фиристодани фармоиш */
function fz_place(int $oid): array {
    $o = one("SELECT * FROM z_orders WHERE id=?", [$oid]);
    if (!$o || $o['status'] !== 'new') return ['ok' => false, 'msg' => 'BAD_STATE'];
    $p = one("SELECT ft_code FROM z_packs WHERE id=?", [$o['pack_id']]);
    if (!$p || empty($p['ft_code'])) return ['ok' => false, 'msg' => 'MANUAL'];

    [$cid, $offer] = array_pad(explode('|', (string)$p['ft_code'], 2), 2, '');
    if ($cid === '' || $offer === '') {
        q("UPDATE z_packs SET active=0 WHERE id=?", [$o['pack_id']]);
        return ['ok' => false, 'msg' => 'BAD_SKU'];
    }

    $g = one("SELECT * FROM z_games WHERE id=?", [$o['game_id']]);
    $vals = json_decode((string)$o['note'], true);
    $f = [];
    foreach (game_fields($g ?: []) as $i => $x) {
        $f[$x['key']] = $i === 0 ? (string)$o['player_id'] : (string)($o['server_id'] ?? '');
    }
    if (is_array($vals)) foreach ($vals as $k => $v) if ($v !== '') $f[$k] = (string)$v;

    $ref = $o['ref'] ?: ('ZV' . $o['uid'] . '-' . $oid . '-' . bin2hex(random_bytes(3)));
    q("UPDATE z_orders SET ref=? WHERE id=? AND ref IS NULL", [$ref, $oid]);

    $r = fz('POST', '/topups/order', [],
            ['category_id' => $cid, 'offer_id' => $offer, 'fields' => (object)$f], $ref);
    if (empty($r['ok'])) return ['ok' => false, 'msg' => fzerr($r)];

    $ord = is_array($r['order'] ?? null) ? $r['order'] : $r;
    $fid = (string)(deepv($ord, ['order_id', 'id', 'public_id']) ?? '');
    $stt = (string)(deepv($ord, ['status']) ?? 'processing');
    q("UPDATE z_orders SET ft_id=? WHERE id=?", [$fid, $oid]);

    fz_apply($oid, $stt, (string)(deepv($ord, ['error', 'message', 'reason']) ?? ''), $ord);
    return ['ok' => true, 'status' => $stt];
}

/** Навсозии ҳолат */
function fz_apply(int $oid, string $stt, string $note = '', array $ord = []): void {
    $o = one("SELECT * FROM z_orders WHERE id=?", [$oid]);
    if (!$o || $o['status'] !== 'new') return;
    $l = mb_strtolower($stt);
    $done = str_contains($l, 'complet') || str_contains($l, 'success') || str_contains($l, 'delivered')
         || str_contains($l, 'fulfil') || str_contains($l, 'done');
    $bad  = str_contains($l, 'fail') || str_contains($l, 'refund') || str_contains($l, 'cancel')
         || str_contains($l, 'error') || str_contains($l, 'reject');

    $code = '';
    foreach (['cards', 'codes', 'keys'] as $k) {
        if (!empty($ord[$k]) && is_array($ord[$k])) {
            $arr = [];
            foreach ($ord[$k] as $x) $arr[] = is_array($x)
                ? (string)(deepv($x, ['code', 'key', 'value']) ?? json_encode($x))
                : (string)$x;
            $code = implode("\n", array_filter($arr));
            break;
        }
    }

    if ($done) order_done($oid, 0, $code);
    elseif ($bad) {
        if ($note !== '') pack_disable_if_gone((int)$o['pack_id'], $note);
        order_fail($oid, 0, $note !== '' ? $note : 'Провайдер рад кард');
    }
}

/** Санҷиши фармоишҳои дар коркард */
function fz_poll(): string {
    // 1) заказҳое ки ft_id доранд — статусро аз провайдер мепурсем
    $rows = all("SELECT id, ft_id FROM z_orders WHERE status='new' AND ft_id IS NOT NULL
                 AND ft_id<>'' AND created_at < ? ORDER BY id DESC LIMIT 40", [time() - 40]);
    $n = 0;
    foreach ($rows as $row) {
        $r = fz('GET', '/orders/' . rawurlencode((string)$row['ft_id']));
        if (empty($r['ok'])) continue;
        $ord = is_array($r['order'] ?? null) ? $r['order'] : $r;
        fz_apply((int)$row['id'], (string)(deepv($ord, ['status']) ?? ''),
                 (string)(deepv($ord, ['error', 'message', 'reason']) ?? ''), $ord);
        $n++;
        usleep(120000);
    }

    // 2) ФИНАЛӢ: заказҳое ки хеле кӯҳна шудаанд ва ҳанӯз 'new' мондаанд
    //    (провайдер ҷавоб надод, вебхук гум шуд, ё ft_id сабт нашуд) —
    //    пулро худкор бармегардонем. Ин кафолат аст: пул ҳеҷ гоҳ гум намешавад.
    //    20 дақиқа — вақти кофӣ барои иҷрои воқеӣ.
    try {
        $ref = refund_stuck(1200, true, 50);   // 1200 сония = 20 дақиқа
        if ($ref['done'] > 0) {
            $n += $ref['done'];
            foreach (ADMINS as $a) {
                try { say($a, "↩ <b>Худкор баргардонида шуд:</b> {$ref['done']} заказ · "
                    . money($ref['sum']) . "\n<i>(заказҳо иҷро нашуданд, пул ба муштариён баргашт)</i>"); }
                catch (Throwable $e) {}
            }
        }
    } catch (Throwable $e) { zlog('poll', 'auto-refund: ' . $e->getMessage()); }

    return (string)$n;
}

/** Вебхуки FazerCards — имзои HMAC-SHA256 санҷида мешавад */
function fz_webhook(): void {
    $raw = file_get_contents('php://input');
    $sig = '';
    foreach ($_SERVER as $k => $v) {
        if (in_array(strtoupper($k), ['HTTP_X_WEBHOOK_SIGNATURE', 'HTTP_X_SIGNATURE',
                                      'HTTP_X_FZ_SIGNATURE'], true)) { $sig = (string)$v; break; }
    }

    $ok = false;
    if (FZ_HOOK !== '' && $sig !== '' && $raw !== '') {
        $got = strtolower(trim(preg_replace('~^sha256=~i', '', $sig)));
        foreach ([FZ_HOOK, preg_replace('~^whsec_~', '', FZ_HOOK)] as $key) {
            if (hash_equals(hash_hmac('sha256', (string)$raw, $key), $got)) { $ok = true; break; }
        }
    }
    if (!$ok) zlog('hook_bad', mb_substr('sig=' . $sig . ' body=' . $raw, 0, 500));

    http_response_code(200);
    header('Content-Type: application/json');
    echo '{"ok":true}';

    $p = json_decode((string)$raw, true);
    if (!is_array($p)) return;
    zlog('hook', mb_substr($raw, 0, 900));

    $id = (string)(deepv($p, ['order_id', 'id']) ?? '');
    if ($id === '') return;
    $o = one("SELECT id FROM z_orders WHERE ft_id=?", [$id]);
    if (!$o) return;

    // ҳолатро аз API мегирем — бехатартар аз бовар ба худи вебхук
    $r = fz('GET', '/orders/' . rawurlencode($id));
    if (empty($r['ok'])) {
        if ($ok) fz_apply((int)$o['id'], (string)(deepv($p, ['status']) ?? ''),
                          (string)(deepv($p, ['error', 'message', 'reason']) ?? ''), $p);
        return;
    }
    $ord = is_array($r['order'] ?? null) ? $r['order'] : $r;
    fz_apply((int)$o['id'], (string)(deepv($ord, ['status']) ?? ''),
             (string)(deepv($ord, ['error', 'message', 'reason']) ?? ''), $ord);
}

/** Огоҳӣ дар бораи баланси кам */
function fz_low_balance(): void {
    if (!rate('lowbal', 1, 900)) return;
    $r = fz('GET', '/balance');
    if (empty($r['ok'])) return;
    $b = (float)str_replace(',', '.', (string)($r['balance'] ?? '0'));
    $lim = (float)cfg('lowbal', '5');
    $was = cfg('lownote', '0');
    if ($b <= $lim && $was === '0') {
        setcfg('lownote', '1');
        foreach (ADMINS as $a) {
            say($a, "◉ <b>БАЛАНСИ FAZERCARDS КАМ АСТ</b>\n<code>───────────────</code>\n"
                . "Ҳозир · <b>" . number_format($b, 2) . " USD</b>\n"
                . "Пур накунед — фармоишҳо иҷро намешаванд!");
        }
    } elseif ($b > $lim * 1.5 && $was === '1') setcfg('lownote', '0');
}

/* ======================= ФАРМОИШ ======================= */

function order_card(array $o, $uid = null): string {
    $st = ['new' => '○ Нав', 'done' => '● Иҷро шуд', 'fail' => '× Нашуд', 'refund' => '↩ Баргашт'];
    $t  = "<code>───────────────</code>\n";
    $t .= "<b>#" . str_pad((string)$o['id'], 5, '0', STR_PAD_LEFT) . "</b>  "
        . ($st[$o['status']] ?? $o['status']) . "\n";
    $t .= "<code>───────────────</code>\n";
    $t .= "Бозӣ · <b>" . h($o['game_name']) . "</b>\n";
    $t .= "Пакет · <b>" . h($o['pack_name']) . "</b>\n";
    $t .= "ID · <code>" . h($o['player_id']) . "</code>\n";
    if (!empty($o['server_id'])) $t .= "Server · <code>" . h($o['server_id']) . "</code>\n";
    $t .= "Маблағ · <b>" . money((float)$o['price']) . "</b>\n";
    if (!empty($o['promo'])) {
        $t .= "Промокод · <code>" . h((string)$o['promo']) . "</code> (−"
            . money((float)$o['discount']) . ")\n";
    }
    $t .= "Сана · " . date('d.m.Y H:i', (int)$o['created_at']) . "\n";
    if (!empty($o['code'])) $t .= "\nКод · <code>" . h($o['code']) . "</code>\n";
    if (!tech_note((string)($o['note'] ?? ''))) {
        $t .= "\n" . h(nice_err((string)$o['note'], $uid)) . "\n";
    }
    return $t;
}

function notify_order_admins(array $o): void {
    $u = one("SELECT name,username,phone FROM z_users WHERE id=?", [$o['uid']]);
    $t  = "<b>◆ ФАРМОИШИ НАВ</b>\n";
    $t .= order_card($o);
    $t .= "\nМуштарӣ · <a href=\"tg://user?id={$o['uid']}\">" . h($u['name'] ?? $o['uid']) . "</a>";
    if (!empty($u['username'])) $t .= " (@" . h($u['username']) . ")";
    foreach (ADMINS as $a) {
        say($a, $t, [
            [['text' => '● Иҷро шуд', 'callback_data' => 'ao:d:' . $o['id']],
             ['text' => '× Нашуд',    'callback_data' => 'ao:f:' . $o['id']]],
            [['text' => '⌨ Код фиристодан', 'callback_data' => 'ao:c:' . $o['id']]],
        ]);
    }
}

function order_done(int $oid, $adminId, string $code = ''): bool {
    $o = one("SELECT * FROM z_orders WHERE id=?", [$oid]);
    if (!$o || $o['status'] !== 'new') return false;
    q("UPDATE z_orders SET status='done', admin_id=?, code=?, done_at=? WHERE id=? AND status='new'",
      [$adminId, $code !== '' ? $code : null, time(), $oid]);
    q("UPDATE z_users SET orders_cnt=orders_cnt+1, spent=spent+? WHERE id=?", [$o['price'], $o['uid']]);

    $o = one("SELECT * FROM z_orders WHERE id=?", [$oid]);
    $t = "<b>● ФАРМОИШ ИҶРО ШУД</b>\n" . order_card($o) . "\n"
       . "<i>" . h(cfg('shop', '')) . " · " . h(cfg('support', '')) . "</i>";
    say($o['uid'], $t);
    ref_pay((int)$o['uid']);
    post_channel($o);

    if (cfg('ask_rev', '1') === '1') ask_review($oid);
    return true;
}

/** Пурсидани шарҳ барои як фармоиш (stars=0 → «пурсидем, ҷавоб нест») */
function ask_review(int $oid): bool {
    ensure_tables();
    $o = one("SELECT id, uid, status FROM z_orders WHERE id=?", [$oid]);
    if (!$o || $o['status'] !== 'done') return false;
    if (one("SELECT id FROM z_reviews WHERE order_id=?", [$oid])) return false;

    try {
        q("INSERT IGNORE INTO z_reviews (uid,order_id,stars,created_at) VALUES (?,?,0,?)",
          [(int)$o['uid'], $oid, time()]);
    } catch (Throwable $e) { return false; }

    $st = [];
    for ($i = 1; $i <= 5; $i++) $st[] = ['text' => str_repeat('★', $i),
                                         'callback_data' => 'rv:' . $oid . ':' . $i];
    $r = say((int)$o['uid'], "<b>" . T('revQ', (int)$o['uid']) . "</b>",
             [[$st[0], $st[1], $st[2]], [$st[3], $st[4]]]);
    return !empty($r['ok']);
}

/** Фармоишҳои иҷрошуда, ки ҳанӯз шарҳ пурсида нашудаанд */
function ask_reviews_pending(int $limit = 15): int {
    if (cfg('ask_rev', '1') !== '1') return 0;
    ensure_tables();
    $n = 0;
    foreach (all("SELECT o.id FROM z_orders o
                  LEFT JOIN z_reviews r ON r.order_id=o.id
                  WHERE o.status='done' AND r.id IS NULL
                    AND o.done_at > ? AND o.done_at < ?
                  ORDER BY o.id DESC LIMIT ?",
                 [time() - 3 * 86400, time() - 120, $limit]) as $row) {
        if (ask_review((int)$row['id'])) { $n++; usleep(350000); }
    }
    return $n;
}

/** Ёддошти хидматӣ (JSON) — ба муштарӣ нишон дода намешавад */
function tech_note(string $n): bool {
    $n = trim($n);
    if ($n === '' || $n === 'null' || $n === '[]' || $n === '{}') return true;
    return str_starts_with($n, '{') || str_starts_with($n, '[');
}

/** Хатои провайдерро ба матни фаҳмо табдил медиҳад */
function nice_err(string $m, $uid = null): string {
    $u = mb_strtoupper($m);
    $l = $uid ? ulang($uid) : 'tj';
    $map = [
      'INSUFFICIENT' => ['tj'=>'Мағоза муваққатан дастрас нест','ru'=>'Магазин временно недоступен',
                         'uz'=>'Do\'kon vaqtincha mavjud emas','ky'=>'Дүкөн убактылуу жеткиликсиз',
                         'en'=>'Shop temporarily unavailable','kk'=>'Дүкен уақытша қолжетімсіз'],
      'REGION'       => ['tj'=>'Минтақаи ҳисоб мувофиқ нест','ru'=>'Регион аккаунта не подходит',
                         'uz'=>'Hisob mintaqasi mos emas','ky'=>'Эсеп аймагы дал келбейт',
                         'en'=>'Account region not eligible','kk'=>'Тіркелгі аймағы сәйкес емес'],
      'PLAYER'       => ['tj'=>'ID-и бозингар нодуруст','ru'=>'Неверный ID игрока',
                         'uz'=>'O\'yinchi ID noto\'g\'ri','ky'=>'Оюнчу ID туура эмес',
                         'en'=>'Invalid player ID','kk'=>'Ойыншы ID қате'],
      'BAD_SKU'      => ['tj'=>'Ин пакет дигар дастрас нест','ru'=>'Этот пакет больше недоступен',
                         'uz'=>'Bu paket endi mavjud emas','ky'=>'Бул пакет жеткиликсиз',
                         'en'=>'This package is no longer available','kk'=>'Бұл пакет қолжетімсіз'],
      'NOT AVAILABLE'=> ['tj'=>'Ин пакет дастрас нест','ru'=>'Пакет недоступен',
                         'uz'=>'Paket mavjud emas','ky'=>'Пакет жеткиликсиз',
                         'en'=>'Package unavailable','kk'=>'Пакет қолжетімсіз'],
    ];
    foreach ($map as $k => $tr) if (str_contains($u, $k)) return $tr[$l] ?? $tr['tj'];
    return $m;
}


function order_fail(int $oid, $adminId, string $note = ''): bool {
    $o = one("SELECT * FROM z_orders WHERE id=?", [$oid]);
    if (!$o || $o['status'] !== 'new') return false;
    // атомарӣ: танҳо як маротиба refund мешавад
    $upd = q("UPDATE z_orders SET status='refund', admin_id=?, note=?, refunded=1, done_at=?
              WHERE id=? AND status='new' AND refunded=0", [$adminId, $note, time(), $oid]);
    if ($upd->rowCount() === 0) return false;

    q("UPDATE z_users SET balance=balance+? WHERE id=?", [$o['price'], $o['uid']]);
    tx($o['uid'], 'refund', (float)$o['price'],
       'Баргашт · ' . (string)$o['pack_name'], $oid);

    $nb = (float)(one("SELECT balance FROM z_users WHERE id=?", [$o['uid']])['balance'] ?? 0);
    try {
        say($o['uid'], "<b>× ФАРМОИШ НАШУД</b>\n"
            . order_card(one("SELECT * FROM z_orders WHERE id=?", [$oid]))
            . "\n<b>" . money((float)$o['price']) . "</b> ба ҳамён баргашт.\n"
            . "Баланс · <b>" . money($nb) . "</b>");
    } catch (Throwable $e) { zlog('order_fail', $e->getMessage()); }
    return true;
}

/**
 * Бехатар: заказро дар FazerCards мегузорад.
 * Ҳар хатогӣ/exception → пул фавран баргардонида мешавад (order_fail).
 * Ҳеҷ гоҳ пул бе натиҷа гум намешавад.
 */
function place_safe(int $oid, $uid): string {
    try {
        $res = fz_place($oid);
    } catch (Throwable $e) {
        zlog('place', "#$oid EXC: " . $e->getMessage());
        // провайдер афтод — пулро бармегардонем
        order_fail($oid, 0, 'Хатои провайдер: ' . mb_substr($e->getMessage(), 0, 80));
        return 'refunded';
    }

    if (empty($res['ok'])) {
        $msg = (string)($res['msg'] ?? 'FAIL');
        if ($msg === 'MANUAL') return 'manual';           // дастӣ — пул дар ҳисоб мемонад
        if (is_nobalance($msg)) { queue_add($oid, $uid, $msg); return 'queued'; }

        // ҳар хатои дигар → refund
        try {
            $pid = (int)(one("SELECT pack_id FROM z_orders WHERE id=?", [$oid])['pack_id'] ?? 0);
            if ($pid) pack_disable_if_gone($pid, $msg);
        } catch (Throwable $e) {}
        order_fail($oid, 0, $msg);
        return 'failed';
    }

    // fz_place гуфт ok=true. Вале ҳолати ВОҚЕИИ заказро месанҷем:
    // fz_apply шояд онро 'done' ё 'refund' карда бошад, ё ҳанӯз 'new' (processing) бошад.
    $st = (string)(one("SELECT status FROM z_orders WHERE id=?", [$oid])['status'] ?? 'new');
    if ($st === 'done')   return 'ok';        // алмаз расид ✓
    if ($st === 'refund') return 'refunded';  // провайдер рад кард, пул баргашт
    // ҳанӯз 'new' = провайдер қабул кард, вале дар коркард аст (processing).
    // fz_poll/cron онро пайгирӣ мекунад: ё иҷро мешавад, ё баъди 20 дақ пул бармегардад.
    return 'processing';
}

/**
 * Заказҳои "часпида": пул кам шуд, вале товар нашуд ва refund ҳам нашуд.
 * status='new' + refunded=0 + аз $minAge сония кӯҳнатар (то ҷории коркард нагирем).
 */
function stuck_orders(int $minAge = 900, int $limit = 500): array {
    return all("SELECT o.*, u.name, u.username, u.balance
                FROM z_orders o LEFT JOIN z_users u ON u.id=o.uid
                WHERE o.status='new' AND o.refunded=0
                  AND o.price > 0
                  AND o.created_at < ?
                ORDER BY o.id ASC LIMIT ?", [time() - $minAge, $limit]);
}

/** Ҳисоботи заказҳои часпида (барои нишон додан пеш аз баргардонидан) */
function stuck_report(int $minAge = 900): array {
    $rows = stuck_orders($minAge);
    $sum = 0.0; $users = [];
    foreach ($rows as $r) { $sum += (float)$r['price']; $users[(int)$r['uid']] = true; }
    return ['count' => count($rows), 'sum' => round($sum, 2),
            'users' => count($users), 'rows' => $rows];
}

/**
 * Баргардонидани пул барои заказҳои часпида.
 * Ҳар як заказ атомарӣ: танҳо як маротиба (refunded=0 дар шарт).
 * $notify = ба муштарӣ хабар диҳем ё не.
 */
function refund_stuck(int $minAge = 900, bool $notify = true, int $limit = 500): array {
    $rows = stuck_orders($minAge, $limit);
    $done = 0; $sum = 0.0; $notified = 0;

    foreach ($rows as $o) {
        $oid = (int)$o['id'];
        // атомарӣ — гонки хатарнок нест
        $upd = q("UPDATE z_orders SET status='refund', refunded=1,
                  note=CONCAT(COALESCE(note,''),' [авто-баргашт]'), done_at=?
                  WHERE id=? AND status='new' AND refunded=0", [time(), $oid]);
        if ($upd->rowCount() === 0) continue;   // касе аллакай коркард кард

        q("UPDATE z_users SET balance=balance+? WHERE id=?", [$o['price'], $o['uid']]);
        try { tx((int)$o['uid'], 'refund', (float)$o['price'],
                 'Баргашт (заказ иҷро нашуд) · ' . (string)$o['pack_name'], $oid); }
        catch (Throwable $e) {}

        $done++; $sum += (float)$o['price'];

        if ($notify) {
            $nb = (float)(one("SELECT balance FROM z_users WHERE id=?", [$o['uid']])['balance'] ?? 0);
            try {
                say((int)$o['uid'],
                    "<b>↩ ПУЛ БАРГАРДОНИДА ШУД</b>\n<code>───────────────</code>\n"
                    . h((string)$o['game_name']) . " · " . h((string)$o['pack_name']) . "\n"
                    . "Фармоиш #$oid иҷро нашуд.\n\n"
                    . "<b>" . money((float)$o['price']) . "</b> ба ҳамёни шумо баргашт.\n"
                    . "Баланс · <b>" . money($nb) . "</b>\n\n"
                    . "<i>Бубахшед барои нороҳатӣ.</i>");
                $notified++;
            } catch (Throwable $e) {}
            usleep(120000);   // то ки Telegram flood надиҳад
        }
    }
    return ['done' => $done, 'sum' => round($sum, 2), 'notified' => $notified];
}

/* ============ ШАРҲҲО (ОТЗЫВЫ) ============ */

/** Кадом канал: rev_ch → reviews → channel */
function rev_channel(): string {
    foreach (['rev_ch', 'reviews', 'channel'] as $k) {
        $v = trim(cfg($k, ''));
        if ($v !== '') {
            if ($v[0] !== '@' && $v[0] !== '-' && !ctype_digit(ltrim($v, '-'))) {
                if (preg_match('~t\.me/([A-Za-z0-9_]+)~', $v, $m)) $v = '@' . $m[1];
                else $v = '@' . ltrim($v, '@');
            }
            return $v;
        }
    }
    return '';
}

/**
 * Шарҳро ба канал мефиристад.
 * $force = дастӣ аз ҷониби админ (ҳатто агар ситораҳо кам бошанд).
 */
function post_review(int $oid, bool $force = false): bool {
    ensure_tables();
    $r = one("SELECT * FROM z_reviews WHERE order_id=?", [$oid]);
    if (!$r) return false;
    if ((int)$r['posted'] === 1 && !$force) return false;

    if ((int)$r['stars'] < 1) return false;      // ҳанӯз баҳо надодааст
    $stars = max(1, min(5, (int)$r['stars']));
    $min   = max(1, min(5, (int)cfg('rev_min', '4')));
    if ($stars < $min && !$force) return false;

    $ch = rev_channel();
    if ($ch === '') return false;

    $txt = trim((string)($r['txt'] ?? ''));
    if ($txt === '-') $txt = '';

    $o = one("SELECT game_name, pack_name FROM z_orders WHERE id=?", [$oid]);
    $u = one("SELECT name, username FROM z_users WHERE id=?", [(int)$r['uid']]);

    // ном: @username → ном → «Муштарӣ». Ҳангоми rev_anon танҳо ҳарфи аввал
    if (cfg('rev_anon', '0') === '1') {
        $nm = mb_substr(trim((string)($u['name'] ?? 'M')), 0, 1) . '***';
    } else {
        $nm = trim((string)($u['name'] ?? '')) ?: 'Муштарӣ';
        if (!empty($u['username'])) $nm = '@' . ltrim((string)$u['username'], '@');
    }

    $t  = str_repeat('★', $stars) . str_repeat('☆', 5 - $stars) . "\n";
    $t .= "<code>───────────────</code>\n";
    if (!empty($o['game_name'])) {
        $t .= "<b>" . h((string)$o['game_name']) . "</b>";
        if (!empty($o['pack_name'])) $t .= " · " . h((string)$o['pack_name']);
        $t .= "\n";
    }
    if ($txt !== '') $t .= "\n«" . h(mb_substr($txt, 0, 500)) . "»\n";
    $t .= "\n— " . h($nm) . "\n";
    $t .= "<code>───────────────</code>\n";
    $t .= "<i>" . h(cfg('shop', 'ZVER TAJ')) . "</i>";

    $kb = null;
    $bu = @bot_user();
    if ($bu !== '') {
        $kb = [[['text' => '▸ ' . mb_strtoupper(cfg('shop', 'ZVER TAJ')),
                 'url' => 'https://t.me/' . $bu]]];
    }

    $p = ['chat_id' => $ch, 'text' => $t, 'parse_mode' => 'HTML',
          'disable_web_page_preview' => true];
    if ($kb) $p['reply_markup'] = ['inline_keyboard' => $kb];
    $res = tg('sendMessage', $p);

    if (empty($res['ok'])) {
        zlog('review', 'post fail ' . $ch . ': ' . ($res['description'] ?? '?'));
        foreach (ADMINS as $a) {
            say($a, "⚠︎ <b>ШАРҲ ба канал НАРАФТ</b>\n<code>───────────────</code>\n"
                . "Канал · <code>" . h($ch) . "</code>\n"
                . "Сабаб · " . h((string)($res['description'] ?? 'номаълум')) . "\n\n"
                . "<i>Ботро ба канал админ кунед.</i>");
        }
        return false;
    }

    q("UPDATE z_reviews SET posted=1 WHERE order_id=?", [$oid]);
    return true;
}

function post_channel(array $o): void {
    $ch = trim(cfg('channel', ''));
    if ($ch === '') return;
    $u = one("SELECT name,username FROM z_users WHERE id=?", [$o['uid']]);
    $nm = $u['name'] ?? 'Корбар';
    if (!empty($u['username'])) $nm .= ' (@' . $u['username'] . ')';
    $t  = "<b>● ФАРМОИШ ИҶРО ШУД</b>\n<code>───────────────</code>\n";
    $t .= "Бозӣ · <b>" . h($o['game_name']) . "</b>\n";
    $t .= "Пакет · <b>" . h($o['pack_name']) . "</b>\n";
    $t .= "ID · <b>" . h($o['player_id']) . "</b>\n";
    $t .= "Маблағ · <b>" . money((float)$o['price']) . "</b>\n";
    $t .= "№ · <b>" . (int)$o['id'] . "</b>\n";
    $t .= "Муштарӣ · " . h($nm) . "\n<code>───────────────</code>";
    tg('sendMessage', ['chat_id' => $ch, 'text' => $t, 'parse_mode' => 'HTML']);
}

function ref_pay($uid): void {
    $u = one("SELECT ref_by, ref_paid, name, username FROM z_users WHERE id=?", [$uid]);
    if (!$u || empty($u['ref_by']) || (int)$u['ref_paid'] === 1) return;
    $inv = (int)$u['ref_by'];
    if ($inv === (int)$uid || !one("SELECT id FROM z_users WHERE id=?", [$inv])) return;
    $b = (float)cfg('ref_bonus', '0.50');
    if ($b <= 0) return;
    if (q("UPDATE z_users SET ref_paid=1 WHERE id=? AND ref_paid=0", [$uid])->rowCount() === 0) return;
    q("UPDATE z_users SET balance=balance+?, ref_sum=ref_sum+?, ref_cnt=ref_cnt+1 WHERE id=?",
      [$b, $b, $inv]);
    tx($inv, 'ref', $b, 'Бонуси даъват · ' . (string)($u['name'] ?: 'Дӯст'), (int)$uid);
    $s = one("SELECT balance, ref_cnt FROM z_users WHERE id=?", [$inv]);
    $nm = $u['name'] ?: 'Дӯст';
    say($inv, "<b>◆ БОНУСИ ДАЪВАТ</b>\n<code>───────────────</code>\n"
        . h($nm) . " хариди аввалро кард.\n\n"
        . "+ <b>" . money($b) . "</b>\n"
        . "Баланс · <b>" . money((float)$s['balance']) . "</b>\n"
        . "Дӯстон · <b>" . (int)$s['ref_cnt'] . "</b>");
}

/* ======================= ПУР КАРДАН ======================= */

/** Кӯҳна — акнун танҳо ба topup_credit равона мешавад (як ҷои ягона) */
function topup_approve(int $tid, $adminId): bool {
    return topup_credit($tid, $adminId, null, false, true);
}

/* ======================= ROUTER ======================= */

$IP = ip();
$IS_API = isset($_GET['api']);

// бан ба API дахл намекунад — то ки барнома нашиканад
if (banned($IP) && !$IS_API) { http_response_code(403); exit('banned'); }
if (!rate('ip:' . $IP, 600, 60)) {
    if (!$IS_API) ban($IP, 10, 'flood');
    http_response_code(429);
    header('Content-Type: application/json');
    exit('{"ok":false,"error":"RATE"}');
}
if (random_int(1, 40) === 1) {
    try {
        q("DELETE FROM z_rate WHERE win < ?", [time() - 900]);
        q("DELETE FROM z_bans WHERE until < ?", [time() - 86400]);
        q("DELETE FROM z_log WHERE at < ?", [time() - 14 * 86400]);
    } catch (Throwable $e) {}
}

try { migrate(); ensure_tables(); } catch (Throwable $e) {
    flog('MIGRATE: ' . $e->getMessage());
    if (isset($_GET['setup']) || isset($_GET['diag'])) {
        header('Content-Type: text/plain; charset=utf-8');
        exit("DB ERROR:\n" . $e->getMessage());
    }
    http_response_code(200); exit('ok');
}

if (isset($_GET['setup'])) {
    guard_page();
    $self = 'https://' . $_SERVER['HTTP_HOST'] . strtok($_SERVER['REQUEST_URI'], '?');
    $r = tg('setWebhook', ['url' => $self . '?s=' . SECRET, 'drop_pending_updates' => true,
                           'secret_token' => SECRET,
                           'allowed_updates' => ['message', 'callback_query']]);
    header('Content-Type: text/plain; charset=utf-8');
    echo "ZVER TAJ · " . VERSION . "\n\n";
    echo "setWebhook: " . json_encode($r, JSON_UNESCAPED_UNICODE) . "\n\n";
    echo "Mini App: " . app_url() . "\n";
    echo "FazerCards Webhook: {$self}?hook=fz\n";
    echo "Cron: curl -s \"{$self}?cron=1&secret=" . SECRET . "\"\n";
    exit;
}

if (isset($_GET['nickdiag'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    echo "=== ДИАГНОСТИКА ПРОВЕРКИ ID/НИКА ===\n" . VERSION . "\n\n";

    $gq  = trim((string)($_GET['game'] ?? ''));
    $id  = trim((string)($_GET['id'] ?? ''));
    $srv = trim((string)($_GET['srv'] ?? ''));
    if ($gq === '' || $id === '') {
        echo "Истифода:\n  ?nickdiag=1&secret=" . SECRET . "&game=Free Fire&id=12345678\n";
        echo "  (агар server лозим бошад: &srv=2000)\n\n";
        echo "-- Бозиҳои фаъол --\n";
        foreach (all("SELECT id,name,ft_code,vcode,need_server FROM z_games WHERE active=1 ORDER BY name LIMIT 60") as $g)
            echo "  #{$g['id']} " . str_pad($g['name'], 26) . " ft_code=" . ($g['ft_code'] ?: '—')
               . " vcode=" . ($g['vcode'] ?: '—') . ($g['need_server'] ? " [srv]" : '') . "\n";
        exit;
    }

    $g = one("SELECT * FROM z_games WHERE (name=? OR id=?) AND active=1", [$gq, (int)$gq])
      ?: one("SELECT * FROM z_games WHERE name LIKE ? AND active=1 LIMIT 1", ['%' . $gq . '%']);
    if (!$g) { echo "× Бозӣ ёфт нашуд: $gq\n"; exit; }

    echo "Бозӣ: {$g['name']} (#{$g['id']})\n";
    echo "  ft_code (FazerCards): " . ($g['ft_code'] ?: '—') . "\n";
    echo "  vcode (захирашуда)  : " . ($g['vcode'] ?: '—') . "\n";
    echo "  need_server         : " . ((int)($g['need_server'] ?? 0) ? 'ҳа' : 'не') . "\n";
    echo "  can_chk             : " . ((int)($g['can_chk'] ?? 0) ? 'ҳа' : 'не') . "\n\n";

    $vals = ['user_id' => $id];
    if ($srv !== '') $vals['server_id'] = $srv;
    echo "Даромад: user_id=$id" . ($srv !== '' ? " server_id=$srv" : '') . "\n";
    echo str_repeat('─', 40) . "\n\n";

    echo "Проверка региона (v_regchk): " . (cfg('v_regchk','0')==='1' ? 'ВКЛ' : 'выкл — ники не отбрасываются') . "\n\n";

    // 0a) gameskinbo (с ключом)
    echo "[0a] GAMESKINBO API (с ключом):\n";
    if (cfg('gs_nick', '1') !== '1') echo "  ⊘ хомӯш (gs_nick=0)\n";
    elseif (trim(cfg('gs_key', GS_KEY_DEFAULT)) === '') echo "  ⊘ калид нест — ?gskey=КЛЮЧ&secret=" . SECRET . "\n";
    else {
        $t0 = microtime(true);
        $gsr = gs_nick($g, $vals);
        $ms  = round((microtime(true) - $t0) * 1000);
        echo "  минтақаи бозӣ: " . (($g['region'] ?? '') ?: '—') . " · вақт: {$ms} мс\n";
        if ($gsr === null) echo "  → НИК: (нест) — ҷавоб надод, лимит, ё ID ёфт нашуд\n";
        else {
            echo "  → НИК: «{$gsr['nick']}» · минтақа: {$gsr['region']}\n";
            $gr = mb_strtoupper((string)($g['region'] ?? ''));
            if ($gr !== '' && $gsr['region'] !== '' && $gr !== $gsr['region'])
                echo "  ℹ️ минтақаи маҳсулот ($gr) ≠ минтақаи аккаунт ({$gsr['region']}) — ин ОДДӢ аст\n"
                   . "     (муқоиса " . (cfg('v_regchk','0')==='1' ? 'ФАЪОЛ — ник рад мешавад' : 'хомӯш — ник нишон дода мешавад') . ")\n";
            else echo "  ✓ минтақа мувофиқ — ҳамин ник нишон дода мешавад\n";
        }
    }
    echo "\n";

    // 0b) Free Fire открытый API
    echo "[0b] FREE FIRE API (открытый, без ключа):\n";
    if (cfg('ff_nick', '1') !== '1') echo "  ⊘ хомӯш (ff_nick=0)\n";
    else {
        $t0 = microtime(true);
        $ffr = ff_nick($g, $vals);
        $ms  = round((microtime(true) - $t0) * 1000);
        echo "  сервер: " . cfg('ff_api', 'https://free-ff-api-src-5plp.onrender.com') . "\n";
        echo "  минтақаи бозӣ: " . (($g['region'] ?? '') ?: '—') . " · вақт: {$ms} мс\n";
        if ($ffr === null) {
            echo "  → НИК: (нест) — сервис ҷавоб надод ё ID ёфт нашуд\n";
            echo "  <i>агар ҳамеша чунин бошад: сервиси ройгон хоб рафтааст,\n";
            echo "   ё ин бозӣ Free Fire нест</i>\n";
        } else {
            echo "  → НИК: «{$ffr['nick']}» · минтақа: {$ffr['region']}\n";
            echo "  ✓ ИН ники ДУРУСТ аст — ҳамин ба клиент нишон дода мешавад\n";
        }
    }
    echo "\n";

    // 1) FlashTopup
    echo "[1] FLASHTOPUP (ft_nick):\n";
    if (cfg('ft_nick', '1') !== '1') echo "  ⊘ хомӯш (ft_nick=0)\n";
    else {
        $m = ftv_match($g);
        echo "  validation_code мувофиқ: " . ($m['vc'] ?? '— НЕСТ (барои ин бозӣ код ёфт нашуд)') . "\n";
        if ($m) {
            $body = ['user_id' => $id, 'validation_code' => $m['vc']];
            if ($srv !== '') $body['server_id'] = $srv;
            $r = ft('POST', '/check-id', [], $body);
            echo "  HTTP: " . ($r['http'] ?? '?') . " · success: " . json_encode($r['success'] ?? false) . "\n";
            $d = is_array($r['data'] ?? null) ? $r['data'] : [];
            echo "  ҷавоб: " . json_encode($d, JSON_UNESCAPED_UNICODE) . "\n";
            $nick = '';
            foreach (['account_name','username','nickname','name','player_name'] as $k)
                if (!empty($d[$k]) && is_string($d[$k])) { $nick = $d[$k]; break; }
            echo "  → НИК: " . ($nick !== '' ? "«$nick»" : '(нест)') . "\n";
            if ($nick !== '' && $nick === $id) echo "  ⚠️ ник = введённому ID — FlashTopup вернул сам ID, значит НЕ проверил реально!\n";
        }
    }
    echo "\n";

    // 2) FazerCards — все кандидаты по очереди
    echo "[2] FAZERCARDS (try_validate, по порядку):\n";
    $cands = [];
    $saved = trim((string)($g['vcode'] ?? ''));
    if ($saved !== '') $cands[] = ['id' => $saved, 'keys' => [], 'src' => 'захирашуда vcode'];
    $own = [];
    foreach (game_fields($g) as $f) if (!empty($f['key'])) $own[] = (string)$f['key'];
    $cands[] = ['id' => (string)$g['ft_code'], 'keys' => $own, 'src' => 'ft_code + майдонҳои бозӣ'];
    $cands[] = ['id' => (string)$g['ft_code'], 'keys' => ['user_id'], 'src' => 'ft_code + user_id'];
    if ((int)($g['need_server'] ?? 0) === 1)
        $cands[] = ['id' => (string)$g['ft_code'], 'keys' => ['user_id','server_id'], 'src' => 'ft_code + user_id+server_id'];

    $seen = [];
    foreach ($cands as $c) {
        $cid = trim((string)$c['id']);
        if ($cid === '') continue;
        $sig = $cid . '|' . implode(',', $c['keys']);
        if (isset($seen[$sig])) continue;
        $seen[$sig] = 1;
        echo "  • category={$cid} · keys=[" . implode(',', $c['keys']) . "] ({$c['src']})\n";
        $r = try_validate($cid, $c['keys'], $vals);
        echo "    → state={$r['state']}"
           . (isset($r['nick']) ? " · НИК=«{$r['nick']}»" : '')
           . (isset($r['msg']) ? " · " . mb_substr($r['msg'], 0, 80) : '') . "\n";
        if ($r['state'] === 'ok') { echo "    ✓ ЭТОТ вариант вернул ник — бот сохранит vcode={$cid}\n"; break; }
    }
    echo "\n" . str_repeat('─', 40) . "\n";

    // 3) Итог — что реально покажет клиенту
    echo "[3] ЧТО ПОКАЖЕТ КЛИЕНТУ (fz_check):\n";
    $fin = fz_check($g, $vals);
    echo json_encode($fin, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n";
    $srcMap = ['ff' => 'Free Fire API (открытый)', 'ft' => 'FlashTopup (старый сервис)'];
    if (!empty($fin['nick'])) {
        $src = (string)($fin['src'] ?? 'fz');
        echo "\n>>> ИСТОЧНИК НИКА: " . ($srcMap[$src] ?? 'FazerCards (validate-id)') . "\n";
        $gr = mb_strtoupper((string)($g['region'] ?? ''));
        $nr = mb_strtoupper((string)($fin['region'] ?? ''));
        if ($gr !== '' && $nr !== '' && $gr !== $nr) {
            echo ">>> ⚠️ ВНИМАНИЕ: минтақаи бозӣ ($gr) ≠ минтақаи ник ($nr)\n";
            echo ">>>    ЭТО ЧУЖОЙ ИГРОК! Проверка идёт не в том регионе.\n";
        }
    }
    echo "\nЕсли ник ЧУЖОЙ:\n";
    echo "  • кэш ника сбросить:  ?ffclear=" . $id . "&secret=" . SECRET . "\n";
    echo "  • весь кэш ников:     ?ffclear=1&secret=" . SECRET . "\n";
    echo "  • сохранённый vcode:  ?nickreset=" . $g['id'] . "&secret=" . SECRET . "\n";
    exit;
}

if (isset($_GET['vlist'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    echo "=== ИГРЫ, КОТОРЫЕ FAZERCARDS УМЕЕТ ПРОВЕРЯТЬ ===\n\n";
    $list = vlist(true);   // force — свежий список
    if (!$list) {
        echo "× Список пуст. FazerCards не вернул поддерживаемых категорий.\n";
        echo "  Значит проверка ника у FazerCards недоступна для вашего тарифа.\n";
        exit;
    }
    $q = mb_strtolower(trim((string)($_GET['q'] ?? '')));
    echo "Всего категорий с проверкой: " . count($list) . "\n";
    if ($q !== '') echo "Фильтр: «$q»\n";
    echo str_repeat('─', 50) . "\n";
    foreach ($list as $v) {
        $nm = mb_strtolower((string)$v['name']);
        $cid = mb_strtolower((string)$v['id']);
        if ($q !== '' && !str_contains($nm, $q) && !str_contains($cid, $q)) continue;
        $keys = [];
        foreach (($v['fields'] ?? []) as $f) if (!empty($f['key'])) $keys[] = (string)$f['key'];
        echo "  category_id: {$v['id']}\n";
        echo "     name: {$v['name']}\n";
        echo "     поля: [" . implode(', ', $keys) . "]\n\n";
    }
    echo str_repeat('─', 50) . "\n";
    echo "Найдите тут Free Fire — возьмите его точный category_id.\n";
    echo "Если Free Fire ЕСТЬ в списке, но у игры в боте ft_code другой —\n";
    echo "проверка не работает из-за неправильного кода.\n";
    echo "\nПоиск по слову:  ?vlist=1&q=fire&secret=" . SECRET . "\n";
    exit;
}

if (isset($_GET['gskey'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    $v = trim((string)$_GET['gskey']);
    if ($v === '0' || $v === '1') {
        setcfg('gs_nick', $v);
        echo "gs_nick = " . cfg('gs_nick', '1') . "  (1=вкл, 0=выкл)\n";
    } elseif ($v !== '' && $v !== 'show') {
        setcfg('gs_key', $v);
        echo "Ключ сохранён: " . mb_substr($v, 0, 6) . "..." . mb_substr($v, -4) . "\n";
    }
    $k = cfg('gs_key', GS_KEY_DEFAULT);
    echo "\nСейчас:\n";
    echo "  gs_nick = " . cfg('gs_nick', '1') . "\n";
    echo "  gs_key  = " . ($k === '' ? '(не задан)' : mb_substr($k, 0, 6) . '...' . mb_substr($k, -4)) . "\n";
    echo "  gs_api  = " . cfg('gs_api', 'https://api.gameskinbo.com') . "\n";
    // санҷиши лимит
    if ($k !== '') {
        $ch = curl_init(rtrim(cfg('gs_api', 'https://api.gameskinbo.com'), '/') . '/api/usage');
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 8,
            CURLOPT_HTTPHEADER => ['x-api-key: ' . $k, 'Accept: application/json']]);
        $r = curl_exec($ch); $c = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE); curl_close($ch);
        echo "\n-- ЛИМИТ (api/usage) --\nHTTP $c\n" . (string)$r . "\n";
    }
    echo "\nИспользование:\n";
    echo "  ?gskey=ВАШ_КЛЮЧ&secret=" . SECRET . "\n";
    echo "  ?gskey=0&secret=" . SECRET . "   — выключить\n";
    echo "  ?gskey=1&secret=" . SECRET . "   — включить\n";
    exit;
}

if (isset($_GET['ffclear'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    $u = trim((string)$_GET['ffclear']);
    if ($u !== '' && $u !== '1' && ctype_digit($u)) {
        q("DELETE FROM z_settings WHERE k IN (?,?)", ['ffn:' . $u, 'gsn:' . $u]);
        echo "Кэш ника для ID $u очищен (оба сервиса).\n";
    } else {
        $n1 = q("DELETE FROM z_settings WHERE k LIKE 'ffn:%'")->rowCount();
        $n2 = q("DELETE FROM z_settings WHERE k LIKE 'gsn:%'")->rowCount();
        echo "Очищен кэш ников: ffn=$n1 gsn=$n2\n";
    }
    echo "\nСледующая проверка запросит ник заново.\n";
    exit;
}

if (isset($_GET['ffset'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    $v = (string)$_GET['ffset'];
    if ($v === '0' || $v === '1') {
        setcfg('ff_nick', $v);
        echo "ff_nick = " . cfg('ff_nick', '1') . "  (1=Free Fire API вкл, 0=выкл)\n";
    } elseif (str_starts_with($v, 'http')) {
        setcfg('ff_api', rtrim($v, '/'));
        echo "ff_api = " . cfg('ff_api', '') . "\n(адрес сервиса изменён)\n";
    } else {
        echo "Использование:\n";
        echo "  ?ffset=1&secret=" . SECRET . "         — включить\n";
        echo "  ?ffset=0&secret=" . SECRET . "         — выключить\n";
        echo "  ?ffset=https://ДРУГОЙ-АДРЕС&secret=" . SECRET . "  — сменить сервер\n\n";
        echo "Сейчас: ff_nick=" . cfg('ff_nick', '1') . " · ff_api=" . cfg('ff_api', 'https://free-ff-api-src-5plp.onrender.com') . "\n";
    }
    exit;
}

if (isset($_GET['nickset'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    setcfg('ft_nick', $_GET['nickset'] === '1' ? '1' : '0');
    echo "ft_nick = " . cfg('ft_nick', '1') . "\n(1=FlashTopup вкл, 0=выкл — тогда ник берёт FazerCards)\n";
    exit;
}

if (isset($_GET['nickreset'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    $gid = (int)$_GET['nickreset'];
    if ($gid > 0) {
        q("UPDATE z_games SET vcode='', can_chk=0 WHERE id=?", [$gid]);
        echo "Игра #$gid: сброшен сохранённый vcode. Следующая проверка подберёт заново.\n";
    } else {
        q("UPDATE z_games SET vcode='', can_chk=0");
        echo "Сброшены vcode у ВСЕХ игр (пересоберутся при проверке).\n";
    }
    // очистим кэш validation-кодов FlashTopup тоже
    setcfg('ftv', ''); setcfg('ftv_at', '0');
    echo "Кэш validation-кодов FlashTopup тоже очищен.\n";
    exit;
}

if (isset($_GET['diag'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    echo "ZVER TAJ " . VERSION . "\nPHP " . PHP_VERSION . "\n";
    echo "FILE " . date('Y-m-d H:i:s', (int)@filemtime(__FILE__)) . "\n\n";
    foreach (['curl', 'pdo_mysql', 'mbstring', 'gd'] as $x) {
        echo str_pad($x, 12) . (extension_loaded($x) ? 'OK' : 'НЕТ') . "\n";
    }
    $ga = (int)(one("SELECT COUNT(*) c FROM z_games WHERE active=1")['c'] ?? 0);
    $gt = (int)(one("SELECT COUNT(*) c FROM z_games")['c'] ?? 0);
    $pa = (int)(one("SELECT COUNT(*) c FROM z_packs WHERE active=1")['c'] ?? 0);
    $pt = (int)(one("SELECT COUNT(*) c FROM z_packs")['c'] ?? 0);
    $vis = (int)(one("SELECT COUNT(*) c FROM z_games g WHERE g.active=1
                      AND EXISTS(SELECT 1 FROM z_packs p WHERE p.game_id=g.id AND p.active=1)")['c'] ?? 0);
    $t0 = microtime(true);
    try { db()->query("SELECT 1")->fetch(); } catch (Throwable $e) {}
    echo "\nDB ping: " . round((microtime(true) - $t0) * 1000) . " мс";
    echo " | db_ver: " . (cfg('db_ver', '—') === VERSION ? 'нав ●' : 'кӯҳна ×') . "\n";
    echo "\nБозиҳо: $ga / $gt фаъол | Пакетҳо: $pa / $pt фаъол\n";
    echo "Дар мағоза нишон дода мешавад: $vis бозӣ\n";
    echo "Корбарон: " . (one("SELECT COUNT(*) c FROM z_users")['c'] ?? 0) . "\n";
    echo "Фармоишҳо: " . (one("SELECT COUNT(*) c FROM z_orders")['c'] ?? 0)
       . " | Нав: " . (one("SELECT COUNT(*) c FROM z_orders WHERE status='new'")['c'] ?? 0) . "\n\n";

    // -- ЗАКАЗҲОИ ЧАСПИДА (пул кам шуд, товар нашуд, refund нашуд) — ТАНҲО НАМОИШ --
    echo "-- ПУЛИ ЧАСПИДА (танҳо намоиш, баргардонида НАМЕШАВАД) --\n";
    $stuckAll = all("SELECT o.id,o.uid,o.pack_name,o.price,o.created_at,o.ft_id,
                            u.name,u.username,u.balance
                     FROM z_orders o LEFT JOIN z_users u ON u.id=o.uid
                     WHERE o.status='new' AND o.refunded=0 AND o.price>0
                     ORDER BY o.created_at ASC");
    if (!$stuckAll) {
        echo "Нест — ҳама пул зачислено ё баргардонида шудааст.\n\n";
    } else {
        $now = time(); $sumOld = 0.0; $nOld = 0; $sumNew = 0.0; $nNew = 0;
        foreach ($stuckAll as $o) {
            $age = $now - (int)$o['created_at'];
            $old = $age >= 900;                 // >15 дақиқа = часпида
            if ($old) { $sumOld += (float)$o['price']; $nOld++; }
            else      { $sumNew += (float)$o['price']; $nNew++; }
            $mins = floor($age / 60);
            echo ($old ? '● ЧАСПИД ' : '○ нав     ')
               . '#' . (int)$o['id'] . ' · '
               . mb_substr((string)($o['name'] ?? $o['uid']), 0, 14)
               . (!empty($o['username']) ? ' @' . $o['username'] : '')
               . ' · ' . number_format((float)$o['price'], 2) . ' смн'
               . ' · ' . mb_substr((string)$o['pack_name'], 0, 22)
               . ' · ' . $mins . ' дақ пеш'
               . (empty($o['ft_id']) ? ' · [провайдер: НЕ размещён]' : ' · ft=' . $o['ft_id'])
               . "\n";
        }
        echo "\nЧАСПИДА (>15 дақ): $nOld заказ · " . number_format($sumOld, 2) . " смн"
           . "  ← инро тугмаи «↩ Баргардонидан» бармегардонад\n";
        echo "Нав (дар коркард): $nNew заказ · " . number_format($sumNew, 2) . " смн"
           . "  (ҳоло даст нарасонед)\n";
    }
    echo "\n";

    // -- ГУМОНБАР: заказ 'done' аст, вале алмаз шояд нарасида бошад --
    echo "-- ГУМОНБАР (иҷрошуда, вале алмаз шояд НАРАСИД) --\n";
    // 1) done вале ft_id холӣ = ба провайдер нарафт, вале иҷрошуда ҳисоб шуд
    $susp1 = all("SELECT id,uid,pack_name,price,created_at,done_at,admin_id
                  FROM z_orders
                  WHERE status='done' AND (ft_id IS NULL OR ft_id='') AND admin_id=0
                  ORDER BY id DESC LIMIT 15");
    // 2) done хеле зуд (камтар аз 8 сония баъди сохт) — провайдер физически нарасонда
    $susp2 = all("SELECT id,uid,pack_name,price,created_at,done_at,ft_id
                  FROM z_orders
                  WHERE status='done' AND done_at>0 AND created_at>0
                    AND (done_at - created_at) < 8 AND (done_at - created_at) >= 0
                  ORDER BY id DESC LIMIT 15");
    if (!$susp1 && !$susp2) {
        echo "Нест — ҳамаи заказҳои иҷрошуда ба провайдер рафтаанд.\n";
    } else {
        if ($susp1) {
            echo "[A] 'done' вале ба провайдер нарафт (ft_id холӣ):\n";
            foreach ($susp1 as $o) {
                echo "  #" . (int)$o['id'] . " · uid=" . (int)$o['uid']
                   . " · " . number_format((float)$o['price'], 2) . " смн · "
                   . mb_substr((string)$o['pack_name'], 0, 22) . " · "
                   . date('d.m H:i', (int)$o['created_at']) . "\n";
            }
        }
        if ($susp2) {
            echo "[B] 'done' хеле зуд (<8 сония, шояд алмаз нарасид):\n";
            foreach ($susp2 as $o) {
                echo "  #" . (int)$o['id'] . " · uid=" . (int)$o['uid']
                   . " · " . number_format((float)$o['price'], 2) . " смн · "
                   . mb_substr((string)$o['pack_name'], 0, 22)
                   . " · ft=" . ((string)$o['ft_id'] ?: '—') . "\n";
            }
        }
        echo "<< инҳоро дастӣ санҷед: ба FazerCards нигаред, алмаз расид ё не >>\n";
    }
    echo "\n";
    echo json_encode(tg('getWebhookInfo')['result'] ?? [], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n\n";
    echo "-- FAZERCARDS --\n";
    echo json_encode(fz('GET', '/me'), JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE) . "\n";
    echo json_encode(fz('GET', '/balance'), JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE) . "\n\n";
    echo "Фоида " . cfg('markup') . "% | Курс " . cfg('rate')
       . " | Худкор " . cfg('auto', '1') . "\n\n";
    echo "-- ВЕБХУКҲО --\n";
    foreach (all("SELECT tag,txt,at FROM z_log WHERE tag IN ('hook','hook_bad')
                  ORDER BY id DESC LIMIT 5") as $l) {
        echo date('H:i:s', (int)$l['at']) . ' [' . $l['tag'] . '] '
           . mb_substr((string)$l['txt'], 0, 200) . "\n";
    }
    echo "\n";
    if (is_file(ZLOG)) echo "-- ХАТОҲО --\n" . implode('', array_slice(@file(ZLOG) ?: [], -20));
    exit;
}

if (in_array($_GET['hook'] ?? '', ['fz', 'ft'], true)) { fz_webhook(); exit; }

if (isset($_GET['bankpay'])) { bankpay(); exit; }

if (isset($_GET['cron'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    $bc = bank_recheck();
    echo "bank auto: {$bc['ok']} | rejected: {$bc['rej']}\n";
    [$qd, $ql] = queue_run();
    echo "queue: done=$qd left=$ql\n";
    echo "poll: " . fz_poll() . "\n";
    $n = (int)(one("SELECT COUNT(*) c FROM z_orders WHERE status='new' AND created_at < ?
                    AND ref IS NULL", [time() - 1800])['c'] ?? 0);
    if ($n > 0) foreach (ADMINS as $a) say($a, "⏰ <b>$n фармоиши дастӣ интизор аст</b>");
    echo "manual pending: $n\n";
    echo "reviews asked: " . ask_reviews_pending() . "\n";

    // --- ТОЗАКУНӢ: ҷадвалҳое ки калон мешаванд (барои 10k корбар муҳим) ---
    try {
        $now = time();
        // rate-limit: тирезаҳои кӯҳна (>1 соат) дигар лозим нест
        $d1 = q("DELETE FROM z_rate WHERE win < ?", [$now - 3600])->rowCount();
        // bans: мӯҳлаташон гузашта
        $d2 = q("DELETE FROM z_bans WHERE until < ?", [$now])->rowCount();
        // hooks-dedup: калидҳои кӯҳна (>7 рӯз)
        $d3 = q("DELETE FROM z_hooks WHERE at < ?", [$now - 7 * 86400])->rowCount();
        // bank-уведомления кӯҳна (>3 рӯз)
        $d4 = 0;
        try { $d4 = q("DELETE FROM z_bank WHERE created_at < ?", [$now - 3 * 86400])->rowCount(); }
        catch (Throwable $e) {}
        echo "cleanup: rate=$d1 bans=$d2 hooks=$d3 bank=$d4\n";
        // кэши никҳо (ffn:*) — калонтар аз 3000 шавад, кӯҳнаҳоро мебарорем
        try {
            foreach (['ffn:', 'gsn:'] as $pfx) {
                $cn = (int)(one("SELECT COUNT(*) c FROM z_settings WHERE k LIKE ?", [$pfx . '%'])['c'] ?? 0);
                if ($cn > 3000) {
                    q("DELETE FROM z_settings WHERE k LIKE ? ORDER BY k LIMIT ?", [$pfx . '%', $cn - 2000]);
                    echo "nick-cache $pfx trimmed: $cn → 2000\n";
                }
            }
        } catch (Throwable $e) {}
    } catch (Throwable $e) { echo "cleanup err: " . $e->getMessage() . "\n"; }

    // лог-файл калон нашавад (>2 МБ → буриш то охирин 500 сатр)
    try {
        if (is_file(ZLOG) && @filesize(ZLOG) > 2 * 1024 * 1024) {
            $lines = @file(ZLOG) ?: [];
            @file_put_contents(ZLOG, implode('', array_slice($lines, -500)));
            echo "log trimmed\n";
        }
    } catch (Throwable $e) {}

    exit;
}

if (isset($_GET['trace'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');

    if (isset($_GET['on']))  { setcfg('trace', '1'); echo "Трассировка ФАЪОЛ\n\n"; }
    if (isset($_GET['off'])) { setcfg('trace', '0'); echo "Трассировка хомӯш\n\n"; }

    echo "Ҳолат: " . (cfg('trace', '0') === '1' ? 'ФАЪОЛ' : 'хомӯш') . "\n";
    echo "Версия: " . VERSION . "\n\n";

    // санҷиши мустақими фиристодан
    if (!empty($_GET['send'])) {
        $to = (int)$_GET['send'];
        $t0 = microtime(true);
        $r = say($to, "◆ Санҷиш аз сервер · " . date('H:i:s'));
        echo "sendMessage → " . $to . "\n";
        echo json_encode($r, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n";
        echo "Вақт: " . round((microtime(true) - $t0) * 1000) . " мс\n\n";
    }

    echo "-- ОХИРИН 25 ҲОДИСА --\n";
    foreach (all("SELECT tag,txt,at FROM z_log WHERE tag IN ('trace','handle','admin')
                  ORDER BY id DESC LIMIT 25") as $l) {
        echo date('H:i:s', (int)$l['at']) . ' [' . $l['tag'] . '] '
           . mb_substr((string)$l['txt'], 0, 160) . "\n";
    }
    echo "\nМисол: ?trace=1&on=1&secret=" . SECRET . "\n";
    echo "       ?trace=1&send=" . (ADMINS[0] ?? '') . "&secret=" . SECRET . "\n";
    exit;
}

if (isset($_GET['dbfix'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    try { q("DELETE FROM z_settings WHERE k='db_ver'"); } catch (Throwable $e) {}
    $t0 = microtime(true);
    try {
        db()->exec("CREATE TABLE IF NOT EXISTS z_settings (k VARCHAR(64) PRIMARY KEY, v TEXT)
                    ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
        migrate();
        ensure_tables();
        echo "● База нав шуд\n";
    } catch (Throwable $e) {
        echo "× " . $e->getMessage() . "\n";
    }
    echo "Вақт: " . round((microtime(true) - $t0) * 1000) . " мс\n\n";
    foreach (['z_users','z_games','z_packs','z_orders','z_topups','z_reqs','z_promo',
              'z_promo_use','z_reviews','z_queue','z_checks','z_bank','z_log',
              'z_rate','z_bans','z_state','z_hooks','z_settings'] as $tb) {
        try {
            $c = db()->query("SELECT COUNT(*) c FROM `$tb`")->fetch();
            echo str_pad($tb, 14) . " OK  " . (int)($c['c'] ?? 0) . "\n";
        } catch (Throwable $e) { echo str_pad($tb, 14) . " НЕСТ\n"; }
    }
    exit;
}

if (isset($_GET['unban'])) {
    if (($_GET['secret'] ?? '') !== SECRET) { http_response_code(403); exit('forbidden'); }
    header('Content-Type: text/plain; charset=utf-8');
    $b = 0; $r = 0;
    try { $b = q("DELETE FROM z_bans")->rowCount(); } catch (Throwable $e) {}
    try { $r = q("DELETE FROM z_rate")->rowCount(); } catch (Throwable $e) {}
    try { q("DELETE FROM z_log WHERE tag='trace'"); } catch (Throwable $e) {}
    echo "Банҳо тоза шуд: $b\nЛимитҳо тоза шуд: $r\nШумо: " . ip() . "\n";
    echo "\nАкнун ба бот /start нависед.\n";
    exit;
}

if (isset($_GET['packs'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    $q = trim((string)($_GET['packs'] ?? ''));
    if ($q === '' || $q === '1') { echo "Мисол: ?packs=free fire cis&secret=...\n"; exit; }

    $gs = ctype_digit($q)
        ? all("SELECT * FROM z_games WHERE id=?", [(int)$q])
        : all("SELECT * FROM z_games WHERE name LIKE ? ORDER BY name LIMIT 6", ['%' . $q . '%']);

    foreach ($gs as $g) {
        echo "\n" . str_repeat('=', 60) . "\n";
        echo $g['name'] . "   [id=" . $g['id'] . ", рег=" . ($g['region'] ?: '—') . "]\n";
        echo str_repeat('=', 60) . "\n";
        printf("%-38s %-10s %8s\n", 'НОМ', 'КАТЕГОРИЯ', 'НАРХ');
        foreach (all("SELECT * FROM z_packs WHERE game_id=? ORDER BY cat, price",
                     [$g['id']]) as $p) {
            printf("%-38s %-10s %8.2f%s\n",
                mb_substr($p['name'], 0, 37), $p['cat'] ?: 'main', (float)$p['price'],
                (int)$p['active'] ? '' : '  (хомӯш)');
        }
    }
    exit;
}

if (isset($_GET['price'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');

    $q  = trim((string)($_GET['price'] ?? ''));
    if ($q === '' || $q === '1') $q = 'free fire';
    $rate   = (float)($_GET['rate']   ?? cfg('rate', '11'));
    $markup = (float)($_GET['markup'] ?? cfg('markup', '20'));
    $step   = (float)($_GET['round']  ?? cfg('round', '0.5'));
    $cur    = cfg('cur', 'TJS');

    $calc = function (float $cost) use ($rate, $markup, $step): float {
        $p = $cost * $rate * (1 + $markup / 100);
        if ($step > 0) $p = ceil($p / $step) * $step;
        return round($p, 2);
    };

    echo "НАРХИ ФУРӮШ · " . mb_strtoupper($q) . "\n";
    echo str_repeat('=', 62) . "\n";
    echo "Курс: 1 USD = $rate $cur   |   Фоида: $markup%   |   Гирдкунӣ: $step\n";
    echo str_repeat('=', 62) . "\n\n";

    $games = all("SELECT * FROM z_games WHERE (base LIKE ? OR name LIKE ?) AND active=1
                  ORDER BY region, name", ['%' . $q . '%', '%' . $q . '%']);
    if (!$games) { echo "Бозӣ ёфт нашуд.\n"; exit; }

    $sumOld = 0.0; $sumNew = 0.0; $sumCost = 0.0; $n = 0;

    foreach ($games as $g) {
        $packs = all("SELECT * FROM z_packs WHERE game_id=? AND active=1
                      ORDER BY cat, price", [$g['id']]);
        if (!$packs) continue;

        echo "\n" . str_repeat('-', 62) . "\n";
        echo mb_strtoupper($g['name']) . "   [" . ($g['region'] ?: '—') . "]\n";
        echo str_repeat('-', 62) . "\n";
        printf("%-30s %8s %10s %10s\n", 'ПАКЕТ', 'USD', 'ҲОЗИР', 'НАВ');

        $catNow = '';
        foreach ($packs as $p) {
            if ($p['cat'] !== $catNow) {
                $catNow = (string)$p['cat'];
                echo "  · " . cat_name($catNow, 'tj') . "\n";
            }
            $cost = (float)$p['cost'];
            $old  = (float)$p['price'];
            $new  = $calc($cost);
            $sumCost += $cost; $sumOld += $old; $sumNew += $new; $n++;
            printf("%-30s %8.4f %10.2f %10.2f%s\n",
                mb_substr($p['name'], 0, 29), $cost, $old, $new,
                abs($new - $old) > 0.004 ? ($new > $old ? '  ▲' : '  ▼') : '');
        }
    }

    echo "\n" . str_repeat('=', 62) . "\n";
    printf("Пакетҳо: %d\n", $n);
    printf("Арзиши харид  : %10.2f USD\n", $sumCost);
    printf("Нархи ҳозира  : %10.2f %s\n", $sumOld, $cur);
    printf("Нархи нав     : %10.2f %s\n", $sumNew, $cur);
    printf("Фарқият       : %+10.2f %s\n", $sumNew - $sumOld, $cur);
    echo str_repeat('=', 62) . "\n";
    echo "\nМисол: ?price=free fire&rate=9.24&markup=20&secret=" . SECRET . "\n";
    echo "Танҳо ҳисоб — базаро тағйир намедиҳад.\n";
    exit;
}

if (isset($_GET['ftv'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    $l = ftv_list(isset($_GET['force']));
    echo "FLASHTOPUP · бозиҳо бо санҷиши ном: " . count($l) . "\n\n";
    foreach (array_slice($l, 0, 60) as $v) {
        echo str_pad(mb_substr($v['name'], 0, 36), 38) . $v['vc'] . "\n";
    }
    echo "\n-- Мувофиқат бо каталоги мо --\n";
    $ok = 0; $no = 0;
    foreach (all("SELECT * FROM z_games WHERE active=1 ORDER BY base, region") as $g) {
        $m = ftv_match($g);
        if ($m) { $ok++; } else { $no++; continue; }
        echo str_pad(mb_substr($g['name'], 0, 34), 36) . '● ' . $m['vc'] . "\n";
    }
    echo "\nМувофиқ: $ok · Бе санҷиш: $no\n";
    if (!empty($_GET['id'])) {
        $g = one("SELECT * FROM z_games WHERE id=?", [(int)$_GET['id']]);
        if ($g) {
            echo "\n-- САНҶИШ --\n" . $g['name'] . "\n";
            $r = ft_nick($g, ['user_id' => (string)($_GET['uid'] ?? '')]);
            echo json_encode($r, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n";
        }
    }
    exit;
}

if (isset($_GET['find'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    $qy = trim((string)($_GET['find'] ?? ''));
    if ($qy === '' || $qy === '1') { echo "Мисол: ?find=free fire&secret=...\n"; exit; }

    echo "ҶУСТУҶӮ: $qy\n\n-- ДАР КАТАЛОГИ МО --\n";
    foreach (all("SELECT g.*, (SELECT COUNT(*) FROM z_packs p WHERE p.game_id=g.id AND p.active=1) c
                  FROM z_games g WHERE g.name LIKE ? ORDER BY g.name", ['%' . $qy . '%']) as $g) {
        echo ($g['active'] ? '●' : '○') . ' ' . str_pad(mb_substr($g['name'], 0, 32), 34)
           . 'рег: ' . str_pad((string)($g['region'] ?: '—'), 7)
           . 'пак: ' . str_pad((string)$g['c'], 5)
           . 'chk: ' . ($g['can_chk'] ? 'ҳа' : 'не') . "\n"
           . '    code: ' . $g['ft_code'] . "\n";
    }

    echo "\n-- ДАР ПРОВАЙДЕР --\n";
    $cursor = null; $found = 0; $guard = 0;
    do {
        $p2 = ['limit' => 200, 'include_ui' => 1];
        if ($cursor) $p2['cursor'] = $cursor;
        $r = fz('GET', '/topups', $p2);
        if (empty($r['ok'])) { echo "хато: " . fzerr($r) . "\n"; break; }
        foreach (($r['items'] ?? []) as $it) {
            if (mb_stripos((string)($it['name'] ?? ''), $qy) === false) continue;
            $found++;
            echo str_pad(mb_substr((string)$it['name'], 0, 36), 38) . $it['category_id'] . "\n";
        }
        $cursor = $r['meta']['next_cursor'] ?? null;
        $guard++;
    } while ($cursor && $guard < 30);
    echo "Ёфт шуд: $found\n";
    exit;
}

if (isset($_GET['clean'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    $oldP = q("DELETE FROM z_packs WHERE ft_code IS NULL OR ft_code NOT LIKE '%|%'")->rowCount();
    $oldG = q("DELETE FROM z_games WHERE id NOT IN
               (SELECT game_id FROM (SELECT DISTINCT game_id FROM z_packs) x)")->rowCount();
    echo "Нест шуд: $oldG бозӣ, $oldP пакет\n";
    echo "Ҳоло: " . (one("SELECT COUNT(*) c FROM z_games")['c'] ?? 0) . " бозӣ, "
       . (one("SELECT COUNT(*) c FROM z_packs")['c'] ?? 0) . " пакет\n";
    exit;
}

if (isset($_GET['hookset'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');

    $host = $_SERVER['HTTP_HOST'] ?? '';
    $dir  = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/');
    $url  = 'https://' . $host . $dir . '/zbot.php?hook=fz';

    echo "URL: $url\n\n";

    if (isset($_GET['off'])) {
        $d = fz('DELETE', '/account/webhook');
        echo "DELETE: " . json_encode($d, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
        exit;
    }

    $r = fz('PUT', '/account/webhook', [], ['url' => $url, 'enabled' => true]);
    echo "PUT:  " . json_encode($r, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n\n";

    $c = fz('GET', '/account/webhook');
    echo "GET:  " . json_encode($c, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n\n";

    if (isset($_GET['test'])) {
        $t = fz('POST', '/account/webhook/test');
        echo "TEST: " . json_encode($t, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n\n";
        $d = fz('GET', '/account/webhook/deliveries');
        echo "DELIVERIES:\n" . json_encode(array_slice($d['deliveries'] ?? [], 0, 5),
             JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n";
    }
    exit;
}

if (isset($_GET['vlist'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    $l = vlist(isset($_GET['force']));
    echo "БОЗИҲОИ САНҶИШИ ID · " . count($l) . "\n\n";
    foreach ($l as $v) {
        $ks = [];
        foreach (($v['fields'] ?? []) as $f) if (!empty($f['key'])) $ks[] = $f['key'];
        echo str_pad(mb_substr($v['name'], 0, 34), 36) . '[' . implode(', ', $ks) . "]\n";
        echo "   id: " . $v['id'] . "\n";
    }
    echo "\n-- Бозиҳои мо бо санҷиш --\n";
    $n = 0;
    foreach (all("SELECT * FROM z_games WHERE active=1 ORDER BY name") as $g) {
        $m = vmatch($g);
        if (!$m) continue;
        $n++;
        echo str_pad(mb_substr($g['name'], 0, 34), 36) . '→ ' . $m['name'] . "\n";
    }
    echo "Ҳамагӣ: $n аз "
       . (one("SELECT COUNT(*) c FROM z_games WHERE active=1")['c'] ?? 0) . "\n";
    exit;
}

if (isset($_GET['selftest'])) {
    guard_page();
    header('Content-Type: text/plain; charset=utf-8');
    echo "SELFTEST " . VERSION . "\n\n";
    $steps = [
        'DB'        => fn() => (string)(one("SELECT COUNT(*) c FROM z_users")['c'] ?? '?') . ' корбар',
        'Games'     => fn() => (string)(one("SELECT COUNT(*) c FROM z_games WHERE active=1")['c'] ?? 0),
        'Packs'     => fn() => (string)(one("SELECT COUNT(*) c FROM z_packs WHERE active=1")['c'] ?? 0),
        'FZ /me'    => fn() => json_encode(fz('GET', '/me'), JSON_UNESCAPED_UNICODE),
        'FZ /balance' => fn() => json_encode(fz('GET', '/balance'), JSON_UNESCAPED_UNICODE),
        'FZ /topups'  => function () {
            $r = fz('GET', '/topups', ['limit' => 3, 'include_ui' => 1]);
            return json_encode(['ok' => $r['ok'] ?? false, 'total' => $r['meta']['total'] ?? null,
                'first' => $r['items'][0]['name'] ?? null, 'err' => $r['error'] ?? null],
                JSON_UNESCAPED_UNICODE);
        },
        'Telegram'  => fn() => json_encode(tg('getMe')['result']['username'] ?? tg('getMe')),
        'app_url'   => fn() => app_url(),
        'Шумо IP'   => fn() => ip() . (banned(ip()) ? '  ⛔️ БАНД АСТ!' : '  ● озод'),
        'Банҳо'     => fn() => (string)(one("SELECT COUNT(*) c FROM z_bans WHERE until>?",
                                            [time()])['c'] ?? 0),
    ];
    foreach ($steps as $k => $fn) {
        try { echo str_pad($k, 14) . ' OK  ' . mb_substr((string)$fn(), 0, 400) . "\n"; }
        catch (Throwable $e) { echo str_pad($k, 14) . ' ХАТО  ' . $e->getMessage() . "\n"; }
    }
    exit;
}

/* ---------- API барои Mini App ---------- */
if (isset($_GET['api'])) {
    $raw = (string)file_get_contents('php://input');
    if (strlen($raw) > 12 * 1024 * 1024) { http_response_code(413); exit; }
    if (!rate('api:' . $IP, 120, 60)) jout(['ok' => false, 'error' => 'RATE'], 429);

    $in = json_decode($raw, true) ?: [];
    $tu = verify_init((string)($in['initData'] ?? ''));
    if (!$tu || empty($tu['id'])) jout(['ok' => false, 'error' => 'AUTH'], 401);
    $uid = (int)$tu['id'];
    q("INSERT INTO z_users (id,username,name,created_at,seen_at) VALUES (?,?,?,?,?)
       ON DUPLICATE KEY UPDATE username=VALUES(username), name=VALUES(name), seen_at=VALUES(seen_at)",
      [$uid, $tu['username'] ?? null, mb_substr($tu['first_name'] ?? '', 0, 120), time(), time()]);

    $me = one("SELECT * FROM z_users WHERE id=?", [$uid]) ?: [
        'id' => $uid, 'phone' => null, 'balance' => 0, 'spent' => 0, 'orders_cnt' => 0,
        'lang' => 'tj', 'blocked' => 0, 'ref_cnt' => 0, 'ref_sum' => 0,
    ];
    if ($me && (int)$me['blocked'] === 1) jout(['ok' => false, 'error' => 'BLOCKED'], 403);
    if (!rate('u:' . $uid, 200, 60)) jout(['ok' => false, 'error' => 'RATE'], 429);

    $m = (string)$_GET['api'];
    $heavy = ['buy' => [8, 60], 'topup' => [6, 300], 'receipt' => [6, 300]];
    if (isset($heavy[$m]) && !rate('h:' . $m . ':' . $uid, $heavy[$m][0], $heavy[$m][1])) {
        jout(['ok' => false, 'error' => 'TOO_FAST'], 429);
    }

    if ($m === 'init' && !sub_ok($uid)) {
        jout(['ok' => false, 'error' => 'SUB', 'channels' => subs_public(),
              'title' => T('subT', $uid), 'text' => T('subTxt', $uid),
              'why' => T('subWhy', $uid), 'go' => T('subGo', $uid), 'chk' => T('subChk', $uid)]);
    }
    if (in_array($m, ['buy', 'topup'], true) && !sub_ok($uid)) {
        jout(['ok' => false, 'error' => 'SUB', 'channels' => subs_public(),
              'title' => T('subT', $uid), 'text' => T('subTxt', $uid),
              'why' => T('subWhy', $uid), 'go' => T('subGo', $uid), 'chk' => T('subChk', $uid)]);
    }

    if ($m === 'init') {
        jout(['ok' => true, 'shop' => cfg('shop', 'ZVER TAJ'), 'cur' => cfg('cur', 'TJS'),
              'support' => cfg('support', ''), 'reviews' => cfg('reviews', ''),
              'wa' => @wa_link($uid),
              'user' => [
                'id' => $uid, 'name' => trim(($tu['first_name'] ?? '') . ' ' . ($tu['last_name'] ?? '')),
                'username' => $tu['username'] ?? null, 'photo' => $tu['photo_url'] ?? null,
                'phone' => $me['phone'] ?? null, 'balance' => (float)($me['balance'] ?? 0),
                'spent' => (float)($me['spent'] ?? 0), 'orders' => (int)($me['orders_cnt'] ?? 0),
                'lang' => $me['lang'] ?? 'tj',
                'ref_link' => (($bu = @bot_user()) !== '' ? 'https://t.me/' . $bu . '?start=' . $uid : ''),
                'ref_cnt' => (int)($me['ref_cnt'] ?? 0), 'ref_sum' => (float)($me['ref_sum'] ?? 0),
                'ref_bonus' => (float)cfg('ref_bonus', '0.50'),
              ]]);
    }

    if ($m === 'lang') {
        $l = in_array($in['lang'] ?? '', LNGS, true) ? $in['lang'] : 'tj';
        q("UPDATE z_users SET lang=? WHERE id=?", [$l, $uid]);
        jout(['ok' => true]);
    }

    if ($m === 'live') {
        $now = time();
        $online = (int)(one("SELECT COUNT(*) c FROM z_users WHERE seen_at > ?",
                            [$now - 900])['c'] ?? 0);
        $base = (int)cfg('live_base', '0');
        if ($online < 3) $online = 3 + ((int)floor($now / 300) % 5);
        $online += $base;

        $today = (int)(one("SELECT COUNT(*) c FROM z_orders WHERE status='done' AND created_at > ?",
                           [strtotime('today')])['c'] ?? 0);
        $total = (int)(one("SELECT COUNT(*) c FROM z_orders WHERE status='done'")['c'] ?? 0);
        $buyers = (int)(one("SELECT COUNT(DISTINCT uid) c FROM z_orders WHERE status='done'")['c'] ?? 0);

        $feed = [];
        foreach (all("SELECT o.game_name, o.pack_name, o.created_at, u.name
                      FROM z_orders o LEFT JOIN z_users u ON u.id=o.uid
                      WHERE o.status='done' ORDER BY o.id DESC LIMIT 12") as $r) {
            $nm = trim((string)($r['name'] ?? ''));
            if ($nm === '') $nm = 'Корбар';
            // ниммаскировка: Алиҷон → Али•••
            $vis = max(2, min(4, (int)floor(mb_strlen($nm) / 2)));
            $nm = mb_substr($nm, 0, $vis) . '•••';
            $feed[] = ['n' => $nm, 'g' => $r['game_name'], 'p' => $r['pack_name'],
                       'at' => (int)$r['created_at']];
        }

        jout(['ok' => true, 'online' => $online, 'today' => $today,
              'total' => $total + (int)cfg('live_add', '0'), 'buyers' => $buyers,
              'feed' => $feed]);
    }

    if ($m === 'games') {
        $rows = all("SELECT g.*, (SELECT COUNT(*) FROM z_packs p WHERE p.game_id=g.id AND p.active=1) c,
                     (SELECT MIN(price) FROM z_packs p WHERE p.game_id=g.id AND p.active=1) mn
                     FROM z_games g WHERE g.active=1 HAVING c>0 ORDER BY g.sort DESC, g.name");
        $gr = [];
        foreach ($rows as $r) {
            $key = $r['base'] !== null && $r['base'] !== '' ? $r['base'] : mb_strtolower($r['name']);
            if (!isset($gr[$key])) {
                $gr[$key] = ['key' => $key, 'name' => nicebase($key), 'image' => $r['image'],
                             'min' => (float)$r['mn'], 'regions' => []];
            }
            if (!empty($r['image']) && (empty($gr[$key]['image'])
                || in_array($r['region'] ?? '', ['CIS', 'GLOBAL'], true))) {
                $gr[$key]['image'] = $r['image'];
            }
            if ((float)$r['mn'] > 0 && (float)$r['mn'] < $gr[$key]['min']) $gr[$key]['min'] = (float)$r['mn'];
            $rc = $r['region'] ?: 'GLOBAL';
            $gr[$key]['regions'][] = ['id' => (int)$r['id'], 'code' => $rc,
                                      'flag' => $r['flag'] ?: '🌐', 'label' => reg_label($rc),
                                      'full' => $r['name'], 'cnt' => (int)$r['c']];
        }
        // тартиб: аввал бозиҳои TOP
        $top = [];
        foreach (explode(',', cfg('top', '')) as $w) {
            $w = trim(mb_strtolower($w));
            if ($w !== '') $top[] = $w;
        }
        foreach ($gr as $k => &$g0) {
            $g0['rank'] = 999;
            foreach ($top as $i => $w) {
                if (str_contains(mb_strtolower($g0['key']), $w)) { $g0['rank'] = $i; break; }
            }
        }
        unset($g0);

        foreach ($gr as &$g) sort_regs($g['regions']);
        unset($g);
        $out = array_values($gr);
        usort($out, function ($a, $b) {
            if ($a['rank'] !== $b['rank']) return $a['rank'] <=> $b['rank'];
            return strcmp($a['name'], $b['name']);
        });
        foreach ($out as &$o) { $o['top'] = $o['rank'] < 900; unset($o['rank']); }
        unset($o);
        jout(['ok' => true, 'items' => $out]);
    }

    if ($m === 'game') {
        $g = one("SELECT * FROM z_games WHERE id=? AND active=1", [(int)($in['id'] ?? 0)]);
        if (!$g) jout(['ok' => false, 'error' => 'NOT_FOUND'], 404);
        $packs = all("SELECT * FROM z_packs WHERE game_id=? AND active=1
                      ORDER BY sort DESC, price", [$g['id']]);
        $lang = $me['lang'] ?? 'tj';
        $regs = [];
        $grpImg = $g['image'];
        if (!empty($g['base'])) {
            $gi = one("SELECT image FROM z_games WHERE base=? AND image IS NOT NULL AND image<>''
                       ORDER BY (region='CIS') DESC, (region='GLOBAL') DESC, id LIMIT 1",
                      [$g['base']]);
            if ($gi && !empty($gi['image'])) $grpImg = $gi['image'];
            foreach (all("SELECT g.id,g.region,g.flag,g.name FROM z_games g
                          WHERE g.base=? AND g.active=1
                            AND EXISTS(SELECT 1 FROM z_packs p WHERE p.game_id=g.id AND p.active=1)
                          ORDER BY g.region", [$g['base']]) as $x) {
                $rc2 = $x['region'] ?: 'GLOBAL';
                $regs[] = ['id' => (int)$x['id'], 'code' => $rc2, 'flag' => $x['flag'] ?: '🌐',
                           'label' => reg_label($rc2)];
            }
            sort_regs($regs);
        }
        $cats = [];
        foreach ($packs as $p) {
            $c = $p['cat'] ?: 'main';
            if (!isset($cats[$c])) $cats[$c] = ['key' => $c, 'name' => cat_name($c, $lang), 'n' => 0];
            $cats[$c]['n']++;
        }
        $order = ['diamond', 'uc', 'coin', 'gem', 'star', 'token', 'credit',
                  'pass', 'pack', 'sub', 'voucher', 'main'];
        if (!empty($g['cat_order'])) {
            $own = array_values(array_filter(array_map('trim', explode(',', (string)$g['cat_order']))));
            if ($own) $order = array_merge($own, array_diff($order, $own));
        }
        uasort($cats, function ($a, $b) use ($order) {
            $ia = array_search($a['key'], $order, true);
            $ib = array_search($b['key'], $order, true);
            if ($ia === false) $ia = 99;
            if ($ib === false) $ib = 99;
            if ($ia !== $ib) return $ia <=> $ib;
            return $b['n'] <=> $a['n'];
        });
        jout(['ok' => true, 'game' => [
            'id' => (int)$g['id'], 'name' => $g['name'], 'image' => $grpImg,
            'title' => ($g['title'] !== null && $g['title'] !== '')
                       ? $g['title'] : ($g['base'] ? nicebase((string)$g['base']) : $g['name']),
            'need_server' => (int)$g['need_server'], 'id_label' => $g['id_label'],
            'server_label' => $g['server_label'], 'hint' => $g['hint'],
            'can_check' => (int)($g['can_chk'] ?? 0) === 1,
            'fields' => game_fields($g),
            'base' => $g['base'], 'region' => $g['region'] ?: 'GLOBAL',
        ], 'regions' => $regs, 'cats' => array_values($cats),
           'packs' => array_map(fn($p) => [
            'id' => (int)$p['id'],
            'name' => ($p['title'] !== null && $p['title'] !== '') ? $p['title'] : $p['name'],
            'price' => (float)$p['price'],
            'cat' => $p['cat'] ?: 'main',
            'old' => $p['old_price'] !== null ? (float)$p['old_price'] : null, 'tag' => $p['tag'],
        ], $packs)]);
    }

    if ($m === 'check') {
        $g = one("SELECT * FROM z_games WHERE id=? AND active=1", [(int)($in['game_id'] ?? 0)]);
        if (!$g) jout(['ok' => false, 'error' => 'NOT_FOUND'], 404);
        if (!rate('chk:' . $uid, 12, 60)) jout(['ok' => false, 'error' => 'TOO_FAST'], 429);
        $vals = is_array($in['fields'] ?? null) ? $in['fields'] : [];
        // ҲИМОЯ: провайдер афтад — ба клиент ҷавоби тоза, на экрани сафед
        try { $r = fz_check($g, $vals); }
        catch (Throwable $e) {
            zlog('chk', 'EXC ' . $e->getMessage());
            jout(['ok' => true, 'skip' => true]);   // санҷиш дастнорас — ID қабул, харид иҷозат
        }
        if (!empty($r['skip'])) jout(['ok' => true, 'skip' => true]);
        if (empty($r['ok'])) jout(['ok' => false, 'error' => $r['msg'] ?? 'FAIL']);
        jout(['ok' => true, 'nick' => $r['nick'], 'region' => $r['region'] ?? '']);
    }

    if ($m === 'promo') {
        if (!rate('pr:' . $uid, 15, 60)) jout(['ok' => false, 'error' => 'TOO_FAST'], 429);
        $sum = round((float)($in['sum'] ?? 0), 2);
        $r = promo_check((string)($in['code'] ?? ''), $uid, $sum);
        if (empty($r['ok'])) {
            jout(['ok' => false, 'error' => $r['err'],
                  'msg' => promo_err($r['err'], $uid, (float)($r['min'] ?? 0))]);
        }
        $pr = is_array($r['promo'] ?? null) ? $r['promo'] : [];
        jout(['ok' => true, 'code' => (string)($pr['code'] ?? ''),
              'kind' => (string)($pr['kind'] ?? ''), 'val' => (float)($pr['val'] ?? 0),
              'off' => $r['off'] ?? 0, 'total' => $r['total'] ?? $sum]);
    }

    if ($m === 'cart') {
        $items = is_array($in['items'] ?? null) ? $in['items'] : [];
        if (!$items) jout(['ok' => false, 'error' => 'CART_SIZE']);
        // ФАҚАТ ЯК пакет иҷозат аст (сабад нест шуд)
        if (count($items) > 1) jout(['ok' => false, 'error' => 'ONE_ONLY']);

        $gid0 = 0; $rows = []; $total = 0.0;
        foreach ($items as $it) {
            $pid0 = (int)($it['id'] ?? 0);
            $qty0 = max(1, min(10, (int)($it['qty'] ?? 1)));
            $p0 = one("SELECT p.*, g.name gname, g.id gid, g.need_server
                       FROM z_packs p JOIN z_games g ON g.id=p.game_id
                       WHERE p.id=? AND p.active=1 AND g.active=1", [$pid0]);
            if (!$p0) jout(['ok' => false, 'error' => 'NO_PACK'], 404);
            if ($gid0 === 0) $gid0 = (int)$p0['gid'];
            elseif ($gid0 !== (int)$p0['gid']) jout(['ok' => false, 'error' => 'MIXED']);
            $total += (float)$p0['price'] * $qty0;
            $rows[] = ['p' => $p0, 'q' => $qty0];
        }
        $total = round($total, 2);

        $gRow = one("SELECT * FROM z_games WHERE id=?", [$gid0]);
        $fl   = game_fields($gRow ?: []);
        $vals = is_array($in['fields'] ?? null) ? $in['fields'] : [];
        $fv = [];
        foreach ($fl as $i => $x) {
            $k = (string)$x['key'];
            $v = trim((string)($vals[$k] ?? ''));
            if ($v === '' && $i === 0) {
                foreach ($vals as $vv) { $vv = trim((string)$vv); if ($vv !== '') { $v = $vv; break; } }
            }
            if ($v === '') { if ($i === 0) jout(['ok' => false, 'error' => 'ID_EMPTY']); continue; }
            $fv[$k] = mb_substr($v, 0, 64);
        }
        if (!$fv) jout(['ok' => false, 'error' => 'ID_EMPTY']);
        $vv2 = array_values($fv);
        $pid = (string)$vv2[0];
        $sid = count($vv2) > 1 ? (string)$vv2[1] : '';

        // промокод
        $pmObj = null; $pmOff = 0.0; $pmCode = null;
        $pmIn = trim((string)($in['promo'] ?? ''));
        if ($pmIn !== '') {
            $pr = promo_check($pmIn, $uid, $total);
            if (!empty($pr['ok'])) {
                $pmObj = $pr['promo']; $pmOff = (float)$pr['off'];
                $pmCode = $pr['promo']['code']; $total = (float)$pr['total'];
            }
        }

        $st = q("UPDATE z_users SET balance=balance-? WHERE id=? AND balance>=?",
                [$total, $uid, $total]);
        if ($st->rowCount() === 0) jout(['ok' => false, 'error' => 'NO_BALANCE', 'need' => $total]);

        // Аз ин ҷо пул кам шуд. Агар то сохтани заказ чизе афтад — пулро бармегардонем.
        $charged = $total; $ids = [];
        try {
        $kf = ($pmOff > 0 && ($total + $pmOff) > 0) ? ($pmOff / ($total + $pmOff)) : 0;
        foreach ($rows as $r) {
            for ($n = 0; $n < $r['q']; $n++) {
                q("INSERT INTO z_orders (uid,game_id,pack_id,game_name,pack_name,player_id,
                    server_id,qty,price,status,note,promo,discount,created_at)
                   VALUES (?,?,?,?,?,?,?,1,?, 'new', ?, ?, ?, ?)",
                  [$uid, $r['p']['gid'], $r['p']['id'], $r['p']['gname'], $r['p']['name'],
                   $pid, $sid !== '' ? $sid : null,
                   round((float)$r['p']['price'] * (1 - $kf), 2),
                   json_encode($fv, JSON_UNESCAPED_UNICODE), $pmCode,
                   round((float)$r['p']['price'] * $kf, 2), time()]);
                $ids[] = (int)db()->lastInsertId();
            }
        }

        if ($pmObj && $ids) {
            try {
                promo_use($pmObj, $uid, (int)$ids[0], $pmOff);
                q("UPDATE z_users SET promo=NULL WHERE id=? AND promo=?", [$uid, $pmCode]);
            } catch (Throwable $e) {}
        }

        tx($uid, 'buy', -$total,
           count($ids) > 1 ? ('Харид · ' . count($ids) . ' пакет')
                           : ('Харид · ' . (string)($rows[0]['p']['name'] ?? 'пакет')),
           (int)($ids[0] ?? 0));

        } catch (Throwable $e) {
            // сохтани заказ афтод — агар ягон заказ насохта бошем, пулро бармегардонем
            zlog('buy', 'cart create EXC: ' . $e->getMessage());
            if (!$ids) {
                q("UPDATE z_users SET balance=balance+? WHERE id=?", [$charged, $uid]);
                tx($uid, 'refund', (float)$charged, 'Хатои система — баргашт', null);
                jout(['ok' => false, 'error' => 'ORDER_FAIL', 'refunded' => true]);
            }
            // агар қисман сохта бошем — заказҳои сохташуда идома медиҳанд
        }

        $ok = 0; $qd = 0; $fail = 0; $proc = 0;
        foreach ($ids as $oid) {
            if (cfg('auto', '1') !== '1') {
                $o = one("SELECT * FROM z_orders WHERE id=?", [$oid]);
                if ($o) { try { notify_order_admins($o); } catch (Throwable $e) {} }
                continue;
            }
            // place_safe ҳеҷ гоҳ exception намепартояд — пулро худаш бармегардонад
            $r = place_safe($oid, $uid);
            if ($r === 'ok') { $ok++; }
            elseif ($r === 'manual') {
                $o = one("SELECT * FROM z_orders WHERE id=?", [$oid]);
                if ($o) { try { notify_order_admins($o); } catch (Throwable $e) {} }
            }
            elseif ($r === 'queued') { $qd++; }
            elseif ($r === 'processing') { $proc++; }  // қабул шуд, дар коркард — пул дуруст аст
            else { $fail++; }   // failed / refunded — пул аллакай баргашт
            usleep(200000);
        }

        if ($qd > 0) {
            try { fz_low_balance(); } catch (Throwable $e) {}
            foreach (ADMINS as $a) {
                say($a, "⏳ <b>$qd ФАРМОИШ ДАР НАВБАТ</b>\n"
                    . "Баланси FazerCards кам аст — пур кунед.\n"
                    . "Дар навбат: <b>" . queue_size() . "</b>");
            }
        }

        $nb = one("SELECT balance FROM z_users WHERE id=?", [$uid])['balance'] ?? 0;
        jout(['ok' => true, 'done' => $ok, 'queued' => $qd, 'failed' => $fail, 'processing' => $proc,
              'total' => count($ids), 'balance' => (float)$nb]);
    }

    if ($m === 'buy') {
        $p = one("SELECT p.*, g.name gname, g.need_server, g.id AS gid
                  FROM z_packs p JOIN z_games g ON g.id=p.game_id
                  WHERE p.id=? AND p.active=1 AND g.active=1", [(int)($in['pack_id'] ?? 0)]);
        if (!$p) jout(['ok' => false, 'error' => 'NO_PACK'], 404);

        // пакети кӯҳна (аз провайдери қаблӣ) — фавран хомӯш
        if (!empty($p['ft_code']) && !str_contains((string)$p['ft_code'], '|')) {
            q("UPDATE z_packs SET active=0 WHERE id=?", [$p['id']]);
            q("UPDATE z_games SET active=0 WHERE id=? AND NOT EXISTS
               (SELECT 1 FROM (SELECT id FROM z_packs WHERE game_id=? AND active=1) x)",
              [$p['gid'], $p['gid']]);
            foreach (ADMINS as $a) {
                say($a, "⚠︎ <b>ПАКЕТИ КӮҲНА</b>\n" . h($p['gname']) . " · " . h($p['name'])
                    . "\n\nАз провайдери қаблӣ мондааст — хомӯш шуд.\n"
                    . "Тугмаи <b>🧹 ТОЗАКУНӢ</b>-ро пахш кунед.");
            }
            jout(['ok' => false, 'error' => 'GONE']);
        }

        // санҷиши зинда будани пакет ва нархи ҷорӣ
        if (!empty($p['ft_code']) && cfg('auto', '1') === '1') {
            [$cid0, $off0] = array_pad(explode('|', (string)$p['ft_code'], 2), 2, '');
            if ($cid0 !== '' && $off0 !== '') {
                $ck = fz('GET', '/topups/offers', ['category_id' => $cid0]);
                if (!empty($ck['ok'])) {
                    $alive = false;
                    foreach (($ck['offers'] ?? []) as $o0) {
                        if (!is_array($o0) || (string)($o0['offer_id'] ?? '') !== $off0) continue;
                        $alive = true;
                        $nc = (float)str_replace(',', '.', (string)($o0['price_usd'] ?? 0));
                        if ($nc > 0 && abs($nc - (float)$p['cost']) > 0.0001) {
                            q("UPDATE z_packs SET cost=?, price=? WHERE id=?",
                              [$nc, sell_of($nc), $p['id']]);
                            $p['price'] = sell_of($nc);
                        }
                        break;
                    }
                    if (!$alive) {
                        q("UPDATE z_packs SET active=0 WHERE id=?", [$p['id']]);
                        foreach (ADMINS as $a) {
                            say($a, "⚠︎ <b>ПАКЕТ НЕСТ</b>\n" . h($p['gname']) . " · " . h($p['name'])
                                . "\nАз мағоза хомӯш шуд.");
                        }
                        jout(['ok' => false, 'error' => 'GONE']);
                    }
                }
            }
        }

        // --- майдонҳои бозингар ---
        $gRow = one("SELECT * FROM z_games WHERE id=?", [$p['gid']]);
        $fl   = game_fields($gRow ?: []);
        $vals = is_array($in['fields'] ?? null) ? $in['fields'] : [];
        if (!$vals && isset($in['player_id']) && !empty($fl[0]['key']))
            $vals = [$fl[0]['key'] => (string)$in['player_id']];

        $fv = [];
        foreach ($fl as $i => $x) {
            $k = (string)$x['key'];
            $v = trim((string)($vals[$k] ?? ''));
            if ($v === '' && $i === 0) {
                // эҳтимол калид фарқ мекунад — қимати аввалро мегирем
                foreach ($vals as $vv) { $vv = trim((string)$vv); if ($vv !== '') { $v = $vv; break; } }
            }
            if ($v === '') {
                if ($i === 0) jout(['ok' => false, 'error' => 'ID_EMPTY']);
                continue;
            }
            $fv[$k] = mb_substr($v, 0, 64);
        }
        if (!$fv) jout(['ok' => false, 'error' => 'ID_EMPTY']);

        $vv  = array_values($fv);
        $pid = (string)$vv[0];
        $sid = count($vv) > 1 ? (string)$vv[1] : '';

        $qty   = max(1, min(10, (int)($in['qty'] ?? 1)));
        $total = round((float)$p['price'] * $qty, 2);

        // промокод
        $pmObj = null; $pmOff = 0.0; $pmCode = null;
        $pmIn = trim((string)($in['promo'] ?? ''));
        if ($pmIn !== '') {
            $pr = promo_check($pmIn, $uid, $total);
            if (!empty($pr['ok'])) {
                $pmObj  = $pr['promo'];
                $pmOff  = (float)$pr['off'];
                $pmCode = $pr['promo']['code'];
                $total  = (float)$pr['total'];
            }
        }

        $st = q("UPDATE z_users SET balance=balance-? WHERE id=? AND balance>=?", [$total, $uid, $total]);
        if ($st->rowCount() === 0) jout(['ok' => false, 'error' => 'NO_BALANCE', 'need' => $total]);

        // пул кам шуд — то сохтани заказ ҳимоя мекунем
        $charged = $total; $ids = [];
        try {
        for ($i = 0; $i < $qty; $i++) {
            $unit = round($total / max(1, $qty), 2);
            q("INSERT INTO z_orders (uid,game_id,pack_id,game_name,pack_name,player_id,server_id,
                qty,price,status,note,promo,discount,created_at)
               VALUES (?,?,?,?,?,?,?,1,?, 'new', ?, ?, ?, ?)",
              [$uid, $p['gid'], $p['id'], $p['gname'], $p['name'], $pid,
               $sid !== '' ? $sid : null, $unit,
               json_encode($fv, JSON_UNESCAPED_UNICODE), $pmCode,
               round($pmOff / max(1, $qty), 2), time()]);
            $ids[] = (int)db()->lastInsertId();
        }
        if ($pmObj && $ids) {
            try { promo_use($pmObj, $uid, (int)$ids[0], $pmOff); } catch (Throwable $e) {}
        }

        tx($uid, 'buy', -$total,
           (string)$p['gname'] . ' · ' . (string)$p['name']
           . ($qty > 1 ? " ×$qty" : ''), (int)($ids[0] ?? 0));

        } catch (Throwable $e) {
            zlog('buy', 'single create EXC: ' . $e->getMessage());
            if (!$ids) {
                q("UPDATE z_users SET balance=balance+? WHERE id=?", [$charged, $uid]);
                tx($uid, 'refund', (float)$charged, 'Хатои система — баргашт', null);
                jout(['ok' => false, 'error' => 'ORDER_FAIL', 'refunded' => true]);
            }
        }

        $queued = false;
        $auto = cfg('auto', '1') === '1' && !empty(one("SELECT ft_code FROM z_packs WHERE id=?",
                     [$p['id']])['ft_code']);
        foreach ($ids as $oid) {
            if (!$auto) {
                $o = one("SELECT * FROM z_orders WHERE id=?", [$oid]);
                if ($o) { try { notify_order_admins($o); } catch (Throwable $e) {} }
                usleep(120000);
                continue;
            }

            // ҳеҷ гоҳ пул гум намешавад: exception ё хато → refund худкор
            $r = place_safe($oid, $uid);

            if ($r === 'ok') { usleep(120000); continue; }

            if ($r === 'manual') {
                $o = one("SELECT * FROM z_orders WHERE id=?", [$oid]);
                if ($o) { try { notify_order_admins($o); } catch (Throwable $e) {} }
                usleep(120000);
                continue;
            }

            if ($r === 'queued') {
                $queued = true;
                try { fz_low_balance(); } catch (Throwable $e) {}
                foreach (ADMINS as $a) {
                    try {
                        say($a, "⏳ <b>ФАРМОИШ ДАР НАВБАТ</b> · #$oid\n"
                            . "<code>───────────────</code>\n"
                            . h($p['gname']) . " · " . h($p['name']) . "\n"
                            . "ID · <code>" . h($pid) . "</code>\n"
                            . "Маблағ · " . money((float)$p['price']) . "\n\n"
                            . "◉ <b>Баланси FazerCards кам аст.</b>\n"
                            . "Пур кунед — фармоиш худкор иҷро мешавад.\n"
                            . "Дар навбат: <b>" . queue_size() . "</b>");
                    } catch (Throwable $e) {}
                }
                usleep(120000);
                continue;
            }

            // failed / refunded — пул аллакай ба ҳамён баргашт
            $o2  = one("SELECT note FROM z_orders WHERE id=?", [$oid]);
            $msg = (string)($o2['note'] ?? 'FAIL');
            $up  = mb_strtoupper($msg);
            $hint = '';
            if ($r === 'processing') {
                // заказ қабул шуд, дар коркади провайдер аст — пул дуруст аст, интизор мешавем
                foreach (ADMINS as $a) {
                    try {
                        say($a, "⏳ <b>ФАРМОИШ ҚАБУЛ ШУД</b> · #$oid\n<code>───────────────</code>\n"
                            . h($p['gname']) . " · " . h($p['name']) . "\n"
                            . "ID · <code>" . h($pid) . "</code>\n"
                            . "Маблағ · " . money((float)$p['price']) . "\n\n"
                            . "◉ Провайдер қабул кард, дар коркард аст.\n"
                            . "<i>Агар дар 20 дақ иҷро нашавад — пул худкор бармегардад.</i>");
                    } catch (Throwable $e) {}
                }
                usleep(120000);
                continue;
            }
            if (str_contains($up, 'INSUFFICIENT')) {
                $hint = "\n\n◉ <b>Баланси FazerCards холӣ аст — пур кунед!</b>";
                try { fz_low_balance(); } catch (Throwable $e) {}
            } elseif (str_contains($up, 'REGION')) {
                $hint = "\n\nМинтақаи ҳисоби муштарӣ мувофиқ нест.";
            }
            foreach (ADMINS as $a) {
                try {
                    say($a, "× <b>ФАРМОИШ НАШУД</b> · #$oid\n<code>───────────────</code>\n"
                        . h($p['gname']) . " · " . h($p['name']) . "\n"
                        . "ID · <code>" . h($pid) . "</code>\n"
                        . "Маблағ · " . money((float)$p['price']) . "\n\n"
                        . "× " . h($msg) . $hint . "\n\nПул баргардонида шуд.");
                } catch (Throwable $e) {}
            }
            usleep(120000);
        }
        try { fz_low_balance(); } catch (Throwable $e) {}
        $nb = one("SELECT balance FROM z_users WHERE id=?", [$uid])['balance'] ?? 0;
        jout(['ok' => true, 'ids' => $ids, 'balance' => (float)$nb, 'queued' => $queued]);
    }

    if ($m === 'orders') {
        $rows = all("SELECT * FROM z_orders WHERE uid=? ORDER BY id DESC LIMIT 50", [$uid]);
        $bal = one("SELECT balance FROM z_users WHERE id=?", [$uid])['balance'] ?? 0;
        jout(['ok' => true, 'balance' => (float)$bal, 'items' => array_map(fn($o) => [
            'id' => (int)$o['id'], 'game' => $o['game_name'], 'pack' => $o['pack_name'],
            'pid' => $o['player_id'], 'sum' => (float)$o['price'], 'status' => $o['status'],
            'code' => $o['code'],
            'note' => tech_note((string)($o['note'] ?? '')) ? null
                      : nice_err((string)$o['note'], $uid),
            'date' => (int)$o['created_at'],
        ], $rows)]);
    }

    if ($m === 'history') {
        ensure_tables();
        $lim = max(10, min(100, (int)($in['limit'] ?? 60)));
        $rows = all("SELECT id,kind,amount,balance,title,ref_id,created_at
                     FROM z_tx WHERE uid=? ORDER BY id DESC LIMIT ?", [$uid, $lim]);

        $in_  = (float)(one("SELECT COALESCE(SUM(amount),0) s FROM z_tx
                             WHERE uid=? AND amount>0", [$uid])['s'] ?? 0);
        $out_ = (float)(one("SELECT COALESCE(SUM(amount),0) s FROM z_tx
                             WHERE uid=? AND amount<0", [$uid])['s'] ?? 0);
        $bal  = (float)(one("SELECT balance FROM z_users WHERE id=?", [$uid])['balance'] ?? 0);

        jout(['ok' => true, 'balance' => $bal,
              'in' => round($in_, 2), 'out' => round(abs($out_), 2),
              'items' => array_map(fn($r) => [
                  'id'    => (int)$r['id'],
                  'kind'  => (string)$r['kind'],
                  'sum'   => (float)$r['amount'],
                  'bal'   => (float)$r['balance'],
                  'title' => (string)($r['title'] ?? ''),
                  'ref'   => (int)($r['ref_id'] ?? 0),
                  'date'  => (int)$r['created_at'],
              ], $rows)]);
    }

    if ($m === 'reqs') {
        $rows = all("SELECT id,bank,fname,lname,owner,number,kind,pay_url,logo FROM z_reqs
                     WHERE active=1 ORDER BY sort DESC, id");
        jout(['ok' => true, 'items' => array_map(fn($r) => [
            'id' => (int)$r['id'], 'bank' => $r['bank'],
            'fname' => $r['fname'] ?: $r['owner'], 'lname' => $r['lname'] ?: '',
            'owner' => $r['owner'], 'number' => $r['number'], 'kind' => $r['kind'],
            'logo' => tg_file_url($r['logo'] ?? null),
            'has_url' => !empty($r['pay_url']),
        ], $rows)]);
    }

    if ($m === 'topup') {
        $a = round((float)($in['amount'] ?? 0), 2);
        if ($a < 1 || $a > 100000) jout(['ok' => false, 'error' => 'AMOUNT']);

        // ЯК заявка дар навбат: агар чеки қаблӣ ҳанӯз тасдиқ/рад нашуда бошад — нав намедиҳем
        $pend = one("SELECT id, amount, created_at FROM z_topups
                     WHERE uid=? AND status='pending' ORDER BY id DESC LIMIT 1", [$uid]);
        if ($pend) {
            jout(['ok' => false, 'error' => 'HAS_PENDING',
                  'tid' => (int)$pend['id'],
                  'amount' => (float)$pend['amount']]);
        }

        $rq = one("SELECT * FROM z_reqs WHERE id=? AND active=1", [(int)($in['req_id'] ?? 0)])
           ?: one("SELECT * FROM z_reqs WHERE active=1 ORDER BY sort DESC, id LIMIT 1");
        if (!$rq) jout(['ok' => false, 'error' => 'NO_REQ']);

        // Заявкаҳои кӯҳнаи 'new' (бе чек, аз 2 соат зиёд) — тоза мекунем, то ҷам нашаванд
        try {
            q("UPDATE z_topups SET status='cancel'
               WHERE uid=? AND status='new' AND created_at < ?", [$uid, time() - 7200]);
        } catch (Throwable $e) {}

        q("INSERT INTO z_topups (uid,amount,req_id,status,created_at) VALUES (?,?,?, 'new', ?)",
          [$uid, $a, (int)$rq['id'], time()]);
        $tid = (int)db()->lastInsertId();
        set_st($uid, 'receipt', ['tid' => $tid]);

        $u = one("SELECT username, name FROM z_users WHERE id=?", [$uid]);
        $nick = trim((string)($u['username'] ?? ''));
        if ($nick !== '') $nick = '@' . ltrim($nick, '@');
        else {
            $nm = trim((string)($u['name'] ?? ''));
            $nick = $nm !== '' ? mb_substr($nm, 0, 20) : ('ID' . $uid);
        }
        $comment = $nick . ' TOP' . $tid;
        $url = trim((string)($rq['pay_url'] ?? ''));
        if ($url !== '') {
            $url = str_replace(
                ['{SUM}', '{ID}', '{COMMENT}', '{NICK}'],
                [(string)$a, 'TOP' . $tid, rawurlencode($comment), rawurlencode($nick)],
                $url);
        }
        q("UPDATE z_topups SET comment=? WHERE id=?", [mb_substr($comment, 0, 60), $tid]);

        jout(['ok' => true, 'tid' => $tid, 'amount' => $a, 'comment' => $comment,
              'req' => ['bank' => $rq['bank'], 'logo' => tg_file_url($rq['logo'] ?? null),
                        'fname' => $rq['fname'] ?: $rq['owner'], 'lname' => $rq['lname'] ?: '',
                        'owner' => $rq['owner'], 'number' => $rq['number'],
                        'kind' => $rq['kind'], 'url' => $url]]);
    }

    if ($m === 'receipt') {
      try {
        $tid = (int)($in['tid'] ?? 0);
        $t = one("SELECT * FROM z_topups WHERE id=? AND uid=?", [$tid, $uid]);
        if (!$t) jout(['ok' => false, 'error' => 'NOT_FOUND'], 404);
        if ($t['status'] === 'pending') jout(['ok' => true, 'already' => true]);
        if ($t['status'] !== 'new') jout(['ok' => false, 'error' => 'ALREADY']);

        // ЯК чек дар навбат: агар заявкаи дигар аллакай pending бошад — қабул намекунем
        $other = one("SELECT id FROM z_topups
                      WHERE uid=? AND status='pending' AND id<>? LIMIT 1", [$uid, $tid]);
        if ($other) jout(['ok' => false, 'error' => 'HAS_PENDING', 'tid' => (int)$other['id']]);

        $b = (string)($in['photo'] ?? '');
        if (str_contains($b, 'base64,')) $b = substr($b, strpos($b, ',') + 1);
        $bin = base64_decode($b, true);
        if ($bin === false || strlen($bin) < 500) jout(['ok' => false, 'error' => 'BAD_IMAGE']);
        if (strlen($bin) > 8 * 1024 * 1024) jout(['ok' => false, 'error' => 'TOO_BIG']);

        $tmp = sys_get_temp_dir() . '/z' . $tid . '_' . bin2hex(random_bytes(3)) . '.jpg';
        @file_put_contents($tmp, $bin);

        $u   = one("SELECT name,username,phone FROM z_users WHERE id=?", [$uid]);
        $cmt = (string)($t['comment'] ?? '');

        // санҷиши тез: айнан ҳамон расм қаблан истифода шудааст? (танҳо огоҳӣ)
        $hash = sha1($bin);
        $dup  = null;
        try {
            $dup = one("SELECT id, topup_id, created_at FROM z_checks
                        WHERE img_hash=? LIMIT 1", [$hash]);
        } catch (Throwable $e) {}
        try {
            q("INSERT INTO z_checks (topup_id,uid,img_hash,amount,verdict,created_at)
               VALUES (?,?,?,?,?,?)",
              [$tid, $uid, $hash, (float)$t['amount'], $dup ? 'dup' : 'ok', time()]);
        } catch (Throwable $e) {}

        $cap = "<b>◆ ПУР КАРДАНИ ҲАМЁН #{$tid}</b>\n<code>───────────────</code>\n"
             . "Муштарӣ · <a href=\"tg://user?id={$uid}\">" . h($u['name'] ?? $uid) . "</a>\n"
             . (!empty($u['username']) ? "@" . h($u['username']) . "\n" : '')
             . (!empty($u['phone']) ? h($u['phone']) . "\n" : '')
             . "Маблағ · <b>" . money((float)$t['amount']) . "</b>\n"
             . ($cmt !== '' ? "Шарҳ · <code>" . h($cmt) . "</code>\n" : '')
             . date('d.m.Y H:i') . "\n"
             . ($dup
                ? "\n⚠️ <b>Ин расм қаблан фиристода шуда буд</b> · заявка #"
                  . (int)($dup['topup_id'] ?? 0) . " · "
                  . date('d.m H:i', (int)($dup['created_at'] ?? 0)) . "\n"
                : '');

        $kb = [[['text' => '● ТАСДИҚ', 'callback_data' => 'at:d:' . $tid],
                ['text' => '× РАД',    'callback_data' => 'at:f:' . $tid]]];

        // --- ҚАДАМИ 1: расм ба админи асосӣ (ягона кори ҳатмӣ) ---
        $fid = null; $upMid = 0;
        $up = photo_file(ADMINS[0], $tmp, $cap, $kb);
        if (!empty($up['result']['photo'])) {
            $ph  = $up['result']['photo'];
            $fid = end($ph)['file_id'] ?? null;
        }
        $upMid = (int)($up['result']['message_id'] ?? 0);
        @unlink($tmp);
        if ($fid === null) {
            zlog('receipt', 'photo_file fail: ' . json_encode($up, JSON_UNESCAPED_UNICODE));
            jout(['ok' => false, 'error' => 'UPLOAD']);
        }

        q("UPDATE z_topups SET file_id=?, status='pending' WHERE id=? AND status='new'",
          [$fid, $tid]);
        clr_st($uid);

        // --- ҚАДАМИ 2: ҷавоб ба муштарӣ ФАВРАН, боқимонда дар пасманзар ---
        $early = jflush(['ok' => true]);

        // ба админҳои дигар
        foreach (array_slice(admins_list(), 1) as $a) {
            try {
                tg('sendPhoto', ['chat_id' => $a, 'photo' => $fid, 'parse_mode' => 'HTML',
                    'caption' => $cap, 'reply_markup' => ['inline_keyboard' => $kb]]);
            } catch (Throwable $e) {}
        }

        // --- САНҶИШ БО УВЕДОМЛЕНИЯИ БОНК — тасдиқи худкор ---
        try {
            $hasBank = (int)(one("SELECT COUNT(*) c FROM z_bank
                                  WHERE created_at > ?", [time() - 86400])['c'] ?? 0);
            if ($hasBank > 0) {
                $t2 = one("SELECT * FROM z_topups WHERE id=?", [$tid]);
                $bm = $t2 ? bank_match($t2) : null;
                if ($bm && topup_credit($tid, 0, (int)$bm['id'], true) && $upMid) {
                    ed_any(ADMINS[0], $upMid,
                        "⚡️ <b>ХУДКОР ТАСДИҚ ШУД</b> · #{$tid}\n<code>───────────────</code>\n"
                        . "Муштарӣ · " . h((string)($u['name'] ?? $uid))
                        . (!empty($u['username']) ? " @" . h($u['username']) : '') . "\n"
                        . "Маблағ · <b>" . money((float)$t['amount']) . "</b>\n"
                        . (!empty($bm['op_no']) ? "№ " . h((string)$bm['op_no']) . "\n" : '')
                        . "\n<i>Чек бо уведомленияи бонк мувофиқ омад.</i>");
                }
            }
        } catch (Throwable $e) { zlog('receipt', 'bank: ' . $e->getMessage()); }

        if (!$early) jout(['ok' => true]);
        exit;

      } catch (Throwable $e) {
        zlog('receipt', $e->getMessage() . ' @' . $e->getLine());

        // ҳатто ҳангоми хато — чек ба админ равад
        try {
            if (!empty($fid) && !empty($tid)) {
                q("UPDATE z_topups SET file_id=?, status='pending' WHERE id=? AND status='new'",
                  [$fid, (int)$tid]);
                $uu = one("SELECT name,username FROM z_users WHERE id=?", [$uid]);
                $tt = one("SELECT amount,comment FROM z_topups WHERE id=?", [(int)$tid]);
                foreach (ADMINS as $a) {
                    tg('sendPhoto', ['chat_id' => $a, 'photo' => $fid, 'parse_mode' => 'HTML',
                        'caption' => "<b>◆ ПУР КАРДАНИ ҲАМЁН #{$tid}</b>\n"
                            . "<code>───────────────</code>\n"
                            . "Муштарӣ · " . h((string)($uu['name'] ?? $uid))
                            . (!empty($uu['username']) ? " @" . h($uu['username']) : '') . "\n"
                            . "Маблағ · <b>" . money((float)($tt['amount'] ?? 0)) . "</b>\n"
                            . (!empty($tt['comment']) ? "Шарҳ · <code>"
                               . h((string)$tt['comment']) . "</code>\n" : '')
                            . "\n⚠️ <i>ИИ санҷида натавонист — дастӣ тафтиш кунед.</i>",
                        'reply_markup' => ['inline_keyboard' => [[
                            ['text' => '● Тасдиқ', 'callback_data' => 'at:d:' . (int)$tid],
                            ['text' => '× Рад',    'callback_data' => 'at:f:' . (int)$tid]]]]]);
                }
                clr_st($uid);
                jout(['ok' => true, 'warn' => 'no_ai']);
            }
        } catch (Throwable $e2) {}

        jout(['ok' => false, 'error' => 'SERVER',
              'detail' => mb_substr($e->getMessage(), 0, 200)]);
      }
    }

    jout(['ok' => false, 'error' => 'UNKNOWN'], 404);
}

/* ---------- Telegram update ---------- */
$raw = file_get_contents('php://input');
$upd = json_decode((string)$raw, true);
if (!is_array($upd)) {
    header('Content-Type: text/plain; charset=utf-8');
    echo "ZVER TAJ\nVERSION: " . VERSION . "\nFILE: " . date('Y-m-d H:i:s', (int)@filemtime(__FILE__)) . "\n";
    exit;
}

// ҲИМОЯ: update танҳо аз Telegram қабул мешавад (секрети ?s= ё header).
// Telegram ин секретро дар setWebhook гирифтааст ва бо ҳар update мефиристад.
$__s = (string)($_GET['s'] ?? '');
$__h = (string)($_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? '');
if (!hash_equals(SECRET, $__s) && !hash_equals(SECRET, $__h)) {
    http_response_code(403);
    exit('forbidden');
}


if (cfg('trace', '0') === '1') {
    try {
        $who = $upd['message']['from']['id'] ?? $upd['callback_query']['from']['id'] ?? '?';
        $txt = $upd['message']['text'] ?? $upd['callback_query']['data'] ?? '(нет текста)';
        zlog('trace', "IN uid=$who: " . mb_substr((string)$txt, 0, 80));
    } catch (Throwable $e) {}
}

try {
    handle($upd);
    if (cfg('trace', '0') === '1') zlog('trace', 'OUT ok');
} catch (Throwable $e) {
    flog('UPD: ' . $e->getMessage() . ' @' . basename($e->getFile()) . ':' . $e->getLine());
    zlog('trace', 'ERR: ' . $e->getMessage() . ' @' . $e->getLine());
}
echo 'ok';

// ---- ПОДСТРАХОВКА: агар cron кор накунад ҳам, пул баргардад ----
// Ба клиент аллакай ҷавоб додем; акнун дар паси зина заказҳои часпидаро тоза мекунем.
// На бештар аз як бор дар 5 дақиқа (то серверро бор накунад).
try {
    if (function_exists('fastcgi_finish_request')) @fastcgi_finish_request();
    $last = (int)cfg('bg_refund_at', '0');
    if (time() - $last >= 300) {              // 5 дақиқа
        setcfg('bg_refund_at', (string)time()); // фавран қулф — параллел набошад
        try { fz_poll(); } catch (Throwable $e) { zlog('bg', 'poll: ' . $e->getMessage()); }
    }
} catch (Throwable $e) {}

/* ======================= HANDLERS ======================= */

function handle(array $u): void {
    try {
        if (isset($u['callback_query'])) { on_cb($u['callback_query']); return; }
        if (isset($u['message']))        { on_msg($u['message']);       return; }
    } catch (Throwable $e) {
        zlog('handle', $e->getMessage() . ' @' . basename($e->getFile()) . ':' . $e->getLine());
        $chat = $u['callback_query']['message']['chat']['id']
             ?? $u['message']['chat']['id'] ?? null;
        $uid  = $u['callback_query']['from']['id'] ?? $u['message']['from']['id'] ?? 0;
        if (!empty($u['callback_query']['id'])) {
            try { toast($u['callback_query']['id'], '× хато', true); } catch (Throwable $x) {}
        }
        if ($chat && is_admin($uid)) {
            try { say($chat, "× <code>" . h(mb_substr($e->getMessage(), 0, 250)) . "</code>"); }
            catch (Throwable $x) {}
        } elseif ($chat) {
            try { say($chat, "⚠️ Хатои муваққатӣ. Такрор кунед ё /start"); }
            catch (Throwable $x) {}
        }
    }
}

function touch_u(array $f): void {
    q("INSERT INTO z_users (id,username,name,created_at,seen_at) VALUES (?,?,?,?,?)
       ON DUPLICATE KEY UPDATE username=VALUES(username), name=VALUES(name), seen_at=VALUES(seen_at)",
      [$f['id'], $f['username'] ?? null, mb_substr($f['first_name'] ?? '', 0, 120), time(), time()]);
}

function on_msg(array $m): void {
    $TR = cfg('trace', '0') === '1';
    $step = fn($x) => $TR ? zlog('trace', '  msg: ' . $x) : null;

    $chat = $m['chat']['id'] ?? null;
    $from = $m['from'] ?? null;
    $step('вход chat=' . var_export($chat, true) . ' type=' . ($m['chat']['type'] ?? '?'));

    if (!$chat || !$from || ($m['chat']['type'] ?? '') !== 'private') {
        $step('ВЫХОД: не приватный чат');
        return;
    }
    $uid = (int)$from['id'];

    try { touch_u($from); } catch (Throwable $e) { $step('touch_u ОШИБКА: ' . $e->getMessage()); }

    $u = one("SELECT blocked FROM z_users WHERE id=?", [$uid]);
    if ($u && (int)$u['blocked'] >= 1) { $step('ВЫХОД: пользователь заблокирован'); return; }

    if (!rate('tg:' . $uid, 60, 60)) {
        $step('ВЫХОД: лимит сообщений');
        if (rate('warn:' . $uid, 1, 300)) say($chat, T('fast', $uid));
        return;
    }

    $text = trim((string)($m['text'] ?? ''));
    $step('текст=' . mb_substr($text, 0, 40));
    $st   = get_st($uid);

    if ($text === '/start' || str_starts_with($text, '/start ') || $text === '/menu') {
        clr_st($uid);
        if (str_starts_with($text, '/start ')) {
            $inv = (int)preg_replace('/\D/', '', substr($text, 7));
            if ($inv > 0 && $inv !== $uid) {
                $me = one("SELECT ref_by, created_at FROM z_users WHERE id=?", [$uid]);
                if ($me && empty($me['ref_by']) && (time() - (int)$me['created_at']) < 300
                    && one("SELECT id FROM z_users WHERE id=?", [$inv])) {
                    q("UPDATE z_users SET ref_by=? WHERE id=? AND ref_by IS NULL", [$inv, $uid]);
                }
            }
        }
        $me = one("SELECT phone, lang FROM z_users WHERE id=?", [$uid]);
        $step('start: lang=' . var_export($me['lang'] ?? null, true)
              . ' phone=' . (empty($me['phone']) ? 'нет' : 'есть'));

        if (empty($me['lang']) || !in_array($me['lang'], LNGS, true)) {
            $step('→ показываю выбор языка');
            say($chat, "<b>ZVER TAJ</b>\n<code>───────────────</code>\nЗабон / Язык / Til / Language",
                kb_langs());
            return;
        }
        if (empty($me['phone'])) { $step('→ прошу телефон'); ask_phone($chat, $uid); return; }

        $ok = true;
        try { $ok = sub_ok($uid); } catch (Throwable $e) { $step('sub_ok ОШИБКА: ' . $e->getMessage()); }
        $step('подписка=' . ($ok ? 'ок' : 'нет') . ' каналов=' . count(subs_list(true)));
        if (!$ok) { $step('→ прошу подписку'); ask_sub($chat, $uid); return; }

        $step('→ главное меню');
        $r = say($chat, main_text($uid), kb_main($uid));
        $step('sendMessage ok=' . var_export($r['ok'] ?? null, true)
              . ' ' . mb_substr((string)($r['description'] ?? ''), 0, 80));
        return;
    }
    if ($text === '/lang') { say($chat, T('lng', $uid), kb_langs(ulang($uid))); return; }
    if ($text === '/id')   { say($chat, "ID · <code>$uid</code>"); return; }
    if ($text === '/unban') {
        if (!is_admin($uid)) { say($chat, '×'); return; }
        $b = 0; $r = 0;
        try { $b = q("DELETE FROM z_bans")->rowCount(); } catch (Throwable $e) {}
        try { $r = q("DELETE FROM z_rate")->rowCount(); } catch (Throwable $e) {}
        say($chat, "● Тоза шуд\n<code>───────────────</code>\nБанҳо · <b>$b</b>\nЛимитҳо · <b>$r</b>");
        return;
    }

    if ($text === '/admin' || $text === '/a') {
        if (!is_admin($uid)) { say($chat, '×'); return; }
        say($chat, "<b>ПАНЕЛИ АДМИН</b>\n<code>───────────────</code>\n"
            . h(cfg('shop', '')) . " · " . VERSION, kb_adm());
        return;
    }

    if (!empty($m['contact'])) {
        $ph = (string)($m['contact']['phone_number'] ?? '');
        $own = (int)($m['contact']['user_id'] ?? 0);
        if ($ph === '' || ($own && $own !== $uid)) { say($chat, T('own', $uid)); return; }
        q("UPDATE z_users SET phone=? WHERE id=?", [mb_substr($ph, 0, 30), $uid]);
        tg('sendMessage', ['chat_id' => $chat, 'text' => '● ' . T('reg', $uid),
                           'reply_markup' => ['remove_keyboard' => true]]);
        show_main($chat, null, $uid);
        return;
    }

    if (!empty($m['photo']) && $st['st'] === 'rq_logo' && is_admin($uid)) {
        $ph = $m['photo'];
        $fid = end($ph)['file_id'] ?? null;
        if ($fid) {
            $d = $st['data'];
            $d['logo'] = $fid;
            set_st($uid, 'rq_name', $d);
            say($chat, "● Логотип қабул шуд\n<code>───────────────</code>\n"
                . "<b>Қадами 3 аз 5</b>\n\n"
                . "Ном ва насабро нависед — ҳамон тавре ки дар корт аст:\n\n"
                . "<i>Мисол: Алиҷон Раҳмонов</i>",
                [[['text' => '× Бекор', 'callback_data' => 'a:req']]]);
        }
        return;
    }

    if (!empty($m['photo']) && $st['st'] === 'receipt') {
        $ph  = $m['photo'];
        $fid = end($ph)['file_id'] ?? null;
        if ($fid) receipt_from_bot($chat, $uid, (int)($st['data']['tid'] ?? 0), $fid);
        return;
    }
    if ($st['st'] === 'receipt') { say($chat, '▸ Расми чекро фиристед'); return; }

    if ($st['st'] === 'rev_txt') {
        $d = $st['data'];
        clr_st($uid);
        $oid = (int)$d['oid'];
        $txt = trim($text);
        if ($txt !== '' && $txt !== '-') {
            q("UPDATE z_reviews SET txt=? WHERE order_id=?", [mb_substr($txt, 0, 500), $oid]);
        }
        $stars = (int)($d['st'] ?? 5);

        // ба канал мефиристем (ситораҳо >= rev_min, матн ҳатмӣ нест)
        $posted = false;
        try { $posted = post_review($oid); } catch (Throwable $e) { zlog('review', $e->getMessage()); }

        $ok = "<b>" . T('revOk', $uid) . "</b>";
        if ($posted) $ok .= "\n\n<i>" . T('revPub', $uid) . "</i>";
        say($chat, $ok, kb_main($uid));

        $u = one("SELECT name,username FROM z_users WHERE id=?", [$uid]);
        $nm = $u['name'] ?? 'Корбар';
        if (!empty($u['username'])) $nm .= ' (@' . $u['username'] . ')';

        // ба админ: ҳамаи шарҳҳо, бо тугмаи дастӣ фиристодан
        $head = $stars <= 3 ? "⚠︎ <b>ШАРҲИ БАД · $stars/5</b>"
                            : "★ <b>ШАРҲИ НАВ · $stars/5</b>";
        $kb = $posted ? null
            : [[['text' => '➤ Ба канал фиристодан', 'callback_data' => 'a:rvp:' . $oid]]];
        foreach (admins_list() as $a) {
            say($a, $head . "\n<code>───────────────</code>\n"
                . h($nm) . " (<code>$uid</code>)\nФармоиш #" . $oid . "\n\n"
                . ($txt !== '' && $txt !== '-' ? h($txt) : '<i>бе матн</i>')
                . ($posted ? "\n\n<i>● Дар канал ҷой гирифт</i>" : ''), $kb);
        }
        return;
    }

    if (is_admin($uid) && $st['st']
        && (str_starts_with($st['st'], 'a_') || str_starts_with($st['st'], 'rq_')
            || str_starts_with($st['st'], 'sub_'))) {
        admin_input($chat, $uid, $st, $text);
        return;
    }
    show_main($chat, null, $uid);
}

function ask_phone($chat, $uid): void {
    tg('sendMessage', [
        'chat_id' => $chat,
        'text' => "<b>" . h(cfg('shop', 'ZVER TAJ')) . "</b>\n<code>───────────────</code>\n"
                . T('phone', $uid),
        'parse_mode' => 'HTML',
        'reply_markup' => ['keyboard' => [[['text' => '▸ ' . T('phb', $uid), 'request_contact' => true]]],
                           'resize_keyboard' => true, 'one_time_keyboard' => true],
    ]);
}

function receipt_from_bot($chat, $uid, int $tid, string $fid): void {
    $t = one("SELECT * FROM z_topups WHERE id=? AND uid=?", [$tid, $uid]);
    if (!$t || $t['status'] !== 'new') { clr_st($uid); say($chat, '▸ /start'); return; }
    q("UPDATE z_topups SET file_id=?, status='pending' WHERE id=?", [$fid, $tid]);
    clr_st($uid);
    say($chat, "<b>● ЧЕК ҚАБУЛ ШУД</b>\n<code>───────────────</code>\n"
        . "Маблағ · <b>" . money((float)$t['amount']) . "</b>\nАдмин тасдиқ мекунад.",
        kb_main($uid));
    $u = one("SELECT name,username FROM z_users WHERE id=?", [$uid]);
    $cap = "<b>◆ ПУР КАРДАНИ ҲАМЁН #{$tid}</b>\n"
         . "Муштарӣ · " . h($u['name'] ?? $uid)
         . (!empty($u['username']) ? " (@" . h($u['username']) . ")" : '') . "\n"
         . "Маблағ · <b>" . money((float)$t['amount']) . "</b>";
    foreach (ADMINS as $a) {
        tg('sendPhoto', ['chat_id' => $a, 'photo' => $fid, 'caption' => $cap, 'parse_mode' => 'HTML',
            'reply_markup' => ['inline_keyboard' => [[
                ['text' => '● Тасдиқ', 'callback_data' => 'at:d:' . $tid],
                ['text' => '× Рад',    'callback_data' => 'at:f:' . $tid]]]]]);
    }
}

function on_cb(array $cb): void {
    $d    = (string)($cb['data'] ?? '');
    $chat = $cb['message']['chat']['id'] ?? null;
    $mid  = $cb['message']['message_id'] ?? null;
    $uid  = (int)($cb['from']['id'] ?? 0);
    if (!$chat) { toast($cb['id']); return; }
    touch_u($cb['from']);
    if (!rate('cb:' . $uid, 90, 60)) { toast($cb['id'], T('fast', $uid), true); return; }
    if ($d === 'noop') { toast($cb['id']); return; }

    if ($d === 'a' || str_starts_with($d, 'a:') || str_starts_with($d, 'ao:')
        || str_starts_with($d, 'at:') || str_starts_with($d, 'atr:')) {
        if (!is_admin($uid)) { toast($cb['id'], '×', true); return; }
        admin_cb($cb, $d === 'a' ? 'a:menu' : $d, $chat, $mid, $uid);
        return;
    }

    if (str_starts_with($d, 'lang:')) {
        $l = substr($d, 5);
        if (!in_array($l, LNGS, true)) { toast($cb['id']); return; }
        q("UPDATE z_users SET lang=? WHERE id=?", [$l, $uid]);
        toast($cb['id'], T('lok', null, $l), true);
        $ph = one("SELECT phone FROM z_users WHERE id=?", [$uid]);
        if (empty($ph['phone'])) {
            tg('deleteMessage', ['chat_id' => $chat, 'message_id' => $mid]);
            ask_phone($chat, $uid);
        } else ed($chat, $mid, main_text($uid), kb_main($uid));
        return;
    }

    if (str_starts_with($d, 'rv:')) {
        [, $oid, $st] = array_pad(explode(':', $d), 3, '');
        $oid = (int)$oid; $st = max(1, min(5, (int)$st));
        if (!one("SELECT id FROM z_orders WHERE id=? AND uid=?", [$oid, $uid])) {
            toast($cb['id'], '×', true); return;
        }
        try { q("INSERT INTO z_reviews (uid,order_id,stars,created_at) VALUES (?,?,?,?)
                 ON DUPLICATE KEY UPDATE stars=VALUES(stars)",
                [$uid, $oid, $st, time()]); } catch (Throwable $e) {}
        set_st($uid, 'rev_txt', ['oid' => $oid, 'st' => $st]);
        ed($chat, $mid, str_repeat('★', $st) . str_repeat('☆', 5 - $st)
            . "\n\n<b>" . T('revTh', $uid) . "</b>\n\n"
            . ($st >= 4 ? T('revAsk', $uid) : T('revBad', $uid)),
            [[['text' => '→ ' . T('skip', $uid), 'callback_data' => 'rvs:' . $oid]]]);
        toast($cb['id'], '★');
        return;
    }

    if (str_starts_with($d, 'rvs:')) {
        $oid = (int)substr($d, 4);
        clr_st($uid);
        if (!one("SELECT id FROM z_reviews WHERE order_id=? AND uid=?", [$oid, $uid])) {
            toast($cb['id'], '×', true); return;
        }
        $posted = false;
        try { $posted = post_review($oid); } catch (Throwable $e) { zlog('review', $e->getMessage()); }
        ed($chat, $mid, "<b>" . T('revOk', $uid) . "</b>"
            . ($posted ? "\n\n<i>" . T('revPub', $uid) . "</i>" : ''), kb_main($uid));
        toast($cb['id'], '●');
        return;
    }

    if ($d === 'subchk') {
        if (sub_ok($uid)) {
            toast($cb['id'], '●', true);
            ed($chat, $mid, main_text($uid), kb_main($uid));
        } else toast($cb['id'], T('subNo', $uid), true);
        return;
    }

    if (!sub_ok($uid) && !str_starts_with($d, 'lang:')) { ask_sub($chat, $uid, $mid); toast($cb['id']); return; }

    if ($d === 'menu') { clr_st($uid); show_main($chat, $mid, $uid); toast($cb['id']); return; }

    if ($d === 'l') {
        ed($chat, $mid, T('lng', $uid), array_merge(kb_langs(ulang($uid)),
            [[['text' => T('back', $uid), 'callback_data' => 'menu']]]));
        toast($cb['id']); return;
    }

    if ($d === 'h') {
        $kb = [];
        $wa = wa_link($uid);
        if ($wa !== '') $kb[] = [['text' => '✆ WHATSAPP', 'url' => $wa]];
        $sup = tg_url(cfg('support', ''));
        if ($sup !== '') $kb[] = [['text' => '✈ TELEGRAM', 'url' => $sup]];
        $kb[] = [['text' => T('back', $uid), 'callback_data' => 'menu']];
        ed($chat, $mid, "<b>" . h(T('hlp', $uid)) . "</b>\n<code>───────────────</code>\n"
            . T('q', $uid), $kb);
        toast($cb['id']); return;
    }

    if ($d === 'w') {
        $u = one("SELECT balance,spent,orders_cnt FROM z_users WHERE id=?", [$uid]);
        $t  = "<b>" . T('wallet', $uid) . "</b>\n<code>───────────────</code>\n";
        $t .= T('bal', $uid) . " · <b>" . money((float)($u['balance'] ?? 0)) . "</b>\n";
        $t .= T('spent', $uid) . " · " . money((float)($u['spent'] ?? 0)) . "\n";
        $t .= T('cnt', $uid) . " · " . (int)($u['orders_cnt'] ?? 0) . "\n";
        $t .= "<code>───────────────</code>\n▸ " . T('topup', $uid);
        ed($chat, $mid, $t, [
            [['text' => T('app', $uid), 'web_app' => ['url' => app_url()]]],
            [['text' => T('back', $uid), 'callback_data' => 'menu']]]);
        toast($cb['id']); return;
    }

    if (str_starts_with($d, 'o:')) {
        $rows = all("SELECT * FROM z_orders WHERE uid=? ORDER BY id DESC LIMIT 10", [$uid]);
        if (!$rows) { ed($chat, $mid, '▸ ' . T('noord', $uid),
            [[['text' => T('back', $uid), 'callback_data' => 'menu']]]); toast($cb['id']); return; }
        $ic = ['new' => '○', 'done' => '●', 'fail' => '×', 'refund' => '↩'];
        $t = "<b>" . T('myord', $uid) . "</b>\n";
        foreach ($rows as $o) {
            $t .= "<code>───────────────</code>\n";
            $t .= ($ic[$o['status']] ?? '·') . " <b>" . h($o['game_name']) . "</b> · "
                . h($o['pack_name']) . "\n";
            $t .= "   " . money((float)$o['price']) . " · " . date('d.m H:i', (int)$o['created_at']) . "\n";
            if (!empty($o['code'])) $t .= "   <code>" . h($o['code']) . "</code>\n";
        }
        ed($chat, $mid, mb_substr($t, 0, 3900), [[['text' => T('back', $uid), 'callback_data' => 'menu']]]);
        toast($cb['id']); return;
    }

    if ($d === 'r') {
        $u  = one("SELECT ref_cnt, ref_sum FROM z_users WHERE id=?", [$uid]);
        $b  = (float)cfg('ref_bonus', '0.50');
        $ln = bot_user() !== '' ? 'https://t.me/' . bot_user() . '?start=' . $uid : '';
        $t  = "<b>" . T('rf', $uid) . "</b>\n<code>───────────────</code>\n";
        $t .= sprintf(T('rfg', $uid), '<b>' . money($b) . '</b>') . "\n";
        $t .= "<i>" . T('rfa', $uid) . "</i>\n<code>───────────────</code>\n";
        $t .= T('rfi', $uid) . " · <b>" . (int)($u['ref_cnt'] ?? 0) . "</b>\n";
        $t .= T('rfs', $uid) . " · <b>" . money((float)($u['ref_sum'] ?? 0)) . "</b>\n\n";
        $t .= T('rfl', $uid) . "\n<code>" . h($ln) . "</code>";
        ed($chat, $mid, $t, [
            [['text' => '▸ ' . T('rfb', $uid),
              'url' => 'https://t.me/share/url?url=' . urlencode($ln)
                     . '&text=' . urlencode(T('rfp', $uid) . ' · ' . cfg('shop', ''))]],
            [['text' => T('back', $uid), 'callback_data' => 'menu']]]);
        toast($cb['id']); return;
    }

    toast($cb['id']);
}

/* ======================= АДМИН ======================= */

function kb_adm(): array {
    $newO = (int)(one("SELECT COUNT(*) c FROM z_orders WHERE status='new'")['c'] ?? 0);
    $newT = (int)(one("SELECT COUNT(*) c FROM z_topups WHERE status='pending'")['c'] ?? 0);
    return [
        [['text' => '◆ ФАРМОИШҲО' . ($newO ? " ($newO)" : ''), 'callback_data' => 'a:ord']],
        [['text' => '◆ ПУР КАРДАНҲО' . ($newT ? " ($newT)" : ''), 'callback_data' => 'a:tops']],
        [['text' => '⟳ СИНК КАТАЛОГ', 'callback_data' => 'a:sync'],
         ['text' => '$ БАЛАНС', 'callback_data' => 'a:bal']],
        [['text' => '⏳ НАВБАТ', 'callback_data' => 'a:queue'],
         ['text' => '≡ ТАЪРИХИ ҲАМЁН', 'callback_data' => 'a:tx']],
        [['text' => '↩ БАРГАРДОНИДАНИ ПУЛИ ЧАСПИДА', 'callback_data' => 'a:stuck']],
        [['text' => '⚡️ АВТОҚАБУЛИ ПАРДОХТ', 'callback_data' => 'a:bank']],
        [['text' => '⧉ ГУРӮҲБАНДӢ (регионҳо)', 'callback_data' => 'a:group']],
        [['text' => '⌕ САНҶИШИ ID — навсозӣ', 'callback_data' => 'a:vsync']],
        [['text' => '👤 Номи бозингар (FlashTopup)', 'callback_data' => 'a:ftnick']],
        [['text' => '🎟 ПРОМОКОДҲО', 'callback_data' => 'a:pr'],
         ['text' => '★ ШАРҲҲО', 'callback_data' => 'a:rv']],
        [['text' => '🌍 МИНТАҚАҲО (нишон додан/пинҳон)', 'callback_data' => 'a:regs:0']],
        [['text' => '🧹 ТОЗАКУНӢ (кӯҳнаҳоро нест кун)', 'callback_data' => 'a:clean']],
        [['text' => '↺ ҲАМАРО ФАЪОЛ КАРДАН', 'callback_data' => 'a:packon']],
        [['text' => '▪ БОЗИҲО', 'callback_data' => 'a:games'],
         ['text' => '▪ ПАКЕТҲО', 'callback_data' => 'a:gp']],
        [['text' => '% ФОИДА', 'callback_data' => 'a:set:markup'],
         ['text' => '≈ КУРС', 'callback_data' => 'a:set:rate']],
        [['text' => '▪ РЕКВИЗИТҲО', 'callback_data' => 'a:req'],
         ['text' => '▪ КОРБАРОН', 'callback_data' => 'a:usr:0']],
        [['text' => '📢 ОП-КАНАЛҲО (обунаи ҳатмӣ)', 'callback_data' => 'a:subs']],
        [['text' => '▪ ОМОР', 'callback_data' => 'a:stat'],
         ['text' => '▪ ЭЪЛОН', 'callback_data' => 'a:bc']],
        [['text' => '▪ ТАНЗИМОТ', 'callback_data' => 'a:cfg']],
        [['text' => '‹ Бозгашт', 'callback_data' => 'menu']],
    ];
}

function admin_cb(array $cb, string $d, $chat, $mid, $uid): void {
    try { admin_cb_run($cb, $d, $chat, $mid, $uid); }
    catch (Throwable $e) {
        zlog('admin', $d . ' | ' . $e->getMessage() . ' @' . $e->getLine());
        toast($cb['id'] ?? '', '× хато', true);
        try {
            say($chat, "× <b>Хато</b>\n<code>" . h(mb_substr($e->getMessage(), 0, 200))
                . "</code>", [[['text' => '‹ Меню', 'callback_data' => 'a:menu']]]);
        } catch (Throwable $e2) {}
    }
}

function admin_cb_run(array $cb, string $d, $chat, $mid, $uid): void {
    // фармоиш
    if (str_starts_with($d, 'ao:')) {
        [, $act, $oid] = array_pad(explode(':', $d), 3, '');
        $oid = (int)$oid;
        if ($act === 'd') {
            $ok = order_done($oid, $uid);
            tg('editMessageText', ['chat_id' => $chat, 'message_id' => $mid, 'parse_mode' => 'HTML',
                'text' => ($ok ? "<b>● ИҶРО ШУД</b> · #$oid" : "Аллакай коркард шуд · #$oid")]);
            toast($cb['id'], $ok ? '●' : '·'); return;
        }
        if ($act === 'f') {
            $ok = order_fail($oid, $uid, 'Иҷро нашуд');
            tg('editMessageText', ['chat_id' => $chat, 'message_id' => $mid, 'parse_mode' => 'HTML',
                'text' => ($ok ? "<b>× НАШУД</b> · #$oid · пул баргашт" : "Аллакай коркард шуд · #$oid")]);
            toast($cb['id'], $ok ? '×' : '·'); return;
        }
        if ($act === 'c') {
            set_st($uid, 'a_code', ['oid' => $oid]);
            say($chat, "⌨ Коди фармоиш #$oid-ро нависед:");
            toast($cb['id']); return;
        }
    }

    // пур кардан
    if (str_starts_with($d, 'at:')) {
        [, $act, $tid] = array_pad(explode(':', $d), 3, '');
        $tid = (int)$tid;
        if ($act === 'd') {
            $before = one("SELECT status, amount, uid FROM z_topups WHERE id=?", [$tid]);
            // force=true — тасдиқи дастии админ аз ҳар ҳолат ғайр аз 'ok'
            $ok = topup_credit($tid, $uid, null, false, true);

            if ($ok) {
                $nb = (float)(one("SELECT balance FROM z_users WHERE id=?",
                                  [(int)$before['uid']])['balance'] ?? 0);
                $cap = "<b>● ТАСДИҚ ШУД</b> · #$tid\n<code>───────────────</code>\n"
                     . "+ <b>" . money((float)$before['amount']) . "</b>\n"
                     . "Баланси муштарӣ · <b>" . money($nb) . "</b>"
                     . (($before['status'] ?? '') === 'no'
                        ? "\n\n<i>Дастӣ тасдиқ шуд (ИИ рад карда буд).</i>" : '');
            } else {
                $cap = "· <b>АЛЛАКАЙ ЗАЧИСЛЕНИЕ ШУДА БУД</b> · #$tid\n"
                     . "<code>───────────────</code>\n"
                     . "<i>Пул аллакай ба ҳамён гузошта шудааст. Дубора намешавад.</i>";
            }
            ed_any($chat, $mid, $cap);
            toast($cb['id'], $ok ? '● Зачислено' : '· Уже зачислено', true); return;
        }
        // × РАД → аввал сабабро мепурсем
        if ($act === 'f') {
            $t = one("SELECT * FROM z_topups WHERE id=?", [$tid]);
            if ($t && $t['status'] === 'ok') {
                ed_any($chat, $mid, "· <b>ДЕР ШУД</b> · #$tid\n"
                    . "<i>Пул аллакай гузошта шудааст — рад кардан мумкин нест.</i>");
                toast($cb['id'], '· Уже зачислено', true); return;
            }
            $kb = [];
            foreach (rej_reasons() as $code => $ru) {
                $kb[] = [['text' => $ru, 'callback_data' => 'atr:' . $code . ':' . $tid]];
            }
            $kb[] = [['text' => '⌨ Сабаби худам', 'callback_data' => 'atr:own:' . $tid]];
            $kb[] = [['text' => '→ Бе сабаб (гузаштан)', 'callback_data' => 'atr:skip:' . $tid]];
            $kb[] = [['text' => '‹ Бекор', 'callback_data' => 'atr:back:' . $tid]];

            ed_any($chat, $mid, "× <b>РАД КАРДАНИ #$tid</b>\n<code>───────────────</code>\n"
                . "Маблағ · <b>" . money((float)($t['amount'] ?? 0)) . "</b>\n\n"
                . "Сабабро интихоб кунед — ба муштарӣ фиристода мешавад.", $kb);
            toast($cb['id']); return;
        }
    }

    // сабаби радкунӣ
    if (str_starts_with($d, 'atr:')) {
        [, $code, $tid] = array_pad(explode(':', $d), 3, '');
        $tid = (int)$tid;
        $t = one("SELECT * FROM z_topups WHERE id=?", [$tid]);
        if (!$t) { toast($cb['id'], '×', true); return; }

        if ($code === 'back') {
            $kb = [[['text' => '● ТАСДИҚ', 'callback_data' => 'at:d:' . $tid],
                    ['text' => '× РАД',    'callback_data' => 'at:f:' . $tid]]];
            ed_any($chat, $mid, "<b>◆ ПУР КАРДАНИ ҲАМЁН #{$tid}</b>\n"
                . "<code>───────────────</code>\n"
                . "Маблағ · <b>" . money((float)$t['amount']) . "</b>\n"
                . (!empty($t['comment']) ? "Шарҳ · <code>" . h((string)$t['comment']) . "</code>" : ''),
                $kb);
            toast($cb['id']); return;
        }

        if ($code === 'own') {
            set_st($uid, 'a_rej', ['tid' => $tid, 'mid' => $mid, 'chat' => $chat]);
            say($chat, "⌨ Сабаби радкуниро нависед барои #$tid:\n"
                . "<i>«-» = бе сабаб</i>");
            toast($cb['id']); return;
        }

        $ok = topup_deny($tid, $uid, $code === 'skip' ? '' : $code);
        ed_any($chat, $mid, $ok
            ? "<b>× РАД ШУД</b> · #$tid"
              . ($code === 'skip' ? "\n<i>Бе сабаб</i>"
                                  : "\n<i>" . h(rej_reasons()[$code] ?? '') . "</i>")
            : "· Аллакай коркард шуд · #$tid",
            [[['text' => '● Ба ҳар ҳол тасдиқ', 'callback_data' => 'at:d:' . $tid]]]);
        toast($cb['id'], $ok ? '×' : '·'); return;
    }

    $c = substr($d, 2);

    if ($c === '' || $c === 'menu') {
        ed($chat, $mid, "<b>ПАНЕЛИ АДМИН</b>\n<code>───────────────</code>\n"
            . h(cfg('shop', '')) . " · " . VERSION, kb_adm());
        toast($cb['id']); return;
    }

    if ($c === 'sync') {
        toast($cb['id'], 'Сар шуд...');
        ed($chat, $mid, "⟳ <b>СИНХРОНИЗАТСИЯ</b>\n<code>───────────────</code>\nБор мешавад...");
        $t0 = time(); $last = 0;
        $st = fz_sync(function ($i, $tot, $pk) use ($chat, $mid, $t0, &$last) {
            if (time() - $last < 3) return;
            $last = time();
            $pct = $tot ? (int)round($i / $tot * 100) : 0;
            $bar = str_repeat('█', (int)round($pct / 10)) . str_repeat('░', 10 - (int)round($pct / 10));
            ed($chat, $mid, "⟳ <b>СИНХРОНИЗАТСИЯ</b>\n<code>───────────────</code>\n"
                . "<code>$bar</code> $pct%\n\nБозиҳо · <b>$i</b> / $tot\nПакетҳо · <b>$pk</b>\n"
                . "Вақт · " . gmdate('i:s', time() - $t0));
        });
        $t = "● <b>КАТАЛОГ НАВ ШУД</b>\n<code>───────────────</code>\n"
           . "Бозиҳо · <b>{$st['g']}</b>\nПакетҳо · <b>{$st['p']}</b>\n";
        if (!empty($st['old']))  $t .= "Кӯҳна нест шуд · <b>{$st['old']}</b> пакет\n";
        if (!empty($st['off']))  $t .= "Хомӯш шуд · <b>{$st['off']}</b> пакет\n";
        if (!empty($st['offg'])) $t .= "Хомӯш шуд · <b>{$st['offg']}</b> бозӣ\n";
        $t .= "Вақт · " . gmdate('i:s', time() - $t0) . "\n";
        if ($st['err']) $t .= "\n× Хатоҳо · " . count($st['err']) . "\n"
                            . h(mb_substr(implode("\n", array_slice($st['err'], 0, 3)), 0, 400));
        ed($chat, $mid, $t, [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        return;
    }

    if ($c === 'packon') {
        $g = q("UPDATE z_games SET active=1 WHERE active=0 AND hidden=0")->rowCount();
        $n = q("UPDATE z_packs SET active=1 WHERE active=0")->rowCount();
        $ag = (int)(one("SELECT COUNT(*) c FROM z_games WHERE active=1")['c'] ?? 0);
        $ap = (int)(one("SELECT COUNT(*) c FROM z_packs WHERE active=1")['c'] ?? 0);
        ed($chat, $mid, "● <b>КАТАЛОГ БАРГАРДОНИДА ШУД</b>\n<code>───────────────</code>\n"
            . "Фаъол шуд · <b>$g</b> бозӣ, <b>$n</b> пакет\n"
            . "Ҳоло фаъол · <b>$ag</b> бозӣ, <b>$ap</b> пакет",
            [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        toast($cb['id'], '●', true); return;
    }

    if ($c === 'pr') {
        $rows = all("SELECT * FROM z_promo ORDER BY active DESC, id DESC LIMIT 20");
        $t = "<b>ПРОМОКОДҲО</b>\n";
        $kb = [];
        foreach ($rows as $r) {
            $d = $r['kind'] === 'fix' ? money((float)$r['val']) : rtrim(rtrim(number_format((float)$r['val'], 2, '.', ''), '0'), '.') . '%';
            $t .= "<code>───────────────</code>\n"
                . ((int)$r['active'] ? '●' : '○') . " <code>" . h($r['code']) . "</code> · <b>−$d</b>\n"
                . "Истифода · " . (int)$r['used']
                . ((int)$r['max_uses'] > 0 ? '/' . (int)$r['max_uses'] : '')
                . " · Тахфиф: " . money((float)$r['saved']) . "\n";
            $kb[] = [['text' => ((int)$r['active'] ? '● ' : '○ ') . $r['code'] . " · −$d",
                      'callback_data' => 'a:pr1:' . $r['id']]];
        }
        if (!$rows) $t .= "<i>Ҳанӯз промокод нест</i>\n";
        $kb[] = [['text' => '+ ПРОМОКОДИ НАВ', 'callback_data' => 'a:pradd']];
        $kb[] = [['text' => '‹', 'callback_data' => 'a:menu']];
        ed($chat, $mid, mb_substr($t, 0, 3800), $kb);
        toast($cb['id']); return;
    }

    if ($c === 'pradd') {
        set_st($uid, 'a_pradd', []);
        ed($chat, $mid, "<b>ПРОМОКОДИ НАВ</b>\n<code>───────────────</code>\n"
            . "<code>РАМЗ | тахфиф | ҳадди ақал | шумора | ба як нафар</code>\n\n"
            . "<b>Мисолҳо:</b>\n"
            . "<code>ZVER10 | 10%</code> — 10% тахфиф\n"
            . "<code>ZVER15 | 15% | 50</code> — 15%, аз 50 сомонӣ\n"
            . "<code>SALOM | 5 | 0 | 100 | 1</code> — 5 сомонӣ, 100 маротиба, 1 бор ба ҳар кас\n\n"
            . "<i>Танҳо ду майдони аввал ҳатмист.\n"
            . "Бе % — маблағи тайёр (сомонӣ).</i>",
            [[['text' => '‹', 'callback_data' => 'a:pr']]]);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'pr1:')) {
        $pid = (int)substr($c, 4);
        $r = one("SELECT * FROM z_promo WHERE id=?", [$pid]);
        if (!$r) { toast($cb['id'], '×', true); return; }
        $d = $r['kind'] === 'fix' ? money((float)$r['val'])
           : rtrim(rtrim(number_format((float)$r['val'], 2, '.', ''), '0'), '.') . '%';
        $t  = "<b>" . h($r['code']) . "</b>\n<code>───────────────</code>\n";
        $t .= "Тахфиф · <b>−$d</b>\n";
        $t .= "Ҳадди ақали харид · " . ((float)$r['min_sum'] > 0 ? money((float)$r['min_sum']) : '—') . "\n";
        $t .= "Ҳадди шумора · " . ((int)$r['max_uses'] > 0 ? (int)$r['max_uses'] : '∞') . "\n";
        $t .= "Ба як корбар · " . ((int)$r['per_user'] > 0 ? (int)$r['per_user'] : '∞') . "\n";
        $t .= "Мӯҳлат · " . (!empty($r['until']) ? date('d.m.Y', (int)$r['until']) : '—') . "\n";
        $t .= "<code>───────────────</code>\n";
        $t .= "Истифода шуд · <b>" . (int)$r['used'] . "</b>\n";
        $t .= "Ҷамъи тахфиф · <b>" . money((float)$r['saved']) . "</b>\n";
        $t .= "Ҳолат · " . ((int)$r['active'] ? '● фаъол' : '○ хомӯш');
        ed($chat, $mid, $t, [
            [['text' => (int)$r['active'] ? '○ Хомӯш' : '● Фаъол', 'callback_data' => 'a:prtog:' . $pid],
             ['text' => '🗑 Нест', 'callback_data' => 'a:prdel:' . $pid]],
            [['text' => '📊 Кӣ истифода кард', 'callback_data' => 'a:pruse:' . $pid]],
            [['text' => '‹', 'callback_data' => 'a:pr']]]);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'prtog:')) {
        q("UPDATE z_promo SET active=1-active WHERE id=?", [(int)substr($c, 6)]);
        admin_cb($cb, 'a:pr1:' . (int)substr($c, 6), $chat, $mid, $uid); return;
    }
    if (str_starts_with($c, 'prdel:')) {
        $pid = (int)substr($c, 6);
        q("DELETE FROM z_promo WHERE id=?", [$pid]);
        q("DELETE FROM z_promo_use WHERE promo_id=?", [$pid]);
        toast($cb['id'], 'Нест шуд', true);
        admin_cb($cb, 'a:pr', $chat, $mid, $uid); return;
    }
    if (str_starts_with($c, 'pruse:')) {
        $pid = (int)substr($c, 6);
        $rows = all("SELECT u.sum_off, u.at, x.name, x.username, u.uid
                     FROM z_promo_use u LEFT JOIN z_users x ON x.id=u.uid
                     WHERE u.promo_id=? ORDER BY u.id DESC LIMIT 15", [$pid]);
        $t = "<b>КИ ИСТИФОДА КАРД</b>\n";
        foreach ($rows as $r) {
            $t .= "<code>───────────────</code>\n"
                . h((string)($r['name'] ?? $r['uid']))
                . (!empty($r['username']) ? ' @' . h($r['username']) : '') . "\n"
                . "−" . money((float)$r['sum_off']) . " · " . date('d.m H:i', (int)$r['at']) . "\n";
        }
        if (!$rows) $t .= "<i>Ҳанӯз касе истифода накард</i>";
        ed($chat, $mid, mb_substr($t, 0, 3800),
            [[['text' => '‹', 'callback_data' => 'a:pr1:' . $pid]]]);
        toast($cb['id']); return;
    }

    // рӯйхати бозиҳое ки якчанд минтақа доранд
    if (str_starts_with($c, 'regs:')) {
        $pg = (int)substr($c, 5); $per = 10;
        $rows = all("SELECT base, COUNT(*) n,
                     SUM(active) act
                     FROM z_games WHERE base IS NOT NULL AND base<>''
                     GROUP BY base HAVING n>1 ORDER BY n DESC, base
                     LIMIT $per OFFSET " . ($pg * $per));
        $tot = (int)(one("SELECT COUNT(*) c FROM (SELECT base FROM z_games
                          WHERE base IS NOT NULL AND base<>''
                          GROUP BY base HAVING COUNT(*)>1) x")['c'] ?? 0);
        $kb = [];
        foreach ($rows as $r) {
            $kb[] = [['text' => nicebase((string)$r['base']) . ' · '
                              . (int)$r['act'] . '/' . (int)$r['n'],
                      'callback_data' => 'a:reg:' . base64_encode((string)$r['base'])]];
        }
        $pages = max(1, (int)ceil($tot / $per));
        $nav = [];
        if ($pg > 0) $nav[] = ['text' => '‹', 'callback_data' => 'a:regs:' . ($pg - 1)];
        $nav[] = ['text' => ($pg + 1) . '/' . $pages, 'callback_data' => 'noop'];
        if ($pg < $pages - 1) $nav[] = ['text' => '›', 'callback_data' => 'a:regs:' . ($pg + 1)];
        $kb[] = $nav;
        $kb[] = [['text' => '‹ Меню', 'callback_data' => 'a:menu']];
        ed($chat, $mid, "<b>МИНТАҚАҲО</b>\n<code>───────────────</code>\n"
            . "Бозиҳо бо якчанд минтақа · <b>$tot</b>\n"
            . "Бозиро интихоб кунед:", $kb);
        toast($cb['id']); return;
    }

    // минтақаҳои як бозӣ
    if (str_starts_with($c, 'reg:')) {
        $base = base64_decode(substr($c, 4)) ?: '';
        $rows = all("SELECT id,name,region,flag,active,
                     (SELECT COUNT(*) FROM z_packs p WHERE p.game_id=z_games.id AND p.active=1) pk
                     FROM z_games WHERE base=? ORDER BY region", [$base]);
        if (!$rows) { toast($cb['id'], '×', true); return; }
        $b64 = base64_encode($base);
        $on = 0;
        $kb = [];
        foreach ($rows as $r) {
            if ((int)$r['active']) $on++;
            $kb[] = [['text' => ((int)$r['active'] ? '● ' : '○ ')
                              . ($r['flag'] ?: '') . ' ' . ($r['region'] ?: '?')
                              . ' · ' . (int)$r['pk'],
                      'callback_data' => 'a:regt:' . $r['id'] . ':' . mb_substr($b64, 0, 40)]];
        }
        $kb[] = [['text' => '● Ҳамаро фаъол', 'callback_data' => 'a:regall:1:' . $b64],
                 ['text' => '○ Ҳамаро хомӯш', 'callback_data' => 'a:regall:0:' . $b64]];
        $kb[] = [['text' => '‹', 'callback_data' => 'a:regs:0']];
        ed($chat, $mid, "<b>" . h(nicebase($base)) . "</b>\n<code>───────────────</code>\n"
            . "Фаъол · <b>$on</b> аз " . count($rows) . "\n\n"
            . "<i>Пахш кунед — фаъол/хомӯш мешавад</i>", $kb);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'regt:')) {
        [, $gid, $b64] = array_pad(explode(':', $c, 3), 3, '');
        q("UPDATE z_games SET active=1-active, hidden=IF(active=1,0,1) WHERE id=?", [(int)$gid]);
        $base = one("SELECT base FROM z_games WHERE id=?", [(int)$gid])['base'] ?? '';
        admin_cb($cb, 'a:reg:' . base64_encode((string)$base), $chat, $mid, $uid);
        return;
    }

    if (str_starts_with($c, 'regall:')) {
        [, $v, $b64] = array_pad(explode(':', $c, 3), 3, '');
        $base = base64_decode($b64) ?: '';
        q("UPDATE z_games SET active=?, hidden=? WHERE base=?",
          [(int)$v, (int)$v === 1 ? 0 : 1, $base]);
        admin_cb($cb, 'a:reg:' . $b64, $chat, $mid, $uid);
        return;
    }

    if ($c === 'clean') {
        // пакетҳои FazerCards ҳатман ft_code бо '|' доранд
        $oldP = q("DELETE FROM z_packs WHERE ft_code IS NULL OR ft_code NOT LIKE '%|%'")->rowCount();
        $oldG = q("DELETE FROM z_games WHERE id NOT IN
                   (SELECT game_id FROM (SELECT DISTINCT game_id FROM z_packs) x)")->rowCount();
        $g = (int)(one("SELECT COUNT(*) c FROM z_games")['c'] ?? 0);
        $pk = (int)(one("SELECT COUNT(*) c FROM z_packs")['c'] ?? 0);
        ed($chat, $mid, "● <b>ТОЗАКУНӢ ТАМОМ</b>\n<code>───────────────</code>\n"
            . "Нест шуд · <b>$oldG</b> бозии кӯҳна\n"
            . "Нест шуд · <b>$oldP</b> пакети кӯҳна\n\n"
            . "Ҳоло · <b>$g</b> бозӣ, <b>$pk</b> пакет",
            [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        toast($cb['id'], '●', true); return;
    }

    if ($c === 'ftnick') {
        setcfg('ft_nick', cfg('ft_nick', '1') === '1' ? '0' : '1');
        $l = ftv_list();
        ed($chat, $mid, "<b>САНҶИШИ НОМ</b>\n<code>───────────────</code>\n"
            . "FlashTopup · <b>" . (cfg('ft_nick', '1') === '1' ? 'ФАЪОЛ ●' : 'хомӯш ×') . "</b>\n"
            . "Дар рӯйхати онҳо · <b>" . count($l) . "</b> бозӣ\n\n"
            . "<i>Танҳо барои нишон додани номи бозингар.\n"
            . "Харид ҳамеша аз FazerCards меравад.</i>",
            [[['text' => cfg('ft_nick', '1') === '1' ? '× Хомӯш' : '● Фаъол',
               'callback_data' => 'a:ftnick']],
             [['text' => '‹', 'callback_data' => 'a:menu']]]);
        toast($cb['id']); return;
    }

    if ($c === 'vsync') {
        toast($cb['id'], '...');
        $list = vlist(true);
        $on = 0; $off = 0;
        foreach (all("SELECT id,ft_code,name,base FROM z_games") as $g) {
            $vm = vmatch($g);
            q("UPDATE z_games SET can_chk=?, vcode=? WHERE id=?",
              [$vm ? 1 : 0, $vm ? $vm['id'] : '', $g['id']]);
            $vm ? $on++ : $off++;
        }
        $names = [];
        foreach (all("SELECT DISTINCT base FROM z_games WHERE can_chk=1 AND base IS NOT NULL
                      ORDER BY base LIMIT 12") as $b) $names[] = nicebase((string)$b['base']);
        ed($chat, $mid, "● <b>САНҶИШИ ID НАВ ШУД</b>\n<code>───────────────</code>\n"
            . "Провайдер месанҷад · <b>" . count($list) . "</b> бозӣ\n"
            . "Дар каталоги мо · <b>$on</b> бозӣ\n"
            . "Бе санҷиш · $off\n\n"
            . ($names ? "Бо санҷиш:\n· " . h(implode("\n· ", $names)) : ''),
            [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        return;
    }

    if ($c === 'group') {
        toast($cb['id'], '...');
        $r = regroup();
        $top = all("SELECT base, COUNT(*) c FROM z_games WHERE active=1
                    GROUP BY base HAVING c>1 ORDER BY c DESC LIMIT 8");
        $t  = "● <b>ГУРӮҲБАНДӢ ТАМОМ</b>\n<code>───────────────</code>\n";
        $t .= "Бозиҳо · <b>{$r['games']}</b>\n";
        $t .= "Гурӯҳҳо · <b>{$r['groups']}</b>\n";
        $t .= "Пакетҳо · <b>{$r['packs']}</b>\n";
        if ($top) {
            $t .= "<code>───────────────</code>\nБо якчанд минтақа:\n";
            foreach ($top as $x) $t .= "· " . h(nicebase((string)$x['base']))
                                     . " — <b>" . (int)$x['c'] . "</b>\n";
        }
        ed($chat, $mid, $t, [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        return;
    }

    if ($c === 'hook') {
        $self = 'https://' . ($_SERVER['HTTP_HOST'] ?? '')
              . rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/')
              . '/zbot.php?hook=fz';
        $r = fz('PUT', '/account/webhook', [], ['url' => $self, 'enabled' => true]);
        if (!empty($r['ok'])) fz('POST', '/account/webhook/test');
        $cur = fz('GET', '/account/webhook');
        ed($chat, $mid, "<b>ВЕБХУК</b>\n<code>───────────────</code>\n"
            . "<code>" . h($self) . "</code>\n\n"
            . (!empty($r['ok']) ? "● Сабт шуд" : "× " . h(fzerr($r))) . "\n\n"
            . "<code>" . h(mb_substr(json_encode($cur['webhook'] ?? $cur,
                JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES), 0, 700)) . "</code>",
            [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        toast($cb['id']); return;
    }

    if ($c === 'bank') {
        try {
            db()->exec("CREATE TABLE IF NOT EXISTS z_bank (
                id INT AUTO_INCREMENT PRIMARY KEY,
                op_no VARCHAR(64) NULL, amount DECIMAL(12,2), top_id INT NULL,
                comment VARCHAR(120) NULL, op_date VARCHAR(24) NULL, op_time VARCHAR(16) NULL,
                card VARCHAR(40) NULL, sender VARCHAR(120) NULL,
                matched INT NULL, raw TEXT NULL, created_at INT,
                UNIQUE KEY uq_op (op_no), INDEX (amount)
             ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
        } catch (Throwable $e) {}

        $tot = 0; $ok = 0; $rows = [];
        try {
            $r0 = one("SELECT COUNT(*) c, SUM(matched IS NOT NULL) m FROM z_bank");
            $tot = (int)($r0['c'] ?? 0); $ok = (int)($r0['m'] ?? 0);
            $rows = all("SELECT * FROM z_bank ORDER BY id DESC LIMIT 6");
        } catch (Throwable $e) {}

        $pend = (int)(one("SELECT COUNT(*) c FROM z_topups WHERE status='pending'")['c'] ?? 0);
        $t  = "⚡️ <b>АВТОҚАБУЛИ ПАРДОХТ</b>\n<code>───────────────</code>\n";
        $t .= "Уведомленияҳо · <b>{$tot}</b>\n";
        $t .= "Худкор тасдиқ · <b>{$ok}</b>\n";
        $t .= "Интизори чек · <b>{$pend}</b>\n\n";
        $t .= "Мӯҳлати интизорӣ · <b>" . cfg('bank_wait', '20') . "</b> дақиқа\n";
        $t .= "Радди худкор · " . (cfg('bank_reject', '1') === '1' ? '● фаъол' : '× хомӯш') . "\n\n";
        if ($rows) {
            $t .= "<code>───────────────</code>\nОхиринҳо:\n";
            foreach ($rows as $r2) {
                $t .= (!empty($r2['matched']) ? '⚡️' : '○') . ' '
                    . number_format((float)$r2['amount'], 2)
                    . (!empty($r2['comment']) ? ' · ' . h(mb_substr((string)$r2['comment'], 0, 18)) : '')
                    . ' · ' . date('d.m H:i', (int)$r2['created_at']) . "\n";
            }
        } else {
            $t .= "<i>Ҳанӯз уведомление нест.\nzpay.py-ро дар сервер оғоз кунед.</i>";
        }
        ed($chat, $mid, mb_substr($t, 0, 3800), [
            [['text' => '▶ Ҳозир санҷидан', 'callback_data' => 'a:bchk']],
            [['text' => cfg('bank_reject', '1') === '1' ? '× Радди худкорро хомӯш' : '● Радди худкор',
              'callback_data' => 'a:brej']],
            [['text' => '⏱ Мӯҳлати интизорӣ', 'callback_data' => 'a:set:bank_wait']],
            [['text' => '‹', 'callback_data' => 'a:menu']]]);
        toast($cb['id']); return;
    }

    if ($c === 'bchk') {
        toast($cb['id'], '...');
        $r = bank_recheck(50);
        ed($chat, $mid, "● <b>САНҶИШ ТАМОМ</b>\n<code>───────────────</code>\n"
            . "Тасдиқ шуд · <b>{$r['ok']}</b>\n"
            . "Рад шуд · <b>{$r['rej']}</b>",
            [[['text' => '‹', 'callback_data' => 'a:bank']]]);
        return;
    }

    if ($c === 'brej') {
        setcfg('bank_reject', cfg('bank_reject', '1') === '1' ? '0' : '1');
        admin_cb($cb, 'a:bank', $chat, $mid, $uid); return;
    }

    if ($c === 'tx') {
        ensure_tables();
        $rows = all("SELECT x.*, u.name, u.username FROM z_tx x
                     LEFT JOIN z_users u ON u.id=x.uid
                     ORDER BY x.id DESC LIMIT 25");
        $sIn  = (float)(one("SELECT COALESCE(SUM(amount),0) s FROM z_tx WHERE amount>0")['s'] ?? 0);
        $sOut = (float)(one("SELECT COALESCE(SUM(amount),0) s FROM z_tx WHERE amount<0")['s'] ?? 0);

        $t = "≡ <b>ТАЪРИХИ ҲАМЁН</b>\n<code>───────────────</code>\n"
           . "Ҳамагӣ дохил · <b>+" . money($sIn) . "</b>\n"
           . "Ҳамагӣ хароҷот · <b>−" . money(abs($sOut)) . "</b>\n"
           . "<code>───────────────</code>\n";

        if (!$rows) $t .= "\n<i>Ҳанӯз амалиёт нест.</i>";
        foreach ($rows as $r) {
            $s = (float)$r['amount'];
            $t .= ($s >= 0 ? '+' : '−') . " <b>" . money(abs($s)) . "</b> · "
                . h(mb_substr((string)($r['name'] ?? $r['uid']), 0, 16))
                . (!empty($r['username']) ? " @" . h($r['username']) : '') . "\n"
                . "<i>" . h(mb_substr((string)($r['title'] ?? ''), 0, 40)) . " · "
                . date('d.m H:i', (int)$r['created_at']) . "</i>\n";
        }
        ed($chat, $mid, mb_substr($t, 0, 3800), [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        toast($cb['id']); return;
    }

    if ($c === 'stuck') {
        $rep = stuck_report(900);   // кӯҳнатар аз 15 дақиқа
        if ($rep['count'] === 0) {
            ed($chat, $mid, "● <b>Заказҳои часпида нест.</b>\n<code>───────────────</code>\n"
                . "<i>Ҳама пул ё зачислено, ё аллакай баргардонида шудааст.</i>",
                [[['text' => '‹', 'callback_data' => 'a:menu']]]);
            toast($cb['id'], '● Тоза', true); return;
        }

        $t = "↩ <b>ПУЛИ ЧАСПИДА</b>\n<code>───────────────</code>\n"
           . "Заказҳои иҷронашуда · <b>{$rep['count']}</b>\n"
           . "Муштариён · <b>{$rep['users']}</b>\n"
           . "Ҳамагӣ баргардонида мешавад · <b>" . money($rep['sum']) . "</b>\n"
           . "<code>───────────────</code>\n";

        $show = array_slice($rep['rows'], 0, 15);
        foreach ($show as $o) {
            $t .= "#" . (int)$o['id'] . " · "
                . h(mb_substr((string)($o['name'] ?? $o['uid']), 0, 14))
                . (!empty($o['username']) ? " @" . h((string)$o['username']) : '')
                . " · <b>" . money((float)$o['price']) . "</b>\n"
                . "<i>" . h(mb_substr((string)$o['pack_name'], 0, 30)) . " · "
                . date('d.m H:i', (int)$o['created_at']) . "</i>\n";
        }
        if ($rep['count'] > 15) $t .= "<i>… ва боз " . ($rep['count'] - 15) . " заказ</i>\n";
        $t .= "\n<b>Пулро ба ҳамёни ин муштариён баргардонем?</b>";

        ed($chat, $mid, mb_substr($t, 0, 3900), [
            [['text' => "✓ Ҳа, {$rep['count']} заказро баргардон", 'callback_data' => 'a:stuckgo']],
            [['text' => '✕ Не', 'callback_data' => 'a:menu']],
        ]);
        toast($cb['id']); return;
    }

    if ($c === 'stuckgo') {
        toast($cb['id'], '↩ Коркард...', true);
        ed($chat, $mid, "↩ <b>Баргардонида истодаам...</b>\n<i>Каме сабр кунед.</i>");
        $r = refund_stuck(900, true);
        $t = "● <b>ТАМОМ</b>\n<code>───────────────</code>\n"
           . "Баргардонида шуд · <b>{$r['done']}</b> заказ\n"
           . "Маблағи умумӣ · <b>" . money($r['sum']) . "</b>\n"
           . "Ба муштариён хабар дода шуд · <b>{$r['notified']}</b>\n\n"
           . "<i>Пул ба ҳамёни ҳар кас гузошта шуд ва дар таърих сабт гардид.</i>";
        ed($chat, $mid, $t, [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        foreach (array_slice(admins_list(), 1) as $a) {
            try { say($a, "↩ <b>{$r['done']} заказ баргардонида шуд</b> · "
                . money($r['sum']) . " (аз ҷониби админ)"); } catch (Throwable $e) {}
        }
        return;
    }

    if ($c === 'rv') {
        ensure_tables();
        $tot = (int)(one("SELECT COUNT(*) c FROM z_reviews WHERE stars>0")['c'] ?? 0);
        $ask = (int)(one("SELECT COUNT(*) c FROM z_reviews WHERE stars=0")['c'] ?? 0);
        $pub = (int)(one("SELECT COUNT(*) c FROM z_reviews WHERE posted=1")['c'] ?? 0);
        $avg = (float)(one("SELECT AVG(stars) a FROM z_reviews WHERE stars>0")['a'] ?? 0);
        $ch  = rev_channel();

        // --- ТАШХИС: чаро шарҳ намеояд? ---
        $w = time() - 7 * 86400;
        $dn = (int)(one("SELECT COUNT(*) c FROM z_orders WHERE status='done' AND created_at > ?",
                        [$w])['c'] ?? 0);
        $nw = (int)(one("SELECT COUNT(*) c FROM z_orders WHERE status='new'")['c'] ?? 0);
        $miss = (int)(one("SELECT COUNT(*) c FROM z_orders o
                           LEFT JOIN z_reviews r ON r.order_id=o.id
                           WHERE o.status='done' AND r.id IS NULL AND o.done_at > ?",
                          [time() - 3 * 86400])['c'] ?? 0);

        $t  = "★ <b>ШАРҲҲО</b>\n<code>───────────────</code>\n";
        $t .= "Баҳо додаанд · <b>{$tot}</b>\n";
        $t .= "Пурсидем, ҷавоб нест · <b>{$ask}</b>\n";
        $t .= "Дар канал · <b>{$pub}</b>\n";
        $t .= "Баҳои миёна · <b>" . ($avg > 0 ? number_format($avg, 2) : '—') . "</b>\n";
        $t .= "<code>───────────────</code>\n";
        $t .= "Фармоиши иҷрошуда (7 рӯз) · <b>{$dn}</b>\n";
        $t .= "Фармоиши иҷронашуда · <b>{$nw}</b>\n";
        if ($miss > 0) $t .= "Шарҳ напурсидем · <b>{$miss}</b>\n";
        if ($dn === 0) {
            $t .= "\n<b>⚠︎ Дар 7 рӯз ягон фармоиш иҷро нашудааст.</b>\n"
                . "<i>Шарҳ танҳо баъди «● Иҷро шуд» пурсида мешавад.\n"
                . "Агар фармоишҳо дар ҳолати «○ Нав» монда бошанд —\n"
                . "провайдер ҷавоб намедиҳад, шарҳ ҳам намеояд.</i>\n";
        }
        $t .= "<code>───────────────</code>\n";
        $t .= "Канал · <b>" . ($ch !== '' ? h($ch) : '× танзим нашуда') . "</b>\n";
        $t .= "Аз чанд ситора мефиристем · <b>" . (int)cfg('rev_min', '4') . "+</b>\n";
        $t .= "Номи муштарӣ · <b>"
            . (cfg('rev_anon', '0') === '1' ? 'пинҳон' : 'нишон дода мешавад') . "</b>\n";
        $t .= "Пурсидани шарҳ · <b>" . (cfg('ask_rev', '1') === '1' ? 'ФАЪОЛ' : 'ХОМӮШ') . "</b>\n";

        if ($ch === '') {
            $t .= "\n<i>Каналро танзим кунед ва ботро дар он админ созед,\n"
                . "вагарна шарҳҳо фиристода намешаванд.</i>\n";
        }

        $last = all("SELECT r.*, u.name, u.username, o.game_name
                     FROM z_reviews r
                     LEFT JOIN z_users u ON u.id=r.uid
                     LEFT JOIN z_orders o ON o.id=r.order_id
                     WHERE r.stars > 0
                     ORDER BY r.id DESC LIMIT 6");
        if ($last) {
            $t .= "<code>───────────────</code>\n";
            foreach ($last as $r) {
                $t .= ((int)$r['posted'] === 1 ? '●' : '○') . ' '
                    . str_repeat('★', max(1, min(5, (int)$r['stars']))) . ' · '
                    . h(mb_substr((string)($r['name'] ?? $r['uid']), 0, 14))
                    . ' · #' . (int)$r['order_id'] . "\n";
                if (!empty($r['txt'])) {
                    $t .= '<i>' . h(mb_substr((string)$r['txt'], 0, 70)) . "</i>\n";
                }
            }
        }

        $kb = [
            [['text' => '✎ Канали шарҳҳо', 'callback_data' => 'a:rvch']],
            [['text' => '★ Ҳадди ақал: ' . (int)cfg('rev_min', '4'), 'callback_data' => 'a:rvmin'],
             ['text' => cfg('rev_anon', '0') === '1' ? '👤 Пинҳон' : '👤 Ошкор',
              'callback_data' => 'a:rvan']],
            [['text' => cfg('ask_rev', '1') === '1' ? '× Пурсиданро хомӯш' : '● Пурсиданро фаъол',
              'callback_data' => 'a:rvask']],
            [['text' => '⚡ Санҷиши канал', 'callback_data' => 'a:rvtest']],
            [['text' => '➤ Нафиристодаҳоро фиристодан', 'callback_data' => 'a:rvall']],
            [['text' => '☆ Шарҳ пурсидан (нав)', 'callback_data' => 'a:rvask2']],
            [['text' => '‹', 'callback_data' => 'a:menu']],
        ];
        ed($chat, $mid, mb_substr($t, 0, 3800), $kb);
        toast($cb['id']); return;
    }

    if ($c === 'rvch') {
        set_st($uid, 'a_rvch', []);
        say($chat, "✎ Канали шарҳҳоро нависед:\n"
            . "<code>@channel</code> ё <code>-1001234567890</code>\n\n"
            . "<i>«-» = холӣ кардан (он гоҳ канали фармоишҳо истифода мешавад)</i>\n"
            . "<b>Муҳим:</b> ботро дар канал админ кунед!");
        toast($cb['id']); return;
    }

    if ($c === 'rvmin') {
        $n = (int)cfg('rev_min', '4');
        $n = $n >= 5 ? 1 : $n + 1;
        setcfg('rev_min', (string)$n);
        admin_cb($cb, 'a:rv', $chat, $mid, $uid); return;
    }
    if ($c === 'rvan') {
        setcfg('rev_anon', cfg('rev_anon', '0') === '1' ? '0' : '1');
        admin_cb($cb, 'a:rv', $chat, $mid, $uid); return;
    }
    if ($c === 'rvask') {
        setcfg('ask_rev', cfg('ask_rev', '1') === '1' ? '0' : '1');
        admin_cb($cb, 'a:rv', $chat, $mid, $uid); return;
    }

    if ($c === 'rvtest') {
        $ch = rev_channel();
        if ($ch === '') {
            toast($cb['id'], '× Канал танзим нашудааст', true); return;
        }
        $r = tg('sendMessage', ['chat_id' => $ch, 'parse_mode' => 'HTML',
            'text' => "★★★★★\n<code>───────────────</code>\n"
                . "<i>Санҷиш — канали шарҳҳо кор мекунад.</i>\n"
                . "<code>───────────────</code>\n" . h(cfg('shop', 'ZVER TAJ'))]);
        say($chat, !empty($r['ok'])
            ? "● Канал <code>" . h($ch) . "</code> кор мекунад."
            : "× <b>НАШУД</b> · <code>" . h($ch) . "</code>\n"
              . "Сабаб · <code>" . h((string)($r['description'] ?? '?')) . "</code>\n\n"
              . "<i>Ботро ба канал админ кунед бо иҷозати «Фиристодани паём».</i>",
            [[['text' => '‹ Шарҳҳо', 'callback_data' => 'a:rv']]]);
        toast($cb['id'], !empty($r['ok']) ? '●' : '×', true); return;
    }

    if ($c === 'rvask2') {
        toast($cb['id'], '...');
        $n = ask_reviews_pending(20);
        say($chat, $n > 0
            ? "☆ Ба <b>$n</b> муштарӣ пурсиши шарҳ фиристода шуд."
            : "· Ҳамаи фармоишҳои иҷрошуда аллакай пурсида шудаанд\n"
              . "<i>(ё дар 3 рӯзи охир фармоиши иҷрошуда нест)</i>",
            [[['text' => '‹ Шарҳҳо', 'callback_data' => 'a:rv']]]);
        return;
    }

    if ($c === 'rvall') {
        toast($cb['id'], '...');
        $n = 0;
        foreach (all("SELECT order_id FROM z_reviews WHERE posted=0 AND stars>0
                      ORDER BY id DESC LIMIT 20") as $r) {
            if (post_review((int)$r['order_id'])) $n++;
            usleep(400000);
        }
        toast($cb['id'], "● $n фиристода шуд", true);
        admin_cb($cb, 'a:rv', $chat, $mid, $uid); return;
    }

    if (str_starts_with($c, 'rvp:')) {
        $oid = (int)substr($c, 4);
        $ok = post_review($oid, true);
        ed_any($chat, $mid, $ok ? "● Шарҳ ба канал фиристода шуд · #$oid"
                                : "× Нашуд — канал танзим нашудааст ё бот админ нест");
        toast($cb['id'], $ok ? '●' : '×', true); return;
    }

    if ($c === 'queue') {
        try {
            db()->exec("CREATE TABLE IF NOT EXISTS z_queue (
                id INT AUTO_INCREMENT PRIMARY KEY, order_id INT UNIQUE, uid BIGINT,
                tries INT DEFAULT 0, last_err VARCHAR(191) NULL, created_at INT,
                INDEX (uid)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
        } catch (Throwable $e) {}

        $rows = []; $sum = 0.0;
        try {
            $rows = all("SELECT q.*, o.game_name, o.pack_name, o.price, o.player_id
                         FROM z_queue q JOIN z_orders o ON o.id=q.order_id ORDER BY q.id LIMIT 12");
            $sum = (float)(one("SELECT COALESCE(SUM(o.price),0) s FROM z_queue q
                                JOIN z_orders o ON o.id=q.order_id")['s'] ?? 0);
        } catch (Throwable $e) {}
        $t = "⏳ <b>НАВБАТИ ФАРМОИШҲО</b>\n<code>───────────────</code>\n";
        if (!$rows) $t .= "<i>Навбат холӣ аст</i>";
        else {
            $t .= "Дар навбат · <b>" . queue_size() . "</b> фармоиш\n"
                . "Маблағ · <b>" . money($sum) . "</b>\n\n"
                . "<i>Баъди пур кардани баланси FazerCards\nхудкор иҷро мешаванд.</i>\n";
            foreach ($rows as $r) {
                $t .= "<code>───────────────</code>\n"
                    . "#" . (int)$r['order_id'] . " · " . h((string)$r['game_name']) . "\n"
                    . h((string)$r['pack_name']) . " · ID " . h((string)$r['player_id']) . "\n";
            }
        }
        ed($chat, $mid, mb_substr($t, 0, 3800), [
            [['text' => '▶ Ҳозир иҷро кардан', 'callback_data' => 'a:qrun']],
            [['text' => '🗑 Навбатро тоза кардан', 'callback_data' => 'a:qclr']],
            [['text' => '‹', 'callback_data' => 'a:menu']]]);
        toast($cb['id']); return;
    }

    if ($c === 'qrun') {
        toast($cb['id'], '...');
        ed($chat, $mid, "▶ Иҷро шуда истодааст...");
        [$d, $l] = queue_run(50);
        ed($chat, $mid, "● <b>НАВБАТ КОРКАРД ШУД</b>\n<code>───────────────</code>\n"
            . "Иҷро шуд · <b>$d</b>\nБоқӣ монд · <b>$l</b>"
            . ($l > 0 ? "\n\n<i>Баланси провайдер ҳанӯз кам аст.</i>" : ''),
            [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        return;
    }

    if ($c === 'qclr') {
        foreach (all("SELECT order_id FROM z_queue") as $r) {
            order_fail((int)$r['order_id'], $uid, 'Бекор карда шуд');
        }
        q("DELETE FROM z_queue");
        toast($cb['id'], 'Тоза шуд', true);
        admin_cb($cb, 'a:menu', $chat, $mid, $uid); return;
    }

    if ($c === 'bal') {
        toast($cb['id'], '...');
        $t = "<b>БАЛАНСИ FAZERCARDS</b>\n<code>───────────────</code>\n";
        $qs = 0;

        try {
            $r = fz('GET', '/balance');
            if (!empty($r['ok'])) {
                $bal = (float)str_replace(',', '.', (string)($r['balance'] ?? '0'));
                $t .= "💵 <b>" . number_format($bal, 2) . " "
                    . h((string)($r['currency'] ?? 'USD')) . "</b>\n"
                    . "≈ " . number_format($bal * (float)cfg('rate', '11'), 2) . " "
                    . h(cfg('cur', 'TJS')) . "\n";
            } else {
                $t .= "× " . h(fzerr($r)) . "\n";
            }
        } catch (Throwable $e) { $t .= "× хатои пайваст\n"; }

        try {
            $me = fz('GET', '/me');
            if (!empty($me['ok'])) {
                $t .= "<code>───────────────</code>\n"
                    . "Аккаунт · " . h((string)($me['login'] ?? '—')) . "\n"
                    . "Тариф · <b>" . h((string)($me['plan'] ?? '—')) . "</b>";
                if (!empty($me['planExpiresAt'])) {
                    $ts = strtotime((string)$me['planExpiresAt']);
                    if ($ts) {
                        $left = (int)ceil(($ts - time()) / 86400);
                        $t .= " · " . date('d.m.Y', $ts)
                            . ($left > 0 ? " ({$left} рӯз)" : " ⚠️");
                    }
                }
                $t .= "\n";
            }
        } catch (Throwable $e) {}

        try { $qs = queue_size(); } catch (Throwable $e) {}

        $t .= "<code>───────────────</code>\n"
            . "Фоида · " . h(cfg('markup', '20')) . "%\n"
            . "Курс · 1 USD = " . h(cfg('rate', '11')) . " " . h(cfg('cur', 'TJS')) . "\n"
            . "Худкор · " . (cfg('auto', '1') === '1' ? 'ФАЪОЛ ●' : 'хомӯш ×');
        if ($qs > 0) $t .= "\n\n⏳ <b>Дар навбат: {$qs} фармоиш</b>";

        $kb = [];
        if ($qs > 0) $kb[] = [['text' => '▶ Навбатро иҷро кардан', 'callback_data' => 'a:qtry']];
        $kb[] = [['text' => cfg('auto', '1') === '1' ? '× Худкорро хомӯш' : '● Худкор фаъол',
                  'callback_data' => 'a:auto']];
        $kb[] = [['text' => '‹', 'callback_data' => 'a:menu']];

        ed($chat, $mid, $t, $kb);
        return;
    }

    if ($c === 'qtry') {
        toast($cb['id'], '...');
        [$d, $l] = queue_run(50);
        toast($cb['id'], "● $d иҷро, $l монд", true);
        admin_cb($cb, 'a:bal', $chat, $mid, $uid); return;
    }

    if ($c === 'auto') {
        setcfg('auto', cfg('auto', '1') === '1' ? '0' : '1');
        admin_cb($cb, 'a:bal', $chat, $mid, $uid); return;
    }
    if ($c === 'sb') {
        setcfg('sandbox', cfg('sandbox', '0') === '1' ? '0' : '1');
        admin_cb($cb, 'a:bal', $chat, $mid, $uid); return;
    }

    if ($c === 'ord') {
        $rows = all("SELECT * FROM z_orders WHERE status='new' ORDER BY id LIMIT 8");
        if (!$rows) { ed($chat, $mid, "◆ Фармоиши нав нест.", [[['text' => '‹', 'callback_data' => 'a:menu']]]);
            toast($cb['id']); return; }
        foreach ($rows as $o) {
            say($chat, "<b>◆ #{$o['id']}</b>" . order_card($o), [
                [['text' => '● Иҷро шуд', 'callback_data' => 'ao:d:' . $o['id']],
                 ['text' => '× Нашуд', 'callback_data' => 'ao:f:' . $o['id']]],
                [['text' => '⌨ Код', 'callback_data' => 'ao:c:' . $o['id']]]]);
        }
        toast($cb['id']); return;
    }

    if ($c === 'tops') {
        // интизор + онҳое ки ИИ дар 24 соати охир рад кард (то ки дастӣ тасдиқ шаванд)
        $rows = all("SELECT t.*, u.name FROM z_topups t LEFT JOIN z_users u ON u.id=t.uid
                     WHERE t.status='pending'
                        OR (t.status='no' AND t.created_at > ?)
                     ORDER BY (t.status='pending') DESC, t.id DESC LIMIT 10",
                    [time() - 86400]);
        if (!$rows) { ed($chat, $mid, "◆ Дархости пур кардан нест.",
            [[['text' => '‹', 'callback_data' => 'a:menu']]]); toast($cb['id']); return; }

        ed($chat, $mid, "<b>ДАРХОСТҲОИ ПУР КАРДАН · " . count($rows) . "</b>\n"
            . "<code>───────────────</code>\n"
            . "<i>Радшудаҳо низ нишон дода мешаванд — метавонед дастӣ тасдиқ кунед.</i>",
            [[['text' => '‹', 'callback_data' => 'a:menu']]]);

        foreach ($rows as $t) {
            $rej = ($t['status'] === 'no');
            $cap = ($rej ? "🛑 <b>РАД ШУДА</b> · " : "⏳ ")
                 . "#{$t['id']} · " . h((string)$t['name']) . "\n"
                 . "<b>" . money((float)$t['amount']) . "</b>"
                 . (!empty($t['comment']) ? "\n<code>" . h((string)$t['comment']) . "</code>" : '')
                 . "\n" . date('d.m H:i', (int)$t['created_at']);

            $kb = $rej
                ? [[['text' => '● Ба ҳар ҳол тасдиқ', 'callback_data' => 'at:d:' . $t['id']]]]
                : [[['text' => '● Тасдиқ', 'callback_data' => 'at:d:' . $t['id']],
                    ['text' => '× Рад',    'callback_data' => 'at:f:' . $t['id']]]];

            if ($t['file_id']) {
                tg('sendPhoto', ['chat_id' => $chat, 'photo' => $t['file_id'],
                    'parse_mode' => 'HTML', 'caption' => $cap,
                    'reply_markup' => ['inline_keyboard' => $kb]]);
            } else {
                say($chat, $cap, $kb);
            }
        }
        toast($cb['id']); return;
    }

    /* ---- БОЗИҲО ---- */
    if ($c === 'games') {
        $rows = all("SELECT g.*, (SELECT COUNT(*) FROM z_packs p WHERE p.game_id=g.id) c
                     FROM z_games g ORDER BY g.sort DESC, g.id");
        $t = "<b>БОЗИҲО · " . count($rows) . "</b>\n";
        $kb = [];
        foreach ($rows as $g) {
            $t .= "<code>───────────────</code>\n"
                . ($g['active'] ? '●' : '○') . " <b>" . h($g['name']) . "</b> · "
                . (int)$g['c'] . " пакет\n";
            $kb[] = [['text' => ($g['active'] ? '● ' : '○ ') . mb_substr($g['name'], 0, 22),
                      'callback_data' => 'a:g:' . $g['id']]];
        }
        $kb[] = [['text' => '+ БОЗИИ НАВ', 'callback_data' => 'a:gadd']];
        $kb[] = [['text' => '‹', 'callback_data' => 'a:menu']];
        ed($chat, $mid, $t, $kb);
        toast($cb['id']); return;
    }

    if ($c === 'gadd') {
        set_st($uid, 'a_gadd', []);
        ed($chat, $mid, "<b>БОЗИИ НАВ</b>\n<code>───────────────</code>\n"
            . "Формат (бо |):\n\n<code>Ном | расм-URL | server(0/1)</code>\n\n"
            . "Мисол:\n<code>PUBG Mobile | https://site.com/pubg.jpg | 0</code>\n"
            . "<code>Mobile Legends | https://site.com/ml.jpg | 1</code>\n\n"
            . "<i>server=1 агар бозӣ Server ID талаб кунад</i>",
            [[['text' => '‹', 'callback_data' => 'a:games']]]);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'g:')) {
        $gid = (int)substr($c, 2);
        $g = one("SELECT * FROM z_games WHERE id=?", [$gid]);
        if (!$g) { toast($cb['id'], '×', true); return; }
        $cnt = (int)(one("SELECT COUNT(*) c FROM z_packs WHERE game_id=?", [$gid])['c'] ?? 0);
        $t  = "<b>" . h($g['name']) . "</b>\n<code>───────────────</code>\n";
        $t .= "Ҳолат · " . ($g['active'] ? '● фаъол' : '○ хомӯш') . "\n";
        $t .= "Server ID · " . ($g['need_server'] ? 'ҳа' : 'не') . "\n";
        $t .= "Пакетҳо · <b>$cnt</b>\n";
        if (!empty($g['image'])) $t .= "Расм · " . h(mb_substr($g['image'], 0, 60)) . "\n";
        ed($chat, $mid, $t, [
            [['text' => '+ Пакет', 'callback_data' => 'a:padd:' . $gid],
             ['text' => '▪ Пакетҳо', 'callback_data' => 'a:plist:' . $gid]],
            [['text' => $g['active'] ? '○ Хомӯш' : '● Фаъол', 'callback_data' => 'a:gtog:' . $gid],
             ['text' => '✎ Расм', 'callback_data' => 'a:gimg:' . $gid]],
            [['text' => '🗑 Нест кардан', 'callback_data' => 'a:gdel:' . $gid]],
            [['text' => '‹', 'callback_data' => 'a:games']]]);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'gtog:')) {
        $gid = (int)substr($c, 5);
        q("UPDATE z_games SET active=1-active WHERE id=?", [$gid]);
        admin_cb($cb, 'a:g:' . $gid, $chat, $mid, $uid); return;
    }
    if (str_starts_with($c, 'gdel:')) {
        $gid = (int)substr($c, 5);
        q("DELETE FROM z_packs WHERE game_id=?", [$gid]);
        q("DELETE FROM z_games WHERE id=?", [$gid]);
        toast($cb['id'], 'Нест шуд', true);
        admin_cb($cb, 'a:games', $chat, $mid, $uid); return;
    }
    if (str_starts_with($c, 'gimg:')) {
        $gid = (int)substr($c, 5);
        set_st($uid, 'a_gimg', ['gid' => $gid]);
        ed($chat, $mid, "URL-и расмро нависед (https://...):",
            [[['text' => '‹', 'callback_data' => 'a:g:' . $gid]]]);
        toast($cb['id']); return;
    }

    /* ---- ПАКЕТҲО ---- */
    if ($c === 'gp') {
        $rows = all("SELECT * FROM z_games ORDER BY sort DESC, id");
        if (!$rows) { ed($chat, $mid, "▪ Аввал бозӣ илова кунед.",
            [[['text' => '+ БОЗӢ', 'callback_data' => 'a:gadd']], [['text' => '‹', 'callback_data' => 'a:menu']]]);
            toast($cb['id']); return; }
        $kb = [];
        foreach ($rows as $g) $kb[] = [['text' => mb_substr($g['name'], 0, 26),
                                        'callback_data' => 'a:plist:' . $g['id']]];
        $kb[] = [['text' => '‹', 'callback_data' => 'a:menu']];
        ed($chat, $mid, "<b>ПАКЕТҲО</b>\nБозиро интихоб кунед:", $kb);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'plist:')) {
        $gid  = (int)substr($c, 6);
        $g    = one("SELECT * FROM z_games WHERE id=?", [$gid]);
        $rows = all("SELECT * FROM z_packs WHERE game_id=? ORDER BY sort DESC, price", [$gid]);
        $t = "<b>" . h($g['name'] ?? '') . " · пакетҳо</b>\n";
        $kb = [];
        foreach ($rows as $p) {
            $t .= "<code>───────────────</code>\n"
                . ($p['active'] ? '●' : '○') . " " . h($p['name']) . " · <b>"
                . money((float)$p['price']) . "</b>\n";
            $kb[] = [['text' => ($p['active'] ? '● ' : '○ ') . mb_substr($p['name'], 0, 18)
                              . ' · ' . number_format((float)$p['price'], 2),
                      'callback_data' => 'a:p:' . $p['id']]];
        }
        if (!$rows) $t .= "<i>Пакет нест</i>\n";
        $kb[] = [['text' => '+ ПАКЕТ', 'callback_data' => 'a:padd:' . $gid]];
        $kb[] = [['text' => '‹', 'callback_data' => 'a:g:' . $gid]];
        ed($chat, $mid, mb_substr($t, 0, 3800), $kb);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'padd:')) {
        $gid = (int)substr($c, 5);
        set_st($uid, 'a_padd', ['gid' => $gid]);
        ed($chat, $mid, "<b>ПАКЕТИ НАВ</b>\n<code>───────────────</code>\n"
            . "Як сатр = як пакет:\n\n<code>Ном | нарх</code>\n\n"
            . "Мисол (якчанд якбора):\n"
            . "<code>60 UC | 10\n325 UC | 45\n660 UC | 89</code>",
            [[['text' => '‹', 'callback_data' => 'a:plist:' . $gid]]]);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'p:')) {
        $pid = (int)substr($c, 2);
        $p = one("SELECT p.*, g.name gname FROM z_packs p JOIN z_games g ON g.id=p.game_id WHERE p.id=?",
                 [$pid]);
        if (!$p) { toast($cb['id'], '×', true); return; }
        ed($chat, $mid, "<b>" . h($p['name']) . "</b>\n<code>───────────────</code>\n"
            . "Бозӣ · " . h($p['gname']) . "\n"
            . "Нарх · <b>" . money((float)$p['price']) . "</b>\n"
            . "Ҳолат · " . ($p['active'] ? '● фаъол' : '○ хомӯш'), [
            [['text' => '✎ Нарх', 'callback_data' => 'a:pprice:' . $pid],
             ['text' => $p['active'] ? '○ Хомӯш' : '● Фаъол', 'callback_data' => 'a:ptog:' . $pid]],
            [['text' => '🗑 Нест кардан', 'callback_data' => 'a:pdel:' . $pid]],
            [['text' => '‹', 'callback_data' => 'a:plist:' . $p['game_id']]]]);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'ptog:')) {
        $pid = (int)substr($c, 5);
        q("UPDATE z_packs SET active=1-active WHERE id=?", [$pid]);
        admin_cb($cb, 'a:p:' . $pid, $chat, $mid, $uid); return;
    }
    if (str_starts_with($c, 'pdel:')) {
        $pid = (int)substr($c, 5);
        $p = one("SELECT game_id FROM z_packs WHERE id=?", [$pid]);
        q("DELETE FROM z_packs WHERE id=?", [$pid]);
        toast($cb['id'], 'Нест шуд', true);
        admin_cb($cb, 'a:plist:' . (int)($p['game_id'] ?? 0), $chat, $mid, $uid); return;
    }
    if (str_starts_with($c, 'pprice:')) {
        $pid = (int)substr($c, 7);
        set_st($uid, 'a_pprice', ['pid' => $pid]);
        ed($chat, $mid, "Нархи навро нависед:", [[['text' => '‹', 'callback_data' => 'a:p:' . $pid]]]);
        toast($cb['id']); return;
    }

    /* ---- РЕКВИЗИТҲО ---- */
    if ($c === 'req') {
        $rows = all("SELECT * FROM z_reqs ORDER BY sort DESC, id");
        $t = "<b>РЕКВИЗИТҲО</b>\n";
        $kb = [];
        foreach ($rows as $r) {
            $t .= "<code>───────────────</code>\n"
                . ($r['active'] ? '●' : '○') . " <b>" . h($r['bank']) . "</b>\n"
                . h($r['owner']) . "\n<code>" . h($r['number']) . "</code>\n";
            $kb[] = [['text' => ($r['active'] ? '● ' : '○ ') . mb_substr($r['bank'], 0, 20),
                      'callback_data' => 'a:rq:' . $r['id']]];
        }
        if (!$rows) $t .= "<i>Реквизит нест</i>\n";
        $kb[] = [['text' => '+ РЕКВИЗИТ', 'callback_data' => 'a:rqadd']];
        $kb[] = [['text' => '‹', 'callback_data' => 'a:menu']];
        ed($chat, $mid, $t, $kb);
        toast($cb['id']); return;
    }
    if ($c === 'rqadd') {
        set_st($uid, 'rq_bank', []);
        ed($chat, $mid, "<b>РЕКВИЗИТИ НАВ</b>\n<code>───────────────</code>\n"
            . "<b>Қадами 1 аз 5</b>\n\n"
            . "Номи бонкро нависед:\n\n"
            . "<i>Мисол: DC Next · Алиф Бонк · Эсхата</i>",
            [[['text' => '× Бекор', 'callback_data' => 'a:req']]]);
        toast($cb['id']); return;
    }

    if ($c === 'rqskip') {
        $stx = get_st($uid);
        $d = $stx['data'];
        set_st($uid, 'rq_name', $d);
        ed($chat, $mid, "<b>" . h((string)($d['bank'] ?? '')) . "</b>\n"
            . "<code>───────────────</code>\n<b>Қадами 3 аз 5</b>\n\n"
            . "Ном ва насабро нависед:\n\n<i>Мисол: Алиҷон Раҳмонов</i>",
            [[['text' => '× Бекор', 'callback_data' => 'a:req']]]);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'rqkind:')) {
        $kind = substr($c, 7) === 'phone' ? 'phone' : 'card';
        $stx = get_st($uid);
        $d = $stx['data'];
        $d['kind'] = $kind;
        set_st($uid, 'rq_num', $d);
        ed($chat, $mid, "<b>" . h((string)($d['bank'] ?? '')) . "</b>\n"
            . "<code>───────────────</code>\n<b>Қадами 5 аз 5</b>\n\n"
            . ($kind === 'phone'
                ? "📱 Рақами телефонро нависед:\n\n<i>900112233 ё +992900112233</i>"
                : "💳 Рақами кортро нависед:\n\n<i>9762000172118035</i>"),
            [[['text' => '× Бекор', 'callback_data' => 'a:req']]]);
        toast($cb['id']); return;
    }
    if (str_starts_with($c, 'rq:')) {
        $rid = (int)substr($c, 3);
        $r = one("SELECT * FROM z_reqs WHERE id=?", [$rid]);
        if (!$r) { toast($cb['id'], '×', true); return; }
        ed($chat, $mid, "<b>" . h($r['bank']) . "</b>\n<code>───────────────</code>\n"
            . "Ном · " . h((string)($r['fname'] ?? '')) . "\n"
            . "Насаб · " . h((string)($r['lname'] ?? '')) . "\n"
            . "Рақам · <code>" . h($r['number']) . "</code>\n"
            . "Навъ · " . h($r['kind']) . "\n"
            . "Линк · " . (!empty($r['pay_url']) ? '✓ ҳаст' : '—') . "\n"
            . "Ҳолат · " . ($r['active'] ? '● фаъол' : '○ хомӯш'), [
            [['text' => '🔗 Линки пардохт', 'callback_data' => 'a:rqurl:' . $rid]],
            [['text' => '✎ Ном', 'callback_data' => 'a:rqname:' . $rid],
             ['text' => '✎ Рақам', 'callback_data' => 'a:rqnum:' . $rid]],
            [['text' => $r['active'] ? '○ Хомӯш' : '● Фаъол', 'callback_data' => 'a:rqtog:' . $rid],
             ['text' => '🗑', 'callback_data' => 'a:rqdel:' . $rid]],
            [['text' => '‹', 'callback_data' => 'a:req']]]);
        toast($cb['id']); return;
    }
    if (str_starts_with($c, 'rqurl:')) {
        $rid = (int)substr($c, 6);
        $r = one("SELECT * FROM z_reqs WHERE id=?", [$rid]);
        set_st($uid, 'a_rqurl', ['id' => $rid]);
        ed($chat, $mid, "🔗 <b>ЛИНКИ ПАРДОХТ</b>\n<code>───────────────</code>\n"
            . "Ҳозир: " . (!empty($r['pay_url'])
                ? "<code>" . h(mb_substr((string)$r['pay_url'], 0, 120)) . "</code>" : '—') . "\n\n"
            . "<b>Душанбе Сити / ExpressPay:</b>\n"
            . "<code>http://pay.expresspay.tj/?A=" . h((string)$r['number'])
            . "&s={SUM}&c=&f1=133&FIELD2=&FIELD3=</code>\n\n"
            . "<i>{SUM} — маблағ\n{ID} — рақами дархост (TOP12)\n"
            . "{NICK} — ники муштарӣ\n{COMMENT} — ник + рақам</i>\n\n"
            . "Барои нест кардан: <code>-</code>",
            [[['text' => '‹', 'callback_data' => 'a:rq:' . $rid]]]);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'rqname:')) {
        $rid = (int)substr($c, 7);
        set_st($uid, 'a_rqname', ['id' => $rid]);
        ed($chat, $mid, "✎ Ном ва насаб:\n<code>Алиҷон | Раҳмонов</code>",
            [[['text' => '‹', 'callback_data' => 'a:rq:' . $rid]]]);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'rqnum:')) {
        $rid = (int)substr($c, 6);
        set_st($uid, 'a_rqnum', ['id' => $rid]);
        ed($chat, $mid, "✎ Рақами нав:", [[['text' => '‹', 'callback_data' => 'a:rq:' . $rid]]]);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'rqtog:')) {
        q("UPDATE z_reqs SET active=1-active WHERE id=?", [(int)substr($c, 6)]);
        admin_cb($cb, 'a:req', $chat, $mid, $uid); return;
    }
    if (str_starts_with($c, 'rqdel:')) {
        q("DELETE FROM z_reqs WHERE id=?", [(int)substr($c, 6)]);
        toast($cb['id'], 'Нест шуд', true);
        admin_cb($cb, 'a:req', $chat, $mid, $uid); return;
    }

    /* ---- ОП-КАНАЛҲО (обунаи ҳатмӣ) ---- */
    if ($c === 'subs') {
        $rows = subs_list(false);
        $t = "📢 <b>ОП-КАНАЛҲО</b>\n<code>───────────────</code>\n"
           . "Каналҳое ки муштарӣ бояд обуна шавад,\nто бот кор кунад.\n\n";
        $kb = [];
        foreach ($rows as $r) {
            $tt = trim((string)$r['title']) !== '' ? (string)$r['title'] : (string)$r['chat'];
            $kb[] = [['text' => ($r['active'] ? '● ' : '○ ') . mb_substr($tt, 0, 30),
                      'callback_data' => 'a:sub:' . $r['id']]];
        }
        if (!$rows) $t .= "<i>Ҳоло ягон канал нест.\nБот озод кор мекунад.</i>\n";
        else $t .= "● фаъол · ○ хомӯш\n<i>Барои идора — пахш кунед.</i>\n";
        $kb[] = [['text' => '+ КАНАЛ ИЛОВА КАРДАН', 'callback_data' => 'a:subadd']];
        $kb[] = [['text' => '‹', 'callback_data' => 'a:menu']];
        ed($chat, $mid, $t, $kb);
        toast($cb['id']); return;
    }
    if ($c === 'subadd') {
        set_st($uid, 'sub_chat', []);
        ed($chat, $mid, "📢 <b>КАНАЛИ НАВ</b>\n<code>───────────────</code>\n"
            . "<b>Қадами 1 аз 2</b>\n\n"
            . "Каналро нависед — @username ё ссылка:\n\n"
            . "<i>Мисол: @zvertaj\nё https://t.me/zvertaj\nё барои канали пӯшида: -1001234567890</i>\n\n"
            . "⚠️ <b>Муҳим:</b> ботро ба он канал <b>админ</b> кунед,\n"
            . "вагарна санҷиши обуна кор намекунад.",
            [[['text' => '× Бекор', 'callback_data' => 'a:subs']]]);
        toast($cb['id']); return;
    }
    if (str_starts_with($c, 'sub:')) {
        $sid = (int)substr($c, 4);
        $r = one("SELECT * FROM z_subs WHERE id=?", [$sid]);
        if (!$r) { toast($cb['id'], '×', true); return; }
        $chk = sub_norm((string)$r['chat']);
        $t = "📢 <b>" . h((string)($r['title'] ?: $r['chat'])) . "</b>\n<code>───────────────</code>\n"
           . "Канал · <code>" . h((string)$r['chat']) . "</code>\n"
           . "Тугма · " . h((string)($r['title'] ?: '—')) . "\n"
           . "Ссылка · " . (!empty($r['link']) ? '✓ дастӣ' : 'худкор') . "\n"
           . "Ҳолат · " . ($r['active'] ? '● фаъол' : '○ хомӯш') . "\n";
        if ($chk === '') $t .= "\n⚠️ <i>Ин ссылкаи даъватист — санҷиши обуна\nкор намекунад. @username лозим аст.</i>\n";
        ed($chat, $mid, $t, [
            [['text' => '✎ Номи тугма', 'callback_data' => 'a:subttl:' . $sid]],
            [['text' => '🔗 Ссылкаи дастӣ', 'callback_data' => 'a:sublink:' . $sid]],
            [['text' => $r['active'] ? '○ Хомӯш кардан' : '● Фаъол кардан', 'callback_data' => 'a:subtog:' . $sid],
             ['text' => '🗑 Нест', 'callback_data' => 'a:subdel:' . $sid]],
            [['text' => '🧪 Санҷиш', 'callback_data' => 'a:subtest:' . $sid]],
            [['text' => '‹', 'callback_data' => 'a:subs']]]);
        toast($cb['id']); return;
    }
    if (str_starts_with($c, 'subttl:')) {
        $sid = (int)substr($c, 7);
        set_st($uid, 'a_subttl', ['id' => $sid]);
        ed($chat, $mid, "✎ Номи тугмаро нависед:\n\n<i>Мисол: Канали мо · ZVER TAJ · Новости</i>",
            [[['text' => '‹', 'callback_data' => 'a:sub:' . $sid]]]);
        toast($cb['id']); return;
    }
    if (str_starts_with($c, 'sublink:')) {
        $sid = (int)substr($c, 8);
        set_st($uid, 'a_sublink', ['id' => $sid]);
        ed($chat, $mid, "🔗 Ссылкаи дастиро нависед (барои тугма):\n\n"
            . "<i>Мисол: https://t.me/+AbCdEf12345\n(барои каналҳои пӯшида)</i>\n\n"
            . "Барои нест кардан: <code>-</code>",
            [[['text' => '‹', 'callback_data' => 'a:sub:' . $sid]]]);
        toast($cb['id']); return;
    }
    if (str_starts_with($c, 'subtog:')) {
        q("UPDATE z_subs SET active=1-active WHERE id=?", [(int)substr($c, 7)]);
        admin_cb($cb, 'a:subs', $chat, $mid, $uid); return;
    }
    if (str_starts_with($c, 'subdel:')) {
        q("DELETE FROM z_subs WHERE id=?", [(int)substr($c, 7)]);
        toast($cb['id'], 'Нест шуд', true);
        admin_cb($cb, 'a:subs', $chat, $mid, $uid); return;
    }
    if (str_starts_with($c, 'subtest:')) {
        $sid = (int)substr($c, 8);
        $r = one("SELECT * FROM z_subs WHERE id=?", [$sid]);
        $chat_id = sub_norm((string)($r['chat'] ?? ''));
        if ($chat_id === '') { toast($cb['id'], '⚠️ @username лозим', true); return; }
        $res = tg('getChat', ['chat_id' => $chat_id]);
        if (!empty($res['ok'])) {
            $me = tg('getChatMember', ['chat_id' => $chat_id, 'user_id' => $uid]);
            $st = (string)($me['result']['status'] ?? '?');
            toast($cb['id'], '✓ Канал ёфт шуд · шумо: ' . $st, true);
        } else {
            toast($cb['id'], '× Бот ба канал админ нест ё канал нодуруст', true);
        }
        return;
    }

    /* ---- КОРБАРОН ---- */
    if (str_starts_with($c, 'usr:')) {
        $pg = (int)substr($c, 4); $per = 8;
        $tot = (int)(one("SELECT COUNT(*) c FROM z_users")['c'] ?? 0);
        $sum = one("SELECT COALESCE(SUM(balance),0) s FROM z_users")['s'] ?? 0;
        $rows = all("SELECT * FROM z_users ORDER BY seen_at DESC LIMIT $per OFFSET " . ($pg * $per));
        $t = "<b>КОРБАРОН · $tot</b>\n<code>───────────────</code>\n"
           . "Дар ҳамёнҳо · <b>" . money((float)$sum) . "</b>\n";
        $kb = [];
        foreach ($rows as $u) {
            $nm = mb_substr($u['name'] ?: (string)$u['id'], 0, 16);
            if (!empty($u['username'])) $nm .= ' @' . mb_substr($u['username'], 0, 12);
            $kb[] = [['text' => ((int)$u['blocked'] ? '× ' : '') . $nm . ' · '
                              . number_format((float)$u['balance'], 0),
                      'callback_data' => 'a:u:' . $u['id']]];
        }
        $pages = max(1, (int)ceil($tot / $per));
        $nav = [];
        if ($pg > 0) $nav[] = ['text' => '‹', 'callback_data' => 'a:usr:' . ($pg - 1)];
        $nav[] = ['text' => ($pg + 1) . '/' . $pages, 'callback_data' => 'noop'];
        if ($pg < $pages - 1) $nav[] = ['text' => '›', 'callback_data' => 'a:usr:' . ($pg + 1)];
        $kb[] = $nav;
        $kb[] = [['text' => '‹ Меню', 'callback_data' => 'a:menu']];
        ed($chat, $mid, $t, $kb);
        toast($cb['id']); return;
    }

    if (str_starts_with($c, 'u:')) {
        $tid = (int)substr($c, 2);
        $u = one("SELECT * FROM z_users WHERE id=?", [$tid]);
        if (!$u) { toast($cb['id'], '×', true); return; }
        ed($chat, $mid, user_card($u), user_kb($tid, (int)$u['blocked'] === 1));
        toast($cb['id']); return;
    }
    if (str_starts_with($c, 'ublk:')) {
        $tid = (int)substr($c, 5);
        q("UPDATE z_users SET blocked=1-blocked WHERE id=?", [$tid]);
        admin_cb($cb, 'a:u:' . $tid, $chat, $mid, $uid); return;
    }
    if (str_starts_with($c, 'ubal:')) {
        [, $sg, $tid] = array_pad(explode(':', $c), 3, '');
        set_st($uid, 'a_bal', ['tid' => (int)$tid, 'sg' => $sg]);
        ed($chat, $mid, ($sg === 'p' ? '+ Илова кардан' : '− Кам кардан') . "\nМаблағро нависед:",
            [[['text' => '‹', 'callback_data' => 'a:u:' . $tid]]]);
        toast($cb['id']); return;
    }

    /* ---- ОМОР ---- */
    if ($c === 'stat') {
        $u  = one("SELECT COUNT(*) c, COALESCE(SUM(balance),0) b FROM z_users");
        $o  = one("SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM z_orders WHERE status='done'");
        $nw = (int)(one("SELECT COUNT(*) c FROM z_orders WHERE status='new'")['c'] ?? 0);
        $td = one("SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM z_orders
                   WHERE status='done' AND created_at>?", [strtotime('today')]);
        $tp = one("SELECT COALESCE(SUM(amount),0) s FROM z_topups WHERE status='ok'");
        $t  = "<b>ОМОР</b>\n<code>───────────────</code>\n";
        $t .= "Корбарон · <b>" . (int)($u['c'] ?? 0) . "</b>\n";
        $t .= "Дар ҳамёнҳо · <b>" . money((float)($u['b'] ?? 0)) . "</b>\n";
        $t .= "<code>───────────────</code>\n";
        $t .= "Фармоишҳо · <b>" . (int)($o['c'] ?? 0) . "</b>\n";
        $t .= "Фурӯш · <b>" . money((float)($o['s'] ?? 0)) . "</b>\n";
        $t .= "Интизор · <b>$nw</b>\n";
        $t .= "<code>───────────────</code>\n";
        $t .= "Имрӯз · <b>" . (int)($td['c'] ?? 0) . "</b> фармоиш · "
            . money((float)($td['s'] ?? 0)) . "\n";
        $t .= "Пур карданҳо · <b>" . money((float)($tp['s'] ?? 0)) . "</b>";
        ed($chat, $mid, $t, [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        toast($cb['id']); return;
    }

    /* ---- ЭЪЛОН ---- */
    if ($c === 'bc') {
        set_st($uid, 'a_bc', []);
        ed($chat, $mid, "<b>ЭЪЛОН</b>\nМатнро нависед:",
            [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        toast($cb['id']); return;
    }
    if ($c === 'bcgo') {
        $txt = cfg('bc_draft', '');
        if ($txt === '') { toast($cb['id'], 'Матн нест', true); return; }
        $users = all("SELECT id FROM z_users WHERE blocked=0");
        $tot = count($users); $ok = 0; $i = 0; $last = time();
        $t0 = time(); $stopped = false;
        @set_time_limit(0);
        ed($chat, $mid, "▸ Фиристода истодаам... 0 / $tot");
        foreach ($users as $u) {
            $i++;
            // ҲИМОЯ: хатои як корбар тамоми эъдонро наафтонад
            try {
                $r = say($u['id'], $txt, [[['text' => T('app', $u['id']), 'web_app' => ['url' => app_url()]]]]);
                if (!empty($r['ok'])) $ok++;
            } catch (Throwable $e) { /* ин корбарро мегузарем */ }
            if (time() - $last >= 4) { $last = time(); ed($chat, $mid, "▸ $i / $tot · ● $ok"); }
            // ҳимоя аз таймаути хостинг (25 дақ) — бас мекунем ва хабар медиҳем
            if (time() - $t0 > 1500) { $stopped = true; break; }
            usleep(60000);
        }
        setcfg('bc_draft', '');
        ed($chat, $mid, "<b>● ЭЪЛОН " . ($stopped ? 'ҚИСМАН' : 'ТАМОМ') . "</b>\nРасид · <b>$ok</b> / $tot"
            . ($stopped ? "\n<i>Вақт тамом шуд — $i корбар коркард шуд</i>" : ''),
            [[['text' => '‹', 'callback_data' => 'a:menu']]]);
        return;
    }

    /* ---- ТАНЗИМОТ ---- */
    if ($c === 'cfg') {
        $t  = "<b>ТАНЗИМОТ</b>\n<code>───────────────</code>\n";
        $t .= "Ном · <b>" . h(cfg('shop', '')) . "</b>\n";
        $t .= "Асъор · <b>" . h(cfg('cur', '')) . "</b>\n";
        $t .= "Дастгирӣ TG · " . h(cfg('support', '')) . "\n";
        $t .= "WhatsApp · " . (cfg('wa', '') !== '' ? '+' . h(cfg('wa')) : '—') . "\n";
        $t .= "Канал · " . (cfg('channel', '') !== '' ? h(cfg('channel')) : '—') . "\n";
        $t .= "Обунаи ҳатмӣ · " . count(subs_list(true)) . " канал\n";
        $t .= "Шарҳҳо · " . (cfg('reviews', '') !== '' ? h(cfg('reviews')) : '—') . "\n";
        $t .= "Бонуси даъват · <b>" . money((float)cfg('ref_bonus', '0.50')) . "</b>\n";
        $t .= "Фоида · <b>" . cfg('markup') . "%</b>\n";
        $t .= "Курс · <b>1 USD = " . cfg('rate') . "</b>\n";
        $t .= "Огоҳии баланс · <b>" . cfg('lowbal', '5') . " USD</b>\n";
        $t .= "Шаблони линк · " . (cfg('pay_tpl', '') !== '' ? '✓ ҳаст' : '—');
        ed($chat, $mid, $t, [
            [['text' => 'Ном', 'callback_data' => 'a:set:shop'],
             ['text' => 'Асъор', 'callback_data' => 'a:set:cur']],
            [['text' => 'Дастгирӣ TG', 'callback_data' => 'a:set:support'],
             ['text' => 'WhatsApp', 'callback_data' => 'a:set:wa']],
            [['text' => 'Бонус', 'callback_data' => 'a:set:ref_bonus']],
            [['text' => 'Фоида %', 'callback_data' => 'a:set:markup'],
             ['text' => 'Курс', 'callback_data' => 'a:set:rate']],
            [['text' => 'Канали фармоишҳо', 'callback_data' => 'a:set:channel']],
            [['text' => '🔒 Канали обуна (ҳатмӣ)', 'callback_data' => 'a:set:sub_ch']],
            [['text' => 'Канали шарҳҳо', 'callback_data' => 'a:set:reviews']],
            [['text' => 'TOP бозиҳо', 'callback_data' => 'a:set:top']],
            [['text' => 'Онлайн +', 'callback_data' => 'a:set:live_base'],
             ['text' => 'Фармоишҳо +', 'callback_data' => 'a:set:live_add']],
            [['text' => '🔗 Шаблони линки пардохт', 'callback_data' => 'a:set:pay_tpl']],
            [['text' => 'Ҳадди огоҳии баланс', 'callback_data' => 'a:set:lowbal']],
            [['text' => 'Матни хуш омадед', 'callback_data' => 'a:set:welcome']],
            [['text' => '‹', 'callback_data' => 'a:menu']]]);
        toast($cb['id']); return;
    }
    if (str_starts_with($c, 'set:')) {
        $k = substr($c, 4);
        set_st($uid, 'a_set', ['k' => $k]);
        ed($chat, $mid, "Қимати навро нависед:\n\nҲозир · <code>" . h(cfg($k, '—')) . "</code>\n\n"
            . "<i>«-» = холӣ кардан</i>", [[['text' => '‹', 'callback_data' => 'a:cfg']]]);
        toast($cb['id']); return;
    }

    toast($cb['id']);
}

function user_card(array $u): string {
    $t  = "<b>" . h($u['name'] ?: 'Корбар') . "</b>";
    if ((int)$u['blocked'] === 1) $t .= " · <b>× БАСТА</b>";
    $t .= "\n<code>───────────────</code>\n";
    if (!empty($u['username'])) $t .= "@" . h($u['username']) . "\n";
    if (!empty($u['phone']))    $t .= "<code>" . h($u['phone']) . "</code>\n";
    $t .= "ID · <code>" . $u['id'] . "</code>\n";
    $t .= "<code>───────────────</code>\n";
    $t .= "Баланс · <b>" . money((float)$u['balance']) . "</b>\n";
    $t .= "Хароҷот · " . money((float)$u['spent']) . "\n";
    $t .= "Фармоишҳо · <b>" . (int)$u['orders_cnt'] . "</b>\n";
    $t .= "Дӯстон · " . (int)$u['ref_cnt'] . " · " . money((float)$u['ref_sum']) . "\n";
    $t .= "Охирин · " . date('d.m.Y H:i', (int)$u['seen_at']) . "\n";
    $rows = all("SELECT pack_name,price,status,created_at FROM z_orders WHERE uid=? ORDER BY id DESC LIMIT 5",
                [$u['id']]);
    if ($rows) {
        $ic = ['new' => '○', 'done' => '●', 'fail' => '×', 'refund' => '↩'];
        $t .= "<code>───────────────</code>\n";
        foreach ($rows as $o) {
            $t .= ($ic[$o['status']] ?? '·') . ' ' . h(mb_substr($o['pack_name'], 0, 20))
                . ' · ' . money((float)$o['price']) . ' · ' . date('d.m', (int)$o['created_at']) . "\n";
        }
    }
    return $t;
}
function user_kb($id, bool $blk): array {
    return [
        [['text' => '+ Илова', 'callback_data' => 'a:ubal:p:' . $id],
         ['text' => '− Кам', 'callback_data' => 'a:ubal:m:' . $id]],
        [['text' => $blk ? '● Кушодан' : '× Бастан', 'callback_data' => 'a:ublk:' . $id]],
        [['text' => '‹ Рӯйхат', 'callback_data' => 'a:usr:0']],
    ];
}

function admin_input($chat, $uid, array $st, string $text): void {
    $s = $st['st']; $d = $st['data']; $text = trim($text);

    if ($s === 'a_gadd') {
        $p = array_map('trim', explode('|', $text));
        if (count($p) < 1 || $p[0] === '') { say($chat, '× Ном холӣ'); return; }
        $img = $p[1] ?? '';
        if ($img !== '' && !preg_match('~^https://~i', $img)) $img = '';
        q("INSERT INTO z_games (name,image,need_server,active,created_at) VALUES (?,?,?,1,?)",
          [mb_substr($p[0], 0, 110), $img !== '' ? $img : null,
           (int)(($p[2] ?? '0') === '1'), time()]);
        $gid = (int)db()->lastInsertId();
        clr_st($uid);
        say($chat, "● Бозӣ илова шуд · <b>" . h($p[0]) . "</b>",
            [[['text' => '+ Пакет', 'callback_data' => 'a:padd:' . $gid]],
             [['text' => '‹ Бозиҳо', 'callback_data' => 'a:games']]]);
        return;
    }

    if ($s === 'a_gimg') {
        if (!preg_match('~^https://~i', $text)) { say($chat, '× URL бояд https:// бошад'); return; }
        q("UPDATE z_games SET image=? WHERE id=?", [mb_substr($text, 0, 250), (int)$d['gid']]);
        clr_st($uid);
        say($chat, '● Расм иваз шуд', [[['text' => '‹', 'callback_data' => 'a:g:' . (int)$d['gid']]]]);
        return;
    }

    if ($s === 'a_padd') {
        $gid = (int)$d['gid']; $n = 0;
        foreach (explode("\n", $text) as $line) {
            $p = array_map('trim', explode('|', $line));
            if (count($p) < 2 || $p[0] === '') continue;
            $price = round((float)str_replace(',', '.', $p[1]), 2);
            if ($price <= 0) continue;
            q("INSERT INTO z_packs (game_id,name,price,active) VALUES (?,?,?,1)",
              [$gid, mb_substr($p[0], 0, 110), $price]);
            $n++;
        }
        clr_st($uid);
        say($chat, $n ? "● Илова шуд · <b>$n</b> пакет" : '× Ҳеҷ чиз илова нашуд',
            [[['text' => '▪ Пакетҳо', 'callback_data' => 'a:plist:' . $gid]],
             [['text' => '+ Боз', 'callback_data' => 'a:padd:' . $gid]]]);
        return;
    }

    if ($s === 'a_pprice') {
        $v = round((float)str_replace(',', '.', $text), 2);
        if ($v <= 0) { say($chat, '× Нарх нодуруст'); return; }
        q("UPDATE z_packs SET price=? WHERE id=?", [$v, (int)$d['pid']]);
        clr_st($uid);
        say($chat, '● Нарх · <b>' . money($v) . '</b>',
            [[['text' => '‹', 'callback_data' => 'a:p:' . (int)$d['pid']]]]);
        return;
    }

    if ($s === 'a_pradd') {
        $p = array_map('trim', explode('|', $text));
        clr_st($uid);
        $code = mb_strtoupper(preg_replace('~[^A-Za-z0-9_-]~', '', $p[0] ?? ''));
        if ($code === '' || mb_strlen($code) < 3) { say($chat, '× Рамз кӯтоҳ аст'); return; }
        if (one("SELECT id FROM z_promo WHERE code=?", [$code])) {
            say($chat, '× Чунин рамз аллакай ҳаст'); return;
        }
        $raw = trim($p[1] ?? '');
        $kind = str_contains($raw, '%') ? 'pct' : 'fix';
        $val = (float)str_replace([',', '%', ' '], ['.', '', ''], $raw);
        if ($val <= 0) { say($chat, '× Тахфиф нодуруст'); return; }
        if ($kind === 'pct' && $val > 90) { say($chat, '× Ҳадди аксар 90%'); return; }

        q("INSERT INTO z_promo (code,kind,val,min_sum,max_uses,per_user,active,created_at)
           VALUES (?,?,?,?,?,?,1,?)",
          [$code, $kind, $val,
           round((float)str_replace(',', '.', $p[2] ?? '0'), 2),
           (int)($p[3] ?? 0), (int)($p[4] ?? 1), time()]);

        $d = $kind === 'fix' ? money($val) : rtrim(rtrim(number_format($val, 2, '.', ''), '0'), '.') . '%';
        say($chat, "● <b>ПРОМОКОД СОХТА ШУД</b>\n<code>───────────────</code>\n"
            . "<code>$code</code> · <b>−$d</b>\n\n"
            . "Барои муштариён фиристед — онҳо дар барнома ворид мекунанд.",
            [[['text' => '🎟 Промокодҳо', 'callback_data' => 'a:pr']]]);
        return;
    }

    if ($s === 'a_rqurl') {
        $rid = (int)$d['id'];
        clr_st($uid);
        $v = trim($text);
        if ($v === '-' || $v === '') {
            q("UPDATE z_reqs SET pay_url=NULL WHERE id=?", [$rid]);
            say($chat, "● Линк нест шуд", [[['text' => '‹', 'callback_data' => 'a:rq:' . $rid]]]);
            return;
        }
        if (!preg_match('~^https?://~i', $v)) { say($chat, "× Линк бояд бо https:// сар шавад"); return; }
        q("UPDATE z_reqs SET pay_url=? WHERE id=?", [mb_substr($v, 0, 250), $rid]);

        $r = one("SELECT * FROM z_reqs WHERE id=?", [$rid]);
        $test = str_replace(['{SUM}', '{ID}'], ['50', 'TOP1'], $v);
        say($chat, "● <b>Линк сабт шуд</b>\n<code>───────────────</code>\n"
            . "Санҷиш (50 " . cfg('cur') . "):\n" . h($test),
            [[['text' => '🔗 Кушодан', 'url' => $test]],
             [['text' => '‹', 'callback_data' => 'a:rq:' . $rid]]]);
        return;
    }

    if ($s === 'a_rqname') {
        $rid = (int)$d['id'];
        $p = array_map('trim', explode('|', $text));
        clr_st($uid);
        q("UPDATE z_reqs SET fname=?, lname=?, owner=? WHERE id=?",
          [mb_substr($p[0] ?? '', 0, 70), mb_substr($p[1] ?? '', 0, 70),
           mb_substr(trim(($p[0] ?? '') . ' ' . ($p[1] ?? '')), 0, 110), $rid]);
        say($chat, "● Сабт шуд", [[['text' => '‹', 'callback_data' => 'a:rq:' . $rid]]]);
        return;
    }

    if ($s === 'a_rqnum') {
        $rid = (int)$d['id'];
        clr_st($uid);
        q("UPDATE z_reqs SET number=? WHERE id=?", [mb_substr(trim($text), 0, 70), $rid]);
        say($chat, "● Рақам сабт шуд", [[['text' => '‹', 'callback_data' => 'a:rq:' . $rid]]]);
        return;
    }

    // ---- ОП-КАНАЛҲО: иловаи канали нав (қадами 1: chat) ----
    if ($s === 'sub_chat') {
        $v = trim($text);
        if ($v === '' || mb_strlen($v) > 120) { say($chat, '× Канал нодуруст'); return; }
        set_st($uid, 'sub_title', ['chat' => $v]);
        say($chat, "<code>" . h($v) . "</code>\n<code>───────────────</code>\n"
            . "<b>Қадами 2 аз 2</b>\n\n"
            . "Номи тугмаро нависед (чӣ дар тугма нависад):\n\n"
            . "<i>Мисол: Канали мо · ZVER TAJ · Подпишись</i>\n\n"
            . "Ё <code>-</code> нависед — номи канал истифода мешавад.",
            [[['text' => '× Бекор', 'callback_data' => 'a:subs']]]);
        return;
    }
    if ($s === 'sub_title') {
        $v = trim($text);
        $d = $st['data'];
        $chatv = (string)($d['chat'] ?? '');
        $title = ($v === '' || $v === '-') ? $chatv : mb_substr($v, 0, 100);
        q("INSERT INTO z_subs (chat,title,link,active,sort,created_at) VALUES (?,?,?,1,0,?)",
          [$chatv, $title, '', time()]);
        clr_st($uid);
        $chk = sub_norm($chatv);
        $warn = $chk === ''
            ? "\n\n⚠️ <b>Диққат:</b> ин ссылкаи даъватист.\nСанҷиши обуна танҳо бо @username кор мекунад."
            : "\n\n<i>Ботро ба ин канал админ кунед, то санҷиш кор кунад.\n«🧪 Санҷиш»-ро пахш карда тафтиш кунед.</i>";
        say($chat, "✅ <b>Канал илова шуд!</b>\n<code>───────────────</code>\n"
            . "Канал · <code>" . h($chatv) . "</code>\n"
            . "Тугма · " . h($title) . $warn,
            [[['text' => '‹ ОП-каналҳо', 'callback_data' => 'a:subs']]]);
        return;
    }
    // ---- таҳрири номи тугмаи канал ----
    if ($s === 'a_subttl') {
        $v = trim($text);
        if ($v === '' || mb_strlen($v) > 100) { say($chat, '× Ном нодуруст'); return; }
        $sid = (int)($st['data']['id'] ?? 0);
        q("UPDATE z_subs SET title=? WHERE id=?", [$v, $sid]);
        clr_st($uid);
        say($chat, "● Номи тугма сабт шуд", [[['text' => '‹', 'callback_data' => 'a:sub:' . $sid]]]);
        return;
    }
    // ---- таҳрири ссылкаи дастии канал ----
    if ($s === 'a_sublink') {
        $v = trim($text);
        $sid = (int)($st['data']['id'] ?? 0);
        $link = ($v === '-' || $v === '') ? '' : mb_substr($v, 0, 250);
        q("UPDATE z_subs SET link=? WHERE id=?", [$link, $sid]);
        clr_st($uid);
        say($chat, $link === '' ? "● Ссылка нест карда шуд" : "● Ссылка сабт шуд",
            [[['text' => '‹', 'callback_data' => 'a:sub:' . $sid]]]);
        return;
    }

    if ($s === 'rq_bank') {
        $v = trim($text);
        if ($v === '' || mb_strlen($v) > 60) { say($chat, '× Номи бонк нодуруст'); return; }
        set_st($uid, 'rq_logo', ['bank' => $v]);
        say($chat, "<b>" . h($v) . "</b>\n<code>───────────────</code>\n"
            . "<b>Қадами 2 аз 5</b>\n\n"
            . "📷 Логотипи бонкро фиристед (расм).\n\n"
            . "<i>Он дар барнома паҳлӯи реквизит нишон дода мешавад.</i>", [
            [['text' => '⏭ Бе логотип', 'callback_data' => 'a:rqskip']],
            [['text' => '× Бекор', 'callback_data' => 'a:req']],
        ]);
        return;
    }

    if ($s === 'rq_logo') {
        say($chat, "📷 Расми логотипро фиристед ё «Бе логотип»-ро пахш кунед.", [
            [['text' => '⏭ Бе логотип', 'callback_data' => 'a:rqskip']],
            [['text' => '× Бекор', 'callback_data' => 'a:req']],
        ]);
        return;
    }

    if ($s === 'rq_name') {
        $v = trim(preg_replace('~\s+~u', ' ', $text));
        if ($v === '' || mb_strlen($v) > 80) { say($chat, '× Ном нодуруст'); return; }
        $parts = explode(' ', $v, 2);
        $d = $st['data'];
        $d['fname'] = $parts[0];
        $d['lname'] = $parts[1] ?? '';
        set_st($uid, 'rq_kind', $d);
        say($chat, "<b>" . h((string)$d['bank']) . "</b> · " . h($v)
            . "\n<code>───────────────</code>\n<b>Қадами 4 аз 5</b>\n\n"
            . "Пардохт ба чӣ меояд?", [
            [['text' => '📱 Ба рақами телефон', 'callback_data' => 'a:rqkind:phone']],
            [['text' => '💳 Ба рақами корт',    'callback_data' => 'a:rqkind:card']],
            [['text' => '× Бекор', 'callback_data' => 'a:req']],
        ]);
        return;
    }

    if ($s === 'rq_num') {
        $d = $st['data'];
        $kind = ($d['kind'] ?? 'card') === 'phone' ? 'phone' : 'card';
        $dg = preg_replace('~\D~', '', trim($text));

        if ($kind === 'phone') {
            if (mb_strlen($dg) < 9) { say($chat, '× Рақами телефон кӯтоҳ аст'); return; }
            if (mb_strlen($dg) === 9) $dg = '992' . $dg;
            $num = '+' . $dg;
        } else {
            if (mb_strlen($dg) < 12) { say($chat, '× Рақами корт кӯтоҳ аст'); return; }
            $num = $dg;
        }

        clr_st($uid);

        // линки пардохт худкор (танҳо барои корт)
        $auto = null;
        if ($kind === 'card') {
            $tpl = cfg('pay_tpl', 'https://pay.dc.tj/?a={NUM}&c={COMMENT}&f1=133&s={SUM}');
            if ($tpl !== '' && $tpl !== '-') {
                $auto = str_replace('{NUM}', $num, $tpl);
            }
        }

        q("INSERT INTO z_reqs (bank,fname,lname,owner,number,kind,logo,pay_url,active,sort)
           VALUES (?,?,?,?,?,?,?,?,1,0)",
          [mb_substr((string)$d['bank'], 0, 70), mb_substr((string)$d['fname'], 0, 70),
           mb_substr((string)($d['lname'] ?? ''), 0, 70),
           mb_substr(trim($d['fname'] . ' ' . ($d['lname'] ?? '')), 0, 110),
           mb_substr($num, 0, 70), $kind,
           !empty($d['logo']) ? (string)$d['logo'] : null,
           $auto !== null ? mb_substr($auto, 0, 250) : null]);
        $rid = (int)db()->lastInsertId();

        $test = $auto ? str_replace(['{SUM}', '{COMMENT}', '{ID}', '{NICK}'],
                                    ['50', 'test', 'TOP1', 'test'], $auto) : '';

        $kb = [];
        if ($test !== '') $kb[] = [['text' => '🔗 Линкро санҷед (50 сомонӣ)', 'url' => $test]];
        $kb[] = [['text' => $auto ? '✎ Линкро иваз кардан' : '🔗 Линки пардохт илова кардан',
                  'callback_data' => 'a:rqurl:' . $rid]];
        $kb[] = [['text' => '‹ Реквизитҳо', 'callback_data' => 'a:req']];

        say($chat, "● <b>РЕКВИЗИТ ТАЙЁР</b>\n<code>───────────────</code>\n"
            . "🏦 " . h((string)$d['bank']) . "\n"
            . "👤 " . h(trim($d['fname'] . ' ' . ($d['lname'] ?? ''))) . "\n"
            . ($kind === 'phone' ? "📱 " : "💳 ") . "<code>" . h($num) . "</code>\n"
            . (!empty($d['logo']) ? "🖼 логотип ҳаст\n" : '')
            . ($auto ? "🔗 линки пардохт худкор сохта шуд\n" : '')
            . "\n<i>Муштариён инро ҳангоми пур кардани ҳамён мебинанд.</i>", $kb);
        return;
    }

    if ($s === 'a_rvch') {
        clr_st($uid);
        $v = trim($text);
        if ($v === '-' || $v === '') { setcfg('rev_ch', ''); say($chat, '● Холӣ шуд'); return; }
        if (preg_match('~t\.me/([A-Za-z0-9_]+)~', $v, $m)) $v = '@' . $m[1];
        if ($v[0] !== '@' && $v[0] !== '-' && !ctype_digit($v)) $v = '@' . ltrim($v, '@');
        setcfg('rev_ch', $v);

        // фавран месанҷем — оё бот метавонад ба канал нависад
        $r = tg('sendMessage', ['chat_id' => $v, 'parse_mode' => 'HTML',
            'text' => "★ <b>Канали шарҳҳо пайваст шуд</b>\n<code>───────────────</code>\n"
                    . "<i>" . h(cfg('shop', 'ZVER TAJ')) . "</i>"]);
        if (!empty($r['ok'])) {
            say($chat, "● Канал <code>" . h($v) . "</code> кор мекунад — паёми санҷишӣ фиристода шуд.",
                [[['text' => '‹ Шарҳҳо', 'callback_data' => 'a:rv']]]);
        } else {
            say($chat, "⚠︎ Канал сабт шуд, вале бот нависта наметавонад:\n<code>"
                . h((string)($r['description'] ?? '?')) . "</code>\n\n"
                . "<i>Ботро ба канал админ кунед ва иҷозати «Фиристодани паём» диҳед.</i>",
                [[['text' => '‹ Шарҳҳо', 'callback_data' => 'a:rv']]]);
        }
        return;
    }

    if ($s === 'a_rej') {
        $tid = (int)($d['tid'] ?? 0);
        clr_st($uid);
        $why = trim($text);
        if ($why === '-' || mb_strtolower($why) === 'skip') $why = '';
        $ok = topup_deny($tid, $uid, mb_substr($why, 0, 200));

        if (!empty($d['mid']) && !empty($d['chat'])) {
            ed_any($d['chat'], (int)$d['mid'],
                ($ok ? "<b>× РАД ШУД</b> · #$tid" : "· Аллакай коркард шуд · #$tid")
                . ($why !== '' ? "\n<i>" . h($why) . "</i>" : "\n<i>Бе сабаб</i>"),
                [[['text' => '● Ба ҳар ҳол тасдиқ', 'callback_data' => 'at:d:' . $tid]]]);
        }
        say($chat, $ok ? "× Дархост #$tid рад шуд" . ($why !== '' ? " · " . h($why) : '')
                       : "· Дархост #$tid аллакай коркард шуда буд");
        return;
    }

    if ($s === 'a_code') {
        $oid = (int)$d['oid'];
        clr_st($uid);
        if (order_done($oid, $uid, $text)) say($chat, "● Фармоиш #$oid иҷро шуд бо код");
        else say($chat, "· Фармоиш аллакай коркард шуд");
        return;
    }

    if ($s === 'a_bal') {
        $tid = (int)$d['tid']; $sg = (string)$d['sg'];
        $v = round((float)str_replace(',', '.', $text), 2);
        if ($v <= 0) { say($chat, '× Маблағ нодуруст'); return; }
        $u = one("SELECT * FROM z_users WHERE id=?", [$tid]);
        if (!$u) { clr_st($uid); say($chat, '× Корбар нест'); return; }
        if ($sg === 'm') {
            $v = min($v, (float)$u['balance']);
            if ($v <= 0) { clr_st($uid); say($chat, '· Баланс холӣ'); return; }
            q("UPDATE z_users SET balance=balance-? WHERE id=?", [$v, $tid]);
            tx($tid, 'admin_sub', -$v, 'Тағйироти админ', null);
        } else {
            q("UPDATE z_users SET balance=balance+? WHERE id=?", [$v, $tid]);
            tx($tid, 'admin_add', $v, 'Тағйироти админ', null);
        }
        clr_st($uid);
        $nb = one("SELECT balance FROM z_users WHERE id=?", [$tid])['balance'] ?? 0;
        zlog('bal', "admin=$uid user=$tid " . ($sg === 'm' ? '-' : '+') . "$v => $nb");
        say($tid, ($sg === 'm' ? '− ' : '+ ') . "<b>" . money($v) . "</b>\n"
            . "Баланс · <b>" . money((float)$nb) . "</b>");
        $u2 = one("SELECT * FROM z_users WHERE id=?", [$tid]);
        say($chat, "● Иҷро шуд\n\n" . user_card($u2), user_kb($tid, (int)$u2['blocked'] === 1));
        return;
    }

    if ($s === 'a_set') {
        $k = (string)$d['k'];
        clr_st($uid);
        $v = ($text === '-') ? '' : $text;
        if ($k === 'ref_bonus') $v = (string)round((float)str_replace(',', '.', $v), 2);
        if ($k === 'support' && $v !== '' && $v[0] !== '@') $v = '@' . ltrim($v, '@');
        if (in_array($k, ['reviews', 'channel', 'sub_ch'], true) && $v !== '') {
            if ($v[0] !== '@' && $v[0] !== '-' && !preg_match('~^https?://~i', $v)) {
                $v = '@' . $v;
            }
        }
        if ($k === 'wa') $v = preg_replace('/\D/', '', $v) ?? '';
        if ($k === 'lowbal') { $v = (string)round((float)str_replace(',', '.', $v), 2);
                               setcfg('lownote', '0'); }
        setcfg($k, mb_substr($v, 0, 200));
        $extra = '';
        if (in_array($k, ['markup', 'rate', 'round'], true)) {
            $n = fz_reprice();
            $extra = "\n\n⟳ Нархи <b>$n</b> пакет аз нав ҳисоб шуд.";
        }
        say($chat, "● Сабт шуд · <code>" . h($v !== '' ? $v : '—') . "</code>" . $extra,
            [[['text' => '‹ Танзимот', 'callback_data' => 'a:cfg']]]);
        return;
    }

    if ($s === 'a_bc') {
        clr_st($uid);
        setcfg('bc_draft', $text);
        $tot = (int)(one("SELECT COUNT(*) c FROM z_users WHERE blocked=0")['c'] ?? 0);
        say($chat, '▸ Пешнамоиш:');
        say($chat, $text, [[['text' => T('app', $uid), 'web_app' => ['url' => app_url()]]]]);
        say($chat, "Қабулкунандагон · <b>$tot</b>", [
            [['text' => "▸ ФИРИСТОДАН ($tot)", 'callback_data' => 'a:bcgo']],
            [['text' => '× Бекор', 'callback_data' => 'a:menu']]]);
        return;
    }
}
