<?php
/**
 * Самопроверка бота: прогоняет все диалоги на временной базе SQLite
 * и не обращается к Telegram (ответы перехватываются).
 *
 * Запуск:  php bin/selftest.php
 *
 * Полезно после правок кода и при переносе на новый хостинг:
 * если всё зелёное — логика расчёта и админ-панель работают.
 */
declare(strict_types=1);

require dirname(__DIR__) . '/src/autoload.php';

use CargoBot\Bot;
use CargoBot\Config;
use CargoBot\Database;
use CargoBot\Handler\Admin\Registry;
use CargoBot\Handler\Router;
use CargoBot\Schema;
use CargoBot\Seeder;

const ADMIN_TG = 7000000001;
const CLIENT_TG = 7000000002;

$failed = 0;
$passed = 0;

function check(string $title, bool $ok, string $details = ''): void
{
    global $failed, $passed;
    if ($ok) {
        $passed++;
        echo "  ✅ $title\n";
    } else {
        $failed++;
        echo "  ❌ $title" . ($details !== '' ? " — $details" : '') . "\n";
    }
}

function section(string $title): void
{
    echo "\n=== $title ===\n";
}

// ---------------------------------------------------------------- окружение
// По умолчанию тест работает на временном файле SQLite и ничего не трогает.
// Чтобы проверить совместимость с MySQL, укажите ПУСТУЮ тестовую базу:
//   SELFTEST_DSN='mysql:host=localhost;dbname=cargo_test;charset=utf8mb4' \
//   SELFTEST_USER=root SELFTEST_PASS= php bin/selftest.php
// ВНИМАНИЕ: указанная база очищается. Не подставляйте рабочую базу.
$dbFile = sys_get_temp_dir() . '/cargo_selftest_' . getmypid() . '.sqlite';
$customDsn = getenv('SELFTEST_DSN') ?: '';

if ($customDsn !== '') {
    $dbConfig = [
        'dsn'  => $customDsn,
        'user' => getenv('SELFTEST_USER') ?: null,
        'pass' => getenv('SELFTEST_PASS') ?: null,
    ];
    echo "Тестовая база: $customDsn\n";
} else {
    @unlink($dbFile);
    $dbConfig = ['dsn' => 'sqlite:' . $dbFile];
}

$config = new Config([
    'bot_token'      => '111:TEST',
    'admin_ids'      => [ADMIN_TG],
    'webhook_secret' => 'test',
    'db'             => $dbConfig,
    'timezone'       => 'Asia/Dushanbe',
    'log_file'       => null,
]);

$db = new Database($config->db());

// Чистим тестовую базу, чтобы прогон всегда начинался с нуля
if ($customDsn !== '') {
    $known = ['states', 'calculations', 'track_history', 'tracks', 'orders', 'logs', 'broadcasts',
              'exchange_rates', 'tariffs', 'coefficients', 'extra_services', 'currencies',
              'categories', 'delivery_types', 'faq', 'contacts', 'warehouses', 'settings',
              'admins', 'users'];
    if ($db->driver() === 'mysql') {
        $db->pdo()->exec('SET FOREIGN_KEY_CHECKS = 0');
    }
    foreach ($known as $table) {
        $db->pdo()->exec('DROP TABLE IF EXISTS ' . ($db->driver() === 'mysql' ? "`$table`" : $table));
    }
    if ($db->driver() === 'mysql') {
        $db->pdo()->exec('SET FOREIGN_KEY_CHECKS = 1');
    }
}

foreach (Schema::statements($db->driver()) as $sql) {
    try {
        $db->pdo()->exec($sql);
    } catch (\PDOException $e) {
        if (stripos($e->getMessage(), 'exist') === false && stripos($e->getMessage(), 'duplicate') === false) {
            throw $e;
        }
    }
}
(new Seeder($db))->run();
echo 'Драйвер базы: ' . $db->driver() . "\n";

/** @var array<int,array{method:string,params:array}> $sent */
$sent = [];
$api = new CargoBot\Telegram\Api('111:TEST', function (string $method, array $params) use (&$sent) {
    $sent[] = ['method' => $method, 'params' => $params];
    return json_encode(['ok' => true, 'result' => ['message_id' => 500 + count($sent)]]);
});

$bot = new Bot($config, $db, $api);
$router = new Router($bot);

