<?php

declare(strict_types=1);

use Hosting\Service\FileManager;
use Hosting\Service\PhpSyntax;
use Hosting\Service\SiteEnv;
use Hosting\Service\SiteTemplates;
use Hosting\Service\TelegramWebhook;
use Hosting\Support\JobLabel;

/** Каталог сайта как на сервере: <site>/public, <site>/.env, <site>/storage, <site>/logs. */
function hosting_test_site_dir(): string
{
    static $dir = null;
    if ($dir === null) {
        $dir = sys_get_temp_dir() . '/hosting-site-' . getmypid();
        foreach (['public', 'storage', 'logs'] as $sub) {
            @mkdir($dir . '/' . $sub, 0o770, true);
        }
    }
    return $dir;
}

// ── Проверка синтаксиса PHP перед сохранением ──────────────────────────────

function test_php_syntax_rejects_broken_code(): void
{
    $bad = PhpSyntax::check("<?php\n\$a = 1;\nfoo bar baz(\n");
    assert_false($bad['ok']);
    assert_true($bad['line'] !== null, 'Должна быть указана строка ошибки');

    $text = PhpSyntax::describe($bad);
    assert_true(str_contains($text, 'строке'), 'Сообщение должно называть строку: ' . $text);
    // Внутренние пути сервера клиенту не показываем.
    assert_false(str_contains($text, '/home'), 'В сообщении не должно быть путей сервера');
    assert_false(str_contains($text, '/tmp'), 'В сообщении не должно быть путей сервера');
}

function test_php_syntax_accepts_valid_code(): void
{
    foreach ([
        '<?php echo "привет";',
        "<?php\nfunction f(array \$x): int { return count(\$x); }\n",
        'обычный текст без php',
        '<?php $a = [1,2]; foreach ($a as $v) { echo $v; }',
    ] as $code) {
        assert_true(PhpSyntax::check($code)['ok'], 'Должно считаться корректным: ' . $code);
    }
}

function test_all_templates_are_valid_php(): void
{
    // Шаблон с ошибкой синтаксиса — это сломанный сайт сразу после нажатия кнопки.
    foreach (SiteTemplates::all() as $key => $template) {
        foreach ($template['files'] as $name => $code) {
            if (!str_ends_with($name, '.php')) {
                continue;
            }
            $result = PhpSyntax::check($code);
            assert_true($result['ok'], "Шаблон {$key}/{$name}: " . PhpSyntax::describe($result));
        }
    }
    assert_true(PhpSyntax::check(SiteTemplates::defaultIndex())['ok'], 'Стартовая страница сайта должна быть валидной');
}

function test_webhook_template_checks_secret_before_anything_else(): void
{
    $code = SiteTemplates::all()['telegram']['files']['public/webhook.php'];

    // Секрет обязателен: без проверки заголовка webhook примет запрос от любого,
    // кто узнал адрес.
    assert_true(str_contains($code, 'HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'), 'Шаблон должен читать заголовок секрета');
    assert_true(str_contains($code, 'hash_equals'), 'Сравнение секрета должно быть за постоянное время');
    assert_true(str_contains($code, '403'), 'При неверном секрете должен возвращаться 403');
    // Токен не должен быть вписан в файл, который отдаёт веб-сервер.
    assert_false((bool) preg_match('~\d{6,}:[A-Za-z0-9_-]{20,}~', $code), 'В шаблоне не должно быть токена');
    assert_true(str_contains($code, "dirname(__DIR__) . '/.env'"), 'Секреты должны читаться из .env над public/');
}

// ── Имена файлов ────────────────────────────────────────────────────────────

function test_file_name_suggestion_never_produces_broken_extension(): void
{
    assert_equals('index.php', FileManager::suggestName('index'));
    assert_equals('webhook.php', FileManager::suggestName('webhook'));
    // Уже указанное расширение не трогаем — именно попытки «поправить» его
    // и давали файлы вроде index.pp.
    assert_equals('index.php', FileManager::suggestName('index.php'));
    assert_equals('style.css', FileManager::suggestName('style.css'));
    assert_equals('.env', FileManager::suggestName('.env'));
    assert_equals('', FileManager::suggestName(''));
}

// ── Файловый менеджер не выпускает за пределы сайта ────────────────────────

