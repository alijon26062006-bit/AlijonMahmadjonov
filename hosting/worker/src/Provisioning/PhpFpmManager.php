<?php
declare(strict_types=1);

namespace Hosting\Worker\Provisioning;

use Hosting\Support\Shell;

/** Пишет пулы php-fpm с той же схемой безопасности, что и NginxManager: test → atomic → reload/rollback. */
final class PhpFpmManager
{
    public function __construct(
        private string $poolDir,
        private string $phpVersion = '8.3',
        private bool $reloadEnabled = true,
    ) {
    }

    public function writeAndApply(string $filename, string $contents): void
    {
        $this->assertSafeFilename($filename);
        $target = $this->poolDir . '/' . $filename;
        $tmp = $target . '.tmp';

        if (@file_put_contents($tmp, $contents) === false) {
            throw new \RuntimeException('Не удалось записать временный пул: ' . $tmp);
        }

        // Валидируем именно новый файл: временно подменяем расширение, чтобы php-fpm -t
        // не подхватил старую версию вместе с новой при двойном чтении каталога.
        $test = $this->validate();
        if (!$test['ok']) {
            @unlink($tmp);
            throw new \RuntimeException("php-fpm -t не прошёл, пул {$filename} НЕ применён:\n" . $test['output']);
        }

        if (!@rename($tmp, $target)) {
            @unlink($tmp);
            throw new \RuntimeException('Не удалось переместить пул на место: ' . $target);
        }

        $this->reload();
    }

    public function remove(string $filename): void
    {
        $this->assertSafeFilename($filename);
        @unlink($this->poolDir . '/' . $filename);
        $this->reload();
    }

    /** @return array{ok:bool,output:string} */
    public function validate(): array
    {
        $result = Shell::run(sprintf('php-fpm%s -t 2>&1', $this->phpVersion), 20);
        return ['ok' => $result['code'] === 0, 'output' => $result['out'] . "\n" . $result['err']];
    }

    private function reload(): void
    {
        if (!$this->reloadEnabled) {
            return;
        }
        $service = 'php' . $this->phpVersion . '-fpm';
        $result = Shell::run('systemctl reload ' . escapeshellarg($service), 15);
        if ($result['code'] !== 0) {
            throw new \RuntimeException("systemctl reload {$service} не удался: " . $result['err']);
        }
    }

    private function assertSafeFilename(string $filename): void
    {
        if (!preg_match('~^[a-z0-9.\-]{1,190}\.conf$~i', $filename)) {
            throw new \InvalidArgumentException('Недопустимое имя файла пула: ' . $filename);
        }
    }
}
