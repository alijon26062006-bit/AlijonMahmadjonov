<?php
/**
 * УСТАНОВЩИК В ОДИН ФАЙЛ — для установки прямо с телефона.
 *
 * Как пользоваться:
 *   1. В файловом менеджере хостинга создайте в корне сайта файл setup.php
 *      и вставьте в него этот код.
 *   2. Откройте в браузере https://ваш-домен/setup.php
 *   3. Заполните форму и нажмите «Установить».
 *
 * Установщик сам скачает все файлы бота из GitHub, создаст настройки и
 * таблицы, включит webhook и удалит себя после успешной установки.
 *
 * Ничего распаковывать не нужно — компьютер не требуется.
 */
declare(strict_types=1);

const REPO_BASE = 'https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/'
                . 'claude/tariff-management-admin-panel-6ojoo2/cargo_bot_php/';

/** Файлы бота: путь в репозитории => куда положить на сайте. */
function manifest(): array
{
    return [
        '.htaccess'          => '.htaccess',
        'public/index.php'   => 'index.php',
        'config.example.php' => 'config.example.php',
        'README.md'          => 'README.md',
        'bin/install.php'    => 'bin/install.php',
        'bin/set_webhook.php' => 'bin/set_webhook.php',
        'bin/selftest.php'   => 'bin/selftest.php',
        'src/autoload.php'   => 'src/autoload.php',
        'src/Config.php'     => 'src/Config.php',
        'src/Database.php'   => 'src/Database.php',
        'src/Schema.php'     => 'src/Schema.php',
        'src/Seeder.php'     => 'src/Seeder.php',
        'src/Bot.php'        => 'src/Bot.php',
        'src/Texts.php'      => 'src/Texts.php',
        'src/Util/Format.php' => 'src/Util/Format.php',
        'src/Telegram/Api.php' => 'src/Telegram/Api.php',
        'src/Telegram/Keyboard.php' => 'src/Telegram/Keyboard.php',
        'src/Repository/Repository.php'  => 'src/Repository/Repository.php',
        'src/Repository/SettingsRepo.php' => 'src/Repository/SettingsRepo.php',
        'src/Repository/StateRepo.php'   => 'src/Repository/StateRepo.php',
        'src/Repository/UserRepo.php'    => 'src/Repository/UserRepo.php',
        'src/Service/Calculator.php' => 'src/Service/Calculator.php',
        'src/Service/Audit.php'      => 'src/Service/Audit.php',
        'src/Service/Notify.php'     => 'src/Service/Notify.php',
        'src/Service/Export.php'     => 'src/Service/Export.php',
        'src/Handler/Router.php'     => 'src/Handler/Router.php',
        'src/Handler/User/StartHandler.php' => 'src/Handler/User/StartHandler.php',
        'src/Handler/User/CalcHandler.php'  => 'src/Handler/User/CalcHandler.php',
        'src/Handler/User/OrderHandler.php' => 'src/Handler/User/OrderHandler.php',
        'src/Handler/User/TrackHandler.php' => 'src/Handler/User/TrackHandler.php',
        'src/Handler/User/InfoHandler.php'  => 'src/Handler/User/InfoHandler.php',
        'src/Handler/Admin/Registry.php'   => 'src/Handler/Admin/Registry.php',
        'src/Handler/Admin/CrudHandler.php' => 'src/Handler/Admin/CrudHandler.php',
        'src/Handler/Admin/AdminHandler.php' => 'src/Handler/Admin/AdminHandler.php',
        'src/Handler/Admin/OrdersHandler.php' => 'src/Handler/Admin/OrdersHandler.php',
        'src/Handler/Admin/TracksHandler.php' => 'src/Handler/Admin/TracksHandler.php',
        'src/Handler/Admin/BroadcastHandler.php' => 'src/Handler/Admin/BroadcastHandler.php',
    ];
}

// --------------------------------------------------------------------- утилиты
function fetch(string $url): ?string
{
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_USERAGENT      => 'CargoBotSetup',
        ]);
        // некоторые хостинги выходят в интернет через прокси
        if ($proxy = getenv('HTTPS_PROXY')) {
            curl_setopt($ch, CURLOPT_PROXY, $proxy);
        }
        $body = curl_exec($ch);
        $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        if ($body !== false && $code === 200) {
            return (string) $body;
        }
    }
    if (ini_get('allow_url_fopen')) {
        $body = @file_get_contents($url);
        if ($body !== false) {
            return (string) $body;
        }
    }
    return null;
}

