<?php
declare(strict_types=1);

namespace Hosting\Service;

/**
 * Проверка initData из Telegram Mini App.
 *
 * Telegram подписывает данные ключом, производным от токена бота. Пока подпись
 * сходится, полям можно верить — это и заменяет пароль. Проверяем строго:
 * ни одно поле нельзя добавить, убрать или подменить, не сломав подпись.
 *
 * @see https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
 */
final class TelegramAuth
{
    /** Сколько живёт подпись: старую initData принимать нельзя (защита от повтора). */
    public const MAX_AGE_SECONDS = 86400;

    public function __construct(private string $botToken)
    {
    }

    public function isConfigured(): bool
    {
        return trim($this->botToken) !== '';
    }

    /**
     * Разбирает и проверяет initData.
     *
     * @return array<string,mixed> поля initData, где user уже развёрнут из JSON
     * @throws \RuntimeException если подпись не сходится или данные просрочены
     */
    public function verify(string $initData, ?int $now = null): array
    {
        if (!$this->isConfigured()) {
            throw new \RuntimeException('Вход через Telegram не настроен: нет токена бота');
        }

        $pairs = self::parseInitData($initData);
        $hash = (string) ($pairs['hash'] ?? '');
        if ($hash === '') {
            throw new \RuntimeException('В данных Telegram нет подписи');
        }

        // В строку проверки не входят сама подпись и signature (подпись Ed25519 для третьих лиц).
        $checked = $pairs;
        unset($checked['hash'], $checked['signature']);
        ksort($checked);

        $lines = [];
        foreach ($checked as $key => $value) {
            $lines[] = $key . '=' . $value;
        }
        $dataCheckString = implode("\n", $lines);

        $secretKey = hash_hmac('sha256', $this->botToken, 'WebAppData', true);
        $expected = hash_hmac('sha256', $dataCheckString, $secretKey);

        if (!hash_equals($expected, $hash)) {
            throw new \RuntimeException('Подпись Telegram не сходится');
        }

        $authDate = (int) ($pairs['auth_date'] ?? 0);
        $now = $now ?? time();
        if ($authDate <= 0 || $now - $authDate > self::MAX_AGE_SECONDS) {
            throw new \RuntimeException('Данные Telegram устарели, откройте приложение заново');
        }

        $result = $pairs;
        if (isset($pairs['user'])) {
            $user = json_decode((string) $pairs['user'], true);
            if (!is_array($user) || !isset($user['id'])) {
                throw new \RuntimeException('Telegram не передал данные пользователя');
            }
            $result['user'] = $user;
        }

        return $result;
    }

    /**
     * Проверка данных от Telegram Login Widget — это вход с ОБЫЧНОГО САЙТА
     * (кнопка «Войти через Telegram»), а не из Mini App.
     *
     * Алгоритм похож, но ключ считается иначе: здесь secret_key = SHA256(токен),
     * а в Mini App — HMAC(токен, "WebAppData"). Перепутать их легко, и тогда
     * подпись просто никогда не сойдётся.
     *
     * @param array<string,string> $params поля из query-строки колбэка (id, first_name, hash, …)
     * @return array{id:int,first_name?:string,last_name?:string,username?:string}
     * @throws \RuntimeException если подпись не сходится или данные просрочены
     *
     * @see https://core.telegram.org/widgets/login#checking-authorization
     */
    public function verifyLoginWidget(array $params, ?int $now = null): array
    {
        if (!$this->isConfigured()) {
            throw new \RuntimeException('Вход через Telegram не настроен: нет токена бота');
        }

        $hash = (string) ($params['hash'] ?? '');
        if ($hash === '') {
            throw new \RuntimeException('В данных Telegram нет подписи');
        }

        $checked = $params;
        unset($checked['hash']);
        ksort($checked);

        $lines = [];
        foreach ($checked as $key => $value) {
            $lines[] = $key . '=' . $value;
        }

        $secretKey = hash('sha256', $this->botToken, true);
        $expected = hash_hmac('sha256', implode("\n", $lines), $secretKey);

        if (!hash_equals($expected, $hash)) {
            throw new \RuntimeException('Подпись Telegram не сходится');
        }

        $authDate = (int) ($params['auth_date'] ?? 0);
        $now = $now ?? time();
        if ($authDate <= 0 || $now - $authDate > self::MAX_AGE_SECONDS) {
            throw new \RuntimeException('Данные Telegram устарели, войдите заново');
        }

        $id = (int) ($params['id'] ?? 0);
        if ($id <= 0) {
            throw new \RuntimeException('Telegram не передал идентификатор пользователя');
        }

        return [
            'id'         => $id,
            'first_name' => (string) ($params['first_name'] ?? ''),
            'last_name'  => (string) ($params['last_name'] ?? ''),
            'username'   => (string) ($params['username'] ?? ''),
        ];
    }

    /**
     * Разбор query-строки вручную: parse_str портит ключи с точками и скобками,
     * а для подписи важно сохранить значения ровно такими, как их прислал Telegram.
     *
     * @return array<string,string>
     */
    public static function parseInitData(string $initData): array
    {
        $pairs = [];

        foreach (explode('&', $initData) as $chunk) {
            if ($chunk === '') {
                continue;
            }
            $parts = explode('=', $chunk, 2);
            $key = urldecode($parts[0]);
            if ($key === '') {
                continue;
            }
            $pairs[$key] = urldecode($parts[1] ?? '');
        }

        return $pairs;
    }
}
