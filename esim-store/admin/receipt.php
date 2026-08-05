<?php
require __DIR__ . '/../includes/bootstrap.php';
admin_require(url('admin/index.php'));

$orderId = (string) ($_GET['order'] ?? '');
$order = order_get($pdo, $orderId);
if (!$order || empty($order['receipt_filename'])) {
    http_response_code(404);
    exit('Not found');
}

// receipt_filename is a generated id + a whitelisted extension only (see save_receipt_upload).
$fileName = basename($order['receipt_filename']);
$path = __DIR__ . '/../data/uploads/receipts/' . $fileName;
if (!is_file($path)) {
    http_response_code(404);
    exit('Not found');
}

$ext = strtolower((string) pathinfo($path, PATHINFO_EXTENSION));
$mimeMap = ['jpg' => 'image/jpeg', 'png' => 'image/png', 'webp' => 'image/webp', 'pdf' => 'application/pdf'];
header('Content-Type: ' . ($mimeMap[$ext] ?? 'application/octet-stream'));
header('Content-Length: ' . filesize($path));
header('Content-Disposition: inline; filename="' . $fileName . '"');
header('Cache-Control: private, max-age=0, no-store');
readfile($path);
