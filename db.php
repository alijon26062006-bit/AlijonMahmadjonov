<?php
/**
 * CodeTJ — платформаи омӯзиши HTML, CSS ва JavaScript бо забони тоҷикӣ
 * db.php — пайвастшавӣ ба база, автомиграцияи схема, функсияҳои ёрирасон.
 *
 * Талабот: PHP 7.1+ (беҳтараш 8.0+), MySQL (pdo_mysql).
 * Бе Composer, бе китобхонаҳои беруна.
 */

// Муҳофизат аз дубора ворид шудани ҳамин файл.
if (defined('CODETJ_DB_LOADED')) {
    return;
}
define('CODETJ_DB_LOADED', 1);

/* ============================================================
 *  КОНФИГУРАЦИЯ — инро пеш аз боркунӣ ба ҳостинг пур кунед
 * ============================================================ */
define('DB_HOST', 'localhost');
define('DB_PORT', '3306');      // порти MySQL (одатан 3306)
define('DB_NAME', '');          // номи базаи MySQL аз панели ҳостинг
define('DB_USER', '');          // корбари база
define('DB_PASS', '');          // пароли база
define('OPENAI_KEY', '');       // калиди API (метавон баъдан дар админка гузошт)
define('SITE_URL', '');         // холӣ монед — худаш муайян мекунад. Ё: https://codetj.tj
define('OPENAI_MODEL', 'gpt-4o-mini');
define('OPENAI_URL', 'https://api.openai.com/v1/chat/completions');

define('CODETJ_SCHEMA_VERSION', 3);   // версияи схемаи база (миграцияҳо худкор)

/* ============================================================
 *  ПАЙВАСТШАВӢ БА БАЗА
 * ============================================================ */

/**
 * PDO-и ягона барои тамоми дархост.
 * @return PDO
 */
function db()
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }
    if (!extension_loaded('pdo_mysql')) {
        codetj_fatal_page(
            'Васеъкунии pdo_mysql фаъол нест',
            'Дар панели ҳостинг версияи PHP-ро ба 8.0 ё болотар гузоред ва васеъкунии <b>pdo_mysql</b>-ро фаъол кунед.',
            'Расширение pdo_mysql не включено. В панели хостинга выберите PHP 8.0+ и включите pdo_mysql.'
        );
    }
    if (DB_NAME === '' || DB_USER === '') {
        codetj_fatal_page(
            'Базаи маълумот ҳанӯз пайваст нашудааст',
            'Файли <b>db.php</b>-ро кушоед ва дар боло <b>DB_NAME</b>, <b>DB_USER</b>, <b>DB_PASS</b>-ро пур кунед.',
            'Откройте файл db.php и заполните вверху DB_NAME, DB_USER, DB_PASS.'
        );
    }
    try {
        $pdo = new PDO(
            'mysql:host=' . DB_HOST . ';port=' . DB_PORT . ';dbname=' . DB_NAME . ';charset=utf8mb4',
            DB_USER,
            DB_PASS,
            array(
                PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES   => false,
            )
        );
    } catch (PDOException $e) {
        codetj_fatal_page(
            'Ба база пайваст шуда натавонистем',
            'Ном, корбар ё пароли базаро дар <b>db.php</b> тафтиш кунед. Дар ҳостинг ном одатан префикс дорад.',
            'Проверьте имя базы, пользователя и пароль в db.php. На хостинге имя обычно с префиксом.',
            $e->getMessage()
        );
    }
    migrate($pdo);
    return $pdo;
}

/**
 * Саҳифаи хатои фаҳмо — ба ҷои экрани сафед.
 * Ҳамеша ду забон, то ҳар кас фаҳмад.
 */
