<?php

declare(strict_types=1);

use Hosting\Model\JobRepository;
use Hosting\Model\PlanRepository;
use Hosting\Model\SiteRepository;
use Hosting\Model\UserRepository;
use Hosting\Service\Auth;
use Hosting\Service\Quota;
use Hosting\Support\Domain;
use Hosting\Support\DnsVerifier;

// ── Валидация поддоменов и зарезервированные имена ──────────────────────────

function test_subdomain_valid_labels_accepted(): void
{
    foreach (['shop', 'my-shop', 'a12', 'test123'] as $label) {
        assert_true(Domain::isValidLabel($label), "'{$label}' должен быть допустимым поддоменом");
    }
}

function test_subdomain_reserved_words_rejected(): void
{
    foreach (['www', 'panel', 'admin', 'api', 'mysql', 'db', 'localhost', 'root'] as $label) {
        assert_false(Domain::isValidLabel($label), "'{$label}' зарезервирован и должен быть отклонён");
    }
}

function test_subdomain_invalid_characters_rejected(): void
{
    $bad = ['../etc', 'shop.evil', 'sh op', 'shop/', 'sh_op', "shop\0", str_repeat('a', 40), 'ab', '-shop', 'shop-'];
    foreach ($bad as $label) {
        assert_false(Domain::isValidLabel($label), "'{$label}' должен быть отклонён валидацией поддомена");
    }
}

function test_custom_domain_fqdn_validation(): void
{
    assert_true(Domain::isValidFqdn('example.tj'));
    assert_true(Domain::isValidFqdn('shop.example.tj'));
    assert_false(Domain::isValidFqdn('not a domain'));
    assert_false(Domain::isValidFqdn('..'));
    assert_false(Domain::isValidFqdn('nodot'));
}

// ── SSRF-защита: приватные/служебные IP не считаются публичными ────────────

function test_dns_verifier_rejects_private_and_loopback_ips(): void
{
    $private = ['127.0.0.1', '10.0.0.1', '172.16.5.5', '192.168.1.1', '169.254.1.1', '::1', 'fc00::1'];
    foreach ($private as $ip) {
        assert_false(DnsVerifier::isPublicIp($ip), "{$ip} не должен считаться публичным адресом");
    }
}

function test_dns_verifier_accepts_public_ips(): void
{
    foreach (['8.8.8.8', '1.1.1.1', '203.0.113.10'] as $ip) {
        assert_true(DnsVerifier::isPublicIp($ip), "{$ip} должен считаться публичным адресом");
    }
}

function test_dns_verifier_rejects_localhost_pseudo_domains(): void
{
    $result = DnsVerifier::pointsToServer('localhost', '1.2.3.4');
    assert_false($result['ok']);

    $result2 = DnsVerifier::pointsToServer('site.internal', '1.2.3.4');
    assert_false($result2['ok']);
}

// ── CSRF ─────────────────────────────────────────────────────────────────

function test_csrf_token_required_and_validated(): void
{
    // Auth::csrfToken()/verifyCsrf() используют $_SESSION напрямую — в CLI это
    // работает через файловую сессию, как и в php-fpm.
    if (session_status() === PHP_SESSION_ACTIVE) {
        session_write_close();
    }
    $_SESSION = [];

    $db = hosting_test_db();
    $plans = new PlanRepository($db);
    $users = new UserRepository($db, $plans);
    $sessions = new \Hosting\Model\SessionRepository($db);
    $attempts = new \Hosting\Model\LoginAttemptRepository($db);
    $auth = new Auth(hosting_test_config(), $sessions, $users, $attempts, false);

    $token = $auth->csrfToken();
    assert_true(strlen($token) >= 32, 'CSRF-токен должен быть достаточно длинным');
    assert_true($auth->verifyCsrf($token), 'Правильный токен должен приниматься');
    assert_false($auth->verifyCsrf('совершенно-другой-токен'), 'Произвольная строка не должна приниматься как CSRF-токен');
    assert_false($auth->verifyCsrf(''), 'Пустой токен не должен приниматься');
}

// ── SQL injection: параметризованные запросы не ломаются на спецсимволах ───

function test_sql_injection_attempt_in_email_is_safe(): void
{
    $db = hosting_test_db();
    $plans = new PlanRepository($db);
    $users = new UserRepository($db, $plans);

    $users->create('victim@example.com', 'password123', 'start');

    $payloads = [
        "' OR '1'='1",
        "victim@example.com' --",
        "'; DROP TABLE users; --",
        "\" OR \"\"=\"",
    ];

    foreach ($payloads as $payload) {
        // Не должно бросать исключение синтаксиса SQL и не должно найти пользователя —
        // подготовленные выражения (PDO) трактуют это как обычную строку, не как код.
        $found = $users->findByEmail($payload);
        assert_true($found === null, "Инъекция '{$payload}' не должна возвращать существующего пользователя");
    }

    // Таблица должна быть на месте (не удалена инъекцией DROP TABLE).
    assert_equals(1, $users->count());
}