function tgCall(string $token, string $method, array $params = []): ?array
{
    $body = fetch('https://api.telegram.org/bot' . $token . '/' . $method
                  . ($params ? '?' . http_build_query($params) : ''));
    if ($body === null) {
        return null;
    }
    $data = json_decode($body, true);
    return is_array($data) ? $data : null;
}

function siteBaseUrl(): string
{
    $https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
             || ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https'
             || (int) ($_SERVER['SERVER_PORT'] ?? 80) === 443;
    $host = $_SERVER['HTTP_HOST'] ?? 'localhost';
    $dir = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/');
    return ($https ? 'https://' : 'http://') . $host . $dir;
}

function isHttps(): bool
{
    return strncmp(siteBaseUrl(), 'https://', 8) === 0;
}

// ------------------------------------------------------------------ проверки
$checks = [
    'PHP 7.4 или новее' => [version_compare(PHP_VERSION, '7.4.0', '>='), PHP_VERSION],
    'Расширение curl'   => [function_exists('curl_init'), function_exists('curl_init') ? 'есть' : 'нет'],
    'Расширение json'   => [function_exists('json_encode'), function_exists('json_encode') ? 'есть' : 'нет'],
    'Расширение mbstring' => [function_exists('mb_strlen'), function_exists('mb_strlen') ? 'есть' : 'нет'],
    'База MySQL (pdo_mysql)' => [extension_loaded('pdo_mysql'), extension_loaded('pdo_mysql') ? 'есть' : 'нет'],
    'База SQLite (pdo_sqlite)' => [extension_loaded('pdo_sqlite'), extension_loaded('pdo_sqlite') ? 'есть' : 'нет'],
    'Запись в папку сайта' => [is_writable(__DIR__), is_writable(__DIR__) ? 'разрешена' : 'запрещена'],
    'Сайт работает по HTTPS' => [isHttps(), isHttps() ? 'да' : 'нет — Telegram требует https'],
];

$fatal = !$checks['PHP 7.4 или новее'][0]
         || !$checks['Расширение curl'][0]
         || !$checks['Запись в папку сайта'][0]
         || (!extension_loaded('pdo_mysql') && !extension_loaded('pdo_sqlite'));

$done = false;
$doneBot = '';
$steps = [];
$error = null;

