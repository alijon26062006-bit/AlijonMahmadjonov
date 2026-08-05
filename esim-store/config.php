<?php
/**
 * Non-secret defaults. Real credentials belong in config.local.php, which is
 * gitignored and never committed/pushed. Copy config.local.example.php to
 * config.local.php on the server and fill in the real values there.
 */
$config = [
    // 'sqlite' works with zero setup (for local testing/demo).
    // Set 'mysql' in config.local.php for production on Somonhost.
    'db_driver' => 'sqlite',
    'db_host' => 'localhost',
    'db_name' => 'esim_store',
    'db_user' => 'root',
    'db_pass' => '',
    'db_sqlite_path' => __DIR__ . '/data/esim.sqlite',

    'admin_password' => 'change-me',

    // Zadarma API (my.zadarma.com -> Интеграции -> Ключи и API). Server-side only.
    'zadarma_key' => '',
    'zadarma_secret' => '',
    // Zadarma WebRTC widget key (Интеграции -> WebRTC tab). Public, safe for the browser.
    'zadarma_widget_key' => '',

    // Airalo Partner API (partners.airalo.com). Server-side only.
    'airalo_client_id' => '',
    'airalo_client_secret' => '',
    'airalo_base_url' => 'https://partners-api.airalo.com',

    'payment_instructions' => 'Переведите точную сумму заказа и загрузите скриншот чека для подтверждения.',
    'site_name' => 'EasySIM',
    'site_url' => 'http://localhost:8000',
    // Set to '/esim' etc. if the app lives in a subfolder instead of the domain root.
    'base_path' => '',
    'support_phone' => '',
    'support_email' => 'support@example.com',

    'max_receipt_size_mb' => 5,
];

$localConfigFile = __DIR__ . '/config.local.php';
if (file_exists($localConfigFile)) {
    $local = require $localConfigFile;
    if (is_array($local)) {
        $config = array_merge($config, $local);
    }
}

return $config;
