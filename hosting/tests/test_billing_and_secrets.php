<?php

declare(strict_types=1);

use Hosting\Config;
use Hosting\Model\DatabaseUserRepository;
use Hosting\Service\Billing;
use Hosting\Support\Brand;
use Hosting\Support\Secret;

// ── Обратимое шифрование паролей от баз ────────────────────────────────────
// Пароль от MySQL панель обязана показать клиенту ещё раз (он его теряет), поэтому
// хеш не подходит — нужен шифр. Ключ живёт в .env, а не в базе: дамп базы без
// файла настроек не должен раскрывать ни одного пароля.

function hosting_test_key(): string
{
    return base64_encode(str_repeat("\x11", 32));
}

function test_secret_roundtrip_returns_original(): void
{
    $enc = Secret::encrypt('Xk7#pQ2mZr9Lw', hosting_test_key());
    assert_equals('Xk7#pQ2mZr9Lw', Secret::decrypt($enc, hosting_test_key()));
}

function test_secret_ciphertext_differs_every_time(): void
{
    $key = hosting_test_key();
    // Один и тот же пароль двух клиентов не должен давать одинаковую строку в базе,
    // иначе по совпадению видно, что пароли равны.
    assert_true(Secret::encrypt('same-password', $key) !== Secret::encrypt('same-password', $key));
}

function test_secret_wrong_key_returns_null_not_garbage(): void
{
    $enc = Secret::encrypt('Xk7#pQ2mZr9Lw', hosting_test_key());
    assert_true(Secret::decrypt($enc, base64_encode(str_repeat("\x22", 32))) === null);
}

function test_secret_tampered_ciphertext_rejected(): void
{
    // GCM проверяет целостность: изменённую строку нельзя расшифровать «частично».
    $enc = Secret::encrypt('Xk7#pQ2mZr9Lw', hosting_test_key());
    $raw = base64_decode($enc, true);
    assert_true(is_string($raw));
    $raw[strlen($raw) - 1] = $raw[strlen($raw) - 1] === "\x00" ? "\x01" : "\x00";

    assert_true(Secret::decrypt(base64_encode($raw), hosting_test_key()) === null);
}

function test_secret_garbage_input_returns_null(): void
{
    assert_true(Secret::decrypt('не base64 вовсе', hosting_test_key()) === null);
    assert_true(Secret::decrypt('', hosting_test_key()) === null);
}

// ── Срок тарифа ────────────────────────────────────────────────────────────

function test_days_left_counts_calendar_days(): void
{
    $in47 = (new DateTimeImmutable('today'))->modify('+47 days')->format('Y-m-d H:i:s');
    assert_equals(47, Billing::daysLeft($in47));
}

function test_days_left_is_zero_on_the_last_day(): void
{
    assert_equals(0, Billing::daysLeft((new DateTimeImmutable('today'))->format('Y-m-d H:i:s')));
}

function test_days_left_is_negative_after_expiry(): void
{
    $ago = (new DateTimeImmutable('today'))->modify('-3 days')->format('Y-m-d H:i:s');
    assert_equals(-3, Billing::daysLeft($ago));
}

function test_days_left_is_null_without_end_date(): void
{
    assert_true(Billing::daysLeft(null) === null);
    assert_true(Billing::daysLeft('') === null);
    assert_true(Billing::daysLeft('не дата') === null);
}

// ── Деньги ────────────────────────────────────────────────────────────────

function test_money_always_shows_two_decimals(): void
{
    // 47.5 на экране обязано быть «47.50»: копейки, «съеденные» округлением,
    // клиент читает как потерянные деньги.
    assert_equals('47.50 TJS', Billing::money(47.5));
    assert_equals('25.00 TJS', Billing::money(25));
    assert_equals('0.00 TJS', Billing::money(0));
}

// ── Пополнение баланса ────────────────────────────────────────────────────

