<?php
declare(strict_types=1);

/**
 * Minimal Zadarma API client (https://zadarma.com/en/support/api/).
 * Auth scheme: Authorization: <key>:<signature>, where
 *   signature = base64(hmac_sha1(secret, path . sorted_params_string . md5(sorted_params_string)))
 */

function zadarma_signature(string $path, array $params, string $secret): string
{
    ksort($params);
    $paramsString = http_build_query($params);
    $authString = $path . $paramsString . md5($paramsString);
    return base64_encode(hash_hmac('sha1', $authString, $secret));
}

/** @throws RuntimeException on missing config or transport failure */
function zadarma_request(array $config, string $path, array $params = [], string $httpMethod = 'GET'): array
{
    if (empty($config['zadarma_key']) || empty($config['zadarma_secret'])) {
        throw new RuntimeException('zadarma_not_configured');
    }

    $sign = zadarma_signature($path, $params, $config['zadarma_secret']);
    $url = 'https://api.zadarma.com' . $path;

    $ch = curl_init();
    if ($httpMethod === 'GET') {
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
    curl_setopt($ch, CURLOPT_TIMEOUT, 15);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Authorization: ' . $config['zadarma_key'] . ':' . $sign,
    ]);

    $body = curl_exec($ch);
    if ($body === false) {
        $err = curl_error($ch);
        curl_close($ch);
        throw new RuntimeException('zadarma_curl_error: ' . $err);
    }
    curl_close($ch);

    $data = json_decode($body, true);
    if (!is_array($data)) {
        throw new RuntimeException('zadarma_invalid_response');
    }
    return $data;
}

/** @throws RuntimeException */
function zadarma_send_sms(array $config, string $phoneE164, string $message): bool
{
    $data = zadarma_request($config, '/v1/sms/send/', [
        'number' => ltrim($phoneE164, '+'),
        'message' => $message,
    ], 'POST');

    if (($data['status'] ?? '') !== 'success') {
        throw new RuntimeException('zadarma_sms_failed: ' . ($data['message'] ?? 'unknown'));
    }
    return true;
}
