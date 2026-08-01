<?php
// Загрузчик установщика Cargo Bot. Скачивает setup.php и открывает его.
$u = 'https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/'
   . 'claude/tariff-management-admin-panel-6ojoo2/cargo_bot_php/setup.php';
$c = curl_init($u);
curl_setopt_array($c, [CURLOPT_RETURNTRANSFER => 1, CURLOPT_FOLLOWLOCATION => 1, CURLOPT_TIMEOUT => 30]);
$body = curl_exec($c);
$code = (int) curl_getinfo($c, CURLINFO_HTTP_CODE);
curl_close($c);
if ($code === 200 && $body && file_put_contents(__DIR__ . '/setup.php', $body)) {
    header('Location: setup.php');
    exit;
}
echo 'Не удалось скачать установщик (код ' . $code . '). Проверьте, что хостинг '
   . 'разрешает исходящие запросы к github.com, или создайте setup.php вручную.';