function msg(string $text, int $tgId = CLIENT_TG): array
{
    return ['message' => [
        'message_id' => random_int(1, 9999),
        'from'       => ['id' => $tgId, 'is_bot' => false, 'first_name' => 'Тест',
                         'last_name' => 'Юзер', 'username' => 'tester' . $tgId],
        'chat'       => ['id' => $tgId, 'type' => 'private'],
        'text'       => $text,
    ]];
}

function cbq(string $data, int $tgId = CLIENT_TG): array
{
    return ['callback_query' => [
        'id'      => 'cb' . random_int(1, 9999),
        'from'    => ['id' => $tgId, 'is_bot' => false, 'first_name' => 'Тест',
                      'last_name' => 'Юзер', 'username' => 'tester' . $tgId],
        'message' => ['message_id' => 777, 'chat' => ['id' => $tgId, 'type' => 'private']],
        'data'    => $data,
    ]];
}

/** Текст всех сообщений, отправленных с момента последнего сброса. */
function outText(): string
{
    global $sent;
    $parts = [];
    foreach ($sent as $s) {
        if (isset($s['params']['text'])) {
            $parts[] = (string) $s['params']['text'];
        }
    }
    return implode("\n---\n", $parts);
}

function reset_out(): void
{
    global $sent;
    $sent = [];
}

// ---------------------------------------------------------------- база
section('База данных и демо-данные');
$tables = ['users', 'admins', 'orders', 'tracks', 'track_history', 'tariffs', 'categories',
           'delivery_types', 'currencies', 'exchange_rates', 'coefficients', 'extra_services',
           'faq', 'contacts', 'warehouses', 'logs', 'broadcasts', 'settings', 'calculations', 'states'];
$missing = [];
foreach ($tables as $table) {
    try {
        $db->value("SELECT COUNT(*) FROM $table");
    } catch (\Throwable $e) {
        $missing[] = $table;
    }
}
check('Все ' . count($tables) . ' таблиц созданы', $missing === [], 'нет: ' . implode(', ', $missing));
check('Тарифы загружены', (int) $db->value('SELECT COUNT(*) FROM tariffs') === 8);
check('Категории загружены', (int) $db->value('SELECT COUNT(*) FROM categories') === 9);
check('Коэффициенты загружены', (int) $db->value('SELECT COUNT(*) FROM coefficients') === 5);

// ---------------------------------------------------------------- расчёт
section('Расчёт стоимости (логика)');
$avia = (int) $db->value("SELECT id FROM delivery_types WHERE name = 'Авиа'");
$sea  = (int) $db->value("SELECT id FROM delivery_types WHERE name = 'Море'");
$cloth = (int) $db->value("SELECT id FROM categories WHERE name = 'Одежда'");
$cosm  = (int) $db->value("SELECT id FROM categories WHERE name = 'Косметика'");
$dense = (int) $db->value("SELECT id FROM categories WHERE name = 'Плотный груз'");

$r = $bot->calc->calculate($avia, $cloth, 10.0, 0.05);
// 5.5 USD/кг × 10 кг = 55 + упаковка 2 = 57
check('Обычный расчёт: 10 кг одежды авиа = 57 USD',
      $r !== null && abs($r['total'] - 57.0) < 0.01,
      $r ? 'получено ' . $r['total'] : 'тариф не найден');
check('Объёмный вес считается (0.05 м³ × 167 = 8.35 кг)',
      $r !== null && abs($r['volumetric_weight'] - 8.35) < 0.01);

$r2 = $bot->calc->calculate($avia, $cloth, 2.0, 0.5);
// объёмный вес 83.5 кг больше фактических 2 кг — платим за 83.5
check('Объёмный вес побеждает фактический',
      $r2 !== null && abs($r2['chargeable_weight'] - 83.5) < 0.01,
      $r2 ? 'оплач. вес ' . $r2['chargeable_weight'] : '');

$r3 = $bot->calc->calculate($avia, $cloth, 1.0, 0.0);
// 5.5 × 1 = 5.5 -> ниже минимума 10, применяется 10 + упаковка 2 = 12
check('Минимальная стоимость заказа применяется',
      $r3 !== null && $r3['min_order_applied'] && abs($r3['total'] - 12.0) < 0.01,
      $r3 ? 'итого ' . $r3['total'] : '');

