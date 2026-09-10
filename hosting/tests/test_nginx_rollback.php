<?php

declare(strict_types=1);

use Hosting\Worker\Provisioning\NginxManager;

/**
 * Проверяет алгоритм «временный файл → nginx -t → atomic replace / rollback» на настоящем
 * NginxManager, но с поддельными бинарниками nginx/systemctl в PATH — реальный root
 * и настоящий nginx для теста не нужны, а код выполнения тот же, что и в проде.
 */
function hosting_test_fake_bin(string $dir, bool $nginxShouldPass): void
{
    if (!is_dir($dir)) {
        mkdir($dir, 0o755, true);
    }

    $nginxScript = "#!/bin/sh\n" . ($nginxShouldPass
        ? "echo 'nginx: configuration file test is successful'\nexit 0\n"
        : "echo 'nginx: [emerg] unexpected end of file' >&2\nexit 1\n");
    file_put_contents($dir . '/nginx', $nginxScript);
    chmod($dir . '/nginx', 0o755);

    file_put_contents($dir . '/systemctl', "#!/bin/sh\nexit 0\n");
    chmod($dir . '/systemctl', 0o755);
}

function hosting_test_with_fake_path(bool $nginxShouldPass, callable $fn): void
{
    $tmp = sys_get_temp_dir() . '/hosting-test-' . bin2hex(random_bytes(6));
    $bin = $tmp . '/bin';
    hosting_test_fake_bin($bin, $nginxShouldPass);

    $originalPath = getenv('PATH');
    putenv('PATH=' . $bin . ':' . $originalPath);

    try {
        $fn($tmp);
    } finally {
        putenv('PATH=' . $originalPath);
        exec('rm -rf ' . escapeshellarg($tmp));
    }
}

function test_nginx_valid_config_is_applied(): void
{
    hosting_test_with_fake_path(true, function (string $tmp): void {
        $available = $tmp . '/sites-available';
        $enabled = $tmp . '/sites-enabled';
        mkdir($available, 0o755, true);
        mkdir($enabled, 0o755, true);

        $manager = new NginxManager($available, $enabled);
        $manager->writeAndApply('shop.myhost.tj.conf', "server { listen 80; }\n");

        assert_true(is_file($available . '/shop.myhost.tj.conf'), 'Конфиг должен быть записан');
        assert_true(is_link($enabled . '/shop.myhost.tj.conf'), 'Конфиг должен быть включён симлинком');
        assert_false(is_file($available . '/shop.myhost.tj.conf.tmp'), 'Временный файл не должен оставаться');
    });
}

function test_nginx_invalid_config_is_rolled_back(): void
{
    hosting_test_with_fake_path(false, function (string $tmp): void {
        $available = $tmp . '/sites-available';
        $enabled = $tmp . '/sites-enabled';
        mkdir($available, 0o755, true);
        mkdir($enabled, 0o755, true);

        // Старый рабочий конфиг уже на месте — он не должен пострадать при неудачном apply.
        file_put_contents($available . '/shop.myhost.tj.conf', "server { listen 80; } # старый рабочий конфиг\n");

        $manager = new NginxManager($available, $enabled);

        assert_throws(static function () use ($manager): void {
            $manager->writeAndApply('shop.myhost.tj.conf', 'server { СЛОМАННЫЙ КОНФИГ');
        }, 'Невалидный конфиг должен приводить к исключению, а не тихо применяться');

        $contents = (string) file_get_contents($available . '/shop.myhost.tj.conf');
        assert_true(
            str_contains($contents, 'старый рабочий конфиг'),
            'После неудачного apply должен остаться старый конфиг, а не сломанный новый'
        );
        assert_false(
            is_file($available . '/shop.myhost.tj.conf.tmp'),
            'Временный файл с плохим конфигом должен быть удалён'
        );
    });
}

function test_nginx_rejects_unsafe_filename(): void
{
    hosting_test_with_fake_path(true, function (string $tmp): void {
        $available = $tmp . '/sites-available';
        $enabled = $tmp . '/sites-enabled';
        mkdir($available, 0o755, true);
        mkdir($enabled, 0o755, true);

        $manager = new NginxManager($available, $enabled);

        assert_throws(static function () use ($manager): void {
            $manager->writeAndApply('../../etc/passwd', 'server {}');
        }, 'Имя файла с traversal должно быть отклонено до записи на диск');
    });
}
