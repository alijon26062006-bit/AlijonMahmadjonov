<?php
/** @var string $csrf
 *  @var list<array<string,mixed>> $databases
 *  @var array<string,mixed> $user
 *  @var string $rootDomain
 *  @var string $dbUser
 *  @var string|null $freshPassword
 *  @var string|null $storedPassword
 */
use Hosting\Support\Html;

$pma = 'https://db.' . $rootDomain;
$password = $freshPassword ?? $storedPassword;

$copyIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
     stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/>
     <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/></svg>';
$eyeIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
     stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/>
     <circle cx="12" cy="12" r="3"/></svg>';

/** Поле «значение + кнопка скопировать». */
$field = static function (string $label, string $value, string $icon): string {
    return '<div class="field"><span class="field-main"><span class="field-label">' . Html::e($label) . '</span>'
        . '<span class="field-value">' . Html::e($value) . '</span></span>'
        . '<button type="button" class="icon-btn" title="Скопировать" data-copy="' . Html::e($value) . '">'
        . $icon . '</button></div>';
};
?>
<div class="card" style="background:linear-gradient(135deg,#12234B,#0E1A38);border:0;color:#E2E8F0;text-align:center;">
  <span class="tile-ico" style="background:rgba(255,255,255,.08);color:#F59E0B;margin:0 auto 14px;width:56px;height:56px;">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="width:28px;height:28px;">
      <ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>
    </svg>
  </span>
  <h2 style="margin:0 0 8px;color:#fff;">Базы данных</h2>
  <p style="margin:0;color:#94A3B8;font-size:15px;">
    Ваша личная база с полной защитой.<br>Другие клиенты доступа к ней не имеют.
  </p>
</div>

<?php if ($freshPassword !== null): ?>
  <div class="card" style="border:2px solid var(--success);background:var(--success-soft);">
    <b style="color:#14532D;">Новый пароль создан</b>
    <p class="muted" style="margin:6px 0 0;color:#14532D;">Он сохранён и показан ниже — записывать отдельно не нужно.</p>
  </div>
<?php endif; ?>

<?php foreach ($databases as $database): ?>
  <div class="card">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
      <span class="tile-ico t-orange" style="width:44px;height:44px;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
          <ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>
        </svg>
      </span>
      <b style="flex:1 1 auto;font-size:17px;word-break:break-all;"><?= Html::e($database['db_name']) ?></b>
      <span class="muted"><?= Html::e(date('d.m.Y', strtotime((string) $database['created_at']))) ?></span>
    </div>

    <?= $field('Хост', 'localhost', $copyIcon) ?>
    <?= $field('Имя базы', (string) $database['db_name'], $copyIcon) ?>
    <?= $field('Пользователь', $dbUser, $copyIcon) ?>

    <div class="field">
      <span class="field-main">
        <span class="field-label">Пароль</span>
        <?php if ($password !== null): ?>
          <span class="field-value" id="pw-<?= (int) $database['id'] ?>" data-hidden="1"
                data-secret="<?= Html::e($password) ?>">••••••••••</span>
        <?php else: ?>
          <span class="field-value">не сохранён — нажмите «Новый пароль»</span>
        <?php endif; ?>
      </span>
      <?php if ($password !== null): ?>
        <button type="button" class="icon-btn" title="Показать" data-reveal="#pw-<?= (int) $database['id'] ?>"><?= $eyeIcon ?></button>
        <button type="button" class="icon-btn" title="Скопировать" data-copy="<?= Html::e($password) ?>"><?= $copyIcon ?></button>
      <?php endif; ?>
    </div>

    <?= $field('Порт', '3306', $copyIcon) ?>

    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;">
      <a class="btn secondary" href="<?= Html::e($pma) ?>" target="_blank" rel="noopener">phpMyAdmin</a>
      <form method="post" action="/databases/password"
            data-confirm="Сменить пароль? Старый перестанет работать во всех сайтах.">
        <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
        <button type="submit" class="secondary">Новый пароль</button>
      </form>
      <form method="post" action="/databases/<?= (int) $database['id'] ?>/delete"
            data-confirm="Удалить базу <?= Html::e($database['db_name']) ?> со всеми таблицами? Это необратимо.">
        <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
        <button type="submit" class="danger">Удалить</button>
      </form>
    </div>
  </div>
<?php endforeach; ?>

<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;">
    <span>
      <b style="font-size:17px;">Добавить базу</b><br>
      <span class="muted">Максимум: <?= (int) $user['max_databases'] ?> <?= Html::plural((int) $user['max_databases'], 'база', 'базы', 'баз') ?> по тарифу</span>
    </span>
  </div>
  <form method="post" action="/databases" style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;margin-top:14px;">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <div style="flex:1 1 180px;">
      <label>Имя базы</label>
      <input type="text" name="name" placeholder="shop" required pattern="[a-z][a-z0-9_]{1,24}">
      <div class="muted" style="margin-top:6px;">Полное имя: <code><?= Html::e($user['system_user']) ?>_имя</code></div>
    </div>
    <button type="submit">+ Создать базу</button>
  </form>
</div>

<div class="card">
  <h2 style="margin-top:0;display:flex;align-items:center;gap:10px;">
    <svg viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="1.9" stroke-linecap="round"
         stroke-linejoin="round" style="width:22px;height:22px;"><path d="M12 3l7 3v6c0 4-3 7.5-7 9-4-1.5-7-5-7-9V6l7-3Z"/></svg>
    Защита
  </h2>
  <div style="display:grid;gap:14px;">
    <div style="display:flex;gap:14px;align-items:flex-start;">
      <span class="tile-ico t-green" style="width:40px;height:40px;flex:none;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" style="width:20px;height:20px;"><path d="M12 3l7 3v6c0 4-3 7.5-7 9-4-1.5-7-5-7-9V6l7-3Z"/></svg>
      </span>
      <span><b>Полная изоляция</b><br><span class="muted">Каждый клиент видит только свою базу</span></span>
    </div>
    <div style="display:flex;gap:14px;align-items:flex-start;">
      <span class="tile-ico t-blue" style="width:40px;height:40px;flex:none;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" style="width:20px;height:20px;"><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>
      </span>
      <span><b>Надёжный пароль</b><br><span class="muted">Случайный, выдаётся сервером, хранится зашифрованным</span></span>
    </div>
    <div style="display:flex;gap:14px;align-items:flex-start;">
      <span class="tile-ico t-red" style="width:40px;height:40px;flex:none;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" style="width:20px;height:20px;"><circle cx="12" cy="12" r="9"/><path d="m6 6 12 12"/></svg>
      </span>
      <span><b>Доступ снаружи закрыт</b><br><span class="muted">База отвечает только с этого сервера</span></span>
    </div>
  </div>
</div>