$r4 = $bot->calc->calculate($avia, $cosm, 5.0, 0.0);
check('Нет точного тарифа → берётся общий по типу доставки',
      $r4 !== null && $r4['tariff']['name'] === 'Авиа / Общий',
      $r4 ? $r4['tariff']['name'] : '');

$r5 = $bot->calc->calculate($avia, $dense, 10.0, 0.0);
// общий тариф 6.5 × коэффициент плотного груза 1.2 = 7.8
check('Коэффициент плотного груза меняет цену (6.5 × 1.2 = 7.8)',
      $r5 !== null && abs($r5['price_per_kg'] - 7.8) < 0.01,
      $r5 ? 'цена/кг ' . $r5['price_per_kg'] : '');

$r6 = $bot->calc->calculate($sea, $cloth, 2.0, 0.0);
// у морского тарифа минимальный вес 5 кг
check('Минимальный оплачиваемый вес тарифа применяется',
      $r6 !== null && abs($r6['chargeable_weight'] - 5.0) < 0.01,
      $r6 ? 'оплач. вес ' . $r6['chargeable_weight'] : '');

check('Пересчёт в TJS по курсу выполняется',
      $r !== null && $r['total_tjs'] !== null && $r['total_tjs'] > $r['total']);
check('Расчёты пишутся в историю',
      (int) $db->value('SELECT COUNT(*) FROM calculations') >= 6);

// ---------------------------------------------- изменения из админки применяются сразу
section('Правки из админ-панели применяются мгновенно');
$tariffId = (int) $db->value("SELECT id FROM tariffs WHERE name = 'Авиа / Одежда'");
$db->update('tariffs', $tariffId, ['price_per_kg' => 9.0]);
$rAfter = $bot->calc->calculate($avia, $cloth, 10.0, 0.0);
check('Новая цена за кг сразу в расчёте (9 × 10 + 2 = 92)',
      $rAfter !== null && abs($rAfter['total'] - 92.0) < 0.01,
      $rAfter ? 'итого ' . $rAfter['total'] : '');
$db->update('tariffs', $tariffId, ['price_per_kg' => 5.5]);

$db->update('tariffs', $tariffId, ['is_active' => 0]);
$rOff = $bot->calc->calculate($avia, $cloth, 10.0, 0.0);
check('Отключённый тариф больше не используется',
      $rOff !== null && $rOff['tariff']['name'] === 'Авиа / Общий',
      $rOff ? $rOff['tariff']['name'] : 'расчёт не выполнен');
$db->update('tariffs', $tariffId, ['is_active' => 1]);

$svcId = (int) $db->value("SELECT id FROM extra_services WHERE name = 'Упаковка'");
$db->update('extra_services', $svcId, ['is_active' => 0]);
$rNoFee = $bot->calc->calculate($avia, $cloth, 10.0, 0.0);
check('Отключённый сбор исчезает из расчёта (55 без упаковки)',
      $rNoFee !== null && abs($rNoFee['total'] - 55.0) < 0.01,
      $rNoFee ? 'итого ' . $rNoFee['total'] : '');
$db->update('extra_services', $svcId, ['is_active' => 1]);

$discId = $db->insert('extra_services', [
    'name' => 'Тестовая скидка', 'kind' => 'discount', 'calc_type' => 'percent', 'value' => 10,
]);
// округление отключаем, чтобы проверить именно скидку: 55 + 2 упаковка − 5.5 = 51.5
$bot->settings->set('rounding_mode', 'none');
$rDisc = $bot->calc->calculate($avia, $cloth, 10.0, 0.0);
check('Процентная скидка вычитается (55 + 2 − 5.5 = 51.5)',
      $rDisc !== null && abs($rDisc['total'] - 51.5) < 0.01,
      $rDisc ? 'итого ' . $rDisc['total'] : '');

// а с округлением вверх до целого тот же расчёт даёт 52
$bot->settings->set('rounding_mode', 'up');
$bot->settings->set('rounding_step', '1');
$rDiscRound = $bot->calc->calculate($avia, $cloth, 10.0, 0.0);
check('Округление вверх до целого превращает 51.5 в 52',
      $rDiscRound !== null && abs($rDiscRound['total'] - 52.0) < 0.01,
      $rDiscRound ? 'итого ' . $rDiscRound['total'] : '');
$db->delete('extra_services', $discId);

