<?php
declare(strict_types=1);

/** @return array{ok:bool, filename?:string, error?:string} */
function save_receipt_upload(array $file, array $config): array
{
    if (($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
        return ['ok' => false, 'error' => 'Загрузите скриншот или PDF чека.'];
    }

    $maxBytes = (int) ($config['max_receipt_size_mb'] ?? 5) * 1024 * 1024;
    if ((int) $file['size'] > $maxBytes) {
        return ['ok' => false, 'error' => 'Файл слишком большой (макс. ' . (int) $config['max_receipt_size_mb'] . ' МБ).'];
    }

    $finfo = new finfo(FILEINFO_MIME_TYPE);
    $mime = $finfo->file($file['tmp_name']);
    $allowed = ['image/jpeg' => 'jpg', 'image/png' => 'png', 'image/webp' => 'webp', 'application/pdf' => 'pdf'];
    if (!isset($allowed[$mime])) {
        return ['ok' => false, 'error' => 'Допустимы только изображения (JPG/PNG/WEBP) или PDF.'];
    }

    $dir = __DIR__ . '/../data/uploads/receipts';
    if (!is_dir($dir)) {
        mkdir($dir, 0775, true);
    }
    $storedName = generate_id() . '.' . $allowed[$mime];
    if (!move_uploaded_file($file['tmp_name'], $dir . '/' . $storedName)) {
        return ['ok' => false, 'error' => 'Не удалось сохранить файл, попробуйте ещё раз.'];
    }

    return ['ok' => true, 'filename' => $storedName];
}

function order_create(PDO $pdo, array $plan, int $quantity, string $email, string $phone, bool $phoneVerified): array
{
    $id = generate_id();
    $now = now_iso();
    $total = round($plan['price_usd'] * $quantity, 2);

    $stmt = $pdo->prepare('INSERT INTO orders (
        id, created_at, updated_at, status, customer_email, customer_phone, phone_verified,
        plan_id, plan_title, country_name, country_flag, plan_days, plan_data,
        price_usd, quantity, total_usd
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');

    $stmt->execute([
        $id, $now, $now, 'pending_payment', $email, $phone, $phoneVerified ? 1 : 0,
        $plan['id'], $plan['title'], $plan['country_name'], $plan['country_flag'], $plan['days'], $plan['data_amount'],
        $plan['price_usd'], $quantity, $total,
    ]);

    return order_get($pdo, $id);
}

function order_get(PDO $pdo, string $id): ?array
{
    $stmt = $pdo->prepare('SELECT * FROM orders WHERE id = ?');
    $stmt->execute([$id]);
    $row = $stmt->fetch();
    return $row ?: null;
}

/** @return array<int,array> newest first */
function order_list_all(PDO $pdo, ?string $statusFilter = null): array
{
    if ($statusFilter) {
        $stmt = $pdo->prepare('SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC');
        $stmt->execute([$statusFilter]);
    } else {
        $stmt = $pdo->query('SELECT * FROM orders ORDER BY created_at DESC');
    }
    return $stmt->fetchAll();
}

function order_attach_receipt(PDO $pdo, string $id, string $fileName): void
{
    $stmt = $pdo->prepare('UPDATE orders SET status = ?, receipt_filename = ?, receipt_uploaded_at = ?, updated_at = ? WHERE id = ?');
    $stmt->execute(['pending_review', $fileName, now_iso(), now_iso(), $id]);
}

function order_reject(PDO $pdo, string $id, string $note = ''): void
{
    $stmt = $pdo->prepare('UPDATE orders SET status = ?, admin_note = ?, updated_at = ? WHERE id = ?');
    $stmt->execute(['rejected', $note, now_iso(), $id]);
}

/**
 * Confirms payment and issues the eSIM (real Airalo order when configured,
 * a clearly-marked demo eSIM otherwise so the flow stays testable).
 */
function order_confirm_and_issue(PDO $pdo, array $config, string $id): array
{
    $order = order_get($pdo, $id);
    if (!$order) {
        return ['ok' => false, 'error' => 'not_found'];
    }

    $pdo->prepare('UPDATE orders SET status = ?, updated_at = ? WHERE id = ?')
        ->execute(['issuing', now_iso(), $id]);

    try {
        if (airalo_configured($config)) {
            $esim = airalo_create_order($config, $order['plan_id'], (int) $order['quantity']);
        } else {
            $esim = airalo_create_demo_order($order['plan_id']);
        }

        $stmt = $pdo->prepare('UPDATE orders SET status = ?, esim_iccid = ?, esim_qr_url = ?, esim_demo = ?, updated_at = ? WHERE id = ?');
        $stmt->execute(['issued', $esim['iccid'], $esim['qr_code_url'], $esim['demo'] ? 1 : 0, now_iso(), $id]);

        return ['ok' => true];
    } catch (Throwable $e) {
        error_log('[airalo] order issuance failed for ' . $id . ': ' . $e->getMessage());
        $pdo->prepare('UPDATE orders SET status = ?, admin_note = ?, updated_at = ? WHERE id = ?')
            ->execute(['failed', 'Airalo error: ' . $e->getMessage(), now_iso(), $id]);
        return ['ok' => false, 'error' => $e->getMessage()];
    }
}
