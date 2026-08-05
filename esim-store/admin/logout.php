<?php
require __DIR__ . '/../includes/bootstrap.php';
admin_logout();
redirect(url('admin/index.php'));