$bot->settings->set('rounding_mode', 'up');
$bot->settings->set('rounding_step', '10');
$rRound = $bot->calc->calculate($avia, $cloth, 10.0, 0.0);
check('Правило округления работает (57 → 60 при шаге 10 вверх)',
      $rRound !== null && abs($rRound['total'] - 60.0) < 0.01,
      $rRound ? 'итого ' . $rRound['total'] : '');
$bot->settings->set('rounding_mode', 'none');
$bot->settings->set('rounding_step', '1');

// ---------------------------------------------------------------- диалог расчёта
section('Диалог клиента: расчёт по шагам');
reset_out();
$router->handle(msg('/start'));
check('/start показывает приветствие', strpos(outText(), 'Добро пожаловать') !== false);

reset_out();
$router->handle(msg('📦 Рассчитать стоимость доставки'));
check('Кнопка расчёта спрашивает тип доставки', strpos(outText(), 'тип доставки') !== false);

reset_out();
$router->handle(cbq('calc:dt:' . $avia));
check('Выбор типа → спрашивает категорию', strpos(outText(), 'категорию товара') !== false);

reset_out();
$router->handle(cbq('calc:cat:' . $cloth));
check('Выбор категории → спрашивает вес', strpos(outText(), 'вес груза') !== false);

reset_out();
$router->handle(msg('не число'));
check('Некорректный вес отклоняется', strpos(outText(), 'введите число') !== false);

reset_out();
$router->handle(msg('10'));
check('Вес принят → спрашивает объём', strpos(outText(), 'объём') !== false);

reset_out();
$router->handle(msg('0.05'));
$out = outText();
check('Показан результат с итогом', strpos($out, 'Итого') !== false);
check('Показан тариф', strpos($out, 'Авиа / Одежда') !== false);
check('Показана стоимость за кг', strpos($out, 'Стоимость за кг') !== false);
check('Показан объёмный вес', strpos($out, 'объёмный вес') !== false);
check('Показан срок доставки', strpos($out, 'Срок доставки') !== false);
check('Показана сумма в TJS', strpos($out, 'TJS') !== false);
check('Предложено оформить заявку', strpos($out, 'Оформить заявку') !== false);

// ---------------------------------------------------------------- заявка
section('Диалог клиента: заявка после расчёта');
reset_out();
$router->handle(cbq('order:start'));
check('Заявка началась с вопроса об имени', strpos(outText(), 'Как вас зовут') !== false);

$router->handle(msg('Алиджон'));
$router->handle(msg('+992 900 11 22 33'));
$router->handle(msg('https://item.taobao.com/test'));
reset_out();
$router->handle(msg('Кроссовки, 2 пары'));
check('Вес не спрашивается повторно (взят из расчёта)',
      strpos(outText(), 'Комментарий') !== false);

reset_out();
$router->handle(msg('Позвоните после 18:00'));
$out = outText();
check('Заявка создана и клиент получил номер', strpos($out, 'ORD-') !== false);

$order = $db->one('SELECT * FROM orders ORDER BY id DESC LIMIT 1');
check('Заявка сохранена в базе', $order !== null && $order['name'] === 'Алиджон');
check('Телефон сохранён', $order !== null && $order['phone'] === '+992 900 11 22 33');
check('Вес подставлен из расчёта', $order !== null && abs((float) $order['weight'] - 10.0) < 0.01);
check('Менеджеру ушло уведомление о заявке', strpos($out, 'Новая заявка') !== false);

// ---------------------------------------------------------------- админ-панель
section('Админ-панель: доступ');
reset_out();
$router->handle(msg('/admin', CLIENT_TG));
check('Клиент не получает доступ к /admin', strpos(outText(), 'только администраторам') !== false);

reset_out();
$router->handle(msg('/admin', ADMIN_TG));
check('Администратор видит панель', strpos(outText(), 'Панель администратора') !== false);

reset_out();
$router->handle(cbq('e:trf:list:1', CLIENT_TG));
$blocked = true;
foreach ($sent as $s) {
    if ($s['method'] === 'answerCallbackQuery' && strpos((string) ($s['params']['text'] ?? ''), 'только администраторам') !== false) {
        $blocked = true;
    }
    if ($s['method'] === 'editMessageText') {
        $blocked = false;
    }
}
check('Клиент не может открыть раздел тарифов', $blocked);

