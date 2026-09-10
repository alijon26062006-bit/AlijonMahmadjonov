<?php
/** @var string $csrf
 *  @var array<string,mixed> $site
 *  @var list<array<string,mixed>> $jobs
 *  @var bool $hasWebhookFile
 *  @var string $botToken
 *  @var string $botMasked
 *  @var string $botUsername
 *  @var string $webhookUrl
 *  @var array<string,mixed>|null $webhookInfo
 *  @var string|null $webhookHint
 *  @var array<string,mixed>|null $health
 */
use Hosting\Support\Html;
use Hosting\Support\JobLabel;

$sid    = (int) $site['id'];
$status = (string) $site['status'];
$domain = (string) $site['domain'];

$statusText = match ($status) {
    'active'    => 'Активен',
    'pending'   => 'Создаётся',
    'suspended' => 'Приостановлен',
    'error'     => 'Ошибка создания',
    default     => $status,
};
$statusClass = match ($status) {
    'active'  => 'active',
    'pending' => 'pending',
    default   => 'suspended',
};

// Пока сайт создаётся — обновляем страницу сами, чтобы человек не жал F5.
$lastJob = $jobs[0] ?? null;
$failed  = $lastJob !== null && $lastJob['status'] === 'failed';
$stages  = JobLabel::siteStages();
$doneStages = match (true) {
    $status === 'active' => count($stages),
    $failed              => 0,
    $lastJob === null    => 0,
    $lastJob['status'] === 'running' => 3,
    default              => 1,
};
?>
<?php if ($status === 'pending' && !$failed): ?>
  <meta http-equiv="refresh" content="4">
<?php endif; ?>

<style>
  .st-head { display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-bottom:16px; }
  .st-head h1 { margin:0; font-size:clamp(20px,5vw,28px); word-break:break-all; }
  .st-actions { display:grid; gap:10px; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); }
  .st-actions .btn { width:100%; justify-content:center; }
  .st-kv { display:grid; gap:10px; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); }
  .st-kv div { background:var(--surface-2); border:1px solid var(--border); border-radius:var(--r-md); padding:12px 14px; }
  .st-kv dt { font-size:12.5px; color:var(--muted); font-weight:600; text-transform:uppercase; letter-spacing:.05em; }
  .st-kv dd { margin:4px 0 0; font-weight:600; word-break:break-all; }
  .st-steps { display:grid; gap:10px; margin:0; padding:0; list-style:none; }
  .st-step { display:flex; align-items:center; gap:12px; font-size:15px; }
  .st-dot { flex:none; width:26px; height:26px; border-radius:50%; display:grid; place-items:center;
            background:var(--surface-2); color:var(--muted); font-size:13px; font-weight:700; }
  .st-step.is-done .st-dot { background:var(--success-soft); color:var(--success); }
  .st-step.is-done { color:var(--text); }
  .st-step.is-wait { color:var(--muted); }
  .st-jobs { display:grid; gap:8px; }
  .st-job { display:flex; flex-wrap:wrap; justify-content:space-between; gap:8px; padding:10px 12px;
            background:var(--surface-2); border-radius:var(--r-sm); font-size:14px; }
  .tg-row { display:grid; gap:10px; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); }
  .tg-row form, .tg-row .btn { width:100%; }
  .tg-row button { width:100%; }
  .mono { font-family:ui-monospace,monospace; font-size:13.5px; word-break:break-all; }
  @media (max-width:640px) { .st-actions { grid-template-columns:1fr 1fr; } }
</style>

<div class="st-head">
  <a class="btn secondary" href="/sites">← Сайты</a>
  <h1><?= Html::e($domain) ?></h1>
  <span class="badge <?= $statusClass ?>"><?= Html::e($statusText) ?></span>
</div>

