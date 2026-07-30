<?php
declare(strict_types=1);

namespace Core;

/**
 * Validates Telegram WebApp `initData` per the official algorithm:
 *
 *   secret_key = HMAC_SHA256(bot_token, "WebAppData")
 *   check_hash = HMAC_SHA256(data_check_string, secret_key)
 *
 * See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
 */
final class TelegramAuth
{
    /**
     * @return array|null Parsed `user` object on success, null on failure.
     */
    public static function validate(string $initData, string $botToken, int $ttl = 86400): ?array
    {
        if ($initData === '') {
            return null;
        }

        parse_str($initData, $params);
        if (empty($params['hash'])) {
            return null;
        }

        $hash = $params['hash'];
        // Exclude `hash` and the newer Ed25519 `signature` field — neither is part
        // of the HMAC data-check-string (recent Telegram clients send `signature`).
        unset($params['hash'], $params['signature']);

        // Build the data-check-string: keys sorted alphabetically, "key=value" joined by \n
        ksort($params);
        $pairs = [];
        foreach ($params as $key => $value) {
            $pairs[] = $key . '=' . $value;
        }
        $dataCheckString = implode("\n", $pairs);

        $secretKey    = hash_hmac('sha256', $botToken, 'WebAppData', true);
        $computedHash = hash_hmac('sha256', $dataCheckString, $secretKey);

        if (!hash_equals($computedHash, $hash)) {
            return null;
        }

        // Reject stale payloads to limit replay
        if (!empty($params['auth_date'])) {
            $age = time() - (int) $params['auth_date'];
            if ($age > $ttl) {
                return null;
            }
        }

        if (empty($params['user'])) {
            return null;
        }

        $user = json_decode($params['user'], true);
        return is_array($user) ? $user : null;
    }
}