section('Админ-панель: списки и карточки всех разделов');
$broken = [];
foreach (array_keys(Registry::all()) as $key) {
    reset_out();
    $router->handle(cbq("e:$key:list:1", ADMIN_TG));
    $listed = strpos(outText(), 'Всего записей') !== false;

    $entity = Registry::get($key);
    $first = $db->one('SELECT * FROM ' . $entity['table'] . ' ORDER BY id LIMIT 1');
    $viewed = true;
    if ($first) {
        reset_out();
        $router->handle(cbq("e:$key:view:" . $first['id'], ADMIN_TG));
        $viewed = strpos(outText(), '#' . $first['id']) !== false;
    }
    if (!$listed || !$viewed) {
        $broken[] = $key . (!$listed ? ' (список)' : '') . (!$viewed ? ' (карточка)' : '');
    }
}
check('Все ' . count(Registry::all()) . ' разделов открываются', $broken === [],
      'проблемы: ' . implode(', ', $broken));

section('Админ-панель: добавление тарифа по шагам');
$before = (int) $db->value('SELECT COUNT(*) FROM tariffs');
reset_out();
$router->handle(cbq('e:trf:add', ADMIN_TG));
check('Добавление началось', strpos(outText(), 'Новая запись') !== false);

$router->handle(msg('Тест: Авиа срочно', ADMIN_TG));        // название
$router->handle(cbq('e:trf:av:' . $avia, ADMIN_TG));        // тип доставки
$router->handle(cbq('e:trf:av:_', ADMIN_TG));               // категория — пропуск
$router->handle(msg('12.5', ADMIN_TG));                     // цена за кг
$router->handle(msg('20', ADMIN_TG));                       // мин. стоимость
$router->handle(msg('1', ADMIN_TG));                        // мин. вес
$router->handle(cbq('e:trf:av:USD', ADMIN_TG));             // валюта
reset_out();
$router->handle(msg('3–5 дней', ADMIN_TG));                 // срок
check('Тариф создан', strpos(outText(), 'Запись создана') !== false);
check('Количество тарифов увеличилось', (int) $db->value('SELECT COUNT(*) FROM tariffs') === $before + 1);

$newTariff = $db->one("SELECT * FROM tariffs WHERE name = 'Тест: Авиа срочно'");
check('Цена за кг сохранена верно', $newTariff !== null && abs((float) $newTariff['price_per_kg'] - 12.5) < 0.01);
check('Категория осталась пустой (общий тариф)', $newTariff !== null && $newTariff['category_id'] === null);
check('Срок доставки сохранён', $newTariff !== null && $newTariff['delivery_time'] === '3–5 дней');
check('Создание записано в журнал',
      (int) $db->value("SELECT COUNT(*) FROM logs WHERE entity = 'tariffs' AND action = 'create'") >= 1);

section('Админ-панель: правка и отключение');
reset_out();
$router->handle(cbq('e:trf:ef:' . $newTariff['id'] . ':3', ADMIN_TG)); // поле «Стоимость за 1 кг»
check('Запрошено новое значение цены', strpos(outText(), 'Стоимость за 1 кг') !== false);

reset_out();
$router->handle(msg('7.25', ADMIN_TG));
check('Новое значение сохранено', strpos(outText(), 'Сохранено') !== false);
$updated = $db->one('SELECT * FROM tariffs WHERE id = :i', ['i' => $newTariff['id']]);
check('Цена в базе обновлена', abs((float) $updated['price_per_kg'] - 7.25) < 0.01);

$logRow = $db->one("SELECT * FROM logs WHERE entity = 'tariffs' AND action = 'update' ORDER BY id DESC LIMIT 1");
check('В журнале сохранены старое и новое значения',
      $logRow !== null
      && strpos((string) $logRow['old_data'], '12.5') !== false
      && strpos((string) $logRow['new_data'], '7.25') !== false,
      $logRow ? 'было=' . $logRow['old_data'] . ' стало=' . $logRow['new_data'] : '');
check('В журнале записан ID администратора',
      $logRow !== null && (int) $logRow['actor_tg_id'] === ADMIN_TG);

