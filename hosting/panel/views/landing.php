<?php
/** @var list<array<string,mixed>> $plans
 *  @var string $rootDomain
 *  @var string $botUsername
 *  @var string $appUrl
 */
use Hosting\Support\Html;
?>
<style>
  .hero { text-align:center; padding:48px 16px 32px; }
  .hero h1 { font-size:34px; margin:0 0 12px; line-height:1.2; }
  .hero p.lead { font-size:17px; color:var(--muted); max-width:520px; margin:0 auto 28px; }
  .tg-box { display:flex; flex-direction:column; align-items:center; gap:10px; min-height:60px; }
  .plans { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; }
  .plan { background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:20px; }
  .plan h3 { margin:0 0 4px; font-size:18px; }
  .plan .price { font-size:30px; font-weight:700; margin:8px 0 16px; }
  .plan .price span { font-size:14px; font-weight:400; color:var(--muted); }
  .plan ul { list-style:none; padding:0; margin:0; font-size:14px; }
  .plan li { padding:5px 0; border-bottom:1px solid var(--border); }
  .plan li:last-child { border-bottom:0; }
  .steps { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }
  .step { padding:16px; }
  .step .num { display:inline-flex; width:28px; height:28px; align-items:center; justify-content:center;
                border-radius:50%; background:var(--accent); color:#052e16; font-weight:700; margin-bottom:8px; }
</style>

<div class="hero">
  <h1>Хостинг для PHP-сайтов</h1>
  <p class="lead">
    WordPress, Laravel или свой код — заливаете файлы и сайт работает.
    Бесплатный адрес вида <code>вашсайт.<?= Html::e($rootDomain) ?></code>, база данных,
    SSL-сертификат и защита от перегрузок включены в любой тариф.
  </p>

  <div class="tg-box">
    <?php if ($botUsername !== ''): ?>
      <script async src="https://telegram.org/js/telegram-widget.js?22"
              data-telegram-login="<?= Html::e($botUsername) ?>"
              data-size="large"
              data-userpic="false"
              data-auth-url="<?= Html::e($appUrl) ?>/telegram/widget"
              data-request-access="write"></script>
      <div class="muted">Вход в один клик — без пароля и анкет</div>
      <?php // Виджет выше работает только после /setdomain в @BotFather. Ссылка на
            // самого бота работает всегда — чтобы посетитель не упёрся в пустое место,
            // если админ ещё не дошёл до этой настройки. ?>
      <div style="margin-top:10px;">
        <a class="btn" href="https://t.me/<?= Html::e($botUsername) ?>">Открыть в Telegram</a>
      </div>
    <?php else: ?>
      <a class="btn" href="/register">Создать аккаунт</a>
      <div class="muted">Вход через Telegram появится, когда админ настроит бота</div>
    <?php endif; ?>
    <div class="muted" style="margin-top:6px;">
      <a href="/login">Вход по e-mail</a> · <a href="/register">регистрация по e-mail</a>
    </div>
  </div>
</div>

<div class="card">
  <h2 style="margin-top:0;">Как это работает</h2>
  <div class="steps">
    <div class="step">
      <div class="num">1</div>
      <div><strong>Входите через Telegram</strong><br>
        <span class="muted">Аккаунт создаётся сам, ничего заполнять не нужно</span></div>
    </div>
    <div class="step">
      <div class="num">2</div>
      <div><strong>Создаёте сайт</strong><br>
        <span class="muted">Придумываете имя — адрес выдаётся сразу</span></div>
    </div>
    <div class="step">
      <div class="num">3</div>
      <div><strong>Заливаете файлы</strong><br>
        <span class="muted">Через панель или ZIP-архивом, база данных — в один клик</span></div>
    </div>
  </div>
</div>

<div class="card">
  <h2 style="margin-top:0;">Тарифы</h2>
  <div class="plans">
    <?php foreach ($plans as $plan): ?>
      <div class="plan">
        <h3><?= Html::e($plan['title']) ?></h3>
        <div class="price"><?= Html::e((int) $plan['price_tjs']) ?> <span>сомони / мес</span></div>
        <ul>
          <li><?= Html::e(round((int) $plan['disk_quota_mb'] / 1024, 1)) ?> ГБ на диске</li>
          <li><?= Html::e($plan['max_sites']) ?> <?= ((int) $plan['max_sites']) === 1 ? 'сайт' : 'сайтов' ?></li>
          <li><?= Html::e($plan['max_databases']) ?> баз данных</li>
          <li>SSL-сертификат бесплатно</li>
          <li>Резервные копии каждую ночь</li>
        </ul>
      </div>
    <?php endforeach; ?>
  </div>
  <p class="muted" style="margin-top:16px;">
    Оплата после регистрации. Сначала можно всё попробовать.
  </p>
</div>

<div class="card">
  <h2 style="margin-top:0;">Что внутри</h2>
  <table>
    <tr><td>PHP</td><td class="muted">Свежая версия, отдельный процесс на каждого клиента</td></tr>
    <tr><td>База данных</td><td class="muted">MariaDB, доступ через phpMyAdmin</td></tr>
    <tr><td>Файлы</td><td class="muted">Менеджер в панели, загрузка ZIP, SFTP</td></tr>
    <tr><td>Адреса</td><td class="muted">Бесплатный поддомен или свой домен с SSL</td></tr>
    <tr><td>Резервные копии</td><td class="muted">Автоматически, восстановление из панели</td></tr>
    <tr><td>Защита</td><td class="muted">Firewall, Fail2ban, изоляция клиентов друг от друга</td></tr>
  </table>
</div>
