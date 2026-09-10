<?php

declare(strict_types=1);

use Hosting\Service\FileManager;
use Hosting\Support\Path;

function hosting_test_home(): string
{
    $home = sys_get_temp_dir() . '/hosting-fm-' . bin2hex(random_bytes(6));
    mkdir($home . '/public_html', 0o750, true);
    return $home;
}

function hosting_test_cleanup(string $home): void
{
    exec('rm -rf ' . escapeshellarg($home));
}

// ── Path traversal ──────────────────────────────────────────────────────────

function test_fm_path_traversal_dotdot_rejected(): void
{
    $home = hosting_test_home();
    try {
        assert_throws(static function () use ($home): void {
            Path::resolve($home, '../../../etc/passwd');
        }, '../../../etc/passwd должен быть отклонён');
    } finally {
        hosting_test_cleanup($home);
    }
}

function test_fm_path_traversal_mixed_dotdot_normalizes_inside(): void
{
    $home = hosting_test_home();
    try {
        // public_html/../public_html/index.php нормализуется ВНУТРИ дома — это не побег,
        // просто некрасивый, но легальный путь, и resolve должен его принять.
        file_put_contents($home . '/public_html/index.php', '<?php');
        $resolved = Path::resolve($home, 'public_html/../public_html/index.php');
        assert_true(str_starts_with($resolved, realpath($home)), 'Путь должен остаться внутри дома');
    } finally {
        hosting_test_cleanup($home);
    }
}

function test_fm_symlink_escape_rejected(): void
{
    $home = hosting_test_home();
    $outside = sys_get_temp_dir() . '/hosting-fm-outside-' . bin2hex(random_bytes(6));
    mkdir($outside, 0o750, true);
    file_put_contents($outside . '/secret.txt', 'тайна соседа');

    try {
        symlink($outside, $home . '/public_html/escape');
        assert_throws(static function () use ($home): void {
            Path::resolve($home, 'public_html/escape/secret.txt');
        }, 'Симлинк наружу домашнего каталога должен быть отклонён');
    } finally {
        hosting_test_cleanup($home);
        hosting_test_cleanup($outside);
    }
}

function test_fm_null_byte_in_name_rejected(): void
{
    assert_false(Path::isSafeName("evil.php\0.jpg"), 'Имя с null byte должно быть отклонено');
}

function test_fm_malicious_filenames_rejected(): void
{
    $bad = ['../etc/passwd', '..', '.', '', str_repeat('a', 300), "file\0.php", 'a/b'];
    foreach ($bad as $name) {
        assert_false(Path::isSafeName($name), "Имя '{$name}' должно быть отклонено как небезопасное");
    }
    assert_true(Path::isSafeName('normal-file_v2.php'), 'Обычное безопасное имя должно проходить');
}

// ── Zip Slip ─────────────────────────────────────────────────────────────────

function hosting_test_make_zip(string $path, array $entries): void
{
    $zip = new ZipArchive();
    $zip->open($path, ZipArchive::CREATE | ZipArchive::OVERWRITE);
    foreach ($entries as $name => $contents) {
        $zip->addFromString($name, $contents);
    }
    $zip->close();
}

function test_fm_zip_slip_does_not_escape_destination(): void
{
    $home = hosting_test_home();
    try {
        $zipPath = $home . '/public_html/evil.zip';
        hosting_test_make_zip($zipPath, [
            '../../../../tmp/hosting-zipslip-pwned.txt' => 'если это создалось вне — тест провален',
            'normal.txt' => 'обычный файл',
        ]);

        $fm = new FileManager($home);
        $fm->unzip('public_html/evil.zip');

        assert_false(
            is_file('/tmp/hosting-zipslip-pwned.txt'),
            'Zip Slip: файл не должен был вырваться за пределы каталога назначения'
        );
        assert_true(is_file($home . '/public_html/normal.txt'), 'Обычный файл должен был распаковаться');
    } finally {
        @unlink('/tmp/hosting-zipslip-pwned.txt');
        hosting_test_cleanup($home);
    }
}

function test_fm_zip_extracts_all_entries_under_limit(): void
{
    $home = hosting_test_home();
    try {
        $zipPath = $home . '/public_html/many.zip';
        $entries = [];
        for ($i = 0; $i < 5; $i++) {
            $entries["file{$i}.txt"] = 'x';
        }
        hosting_test_make_zip($zipPath, $entries);

        $fm = new FileManager($home);
        $extracted = $fm->unzip('public_html/many.zip');
        assert_equals(5, $extracted);
    } finally {
        hosting_test_cleanup($home);
    }
}

function test_fm_zip_entry_count_over_limit_rejected(): void
{
    $home = hosting_test_home();
    try {
        $zipPath = $home . '/public_html/bomb.zip';
        $entries = [];
        // Больше FileManager::MAX_ZIP_ENTRIES (20000) — считать статы всё равно дёшево и быстро.
        for ($i = 0; $i <= FileManager::MAX_ZIP_ENTRIES; $i++) {
            $entries["f{$i}"] = '';
        }
        hosting_test_make_zip($zipPath, $entries);

        $fm = new FileManager($home);
        assert_throws(static function () use ($fm): void {
            $fm->unzip('public_html/bomb.zip');
        }, 'Архив с числом файлов больше лимита должен быть отклонён целиком');
    } finally {
        hosting_test_cleanup($home);
    }
}

function test_fm_zip_oversized_uncompressed_rejected(): void
{
    $home = hosting_test_home();
    try {
        $zipPath = $home . '/public_html/big.zip';
        // 200 КБ несжатого контента, лимит передаём явно маленький (100 КБ) — должен отказать.
        hosting_test_make_zip($zipPath, ['big.txt' => str_repeat('A', 200 * 1024)]);

        $fm = new FileManager($home);
        assert_throws(static function () use ($fm): void {
            $fm->unzip('public_html/big.zip', 100 * 1024);
        }, 'Архив, превышающий переданный лимит распакованного размера, должен быть отклонён целиком');

        assert_false(is_file($home . '/public_html/big.txt'), 'Ничего не должно было распаковаться (отказ ДО записи)');
    } finally {
        hosting_test_cleanup($home);
    }
}

// ── Загрузка: запрещённые расширения ────────────────────────────────────────

function test_fm_blocked_extension_rejected_on_create(): void
{
    $home = hosting_test_home();
    try {
        $fm = new FileManager($home);
        assert_throws(static function () use ($fm): void {
            $fm->createFile('public_html', 'shell.phtml', '<?php system($_GET[0]);');
        }, 'Файлы .phtml должны быть запрещены');
    } finally {
        hosting_test_cleanup($home);
    }
}
