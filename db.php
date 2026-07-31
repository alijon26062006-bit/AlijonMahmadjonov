<?php
/**
 * CodeTJ — платформаи омӯзиши HTML, CSS ва JavaScript бо забони тоҷикӣ
 * db.php — пайвастшавӣ ба база, автомиграцияи схема, функсияҳои ёрирасон.
 *
 * Талабот: PHP 8.1+, MySQL (pdo_mysql). Бе Composer, бе китобхонаҳои беруна.
 */

/* ============================================================
 *  КОНФИГУРАЦИЯ — инро пеш аз боркунӣ ба ҳостинг пур кунед
 * ============================================================ */
define('DB_HOST', 'localhost');
define('DB_NAME', '');          // номи базаи MySQL аз cPanel
define('DB_USER', '');          // корбари база
define('DB_PASS', '');          // пароли база
define('OPENAI_KEY', '');       // калиди API (метавон баъдан дар админка гузошт)
define('SITE_URL', '');         // масалан: https://codetj.example.com (бе / дар охир)

define('CODETJ_SCHEMA_VERSION', 1);   // версияи схемаи база (миграцияҳо худкор)

/* ============================================================
 *  ПАЙВАСТШАВӢ БА БАЗА
 * ============================================================ */

/** PDO-и ягона барои тамоми дархост. */
function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }
    if (DB_NAME === '' || DB_USER === '') {
        codetj_config_needed_page();
    }
    try {
        $pdo = new PDO(
            'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4',
            DB_USER,
            DB_PASS,
            [
                PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES   => false,
            ]
        );
    } catch (PDOException $e) {
        codetj_db_error_page($e->getMessage());
    }
    migrate($pdo);
    return $pdo;
}

/** Саҳифаи дӯстона, вақте конфигурация ҳанӯз пур нашудааст. */
function codetj_config_needed_page(): never
{
    http_response_code(503);
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="tj"><head><meta charset="utf-8">'
       . '<meta name="viewport" content="width=device-width,initial-scale=1">'
       . '<title>CodeTJ — насбкунӣ</title>'
       . '<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px}'
       . '.box{max-width:640px;background:#1e293b;border-radius:16px;padding:32px;line-height:1.7}'
       . 'code{background:#0f172a;padding:2px 8px;border-radius:6px;color:#fbbf24}h1{font-size:1.5rem}ol{padding-left:20px}</style></head><body><div class="box">'
       . '<h1>🛠 CodeTJ: базаи маълумот ҳанӯз пайваст нашудааст</h1>'
       . '<p>Барои оғоз кардан:</p><ol>'
       . '<li>Дар cPanel → <b>MySQL Databases</b> база ва корбар созед, корбарро ба база бо ҳамаи ҳуқуқҳо пайваст кунед.</li>'
       . '<li>Файли <code>db.php</code>-ро кушоед ва дар боло <code>DB_NAME</code>, <code>DB_USER</code>, <code>DB_PASS</code>-ро пур кунед.</li>'
       . '<li>Ин саҳифаро аз нав кушоед — ҷадвалҳо худкор сохта мешаванд.</li>'
       . '</ol><p style="color:#94a3b8">Ҳамин саҳифа бо русӣ: заполните <code>DB_NAME</code>, <code>DB_USER</code>, <code>DB_PASS</code> в начале файла <code>db.php</code> и обновите страницу — таблицы создадутся автоматически.</p>'
       . '</div></body></html>';
    exit;
}

/** Хатои пайвастшавӣ — бе экрани сафед. */
function codetj_db_error_page(string $detail): never
{
    http_response_code(503);
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="tj"><head><meta charset="utf-8">'
       . '<meta name="viewport" content="width=device-width,initial-scale=1">'
       . '<title>CodeTJ — хато</title>'
       . '<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px}'
       . '.box{max-width:640px;background:#1e293b;border-radius:16px;padding:32px;line-height:1.7}pre{background:#0f172a;padding:12px;border-radius:8px;white-space:pre-wrap;color:#f87171;font-size:.85rem}</style></head><body><div class="box">'
       . '<h1>⚠️ Ба база пайваст шуда натавонистем</h1>'
       . '<p>Маълумоти <code>db.php</code>-ро тафтиш кунед (ном, корбар, парол). / Проверьте данные подключения в <code>db.php</code>.</p>'
       . '<pre>' . htmlspecialchars($detail, ENT_QUOTES, 'UTF-8') . '</pre>'
       . '</div></body></html>';
    exit;
}

/* ============================================================
 *  АВТОМИГРАЦИЯИ СХЕМА
 * ============================================================ */