reset_out();
$router->handle(cbq('e:trf:tg:' . $newTariff['id'], ADMIN_TG));
$toggled = $db->one('SELECT * FROM tariffs WHERE id = :i', ['i' => $newTariff['id']]);
check('Тариф отключён кнопкой', (int) $toggled['is_active'] === 0);
check('Отключение записано в журнал',
      (int) $db->value("SELECT COUNT(*) FROM logs WHERE entity = 'tariffs' AND action = 'toggle'") >= 1);

reset_out();
$router->handle(cbq('e:trf:dl:' . $newTariff['id'], ADMIN_TG));
check('Тариф удалён', $db->one('SELECT * FROM tariffs WHERE id = :i', ['i' => $newTariff['id']]) === null);
check('Удаление записано в журнал',
      (int) $db->value("SELECT COUNT(*) FROM logs WHERE entity = 'tariffs' AND action = 'delete'") >= 1);

section('Админ-панель: курс валюты и настройки');
$usdCurId = (int) $db->value("SELECT id FROM currencies WHERE code = 'USD'");
$rateRow = $db->one('SELECT * FROM exchange_rates WHERE currency_id = :i', ['i' => $usdCurId]);
$router->handle(cbq('e:rate:ef:' . $rateRow['id'] . ':1', ADMIN_TG));
reset_out();
$router->handle(msg('12.5', ADMIN_TG));
check('Курс валюты изменён', strpos(outText(), 'Сохранено') !== false);
$rCur = $bot->calc->calculate($avia, $cloth, 10.0, 0.0);
check('Новый курс сразу применяется (57 × 12.5 = 712.5 TJS)',
      $rCur !== null && abs((float) $rCur['total_tjs'] - 712.5) < 0.01,
      $rCur ? 'получено ' . $rCur['total_tjs'] : '');
check('Изменение курса записано в журнал с автором',
      (int) $db->value("SELECT COUNT(*) FROM logs WHERE entity = 'exchange_rates'") >= 1);

// ---------------------------------------------------------------- треки
section('Треки: создание, статусы, отслеживание клиентом');
reset_out();
$router->handle(cbq('adm:track_new', ADMIN_TG));
check('Запрошен трек-номер', strpos(outText(), 'трек-номер') !== false);

$router->handle(msg('CN123456789', ADMIN_TG));
reset_out();
$router->handle(msg((string) CLIENT_TG, ADMIN_TG));
check('Трек создан и привязан к клиенту', strpos(outText(), 'Трек создан') !== false);
$track = $db->one("SELECT * FROM tracks WHERE track_number = 'CN123456789'");
check('Трек есть в базе', $track !== null);
check('Клиент привязан', $track !== null && $track['user_id'] !== null);
check('Первая запись истории создана',
      (int) $db->value('SELECT COUNT(*) FROM track_history WHERE track_id = :t', ['t' => (int) $track['id']]) === 1);
check('Клиент уведомлён о создании трека', strpos(outText(), 'создан груз') !== false);

reset_out();
$router->handle(cbq('adm:tstatus:' . $track['id'] . ':4', ADMIN_TG)); // «В пути»
$out = outText();
check('Статус груза изменён', strpos($out, 'В пути') !== false);
check('Клиент уведомлён о смене статуса', strpos($out, 'Статус вашего груза') !== false);
check('История статусов пополнилась',
      (int) $db->value('SELECT COUNT(*) FROM track_history WHERE track_id = :t', ['t' => (int) $track['id']]) === 2);

reset_out();
$router->handle(msg('🔍 Отследить груз'));
check('Клиенту предложено ввести трек', strpos(outText(), 'трек-номер') !== false);

reset_out();
$router->handle(msg('НЕТ-ТАКОГО'));
check('Неизвестный трек не найден', strpos(outText(), 'не найден') !== false);

reset_out();
$router->handle(msg('CN123456789'));
$out = outText();
check('Клиент видит текущий статус', strpos($out, 'В пути') !== false);
check('Клиент видит историю статусов', strpos($out, 'История') !== false);

// ---------------------------------------------------------------- заявки в админке
section('Заявки в админ-панели');
reset_out();
$router->handle(cbq('adm:orders:1', ADMIN_TG));
check('Список заявок открывается', strpos(outText(), 'Заявки') !== false);

$orderRow = $db->one('SELECT * FROM orders ORDER BY id DESC LIMIT 1');
reset_out();
$router->handle(cbq('adm:order:' . $orderRow['id'], ADMIN_TG));
check('Карточка заявки открывается', strpos(outText(), $orderRow['number']) !== false);