function codetj_fatal_page($titleTj, $helpTj, $helpRu, $detail = '')
{
    if (!headers_sent()) {
        http_response_code(503);
        header('Content-Type: text/html; charset=utf-8');
    }
    echo '<!doctype html><html lang="tg"><head><meta charset="utf-8">'
       . '<meta name="viewport" content="width=device-width,initial-scale=1">'
       . '<title>CodeTJ — хато</title><style>'
       . 'body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0b1120;color:#e7edf7;'
       . 'display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px;line-height:1.7}'
       . '.box{max-width:680px;width:100%;background:#16223a;border:1px solid #243350;border-radius:16px;padding:28px}'
       . 'h1{font-size:1.35rem;margin:0 0 14px}b{color:#38bdf8}'
       . '.ru{color:#8fa0bd;font-size:.92rem;margin-top:14px;padding-top:14px;border-top:1px solid #243350}'
       . 'pre{background:#0b1120;padding:12px;border-radius:8px;white-space:pre-wrap;word-break:break-word;'
       . 'color:#f87171;font-size:.8rem;margin-top:14px}'
       . '.hint{background:#0b1120;border-radius:10px;padding:12px 14px;margin-top:14px;font-size:.9rem;color:#8fa0bd}'
       . '</style></head><body><div class="box">'
       . '<h1>&#9888;&#65039; ' . htmlspecialchars($titleTj, ENT_QUOTES, 'UTF-8') . '</h1>'
       . '<p>' . $helpTj . '</p>'
       . '<div class="ru">' . htmlspecialchars($helpRu, ENT_QUOTES, 'UTF-8') . '</div>';
    if ($detail !== '') {
        echo '<pre>' . htmlspecialchars($detail, ENT_QUOTES, 'UTF-8') . '</pre>';
    }
    echo '<div class="hint">Барои санҷиши пурраи ҳостинг файли <b>check.php</b>-ро кушоед: '
       . '<b>сайт.tj/check.php</b><br>Для полной диагностики хостинга откройте check.php</div>'
       . '</div></body></html>';
    exit;
}

/* ============================================================
 *  АВТОМИГРАЦИЯИ СХЕМА
 * ============================================================ */

function migrate(PDO $pdo)
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS cj_settings (
        k VARCHAR(64) NOT NULL PRIMARY KEY,
        v TEXT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $cur = 0;
    try {
        $st = $pdo->prepare('SELECT v FROM cj_settings WHERE k = ?');
        $st->execute(array('schema_version'));
        $cur = (int)$st->fetchColumn();
    } catch (PDOException $e) {
        $cur = 0;
    }

    if ($cur < 1) {
        migrate_to_v1($pdo);
    }
    if ($cur < 2) {
        migrate_to_v2($pdo);
    }
    if ($cur < 3) {
        migrate_to_v3($pdo);
    }

    if ($cur < CODETJ_SCHEMA_VERSION) {
        $st = $pdo->prepare('REPLACE INTO cj_settings (k, v) VALUES (?, ?)');
        $st->execute(array('schema_version', (string)CODETJ_SCHEMA_VERSION));
    }

    // Дарсҳо «попутно» ворид мешаванд — cron лозим нест.
    seed_lessons($pdo);
}

