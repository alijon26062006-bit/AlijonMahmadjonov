<?php
declare(strict_types=1);

function admin_is_logged_in(): bool
{
    return !empty($_SESSION['is_admin']);
}

function admin_login_locked(): bool
{
    $until = $_SESSION['admin_lock_until'] ?? 0;
    return $until > time();
}

function admin_login(array $config, string $password): bool
{
    if (admin_login_locked()) {
        return false;
    }

    $expected = (string) ($config['admin_password'] ?? '');
    if ($expected !== '' && hash_equals($expected, $password)) {
        $_SESSION['is_admin'] = true;
        $_SESSION['admin_attempts'] = 0;
        session_regenerate_id(true);
        return true;
    }

    $_SESSION['admin_attempts'] = ($_SESSION['admin_attempts'] ?? 0) + 1;
    if ($_SESSION['admin_attempts'] >= 5) {
        $_SESSION['admin_lock_until'] = time() + 60;
        $_SESSION['admin_attempts'] = 0;
    }
    return false;
}

function admin_logout(): void
{
    unset($_SESSION['is_admin']);
    session_regenerate_id(true);
}

function admin_require(string $loginPath = 'index.php'): void
{
    if (!admin_is_logged_in()) {
        redirect($loginPath);
    }
}
