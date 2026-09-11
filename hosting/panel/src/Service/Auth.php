<?php
declare(strict_types=1);

namespace Hosting\Service;

use Hosting\Config;
use Hosting\Model\LoginAttemptRepository;
use Hosting\Model\SessionRepository;
use Hosting\Model\UserRepository;

/**
 * Сессии + CSRF в одном месте. Cookie: HttpOnly, Secure (в проде), SameSite=Lax —
 * Lax, а не Strict, потому что Telegram открывает панель в своём WebView и переход
 * должен донести cookie при первой навигации.
 */
final class Auth
{
    private const COOKIE_NAME = 'hosting_session';
    private const CSRF_SESSION_KEY = '_csrf';

    private ?array $currentUser = null;
    private bool $resolved = false;
    private ?string $sessionToken = null;

    public function __construct(
        private Config $config,
        private SessionRepository $sessions,
        private UserRepository $users,
        private LoginAttemptRepository $attempts,
        private bool $secureCookies = true,
    ) {
    }

    public function login(array $user, string $ip, string $userAgent): void
    {
        $session = $this->sessions->create((int) $user['id'], $ip, $userAgent);
        $this->setCookie($session['token'], $session['expires_at']);
        $this->currentUser = $user;
        $this->resolved = true;
        $this->sessionToken = $session['token'];
    }

    public function logout(): void
    {
        $token = $_COOKIE[self::COOKIE_NAME] ?? null;
        if (is_string($token) && $token !== '') {
            $this->sessions->destroy($token);
        }
        $this->clearCookie();
        $this->currentUser = null;
        $this->resolved = true;
    }

    public function user(): ?array
    {
        if ($this->resolved) {
            return $this->currentUser;
        }
        $this->resolved = true;

        $token = $_COOKIE[self::COOKIE_NAME] ?? null;
        if (!is_string($token) || $token === '') {
            return null;
        }

        $session = $this->sessions->findByToken($token);
        if ($session === null) {
            return null;
        }

        $user = $this->users->findById((int) $session['user_id']);
        if ($user === null || !UserRepository::isActive($user)) {
            return null;
        }

        $this->sessionToken = $token;
        $this->currentUser = $user;
        return $user;
    }

    public function isAdmin(): bool
    {
        $user = $this->user();
        return $user !== null && $user['role'] === 'admin';
    }

    /** Rate limit на логин поверх Fail2ban — быстрее реагирует и работает даже без него. */
    public function isLoginRateLimited(string $identifier, string $ip): bool
    {
        return $this->attempts->recentFailures($identifier, $ip, 600) >= 5;
    }

    public function recordLoginAttempt(string $identifier, string $ip, bool $success): void
    {
        $this->attempts->record($identifier, $ip, $success);
    }

    private function setCookie(string $token, string $expiresAt): void
    {
        setcookie(self::COOKIE_NAME, $token, [
            'expires'  => strtotime($expiresAt),
            'path'     => '/',
            'secure'   => $this->secureCookies,
            'httponly' => true,
            'samesite' => 'Lax',
        ]);
    }

    private function clearCookie(): void
    {
        setcookie(self::COOKIE_NAME, '', [
            'expires'  => time() - 3600,
            'path'     => '/',
            'secure'   => $this->secureCookies,
            'httponly' => true,
            'samesite' => 'Lax',
        ]);
    }

    // ── CSRF ─────────────────────────────────────────────────────────────────

    /**
     * Гарантирует запущенную PHP-сессию.
     *
     * Сессия раньше стартовала только внутри csrfToken()/verifyCsrf(), то есть
     * как побочный эффект работы с CSRF. Любой код, читавший $_SESSION до этого
     * момента, получал пустой массив — например, одноразовый пароль от базы
     * записывался при создании и бесследно пропадал на следующей странице.
     */
    public function ensureSession(): void
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            session_start();
        }
    }

    public function csrfToken(): string
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            session_start();
        }
        if (empty($_SESSION[self::CSRF_SESSION_KEY])) {
            $_SESSION[self::CSRF_SESSION_KEY] = bin2hex(random_bytes(32));
        }
        return (string) $_SESSION[self::CSRF_SESSION_KEY];
    }

    public function verifyCsrf(string $token): bool
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            session_start();
        }
        $expected = $_SESSION[self::CSRF_SESSION_KEY] ?? null;
        return is_string($expected) && $expected !== '' && hash_equals($expected, $token);
    }
}