<?php if ($status === 'pending' && !$failed): ?>
  <div class="card">
    <h2 style="margin-top:0;">Сайт создаётся</h2>
    <p class="muted">Это занимает несколько секунд. Страница обновится сама.</p>
    <ul class="st-steps">
      <?php foreach ($stages as $i => $stage): ?>
        <li class="st-step <?= $i < $doneStages ? 'is-done' : 'is-wait' ?>">
          <span class="st-dot"><?= $i < $doneStages ? '✓' : (string) ($i + 1) ?></span>
          <?= Html::e($stage) ?>
        </li>
      <?php endforeach; ?>
    </ul>
  </div>
<?php endif; ?>

<?php if ($failed || $status === 'error'): ?>
  <div class="card" style="border-color:#F7C9C9;background:var(--danger-soft);">
    <h2 style="margin-top:0;color:#991B1B;">Сайт не создался</h2>
    <p style="color:#991B1B;margin-bottom:0;">
      <?= Html::e($lastJob['error_text'] ?? 'Провижининг завершился с ошибкой.') ?><br>
      Попробуйте удалить сайт и создать заново. Если повторится — напишите в поддержку.
    </p>
  </div>
<?php endif; ?>

<div class="card">
  <div class="st-actions">
    <a class="btn" href="https://<?= Html::e($domain) ?>" target="_blank" rel="noopener">Открыть сайт</a>
    <a class="btn secondary" href="/sites/<?= $sid ?>/files">Файлы</a>
    <a class="btn secondary" href="/sites/<?= $sid ?>/logs">Логи</a>
    <a class="btn secondary" href="/sites/<?= $sid ?>/domains">Домены</a>
    <a class="btn secondary" href="/databases">Базы данных</a>
    <a class="btn secondary" href="/backups">Бэкапы</a>
    <a class="btn secondary" href="#telegram">Telegram-бот</a>
  </div>
</div>

<div class="card">
  <h2 style="margin-top:0;">Проверка сайта</h2>
  <?php if ($health !== null): ?>
    <div class="st-kv" style="margin-bottom:14px;">
      <div><dt>Ответ</dt><dd><?= $health['ok'] ? 'Сайт работает' : 'Сайт не отвечает' ?></dd></div>
      <div><dt>HTTP</dt><dd><?= (int) $health['status'] ?: '—' ?></dd></div>
      <div><dt>Время ответа</dt><dd><?= (int) $health['ms'] ?> мс</dd></div>
      <div><dt>SSL</dt><dd><?= $health['ssl'] ? 'Активен' : 'Нет' ?></dd></div>
    </div>
    <?php if (!empty($health['hint'])): ?>
      <p class="muted" style="margin-top:0;"><?= Html::e((string) $health['hint']) ?></p>
    <?php endif; ?>
  <?php endif; ?>
  <form method="post" action="/sites/<?= $sid ?>/health">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <button type="submit" class="secondary">Проверить сайт</button>
  </form>
</div>

<div class="card">
  <h2 style="margin-top:0;">О сайте</h2>
  <div class="st-kv">
    <div><dt>Адрес</dt><dd><?= Html::e($domain) ?></dd></div>
    <div><dt>PHP</dt><dd><?= Html::e($site['php_version']) ?></dd></div>
    <div><dt>Каталог сайта</dt><dd class="mono">public/</dd></div>
    <div><dt>Создан</dt><dd><?= Html::e(date('d.m.Y', strtotime((string) $site['created_at']))) ?></dd></div>
  </div>
</div>

