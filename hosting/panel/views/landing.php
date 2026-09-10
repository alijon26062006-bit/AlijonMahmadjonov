<?php
/** @var list<array<string,mixed>> $plans
 *  @var string $rootDomain
 *  @var string $botUsername
 *  @var string $appUrl
 *  @var bool   $loginWidget
 */
use Hosting\Support\Html;

$botLink = $botUsername !== '' ? 'https://t.me/' . $botUsername : '';
?>
<style>
  /* Лендинг ломает ограничение main{max-width:960px;padding:16px}, чтобы герой
     и разделы шли от края до края — внутри у каждого свой контейнер. */
  /* Во всю ширину окна, несмотря на main{max-width:960px;padding:16px}:
     100vw и отрицательный отступ ровно до края вьюпорта. 100vw включает в себя
     ширину полосы прокрутки, поэтому в браузерах с «классической» (не наложенной)
     полосой без этого появлялась бы горизонтальная прокрутка на пару пикселей. */
  body { overflow-x:hidden; }
  .lp { width:100vw; margin-left:calc(50% - 50vw); margin-top:-16px; margin-bottom:-16px; }
  .lp-wrap { max-width:1000px; margin:0 auto; padding:0 20px; }

  .lp-hero { position:relative; overflow:hidden; padding:64px 0 56px;
             background:radial-gradient(1000px 420px at 50% -120px, #1d3a5c 0%, transparent 70%), #0b1220; }
  .lp-hero::after { content:""; position:absolute; left:0; right:0; bottom:0; height:1px; background:var(--border); }
  .lp-eyebrow { display:inline-block; padding:5px 12px; border-radius:999px; font-size:13px;
                background:rgba(34,197,94,.12); color:#86efac; border:1px solid rgba(34,197,94,.28); }
  .lp-hero h1 { font-size:clamp(30px,7vw,50px); line-height:1.1; letter-spacing:-.02em;
                margin:18px 0 14px; max-width:16ch; }
  .lp-lead { font-size:clamp(16px,2.4vw,19px); color:var(--muted); max-width:52ch; margin:0 0 30px; }
  .lp-lead code { background:rgba(255,255,255,.06); border-color:rgba(255,255,255,.12); font-size:.92em; }

  .lp-cta { display:flex; flex-wrap:wrap; align-items:center; gap:12px; }
  .lp-btn { display:inline-flex; align-items:center; gap:9px; padding:14px 24px; border-radius:12px;
            font-size:16px; font-weight:650; text-decoration:none; border:1px solid transparent; }
  .lp-btn-primary { background:var(--accent); color:#052e16; }
  .lp-btn-primary:hover { filter:brightness(1.07); }
  .lp-btn-ghost { background:transparent; color:var(--text); border-color:var(--border); }
  .lp-btn-ghost:hover { border-color:var(--muted); }
  .lp-note { margin:14px 0 0; font-size:14px; color:var(--muted); }
  .lp-widget { margin-top:18px; }

  .lp-section { padding:56px 0; }
  .lp-section + .lp-section { border-top:1px solid var(--border); }
  .lp-h2 { font-size:clamp(22px,4vw,30px); letter-spacing:-.015em; margin:0 0 8px; }
  .lp-sub { color:var(--muted); margin:0 0 28px; max-width:56ch; }

  .lp-steps { display:grid; gap:16px; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); }
  .lp-step { background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:22px; }
  .lp-num { display:flex; width:34px; height:34px; align-items:center; justify-content:center;
            border-radius:10px; background:rgba(34,197,94,.14); color:#86efac; font-weight:700; margin-bottom:14px; }
  .lp-step h3 { margin:0 0 6px; font-size:17px; }
  .lp-step p { margin:0; color:var(--muted); font-size:14px; }

  .lp-plans { display:grid; gap:18px; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); align-items:start; }
  .lp-plan { position:relative; background:var(--panel); border:1px solid var(--border);
             border-radius:16px; padding:26px 22px; }
  .lp-plan.is-featured { border-color:rgba(34,197,94,.5); box-shadow:0 0 0 1px rgba(34,197,94,.2); }
  .lp-tag { position:absolute; top:-11px; left:22px; padding:3px 10px; border-radius:999px; font-size:12px;
            font-weight:600; background:var(--accent); color:#052e16; }
  .lp-plan h3 { margin:0; font-size:16px; color:var(--muted); font-weight:600;
                text-transform:uppercase; letter-spacing:.06em; }
  .lp-price { display:flex; align-items:baseline; gap:7px; margin:12px 0 20px; }
  .lp-price b { font-size:40px; font-weight:700; letter-spacing:-.03em; }
  .lp-price span { color:var(--muted); font-size:14px; }
  .lp-plan ul { list-style:none; padding:0; margin:0 0 22px; }
  .lp-plan li { display:flex; gap:10px; padding:7px 0; font-size:14.5px; }
  .lp-plan li::before { content:"✓"; color:var(--accent); font-weight:700; }
  .lp-plan .lp-btn { width:100%; justify-content:center; padding:11px 18px; font-size:15px; }

  .lp-features { display:grid; gap:1px; background:var(--border); border:1px solid var(--border);
                 border-radius:14px; overflow:hidden; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }
  .lp-feature { background:var(--panel); padding:20px 22px; }
  .lp-feature h4 { margin:0 0 5px; font-size:15px; }
  .lp-feature p { margin:0; color:var(--muted); font-size:14px; }

  .lp-foot { padding:34px 0 42px; border-top:1px solid var(--border); color:var(--muted); font-size:14px; }
  .lp-foot a { color:var(--muted); }

  @media (max-width:520px) {
    .lp-hero { padding:44px 0 40px; }
    .lp-section { padding:42px 0; }
    .lp-btn { width:100%; justify-content:center; }
  }
</style>

<div class="lp">

  <section class="lp-hero">
    <div class="lp-wrap">
      <span class="lp-eyebrow">Хостинг в Таджикистане</span>
      <h1>Сайт на PHP, который просто работает</h1>
      <p class="lp-lead">
        WordPress, Laravel или свой код — загружаете файлы и сайт открывается.
        Адрес вида <code>вашсайт.<?= Html::e($rootDomain) ?></code>, база данных,
        SSL-сертификат и защита от перегрузок входят в любой тариф.
      </p>

      <div class="lp-cta">
        <?php if ($botLink !== ''): ?>
          <a class="lp-btn lp-btn-primary" href="<?= Html::e($botLink) ?>">Войти через Telegram</a>
          <a class="lp-btn lp-btn-ghost" href="/register">Регистрация по e-mail</a>
        <?php else: ?>
          <a class="lp-btn lp-btn-primary" href="/register">Создать аккаунт</a>
          <a class="lp-btn lp-btn-ghost" href="/login">Войти</a>
        <?php endif; ?>
      </div>

      <p class="lp-note">
        <?php if ($botLink !== ''): ?>
          Аккаунт создаётся сам — ни анкет, ни пароля.
          Уже есть аккаунт? <a href="/login">Вход по e-mail</a>
        <?php else: ?>
          Вход через Telegram появится, когда администратор настроит бота.
        <?php endif; ?>
      </p>

      <?php // Виджет Telegram работает только после /setdomain в @BotFather. Без этого
            // он рисует белую плашку «Bot domain invalid» поверх страницы, поэтому
            // включается явным TELEGRAM_LOGIN_WIDGET=true (это делает setup.sh). ?>
      <?php if ($loginWidget && $botUsername !== ''): ?>
        <div class="lp-widget">
          <script async src="https://telegram.org/js/telegram-widget.js?22"
                  data-telegram-login="<?= Html::e($botUsername) ?>"
                  data-size="large"
                  data-userpic="false"
                  data-auth-url="<?= Html::e($appUrl) ?>/telegram/widget"
                  data-request-access="write"></script>
        </div>
      <?php endif; ?>
    </div>
  </section>

  <section class="lp-section">
    <div class="lp-wrap">
      <h2 class="lp-h2">Три шага до работающего сайта</h2>
      <p class="lp-sub">От входа до открытой страницы — несколько минут, без переписки с поддержкой.</p>
      <div class="lp-steps">
        <div class="lp-step">
          <div class="lp-num">1</div>
          <h3>Входите через Telegram</h3>
          <p>Аккаунт создаётся автоматически. Заполнять ничего не нужно.</p>
        </div>
        <div class="lp-step">
          <div class="lp-num">2</div>
          <h3>Создаёте сайт</h3>
          <p>Придумываете имя — адрес и SSL выдаются сразу.</p>
        </div>
        <div class="lp-step">
          <div class="lp-num">3</div>
          <h3>Загружаете файлы</h3>
          <p>Через файловый менеджер, ZIP-архивом или по SFTP. База данных — в один клик.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section">
    <div class="lp-wrap">
      <h2 class="lp-h2">Тарифы</h2>
      <p class="lp-sub">Оплата после регистрации — сначала можно всё попробовать.</p>
      <div class="lp-plans">
        <?php foreach (array_values($plans) as $i => $plan): ?>
          <?php $featured = count($plans) > 1 && $i === 1; ?>
          <div class="lp-plan<?= $featured ? ' is-featured' : '' ?>">
            <?php if ($featured): ?><span class="lp-tag">Выбирают чаще</span><?php endif; ?>
            <h3><?= Html::e($plan['title']) ?></h3>
            <div class="lp-price">
              <b><?= Html::e((int) $plan['price_tjs']) ?></b><span>сомони / мес</span>
            </div>
            <ul>
              <li><?= Html::e(round((int) $plan['disk_quota_mb'] / 1024, 1)) ?> ГБ на диске</li>
              <?php $sites = (int) $plan['max_sites']; $dbs = (int) $plan['max_databases']; ?>
              <li><?= $sites ?> <?= Html::plural($sites, 'сайт', 'сайта', 'сайтов') ?></li>
              <li><?= $dbs ?> <?= Html::plural($dbs, 'база', 'базы', 'баз') ?> данных</li>
              <li>SSL-сертификат бесплатно</li>
              <li>Резервные копии каждую ночь</li>
            </ul>
            <a class="lp-btn <?= $featured ? 'lp-btn-primary' : 'lp-btn-ghost' ?>"
               href="<?= $botLink !== '' ? Html::e($botLink) : '/register' ?>">Начать</a>
          </div>
        <?php endforeach; ?>
      </div>
    </div>
  </section>

  <section class="lp-section">
    <div class="lp-wrap">
      <h2 class="lp-h2">Что внутри</h2>
      <p class="lp-sub">Всё, что нужно обычному сайту, уже настроено.</p>
      <div class="lp-features">
        <div class="lp-feature">
          <h4>PHP</h4>
          <p>Свежая версия и отдельный процесс на каждого клиента — соседи не влияют на ваш сайт.</p>
        </div>
        <div class="lp-feature">
          <h4>База данных</h4>
          <p>MariaDB с доступом через phpMyAdmin прямо из панели.</p>
        </div>
        <div class="lp-feature">
          <h4>Файлы</h4>
          <p>Менеджер в панели, загрузка ZIP-архивом и доступ по SFTP.</p>
        </div>
        <div class="lp-feature">
          <h4>Адреса</h4>
          <p>Бесплатный поддомен или свой домен — сертификат выпускается сам.</p>
        </div>
        <div class="lp-feature">
          <h4>Резервные копии</h4>
          <p>Создаются каждую ночь, восстановление — из панели.</p>
        </div>
        <div class="lp-feature">
          <h4>Защита</h4>
          <p>Firewall, Fail2ban и полная изоляция клиентов друг от друга.</p>
        </div>
      </div>
    </div>
  </section>

  <footer class="lp-foot">
    <div class="lp-wrap">
      <?= Html::e($rootDomain) ?> · <a href="/login">Вход</a> · <a href="/register">Регистрация</a>
      <?php if ($botLink !== ''): ?> · <a href="<?= Html::e($botLink) ?>">Telegram</a><?php endif; ?>
    </div>
  </footer>

</div>
