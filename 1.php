<?php
/**
 * CodeTJ — хурдтарин файли санҷишӣ. / Самый маленький тестовый файл.
 *
 * Вазифа: фаҳмидан, ки сервер кадом папкаро мебинад.
 * Онро ба ҳар папкае, ки гумон дорӣ, гузор ва кушо: сайт.com/1.php
 *
 * Агар ин саҳифа кушода шавад — маҳз ҳамон папка дуруст аст,
 * ҳамаи файлҳои CodeTJ-ро ба ҳамон ҷо гузор.
 */
header('Content-Type: text/html; charset=utf-8');
$here = __DIR__;
$root = isset($_SERVER['DOCUMENT_ROOT']) ? $_SERVER['DOCUMENT_ROOT'] : '';
$same = ($root !== '' && rtrim($root, '/') === rtrim($here, '/'));
$files = array();
foreach (array('index.php', 'app.php', 'db.php', 'check.php') as $f) {
    $files[$f] = file_exists($here . '/' . $f);
}
$hasSeed = is_dir($here . '/seed');
?>
<!doctype html>
<html lang="tg"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>1.php — санҷиш</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0b1120;color:#e7edf7;
 margin:0;padding:20px;line-height:1.7}
.box{max-width:640px;margin:0 auto;background:#16223a;border:1px solid #243350;
 border-radius:16px;padding:24px}
h1{font-size:1.3rem;margin:0 0 6px;color:#22c55e}
p{margin:8px 0}
b{color:#38bdf8}
code{display:block;background:#0b1120;padding:10px 12px;border-radius:8px;color:#fbbf24;
 font-size:.82rem;word-break:break-all;margin:6px 0 14px}
ul{margin:6px 0;padding-left:20px}
.ru{color:#8fa0bd;font-size:.88rem;margin-top:18px;padding-top:14px;border-top:1px solid #243350}
</style></head><body><div class="box">
<h1>&#9989; Кор мекунад! PHP дар ин папка иҷро мешавад.</h1>

<p><b>Ин файл дар куҷост:</b></p>
<code><?= htmlspecialchars($here) ?></code>

<p><b>Сервер кадом папкаро мебинад:</b></p>
<code><?= $root === '' ? 'номаълум' : htmlspecialchars($root) ?></code>

<?php if ($same): ?>
  <p style="color:#22c55e"><b>&#10003; Папкаҳо мувофиқанд.</b> Ҳамаи файлҳои CodeTJ-ро маҳз ба ҳамин папка гузор.</p>
<?php elseif ($root !== ''): ?>
  <p style="color:#eab308"><b>&#9888; Папкаҳо мувофиқ нестанд.</b>
  Сервер папкаи болоиро мебинад. Файлҳоро ба папкаи дуюм гузор.</p>
<?php endif; ?>

<p><b>Дар ҳамин папка ҳозир ҳаст:</b></p>
<ul>
<?php foreach ($files as $f => $ok): ?>
  <li><?= htmlspecialchars($f) ?> — <?= $ok ? '<span style="color:#22c55e">ҳаст</span>' : '<span style="color:#ef4444">нест</span>' ?></li>
<?php endforeach; ?>
  <li>папкаи seed — <?= $hasSeed ? '<span style="color:#22c55e">ҳаст</span>' : '<span style="color:#ef4444">нест</span>' ?></li>
</ul>

<p><b>Суроғае, ки ту кушодӣ:</b></p>
<code><?= htmlspecialchars((isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : '?') . (isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '')) ?></code>

<p>Версияи PHP: <b><?= PHP_VERSION ?></b><?php
  if (version_compare(PHP_VERSION, '8.0.0', '<')) {
      echo ' <span style="color:#eab308">— кӯҳна, беҳтараш 8.1</span>';
  } ?></p>
<p>Сервер: <b><?= htmlspecialchars(isset($_SERVER['SERVER_SOFTWARE']) ? $_SERVER['SERVER_SOFTWARE'] : '?') ?></b></p>

<div class="ru">
  <b>По-русски:</b> если вы видите эту страницу — значит папка правильная и PHP работает.
  Кладите все файлы CodeTJ именно сюда. Скиньте этот экран целиком —
  по нему сразу видно, что делать дальше.
</div>
</div></body></html>
