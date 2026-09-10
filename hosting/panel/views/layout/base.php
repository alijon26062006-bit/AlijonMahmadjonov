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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap">
<style>
  /* Светлая тема панели. Все цвета — здесь, ни один экран не задаёт свой hex:
     поменять палитру = поменять этот блок. */
  :root {
    color-scheme: light;

    --bg:#F5F7FD;            /* фон страницы */
    --bg-soft:#EEF2FC;       /* чередующиеся секции */
    --surface:#FFFFFF;       /* карточки */
    --surface-2:#F4F7FE;     /* мягкая карточка внутри белой секции */
    --text:#0E1A38;          /* тёмно-синий, а не чёрный */
    --muted:#64748B;
    --border:#E3E9F6;

    --primary:#2563EB;
    --primary-600:#1D4ED8;
    --primary-soft:#EAF1FE;
    --on-primary:#FFFFFF;

    --success:#16A34A;  --success-soft:#E7F8EF;
    --danger:#DC2626;   --danger-soft:#FDECEC;
    --warning:#EA580C;  --warning-soft:#FEF3E2;
    --purple:#7C3AED;   --purple-soft:#F3EDFE;

    --r-sm:10px; --r-md:14px; --r-lg:20px; --r-xl:24px;
    --shadow-sm:0 1px 2px rgba(14,26,56,.05);
    --shadow-md:0 6px 20px rgba(14,26,56,.06);
    --shadow-primary:0 10px 28px rgba(37,99,235,.28);

    /* Плотный шрифт из скриншота-образца; системный стек — запасной,
       чтобы страница не ждала загрузки и не ломалась без интернета. */
    --font:"Plus Jakarta Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  }

  * { box-sizing:border-box; }
  html { -webkit-text-size-adjust:100%; }
  body { margin:0; font:400 15px/1.6 var(--font); background:var(--bg); color:var(--text);
         -webkit-font-smoothing:antialiased; }
  a { color:var(--primary); text-decoration:none; }
  a:hover { text-decoration:underline; }
  h1,h2,h3,h4 { letter-spacing:-.02em; line-height:1.2; font-weight:800; }

  /* ── шапка ─────────────────────────────────────────────────────────── */
  header.top { position:sticky; top:0; z-index:50; display:flex; align-items:center;
               justify-content:space-between; gap:12px; flex-wrap:wrap;
               padding:12px 20px; background:rgba(255,255,255,.88);
               backdrop-filter:blur(12px); border-bottom:1px solid var(--border); }
  header.top .brand { display:flex; align-items:center; gap:10px; font-size:19px;
                      font-weight:800; letter-spacing:-.02em; color:var(--text); }
  header.top .brand:hover { text-decoration:none; }
  .brand-mark { display:grid; place-items:center; width:38px; height:38px; border-radius:11px;
                background:linear-gradient(135deg,#3B82F6,#2563EB); color:#fff;
                box-shadow:0 4px 12px rgba(37,99,235,.35); }
  .brand-mark svg { width:20px; height:20px; }
  .brand em { font-style:normal; color:var(--primary); }

  nav.tabs { display:flex; gap:4px; flex-wrap:wrap; padding:8px 20px;
             background:var(--surface); border-bottom:1px solid var(--border); }
  nav.tabs a { padding:8px 14px; border-radius:var(--r-sm); color:var(--muted);
               font-size:14px; font-weight:600; }
  nav.tabs a:hover { background:var(--primary-soft); color:var(--primary); text-decoration:none; }

  main { max-width:1000px; margin:0 auto; padding:20px; }

  /* ── компоненты ────────────────────────────────────────────────────── */
  .card { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-lg);
          padding:22px; margin-bottom:18px; box-shadow:var(--shadow-sm); }

  .flash { padding:12px 16px; border-radius:var(--r-md); margin-bottom:14px; font-size:14px;
           font-weight:500; border:1px solid transparent; }
  .flash.error   { background:var(--danger-soft);  color:#991B1B; border-color:#F7C9C9; }
  .flash.success { background:var(--success-soft); color:#14532D; border-color:#BBE9CD; }

  table { width:100%; border-collapse:collapse; font-size:14px; }
  th, td { text-align:left; padding:11px 8px; border-bottom:1px solid var(--border); }
  th { color:var(--muted); font-weight:600; font-size:13px; text-transform:uppercase;
       letter-spacing:.04em; }

  input, select, textarea { width:100%; padding:11px 13px; border-radius:var(--r-md);
    border:1px solid var(--border); background:var(--surface); color:var(--text);
    font:inherit; font-size:15px; }
  input:focus, select:focus, textarea:focus { outline:none; border-color:var(--primary);
    box-shadow:0 0 0 3px rgba(37,99,235,.15); }
  label { display:block; margin:14px 0 6px; font-size:13px; font-weight:600; color:var(--muted); }

  button, .btn { display:inline-flex; align-items:center; justify-content:center; gap:8px;
    padding:11px 20px; border-radius:var(--r-md); border:1px solid transparent;
    background:var(--primary); color:var(--on-primary); font:inherit; font-weight:700;
    font-size:15px; cursor:pointer; transition:background .18s, box-shadow .18s, border-color .18s; }
  button:hover, .btn:hover { background:var(--primary-600); text-decoration:none; }
  button.secondary, .btn.secondary { background:var(--surface); color:var(--text); border-color:var(--border); }
  button.secondary:hover, .btn.secondary:hover { background:var(--surface-2); border-color:#C7D5F0; }
  button.danger, .btn.danger { background:var(--danger); color:#fff; }
  button:disabled { opacity:.5; cursor:not-allowed; }
  :focus-visible { outline:2px solid var(--primary); outline-offset:2px; }

  .badge { display:inline-block; padding:4px 10px; border-radius:999px; font-size:12px; font-weight:700; }
  .badge.active { background:var(--success-soft); color:#14532D; }
  .badge.pending { background:var(--warning-soft); color:#9A3412; }
  .badge.suspended { background:var(--danger-soft); color:#991B1B; }

  code, pre { background:var(--surface-2); border:1px solid var(--border); border-radius:8px;
              padding:2px 7px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.92em; }
  pre { padding:14px; overflow-x:auto; }
  .muted { color:var(--muted); font-size:14px; }

  @media (prefers-reduced-motion:reduce) {
    * { animation-duration:.01ms !important; transition-duration:.01ms !important; }
  }
</style>
</head>
<body>
<header class="top">
  <a class="brand" href="<?= $currentUser ? '/dashboard' : '/' ?>">
    <span class="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 9.5 12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5Z"/>
      </svg>
    </span>
    <?php // Второе слово названия — синим, как в образце. Если слово одно, красим целиком.
      $brandParts = preg_split('~(?=[A-ZА-Я])~u', $panelName, -1, PREG_SPLIT_NO_EMPTY) ?: [$panelName];
      $brandTail = count($brandParts) > 1 ? array_pop($brandParts) : '';
    ?>
    <span><?= Html::e(implode('', $brandParts)) ?><em><?= Html::e($brandTail) ?></em></span>
  </a>
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
