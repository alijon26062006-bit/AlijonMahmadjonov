<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/google.php';

function google_login_fail(string $message): void
{
    $pageTitle = 'Ошибка входа';
    require __DIR__ . '/../includes/layout_start.php';
    echo '<div class="login-wrap"><h1>Не удалось войти через Google</h1><div class="error">'
        . htmlspecialchars($message) . '</div><p><a href="/index.php">Вернуться ко входу</a></p></div>';
    require __DIR__ . '/../includes/layout_end.php';
    exit;
}

$state = $_GET['state'] ?? '';
if (!$state || $state !== ($_SESSION['google_oauth_state'] ?? null)) {
    google_login_fail('Сессия входа устарела, попробуйте ещё раз.');
}
unset($_SESSION['google_oauth_state']);

$code = $_GET['code'] ?? '';
if (!$code) {
    google_login_fail('Google не передал код авторизации.');
}

function google_curl_post(string $url, array $fields): ?array
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => http_build_query($fields),
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 15,
    ]);
    $response = curl_exec($ch);
    curl_close($ch);
    if ($response === false) {
        return null;
    }
    $data = json_decode($response, true);
    return is_array($data) ? $data : null;
}

function google_curl_get(string $url, string $bearerToken): ?array
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $bearerToken],
        CURLOPT_TIMEOUT => 15,
    ]);
    $response = curl_exec($ch);
    curl_close($ch);
    if ($response === false) {
        return null;
    }
    $data = json_decode($response, true);
    return is_array($data) ? $data : null;
}

$tokenResponse = google_curl_post('https://oauth2.googleapis.com/token', [
    'code' => $code,
    'client_id' => GOOGLE_CLIENT_ID,
    'client_secret' => GOOGLE_CLIENT_SECRET,
    'redirect_uri' => GOOGLE_REDIRECT_URI,
    'grant_type' => 'authorization_code',
]);

if (!$tokenResponse || empty($tokenResponse['access_token'])) {
    google_login_fail('Не удалось получить токен от Google. Проверьте настройки config/google.php.');
}

$userInfo = google_curl_get(
    'https://www.googleapis.com/oauth2/v3/userinfo',
    $tokenResponse['access_token']
);

if (!$userInfo || empty($userInfo['email'])) {
    google_login_fail('Не удалось получить данные аккаунта Google.');
}

$email = $userInfo['email'];
$googleId = $userInfo['sub'] ?? null;

$db = get_db();
$stmt = $db->prepare('SELECT * FROM users WHERE email = ? OR google_id = ?');
$stmt->execute([$email, $googleId]);
$user = $stmt->fetch();

if (!$user) {
    google_login_fail(
        'Аккаунт с email ' . $email . ' не найден в системе. '
        . 'Попросите шефа указать этот email в вашем профиле, либо войдите по логину и паролю.'
    );
}

if (empty($user['google_id']) && $googleId) {
    $stmt = $db->prepare('UPDATE users SET google_id = ? WHERE id = ?');
    $stmt->execute([$googleId, $user['id']]);
}

login_user($user);
header('Location: ' . ($user['role'] === 'boss' ? '/boss/dashboard.php' : '/worker/dashboard.php'));
exit;