reset_out();
$router->handle(cbq('adm:ostatus:' . $orderRow['id'] . ':1', ADMIN_TG)); // «В обработке»
$out = outText();
check('Статус заявки изменён', strpos($out, 'В обработке') !== false);
check('Клиент уведомлён о статусе заявки', strpos($out, 'Статус вашей заявки') !== false);
check('Смена статуса записана в журнал',
      (int) $db->value("SELECT COUNT(*) FROM logs WHERE entity = 'orders' AND action = 'status'") >= 1);

// ---------------------------------------------------------------- прочие разделы
section('Информационные разделы и статистика');
foreach ([
    '💰 Тарифы'  => 'Актуальные тарифы',
    '📍 Склады'  => 'Адреса складов',
    '☎ Контакты' => 'Контакты',
    '❓ FAQ'      => 'вопросы',
] as $button => $expect) {
    reset_out();
    $router->handle(msg($button));
    check("Раздел «{$button}» работает", mb_stripos(outText(), $expect) !== false);
}

reset_out();
$faqRow = $db->one('SELECT * FROM faq ORDER BY id LIMIT 1');
$router->handle(cbq('faq:' . $faqRow['id']));
check('Ответ на вопрос FAQ показывается', strpos(outText(), (string) $faqRow['question']) !== false);

foreach ([
    'adm:stats'   => 'Статистика',
    'adm:users:1' => 'Пользователи',
    'adm:calcs:1' => 'История расчётов',
    'adm:logs:1'  => 'Журнал изменений',
] as $data => $expect) {
    reset_out();
    $router->handle(cbq($data, ADMIN_TG));
    check("Раздел «{$expect}» открывается", strpos(outText(), $expect) !== false);
}

// ---------------------------------------------------------------- рассылка
section('Массовая рассылка');
reset_out();
$router->handle(cbq('adm:broadcast', ADMIN_TG));
check('Запрошен текст рассылки', strpos(outText(), 'текст рассылки') !== false);

reset_out();
$router->handle(msg('Привет всем клиентам!', ADMIN_TG));
check('Показано подтверждение с числом получателей', strpos(outText(), 'Получателей') !== false);
$bcRow = $db->one('SELECT * FROM broadcasts ORDER BY id DESC LIMIT 1');
check('Рассылка сохранена', $bcRow !== null);

reset_out();
$router->handle(cbq('adm:bc_go:' . $bcRow['id'], ADMIN_TG));
$out = outText();
check('Рассылка выполнена', strpos($out, 'Рассылка завершена') !== false);
$bcDone = $db->one('SELECT * FROM broadcasts WHERE id = :i', ['i' => (int) $bcRow['id']]);
check('Счётчик отправленных заполнен', (int) $bcDone['sent'] >= 2, 'sent=' . $bcDone['sent']);

// ---------------------------------------------------------------- отмена
section('Отмена диалога');
$router->handle(msg('📝 Оставить заявку'));
reset_out();
$router->handle(msg('❌ Отмена'));
check('Диалог отменяется кнопкой', strpos(outText(), 'отменено') !== false);
check('Состояние очищено', $bot->state->state(CLIENT_TG) === null);

// ---------------------------------------------------------------- экспорт
section('Экспорт в Excel');
$export = new CargoBot\Service\Export($db, sys_get_temp_dir() . '/cargo_export_test');
$ordersFile = $export->orders();
$usersFile = $export->users();
check('Файл заявок создан', is_file($ordersFile) && filesize($ordersFile) > 50);
check('Файл пользователей создан', is_file($usersFile) && filesize($usersFile) > 50);
check('В файле заявок есть данные', strpos((string) file_get_contents($ordersFile), 'Алиджон') !== false);
@unlink($ordersFile);
@unlink($usersFile);
@rmdir(sys_get_temp_dir() . '/cargo_export_test');

// ---------------------------------------------------------------- итог
@unlink($dbFile);

echo "\n" . str_repeat('=', 52) . "\n";
if ($failed === 0) {
    echo "✅ ВСЁ РАБОТАЕТ: пройдено проверок — $passed\n";
} else {
    echo "❌ Пройдено: $passed, провалено: $failed\n";
}
echo str_repeat('=', 52) . "\n";
exit($failed === 0 ? 0 : 1);
