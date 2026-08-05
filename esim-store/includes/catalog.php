<?php
declare(strict_types=1);

/**
 * Plan catalog. Tries the live Airalo Partner API first (when credentials are
 * configured); falls back to a bundled mock catalog otherwise, or if the API
 * call fails, so the storefront always has something to show.
 */

function mock_catalog(): array
{
    return [
        ['slug' => 'turkey', 'name' => 'Турция', 'flag' => '🇹🇷', 'plans' => [
            ['data' => '1 GB', 'days' => 7, 'price' => 4.5],
            ['data' => '3 GB', 'days' => 15, 'price' => 9.0],
            ['data' => '10 GB', 'days' => 30, 'price' => 19.0],
        ]],
        ['slug' => 'uae', 'name' => 'ОАЭ', 'flag' => '🇦🇪', 'plans' => [
            ['data' => '1 GB', 'days' => 7, 'price' => 5.5],
            ['data' => '5 GB', 'days' => 30, 'price' => 16.0],
            ['data' => '10 GB', 'days' => 30, 'price' => 26.0],
        ]],
        ['slug' => 'russia', 'name' => 'Россия', 'flag' => '🇷🇺', 'plans' => [
            ['data' => '1 GB', 'days' => 7, 'price' => 3.5],
            ['data' => '5 GB', 'days' => 30, 'price' => 12.0],
            ['data' => '20 GB', 'days' => 30, 'price' => 24.0],
        ]],
        ['slug' => 'usa', 'name' => 'США', 'flag' => '🇺🇸', 'plans' => [
            ['data' => '1 GB', 'days' => 7, 'price' => 6.0],
            ['data' => '5 GB', 'days' => 30, 'price' => 18.0],
            ['data' => '10 GB', 'days' => 30, 'price' => 29.0],
        ]],
        ['slug' => 'schengen', 'name' => 'Европа (Шенген)', 'flag' => '🇪🇺', 'plans' => [
            ['data' => '3 GB', 'days' => 15, 'price' => 11.0],
            ['data' => '10 GB', 'days' => 30, 'price' => 27.0],
            ['data' => '20 GB', 'days' => 30, 'price' => 39.0],
        ]],
        ['slug' => 'thailand', 'name' => 'Таиланд', 'flag' => '🇹🇭', 'plans' => [
            ['data' => '1 GB', 'days' => 7, 'price' => 4.0],
            ['data' => '5 GB', 'days' => 15, 'price' => 10.5],
            ['data' => '10 GB', 'days' => 30, 'price' => 18.0],
        ]],
        ['slug' => 'china', 'name' => 'Китай', 'flag' => '🇨🇳', 'plans' => [
            ['data' => '1 GB', 'days' => 7, 'price' => 5.0],
            ['data' => '5 GB', 'days' => 15, 'price' => 13.0],
            ['data' => '10 GB', 'days' => 30, 'price' => 22.0],
        ]],
        ['slug' => 'georgia', 'name' => 'Грузия', 'flag' => '🇬🇪', 'plans' => [
            ['data' => '1 GB', 'days' => 7, 'price' => 3.0],
            ['data' => '5 GB', 'days' => 30, 'price' => 10.0],
            ['data' => '10 GB', 'days' => 30, 'price' => 16.0],
        ]],
        ['slug' => 'kazakhstan', 'name' => 'Казахстан', 'flag' => '🇰🇿', 'plans' => [
            ['data' => '1 GB', 'days' => 7, 'price' => 3.0],
            ['data' => '5 GB', 'days' => 30, 'price' => 9.5],
            ['data' => '10 GB', 'days' => 30, 'price' => 15.5],
        ]],
        ['slug' => 'egypt', 'name' => 'Египет', 'flag' => '🇪🇬', 'plans' => [
            ['data' => '1 GB', 'days' => 7, 'price' => 4.0],
            ['data' => '5 GB', 'days' => 30, 'price' => 12.5],
            ['data' => '10 GB', 'days' => 30, 'price' => 20.0],
        ]],
        ['slug' => 'uk', 'name' => 'Великобритания', 'flag' => '🇬🇧', 'plans' => [
            ['data' => '1 GB', 'days' => 7, 'price' => 5.5],
            ['data' => '5 GB', 'days' => 30, 'price' => 17.0],
            ['data' => '10 GB', 'days' => 30, 'price' => 27.0],
        ]],
        ['slug' => 'south-korea', 'name' => 'Южная Корея', 'flag' => '🇰🇷', 'plans' => [
            ['data' => '1 GB', 'days' => 5, 'price' => 4.5],
            ['data' => '5 GB', 'days' => 15, 'price' => 12.0],
            ['data' => '10 GB', 'days' => 30, 'price' => 21.0],
        ]],
        ['slug' => 'global', 'name' => 'Весь мир', 'flag' => '🌍', 'plans' => [
            ['data' => '1 GB', 'days' => 7, 'price' => 9.0],
            ['data' => '3 GB', 'days' => 30, 'price' => 22.0],
            ['data' => '10 GB', 'days' => 30, 'price' => 55.0],
        ]],
    ];
}