function test_file_manager_blocks_escape_from_site_directory(): void
{
    $site = hosting_test_site_dir();
    $fm = new FileManager($site);

    $secret = dirname($site) . '/hosting-outside-' . getmypid() . '.txt';
    file_put_contents($secret, 'секрет соседа');

    foreach ([
        '../' . basename($secret),
        '../../etc/passwd',
        '/etc/passwd',
        'public/../../' . basename($secret),
        "public/..\\..\\" . basename($secret),
    ] as $attempt) {
        $escaped = false;
        try {
            $fm->read($attempt);
            $escaped = true;
        } catch (\Throwable) {
            // ожидаемо
        }
        assert_false($escaped, 'Удалось выйти за пределы сайта: ' . $attempt);
    }

    @unlink($secret);
}

function test_file_manager_blocks_symlink_escape(): void
{
    $site = hosting_test_site_dir();
    $outside = dirname($site) . '/hosting-outside-dir-' . getmypid();
    @mkdir($outside, 0o770, true);
    file_put_contents($outside . '/secret.txt', 'чужое');

    $link = $site . '/public/escape';
    @unlink($link);
    if (!@symlink($outside, $link)) {
        return; // на файловой системе без симлинков проверять нечего
    }

    $fm = new FileManager($site);
    $escaped = false;
    try {
        $fm->read('public/escape/secret.txt');
        $escaped = true;
    } catch (\Throwable) {
        // ожидаемо: realpath уводит наружу, Path::resolve это ловит
    }

    @unlink($link);
    @unlink($outside . '/secret.txt');
    @rmdir($outside);

    assert_false($escaped, 'Симлинк выпустил за пределы каталога сайта');
}

function test_file_manager_creates_nested_file_for_template(): void
{
    $site = hosting_test_site_dir();
    $fm = new FileManager($site);

    $path = $fm->createFileDeep('public/api/index.php', '<?php echo 1;', true);
    assert_true(is_file($path), 'Файл шаблона не создан');
    assert_true(str_starts_with($path, realpath($site)), 'Файл создан вне каталога сайта');

    @unlink($path);
    @rmdir($site . '/public/api');
}

// ── .env сайта ──────────────────────────────────────────────────────────────

function test_site_env_stores_and_masks_token(): void
{
    $site = hosting_test_site_dir();
    $env = new SiteEnv($site);

    $env->set(['TELEGRAM_BOT_TOKEN' => '123456789:AAEsecret-token-value', 'OTHER' => 'значение']);
    assert_equals('123456789:AAEsecret-token-value', $env->get('TELEGRAM_BOT_TOKEN'));

    // Повторная запись не плодит дубли и не теряет чужие строки.
    $env->set(['TELEGRAM_BOT_TOKEN' => '987654321:BBBnew-token-value']);
    assert_equals('987654321:BBBnew-token-value', $env->get('TELEGRAM_BOT_TOKEN'));
    assert_equals('значение', $env->get('OTHER'));
    assert_equals(1, substr_count((string) file_get_contents($env->path()), 'TELEGRAM_BOT_TOKEN='));

    // В интерфейс полный токен не возвращается никогда.
    $masked = SiteEnv::maskToken('987654321:BBBnew-token-value');
    assert_true(str_starts_with($masked, '987654321:BBBn'), 'Маска: ' . $masked);
    assert_false(str_contains($masked, 'new-token-value'), 'Маска не должна содержать сам токен');

    @unlink($env->path());
}

function test_site_env_lives_outside_public(): void
{
    $env = new SiteEnv(hosting_test_site_dir());
    // Каталог, который отдаёт веб-сервер, — public/. .env обязан быть НАД ним,
    // иначе его можно просто скачать по адресу сайта.
    assert_false(str_contains($env->path(), '/public/'), '.env не должен лежать внутри public/');
}

// ── Telegram ────────────────────────────────────────────────────────────────

function test_telegram_errors_never_leak_token(): void
{
    $text = 'Failed with 123456789:AAEabcdefghijklmnopqrstuvwxyz01 while calling';
    $clean = TelegramWebhook::scrub($text);

    assert_false(str_contains($clean, 'AAEabcdefghijklmnopqrstuvwxyz01'), 'Токен просочился: ' . $clean);
    assert_true(str_contains($clean, 'скрыт'), 'Должна остаться пометка о скрытом токене');
}

