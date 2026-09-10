<?php
/** @var string $csrf
 *  @var list<array<string,mixed>> $sites
 *  @var array<string,mixed> $user
 *  @var string $rootDomain
 */
use Hosting\Support\Html;
$statusLabel = ['pending' => 'создаётся', 'active' => 'активен', 'suspended' => 'приостановлен', 'deleted' => 'удалён'];
?>
<div class="card">
  <h2>Новый сайт</h2>
  <form method="post" action="/sites" style="display:flex;gap:10px;align-items:end;flex-wrap:wrap;">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <div style="flex:1;min-width:180px;">
      <label>Поддомен</label>
      <input type="text" name="slug" placeholder="shop" required pattern="[a-z0-9-]{3,30}">
    </div>
    <div class="muted" style="padding-bottom:10px;">.<?= Html::e($rootDomain) ?></div>
    <button type="submit">Создать</button>
  </form>
  <p class="muted">Сайтов: <?= count($sites) ?> / <?= Html::e($user['max_sites']) ?> по тарифу</p>
</div>

<div class="card">
  <h2>Мои сайты</h2>
  <?php if ($sites === []): ?>
    <p class="muted">Пока нет ни одного сайта.</p>
  <?php else: ?>
  <table>
    <thead><tr><th>Домен</th><th>PHP</th><th>Статус</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($sites as $site): ?>
      <tr>
        <td>
          <a href="https://<?= Html::e($site['domain']) ?>" target="_blank" rel="noopener"><?= Html::e($site['domain']) ?></a><br>
          <a class="muted" href="/sites/<?= (int) $site['id'] ?>/files">файлы</a> ·
          <a class="muted" href="/sites/<?= (int) $site['id'] ?>/logs">логи</a> ·
          <a class="muted" href="/sites/<?= (int) $site['id'] ?>/domains">домены</a>
        </td>
        <td><?= Html::e($site['php_version']) ?></td>
        <td><span class="badge <?= Html::e($site['status']) ?>"><?= Html::e($statusLabel[$site['status']] ?? $site['status']) ?></span></td>
        <td style="white-space:nowrap;">
          <?php if ($site['status'] === 'active'): ?>
            <form method="post" action="/sites/<?= (int) $site['id'] ?>/suspend" style="display:inline;">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <button type="submit" class="secondary">Приостановить</button>
            </form>
          <?php elseif ($site['status'] === 'suspended'): ?>
            <form method="post" action="/sites/<?= (int) $site['id'] ?>/unsuspend" style="display:inline;">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <button type="submit" class="secondary">Возобновить</button>
            </form>
          <?php endif; ?>
          <form method="post" action="/sites/<?= (int) $site['id'] ?>/delete" style="display:inline;"
                onsubmit="return confirm('Удалить сайт вместе с файлами безвозвратно?');">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <button type="submit" class="danger">Удалить</button>
          </form>
        </td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
  <?php endif; ?>
</div>