<div class="card" id="telegram">
  <h2 style="margin-top:0;">Telegram-бот</h2>
  <p class="muted" style="margin-top:0;">
    Токен хранится в <span class="mono">.env</span> над <span class="mono">public/</span> — из браузера он недоступен.
  </p>

  <form method="post" action="/sites/<?= $sid ?>/telegram/token" style="margin-bottom:18px;">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <label><?= $botToken !== '' ? 'Токен бота (сохранён)' : 'Токен бота от @BotFather' ?></label>
    <?php if ($botToken !== ''): ?>
      <p class="mono" style="margin:0 0 10px;"><?= Html::e($botMasked) ?><?= $botUsername !== '' ? ' — @' . Html::e($botUsername) : '' ?></p>
    <?php endif; ?>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <input type="password" name="token" placeholder="123456789:AAE…" autocomplete="off"
             style="flex:1 1 220px;" <?= $botToken === '' ? 'required' : '' ?>>
      <button type="submit"><?= $botToken !== '' ? 'Изменить токен' : 'Сохранить токен' ?></button>
    </div>
  </form>

  <div class="tg-row">
    <form method="post" action="/sites/<?= $sid ?>/telegram/webhook-file"
          <?= $hasWebhookFile ? 'data-confirm="webhook.php уже есть. Перезаписать шаблоном?"' : '' ?>>
      <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
      <?php if ($hasWebhookFile): ?><input type="hidden" name="overwrite" value="1"><?php endif; ?>
      <button type="submit" class="secondary"><?= $hasWebhookFile ? 'Пересоздать webhook.php' : 'Создать webhook.php' ?></button>
    </form>

    <form method="post" action="/sites/<?= $sid ?>/telegram/connect">
      <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
      <button type="submit">Подключить webhook</button>
    </form>

    <form method="post" action="/sites/<?= $sid ?>/telegram/check">
      <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
      <button type="submit" class="secondary">Проверить webhook</button>
    </form>

    <form method="post" action="/sites/<?= $sid ?>/telegram/disconnect"
          data-confirm="Отключить webhook? Бот перестанет получать сообщения.">
      <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
      <button type="submit" class="danger">Отключить webhook</button>
    </form>
  </div>

  <?php if ($webhookInfo !== null): ?>
    <?php $active = !empty($webhookInfo['url']); ?>
    <div class="st-kv" style="margin-top:18px;">
      <div><dt>Статус</dt><dd><?= $active ? 'Активен' : 'Не подключён' ?></dd></div>
      <div><dt>Адрес</dt><dd class="mono"><?= Html::e((string) ($webhookInfo['url'] ?? '—')) ?></dd></div>
      <div><dt>Необработанных</dt><dd><?= (int) ($webhookInfo['pending_update_count'] ?? 0) ?></dd></div>
      <div><dt>Соединений</dt><dd><?= (int) ($webhookInfo['max_connections'] ?? 0) ?: '—' ?></dd></div>
      <?php if (!empty($webhookInfo['last_error_date'])): ?>
        <div><dt>Последняя ошибка</dt>
          <dd><?= Html::e(date('d.m.Y H:i', (int) $webhookInfo['last_error_date'])) ?></dd></div>
      <?php endif; ?>
    </div>
    <?php if ($webhookHint !== null): ?>
      <p style="margin:12px 0 0;color:#991B1B;"><?= Html::e($webhookHint) ?></p>
    <?php endif; ?>
  <?php else: ?>
    <p class="muted" style="margin-bottom:0;">Адрес webhook: <span class="mono"><?= Html::e($webhookUrl) ?></span></p>
  <?php endif; ?>
</div>

<?php if ($jobs !== []): ?>
  <div class="card">
    <h2 style="margin-top:0;">Последние операции</h2>
    <div class="st-jobs">
      <?php foreach ($jobs as $job): ?>
        <div class="st-job">
          <span><?= Html::e(JobLabel::type((string) $job['type'])) ?></span>
          <span class="muted">
            <?= Html::e(JobLabel::status((string) $job['status'])) ?>
            <?php if ($job['status'] === 'failed' && !empty($job['error_text'])): ?>
              — <?= Html::e(mb_substr((string) $job['error_text'], 0, 120)) ?>
            <?php endif; ?>
          </span>
        </div>
      <?php endforeach; ?>
    </div>
  </div>
<?php endif; ?>
