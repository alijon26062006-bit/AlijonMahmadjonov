<?php
declare(strict_types=1);

if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

error_reporting(E_ALL);
ini_set('display_errors', '0');

$config = require __DIR__ . '/../config.php';

require_once __DIR__ . '/db.php';
require_once __DIR__ . '/functions.php';
require_once __DIR__ . '/catalog.php';
require_once __DIR__ . '/zadarma.php';
require_once __DIR__ . '/verification.php';
require_once __DIR__ . '/airalo.php';
require_once __DIR__ . '/orders.php';
require_once __DIR__ . '/auth.php';

$pdo = db($config);
