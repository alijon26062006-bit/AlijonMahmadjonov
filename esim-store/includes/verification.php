<?php
declare(strict_types=1);

function verification_generate_code(): string
{
    return (string) random_int(100000, 999999);
}

/** Generates + stores a code and sends it via Zadarma SMS. Falls back to a
 *  visible "demo code" when Zadarma isn't configured or the send fails, so
 *  checkout always stays usable while credentials aren't set yet. */
function verification_send(PDO $pdo, array $config, string $phone): array
{
    $code = verification_generate_code();
    $expires = (new DateTimeImmutable('+5 minutes'))->format(DateTimeInterface::ATOM);

    $pdo->prepare('DELETE FROM verification_codes WHERE phone = ?')->execute([$phone]);
    $pdo->prepare('INSERT INTO verification_codes (phone, code, expires_at, attempts) VALUES (?, ?, ?, 0)')
        ->execute([$phone, $code, $expires]);

    $configured = !empty($config['zadarma_key']) && !empty($config['zadarma_secret']);
    if (!$configured) {
        return ['ok' => true, 'demo' => true, 'demo_code' => $code];
    }

    try {
        zadarma_send_sms($config, $phone, "Код подтверждения {$config['site_name']}: $code");
        return ['ok' => true, 'demo' => false];
    } catch (Throwable $e) {
        error_log('[zadarma] sms send failed: ' . $e->getMessage());
        return ['ok' => true, 'demo' => true, 'demo_code' => $code, 'warning' => 'sms_send_failed'];
    }
}

function verification_check(PDO $pdo, string $phone, string $code): bool
{
    $stmt = $pdo->prepare('SELECT * FROM verification_codes WHERE phone = ?');
    $stmt->execute([$phone]);
    $row = $stmt->fetch();
    if (!$row) {
        return false;
    }
    if (new DateTimeImmutable($row['expires_at']) < new DateTimeImmutable('now')) {
        $pdo->prepare('DELETE FROM verification_codes WHERE phone = ?')->execute([$phone]);
        return false;
    }
    if ((int) $row['attempts'] >= 5) {
        return false;
    }

    $pdo->prepare('UPDATE verification_codes SET attempts = attempts + 1 WHERE phone = ?')->execute([$phone]);

    if (!hash_equals((string) $row['code'], $code)) {
        return false;
    }

    $pdo->prepare('DELETE FROM verification_codes WHERE phone = ?')->execute([$phone]);
    return true;
}
