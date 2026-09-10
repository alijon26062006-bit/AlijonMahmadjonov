<?php
declare(strict_types=1);

namespace Hosting\Service;

/**
 * Вызовы Telegram Bot API для webhook сайта клиента.
 *
 * Всё делается с сервера, никогда из браузера: токен бота не должен попадать
 * ни в JavaScript, ни в адресную строку, ни в логи браузера. Здесь же он не
 * попадает и в наши логи — see scrub().
 */
final class TelegramWebhook
{
    public function __construct(private int $timeoutSeconds = 20)
    {
    }

    /** Секрет для заголовка X-Telegram-Bot-Api-Secret-Token. */
    public static function generateSecret(): string
    {
        // Telegram допускает 1–256 символов A-Z a-z 0-9 _ -
        return rtrim(strtr(base64_encode(random_bytes(24)), '+/', '-_'), '=');
    }

    /** @return array{ok:bool,error:string|null} */
    public function setWebhook(string $token, string $url, string $secret): array
    {
        $response = $this->call($token, 'setWebhook', [
            'url'             => $url,
            'secret_token'    => $secret,
            'max_connections' => 40,
            // Старые накопившиеся апдейты чужого владельца бота нам не нужны.
            'drop_pending_updates' => 'true',
        ]);

        return ['ok' => (bool) ($response['ok'] ?? false), 'error' => $this->errorOf($response)];
    }

    /** @return array{ok:bool,error:string|null,info:array<string,mixed>} */
    public function getInfo(string $token): array
    {
        $response = $this->call($token, 'getWebhookInfo');
        $info = is_array($response['result'] ?? null) ? $response['result'] : [];

        return [
            'ok'    => (bool) ($response['ok'] ?? false),
            'error' => $this->errorOf($response),
            'info'  => $info,
        ];
    }

    /** @return array{ok:bool,error:string|null} */
    public function deleteWebhook(string $token): array
    {
        $response = $this->call($token, 'deleteWebhook', ['drop_pending_updates' => 'true']);

        return ['ok' => (bool) ($response['ok'] ?? false), 'error' => $this->errorOf($response)];
    }

    /** Проверяет токен и возвращает имя бота. @return array{ok:bool,username:string,error:string|null} */
    public function getMe(string $token): array
    {
        $response = $this->call($token, 'getMe');

        return [
            'ok'       => (bool) ($response['ok'] ?? false),
            'username' => (string) ($response['result']['username'] ?? ''),
            'error'    => $this->errorOf($response),
        ];
    }

    /**
     * Человеческое объяснение вместо сообщения Telegram.
     *
     * «Wrong response from the webhook: 500 Internal Server Error» ничего не
     * говорит владельцу сайта — а вот «в webhook.php ошибка, смотрите логи» говорит.
     */
    public static function explain(array $info): ?string
    {
        $error = (string) ($info['last_error_message'] ?? '');
        if ($error === '') {
            return null;
        }

        return match (true) {
            str_contains($error, 'SSL')             => 'Telegram не принимает сертификат сайта. Дождитесь выпуска SSL или проверьте его в «Домены».',
            str_contains($error, 'Connection refused'),
            str_contains($error, 'Failed to resolve'),
            str_contains($error, 'Timeout')          => 'Telegram не может достучаться до сайта. Проверьте, что адрес открывается в браузере.',
            str_contains($error, '404')              => 'Файл webhook.php не найден. Создайте его кнопкой «Создать webhook.php».',
            str_contains($error, '403')              => 'webhook.php отвечает 403 — секрет не совпадает. Нажмите «Подключить webhook» ещё раз.',
            str_contains($error, '500')              => 'Ошибка PHP в webhook.php. Откройте «Логи» — там текст ошибки.',
            default                                  => 'Telegram сообщает об ошибке: ' . self::scrub($error),
        };
    }

    /** Вырезает возможный токен из текста, прежде чем показать его или записать в лог. */
    public static function scrub(string $text): string
    {
        return (string) preg_replace('~\b\d{6,}:[A-Za-z0-9_-]{20,}\b~', '<токен скрыт>', $text);
    }

    /** @return array<string,mixed> */
    private function call(string $token, string $method, array $params = []): array
    {
        $ch = curl_init('https://api.telegram.org/bot' . $token . '/' . $method);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => http_build_query($params),
            CURLOPT_TIMEOUT        => $this->timeoutSeconds,
            CURLOPT_CONNECTTIMEOUT => 5,
        ]);
        $body = curl_exec($ch);
        $netError = curl_errno($ch) !== 0 ? curl_error($ch) : null;
        curl_close($ch);

        if (!is_string($body)) {
            return ['ok' => false, 'description' => $netError ?? 'нет ответа от Telegram'];
        }

        $decoded = json_decode($body, true);

        return is_array($decoded) ? $decoded : ['ok' => false, 'description' => 'непонятный ответ Telegram'];
    }

    private function errorOf(array $response): ?string
    {
        if (($response['ok'] ?? false) === true) {
            return null;
        }

        return self::scrub((string) ($response['description'] ?? 'неизвестная ошибка'));
    }
}
