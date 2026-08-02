<?php
/**
 * CodeTJ — нуқтаи вуруд (bootstrap).
 *
 * ДИҚҚАТ: ин файл дидаву дониста бо синтаксиси КӮҲНАИ PHP навишта шудааст
 * (бе type hint, бе массиви кӯтоҳ), то дар ҳар версияи PHP кушода шавад.
 * Вазифаи он як чиз аст: агар дар ҷое хато бошад, ба ҷои экрани сафед
 * паёми фаҳмо нишон диҳад.
 *
 * Тамоми барнома дар app.php ҷойгир аст.
 */

define('CODETJ_MIN_PHP', '7.1.0');

/* ---------- 1. Версияи PHP ---------- */
if (version_compare(PHP_VERSION, CODETJ_MIN_PHP, '<')) {
    codetj_boot_page(
        'Версияи PHP кӯҳна аст',
        'Дар ҳостинг версияи PHP <b>' . PHP_VERSION . '</b> кор карда истодааст, аммо ба CodeTJ на кам аз <b>8.0</b> лозим аст.'
        . '<br><br>Дар панели ҳостинг бахши <b>PHP Selector</b> ё <b>Интихоби версияи PHP</b>-ро ёбед ва <b>8.1</b> ё <b>8.2</b>-ро интихоб кунед.',
        'На хостинге работает PHP ' . PHP_VERSION . ', а платформе нужен минимум 8.0. В панели хостинга найдите "PHP Selector" / "Выбор версии PHP" и поставьте 8.1 или 8.2.'
    );
}

/* ---------- 2. Хатоҳо: ба корбар не, ба паёми фаҳмо ҳа ---------- */
@ini_set('display_errors', '0');
@ini_set('log_errors', '1');
error_reporting(E_ALL);

set_exception_handler('codetj_exception_handler');
register_shutdown_function('codetj_shutdown_handler');

/* ---------- 3. Худи барнома ---------- */
$codetj_app = __DIR__ . '/app.php';
if (!file_exists($codetj_app)) {
    codetj_boot_page(
        'Файли app.php ёфт нашуд',
        'Ба ҳостинг ҳамаи файлҳо бор нашудаанд. Файли <b>app.php</b>-ро ҳам ба ҳамон папка бор кунед, ки дар он index.php ҳаст.',
        'Файл app.php не загружен. Загрузите его в ту же папку, где лежит index.php.'
    );
}
// Тафтиш мекунем, ки маҳз app.php аст, на файли дигар бо ҳамин ном.
$codetj_src = (string)file_get_contents($codetj_app);
if (strpos($codetj_src, 'function t(') === false) {
    codetj_boot_page(
        'Файли app.php нодуруст аст',
        'Дар папка ба ҷои <b>app.php</b> файли дигар хобидааст. Файли дурусти <b>app.php</b>-ро аз нав бор кунед.',
        'Вместо app.php лежит другой файл. Загрузите правильный app.php заново.'
    );
}
unset($codetj_src);
require $codetj_app;

/* ============================================================
 *  ФУНКСИЯҲОИ ХАТО
 * ============================================================ */

/** Ҳама гуна Exception/Error — ба саҳифаи фаҳмо. */
function codetj_exception_handler($ex)
{
    $msg = $ex->getMessage();
    $where = codetj_short_path($ex->getFile()) . ':' . $ex->getLine();
    error_log('CodeTJ: ' . $msg . ' @ ' . $where);
    codetj_boot_page(
        'Дар сайт хато рӯй дод',
        'Ин хатои барнома аст, на хатои ту. Матни зериро нусха бигир ва ба созанда фирист.',
        'Это ошибка программы. Скопируйте текст ниже и отправьте разработчику.',
        get_class($ex) . ': ' . $msg . "\n" . $where
    );
}

/** Хатоҳои марговар (аз ҷумла parse error дар app.php ё db.php). */
function codetj_shutdown_handler()
{
    $e = error_get_last();
    if ($e === null) {
        return;
    }
    $fatal = array(E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR, E_USER_ERROR);
    if (!in_array($e['type'], $fatal)) {
        return;
    }
    if (headers_sent()) {
        echo '<div style="background:#7f1d1d;color:#fff;padding:16px;font-family:monospace;font-size:13px">'
           . htmlspecialchars($e['message'], ENT_QUOTES, 'UTF-8') . '</div>';
        return;
    }
    $hint = '';
    if (strpos($e['message'], 'syntax error') !== false || $e['type'] === E_PARSE) {
        $hint = '<br><br>Аксаран ин маънои онро дорад, ки версияи PHP кӯҳна аст. '
              . 'Дар панели ҳостинг PHP <b>8.1</b>-ро интихоб кунед.';
    }
    codetj_boot_page(
        'Дар сайт хатои ҷиддӣ рӯй дод',
        'Матни зериро нусха бигир ва ба созанда фирист.' . $hint,
        'Скопируйте текст ниже и отправьте разработчику. Часто причина — старая версия PHP, поставьте 8.1.',
        $e['message'] . "\n" . codetj_short_path($e['file']) . ':' . $e['line']
    );
}

/** Роҳи файлро кӯтоҳ мекунад, то роҳи пурраи сервер ошкор нашавад. */
function codetj_short_path($path)
{
    return basename(dirname($path)) . '/' . basename($path);
}

/** Саҳифаи хато — оддӣ, бе база, бе вобастагӣ. */
function codetj_boot_page($titleTj, $helpTj, $helpRu, $detail = '')
{
    if (!headers_sent()) {
        if (function_exists('http_response_code')) {
            http_response_code(503);
        }
        header('Content-Type: text/html; charset=utf-8');
    }
    echo '<!doctype html><html lang="tg"><head><meta charset="utf-8">'
       . '<meta name="viewport" content="width=device-width,initial-scale=1">'
       . '<title>CodeTJ</title><style>'
       . 'body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0b1120;color:#e7edf7;'
       . 'display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px;line-height:1.7}'
       . '.box{max-width:680px;width:100%;background:#16223a;border:1px solid #243350;border-radius:16px;padding:28px}'
       . 'h1{font-size:1.3rem;margin:0 0 14px}b{color:#38bdf8}'
       . '.ru{color:#8fa0bd;font-size:.9rem;margin-top:16px;padding-top:14px;border-top:1px solid #243350}'
       . 'pre{background:#0b1120;padding:12px;border-radius:8px;white-space:pre-wrap;word-break:break-word;'
       . 'color:#f87171;font-size:.78rem;margin-top:14px}'
       . '.hint{background:#0b1120;border-radius:10px;padding:12px 14px;margin-top:16px;font-size:.88rem;color:#8fa0bd}'
       . '</style></head><body><div class="box">'
       . '<h1>&#9888;&#65039; ' . $titleTj . '</h1><p>' . $helpTj . '</p>';
    if ($detail !== '') {
        echo '<pre>' . htmlspecialchars($detail, ENT_QUOTES, 'UTF-8') . '</pre>';
    }
    echo '<div class="ru">' . htmlspecialchars($helpRu, ENT_QUOTES, 'UTF-8') . '</div>'
       . '<div class="hint">Санҷиши пурраи ҳостинг: файли <b>check.php</b>-ро кушоед &mdash; '
       . 'он мегӯяд, ки чӣ намерасад.<br>Полная диагностика хостинга: откройте <b>check.php</b></div>'
       . '</div></body></html>';
    exit;
}
