<?php
/** @var list<array<string,mixed>> $plans
 *  @var string $rootDomain
 *  @var string $botUsername
 *  @var string $appUrl
 *  @var bool   $loginWidget
 */
use Hosting\Support\Html;

$botLink = $botUsername !== '' ? 'https://t.me/' . $botUsername : '';
$startHref = $botLink !== '' ? $botLink : '/register';

/** Иконка из набора Lucide. Своих SVG ровно столько, сколько нужно странице —
 *  библиотеку целиком тянуть незачем, а эмодзи вместо иконок выглядят кустарно. */
function lp_icon(string $name): string
{
    $paths = [
        'clock'    => '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        'shield'   => '<path d="M12 3l7 3v6c0 4-3 7.5-7 9-4-1.5-7-5-7-9V6l7-3Z"/>',
        'lock'     => '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
        'bolt'     => '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/>',
        'chat'     => '<path d="M4 5h16v11H8l-4 4V5Z"/>',
        'restore'  => '<path d="M4 12a8 8 0 1 0 3-6.2"/><path d="M3 4v5h5"/>',
        'server'   => '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 17.5h.01"/>',
        'database' => '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
        'code'     => '<path d="m9 8-5 4 5 4"/><path d="m15 8 5 4-5 4"/>',
        'disk'     => '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.5"/>',
        'globe'    => '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18Z"/>',
        'arrow'    => '<path d="M5 12h13"/><path d="m13 6 6 6-6 6"/>',
        'star'     => '<path d="m12 3 2.6 5.6 6 .8-4.4 4.2 1.1 6.1L12 16.8 6.7 19.7l1.1-6.1L3.4 9.4l6-.8L12 3Z"/>',
        'check'    => '<path d="m5 12.5 4.5 4.5L19 7"/>',
    ];

    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" '
        . 'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        . ($paths[$name] ?? '') . '</svg>';
}
?>
<style>
  /* Лендинг во всю ширину окна, несмотря на main{max-width:1000px;padding:20px}.
     100vw включает полосу прокрутки, поэтому страховка overflow-x на body. */
  body { overflow-x:hidden; }
  .lp { width:100vw; margin-left:calc(50% - 50vw); margin-top:-20px; margin-bottom:-20px; }
  .lp-wrap { max-width:1080px; margin:0 auto; padding:0 20px; }

  /* Точечная сетка фоном — как в образце, очень слабым контрастом. */
  .lp-dots { background-image:radial-gradient(rgba(37,99,235,.10) 1px, transparent 1px);
             background-size:22px 22px; }

  /* ── герой ─────────────────────────────────────────────────────────── */
  .lp-hero { padding:56px 0 64px; text-align:center; background:var(--bg); }
  .lp-pill { display:inline-flex; align-items:center; gap:9px; padding:9px 18px; border-radius:999px;
             background:var(--surface); border:1px solid var(--border); box-shadow:var(--shadow-sm);
             font-size:12.5px; font-weight:800; letter-spacing:.12em; text-transform:uppercase;
             color:var(--text); }
  .lp-pill i { width:8px; height:8px; border-radius:50%; background:var(--success); }
  .lp-title { font-size:clamp(40px,12vw,76px); font-weight:800; letter-spacing:-.035em;
              margin:26px 0 18px; color:var(--text); }
  .lp-title em { font-style:normal; color:var(--primary); }
  .lp-lead { font-size:clamp(16px,2.5vw,19px); color:var(--muted); max-width:46ch;
             margin:0 auto 30px; }
  .lp-lead code { font-size:.92em; }

  .lp-actions { display:flex; flex-direction:column; align-items:center; gap:12px;
                max-width:380px; margin:0 auto; }
  .lp-btn { display:inline-flex; align-items:center; justify-content:center; gap:10px; width:100%;
            padding:17px 26px; border-radius:16px; font-size:16px; font-weight:800;
            border:1px solid transparent; transition:transform .16s, box-shadow .16s, background .16s; }
  .lp-btn:hover { text-decoration:none; transform:translateY(-1px); }
  .lp-btn svg { width:19px; height:19px; }
  .lp-btn-primary { background:var(--primary); color:#fff; box-shadow:var(--shadow-primary); }
  .lp-btn-primary:hover { background:var(--primary-600); }
  .lp-btn-ghost { background:var(--surface); color:var(--text); border-color:var(--border);
                  box-shadow:var(--shadow-sm); }
  .lp-hint { margin:16px 0 0; font-size:14px; color:var(--muted); }

  .lp-stats { display:grid; grid-template-columns:1fr 1fr; max-width:520px; margin:44px auto 0; }
  .lp-stat { padding:22px 10px; }
  .lp-stat:nth-child(odd)  { border-right:1px solid var(--border); }
  .lp-stat:nth-child(-n+2) { border-bottom:1px solid var(--border); }
  .lp-stat b { display:block; font-size:34px; font-weight:800; letter-spacing:-.03em; }
  .lp-stat b em { font-style:normal; color:var(--primary); }
  .lp-stat span { font-size:12px; font-weight:700; letter-spacing:.1em; text-transform:uppercase;
                  color:var(--muted); }

  /* ── секции ────────────────────────────────────────────────────────── */
  .lp-section { padding:68px 0; }
  .lp-section.on-white { background:var(--surface); }
  .lp-section.on-soft  { background:var(--bg-soft); }
  .lp-eyebrow { display:flex; align-items:center; gap:12px; font-size:12.5px; font-weight:800;
                letter-spacing:.16em; text-transform:uppercase; color:var(--primary); margin-bottom:14px; }
  .lp-eyebrow::before { content:""; width:26px; height:2.5px; border-radius:2px; background:var(--primary); }
  .lp-h2 { font-size:clamp(26px,5.4vw,40px); margin:0 0 12px; max-width:20ch; }
  .lp-sub { color:var(--muted); margin:0 0 34px; max-width:52ch; font-size:16px; }

  /* иконка в пастельной плитке */
  .lp-tile { display:grid; place-items:center; width:54px; height:54px; border-radius:15px; flex:none; }
  .lp-tile svg { width:26px; height:26px; }
  .t-blue   { background:var(--primary-soft); color:var(--primary); }
  .t-green  { background:var(--success-soft); color:var(--success); }
  .t-red    { background:var(--danger-soft);  color:var(--danger); }
  .t-orange { background:var(--warning-soft); color:var(--warning); }
  .t-purple { background:var(--purple-soft);  color:var(--purple); }

  .lp-grid { display:grid; gap:18px; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }
  .lp-feature { background:var(--surface-2); border:1px solid var(--border); border-radius:var(--r-lg);
                padding:26px; }
  .lp-section.on-soft .lp-feature { background:var(--surface); }
  .lp-feature h3 { margin:20px 0 8px; font-size:18px; }
  .lp-feature p { margin:0; color:var(--muted); font-size:15px; }

  .lp-rows { display:grid; gap:26px; }
  .lp-row { display:flex; gap:18px; align-items:flex-start; }
  .lp-row h3 { margin:4px 0 5px; font-size:17px; }
  .lp-row p { margin:0; color:var(--muted); font-size:15px; }

  /* ── тарифы ────────────────────────────────────────────────────────── */
  .lp-plans { display:grid; gap:22px; grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
              align-items:start; }
  .lp-plan { position:relative; background:var(--surface); border:1px solid var(--border);
             border-radius:var(--r-xl); padding:30px 26px; box-shadow:var(--shadow-md); }
  .lp-plan.is-top { border:2px solid var(--primary); box-shadow:0 14px 34px rgba(37,99,235,.16); }
  .lp-plan-tag { position:absolute; top:-15px; left:50%; transform:translateX(-50%);
                 display:inline-flex; align-items:center; gap:6px; white-space:nowrap;
                 padding:7px 18px; border-radius:0 0 12px 12px; background:var(--primary);
                 color:#fff; font-size:12px; font-weight:800; letter-spacing:.08em;
                 text-transform:uppercase; }
  .lp-plan-tag svg { width:14px; height:14px; fill:#FACC15; stroke:#FACC15; }
  .lp-plan-name { font-size:12.5px; font-weight:800; letter-spacing:.16em; text-transform:uppercase;
                  color:var(--muted); }
  .lp-plan-price { display:flex; align-items:flex-start; gap:6px; margin:14px 0 6px; }
  .lp-plan-price span { font-size:15px; font-weight:800; color:var(--muted); padding-top:9px; }
  .lp-plan-price b { font-size:52px; font-weight:800; letter-spacing:-.045em; line-height:1; }
  .lp-plan-per { font-size:14.5px; color:var(--muted); }
  .lp-plan-per b { color:var(--success); font-weight:800; }
  .lp-plan hr { border:0; border-top:1px solid var(--border); margin:22px 0; }
  .lp-plan ul { list-style:none; padding:0; margin:0 0 26px; display:grid; gap:12px; }
  .lp-plan li { display:flex; align-items:center; gap:14px; font-size:15.5px; font-weight:500; }
  .lp-plan li .lp-tile { width:38px; height:38px; border-radius:11px; }
  .lp-plan li .lp-tile svg { width:19px; height:19px; }

  .lp-foot { padding:38px 0 46px; background:var(--surface); border-top:1px solid var(--border);
             color:var(--muted); font-size:14.5px; text-align:center; }
  .lp-foot a { color:var(--muted); }

  @media (min-width:640px) {
    .lp-actions { flex-direction:row; max-width:none; justify-content:center; }
    .lp-hero .lp-btn { width:auto; }   /* только в герое; в карточке тарифа кнопка всегда во всю ширину */
  }
</style>

<div class="lp">

  <section class="lp-hero lp-dots">
    <div class="lp-wrap">
      <span class="lp-pill"><i></i>Хостинг в Таджикистане</span>

      <?php
        // Название двухцветное, как в образце: первая часть тёмная, вторая — синяя.
        $parts = preg_split('~(?=[A-ZА-Я])~u', $panelName, -1, PREG_SPLIT_NO_EMPTY) ?: [$panelName];
        $tail  = count($parts) > 1 ? array_pop($parts) : '';
      ?>
      <h1 class="lp-title"><?= Html::e(implode('', $parts)) ?><em><?= Html::e($tail) ?></em></h1>

      <p class="lp-lead">
        Хостинг для PHP-сайтов: WordPress, Laravel или свой код.
        Адрес <code>вашсайт.<?= Html::e($rootDomain) ?></code>, база данных,
        SSL и защита от перегрузок — в любом тарифе.
      </p>

      <div class="lp-actions">
        <a class="lp-btn lp-btn-primary" href="<?= Html::e($startHref) ?>">
          <?= $botLink !== '' ? 'Войти через Telegram' : 'Создать аккаунт' ?><?= lp_icon('arrow') ?>
        </a>
        <a class="lp-btn lp-btn-ghost" href="#tarify">Посмотреть тарифы</a>
      </div>

      <p class="lp-hint">
        <?php if ($botLink !== ''): ?>
          Аккаунт создаётся сам — ни анкет, ни пароля. <a href="/login">Вход по e-mail</a>
        <?php else: ?>
          Вход через Telegram появится, когда администратор настроит бота.
        <?php endif; ?>
      </p>

      <?php // Виджет Telegram работает только после /setdomain в @BotFather, иначе рисует
            // белую плашку «Bot domain invalid» — поэтому включается явным флагом. ?>
      <?php if ($loginWidget && $botUsername !== ''): ?>
        <div style="margin-top:20px;">
          <script async src="https://telegram.org/js/telegram-widget.js?22"
                  data-telegram-login="<?= Html::e($botUsername) ?>"
                  data-size="large" data-userpic="false"
                  data-auth-url="<?= Html::e($appUrl) ?>/telegram/widget"
                  data-request-access="write"></script>
        </div>
      <?php endif; ?>

      <div class="lp-stats">
        <div class="lp-stat"><b>99.9<em>%</em></b><span>Аптайм</span></div>
        <div class="lp-stat"><b>10<em>×</em></b><span>Скорость NVMe</span></div>
        <div class="lp-stat"><b>24<em>/7</em></b><span>Мониторинг</span></div>
        <div class="lp-stat"><b>3<em> мин</em></b><span>До первого сайта</span></div>
      </div>
    </div>
  </section>

  <section class="lp-section on-white">
    <div class="lp-wrap">
      <div class="lp-eyebrow">Возможности</div>
      <h2 class="lp-h2">Почему <?= Html::e($panelName) ?>?</h2>
      <p class="lp-sub">Всё, что нужно работающему сайту, уже настроено.</p>

      <div class="lp-grid">
        <div class="lp-feature">
          <div class="lp-tile t-blue"><?= lp_icon('clock') ?></div>
          <h3>Работает без присмотра</h3>
          <p>Мониторинг круглосуточно, сертификаты продлеваются сами, сбои видно раньше клиента.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-tile t-red"><?= lp_icon('shield') ?></div>
          <h3>Защита от перегрузок</h3>
          <p>Firewall и Fail2ban на входе, лимиты на запросы — чужой всплеск не роняет ваш сайт.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-tile t-green"><?= lp_icon('lock') ?></div>
          <h3>SSL бесплатно</h3>
          <p>Сертификат выпускается автоматически и для поддомена, и для вашего домена.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-tile t-orange"><?= lp_icon('bolt') ?></div>
          <h3>NVMe-диски</h3>
          <p>Быстрее обычных дисков в разы: страницы отдаются, а не собираются.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-tile t-purple"><?= lp_icon('chat') ?></div>
          <h3>Поддержка в Telegram</h3>
          <p>Пишете туда же, где вошли. Без тикетов и ожидания ответа неделю.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-tile t-blue"><?= lp_icon('restore') ?></div>
          <h3>Ежедневные бэкапы</h3>
          <p>Копия каждую ночь, восстановление из панели в один клик.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section on-soft lp-dots">
    <div class="lp-wrap">
      <div class="lp-eyebrow">Инфраструктура</div>
      <h2 class="lp-h2">Сильные серверы для вашего бизнеса</h2>
      <p class="lp-sub">Ничего не нужно настраивать самому — всё готово к первому сайту.</p>

      <div class="lp-rows">
        <div class="lp-row">
          <div class="lp-tile t-blue"><?= lp_icon('server') ?></div>
          <div>
            <h3>Nginx + PHP</h3>
            <p>Свежая версия PHP и отдельный процесс на каждого клиента — соседи не влияют на ваш сайт.</p>
          </div>
        </div>
        <div class="lp-row">
          <div class="lp-tile t-blue"><?= lp_icon('database') ?></div>
          <div>
            <h3>MariaDB</h3>
            <p>Своя база с полным доступом и phpMyAdmin прямо из панели.</p>
          </div>
        </div>
        <div class="lp-row">
          <div class="lp-tile t-blue"><?= lp_icon('shield') ?></div>
          <div>
            <h3>Firewall + изоляция</h3>
            <p>Каждый клиент в своём системном пользователе: файлы и процессы не пересекаются.</p>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section on-white" id="tarify">
    <div class="lp-wrap">
      <div class="lp-eyebrow">Цены</div>
      <h2 class="lp-h2">Выберите тариф</h2>
      <p class="lp-sub">SSL и защита от перегрузок во всех тарифах. Без скрытых платежей.</p>

      <div class="lp-plans">
        <?php foreach (array_values($plans) as $i => $plan): ?>
          <?php
            $top   = count($plans) > 1 && $i === 1;
            $disk  = round((int) $plan['disk_quota_mb'] / 1024, 1);
            $sites = (int) $plan['max_sites'];
            $dbs   = (int) $plan['max_databases'];
          ?>
          <div class="lp-plan<?= $top ? ' is-top' : '' ?>">
            <?php if ($top): ?>
              <span class="lp-plan-tag"><?= lp_icon('star') ?>Популярный</span>
            <?php endif; ?>

            <div class="lp-plan-name"><?= Html::e($plan['title']) ?></div>
            <div class="lp-plan-price"><span>TJS</span><b><?= (int) $plan['price_tjs'] ?></b></div>
            <div class="lp-plan-per">/ мес · <b>SSL бесплатно</b></div>

            <hr>

            <ul>
              <li><span class="lp-tile t-blue"><?= lp_icon('disk') ?></span><?= $disk ?> ГБ NVMe SSD</li>
              <li><span class="lp-tile t-green"><?= lp_icon('globe') ?></span><?= $sites ?> <?= Html::plural($sites, 'сайт', 'сайта', 'сайтов') ?></li>
              <li><span class="lp-tile t-orange"><?= lp_icon('database') ?></span><?= $dbs ?> <?= Html::plural($dbs, 'база', 'базы', 'баз') ?> данных</li>
              <li><span class="lp-tile t-green"><?= lp_icon('lock') ?></span>SSL-сертификат</li>
              <li><span class="lp-tile t-red"><?= lp_icon('shield') ?></span>Защита от перегрузок</li>
              <li><span class="lp-tile t-purple"><?= lp_icon('code') ?></span>PHP, MySQL, phpMyAdmin</li>
              <li><span class="lp-tile t-blue"><?= lp_icon('restore') ?></span>Бэкап каждую ночь</li>
            </ul>

            <a class="lp-btn <?= $top ? 'lp-btn-primary' : 'lp-btn-ghost' ?>"
               href="<?= Html::e($startHref) ?>">Начать<?= lp_icon('arrow') ?></a>
          </div>
        <?php endforeach; ?>
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
