<?php
declare(strict_types=1);

function url(string $path): string
{
    global $config;
    $base = rtrim((string) ($config['base_path'] ?? ''), '/');
    return $base . '/' . ltrim($path, '/');
}

function h(?string $value): string
{
    return htmlspecialchars($value ?? '', ENT_QUOTES, 'UTF-8');
}

function money(float $usd): string
{
    return '$' . number_format($usd, 2);
}

function generate_id(): string
{
    return strtoupper(bin2hex(random_bytes(5)));
}

function now_iso(): string
{
    return (new DateTimeImmutable('now'))->format(DateTimeInterface::ATOM);
}

function csrf_token(): string
{
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

function csrf_field(): string
{
    return '<input type="hidden" name="csrf_token" value="' . h(csrf_token()) . '">';
}

function csrf_check(): bool
{
    $sent = $_POST['csrf_token'] ?? ($_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
    return !empty($_SESSION['csrf_token']) && hash_equals($_SESSION['csrf_token'], (string) $sent);
}

function json_response(array $data, int $status = 200): never
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

function require_post(): void
{
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
    }
}

function redirect(string $path): never
{
    header('Location: ' . $path);
    exit;
}

function flash_set(string $key, string $message): void
{
    $_SESSION['flash'][$key] = $message;
}

function flash_get(string $key): ?string
{
    if (empty($_SESSION['flash'][$key])) {
        return null;
    }
    $msg = $_SESSION['flash'][$key];
    unset($_SESSION['flash'][$key]);
    return $msg;
}

/** Normalizes a phone number to a loose E.164-ish digits-with-plus form. */
function normalize_phone(string $phone): string
{
    $phone = trim($phone);
    $hasPlus = str_starts_with($phone, '+');
    $digits = preg_replace('/\D+/', '', $phone) ?? '';
    return ($hasPlus ? '+' : '+') . $digits;
}

function is_valid_phone(string $phone): bool
{
    return (bool) preg_match('/^\+\d{9,15}$/', $phone);
}

function is_valid_email(string $email): bool
{
    return filter_var($email, FILTER_VALIDATE_EMAIL) !== false;
}

/** @return array{label:string,class:string} */
function order_status_badge(string $status): array
{
    return match ($status) {
        'pending_payment' => ['label' => 'Ожидает оплаты', 'class' => 'badge-pending'],
        'pending_review' => ['label' => 'Чек на проверке', 'class' => 'badge-pending'],
        'issuing' => ['label' => 'Выдаём eSIM…', 'class' => 'badge-info'],
        'issued' => ['label' => 'eSIM выдан', 'class' => 'badge-success'],
        'rejected' => ['label' => 'Оплата отклонена', 'class' => 'badge-danger'],
        'failed' => ['label' => 'Ошибка выдачи', 'class' => 'badge-danger'],
        default => ['label' => $status, 'class' => 'badge-pending'],
    };
}

function cart_get(): array
{
    return $_SESSION['cart'] ?? [];
}

function cart_count(): int
{
    $count = 0;
    foreach (cart_get() as $item) {
        $count += (int) ($item['quantity'] ?? 1);
    }
    return $count;
}

function cart_add(string $planId, int $quantity = 1): void
{
    if (!isset($_SESSION['cart'])) {
        $_SESSION['cart'] = [];
    }
    if (isset($_SESSION['cart'][$planId])) {
        $_SESSION['cart'][$planId]['quantity'] += $quantity;
    } else {
        $_SESSION['cart'][$planId] = ['plan_id' => $planId, 'quantity' => $quantity];
    }
}

function cart_remove(string $planId): void
{
    unset($_SESSION['cart'][$planId]);
}

function cart_clear(): void
{
    $_SESSION['cart'] = [];
}

/** @return array{items: array<int, array{plan: array, quantity: int, subtotal: float}>, total: float} */
function get_cart_items(array $config): array
{
    $items = [];
    $total = 0.0;
    foreach (cart_get() as $planId => $entry) {
        $plan = get_plan_by_id($config, (string) $planId);
        if (!$plan) {
            cart_remove((string) $planId);
            continue;
        }
        $qty = (int) $entry['quantity'];
        $subtotal = round($plan['price_usd'] * $qty, 2);
        $items[] = ['plan' => $plan, 'quantity' => $qty, 'subtotal' => $subtotal];
        $total += $subtotal;
    }
    return ['items' => $items, 'total' => round($total, 2)];
}
