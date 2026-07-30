<?php
$config = require __DIR__ . '/../config/config.php';
$appName = htmlspecialchars($config['app']['name'], ENT_QUOTES);
// API base is resolved relative to this file; ?route= keeps it host-agnostic.

// Always load the source assets with mtime cache-busting, so an updated
// app.js/app.css takes effect immediately (stale .min files can't shadow them).
$asset = static function (string $rel): string {
    $ver = @filemtime(__DIR__ . '/../assets/' . $rel) ?: time();
    return '../assets/' . $rel . '?v=' . $ver;
};
$cssHref = $asset('css/app.css');
$jsSrc   = $asset('js/app.js');
// Bot username (without @) enables watch-via-deep-link: the app closes and the
// film is delivered in the bot chat.
$botUser = ltrim((string) ($config['telegram']['bot_username'] ?? ''), '@');
?><!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="theme-color" content="#0a0a0c">
<title><?= $appName ?> &#8212; &#1050;&#1080;&#1085;&#1086; &#1080; &#1072;&#1085;&#1086;&#1085;&#1089;&#1099;</title>
<link rel="stylesheet" href="<?= $cssHref ?>">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
</head>
<body>

<!-- ============ TOP BAR ============ -->
<header class="topbar" id="topbar">
  <div class="topbar__brand">
    <span class="logo">&#9680;</span>
    <span class="brand-name"><?= $appName ?></span>
  </div>
  <div class="topbar__actions">
    <button class="icon-btn" id="btnSearch" aria-label="&#1055;&#1086;&#1080;&#1089;&#1082;">
      <svg viewBox="0 0 24 24"><path d="M21 21l-4.3-4.3M11 19a8 8 0 100-16 8 8 0 000 16z"/></svg>
    </button>
    <button class="avatar" id="btnProfile" aria-label="&#1055;&#1088;&#1086;&#1092;&#1080;&#1083;&#1100;"><span id="avatarInitial">U</span></button>
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
    <button class="back-btn" data-back aria-label="&#1053;&#1072;&#1079;&#1072;&#1076;">&#8249;</button>
    <h2 id="catalogTitle">&#1050;&#1072;&#1090;&#1072;&#1083;&#1086;&#1075;</h2>
  </div>
  <div class="grid" id="catalogGrid"></div>
  <div class="loader-sentinel" id="catalogSentinel"></div>
</main>

<!-- ============ PROFILE VIEW ============ -->
<main class="view" id="view-profile">
  <div class="catalog__head">
    <button class="back-btn" data-back aria-label="&#1053;&#1072;&#1079;&#1072;&#1076;">&#8249;</button>
    <h2>&#1055;&#1088;&#1086;&#1092;&#1080;&#1083;&#1100;</h2>
  </div>
  <div id="profileContent"></div>
</main>

<!-- ============ SEARCH OVERLAY ============ -->
<div class="search-overlay" id="searchOverlay">
  <div class="search-bar">
    <button class="back-btn" id="btnSearchClose" aria-label="&#1047;&#1072;&#1082;&#1088;&#1099;&#1090;&#1100;">&#8249;</button>
    <input type="search" id="searchInput" placeholder="&#1060;&#1080;&#1083;&#1100;&#1084;&#1099;, &#1089;&#1077;&#1088;&#1080;&#1072;&#1083;&#1099;, &#1072;&#1085;&#1080;&#1084;&#1077;&#8230;" autocomplete="off">
  </div>
  <div class="filters" id="searchFilters">
    <select id="fCategory" class="chip-select">
      <option value="">&#1042;&#1089;&#1077; &#1090;&#1080;&#1087;&#1099;</option>
      <option value="movie">&#1060;&#1080;&#1083;&#1100;&#1084;&#1099;</option>
      <option value="series">&#1057;&#1077;&#1088;&#1080;&#1072;&#1083;&#1099;</option>
      <option value="anime">&#1040;&#1085;&#1080;&#1084;&#1077;</option>
      <option value="cartoon">&#1052;&#1091;&#1083;&#1100;&#1090;&#1092;&#1080;&#1083;&#1100;&#1084;&#1099;</option>
    </select>
    <select id="fGenre" class="chip-select"><option value="">&#1046;&#1072;&#1085;&#1088;</option></select>
    <select id="fYear" class="chip-select"><option value="">&#1043;&#1086;&#1076;</option></select>
    <select id="fRating" class="chip-select">
      <option value="">&#1056;&#1077;&#1081;&#1090;&#1080;&#1085;&#1075;</option>
      <option value="9">9+</option><option value="8">8+</option>
      <option value="7">7+</option><option value="6">6+</option>
    </select>
  </div>
  <div class="grid" id="searchResults"></div>
  <p class="search-empty" id="searchEmpty" hidden>&#1053;&#1080;&#1095;&#1077;&#1075;&#1086; &#1085;&#1077; &#1085;&#1072;&#1081;&#1076;&#1077;&#1085;&#1086;</p>
</div>

<!-- ============ BOTTOM NAV ============ -->
<nav class="bottom-nav" id="bottomNav">
  <button class="nav-item is-active" data-nav="home">
    <svg viewBox="0 0 24 24"><path d="M3 11l9-8 9 8v9a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z"/></svg>
    <span>&#1043;&#1083;&#1072;&#1074;&#1085;&#1072;&#1103;</span>
  </button>
  <button class="nav-item" data-nav="search">
    <svg viewBox="0 0 24 24"><path d="M21 21l-4.3-4.3M11 19a8 8 0 100-16 8 8 0 000 16z"/></svg>
    <span>&#1055;&#1086;&#1080;&#1089;&#1082;</span>
  </button>
  <button class="nav-item" data-nav="favorites">
    <svg viewBox="0 0 24 24"><path d="M12 21s-7-4.5-9.5-9A5 5 0 0112 5a5 5 0 019.5 7c-2.5 4.5-9.5 9-9.5 9z"/></svg>
    <span>&#1048;&#1079;&#1073;&#1088;&#1072;&#1085;&#1085;&#1086;&#1077;</span>
  </button>
  <button class="nav-item" data-nav="history">
    <svg viewBox="0 0 24 24"><path d="M12 8v5l3 2M21 12a9 9 0 11-9-9"/></svg>
    <span>&#1048;&#1089;&#1090;&#1086;&#1088;&#1080;&#1103;</span>
  </button>
</nav>

<div class="toast" id="toast"></div>

<script>
  window.APP = { name: <?= json_encode($appName) ?>, api: '../api/index.php', bot: <?= json_encode($botUser) ?> };
</script>
<script src="<?= $jsSrc ?>"></script>
</body>
</html>