/** Flattens the nested mock catalog into a plain list of Plan rows. */
function mock_plans(): array
{
    $plans = [];
    foreach (mock_catalog() as $country) {
        foreach ($country['plans'] as $p) {
            $dataSlug = strtolower(str_replace(' ', '', $p['data']));
            $id = "{$country['slug']}-{$dataSlug}-{$p['days']}d";
            $plans[] = [
                'id' => $id,
                'country_slug' => $country['slug'],
                'country_name' => $country['name'],
                'country_flag' => $country['flag'],
                'title' => "{$p['data']} / {$p['days']} дней",
                'data_amount' => $p['data'],
                'days' => $p['days'],
                'price_usd' => $p['price'],
                'source' => 'mock',
            ];
        }
    }
    return $plans;
}

/** @return array<int, array> full flat list of plans, live Airalo data when configured. */
function get_all_plans(array $config): array
{
    static $cache = null;
    if ($cache !== null) {
        return $cache;
    }

    if (!empty($config['airalo_client_id']) && !empty($config['airalo_client_secret'])) {
        try {
            $live = airalo_fetch_plans($config);
            if (!empty($live)) {
                $cache = $live;
                return $cache;
            }
        } catch (Throwable $e) {
            error_log('[airalo] catalog fetch failed, falling back to mock: ' . $e->getMessage());
        }
    }

    $cache = mock_plans();
    return $cache;
}

/** @return array<int, array{slug:string,name:string,flag:string,plans_from:float}> */
function get_destinations(array $config): array
{
    $byCountry = [];
    foreach (get_all_plans($config) as $plan) {
        $slug = $plan['country_slug'];
        if (!isset($byCountry[$slug])) {
            $byCountry[$slug] = [
                'slug' => $slug,
                'name' => $plan['country_name'],
                'flag' => $plan['country_flag'],
                'plans_from' => $plan['price_usd'],
            ];
        } else {
            $byCountry[$slug]['plans_from'] = min($byCountry[$slug]['plans_from'], $plan['price_usd']);
        }
    }
    usort($byCountry, fn($a, $b) => strcmp($a['name'], $b['name']));
    return array_values($byCountry);
}

function get_destination(array $config, string $slug): ?array
{
    foreach (get_destinations($config) as $d) {
        if ($d['slug'] === $slug) {
            return $d;
        }
    }
    return null;
}

/** @return array<int, array> plans for one country */
function get_plans_for_country(array $config, string $slug): array
{
    return array_values(array_filter(
        get_all_plans($config),
        fn($p) => $p['country_slug'] === $slug
    ));
}

function get_plan_by_id(array $config, string $planId): ?array
{
    foreach (get_all_plans($config) as $plan) {
        if ($plan['id'] === $planId) {
            return $plan;
        }
    }
    return null;
}
