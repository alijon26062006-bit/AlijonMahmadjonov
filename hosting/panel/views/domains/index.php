<?php
/** @var string $csrf
 *  @var array<string,mixed> $site
 *  @var list<array<string,mixed>> $domains
 */
use Hosting\Support\Html;
$sslLabel = ['none' => 'нет', 'pending' => 'выпускается', 'issued' => 'выпущен', 'failed' => 'ошибка'];
?>
<p><a href="/sites">&larr; к сайтам</a> · <?= Html::e($site['domain']) ?></p>

<div class="card">
  <h2>Привязать домен</h2>
  <form method="post" action="/sites/<?= (int) $site['id'] ?>/domains" style="display:flex;gap:10px;align-items:end;flex-wrap:wrap;">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <div style="flex:1;min-width:220px;">
      <label>Домен</label>
      <input type="text" name="domain" placeholder="example.tj" required>
    </div>
    <button type="submit">Добавить</button>
  </form>
  <p class="muted">После добавления направьте A-запись домена на IP сервера, затем нажмите «Проверить DNS».</p>
</div>

<div class="card">
  <h2>Домены сайта</h2>
  <?php if ($domains === []): ?>
    <p class="muted">Собственных доменов пока нет.</p>
  <?php else: ?>
  <table>
    <thead><tr><th>Домен</th><th>DNS</th><th>SSL</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($domains as $domain): ?>
      <tr>
        <td><?= Html::e($domain['domain']) ?>
          <?php if ($domain['last_error']): ?><br><span class="muted"><?= Html::e($domain['last_error']) ?></span><?php endif; ?>
        </td>
        <td><span class="badge <?= $domain['verified'] ? 'active' : 'pending' ?>"><?= $domain['verified'] ? 'проверен' : 'не проверен' ?></span></td>
        <td><span class="badge <?= $domain['ssl_status'] === 'issued' ? 'active' : 'pending' ?>"><?= Html::e($sslLabel[$domain['ssl_status']] ?? $domain['ssl_status']) ?></span></td>
        <td style="white-space:nowrap;">
          <form method="post" action="/sites/<?= (int) $site['id'] ?>/domains/<?= (int) $domain['id'] ?>/verify" style="display:inline;">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <button type="submit" class="secondary">Проверить DNS</button>
          </form>
          <?php if ($domain['verified'] && $domain['ssl_status'] !== 'issued'): ?>
          <form method="post" action="/sites/<?= (int) $site['id'] ?>/domains/<?= (int) $domain['id'] ?>/ssl" style="display:inline;">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <button type="submit" class="secondary">Выпустить SSL</button>
          </form>
          <?php endif; ?>
          <form method="post" action="/sites/<?= (int) $site['id'] ?>/domains/<?= (int) $domain['id'] ?>/delete" style="display:inline;"
                onsubmit="return confirm('Отвязать домен?');">
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