// ------------------------------------------------------------------ установка
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST' && !$fatal) {
    @set_time_limit(300);

    $token   = trim((string) ($_POST['token'] ?? ''));
    $adminId = trim((string) ($_POST['admin_id'] ?? ''));
    $dbKind  = (string) ($_POST['db_kind'] ?? 'sqlite');

    try {
        if ($token === '' || strpos($token, ':') === false) {
            throw new RuntimeException('Токен бота указан неверно. Он выглядит так: 1234567890:AAE...');
        }
        if (!preg_match('/^\d+$/', $adminId)) {
            throw new RuntimeException('Telegram ID должен быть числом. Узнать его: @userinfobot');
        }

        // 1. Проверяем токен
        $me = tgCall($token, 'getMe');
        if (!$me || empty($me['ok'])) {
            $why = $me['description'] ?? '';
            throw new RuntimeException('Telegram не принял токен'
                . ($why !== '' ? ': ' . $why : '. Проверьте его у @BotFather'));
        }
        $botName = (string) ($me['result']['username'] ?? '?');
        $steps[] = ['ok', 'Токен рабочий. Бот: @' . $botName];

        // 2. Скачиваем файлы бота
        $written = 0;
        foreach (manifest() as $remote => $local) {
            $content = fetch(REPO_BASE . $remote);
            if ($content === null || $content === '') {
                throw new RuntimeException("Не удалось скачать файл: $remote. "
                    . 'Возможно, хостинг блокирует доступ к github.com.');
            }
            $target = __DIR__ . '/' . $local;
            $dir = dirname($target);
            if (!is_dir($dir) && !@mkdir($dir, 0755, true)) {
                throw new RuntimeException("Не удалось создать папку: $dir");
            }
            if (@file_put_contents($target, $content) === false) {
                throw new RuntimeException("Не удалось записать файл: $local");
            }
            $written++;
        }
        $steps[] = ['ok', "Файлы бота загружены: $written шт."];

        // 3. Настройки
        $secret = bin2hex(random_bytes(16));
        if ($dbKind === 'mysql') {
            $dbName = trim((string) ($_POST['db_name'] ?? ''));
            $dbUser = trim((string) ($_POST['db_user'] ?? ''));
            $dbPass = (string) ($_POST['db_pass'] ?? '');
            $dbHost = trim((string) ($_POST['db_host'] ?? '')) ?: 'localhost';
            if ($dbName === '' || $dbUser === '') {
                throw new RuntimeException('Для MySQL укажите имя базы и пользователя.');
            }
            $dsn = "mysql:host=$dbHost;dbname=$dbName;charset=utf8mb4";
            $dbBlock = "[\n        'dsn'  => " . var_export($dsn, true) . ",\n"
                     . "        'user' => " . var_export($dbUser, true) . ",\n"
                     . "        'pass' => " . var_export($dbPass, true) . ",\n    ]";
        } else {
            $dsn = "sqlite:' . __DIR__ . '/data/cargo.sqlite";
            $dbBlock = "[\n        'dsn'  => 'sqlite:' . __DIR__ . '/data/cargo.sqlite',\n"
                     . "        'user' => null,\n        'pass' => null,\n    ]";
        }

        $config = "<?php\n// Настройки бота. Создано установщиком "
                . date('d.m.Y H:i') . ".\nreturn [\n"
                . "    'bot_token'      => " . var_export($token, true) . ",\n"
                . "    'admin_ids'      => [" . (int) $adminId . "],\n"
                . "    'webhook_secret' => " . var_export($secret, true) . ",\n"
                . "    'db' => $dbBlock,\n"
                . "    'timezone' => 'Asia/Dushanbe',\n"
                . "    'log_file' => __DIR__ . '/data/bot.log',\n];\n";

        if (@file_put_contents(__DIR__ . '/config.php', $config) === false) {
            throw new RuntimeException('Не удалось создать config.php');
        }
        @chmod(__DIR__ . '/config.php', 0600);
        if (!is_dir(__DIR__ . '/data')) {
            @mkdir(__DIR__ . '/data', 0775, true);
        }
        $steps[] = ['ok', 'Настройки сохранены (' . ($dbKind === 'mysql' ? 'MySQL' : 'SQLite') . ')'];

        // 4. Таблицы и демо-данные
        require __DIR__ . '/src/autoload.php';
        $cfg = CargoBot\Config::load(__DIR__ . '/config.php');
        $db = new CargoBot\Database($cfg->db());
        foreach (CargoBot\Schema::statements($db->driver()) as $sql) {
            try {
                $db->pdo()->exec($sql);
            } catch (PDOException $e) {
                if (stripos($e->getMessage(), 'exist') === false
                    && stripos($e->getMessage(), 'duplicate') === false) {
                    throw $e;
                }
            }
        }
        (new CargoBot\Seeder($db))->run();
        $tariffs = (int) $db->value('SELECT COUNT(*) FROM tariffs');
        $steps[] = ['ok', "Таблицы созданы, загружено тарифов: $tariffs"];

        // 5. Webhook
        $webhookUrl = siteBaseUrl() . '/index.php';
        $res = tgCall($token, 'setWebhook', [
            'url'                  => $webhookUrl,
            'secret_token'         => $secret,
            'drop_pending_updates' => 'true',
        ]);
        if (!$res || empty($res['ok'])) {
            throw new RuntimeException('Не удалось включить webhook: '
                . ($res['description'] ?? 'нет ответа от Telegram')
                . '. Адрес: ' . $webhookUrl);
        }
        $steps[] = ['ok', 'Webhook включён: ' . $webhookUrl];

        // 6. Сообщение администратору в Telegram
        tgCall($token, 'sendMessage', [
            'chat_id' => $adminId,
            'text'    => "✅ Бот установлен и работает!\n\n"
                       . "Отправьте /start — меню клиента.\n"
                       . "Отправьте /admin — панель управления тарифами.",
        ]);
        $steps[] = ['ok', 'Вам отправлено сообщение в Telegram'];

        // 7. Установщик удаляет себя
        if (@unlink(__FILE__)) {
            $steps[] = ['ok', 'Установщик удалил себя (так безопаснее)'];
        } else {
            $steps[] = ['warn', 'Удалите файл setup.php вручную через файловый менеджер'];
        }

        $done = true;
        $doneBot = $botName;
    } catch (Throwable $e) {
        $error = $e->getMessage();
    }
}

