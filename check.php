<?php
/**
 * CodeTJ — санҷиши ҳостинг / диагностика хостинга.
 *
 * Ин файлро ба ҳамон папка бор кунед ва кушоед: сайт.tj/check.php
 * Он мегӯяд, ки чӣ намерасад ва чиро дуруст кардан лозим аст.
 *
 * Дидаву дониста бо синтаксиси кӯҳнаи PHP навишта шудааст, то дар
 * ҳар версия кор кунад ва ҳамеша ҷавоб диҳад.
 *
 * ПАРОЛ ИН ҶО НИШОН ДОДА НАМЕШАВАД.
 * Баъд аз санҷиш ин файлро нест кардан беҳтар аст.
 */

header('Content-Type: text/html; charset=utf-8');

$rows = array();      // ҳар сатр: array(ном, ҳолат ok|warn|bad, матн)
$fatal = 0;
$warn = 0;

function add_row(&$rows, &$fatal, &$warn, $name, $state, $text)
{
    $rows[] = array($name, $state, $text);
    if ($state === 'bad') { $fatal++; }
    if ($state === 'warn') { $warn++; }
}

/* ---- 1. Версияи PHP ---- */
$php = PHP_VERSION;
if (version_compare($php, '8.0.0', '>=')) {
    add_row($rows, $fatal, $warn, 'Версияи PHP', 'ok', $php . ' — хуб аст');
} elseif (version_compare($php, '7.1.0', '>=')) {
    add_row($rows, $fatal, $warn, 'Версияи PHP', 'warn',
        $php . ' — кор мекунад, вале беҳтараш 8.1. Дар панели ҳостинг "PHP Selector" → 8.1');
} else {
    add_row($rows, $fatal, $warn, 'Версияи PHP', 'bad',
        $php . ' — хеле кӯҳна! Дар панели ҳостинг "PHP Selector" → 8.1-ро интихоб кунед. '
        . 'Маҳз аз ҳамин сабаб саҳифа сафед мемонад.');
}

/* ---- 2. Васеъкуниҳо ---- */
$need = array(
    'pdo_mysql' => 'ҳатмӣ — бе он база кор намекунад',
    'mbstring'  => 'ҳатмӣ — барои ҳарфҳои тоҷикӣ',
    'json'      => 'ҳатмӣ',
    'curl'      => 'барои санҷиши AI (Қисми 3)',
    'gd'        => 'барои аватарҳо (Қисми 4)',
);
foreach ($need as $ext => $why) {
    $has = extension_loaded($ext);
    $critical = in_array($ext, array('pdo_mysql', 'mbstring', 'json'));
    if ($has) {
        add_row($rows, $fatal, $warn, 'Васеъкунӣ ' . $ext, 'ok', 'фаъол');
    } else {
        add_row($rows, $fatal, $warn, 'Васеъкунӣ ' . $ext, $critical ? 'bad' : 'warn', 'нест — ' . $why);
    }
}

/* ---- 3. Файлҳо: мавҷуданд ва маҳз ҳамонанд? ---- */
// Ҳар файл аломати худро дорад. Агар аломат набошад — файли иштибоҳӣ бор шудааст.
$files = array(
    'index.php' => 'codetj_boot_page',
    'app.php'   => 'function t(',
    'db.php'    => 'function db(',
);
foreach ($files as $f => $mark) {
    $path = __DIR__ . '/' . $f;
    if (!file_exists($path)) {
        add_row($rows, $fatal, $warn, 'Файли ' . $f, 'bad', 'НЕСТ — онро ҳам бор кунед');
        continue;
    }
    $src = (string)file_get_contents($path);
    if (strpos($src, $mark) === false) {
        add_row($rows, $fatal, $warn, 'Файли ' . $f, 'bad',
            'ҳаст, вале ин файли ДИГАР аст! Файли дурусти ' . $f . '-ро аз нав бор кунед.');
        continue;
    }
    // Ду файл набояд якхела бошанд
    $dup = '';
    foreach ($files as $f2 => $m2) {
        if ($f2 !== $f && file_exists(__DIR__ . '/' . $f2)
            && md5_file(__DIR__ . '/' . $f2) === md5_file($path)) {
            $dup = $f2;
        }
    }
    if ($dup !== '') {
        add_row($rows, $fatal, $warn, 'Файли ' . $f, 'bad',
            'айнан бо ' . $dup . ' як хел аст — иштибоҳ шудааст, аз нав бор кунед');
        continue;
    }
    add_row($rows, $fatal, $warn, 'Файли ' . $f, 'ok', 'ҳаст (' . number_format(filesize($path)) . ' байт)');
}

