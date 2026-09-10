<?php

declare(strict_types=1);

use Hosting\Service\TelegramAuth;

/** Строит корректно подписанную initData тем же алгоритмом, что описан в документации Telegram. */
function hosting_test_build_init_data(string $botToken, array $fields, ?int $authDate = null): string
{
    $fields['auth_date'] = (string) ($authDate ?? time());

    $pairs = $fields;
    ksort($pairs);
    $lines = [];
    foreach ($pairs as $key => $value) {
        $lines[] = $key . '=' . $value;
    }
    $dataCheckString = implode("\n", $lines);

    $secretKey = hash_hmac('sha256', $botToken, 'WebAppData', true);
    $hash = hash_hmac('sha256', $dataCheckString, $secretKey);

    $fields['hash'] = $hash;

    $parts = [];
    foreach ($fields as $key => $value) {
        // urlencode (не rawurlencode) — так Telegram реально кодирует initData,
        // и так же TelegramAuth::parseInitData() декодирует через urldecode().
        $parts[] = $key . '=' . urlencode($value);
    }
    return implode('&', $parts);
}

function test_telegram_valid_signature_accepted(): void
{
    $token = 'test-bot-token-12345';
    $auth = new TelegramAuth($token);
    $user = json_encode(['id' => 42, 'first_name' => 'Алиджон', 'username' => 'alijon']);

    $initData = hosting_test_build_init_data($token, ['user' => $user]);
    $result = $auth->verify($initData);

    assert_equals(42, $result['user']['id']);
}

function test_telegram_tampered_field_rejected(): void
{
    $token = 'test-bot-token-12345';
    $auth = new TelegramAuth($token);
    $user = json_encode(['id' => 42, 'first_name' => 'Алиджон']);

    $initData = hosting_test_build_init_data($token, ['user' => $user]);
    // Меняем id пользователя ПОСЛЕ подписи — подпись должна перестать сходиться.
    $tampered = str_replace('%22id%22%3A42', '%22id%22%3A999999', $initData);

    assert_throws(static function () use ($auth, $tampered): void {
        $auth->verify($tampered);
    }, 'Подделанные данные не должны проходить проверку подписи');
}

function test_telegram_wrong_bot_token_rejected(): void
{
    $auth = new TelegramAuth('correct-token');
    $user = json_encode(['id' => 1]);
    // Подписано ДРУГИМ токеном — как будто initData подсунули от чужого бота.
    $initData = hosting_test_build_init_data('wrong-token', ['user' => $user]);

    assert_throws(static function () use ($auth, $initData): void {
        $auth->verify($initData);
    }, 'initData, подписанная чужим токеном, должна быть отклонена');
}

function test_telegram_expired_init_data_rejected(): void
{
    $token = 'test-bot-token-12345';
    $auth = new TelegramAuth($token);
    $user = json_encode(['id' => 1]);

    $oldTimestamp = time() - TelegramAuth::MAX_AGE_SECONDS - 3600; // на час старше лимита
    $initData = hosting_test_build_init_data($token, ['user' => $user], $oldTimestamp);

    assert_throws(static function () use ($auth, $initData): void {
        $auth->verify($initData);
    }, 'Просроченная initData (больше MAX_AGE_SECONDS) должна быть отклонена');
}

function test_telegram_fresh_init_data_accepted(): void
{
    $token = 'test-bot-token-12345';
    $auth = new TelegramAuth($token);
    $user = json_encode(['id' => 1]);

    $recentTimestamp = time() - 60; // минуту назад — валидно
    $initData = hosting_test_build_init_data($token, ['user' => $user], $recentTimestamp);

    $result = $auth->verify($initData);
    assert_equals(1, $result['user']['id']);
}

function test_telegram_missing_hash_rejected(): void
{
    $auth = new TelegramAuth('any-token');
    assert_throws(static function () use ($auth): void {
        $auth->verify('user=%7B%22id%22%3A1%7D&auth_date=' . time());
    }, 'initData без hash вообще не должна проходить');
}

function test_telegram_not_configured_without_token(): void
{
    $auth = new TelegramAuth('');
    assert_false($auth->isConfigured());
    assert_throws(static function () use ($auth): void {
        $auth->verify('hash=x&auth_date=' . time());
    }, 'Без настроенного токена бота вход через Telegram должен быть недоступен');
}

// ── Login Widget: вход через кнопку на обычном сайте ────────────────────────
// Здесь другой алгоритм подписи, чем в Mini App: secret_key = SHA256(токен),
// а не HMAC(токен, "WebAppData"). Перепутать легко, поэтому проверяем отдельно.

function hosting_test_build_widget_params(string $botToken, array $fields, ?int $authDate = null): array
{
    $fields['auth_date'] = (string) ($authDate ?? time());

    $checked = $fields;
    ksort($checked);
    $lines = [];
    foreach ($checked as $key => $value) {
        $lines[] = $key . '=' . $value;
    }

    $secretKey = hash('sha256', $botToken, true);
    $fields['hash'] = hash_hmac('sha256', implode("\n", $lines), $secretKey);

    return $fields;
}

function test_telegram_widget_valid_signature_accepted(): void
{
    $token = 'test-bot-token-12345';
    $auth = new TelegramAuth($token);
    $params = hosting_test_build_widget_params($token, [
        'id' => '777', 'first_name' => 'Алиджон', 'username' => 'alijon',
    ]);

    $user = $auth->verifyLoginWidget($params);
    assert_equals(777, $user['id']);
    assert_equals('alijon', $user['username']);
}

function test_telegram_widget_tampered_id_rejected(): void
{
    $token = 'test-bot-token-12345';
    $auth = new TelegramAuth($token);
    $params = hosting_test_build_widget_params($token, ['id' => '777', 'first_name' => 'Алиджон']);
    // Подменяем id уже после подписи — так выглядела бы попытка войти за другого.
    $params['id'] = '999';

    assert_throws(static function () use ($auth, $params): void {
        $auth->verifyLoginWidget($params);
    }, 'Подменённый id должен ломать подпись');
}

function test_telegram_widget_mini_app_signature_not_accepted(): void
{
    // Подпись, сделанная по алгоритму Mini App, не должна проходить как виджет:
    // иначе перепутанные ключи молча "работали" бы вполсилы.
    $token = 'test-bot-token-12345';
    $auth = new TelegramAuth($token);

    $fields = ['id' => '777', 'auth_date' => (string) time()];
    ksort($fields);
    $lines = [];
    foreach ($fields as $k => $v) {
        $lines[] = $k . '=' . $v;
    }
    $miniAppSecret = hash_hmac('sha256', $token, 'WebAppData', true);
    $fields['hash'] = hash_hmac('sha256', implode("\n", $lines), $miniAppSecret);

    assert_throws(static function () use ($auth, $fields): void {
        $auth->verifyLoginWidget($fields);
    }, 'Подпись по алгоритму Mini App не должна приниматься виджетом');
}

function test_telegram_widget_expired_rejected(): void
{
    $token = 'test-bot-token-12345';
    $auth = new TelegramAuth($token);
    $old = time() - TelegramAuth::MAX_AGE_SECONDS - 600;
    $params = hosting_test_build_widget_params($token, ['id' => '777'], $old);

    assert_throws(static function () use ($auth, $params): void {
        $auth->verifyLoginWidget($params);
    }, 'Просроченные данные виджета должны отклоняться');
}