function migrate_to_v1(PDO $pdo)
{
    $tables = array(

        "CREATE TABLE IF NOT EXISTS cj_users (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            phone VARCHAR(20) NOT NULL DEFAULT '',
            pin VARCHAR(255) NULL,
            login VARCHAR(32) NULL,
            pass_hash VARCHAR(255) NULL,
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
            UNIQUE KEY uq_phone (phone),
            UNIQUE KEY uq_login (login),
            KEY idx_points (points),
            KEY idx_week (week_points)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        "CREATE TABLE IF NOT EXISTS cj_lessons (
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

        "CREATE TABLE IF NOT EXISTS cj_questions (
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

        "CREATE TABLE IF NOT EXISTS cj_progress (
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

        "CREATE TABLE IF NOT EXISTS cj_exam_results (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNSIGNED NOT NULL,
            course VARCHAR(8) NOT NULL,
            level TINYINT UNSIGNED NOT NULL,
            score TINYINT UNSIGNED NOT NULL DEFAULT 0,
            passed TINYINT(1) NOT NULL DEFAULT 0,
            taken_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_user_course (user_id, course, level)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        "CREATE TABLE IF NOT EXISTS cj_drafts (
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

        "CREATE TABLE IF NOT EXISTS cj_ai_cache (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            lesson_id INT UNSIGNED NOT NULL,
            code_hash CHAR(64) NOT NULL,
            lang CHAR(2) NOT NULL DEFAULT 'tj',
            response MEDIUMTEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_hash (lesson_id, code_hash, lang)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        "CREATE TABLE IF NOT EXISTS cj_ai_usage (
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

        "CREATE TABLE IF NOT EXISTS cj_rate_limit (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            ip VARCHAR(45) NOT NULL,
            action VARCHAR(24) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_ip_action (ip, action, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        "CREATE TABLE IF NOT EXISTS cj_points_log (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNSIGNED NOT NULL,
            points INT NOT NULL,
            reason VARCHAR(64) NOT NULL DEFAULT '',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_user (user_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",

        "CREATE TABLE IF NOT EXISTS cj_user_badges (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNSIGNED NOT NULL,
            badge VARCHAR(32) NOT NULL,
            got_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_user_badge (user_id, badge)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",
    );

    foreach ($tables as $sql) {
        $pdo->exec($sql);
    }

    $defaults = array(
        'reg_enabled'     => '1',
        'ai_daily_limit'  => '10',
        'ai_help_daily'   => '5',
        'ai_cooldown_sec' => '15',
        'openai_key'      => '',
        'week_reset_date' => '',
    );
    $st = $pdo->prepare('INSERT IGNORE INTO cj_settings (k, v) VALUES (?, ?)');
    foreach ($defaults as $k => $v) {
        $st->execute(array($k, $v));
    }
}

/** v2: ҷадвали кӯшишҳои тест (кадом савол дуруст ҷавоб дода шуд). */
function migrate_to_v2(PDO $pdo)
{
    $pdo->exec("CREATE TABLE IF NOT EXISTS cj_test_answers (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        user_id INT UNSIGNED NOT NULL,
        question_id INT UNSIGNED NOT NULL,
        attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
        correct TINYINT(1) NOT NULL DEFAULT 0,
        points INT NOT NULL DEFAULT 0,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_user_question (user_id, question_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
}

/** v3: воридшавӣ бо рақами телефон. */
function migrate_to_v3(PDO $pdo)
{
    // Дар нусхаҳои кӯҳна майдонҳо набуданд — бехато илова мекунем.
    $add = array(
        "ALTER TABLE cj_users ADD COLUMN phone VARCHAR(20) NOT NULL DEFAULT ''",
        "ALTER TABLE cj_users ADD COLUMN pin VARCHAR(255) NULL",
        "ALTER TABLE cj_users ADD UNIQUE KEY uq_phone (phone)",
        "ALTER TABLE cj_users MODIFY login VARCHAR(32) NULL",
        "ALTER TABLE cj_users MODIFY pass_hash VARCHAR(255) NULL",
    );
    foreach ($add as $sql) {
        try {
            $pdo->exec($sql);
        } catch (PDOException $e) {
            // майдон аллакай ҳаст — мегузарем
        }
    }
}

/* ============================================================
 *  ВОРИДКУНИИ ДАРСҲО АЗ ФАЙЛҲОИ JSON (папкаи seed/)
 * ============================================================ */

/**
 * Файлҳои seed/*.json-ро мехонад ва дарсҳоро ба база меорад.
 * Такрор ворид намекунад: ҳар файл аз рӯи хэш як бор кор мекунад.
 * Агар папка ё файл набошад — бе хато мегузарад.
 */
function seed_lessons(PDO $pdo)
{
    // Ду роҳ: файлҳои lessons*.php дар ҳамин папка (осонтар — папка сохтан лозим нест)
    // ва файлҳои seed/*.json (агар папкаи seed бошад).
    $files = array();
    // Танҳо lessons1.php, lessons2.php … — файлҳои дигар ба ин ҷо намеафтанд.
    $php = glob(__DIR__ . '/lessons[0-9]*.php');
    if ($php) {
        foreach ($php as $f) {
            // Файли дарс бояд массив баргардонад ва код надошта бошад.
            $head = (string)@file_get_contents($f, false, null, 0, 4096);
            if (strpos($head, 'return ') === false || preg_match('/^\s*function\s+\w+\s*\(/m', $head)) {
                continue;
            }
            $files[] = $f;
        }
    }
    if (is_dir(__DIR__ . '/seed')) {
        $json = glob(__DIR__ . '/seed/*.json');
        if ($json) {
            $files = array_merge($files, $json);
        }
    }
    if (!$files) {
        return;
    }
    sort($files);

    // кадом файлҳо аллакай ворид шудаанд
    $doneRaw = '';
    try {
        $st = $pdo->prepare('SELECT v FROM cj_settings WHERE k = ?');
        $st->execute(array('seeded_files'));
        $doneRaw = (string)$st->fetchColumn();
    } catch (PDOException $e) {
        $doneRaw = '';
    }
    $done = $doneRaw !== '' ? json_decode($doneRaw, true) : array();
    if (!is_array($done)) {
        $done = array();
    }

    $changed = false;
    foreach ($files as $file) {
        $key = basename($file);
        $raw = @file_get_contents($file);
        if ($raw === false || $raw === '') {
            continue;
        }
        $sig = md5($raw);
        if (isset($done[$key]) && $done[$key] === $sig) {
            continue;   // ҳамин нусха аллакай ворид шудааст
        }
        if (substr($file, -4) === '.php') {
            $data = @include $file;   // файл массиви дарсҳоро бармегардонад
        } else {
            $data = json_decode($raw, true);
        }
        if (!is_array($data)) {
            continue;   // файл вайрон — беэътино мегузарем, сайт кор мекунад
        }
        foreach ($data as $lesson) {
            if (is_array($lesson)) {
                import_lesson($pdo, $lesson);
            }
        }
        $done[$key] = $sig;
        $changed = true;
    }

    if ($changed) {
        $st = $pdo->prepare('REPLACE INTO cj_settings (k, v) VALUES (?, ?)');
        $st->execute(array('seeded_files', json_encode($done)));
    }
}

/**
 * Як дарсро ворид ё нав мекунад (аз рӯи course + num).
 * Саволҳо ҳамеша аз нав навишта мешаванд, то такрор нашаванд.
 */
function import_lesson(PDO $pdo, array $L)
{
    $course = isset($L['course']) ? (string)$L['course'] : '';
    $num    = isset($L['num']) ? (int)$L['num'] : 0;
    if (!in_array($course, array('html', 'css', 'js', 'full'), true) || $num < 1 || $num > 50) {
        return;
    }
    $g = function ($k) use ($L) {
        return isset($L[$k]) ? (string)$L[$k] : '';
    };

    $st = $pdo->prepare('SELECT id FROM cj_lessons WHERE course = ? AND num = ?');
    $st->execute(array($course, $num));
    $id = (int)$st->fetchColumn();

    $fields = array(
        $g('title_tj'), $g('title_ru'), $g('theory_tj'), $g('theory_ru'),
        $g('example_code'), $g('task_text_tj'), $g('task_text_ru'),
        $g('task_start_code'), $g('task_criteria'),
    );

    if ($id > 0) {
        $sql = 'UPDATE cj_lessons SET title_tj=?, title_ru=?, theory_tj=?, theory_ru=?, example_code=?,
                task_text_tj=?, task_text_ru=?, task_start_code=?, task_criteria=?, published=1 WHERE id=?';
        $params = $fields;
        $params[] = $id;
        $pdo->prepare($sql)->execute($params);
    } else {
        $sql = 'INSERT INTO cj_lessons (title_tj, title_ru, theory_tj, theory_ru, example_code,
                task_text_tj, task_text_ru, task_start_code, task_criteria, course, num, published)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,1)';
        $params = $fields;
        $params[] = $course;
        $params[] = $num;
        $pdo->prepare($sql)->execute($params);
        $id = (int)$pdo->lastInsertId();
    }

    if ($id < 1 || empty($L['questions']) || !is_array($L['questions'])) {
        return;
    }
    $pdo->prepare('DELETE FROM cj_questions WHERE lesson_id = ?')->execute(array($id));
    $ins = $pdo->prepare('INSERT INTO cj_questions
        (lesson_id, num, q_tj, q_ru, options_tj, options_ru, correct, explain_tj, explain_ru)
        VALUES (?,?,?,?,?,?,?,?,?)');
    $n = 0;
    foreach ($L['questions'] as $q) {
        if (!is_array($q)) {
            continue;
        }
        $optTj = isset($q['options_tj']) && is_array($q['options_tj']) ? array_values($q['options_tj']) : array();
        $optRu = isset($q['options_ru']) && is_array($q['options_ru']) ? array_values($q['options_ru']) : $optTj;
        if (count($optTj) < 2) {
            continue;
        }
        if (count($optRu) !== count($optTj)) {
            $optRu = $optTj;
        }
        $correct = isset($q['correct']) ? (int)$q['correct'] : 0;
        if ($correct < 0 || $correct >= count($optTj)) {
            $correct = 0;
        }
        $n++;
        $ins->execute(array(
            $id, $n,
            isset($q['q_tj']) ? (string)$q['q_tj'] : '',
            isset($q['q_ru']) ? (string)$q['q_ru'] : '',
            json_encode($optTj, JSON_UNESCAPED_UNICODE),
            json_encode($optRu, JSON_UNESCAPED_UNICODE),
            $correct,
            isset($q['explain_tj']) ? (string)$q['explain_tj'] : '',
            isset($q['explain_ru']) ? (string)$q['explain_ru'] : '',
        ));
    }
}

/* ============================================================
 *  SETTINGS
 * ============================================================ */

function setting_get($k, $default = null)
{
    static $cache = array();
    if (array_key_exists($k, $cache)) {
        return $cache[$k];
    }
    $st = db()->prepare('SELECT v FROM cj_settings WHERE k = ?');
    $st->execute(array($k));
    $v = $st->fetchColumn();
    $cache[$k] = ($v === false) ? $default : $v;
    return $cache[$k];
}

function setting_set($k, $v)
{
    $st = db()->prepare('REPLACE INTO cj_settings (k, v) VALUES (?, ?)');
    $st->execute(array($k, $v));
}

/* ============================================================
 *  КУРСҲО ВА САТҲҲО
 * ============================================================ */

/** Мета-маълумоти 4 курс. HTML — норанҷӣ, CSS — кабуд, JS — зард, Ҳамагӣ — сабз. */
function courses()
{
    return array(
        'html' => array('icon' => '&#129521;', 'color' => '#f97316', 'name_tj' => 'HTML', 'name_ru' => 'HTML',
            'desc_tj' => 'Скелети саҳифа: тегҳо, матн, расм, ҷадвал, форма.',
            'desc_ru' => 'Скелет страницы: теги, текст, картинки, таблицы, формы.'),
        'css' => array('icon' => '&#127912;', 'color' => '#3b82f6', 'name_tj' => 'CSS', 'name_ru' => 'CSS',
            'desc_tj' => 'Ороиши сайт: ранг, шрифт, ҷобаҷогузорӣ, анимация.',
            'desc_ru' => 'Оформление сайта: цвета, шрифты, раскладка, анимации.'),
        'js' => array('icon' => '&#9889;', 'color' => '#eab308', 'name_tj' => 'JavaScript', 'name_ru' => 'JavaScript',
            'desc_tj' => 'Ҷони сайт: тугмаҳо, ҳисобкунӣ, бозиҳо, кор бо маълумот.',
            'desc_ru' => 'Жизнь сайта: кнопки, вычисления, игры, работа с данными.'),
        'full' => array('icon' => '&#128640;', 'color' => '#22c55e', 'name_tj' => 'Ҳамагӣ', 'name_ru' => 'Всё вместе',
            'desc_tj' => 'Лоиҳаҳои воқеӣ: HTML + CSS + JS дар як ҷо. Аз компонент то лоиҳаи дипломӣ.',
            'desc_ru' => 'Реальные проекты: HTML + CSS + JS вместе. От компонентов до дипломного проекта.'),
    );
}

/** Номҳои 5 сатҳ (10 дарс дар ҳар кадом). */
function levels()
{
    return array(
        1 => array('tj' => 'Навомӯз',    'ru' => 'Новичок'),
        2 => array('tj' => 'Кӯшокор',    'ru' => 'Старательный'),
        3 => array('tj' => 'Барномасоз', 'ru' => 'Программист'),
        4 => array('tj' => 'Устод',      'ru' => 'Мастер'),
        5 => array('tj' => 'Эксперт',    'ru' => 'Эксперт'),
    );
}

define('LESSONS_PER_COURSE', 50);
define('LESSONS_PER_LEVEL', 10);

function course_done_count($userId, $course)
{
    $st = db()->prepare(
        'SELECT COUNT(*) FROM cj_progress p JOIN cj_lessons l ON l.id = p.lesson_id
         WHERE p.user_id = ? AND l.course = ? AND p.completed = 1'
    );
    $st->execute(array($userId, $course));
    return (int)$st->fetchColumn();
}

/** Рақамҳои дарсҳои супоридашуда: [num => true]. */
function course_done_map($userId, $course)
{
    $st = db()->prepare(
        'SELECT l.num FROM cj_progress p JOIN cj_lessons l ON l.id = p.lesson_id
         WHERE p.user_id = ? AND l.course = ? AND p.completed = 1'
    );
    $st->execute(array($userId, $course));
    $map = array();
    foreach ($st->fetchAll(PDO::FETCH_COLUMN) as $n) {
        $map[(int)$n] = true;
    }
    return $map;
}

function exam_passed($userId, $course, $level)
{
    $st = db()->prepare(
        'SELECT COUNT(*) FROM cj_exam_results WHERE user_id = ? AND course = ? AND level = ? AND passed = 1'
    );
    $st->execute(array($userId, $course, $level));
    return (int)$st->fetchColumn() > 0;
}

/**
 * Сатҳ кушода аст?
 * Сатҳи 1 ҳамеша кушода. Сатҳи N кушода, агар имтиҳони N-1 супорида шуда бошад,
 * ЁКИ ҳамаи 10 дарси сатҳи N-1 супорида шуда бошанд (то имтиҳонҳо тайёр шаванд —
 * шогирд дар ҷои холӣ намемонад).
 */
function level_unlocked($userId, $course, $level)
{
    if ($level <= 1) {
        return true;
    }
    if (exam_passed($userId, $course, $level - 1)) {
        return true;
    }
    $from = ($level - 2) * LESSONS_PER_LEVEL + 1;
    $to = ($level - 1) * LESSONS_PER_LEVEL;
    $st = db()->prepare(
        'SELECT COUNT(*) FROM cj_progress p JOIN cj_lessons l ON l.id = p.lesson_id
         WHERE p.user_id = ? AND l.course = ? AND p.completed = 1 AND l.num BETWEEN ? AND ?'
    );
    $st->execute(array($userId, $course, $from, $to));
    return (int)$st->fetchColumn() >= LESSONS_PER_LEVEL;
}

/** Курси «Ҳамагӣ» — вақте дар html, css, js ҳар кадом ≥ 60%. */
function full_course_unlocked($userId)
{
    $need = (int)ceil(LESSONS_PER_COURSE * 0.6);
    foreach (array('html', 'css', 'js') as $c) {
        if (course_done_count($userId, $c) < $need) {
            return false;
        }
    }
    return true;
}

/* ============================================================
 *  КОРБАРОН, СЕССИЯ, АМНИЯТ
 * ============================================================ */

/** Cookie бо SameSite — дар PHP-и кӯҳна ҳам кор мекунад. */
function codetj_setcookie($name, $value, $expires)
{
    if (PHP_VERSION_ID >= 70300) {
        setcookie($name, $value, array(
            'expires'  => $expires,
            'path'     => '/',
            'samesite' => 'Lax',
        ));
    } else {
        setcookie($name, $value, $expires, '/; samesite=Lax');
    }
}

function codetj_session_start()
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }
    $secure = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
           || (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https');
    $life = 60 * 60 * 24 * 30;
    if (PHP_VERSION_ID >= 70300) {
        session_set_cookie_params(array(
            'lifetime' => $life,
            'path'     => '/',
            'httponly' => true,
            'samesite' => 'Lax',
            'secure'   => $secure,
        ));
    } else {
        session_set_cookie_params($life, '/; samesite=Lax', '', $secure, true);
    }
    session_name('codetj_sid');
    @session_start();
}

/** Корбари ҷорӣ ё null. */
function current_user()
{
    static $user = false;
    if ($user !== false) {
        return $user;
    }
    $user = null;
    if (!empty($_SESSION['uid'])) {
        $st = db()->prepare('SELECT * FROM cj_users WHERE id = ? AND banned = 0');
        $st->execute(array((int)$_SESSION['uid']));
        $u = $st->fetch();
        if ($u) {
            $user = $u;
        } else {
            unset($_SESSION['uid']);
        }
    }
    return $user;
}

function is_admin()
{
    $u = current_user();
    return $u !== null && $u['role'] === 'admin';
}

/** Серия (streak) — «попутно» ҳангоми ҳар воридшавӣ. */
function update_streak(&$user)
{
    $today = date('Y-m-d');
    if ($user['last_active_date'] === $today) {
        return;
    }
    $yesterday = date('Y-m-d', strtotime('-1 day'));
    $streak = ($user['last_active_date'] === $yesterday) ? ((int)$user['streak_days'] + 1) : 1;
    $st = db()->prepare('UPDATE cj_users SET streak_days = ?, last_active_date = ? WHERE id = ?');
    $st->execute(array($streak, $today, (int)$user['id']));
    $user['streak_days'] = $streak;
    $user['last_active_date'] = $today;
}

/** Рейтинги ҳафтаина ҳар душанбе «попутно» нул мешавад. */
function maybe_reset_week()
{
    $monday = date('Y-m-d', strtotime('monday this week'));
    if (setting_get('week_reset_date', '') !== $monday) {
        db()->exec('UPDATE cj_users SET week_points = 0');
        setting_set('week_reset_date', $monday);
    }
}

/* ---------- CSRF ---------- */

function csrf_token()
{
    if (empty($_SESSION['csrf'])) {
        if (function_exists('random_bytes')) {
            $_SESSION['csrf'] = bin2hex(random_bytes(32));
        } else {
            $_SESSION['csrf'] = md5(uniqid('', true) . mt_rand());
        }
    }
    return $_SESSION['csrf'];
}

function csrf_field()
{
    return '<input type="hidden" name="csrf" value="' . csrf_token() . '">';
}

function csrf_ok()
{
    $sent = isset($_POST['csrf']) ? $_POST['csrf'] : (isset($_SERVER['HTTP_X_CSRF']) ? $_SERVER['HTTP_X_CSRF'] : '');
    $have = isset($_SESSION['csrf']) ? $_SESSION['csrf'] : '';
    return is_string($sent) && $sent !== '' && $have !== '' && hash_equals($have, $sent);
}

/* ---------- Rate limit ---------- */

function client_ip()
{
    return substr(isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '0.0.0.0', 0, 45);
}

/** true — иҷозат ҳаст; false — лимит пур шуд. Сабтҳои кӯҳна «попутно» тоза мешаванд. */
function rate_limit($action, $maxHits, $windowSec)
{
    $pdo = db();
    if (mt_rand(1, 50) === 1) {
        $pdo->prepare('DELETE FROM cj_rate_limit WHERE created_at < DATE_SUB(NOW(), INTERVAL 2 DAY)')->execute();
    }
    $ip = client_ip();
    $st = $pdo->prepare(
        'SELECT COUNT(*) FROM cj_rate_limit WHERE ip = ? AND action = ? AND created_at > DATE_SUB(NOW(), INTERVAL ? SECOND)'
    );
    $st->execute(array($ip, $action, $windowSec));
    if ((int)$st->fetchColumn() >= $maxHits) {
        return false;
    }
    $pdo->prepare('INSERT INTO cj_rate_limit (ip, action) VALUES (?, ?)')->execute(array($ip, $action));
    return true;
}

/* ---------- Баллҳо ---------- */

function add_points($userId, $points, $reason)
{
    if ($points === 0) {
        return;
    }
    $pdo = db();
    $pdo->prepare('UPDATE cj_users SET points = points + ?, week_points = week_points + ? WHERE id = ?')
        ->execute(array($points, $points, $userId));
    $pdo->prepare('INSERT INTO cj_points_log (user_id, points, reason) VALUES (?, ?, ?)')
        ->execute(array($userId, $points, $reason));
}

/* ============================================================
 *  ЁРИРАСОНҲОИ УМУМӢ
 * ============================================================ */

/** Экранкунии HTML — ҳамеша барои маълумоти корбар. */
function e($s)
{
    return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
}

function redirect($url)
{
    if (!headers_sent()) {
        header('Location: ' . $url);
    } else {
        echo '<script>location.href=' . json_encode($url) . ';</script>';
    }
    exit;
}

function json_out(array $data, $code = 200)
{
    if (!headers_sent()) {
        http_response_code($code);
        header('Content-Type: application/json; charset=utf-8');
    }
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

/** Суроғаи сайт. Агар SITE_URL холӣ бошад — худаш аз дархост муайян мекунад. */
function site_url()
{
    if (SITE_URL !== '') {
        return rtrim(SITE_URL, '/');
    }
    $https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
          || (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https');
    $host = isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : 'localhost';
    $script = isset($_SERVER['SCRIPT_NAME']) ? $_SERVER['SCRIPT_NAME'] : '/';
    $dir = rtrim(str_replace('\\', '/', dirname($script)), '/');
    return ($https ? 'https://' : 'http://') . $host . $dir;
}