// ── Дубликат сайта / уникальность домена на уровне схемы ───────────────────

function test_duplicate_site_domain_rejected_by_schema(): void
{
    $db = hosting_test_db();
    $plans = new PlanRepository($db);
    $users = new UserRepository($db, $plans);
    $sites = new SiteRepository($db);

    $user = $users->create('dup-site@example.com', 'password123', 'start');
    $sites->create((int) $user['id'], 'shop', 'shop.myhost.tj', '8.3');

    assert_throws(static function () use ($sites, $user): void {
        $sites->create((int) $user['id'], 'shop2', 'shop.myhost.tj', '8.3');
    }, 'Второй сайт с тем же доменом должен быть отклонён уникальным ограничением схемы');
}

// ── Провал задания в очереди фиксируется, а не теряется молча ──────────────

function test_failed_job_is_recorded_with_error(): void
{
    $db = hosting_test_db();
    $plans = new PlanRepository($db);
    $users = new UserRepository($db, $plans);
    $jobs = new JobRepository($db);

    $user = $users->create('jobfail@example.com', 'password123', 'start');
    $job = $jobs->enqueue('create_site', (int) $user['id'], null, []);
    $claimed = $jobs->claimPending(1);

    $jobs->markFailed((int) $claimed[0]['id'], 'nginx -t failed: unexpected token');

    $refreshed = $jobs->findById((int) $job['id']);
    assert_equals('failed', $refreshed['status']);
    assert_true(str_contains((string) $refreshed['error_text'], 'nginx -t failed'));
}

// ── Квота: превышение корректно определяется ────────────────────────────────

function test_quota_exceeded_detection(): void
{
    $home = sys_get_temp_dir() . '/hosting-quota-' . bin2hex(random_bytes(6));
    mkdir($home, 0o750, true);
    file_put_contents($home . '/big.bin', str_repeat('x', 2 * 1024 * 1024)); // 2 МБ

    try {
        $underLimit = Quota::usage($home, 10); // лимит 10 МБ — не превышена
        assert_false($underLimit['exceeded']);

        $overLimit = Quota::usage($home, 1); // лимит 1 МБ — превышена
        assert_true($overLimit['exceeded']);
        assert_true($overLimit['percent'] === 100);
    } finally {
        exec('rm -rf ' . escapeshellarg($home));
    }
}

// ── Cross-account: файловый менеджер одного клиента не видит другого ───────

function test_cross_account_file_manager_isolated(): void
{
    $homeA = sys_get_temp_dir() . '/hosting-fm-a-' . bin2hex(random_bytes(6));
    $homeB = sys_get_temp_dir() . '/hosting-fm-b-' . bin2hex(random_bytes(6));
    mkdir($homeA, 0o750, true);
    mkdir($homeB, 0o750, true);
    file_put_contents($homeB . '/secret.txt', 'чужой секрет');

    try {
        $fmA = new \Hosting\Service\FileManager($homeA);
        // Единственный способ FileManager'а клиента A дотянуться до файла клиента B —
        // через relative-путь, а Path::resolve держит его строго внутри $homeA.
        assert_throws(static function () use ($fmA, $homeB): void {
            $fmA->read('../' . basename($homeB) . '/secret.txt');
        }, 'Клиент A не должен суметь прочитать файл клиента B через relative-путь');
    } finally {
        exec('rm -rf ' . escapeshellarg($homeA) . ' ' . escapeshellarg($homeB));
    }
}

// ── Склонение числительных на витрине ───────────────────────────────────────
// «1 баз данных» и «2 сайтов» на странице тарифов видит каждый посетитель,
// поэтому правило проверяется, а не держится в голове.

function test_russian_plural_forms(): void
{
    $sites = static fn (int $n): string => $n . ' ' . \Hosting\Support\Html::plural($n, 'сайт', 'сайта', 'сайтов');

    assert_equals('1 сайт',    $sites(1));
    assert_equals('2 сайта',   $sites(2));
    assert_equals('4 сайта',   $sites(4));
    assert_equals('5 сайтов',  $sites(5));
    // 11–14 — исключение: несмотря на последнюю цифру, форма «много».
    assert_equals('11 сайтов', $sites(11));
    assert_equals('12 сайтов', $sites(12));
    assert_equals('14 сайтов', $sites(14));
    assert_equals('21 сайт',   $sites(21));
    assert_equals('22 сайта',  $sites(22));
    assert_equals('25 сайтов', $sites(25));
    assert_equals('101 сайт',  $sites(101));
    assert_equals('0 сайтов',  $sites(0));
}
