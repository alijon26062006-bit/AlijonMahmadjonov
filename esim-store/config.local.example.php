<?php
/**
 * Copy this file to config.local.php on the server and fill in real values.
 * config.local.php is gitignored - it must NEVER be committed or pushed to GitHub.
 *
 * On Somonhost: create a MySQL database + user in the hosting control panel first,
 * then paste those credentials below and set db_driver to 'mysql'.
 */
return [
    'db_driver' => 'mysql',
    'db_host' => 'localhost',
    'db_name' => 'your_cpanel_db_name',
    'db_user' => 'your_cpanel_db_user',
    'db_pass' => 'your_cpanel_db_password',

    // Admin panel at /admin - pick a strong password.
    'admin_password' => '',

    // Zadarma (my.zadarma.com -> Интеграции -> Ключи и API)
    'zadarma_key' => '',
    'zadarma_secret' => '',
    'zadarma_widget_key' => '',

    // Airalo Partner API (partners.airalo.com)
    'airalo_client_id' => '',
    'airalo_client_secret' => '',

    'payment_instructions' => 'Переведите точную сумму заказа на карту 0000 0000 0000 0000 (Получатель: Имя Фамилия) и загрузите скриншот чека.',
    'site_name' => 'EasySIM',
    'site_url' => 'https://your-domain.tj',
    'support_phone' => '+992 00 000 0000',
    'support_email' => 'support@your-domain.tj',
];
