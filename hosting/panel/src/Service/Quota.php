<?php
declare(strict_types=1);

namespace Hosting\Service;

/** Подсчёт занятого места в домашнем каталоге клиента. */
final class Quota
{
    public static function directorySize(string $path): int
    {
        if (!is_dir($path)) {
            return 0;
        }

        $total = 0;
        $iterator = new \RecursiveIteratorIterator(
            new \RecursiveDirectoryIterator($path, \FilesystemIterator::SKIP_DOTS),
            \RecursiveIteratorIterator::SELF_FIRST
        );

        foreach ($iterator as $item) {
            /** @var \SplFileInfo $item */
            if ($item->isFile() && !$item->isLink()) {
                $total += (int) $item->getSize();
            }
        }

        return $total;
    }

    /**
     * @return array{used:int,limit:int,percent:int,exceeded:bool}
     */
    public static function usage(string $home, int $quotaMb): array
    {
        $used = self::directorySize($home);
        $limit = $quotaMb * 1024 * 1024;
        $percent = $limit > 0 ? (int) min(100, round($used / $limit * 100)) : 0;

        return [
            'used'     => $used,
            'limit'    => $limit,
            'percent'  => $percent,
            'exceeded' => $limit > 0 && $used >= $limit,
        ];
    }
}
