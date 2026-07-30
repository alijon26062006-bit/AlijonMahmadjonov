<?php
declare(strict_types=1);

namespace Core;

/**
 * Base controller. Provides request helpers and (optional) Telegram auth.
 */
abstract class Controller
{
    protected array $config;
    protected ?array $authUser = null;   // parsed Telegram user (from initData)
    protected ?int $userId = null;       // internal users.id

    public function __construct(array $config)
    {
        $this->config = $config;
    }

    /** Read a query-string parameter. */
    protected function query(string $key, $default = null)
    {
        return $_GET[$key] ?? $default;
    }

    /** Read and decode the JSON request body (cached). */
    protected function body(): array
    {
        static $cache = null;
        if ($cache === null) {
            $raw   = file_get_contents('php://input') ?: '';
            $cache = json_decode($raw, true) ?: [];
        }
        return $cache;
    }

    protected function input(string $key, $default = null)
    {
        $body = $this->body();
        return $body[$key] ?? $_POST[$key] ?? $default;
    }

    /**
     * Authenticate the caller from Telegram initData. initData may arrive in
     * the `X-Telegram-Init-Data` header, a query param, or the JSON body.
     * On success, ensures a users row exists and sets $this->userId.
     */
    protected function authenticate(bool $required = true): ?array
    {
        $initData = $this->headerInitData()
            ?? ($this->query('initData')
            ?? $this->input('initData', ''));

        $user = TelegramAuth::validate(
            (string) $initData,
            $this->config['telegram']['bot_token'],
            (int) $this->config['app']['auth_ttl']
        );

        if ($user === null) {
            if ($required) {
                Response::error('Unauthorized: invalid Telegram signature', 401);
            }
            return null;
        }

        $this->authUser = $user;
        $this->userId   = (new \Models\User())->upsertFromTelegram($user);
        return $user;
    }

    private function headerInitData(): ?string
    {
        $headers = [
            $_SERVER['HTTP_X_TELEGRAM_INIT_DATA'] ?? null,
            $_SERVER['HTTP_AUTHORIZATION'] ?? null,
        ];
        foreach ($headers as $h) {
            if ($h) {
                return preg_replace('/^tma\s+/i', '', $h);
            }
        }
        return null;
    }

    protected function isAdmin(): bool
    {
        if (!$this->authUser) {
            return false;
        }
        $tid = (int) ($this->authUser['id'] ?? 0);
        return in_array($tid, $this->config['telegram']['admin_ids'], true);
    }
}