/* ---- 4. .htaccess ---- */
if (file_exists(__DIR__ . '/.htaccess')) {
    add_row($rows, $fatal, $warn, 'Файли .htaccess', 'ok', 'ҳаст');
} else {
    add_row($rows, $fatal, $warn, 'Файли .htaccess', 'ok',
        'нест — дар nginx он лозим ҳам нест');
}

/* ---- 5. Папкаи uploads ---- */
$up = __DIR__ . '/uploads';
if (!is_dir($up)) {
    add_row($rows, $fatal, $warn, 'Папкаи uploads', 'ok', 'нест — ҳоло лозим нест (барои аватарҳо дар Қисми 4)');
} elseif (!is_writable($up)) {
    add_row($rows, $fatal, $warn, 'Папкаи uploads', 'warn', 'ҳаст, вале навиштан мумкин нест. Ҳуқуқро 755 гузоред.');
} else {
    add_row($rows, $fatal, $warn, 'Папкаи uploads', 'ok', 'ҳаст ва навиштан мумкин');
}

/* ---- 6. Файлҳои дарс ---- */
$lessonPhp = glob(__DIR__ . '/lessons*.php');
if ($lessonPhp) {
    $cntPhp = 0;
    foreach ($lessonPhp as $lf) {
        $d = @include $lf;
        if (is_array($d)) { $cntPhp += count($d); }
    }
    add_row($rows, $fatal, $warn, 'Файлҳои дарс (lessons*.php)', $cntPhp > 0 ? 'ok' : 'warn',
        count($lessonPhp) . ' файл, ' . $cntPhp . ' дарс');
} else {
    add_row($rows, $fatal, $warn, 'Файлҳои дарс (lessons*.php)', 'warn',
        'нестанд — lessons1.php ва lessons2.php-ро бор кунед');
}

$seed = __DIR__ . '/seed';
if (is_dir($seed)) {
    $js = glob($seed . '/*.json');
    $cnt = 0;
    $bad = array();
    foreach ((array)$js as $file) {
        $d = json_decode(file_get_contents($file), true);
        if (is_array($d)) {
            $cnt += count($d);
        } else {
            $bad[] = basename($file);
        }
    }
    if ($bad) {
        add_row($rows, $fatal, $warn, 'Дарсҳо (seed/)', 'warn',
            $cnt . ' дарс тайёр, вале ин файлҳо вайронанд: ' . implode(', ', $bad));
    } else {
        add_row($rows, $fatal, $warn, 'Дарсҳо (seed/)', 'ok', $cnt . ' дарс барои воридкунӣ тайёр');
    }
}

