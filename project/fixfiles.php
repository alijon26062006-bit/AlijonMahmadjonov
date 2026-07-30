<?php
/**
 * Avtoremont PHP-faylov na servere.
 *
 * Ischet fayly, u kotorykh isporchen zagolovok:
 *   - BOM ili probely/perevody stroki pered <?php
 *   - poteryan otkryvayushchiy teg (fayl nachinaetsya s "php")
 * i vosstanavlivaet ikh.
 *
 * Otkryt:  https://vash-domen/kino/fixfiles.php?key=WEBHOOK_SECRET
 * Posle remonta UDALITE etot fayl.
 */

header('Content-Type: text/plain; charset=utf-8');

$config = require __DIR__ . '/config/config.php';
if (($_GET['key'] ?? '') !== $config['telegram']['webhook_secret']) {
    http_response_code(403);
    exit("Dostup zapreshen. Otkroyte: fixfiles.php?key=WEBHOOK_SECRET\n");
}

$root = __DIR__;

/** Rekursivno sobiraem vse .php fayly proekta. */
$files = [];
$it = new RecursiveIteratorIterator(
    new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS)
);
foreach ($it as $f) {
    if ($f->isFile() && strtolower($f->getExtension()) === 'php') {
        $files[] = $f->getPathname();
    }
}
sort($files);

$fixed = [];
$okCount = 0;
$failed = [];

foreach ($files as $path) {
    $src = @file_get_contents($path);
    if ($src === false || $src === '') {
        continue;
    }

    $orig = $src;
    $note = [];

    // 1. Ubiraem BOM.
    if (str_starts_with($src, "\xEF\xBB\xBF")) {
        $src = substr($src, 3);
        $note[] = 'BOM';
    }

    // 2. Poteryan "<?" v nachale: fayl nachinaetsya s "php" + perevod stroki.
    if (!str_starts_with($src, '<?php') && preg_match('/^php\s/', $src)) {
        $src = '<?' . $src;
        $note[] = 'vosstanovlen <?php';
    }

    // 3. Musor (probely/stroki/simvoly) pered pervym <?php.
    if (!str_starts_with($src, '<?php')) {
        $pos = strpos($src, '<?php');
        if ($pos !== false && $pos < 200) {
            $src = substr($src, $pos);
            $note[] = 'ubran musor pered <?php';
        }
    }

    // 4. Ubiraem declare(strict_types=1): eta stroka daet fatalnuyu oshibku
    //    pri lyubom lishnem bayte pered <?php. Bez nee kod rabotaet tak zhe.
    if (preg_match('/^[ \t]*declare[ \t]*\([ \t]*strict_types[ \t]*=[ \t]*1[ \t]*\)[ \t]*;[ \t]*$/m', $src)) {
        $src = preg_replace(
            '/^[ \t]*declare[ \t]*\([ \t]*strict_types[ \t]*=[ \t]*1[ \t]*\)[ \t]*;[ \t]*\R/m',
            '',
            $src,
            1
        );
        $note[] = 'ubran strict_types';
    }

    if ($src === $orig) {
        $okCount++;
        continue;
    }

    // Proveryaem sintaksis pered zapisyu: ne lomaem rabochie fayly.
    $tmp = $path . '.fixcheck';
    @file_put_contents($tmp, $src);
    $out = [];
    $code = 0;
    @exec('php -l ' . escapeshellarg($tmp) . ' 2>&1', $out, $code);
    @unlink($tmp);

    $syntaxOk = ($code === 0) || (!$out && $code === 127); // 127 = net CLI php, propuskaem proverku

    if (!$syntaxOk) {
        $failed[] = substr($path, strlen($root) + 1) . ' -> ' . implode(' ', $out);
        continue;
    }

    // Rezervnaya kopiya i zapis.
    @copy($path, $path . '.bak');
    if (@file_put_contents($path, $src) !== false) {
        $fixed[] = substr($path, strlen($root) + 1) . '  [' . implode(', ', $note) . ']';
    } else {
        $failed[] = substr($path, strlen($root) + 1) . ' -> net prav na zapis';
    }
}

echo "=== REMONT FAYLOV ===\n";
echo 'Vsego PHP-faylov: ' . count($files) . "\n";
echo 'Byli v poryadke:  ' . $okCount . "\n";
echo 'Pochineno:        ' . count($fixed) . "\n\n";

if ($fixed) {
    echo "POCHINENY:\n";
    foreach ($fixed as $f) {
        echo '  ' . $f . "\n";
    }
    echo "\n(ryadom sozdany kopii .bak - ikh mozhno udalit)\n\n";
}

if ($failed) {
    echo "NE UDALOS POCHINIT:\n";
    foreach ($failed as $f) {
        echo '  ' . $f . "\n";
    }
    echo "\nEti fayly nuzhno zagruzit zanovo.\n\n";
}

if (!$fixed && !$failed) {
    echo "Vse fayly v poryadke - remont ne trebuetsya.\n\n";
}

// Diagnostika: pokazyvaem nachalo klyuchevogo fayla pobaytno.
$probe = $root . '/bot/Bot.php';
if (is_file($probe)) {
    $head = (string) file_get_contents($probe, false, null, 0, 60);
    echo "=== NACHALO bot/Bot.php (pervye baytu) ===\n";
    echo 'HEX:  ' . trim(chunk_split(strtoupper(bin2hex($head)), 2, ' ')) . "\n";
    $vis = '';
    for ($i = 0, $n = strlen($head); $i < $n; $i++) {
        $ch = $head[$i];
        $o  = ord($ch);
        $vis .= $ch === "\n" ? '\\n' : ($ch === "\r" ? '\\r' : ($o < 32 || $o > 126 ? '[' . $o . ']' : $ch));
    }
    echo 'TEKST: ' . $vis . "\n\n";
}

echo "Teper otkroyte bottest.php i proverte bota.\n";
echo "Posle remonta UDALITE fixfiles.php\n";