function migrate(PDO $pdo): void
{
    // Ҷадвали settings ҳамеша аввал — версияи схема дар ҳамин ҷо меистад.
    $pdo->exec("CREATE TABLE IF NOT EXISTS settings (
        k VARCHAR(64) NOT NULL PRIMARY KEY,
        v TEXT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $cur = 0;
    try {
        $st = $pdo->prepare('SELECT v FROM settings WHERE k = ?');
        $st->execute(['schema_version']);
        $cur = (int)($st->fetchColumn() ?: 0);
    } catch (PDOException $e) {
        $cur = 0;
    }
    if ($cur >= CODETJ_SCHEMA_VERSION) {
        return;
    }

    if ($cur < 1) {
        migrate_to_v1($pdo);
    }
    // Дар қисмҳои оянда: if ($cur < 2) { migrate_to_v2($pdo); } ва ғ.

    $st = $pdo->prepare('REPLACE INTO settings (k, v) VALUES (?, ?)');
    $st->execute(['schema_version', (string)CODETJ_SCHEMA_VERSION]);
}

function migrate_to_v1(PDO $pdo): void
{
    $tables = [

        // Корбарон
        "CREATE TABLE IF NOT EXISTS users (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            login VARCHAR(32) NOT NULL,
            pass_hash VARCHAR(255) NOT NULL,
            name VARCHAR(64) NOT NULL DEFAULT '',
            city VARCHAR(64) NOT NULL DEFAULT '',
            avatar VARCHAR(128) NOT NULL DEFAULT '',
            role ENUM('student','admin') NOT NULL DEFAULT 'student',
            lang ENUM('tj','ru') NOT NULL DEFAULT 'tj',
            theme ENUM('dark','light') NOT NULL DEFAULT 'dark',
            points INT NOT NULL DEFAULT 0,
            week_points INT NOT NULL DEFAULT 0,
            streak_days INT NOT NULL DEFAULT 0,
            last_active_date DATE NULL,
            banned TINYINT(1) NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_login (login),
            KEY idx_points (points),
            KEY idx_week (week_points)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        // Дарсҳо: 4 курс × 50 дарс, ду забон
        "CREATE TABLE IF NOT EXISTS lessons (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            course VARCHAR(8) NOT NULL,
            num TINYINT UNSIGNED NOT NULL,
            title_tj VARCHAR(160) NOT NULL DEFAULT '',
            title_ru VARCHAR(160) NOT NULL DEFAULT '',
            theory_tj MEDIUMTEXT NULL,
            theory_ru MEDIUMTEXT NULL,
            example_code MEDIUMTEXT NULL,
            task_text_tj TEXT NULL,
            task_text_ru TEXT NULL,
            task_start_code MEDIUMTEXT NULL,
            task_criteria TEXT NULL,
            published TINYINT(1) NOT NULL DEFAULT 1,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_course_num (course, num)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        // Саволҳои тест (5 барои ҳар дарс). Ҷавоби дуруст ҲЕҶ ГОҲ ба браузер намеравад.
        "CREATE TABLE IF NOT EXISTS questions (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            lesson_id INT UNSIGNED NOT NULL,
            num TINYINT UNSIGNED NOT NULL DEFAULT 1,
            q_tj TEXT NOT NULL,
            q_ru TEXT NOT NULL,
            options_tj TEXT NOT NULL,
            options_ru TEXT NOT NULL,
            correct TINYINT UNSIGNED NOT NULL,
            explain_tj TEXT NULL,
            explain_ru TEXT NULL,
            KEY idx_lesson (lesson_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        // Пешрафти корбар аз рӯи дарс
        "CREATE TABLE IF NOT EXISTS progress (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNSIGNED NOT NULL,
            lesson_id INT UNSIGNED NOT NULL,
            ai_passed TINYINT(1) NOT NULL DEFAULT 0,
            ai_score TINYINT UNSIGNED NOT NULL DEFAULT 0,
            test_score TINYINT UNSIGNED NOT NULL DEFAULT 0,
            test_attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
            completed TINYINT(1) NOT NULL DEFAULT 0,
            completed_at DATETIME NULL,
            points_earned INT NOT NULL DEFAULT 0,
            first_try TINYINT(1) NOT NULL DEFAULT 0,
            UNIQUE KEY uq_user_lesson (user_id, lesson_id),
            KEY idx_user (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        // Натиҷаҳои имтиҳони сатҳ (5 сатҳ дар ҳар курс)
        "CREATE TABLE IF NOT EXISTS exam_results (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNSIGNED NOT NULL,
            course VARCHAR(8) NOT NULL,
            level TINYINT UNSIGNED NOT NULL,
            score TINYINT UNSIGNED NOT NULL DEFAULT 0,
            passed TINYINT(1) NOT NULL DEFAULT 0,
            taken_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_user_course (user_id, course, level)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        // Сиёҳнависи код (автозахира аз муҳаррир)
        "CREATE TABLE IF NOT EXISTS drafts (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNSIGNED NOT NULL,
            lesson_id INT UNSIGNED NOT NULL,
            html_code MEDIUMTEXT NULL,
            css_code MEDIUMTEXT NULL,
            js_code MEDIUMTEXT NULL,
            pasted TINYINT(1) NOT NULL DEFAULT 0,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_user_lesson (user_id, lesson_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        // Кэши ҷавобҳои ИИ аз рӯи SHA-256-и код
        "CREATE TABLE IF NOT EXISTS ai_cache (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            lesson_id INT UNSIGNED NOT NULL,
            code_hash CHAR(64) NOT NULL,
            lang CHAR(2) NOT NULL DEFAULT 'tj',
            response MEDIUMTEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_hash (lesson_id, code_hash, lang)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        // Ҳисоби истифодаи ИИ (лимитҳо + омори хароҷот)
        "CREATE TABLE IF NOT EXISTS ai_usage (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNSIGNED NOT NULL,
            lesson_id INT UNSIGNED NOT NULL DEFAULT 0,
            kind ENUM('check','help') NOT NULL DEFAULT 'check',
            tokens_in INT NOT NULL DEFAULT 0,
            tokens_out INT NOT NULL DEFAULT 0,
            cached TINYINT(1) NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_user_day (user_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        // Маҳдудияти суръат (login, register, ai)
        "CREATE TABLE IF NOT EXISTS rate_limit (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            ip VARCHAR(45) NOT NULL,
            action VARCHAR(24) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_ip_action (ip, action, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        // Таърихи баллҳо
        "CREATE TABLE IF NOT EXISTS points_log (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNSIGNED NOT NULL,
            points INT NOT NULL,
            reason VARCHAR(64) NOT NULL DEFAULT '',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_user (user_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        // Значокҳо (badges) — рӯйхат ва гирифташуда
        "CREATE TABLE IF NOT EXISTS user_badges (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNSIGNED NOT NULL,
            badge VARCHAR(32) NOT NULL,
            got_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_user_badge (user_id, badge)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",
    ];

    foreach ($tables as $sql) {
        $pdo->exec($sql);
    }

    // Танзимоти пешфарз (агар набошанд)
    $defaults = [
        'reg_enabled'        => '1',
        'ai_daily_limit'     => '10',   // санҷиши ИИ барои як дарс дар як рӯз
        'ai_help_daily'      => '5',    // саволҳо ба ИИ дар як рӯз
        'ai_cooldown_sec'    => '15',
        'openai_key'         => '',
        'week_reset_date'    => '',     // барои рейтинги ҳафтаина
    ];
    $st = $pdo->prepare('INSERT IGNORE INTO settings (k, v) VALUES (?, ?)');
    foreach ($defaults as $k => $v) {
        $st->execute([$k, $v]);
    }
}

/* ============================================================
 *  SETTINGS
 * ============================================================ */

function setting_get(string $k, ?string $default = null): ?string
{
    static $cache = [];
    if (array_key_exists($k, $cache)) {
        return $cache[$k];
    }
    $st = db()->prepare('SELECT v FROM settings WHERE k = ?');
    $st->execute([$k]);
    $v = $st->fetchColumn();
    $cache[$k] = ($v === false) ? $default : $v;
    return $cache[$k];
}

function setting_set(string $k, string $v): void
{
    $st = db()->prepare('REPLACE INTO settings (k, v) VALUES (?, ?)');
    $st->execute([$k, $v]);
}

/* ============================================================
 *  КУРСҲО ВА САТҲҲО
 * ============================================================ */

/** Мета-маълумоти 4 курс. Рангҳо: HTML — норанҷӣ, CSS — кабуд, JS — зард, Ҳамагӣ — сабз. */
function courses(): array
{
    return [
        'html' => ['icon' => '🧱', 'color' => '#f97316', 'name_tj' => 'HTML',   'name_ru' => 'HTML',
                   'desc_tj' => 'Скелети саҳифа: тегҳо, матн, расм, ҷадвал, форма.',
                   'desc_ru' => 'Скелет страницы: теги, текст, картинки, таблицы, формы.'],
        'css'  => ['icon' => '🎨', 'color' => '#3b82f6', 'name_tj' => 'CSS',    'name_ru' => 'CSS',
                   'desc_tj' => 'Ороиши сайт: ранг, шрифт, ҷобаҷогузорӣ, анимация.',
                   'desc_ru' => 'Оформление сайта: цвета, шрифты, раскладка, анимации.'],
        'js'   => ['icon' => '⚡', 'color' => '#eab308', 'name_tj' => 'JavaScript', 'name_ru' => 'JavaScript',
                   'desc_tj' => 'Ҷони сайт: тугмаҳо, ҳисобкунӣ, бозиҳо, кор бо маълумот.',
                   'desc_ru' => 'Жизнь сайта: кнопки, вычисления, игры, работа с данными.'],
        'full' => ['icon' => '🚀', 'color' => '#22c55e', 'name_tj' => 'Ҳамагӣ', 'name_ru' => 'Всё вместе',
                   'desc_tj' => 'Лоиҳаҳои воқеӣ: HTML + CSS + JS дар як ҷо. Аз компонент то лоиҳаи дипломӣ.',
                   'desc_ru' => 'Реальные проекты: HTML + CSS + JS вместе. От компонентов до дипломного проекта.'],
    ];
}

/** Номҳои 5 сатҳ (10 дарс дар ҳар кадом). */
function levels(): array
{
    return [
        1 => ['tj' => 'Навомӯз',    'ru' => 'Новичок'],
        2 => ['tj' => 'Кӯшокор',    'ru' => 'Старательный'],
        3 => ['tj' => 'Барномасоз', 'ru' => 'Программист'],
        4 => ['tj' => 'Устод',      'ru' => 'Мастер'],
        5 => ['tj' => 'Эксперт',    'ru' => 'Эксперт'],
    ];
}

const LESSONS_PER_COURSE = 50;
const LESSONS_PER_LEVEL  = 10;

/** Чанд дарси курс аз тарафи корбар супорида шудааст. */
function course_done_count(int $userId, string $course): int
{
    $st = db()->prepare(
        'SELECT COUNT(*) FROM progress p JOIN lessons l ON l.id = p.lesson_id
         WHERE p.user_id = ? AND l.course = ? AND p.completed = 1'
    );
    $st->execute([$userId, $course]);
    return (int)$st->fetchColumn();
}

/** Рӯйхати рақамҳои дарсҳои супоридашудаи курс: [num => true]. */
function course_done_map(int $userId, string $course): array
{
    $st = db()->prepare(
        'SELECT l.num FROM progress p JOIN lessons l ON l.id = p.lesson_id
         WHERE p.user_id = ? AND l.course = ? AND p.completed = 1'
    );
    $st->execute([$userId, $course]);
    $map = [];
    foreach ($st->fetchAll(PDO::FETCH_COLUMN) as $n) {
        $map[(int)$n] = true;
    }
    return $map;
}

/** Оё имтиҳони сатҳ супорида шудааст? */
function exam_passed(int $userId, string $course, int $level): bool
{
    $st = db()->prepare(
        'SELECT COUNT(*) FROM exam_results WHERE user_id = ? AND course = ? AND level = ? AND passed = 1'
    );
    $st->execute([$userId, $course, $level]);
    return (int)$st->fetchColumn() > 0;
}

/** Сатҳ кушода аст? Сатҳи 1 ҳамеша кушода; N кушода, агар имтиҳони N-1 супорида шуда бошад. */
function level_unlocked(int $userId, string $course, int $level): bool
{
    if ($level <= 1) {
        return true;
    }
    return exam_passed($userId, $course, $level - 1);
}

/** Курси «Ҳамагӣ» кушода мешавад, вақте дар html, css, js ҳар кадом ≥ 60% супорида шуд. */
function full_course_unlocked(int $userId): bool
{
    foreach (['html', 'css', 'js'] as $c) {
        if (course_done_count($userId, $c) < (int)ceil(LESSONS_PER_COURSE * 0.6)) {
            return false;
        }
    }
    return true;
}

/* ============================================================
 *  КОРБАРОН, СЕССИЯ, АМНИЯТ
 * ============================================================ */

function codetj_session_start(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }
    session_set_cookie_params([
        'lifetime' => 60 * 60 * 24 * 30,
        'path'     => '/',
        'httponly' => true,
        'samesite' => 'Lax',
        'secure'   => (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off'),
    ]);
    session_name('codetj_sid');
    session_start();
}

/** Корбари ҷорӣ ё null. Натиҷа дар дархост кэш мешавад. */
function current_user(): ?array
{
    static $user = false;
    if ($user !== false) {
        return $user;
    }
    $user = null;
    if (!empty($_SESSION['uid'])) {
        $st = db()->prepare('SELECT * FROM users WHERE id = ? AND banned = 0');
        $st->execute([(int)$_SESSION['uid']]);
        $u = $st->fetch();
        if ($u) {
            $user = $u;
        } else {
            unset($_SESSION['uid']);
        }
    }
    return $user;
}

function is_admin(): bool
{
    $u = current_user();
    return $u !== null && $u['role'] === 'admin';
}

/** Ҳисоби серия (streak) — «попутно», ҳар дафъае ки корбар ворид шуд. */
function update_streak(array &$user): void
{
    $today = date('Y-m-d');
    if ($user['last_active_date'] === $today) {
        return;
    }
    $yesterday = date('Y-m-d', strtotime('-1 day'));
    $streak = ($user['last_active_date'] === $yesterday) ? ((int)$user['streak_days'] + 1) : 1;
    $st = db()->prepare('UPDATE users SET streak_days = ?, last_active_date = ? WHERE id = ?');
    $st->execute([$streak, $today, (int)$user['id']]);
    $user['streak_days'] = $streak;
    $user['last_active_date'] = $today;
}

/** Рейтинги ҳафтаина ҳар душанбе «попутно» нул мешавад. */
function maybe_reset_week(): void
{
    $monday = date('Y-m-d', strtotime('monday this week'));
    if (setting_get('week_reset_date', '') !== $monday) {
        db()->exec('UPDATE users SET week_points = 0');
        setting_set('week_reset_date', $monday);
    }
}

/* ---------- CSRF ---------- */

function csrf_token(): string
{
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf'];
}

function csrf_field(): string
{
    return '<input type="hidden" name="csrf" value="' . csrf_token() . '">';
}

/** Тафтиши токен барои ҳар POST. Дар хато — false (даъваткунанда паём медиҳад). */
function csrf_ok(): bool
{
    $sent = $_POST['csrf'] ?? ($_SERVER['HTTP_X_CSRF'] ?? '');
    return is_string($sent) && $sent !== '' && hash_equals($_SESSION['csrf'] ?? '', $sent);
}

/* ---------- Rate limit ---------- */

function client_ip(): string
{
    return substr($_SERVER['REMOTE_ADDR'] ?? '0.0.0.0', 0, 45);
}

/**
 * true — иҷозат ҳаст; false — лимит пур шуд.
 * Сабтҳои кӯҳна «попутно» тоза мешаванд (cron лозим нест).
 */
function rate_limit(string $action, int $maxHits, int $windowSec): bool
{
    $pdo = db();
    // тозакунии тасодуфӣ (~2% дархостҳо), то ҷадвал калон нашавад
    if (random_int(1, 50) === 1) {
        $pdo->prepare('DELETE FROM rate_limit WHERE created_at < DATE_SUB(NOW(), INTERVAL 2 DAY)')->execute();
    }
    $ip = client_ip();
    $st = $pdo->prepare(
        'SELECT COUNT(*) FROM rate_limit WHERE ip = ? AND action = ? AND created_at > DATE_SUB(NOW(), INTERVAL ? SECOND)'
    );
    $st->execute([$ip, $action, $windowSec]);
    if ((int)$st->fetchColumn() >= $maxHits) {
        return false;
    }
    $pdo->prepare('INSERT INTO rate_limit (ip, action) VALUES (?, ?)')->execute([$ip, $action]);
    return true;
}

/* ---------- Баллҳо ---------- */

function add_points(int $userId, int $points, string $reason): void
{
    if ($points === 0) {
        return;
    }
    $pdo = db();
    $pdo->prepare('UPDATE users SET points = points + ?, week_points = week_points + ? WHERE id = ?')
        ->execute([$points, $points, $userId]);
    $pdo->prepare('INSERT INTO points_log (user_id, points, reason) VALUES (?, ?, ?)')
        ->execute([$userId, $points, $reason]);
}

/* ============================================================
 *  ЁРИРАСОНҲОИ УМУМӢ
 * ============================================================ */

/** Экранкунии HTML — ҳамеша барои маълумоти корбар. */
function e(?string $s): string
{
    return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
}

/** Redirect ва тамом. */
function redirect(string $url): never
{
    header('Location: ' . $url);
    exit;
}

/** Ҷавоби JSON ва тамом. */
function json_out(array $data, int $code = 200): never
{
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}