/* ---- 7. База ---- */
$dbOk = false;
$dbName = '';
$dbUser = '';
if (file_exists(__DIR__ . '/db.php')) {
    // Танҳо конфигурацияро мехонем, худи db.php-ро иҷро намекунем.
    $src = file_get_contents(__DIR__ . '/db.php');
    $get = function ($const) use ($src) {
        if (preg_match("/define\\(\\s*'" . $const . "'\\s*,\\s*'([^']*)'/", $src, $m)) {
            return $m[1];
        }
        return '';
    };
    $dbHost = $get('DB_HOST');
    $dbPort = $get('DB_PORT');
    $dbName = $get('DB_NAME');
    $dbUser = $get('DB_USER');
    $dbPass = $get('DB_PASS');
    if ($dbPort === '') { $dbPort = '3306'; }

    if ($dbName === '' || $dbUser === '') {
        add_row($rows, $fatal, $warn, 'Танзими база', 'bad',
            'дар db.php DB_NAME ё DB_USER холӣ аст — онҳоро пур кунед');
    } else {
        add_row($rows, $fatal, $warn, 'Танзими база', 'ok',
            'база: ' . htmlspecialchars($dbName) . ', корбар: ' . htmlspecialchars($dbUser)
            . ', парол: ' . ($dbPass === '' ? 'ХОЛӢ!' : str_repeat('*', 8)));

        if (extension_loaded('pdo_mysql')) {
            try {
                $pdo = new PDO(
                    'mysql:host=' . $dbHost . ';port=' . $dbPort . ';dbname=' . $dbName . ';charset=utf8mb4',
                    $dbUser, $dbPass,
                    array(PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_TIMEOUT => 5)
                );
                $dbOk = true;
                $ver = $pdo->query('SELECT VERSION()')->fetchColumn();
                add_row($rows, $fatal, $warn, 'Пайвасти база', 'ok', 'кор мекунад, MySQL ' . htmlspecialchars($ver));

                $tables = $pdo->query('SHOW TABLES')->fetchAll(PDO::FETCH_COLUMN);
                if (count($tables) === 0) {
                    add_row($rows, $fatal, $warn, 'Ҷадвалҳо', 'warn',
                        'ҳанӯз нестанд — саҳифаи асосиро кушоед, онҳо худкор сохта мешаванд');
                } else {
                    $mine = array();
                    foreach ($tables as $tn) {
                        if (strpos($tn, 'cj_') === 0) { $mine[] = $tn; }
                    }
                    if (count($mine) === 0) {
                        add_row($rows, $fatal, $warn, 'Ҷадвалҳои CodeTJ', 'warn',
                            'ҳанӯз нестанд — саҳифаи асосиро кушоед, худашон сохта мешаванд');
                    } else {
                        add_row($rows, $fatal, $warn, 'Ҷадвалҳои CodeTJ', 'ok',
                            count($mine) . ' ҷадвали cj_ (дар база ҳамагӣ ' . count($tables) . ' ҷадвал, боқимонда аз лоиҳаҳои дигар)');
                    }
                }
                if (in_array('cj_users', $tables)) {
                    $u = (int)$pdo->query('SELECT COUNT(*) FROM cj_users')->fetchColumn();
                    add_row($rows, $fatal, $warn, 'Корбарон', 'ok',
                        $u . ' нафар' . ($u === 0 ? ' — саҳифаро кушоед ва администратор созед' : ''));
                }
                if (in_array('cj_lessons', $tables)) {
                    $l = (int)$pdo->query('SELECT COUNT(*) FROM cj_lessons')->fetchColumn();
                    add_row($rows, $fatal, $warn, 'Дарсҳо дар база', $l > 0 ? 'ok' : 'warn', $l . ' дарс');
                }
            } catch (Exception $ex) {
                add_row($rows, $fatal, $warn, 'Пайвасти база', 'bad',
                    'НАШУД: ' . htmlspecialchars($ex->getMessage())
                    . ' — ном/корбар/паролро дар db.php тафтиш кунед');
            }
        }
    }
}

/* ---- 8. Роҳҳо: кадом папкаро сервер мебинад ---- */
$here = __DIR__;
$docroot = isset($_SERVER['DOCUMENT_ROOT']) ? $_SERVER['DOCUMENT_ROOT'] : '';
add_row($rows, $fatal, $warn, 'Ин файл дар куҷост', 'ok', htmlspecialchars($here));
add_row($rows, $fatal, $warn, 'Папкаи сайт (DOCUMENT_ROOT)', 'ok',
    $docroot === '' ? 'номаълум' : htmlspecialchars($docroot));
if ($docroot !== '' && rtrim($docroot, '/') !== rtrim($here, '/')) {
    add_row($rows, $fatal, $warn, 'Мувофиқати папкаҳо', 'warn',
        'файл дар папкаи дигар аст. Сервер папкаи болоиро мебинад — '
        . 'файлҳоро маҳз ба он ҷо гузоред.');
} else {
    add_row($rows, $fatal, $warn, 'Мувофиқати папкаҳо', 'ok', 'файлҳо дар ҳамон ҷое, ки сервер мебинад');
}
add_row($rows, $fatal, $warn, 'Суроғаи ҷорӣ', 'ok',
    htmlspecialchars((isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : '?')
    . (isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '')));

/* ---- 9. Иловагӣ ---- */
add_row($rows, $fatal, $warn, 'Сервер', 'ok',
    htmlspecialchars(isset($_SERVER['SERVER_SOFTWARE']) ? $_SERVER['SERVER_SOFTWARE'] : 'номаълум'));
add_row($rows, $fatal, $warn, 'Хотира (memory_limit)', 'ok', ini_get('memory_limit'));
add_row($rows, $fatal, $warn, 'Кодировкаи файл', 'ok',
    'ҳарфҳои тоҷикӣ: ӣ ӯ ҳ қ ғ ҷ — агар ин ҷо аломати савол бошад, файл дар UTF-8 нест');

