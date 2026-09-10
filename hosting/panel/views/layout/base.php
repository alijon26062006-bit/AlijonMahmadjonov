<?php
/** @var string $content
 *  @var array{email?:string,display_name?:string,role?:string}|null $currentUser
 *  @var string $panelName
 *  @var list<array{type:string,text:string}> $flashes
 */
$currentUser ??= null;
$panelName ??= 'AlijonHost';
$flashes ??= [];
use Hosting\Support\Html;
?>
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title><?= Html::e($panelName) ?></title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root { color-scheme: light dark; --bg:#0f172a; --panel:#1e293b; --text:#e2e8f0; --muted:#94a3b8;
          --accent:#22c55e; --danger:#ef4444; --border:#334155; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.5 system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); }
  a { color:#60a5fa; }
  header.top { display:flex; align-items:center; justify-content:space-between; padding:12px 16px;
               background:var(--panel); border-bottom:1px solid var(--border); flex-wrap:wrap; gap:8px; }
  header.top .brand { font-weight:700; }
  nav.tabs { display:flex; gap:4px; flex-wrap:wrap; padding:8px 16px; background:var(--panel);
             border-bottom:1px solid var(--border); }
  nav.tabs a { padding:6px 10px; border-radius:8px; text-decoration:none; color:var(--muted); font-size:14px; }
  nav.tabs a:hover { background:#0f172a; color:var(--text); }
  main { max-width:960px; margin:0 auto; padding:16px; }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:16px; margin-bottom:16px; }
  .flash { padding:10px 14px; border-radius:8px; margin-bottom:12px; font-size:14px; }
  .flash.error { background:#450a0a; color:#fecaca; border:1px solid #7f1d1d; }
  .flash.success { background:#052e16; color:#bbf7d0; border:1px solid #14532d; }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th, td { text-align:left; padding:8px; border-bottom:1px solid var(--border); }
  input, select { width:100%; padding:8px 10px; border-radius:8px; border:1px solid var(--border);
                  background:#0f172a; color:var(--text); font-size:14px; }
  label { display:block; margin:10px 0 4px; font-size:13px; color:var(--muted); }
  button, .btn { display:inline-block; padding:8px 14px; border-radius:8px; border:1px solid var(--border);
                 background:var(--accent); color:#052e16; font-weight:600; cursor:pointer; text-decoration:none; font-size:14px; }
  button.secondary, .btn.secondary { background:transparent; color:var(--text); }
  button.danger, .btn.danger { background:var(--danger); color:#fff; }
  .badge { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; }
  .badge.active { background:#052e16; color:#bbf7d0; }
  .badge.pending { background:#422006; color:#fed7aa; }
  .badge.suspended { background:#450a0a; color:#fecaca; }
  code, pre { background:#0f172a; border:1px solid var(--border); border-radius:6px; padding:2px 6px; }
  pre { padding:10px; overflow-x:auto; }
  .muted { color:var(--muted); font-size:13px; }
</style>
</head>
<body>
<header class="top">
  <div class="brand"><?= Html::e($panelName) ?></div>
  <?php if ($currentUser): ?>
    <div class="muted">
      <?= Html::e($currentUser['display_name'] ?? $currentUser['email'] ?? '') ?>
      · <a href="/logout" onclick="return true">Выйти</a>
    </div>
  <?php endif; ?>
</header>
<?php if ($currentUser): ?>
<nav class="tabs">
  <a href="/dashboard">Обзор</a>
  <a href="/sites">Сайты</a>
  <a href="/databases">Базы данных</a>
  <a href="/backups">Бэкапы</a>
  <?php if (($currentUser['role'] ?? '') === 'admin'): ?><a href="/admin">Админ</a><?php endif; ?>
</nav>
<?php endif; ?>
<main>
  <?php foreach ($flashes as $flash): ?>
    <div class="flash <?= Html::e($flash['type']) ?>"><?= Html::e($flash['text']) ?></div>
  <?php endforeach; ?>
  <?= $content ?>
</main>
</body>
</html>