function test_credit_updates_balance_and_writes_history(): void
{
    $db = hosting_test_db();
    $pdo = $db->pdo();
    $pdo->exec("INSERT INTO users (email, system_user, plan_id, balance_tjs)
                VALUES ('credit@test.tj', 'credituser', 1, 10)");
    $uid = (int) $pdo->lastInsertId();

    (new Billing($db))->credit($uid, 40.5, 'перевод на карту');

    $balance = $pdo->query("SELECT balance_tjs FROM users WHERE id = {$uid}")->fetchColumn();
    assert_equals('50.50', number_format((float) $balance, 2, '.', ''));

    $row = $pdo->query("SELECT * FROM payments WHERE user_id = {$uid}")->fetch();
    assert_equals('paid', $row['status']);
    assert_equals('перевод на карту', $row['external_id']);
}

function test_credit_rejects_zero_and_negative_amounts(): void
{
    $db = hosting_test_db();
    $billing = new Billing($db);
    assert_throws(static fn () => $billing->credit(1, 0));
    assert_throws(static fn () => $billing->credit(1, -100));
}

function test_approving_a_request_credits_balance_exactly_once(): void
{
    $db = hosting_test_db();
    $pdo = $db->pdo();
    $pdo->exec("INSERT INTO users (email, system_user, plan_id, balance_tjs)
                VALUES ('approve@test.tj', 'approveuser', 1, 5)");
    $uid = (int) $pdo->lastInsertId();
    $pdo->exec("INSERT INTO payments (user_id, provider, amount_tjs, status)
                VALUES ({$uid}, 'manual', 100, 'pending')");
    $paymentId = (int) $pdo->lastInsertId();

    $billing = new Billing($db);
    assert_true($billing->approvePayment($paymentId));

    // Повторное нажатие «Зачислить» не должно добавить сто сомони второй раз.
    assert_false($billing->approvePayment($paymentId));

    $balance = $pdo->query("SELECT balance_tjs FROM users WHERE id = {$uid}")->fetchColumn();
    assert_equals('105.00', number_format((float) $balance, 2, '.', ''));
}

function test_rejecting_a_request_leaves_balance_untouched(): void
{
    $db = hosting_test_db();
    $pdo = $db->pdo();
    $pdo->exec("INSERT INTO users (email, system_user, plan_id, balance_tjs)
                VALUES ('reject@test.tj', 'rejectuser', 1, 5)");
    $uid = (int) $pdo->lastInsertId();
    $pdo->exec("INSERT INTO payments (user_id, provider, amount_tjs, status)
                VALUES ({$uid}, 'manual', 100, 'pending')");
    $paymentId = (int) $pdo->lastInsertId();

    $billing = new Billing($db);
    assert_true($billing->rejectPayment($paymentId));
    assert_false($billing->approvePayment($paymentId), 'Отклонённую заявку нельзя зачислить');

    $balance = $pdo->query("SELECT balance_tjs FROM users WHERE id = {$uid}")->fetchColumn();
    assert_equals('5.00', number_format((float) $balance, 2, '.', ''));
}

function test_pending_requests_list_only_unprocessed_ones(): void
{
    $db = hosting_test_db();
    $pdo = $db->pdo();
    $pdo->exec("INSERT INTO users (email, system_user, plan_id) VALUES ('list@test.tj', 'listuser', 1)");
    $uid = (int) $pdo->lastInsertId();
    $pdo->exec("INSERT INTO payments (user_id, provider, amount_tjs, status) VALUES ({$uid}, 'manual', 10, 'pending')");
    $pdo->exec("INSERT INTO payments (user_id, provider, amount_tjs, status) VALUES ({$uid}, 'manual', 20, 'paid')");
    $pdo->exec("INSERT INTO payments (user_id, provider, amount_tjs, status) VALUES ({$uid}, 'manual', 30, 'failed')");

    $pending = (new Billing($db))->pendingPayments();
    assert_equals(1, count($pending));
    assert_equals('10.00', number_format((float) $pending[0]['amount_tjs'], 2, '.', ''));
    assert_equals('list@test.tj', $pending[0]['email']);
}

// ── Пароль от базы: хранение и повторный показ ────────────────────────────

function hosting_test_db_user(Hosting\Database $db, string $login): int
{
    $pdo = $db->pdo();
    $pdo->exec("INSERT INTO users (email, system_user, plan_id) VALUES ('{$login}@test.tj', '{$login}', 1)");
    $uid = (int) $pdo->lastInsertId();
    (new DatabaseUserRepository($db))->getOrCreateForUser(
        ['id' => $uid, 'system_user' => $login],
        5
    );

    return $uid;
}

function test_database_password_is_shown_again_to_the_client(): void
{
    // Клиент теряет пароль от базы, а менять его — значит ломать уже настроенные
    // сайты. Поэтому пароль обязан читаться обратно, а не только проверяться.
    $db = hosting_test_db();
    $repo = new DatabaseUserRepository($db);
    $uid = hosting_test_db_user($db, 'showpw');

    $repo->storePassword($uid, 'Xk7#pQ2mZr9Lw', hosting_test_key());
    assert_equals('Xk7#pQ2mZr9Lw', $repo->revealPassword($uid, hosting_test_key()));
}

function test_database_password_is_never_stored_in_plain_text(): void
{
    $db = hosting_test_db();
    $repo = new DatabaseUserRepository($db);
    $uid = hosting_test_db_user($db, 'plainpw');

    $repo->storePassword($uid, 'Xk7#pQ2mZr9Lw', hosting_test_key());

    $stored = (string) $db->pdo()
        ->query("SELECT password_enc FROM database_users WHERE user_id = {$uid}")
        ->fetchColumn();

    assert_true($stored !== '', 'Пароль должен быть сохранён');
    assert_false(str_contains($stored, 'Xk7#pQ2mZr9Lw'), 'В базе не должно быть пароля открытым текстом');
}

function test_new_password_replaces_the_old_one(): void
{
    // После «Нового пароля» панель обязана показывать новый: если она покажет
    // старый, клиент будет вводить его в phpMyAdmin и получать отказ.
    $db = hosting_test_db();
    $repo = new DatabaseUserRepository($db);
    $uid = hosting_test_db_user($db, 'newpw');

    $repo->storePassword($uid, 'старый-пароль', hosting_test_key());
    $repo->storePassword($uid, 'новый-пароль', hosting_test_key());

    assert_equals('новый-пароль', $repo->revealPassword($uid, hosting_test_key()));
}

function test_password_is_not_stored_at_all_without_app_key(): void
{
    // Лучше не показать пароль, чем положить его в базу открытым текстом.
    $db = hosting_test_db();
    $repo = new DatabaseUserRepository($db);
    $uid = hosting_test_db_user($db, 'nokeypw');

    $repo->storePassword($uid, 'Xk7#pQ2mZr9Lw', '');

    $stored = $db->pdo()
        ->query("SELECT password_enc FROM database_users WHERE user_id = {$uid}")
        ->fetchColumn();

    assert_true($stored === null || $stored === '', 'Без APP_KEY в базе не должно появиться ничего');
    assert_true($repo->revealPassword($uid, hosting_test_key()) === null);
}

// ── Имя панели берётся из купленного домена ───────────────────────────────

function test_panel_name_defaults_to_brand_from_domain(): void
{
    $config = Config::fromEnv(['HOSTING_ROOT_DOMAIN' => 'diyorhost.com']);
    assert_equals('DiyorHost', $config->str('panel_name'));
}

function test_panel_name_env_wins_over_domain(): void
{
    $config = Config::fromEnv([
        'HOSTING_ROOT_DOMAIN' => 'diyorhost.com',
        'PANEL_NAME'          => 'Мой Хостинг',
    ]);
    assert_equals('Мой Хостинг', $config->str('panel_name'));
}

function test_brand_from_domain_handles_plain_names(): void
{
    assert_equals('DiyorHost', Brand::fromDomain('diyorhost.com'));
    assert_equals('Uways', Brand::fromDomain('uways.tj'));
    assert_equals('', Brand::fromDomain(''));
}
