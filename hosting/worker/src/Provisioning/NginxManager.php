<?php
declare(strict_types=1);

namespace Hosting\Worker\Provisioning;

use Hosting\Support\Shell;

/**
 * Пишет vhost-конфиги nginx и применяет их безопасно:
 *
 *   создать временный файл → nginx -t → если OK: atomic rename + reload
 *                                        если ERROR: удалить временный, оставить старый, вернуть ошибку
 *
 * Ни один недействительный конфиг никогда не попадает в sites-available/enabled.
 */
final class NginxManager
{
    public function __construct(
        private string $availableDir,
        private string $enabledDir,
        private bool $reloadEnabled = true,
    ) {
    }

    /** @throws \RuntimeException если nginx -t не проходит — старый конфиг остаётся нетронутым */
    /**
     * Убирает строки `listen [::]…`, если у ядра нет IPv6.
     *
     * nginx на такой машине падает на СТАРТЕ проверки конфига с
     * «socket() [::]:80 failed (97: Address family not supported by protocol)»,
     * то есть не применяется вообще ни один сайт — включая панель. Отсутствие
     * /proc/net/if_inet6 — стандартный признак выключенного IPv6.
     */
    public static function stripIpv6IfUnavailable(string $contents): string
    {
        if (file_exists('/proc/net/if_inet6')) {
            return $contents;
        }

        return (string) preg_replace('~^[ \t]*listen[ \t]+\[::\][^\n]*\n~m', '', $contents);
    }

    public function writeAndApply(string $filename, string $contents): void
    {
        $contents = self::stripIpv6IfUnavailable($contents);

        $this->assertSafeFilename($filename);
        $target = $this->availableDir . '/' . $filename;
        $tmp = $target . '.tmp';

        if (@file_put_contents($tmp, $contents) === false) {
            throw new \RuntimeException('Не удалось записать временный конфиг: ' . $tmp);
        }

        $test = $this->validate();
        if (!$test['ok']) {
            @unlink($tmp);
            throw new \RuntimeException("nginx -t не прошёл, конфиг {$filename} НЕ применён:\n" . $test['output']);
        }

        if (!@rename($tmp, $target)) {
            @unlink($tmp);
            throw new \RuntimeException('Не удалось переместить конфиг на место: ' . $target);
        }

        $this->enable($filename);
        $this->reload();
    }

    public function remove(string $filename): void
    {
        $this->assertSafeFilename($filename);
        $this->disable($filename);
        @unlink($this->availableDir . '/' . $filename);
        $this->reload();
    }

    public function disable(string $filename): void
    {
        $this->assertSafeFilename($filename);
        @unlink($this->enabledDir . '/' . $filename);
    }

    private function enable(string $filename): void
    {
        $link = $this->enabledDir . '/' . $filename;
        $target = $this->availableDir . '/' . $filename;
        if (!file_exists($link)) {
            @symlink($target, $link);
        }
    }

    /** @return array{ok:bool,output:string} */
    public function validate(): array
    {
        $result = Shell::run('nginx -t 2>&1', 20);
        return ['ok' => $result['code'] === 0, 'output' => $result['out'] . "\n" . $result['err']];
    }

    private function reload(): void
    {
        if (!$this->reloadEnabled) {
            return;
        }
        $result = Shell::run('systemctl reload nginx', 15);
        if ($result['code'] !== 0) {
            throw new \RuntimeException('systemctl reload nginx не удался: ' . $result['err']);
        }
    }

    private function assertSafeFilename(string $filename): void
    {
        if (!preg_match('~^[a-z0-9.\-]{1,190}\.conf$~i', $filename)) {
            throw new \InvalidArgumentException('Недопустимое имя файла конфига: ' . $filename);
        }
    }
}