function test_telegram_webhook_secret_is_long_and_valid(): void
{
    $secret = TelegramWebhook::generateSecret();
    assert_true(strlen($secret) >= 24, 'Секрет слишком короткий: ' . strlen($secret));
    // Telegram принимает только A-Z a-z 0-9 _ -
    assert_true((bool) preg_match('~^[A-Za-z0-9_-]+$~', $secret), 'Недопустимые символы в секрете: ' . $secret);
    assert_true(TelegramWebhook::generateSecret() !== $secret, 'Секрет должен быть случайным');
}

function test_telegram_errors_are_explained_in_human_words(): void
{
    assert_true(str_contains((string) TelegramWebhook::explain(['last_error_message' => 'SSL error']), 'сертификат'));
    assert_true(str_contains((string) TelegramWebhook::explain(['last_error_message' => 'webhook: 404']), 'webhook.php'));
    assert_true(str_contains((string) TelegramWebhook::explain(['last_error_message' => 'webhook: 500']), 'Логи'));
    assert_true(TelegramWebhook::explain([]) === null, 'Без ошибки объяснять нечего');
}

// ── Названия операций ───────────────────────────────────────────────────────

function test_job_names_are_shown_in_human_words(): void
{
    assert_equals('Создание сайта', JobLabel::type('create_site'));
    assert_equals('Создание базы данных', JobLabel::type('create_database'));
    assert_equals('Создание резервной копии', JobLabel::type('create_backup'));
    // Незнакомый тип не показываем как есть — внутреннее имя клиенту ни о чём не говорит.
    assert_equals('Операция', JobLabel::type('some_internal_thing'));

    assert_equals('В очереди', JobLabel::status('pending'));
    assert_equals('Выполняется', JobLabel::status('running'));
    assert_equals('Готово', JobLabel::status('success'));
    assert_equals('Ошибка', JobLabel::status('failed'));
}

// ── Права на созданные файлы ────────────────────────────────────────────────

function test_files_created_by_panel_are_readable_by_client_php(): void
{
    // Реальный случай с сервера: файл, созданный панелью, принадлежит
    // пользователю hosting-panel, а выполняет его php-fpm КЛИЕНТА — он не
    // владелец и не в группе, то есть «остальной». При правах 0660 сайт отдавал
    // 403 на собственный файл. Изоляцию обеспечивает каталог (2770), поэтому
    // бит чтения для «остальных» ничего не открывает посторонним.
    $site = hosting_test_site_dir();
    $fm = new FileManager($site);

    $created = $fm->createFile('public', 'perm-check.php', '<?php echo 1;');
    clearstatcache();
    $mode = fileperms($created) & 0o777;
    assert_true(($mode & 0o004) !== 0, sprintf('Файл создан с правами 0%o — php-fpm клиента его не прочитает', $mode));

    $fm->write('public/perm-check.php', '<?php echo 2;');
    clearstatcache();
    $mode = fileperms($created) & 0o777;
    assert_true(($mode & 0o004) !== 0, sprintf('После сохранения права стали 0%o', $mode));

    @unlink($created);
}

function test_site_env_is_readable_by_client_php(): void
{
    // webhook.php читает секрет из .env под пользователем клиента.
    $env = new SiteEnv(hosting_test_site_dir());
    $env->set(['TELEGRAM_WEBHOOK_SECRET' => 'proverka']);
    clearstatcache();
    $mode = fileperms($env->path()) & 0o777;
    assert_true(($mode & 0o004) !== 0, sprintf('.env с правами 0%o — webhook.php не прочитает секрет', $mode));

    @unlink($env->path());
}

// ── Домен хостинга ──────────────────────────────────────────────────────────

function test_domain_validation_rejects_pasted_commands(): void
{
    // Реальный случай: человек вставил в терминал две команды сразу, и вторая
    // строка попала в ответ на вопрос о домене. Мастер это принял, и дальше
    // сломалось всё — vhost не собрался, Telegram отверг адрес Mini App.
    $bad = [
        'sudo bash hosting/scripts/telegram.sh',
        'диёрхост.ком',
        '',
        '-bad.com',
        'no-dot',
        'domain.com/path',
        'два слова.com',
    ];
    foreach ($bad as $value) {
        assert_false(\Hosting\Support\Domain::isValidFqdn($value), 'Должно отклоняться: ' . $value);
    }

    foreach (['diyorhost.com', 'panel.diyorhost.com', 'a-b.example.tj'] as $value) {
        assert_true(\Hosting\Support\Domain::isValidFqdn($value), 'Должно приниматься: ' . $value);
    }
}