$base = siteBaseUrl();
?><!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Установка Cargo Bot</title>
<style>
*{box-sizing:border-box}
body{margin:0;padding:16px;font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
     background:#0f1115;color:#e8eaed}
.wrap{max-width:560px;margin:0 auto}
h1{font-size:22px;margin:8px 0 4px}
p.sub{color:#9aa0a6;margin:0 0 20px}
.card{background:#1a1d23;border:1px solid #2a2e37;border-radius:14px;padding:16px;margin-bottom:16px}
label{display:block;margin:14px 0 6px;font-weight:600;font-size:14px}
input,select{width:100%;padding:14px;font-size:16px;border-radius:10px;border:1px solid #343945;
     background:#0f1115;color:#e8eaed}
input:focus,select:focus{outline:2px solid #4c8bf5;border-color:#4c8bf5}
small{display:block;color:#9aa0a6;margin-top:5px;font-size:13px}
button{width:100%;padding:16px;margin-top:22px;font-size:17px;font-weight:600;border:0;
     border-radius:10px;background:#4c8bf5;color:#fff}
button:disabled{background:#3a3f4b;color:#8b9098}
.row{display:flex;gap:10px}.row>div{flex:1}
.chk{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px solid #23262e;font-size:14px}
.chk:last-child{border:0}
.ok{color:#4ade80}.bad{color:#f87171}.warn{color:#fbbf24}
.step{padding:10px 0;border-bottom:1px solid #23262e;font-size:15px}
.step:last-child{border:0}
.big{font-size:19px;font-weight:600;margin:0 0 12px}
code{background:#0f1115;border:1px solid #2a2e37;border-radius:6px;padding:2px 6px;
     font-size:13px;word-break:break-all}
.hide{display:none}
a{color:#7aa7f7}
</style>
</head>
<body>
<div class="wrap">

<?php if ($done): ?>
  <div class="card">
    <p class="big ok">✅ Готово! Бот установлен</p>
    <?php foreach ($steps as [$kind, $text]): ?>
      <div class="step <?= $kind === 'ok' ? 'ok' : 'warn' ?>">
        <?= $kind === 'ok' ? '✓' : '!' ?> <?= htmlspecialchars($text, ENT_QUOTES, 'UTF-8') ?>
      </div>
    <?php endforeach; ?>
  </div>
  <div class="card">
    <p class="big">Что дальше</p>
    <p>Откройте бота в Telegram: <b>@<?= htmlspecialchars($doneBot ?? '', ENT_QUOTES, 'UTF-8') ?></b></p>
    <p>• <code>/start</code> — меню клиента<br>
       • <code>/admin</code> — панель управления тарифами</p>
    <p style="color:#9aa0a6">Все тарифы, коэффициенты, курсы валют, сборы и скидки
       меняются прямо в боте через <code>/admin</code>. Код править не нужно.</p>
  </div>

<?php else: ?>
  <h1>Установка Cargo Bot</h1>
  <p class="sub">Бот карго-доставки Китай → Таджикистан.<br>Установка прямо с телефона, за один шаг.</p>

  <div class="card">
    <p class="big">Проверка хостинга</p>
    <?php foreach ($checks as $name => [$ok, $note]): ?>
      <div class="chk">
        <span><?= htmlspecialchars($name, ENT_QUOTES, 'UTF-8') ?></span>
        <span class="<?= $ok ? 'ok' : ($name === 'База MySQL (pdo_mysql)' || $name === 'База SQLite (pdo_sqlite)' ? 'warn' : 'bad') ?>">
          <?= $ok ? '✓' : '✕' ?> <?= htmlspecialchars((string) $note, ENT_QUOTES, 'UTF-8') ?>
        </span>
      </div>
    <?php endforeach; ?>
  </div>

  <?php if ($fatal): ?>
    <div class="card">
      <p class="big bad">Хостинг не подходит</p>
      <p>Не хватает того, что отмечено красным. Напишите в поддержку хостинга —
         попросите включить нужное расширение PHP, либо смените тариф.</p>
    </div>
  <?php else: ?>

    <?php if (!isHttps()): ?>
      <div class="card">
        <p class="big warn">⚠️ Нужен HTTPS</p>
        <p>Сейчас страница открыта по <code>http://</code>, а Telegram отправляет
           сообщения боту только на <code>https://</code>.</p>
        <p>Включите бесплатный SSL-сертификат в панели хостинга (обычно раздел
           «SSL» или «Let's Encrypt»), затем откройте эту страницу заново по адресу
           <code>https://<?= htmlspecialchars($_SERVER['HTTP_HOST'] ?? '', ENT_QUOTES, 'UTF-8') ?>/setup.php</code></p>
      </div>
    <?php endif; ?>

    <?php if ($error !== null): ?>
      <div class="card">
        <p class="big bad">Ошибка установки</p>
        <p><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></p>
        <?php foreach ($steps as [$kind, $text]): ?>
          <div class="step ok">✓ <?= htmlspecialchars($text, ENT_QUOTES, 'UTF-8') ?></div>
        <?php endforeach; ?>
      </div>
    <?php endif; ?>

    <form method="post" class="card">
      <p class="big">Данные бота</p>

      <label for="token">Токен бота</label>
      <input id="token" name="token" required placeholder="1234567890:AAE..."
             value="<?= htmlspecialchars((string) ($_POST['token'] ?? ''), ENT_QUOTES, 'UTF-8') ?>">
      <small>Получить у @BotFather → /mybots → ваш бот → API Token</small>

      <label for="admin_id">Ваш Telegram ID</label>
      <input id="admin_id" name="admin_id" required inputmode="numeric" placeholder="123456789"
             value="<?= htmlspecialchars((string) ($_POST['admin_id'] ?? ''), ENT_QUOTES, 'UTF-8') ?>">
      <small>Узнать: напишите @userinfobot. Только этот ID получит доступ к /admin</small>

      <label for="db_kind">База данных</label>
      <select id="db_kind" name="db_kind" onchange="document.getElementById('my').className = this.value==='mysql' ? '' : 'hide'">
        <option value="sqlite"<?= extension_loaded('pdo_sqlite') ? '' : ' disabled' ?>>SQLite — проще, ничего создавать не нужно</option>
        <option value="mysql"<?= (($_POST['db_kind'] ?? '') === 'mysql') ? ' selected' : '' ?><?= extension_loaded('pdo_mysql') ? '' : ' disabled' ?>>MySQL — если база уже создана в панели</option>
      </select>
      <small>Не знаете что выбрать — оставьте SQLite, потом можно перейти на MySQL</small>

      <div id="my" class="<?= (($_POST['db_kind'] ?? '') === 'mysql') ? '' : 'hide' ?>">
        <label for="db_name">Имя базы MySQL</label>
        <input id="db_name" name="db_name" placeholder="user_cargo"
               value="<?= htmlspecialchars((string) ($_POST['db_name'] ?? ''), ENT_QUOTES, 'UTF-8') ?>">
        <div class="row">
          <div>
            <label for="db_user">Пользователь</label>
            <input id="db_user" name="db_user"
                   value="<?= htmlspecialchars((string) ($_POST['db_user'] ?? ''), ENT_QUOTES, 'UTF-8') ?>">
          </div>
          <div>
            <label for="db_pass">Пароль базы</label>
            <input id="db_pass" name="db_pass" type="password">
          </div>
        </div>
        <label for="db_host">Сервер базы</label>
        <input id="db_host" name="db_host" placeholder="localhost"
               value="<?= htmlspecialchars((string) ($_POST['db_host'] ?? 'localhost'), ENT_QUOTES, 'UTF-8') ?>">
      </div>

      <button type="submit"<?= isHttps() ? '' : ' disabled' ?>>
        <?= isHttps() ? 'Установить бота' : 'Сначала включите HTTPS' ?>
      </button>
      <small style="margin-top:14px">Установщик скачает файлы бота, создаст таблицы,
        включит webhook по адресу <code><?= htmlspecialchars($base, ENT_QUOTES, 'UTF-8') ?>/index.php</code>
        и удалит себя.</small>
    </form>
  <?php endif; ?>
<?php endif; ?>

</div>
</body>
</html>
