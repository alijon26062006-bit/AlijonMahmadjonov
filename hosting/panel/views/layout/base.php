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

  /* ── шапка с балансом ──────────────────────────────────────────────── */
  header.top .top-title { flex:1 1 auto; font-weight:800; font-size:18px; letter-spacing:-.01em; }
  header.top .top-right { display:flex; align-items:center; gap:8px; flex:none; }
  .chip { padding:9px 14px; border-radius:999px; background:var(--primary-soft);
          color:var(--primary); font-weight:800; font-size:14px; white-space:nowrap; }
  .chip:hover { text-decoration:none; }
  header.top .top-right .btn { padding:9px 16px; font-size:14px; white-space:nowrap; }

  .burger { display:flex; flex-direction:column; justify-content:center; gap:4px;
            width:40px; height:40px; flex:none; padding:9px 8px; border-radius:10px; }
  .burger:hover { background:var(--surface-2); }
  .burger span { display:block; height:2.5px; border-radius:2px; background:var(--text); }

  /* ── меню-шторка ───────────────────────────────────────────────────── */
  /* Открывается по :target — то есть работает без JavaScript. Скрипт мог не
     загрузиться, а меню в панели управления обязано открываться всегда. */
  .drawer { position:fixed; inset:0 auto 0 0; width:min(84vw,300px); z-index:70;
            background:var(--surface); border-right:1px solid var(--border);
            transform:translateX(-102%); transition:transform .22s ease;
            display:flex; flex-direction:column; overflow-y:auto; }
  .drawer:target { transform:none; box-shadow:0 0 60px rgba(14,26,56,.25); }
  .drawer-scrim { position:fixed; inset:0; z-index:69; background:rgba(14,26,56,.45);
                  opacity:0; pointer-events:none; transition:opacity .22s ease; }
  .drawer:target ~ .drawer-scrim { opacity:1; pointer-events:auto; }

  .drawer-head { display:flex; align-items:center; justify-content:space-between; gap:10px;
                 padding:16px 18px; border-bottom:1px solid var(--border); }
  .drawer-close { font-size:26px; line-height:1; color:var(--muted); padding:0 6px; }
  .drawer-close:hover { text-decoration:none; color:var(--text); }

  .drawer-user { display:flex; align-items:center; gap:12px; padding:16px 18px;
                 border-bottom:1px solid var(--border); }
  .drawer-user b { display:block; font-size:15px; }
  .drawer-user small { color:var(--primary); font-weight:700; font-size:13.5px; }
  .avatar { display:grid; place-items:center; width:44px; height:44px; flex:none;
            border-radius:13px; background:var(--primary); color:#fff; font-weight:800; font-size:18px; }

  .drawer-nav { display:flex; flex-direction:column; gap:2px; padding:12px; }
  .drawer-nav a { display:flex; align-items:center; gap:12px; padding:12px 14px;
                  border-radius:12px; color:var(--text); font-weight:600; font-size:15px; }
  .drawer-nav a:hover { background:var(--surface-2); text-decoration:none; }
  .drawer-nav a.is-active { background:var(--primary-soft); color:var(--primary); }
  .drawer-nav svg { width:20px; height:20px; flex:none; color:var(--muted); }
  .drawer-nav a.is-active svg { color:var(--primary); }

  main { max-width:1000px; margin:0 auto; padding:18px 16px 40px; }

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

  /* ── плитки, общие для главной и разделов ──────────────────────────── */
  .tiles { display:grid; gap:12px; grid-template-columns:1fr 1fr; }
  .tile { display:flex; flex-direction:column; gap:10px; padding:18px 16px; background:var(--surface);
          border:1px solid var(--border); border-radius:var(--r-lg); box-shadow:var(--shadow-sm); }
  .tile:hover { text-decoration:none; border-color:#C7D5F0; }
  .tile-ico { display:grid; place-items:center; width:46px; height:46px; border-radius:14px; }
  .tile-ico svg { width:23px; height:23px; }
  .tile b { font-size:28px; font-weight:800; letter-spacing:-.02em; line-height:1.1; }
  .tile span { font-size:13.5px; color:var(--muted); }
  .tile.is-action { align-items:center; text-align:center; color:var(--text); }
  .tile.is-action b { font-size:15px; font-weight:700; }
  .t-blue { background:var(--primary-soft); color:var(--primary); }
  .t-green { background:var(--success-soft); color:var(--success); }
  .t-orange { background:var(--warning-soft); color:var(--warning); }
  .t-red { background:var(--danger-soft); color:var(--danger); }
  .t-purple { background:var(--purple-soft); color:var(--purple); }

  /* ── поле «скопировать» ────────────────────────────────────────────── */
  .field { display:flex; align-items:center; gap:10px; padding:12px 14px; margin-bottom:10px;
           background:var(--surface-2); border:1px solid var(--border); border-radius:var(--r-md); }
  .field-main { flex:1 1 auto; min-width:0; }
  .field-label { display:block; font-size:11.5px; font-weight:700; letter-spacing:.08em;
                 text-transform:uppercase; color:var(--muted); margin-bottom:5px; }
  .field-value { display:inline-block; padding:4px 9px; border-radius:8px; background:var(--primary-soft);
                 font-family:ui-monospace,monospace; font-size:14px; word-break:break-all; }
  .field .icon-btn { flex:none; }
  .icon-btn { display:grid; place-items:center; width:38px; height:38px; border-radius:11px;
              background:transparent; border:0; color:var(--muted); cursor:pointer; padding:0; }
  .icon-btn:hover { background:var(--surface); color:var(--primary); }
  .icon-btn svg { width:19px; height:19px; }

  .progress { height:8px; border-radius:999px; background:var(--border); overflow:hidden; }
  .progress i { display:block; height:100%; border-radius:999px; background:var(--primary); }

  @media (prefers-reduced-motion:reduce) {
    * { animation-duration:.01ms !important; transition-duration:.01ms !important; }
  }
</style>
</head>
<body<?= $currentUser ? ' class="has-shell"' : '' ?>>
<?php
use Hosting\Service\Billing;

$pageTitle ??= '';
$balance   ??= null;

/** Иконки меню — свои SVG, ровно те, что нужны: эмодзи выглядят по-разному на разных телефонах. */
$navIcon = static function (string $name): string {
    $p = [
        'home'   => '<path d="M3 9.5 12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5Z"/>',
        'sites'  => '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
        'files'  => '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>',
        'domain' => '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18Z"/>',
        'db'     => '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
        'backup' => '<path d="M4 12a8 8 0 1 0 3-6.2"/><path d="M3 4v5h5"/>',
        'wallet' => '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M16 12h3"/>',
        'money'  => '<path d="M12 3v18"/><path d="M16.5 7.5c0-1.7-2-2.5-4.5-2.5s-4.5.8-4.5 2.5S9.5 11 12 11s4.5 1.3 4.5 3-2 3-4.5 3-4.5-1.3-4.5-3"/>',
        'user'   => '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
        'admin'  => '<path d="M12 3l7 3v6c0 4-3 7.5-7 9-4-1.5-7-5-7-9V6l7-3Z"/>',
        'exit'   => '<path d="M15 4h3a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-3"/><path d="M10 8l-4 4 4 4"/><path d="M6 12h9"/>',
    ];
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        . 'stroke-linecap="round" stroke-linejoin="round">' . ($p[$name] ?? '') . '</svg>';
};

$navItems = [
    ['/dashboard', 'Главная',   'home'],
    ['/sites',     'Мои сайты', 'sites'],
    ['/databases', 'Базы данных', 'db'],
    ['/backups',   'Бэкапы',    'backup'],
    ['/billing',   'Баланс',    'money'],
    ['/profile',   'Профиль',   'user'],
];
$currentPath = strtok($_SERVER['REQUEST_URI'] ?? '/', '?');
?>
<?php if ($currentUser): ?>
<div class="shell">
  <?php // Меню-«шторка». Открывается ссылкой на #menu, закрывается ссылкой обратно —
        // без JavaScript: так оно работает даже если скрипт не загрузился. ?>
  <div class="drawer" id="menu">
    <div class="drawer-head">
      <a class="brand" href="/dashboard">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 9.5 12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5Z"/>
          </svg>
        </span>
        <?php [$bh, $bt] = \Hosting\Support\Brand::split($panelName); ?>
        <span><?= Html::e($bh) ?><em><?= Html::e($bt) ?></em></span>
      </a>
      <a class="drawer-close" href="#" aria-label="Закрыть меню">&times;</a>
    </div>

    <div class="drawer-user">
      <span class="avatar"><?= Html::e(mb_strtoupper(mb_substr((string) ($currentUser['display_name'] ?: $currentUser['email']), 0, 1))) ?></span>
      <span>
        <b><?= Html::e($currentUser['display_name'] ?: strstr((string) $currentUser['email'], '@', true)) ?></b>
        <small><?= Html::e(Billing::money((float) ($currentUser['balance_tjs'] ?? 0))) ?></small>
      </span>
    </div>

    <nav class="drawer-nav">
      <?php foreach ($navItems as [$href, $label, $icon]): ?>
        <a href="<?= $href ?>" class="<?= $currentPath === $href ? 'is-active' : '' ?>">
          <?= $navIcon($icon) ?><?= Html::e($label) ?>
        </a>
      <?php endforeach; ?>
      <?php if (($currentUser['role'] ?? '') === 'admin'): ?>
        <a href="/admin" class="<?= $currentPath === '/admin' ? 'is-active' : '' ?>"><?= $navIcon('admin') ?>Админ</a>
      <?php endif; ?>
      <a href="/logout"><?= $navIcon('exit') ?>Выйти</a>
    </nav>
  </div>
  <a class="drawer-scrim" href="#" aria-hidden="true" tabindex="-1"></a>
</div>
<?php endif; ?>

<header class="top">
  <?php if ($currentUser): ?>
    <a class="burger" href="#menu" aria-label="Меню">
      <span></span><span></span><span></span>
    </a>
    <span class="top-title"><?= Html::e($pageTitle !== '' ? $pageTitle : $panelName) ?></span>
    <span class="top-right">
      <a class="chip" href="/billing"><?= Html::e(Billing::money((float) ($currentUser['balance_tjs'] ?? 0))) ?></a>
      <a class="btn" href="/billing">+ Пополнить</a>
    </span>
  <?php else: ?>
    <a class="brand" href="/">
      <span class="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 9.5 12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5Z"/>
        </svg>
      </span>
      <?php [$bh, $bt] = \Hosting\Support\Brand::split($panelName); ?>
      <span><?= Html::e($bh) ?><em><?= Html::e($bt) ?></em></span>
    </a>
  <?php endif; ?>
</header>
<main>
  <?php foreach ($flashes as $flash): ?>
    <div class="flash <?= Html::e($flash['type']) ?>"><?= Html::e($flash['text']) ?></div>
  <?php endforeach; ?>
  <?= $content ?>
</main>
<?php // Скрипт отдельным файлом: CSP панели разрешает только script-src 'self',
      // поэтому атрибуты onclick/onsubmit в разметке не сработали бы. ?>
<script src="/assets/panel.js"></script>
</body>
</html>
