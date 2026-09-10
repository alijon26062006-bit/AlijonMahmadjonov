<?php
declare(strict_types=1);

namespace Hosting\Service;

/**
 * Тарифы хостинга. Лимиты копируются в карточку клиента при регистрации,
 * поэтому изменение тарифа здесь не ломает уже выданные лимиты.
 */
final class Plans
{
    public const PLANS = [
        'start' => [
            'title'         => 'Старт',
            'price_tjs'     => 15,
            'disk_quota_mb' => 1024,
            'max_sites'     => 1,
            'max_databases' => 1,
        ],
        'business' => [
            'title'         => 'Бизнес',
            'price_tjs'     => 45,
            'disk_quota_mb' => 5120,
            'max_sites'     => 5,
            'max_databases' => 5,
        ],
        'pro' => [
            'title'         => 'Про',
            'price_tjs'     => 90,
            'disk_quota_mb' => 20480,
            'max_sites'     => 25,
            'max_databases' => 25,
        ],
    ];

    public static function exists(string $code): bool
    {
        return isset(self::PLANS[$code]);
    }

    /** @return array{title:string,price_tjs:int,disk_quota_mb:int,max_sites:int,max_databases:int} */
    public static function get(string $code): array
    {
        if (!self::exists($code)) {
            throw new \InvalidArgumentException("Неизвестный тариф: {$code}");
        }
        return self::PLANS[$code];
    }

    public static function title(string $code): string
    {
        return self::exists($code) ? self::PLANS[$code]['title'] : $code;
    }

    /** @return array<string,array<string,mixed>> */
    public static function all(): array
    {
        return self::PLANS;
    }
}
