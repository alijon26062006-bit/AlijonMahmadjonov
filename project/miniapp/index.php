<?php
$config = require __DIR__ . '/../config/config.php';
$appName = htmlspecialchars($config['app']['name'], ENT_QUOTES);
// API base is resolved relative to this file; ?route= keeps it host-agnostic.

// Prefer minified assets (built via `php assets/build.php`) and cache-bust by mtime.
$asset = static function (string $min, string $src): string {
    $base = __DIR__ . '/../assets/';
    $rel  = is_file($base . $min) ? $min : $src;
    $ver  = @filemtime($base . $rel) ?: time();
    return '../assets/' . $rel . '?v=' . $ver;
};
$cssHref = $asset('css/app.min.css', 'css/app.css');
$jsSrc   = $asset('js/app.min.js', 'js/app.js');
?><!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="theme-color" content="#0a0a0c">
<title><?= $appName ?> — Кино и анонсы</title>
<link rel="stylesheet" href="<?= $cssHref ?>">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
</head>
<body>

<!-- ============ TOP BAR ============ -->
<header class="topbar" id="topbar">
  <div class="topbar__brand">
    <span class="logo">◐</span>
    <span class="brand-name"><?= $appName ?></span>
  </div>
  <div class="topbar__actions">
    <button class="icon-btn" id="btnSearch" aria-label="Поиск">
      <svg viewBox="0 0 24 24"><path d="M21 21l-4.3-4.3M11 19a8 8 0 100-16 8 8 0 000 16z"/></svg>
    </button>
    <button class="avatar" id="btnProfile" aria-label="Профиль"><span id="avatarInitial">U</span></button>
  </div>
</header>

<!-- ============ HOME VIEW ============ -->
<main class="view view--active" id="view-home">

  <!-- Hero -->
  <section class="hero" id="hero">
    <div class="hero__track" id="heroTrack"></div>
    <div class="hero__dots" id="heroDots"></div>
  </section>

  <!-- Rails injected here -->
  <div id="rails"></div>

</main>

<!-- ============ DETAIL VIEW ============ -->
<main class="view" id="view-detail">
  <div id="detailContent"></div>
</main>

<!-- ============ CATALOG / SECTION VIEW ============ -->
<main class="view" id="view-catalog">
  <div class="catalog__head">
    <button class="back-btn" data-back aria-label="Назад">‹</button>
    <h2 id="catalogTitle">Каталог</h2>
  </div>
  <div class="grid" id="catalogGrid"></div>
  <div class="loader-sentinel" id="catalogSentinel"></div>
</main>

<!-- ============ SEARCH OVERLAY ============ -->
<div class="search-overlay" id="searchOverlay">
  <div class="search-bar">
    <button class="back-btn" id="btnSearchClose" aria-label="Закрыть">‹</button>
    <input type="search" id="searchInput" placeholder="Фильмы, сериалы, аниме…" autocomplete="off">
  </div>
  <div class="filters" id="searchFilters">
    <select id="fCategory" class="chip-select">
      <option value="">Все типы</option>
      <option value="movie">Фильмы</option>
      <option value="series">Сериалы</option>
      <option value="anime">Аниме</option>
      <option value="cartoon">Мультфильмы</option>
    </select>
    <select id="fGenre" class="chip-select"><option value="">Жанр</option></select>
    <select id="fYear" class="chip-select"><option value="">Год</option></select>
    <select id="fRating" class="chip-select">
      <option value="">Рейтинг</option>
      <option value="9">9+</option><option value="8">8+</option>
      <option value="7">7+</option><option value="6">6+</option>
    </select>
  </div>
  <div class="grid" id="searchResults"></div>
  <p class="search-empty" id="searchEmpty" hidden>Ничего не найдено</p>
</div>

<!-- ============ BOTTOM NAV ============ -->
<nav class="bottom-nav" id="bottomNav">
  <button class="nav-item is-active" data-nav="home">
    <svg viewBox="0 0 24 24"><path d="M3 11l9-8 9 8v9a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z"/></svg>
    <span>Главная</span>
  </button>
  <button class="nav-item" data-nav="search">
    <svg viewBox="0 0 24 24"><path d="M21 21l-4.3-4.3M11 19a8 8 0 100-16 8 8 0 000 16z"/></svg>
    <span>Поиск</span>
  </button>
  <button class="nav-item" data-nav="favorites">
    <svg viewBox="0 0 24 24"><path d="M12 21s-7-4.5-9.5-9A5 5 0 0112 5a5 5 0 019.5 7c-2.5 4.5-9.5 9-9.5 9z"/></svg>
    <span>Избранное</span>
  </button>
  <button class="nav-item" data-nav="history">
    <svg viewBox="0 0 24 24"><path d="M12 8v5l3 2M21 12a9 9 0 11-9-9"/></svg>
    <span>История</span>
  </button>
</nav>

<div class="toast" id="toast"></div>

<script>
  window.APP = { name: <?= json_encode($appName) ?>, api: '../api/index.php' };
</script>
<script src="<?= $jsSrc ?>"></script>
</body>
</html>