$icons = array('ok' => '&#9989;', 'warn' => '&#9888;&#65039;', 'bad' => '&#10060;');
$colors = array('ok' => '#22c55e', 'warn' => '#eab308', 'bad' => '#ef4444');
?>
<!doctype html>
<html lang="tg">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CodeTJ — санҷиши ҳостинг</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0b1120;color:#e7edf7;
 margin:0;padding:20px;line-height:1.6}
.box{max-width:820px;margin:0 auto}
h1{font-size:1.4rem;margin:0 0 6px}
.sub{color:#8fa0bd;font-size:.9rem;margin-bottom:20px}
.verdict{border-radius:14px;padding:18px;margin-bottom:20px;font-weight:600}
.v-ok{background:rgba(34,197,94,.15);border:1px solid #22c55e}
.v-bad{background:rgba(239,68,68,.15);border:1px solid #ef4444}
.v-warn{background:rgba(234,179,8,.15);border:1px solid #eab308}
table{width:100%;border-collapse:collapse;background:#16223a;border-radius:14px;overflow:hidden}
td{padding:11px 14px;border-bottom:1px solid #243350;vertical-align:top;font-size:.9rem}
tr:last-child td{border-bottom:0}
td:first-child{font-weight:700;white-space:nowrap;width:1%}
.ic{width:1%;text-align:center}
.note{margin-top:22px;background:#16223a;border:1px solid #243350;border-radius:14px;padding:18px;font-size:.9rem}
.note b{color:#38bdf8}
code{background:#0b1120;padding:2px 7px;border-radius:6px;color:#fbbf24;font-size:.86em}
a{color:#38bdf8}
</style>
</head>
<body>
<div class="box">
  <h1>&#128295; CodeTJ — санҷиши ҳостинг</h1>
  <div class="sub">Диагностика хостинга. Файлро баъд аз санҷиш нест кунед / удалите файл после проверки.</div>

  <?php if ($fatal > 0): ?>
    <div class="verdict v-bad">&#10060; <?= $fatal ?> мушкилии ҷиддӣ ёфт шуд. Сайт то ислоҳи онҳо кор намекунад.
    Дар ҷадвали поён сатрҳои сурхро бинед.</div>
  <?php elseif ($warn > 0): ?>
    <div class="verdict v-warn">&#9888;&#65039; Ҳама чизи асосӣ хуб аст, вале <?= $warn ?> огоҳӣ ҳаст. Сайт кор мекунад.</div>
  <?php else: ?>
    <div class="verdict v-ok">&#9989; Ҳама чиз тайёр! Ҳозир саҳифаи асосиро кушоед: <a href="index.php">index.php</a></div>
  <?php endif; ?>

  <table>
    <?php foreach ($rows as $r): ?>
      <tr>
        <td class="ic" style="color:<?= $colors[$r[1]] ?>"><?= $icons[$r[1]] ?></td>
        <td><?= $r[0] ?></td>
        <td style="color:<?= $r[1] === 'ok' ? '#8fa0bd' : $colors[$r[1]] ?>"><?= $r[2] ?></td>
      </tr>
    <?php endforeach; ?>
  </table>

  <div class="note">
    <p><b>Агар саҳифаи сайт сафед бошад</b> — аксаран версияи PHP кӯҳна аст.
    Дар панели somonhost бахши <b>PHP Selector</b> ё <b>Интихоби версияи PHP</b>-ро ёбед ва <b>8.1</b>-ро интихоб кунед.</p>
    <p><b>Агар сайти кӯҳна кушода шавад</b> — файли <code>.htaccess</code> бор нашудааст.
    Дар файловый менеджер <b>Show Hidden Files</b>-ро фаъол кунед, ё файли <code>index.html</code>-ро
    ба <code>portfolio.html</code> иваз кунед.</p>
    <p style="color:#8fa0bd;margin-top:12px">По-русски: если сайт белый — на хостинге старая версия PHP,
    поставьте 8.1 в PHP Selector. Если открывается старое портфолио — не загрузился .htaccess,
    включите показ скрытых файлов или переименуйте index.html в portfolio.html.</p>
  </div>
</div>
</body>
</html>
