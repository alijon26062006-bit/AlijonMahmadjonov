<?php
declare(strict_types=1);

/**
 * Airalo Partner API client (https://partners-api.airalo.com).
 * OAuth2 client_credentials for the token, then Bearer auth for packages/orders.
 *
 * NOTE: written from the public Airalo Partner API docs. Field names on the
 * packages/orders payloads can change between API versions - if a real
 * account shows different JSON shapes, adjust the *_normalize_* helpers
 * below; the rest of the app only depends on the normalized array shape.
 */

function airalo_configured(array $config): bool
{
    return !empty($config['airalo_client_id']) && !empty($config['airalo_client_secret']);
}

function airalo_token_cache_path(): string
{
    return __DIR__ . '/../data/airalo_token.json';
}

/** @throws RuntimeException */
function airalo_get_token(array $config): string
{
    $cachePath = airalo_token_cache_path();
    if (is_file($cachePath)) {
        $cached = json_decode((string) file_get_contents($cachePath), true);
        if (is_array($cached) && ($cached['expires_at'] ?? 0) > time() + 30) {
            return (string) $cached['access_token'];
        }
    }

    $ch = curl_init($config['airalo_base_url'] . '/v2/token');
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query([
        'client_id' => $config['airalo_client_id'],
        'client_secret' => $config['airalo_client_secret'],
        'grant_type' => 'client_credentials',
    ]));
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 20);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Accept: application/json']);

    $body = curl_exec($ch);
    if ($body === false) {
        $err = curl_error($ch);
        curl_close($ch);
        throw new RuntimeException('airalo_token_curl_error: ' . $err);
    }
    curl_close($ch);

    $data = json_decode((string) $body, true);
    $token = $data['data']['access_token'] ?? $data['access_token'] ?? null;
    $expiresIn = (int) ($data['data']['expires_in'] ?? $data['expires_in'] ?? 3600);
    if (!$token) {
        throw new RuntimeException('airalo_token_missing: ' . $body);
    }

    @file_put_contents($cachePath, json_encode([
        'access_token' => $token,
        'expires_at' => time() + $expiresIn,
    ]));

    return (string) $token;
}

/** @throws RuntimeException */
function airalo_request(array $config, string $method, string $path, array $params = []): array
{
    $token = airalo_get_token($config);
    $url = $config['airalo_base_url'] . $path;

    $ch = curl_init();
    if ($method === 'GET') {
        if (!empty($params)) {
            $url .= '?' . http_build_query($params);
        }
        curl_setopt($ch, CURLOPT_URL, $url);
    } else {
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($params));
    }
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 25);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Authorization: Bearer ' . $token,
        'Accept: application/json',
    ]);

    $body = curl_exec($ch);
    if ($body === false) {
        $err = curl_error($ch);
        curl_close($ch);
        throw new RuntimeException('airalo_curl_error: ' . $err);
    }
    curl_close($ch);

    $data = json_decode((string) $body, true);
    if (!is_array($data)) {
        throw new RuntimeException('airalo_invalid_response: ' . $body);
    }
    return $data;
}

/** @return array<int,array> normalized Plan rows, or [] if nothing usable came back */
function airalo_fetch_plans(array $config): array
{
    $response = airalo_request($config, 'GET', '/v2/packages', ['limit' => 200]);
    $countries = $response['data'] ?? [];
    if (!is_array($countries)) {
        return [];
    }

    $plans = [];
    foreach ($countries as $country) {
        $countryName = $country['title'] ?? $country['name'] ?? 'Unknown';
        $countrySlug = strtolower((string) ($country['slug'] ?? preg_replace('/\s+/', '-', $countryName)));
        $countryFlag = $country['image']['flag'] ?? '🌍';
        $operators = $country['operators'] ?? [];

        foreach ($operators as $operator) {
            $packages = $operator['packages'] ?? [];
            foreach ($packages as $pkg) {
                $days = (int) ($pkg['day'] ?? $pkg['validity'] ?? 0);
                $dataAmount = $pkg['data'] ?? (isset($pkg['amount']) ? round($pkg['amount'] / 1024, 1) . ' GB' : '—');
                $price = (float) ($pkg['price'] ?? $pkg['net_price'] ?? 0);
                if (!isset($pkg['id']) || $price <= 0) {
                    continue;
                }
                $plans[] = [
                    'id' => (string) $pkg['id'],
                    'country_slug' => $countrySlug,
                    'country_name' => $countryName,
                    'country_flag' => $countryFlag,
                    'title' => "$dataAmount / $days дней",
                    'data_amount' => $dataAmount,
                    'days' => $days,
                    'price_usd' => $price,
                    'source' => 'airalo',
                ];
            }
        }
    }

    return $plans;
}

/**
 * Places a real eSIM order with Airalo and returns normalized eSIM details.
 * @return array{iccid:?string, qr_code_url:?string, qr_code_data:?string, demo:bool}
 * @throws RuntimeException
 */
function airalo_create_order(array $config, string $packageId, int $quantity = 1): array
{
    $response = airalo_request($config, 'POST', '/v2/orders', [
        'package_id' => $packageId,
        'quantity' => $quantity,
    ]);

    $sims = $response['data']['sims'] ?? [];
    $first = $sims[0] ?? null;
    if (!$first) {
        throw new RuntimeException('airalo_order_no_sim: ' . json_encode($response));
    }

    return [
        'iccid' => $first['iccid'] ?? null,
        'qr_code_url' => $first['qrcode_url'] ?? null,
        'qr_code_data' => $first['qrcode'] ?? $first['lpa'] ?? null,
        'demo' => false,
    ];
}

/** Used when Airalo isn't configured yet, so the admin flow stays testable end-to-end. */
function airalo_create_demo_order(string $planId): array
{
    $fakeIccid = '8988' . str_pad((string) random_int(0, 999999999999), 12, '0', STR_PAD_LEFT);
    return [
        'iccid' => $fakeIccid,
        'qr_code_url' => null,
        'qr_code_data' => "LPA:1\$demo.esim.local\$" . strtoupper(bin2hex(random_bytes(8))),
        'demo' => true,
    ];
}
