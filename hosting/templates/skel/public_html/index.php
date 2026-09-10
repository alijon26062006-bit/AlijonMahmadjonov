<?php
// Стартовая страница нового сайта. Замените её своим кодом —
// или загрузите файлы через файловый менеджер панели.
$domain = $_SERVER['HTTP_HOST'] ?? 'сайт';
?>
<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= htmlspecialchars($domain, ENT_QUOTES) ?> — сайт работает</title>
<style>
  body { font: 16px/1.6 system-ui, sans-serif; margin: 0; display: grid;
         place-items: center; min-height: 100vh; background: #0f172a; color: #e2e8f0; }
  .card { max-width: 34rem; padding: 2rem; background: #1e293b;
          border-radius: 14px; box-shadow: 0 10px 40px rgb(0 0 0 / .35); }
  h1 { margin: 0 0 .5rem; font-size: 1.5rem; }
  code { background: #0f172a; padding: .15rem .4rem; border-radius: 5px; }
  .muted { color: #94a3b8; font-size: .9rem; }
</style>
<div class="card">
  <h1>Сайт <?= htmlspecialchars($domain, ENT_QUOTES) ?> работает</h1>
  <p>PHP <?= PHP_VERSION ?> отвечает на запросы. Файлы сайта лежат в
     каталоге <code>public_html</code>.</p>
  <p class="muted">Эта страница — файл <code>index.php</code>. Удалите или
     замените его, когда зальёте свой проект.</p>
</div>
