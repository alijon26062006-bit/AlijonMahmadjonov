<?php

namespace CargoBot\Service;

use CargoBot\Database;
use CargoBot\Repository\SettingsRepo;

/**
 * Расчёт стоимости доставки.
 *
 * Ни одно число не задано в коде: тарифы, коэффициенты, сборы, скидки,
 * курсы валют и правила округления читаются из базы при каждом расчёте.
 * Поэтому правки из админ-панели применяются мгновенно.
 */
class Calculator
{
    private Database $db;
    private SettingsRepo $settings;

    public function __construct(Database $db)
    {
        $this->db = $db;
        $this->settings = new SettingsRepo($db);
    }

    /**
     * @return array<string,mixed>|null null, если подходящего тарифа нет
     */
    public function calculate(int $deliveryTypeId, int $categoryId, float $weight,
                              float $volume = 0.0, ?int $userId = null): ?array
    {
        $tariff = $this->findTariff($deliveryTypeId, $categoryId);
        if (!$tariff) {
            return null;
        }

        $deliveryType = $this->db->one('SELECT * FROM delivery_types WHERE id = :i', ['i' => $deliveryTypeId]);
        $category     = $this->db->one('SELECT * FROM categories WHERE id = :i', ['i' => $categoryId]);

        // 1. Объёмный вес
        $volCoef = $this->coefficient('volumetric', $deliveryTypeId, null);
        $volumetricWeight = ($volCoef !== null && $volume > 0)
            ? round($volume * $volCoef, 2)
            : 0.0;

        // 2. Оплачиваемый вес = max(фактический, объёмный, минимальный по тарифу)
        $chargeable = max($weight, $volumetricWeight, (float) $tariff['min_weight']);

        // 3. Базовая стоимость (с учётом коэффициента плотного груза)
        $price = (float) $tariff['price_per_kg'];
        $density = $this->coefficient('density', null, $categoryId);
        if ($density !== null) {
            $price = $price * $density;
        }
        $base = round($price * $chargeable, 2);

        // 4. Минимальная стоимость заказа
        $minCost = (float) $tariff['min_order_cost'];
        $minApplied = $base < $minCost;
        if ($minApplied) {
            $base = $minCost;
        }

        // 5. Дополнительные сборы, скидки, наценки
        $lines = [];
        $total = $base;
        $services = $this->db->all('SELECT * FROM extra_services WHERE is_active = 1 ORDER BY kind, id');
        foreach ($services as $s) {
            $sDt  = $s['delivery_type_id'] !== null ? (int) $s['delivery_type_id'] : null;
            $sCat = $s['category_id'] !== null ? (int) $s['category_id'] : null;
            if ($sDt !== null && $sDt !== $deliveryTypeId) {
                continue;
            }
            if ($sCat !== null && $sCat !== $categoryId) {
                continue;
            }
            $value = (float) $s['value'];
            if ($s['calc_type'] === 'percent') {
                $amount = round($base * $value / 100, 2);
            } elseif ($s['calc_type'] === 'per_kg') {
                $amount = round($value * $chargeable, 2);
            } else {
                $amount = $value;
            }
            if ($s['kind'] === 'discount') {
                $amount = -$amount;
            }
            $lines[] = ['name' => (string) $s['name'], 'amount' => $amount];
            $total += $amount;
        }
        $total = max($total, 0.0);

        // 6. Округление по правилам из настроек
        $mode = $this->settings->get('rounding_mode', 'none');
        $step = (float) ($this->settings->get('rounding_step', '1') ?: '1');
        $total = $this->applyRounding($total, (string) $mode, $step);

        // 7. Пересчёт в базовую валюту (TJS)
        $totalTjs = null;
        $rate = $this->rateToBase((string) $tariff['currency_code']);
        if ($rate !== null && $tariff['currency_code'] !== 'TJS') {
            $totalTjs = round($total * $rate, 2);
        }

        $result = [
            'tariff'            => $tariff,
            'delivery_type'     => $deliveryType,
            'category'          => $category,
            'weight'            => $weight,
            'volume'            => $volume,
            'volumetric_weight' => $volumetricWeight,
            'chargeable_weight' => $chargeable,
            'price_per_kg'      => round($price, 2),
            'base_cost'         => $base,
            'min_order_applied' => $minApplied,
            'lines'             => $lines,
            'total'             => $total,
            'currency_code'     => (string) $tariff['currency_code'],
            'total_tjs'         => $totalTjs,
            'delivery_time'     => $tariff['delivery_time'] ?? null,
        ];

        // 8. История расчётов
        $this->db->insert('calculations', [
            'user_id'           => $userId,
            'tariff_id'         => (int) $tariff['id'],
            'delivery_type'     => $deliveryType['name'] ?? null,
            'category'          => $category['name'] ?? null,
            'weight'            => $weight,
            'volume'            => $volume,
            'chargeable_weight' => $chargeable,
            'total'             => $total,
            'currency_code'     => (string) $tariff['currency_code'],
            'details'           => json_encode(['base' => $base, 'lines' => $lines], JSON_UNESCAPED_UNICODE),
            'created_at'        => $this->db->now(),
        ]);

        return $result;
    }

    /** Сначала точный тариф (тип + категория), затем общий (категория не указана). */
    private function findTariff(int $deliveryTypeId, int $categoryId): ?array
    {
        $exact = $this->db->one(
            'SELECT * FROM tariffs
             WHERE is_active = 1 AND delivery_type_id = :dt AND category_id = :cat
             ORDER BY id LIMIT 1',
            ['dt' => $deliveryTypeId, 'cat' => $categoryId]
        );
        if ($exact) {
            return $exact;
        }
        return $this->db->one(
            'SELECT * FROM tariffs
             WHERE is_active = 1 AND delivery_type_id = :dt AND category_id IS NULL
             ORDER BY id LIMIT 1',
            ['dt' => $deliveryTypeId]
        );
    }

    /**
     * Наиболее подходящий активный коэффициент:
     * сначала привязанный к типу доставки/категории, затем глобальный.
     */
    private function coefficient(string $code, ?int $deliveryTypeId, ?int $categoryId): ?float
    {
        $rows = $this->db->all(
            'SELECT * FROM coefficients WHERE is_active = 1 AND code = :c ORDER BY id',
            ['c' => $code]
        );
        foreach ($rows as $row) {
            $rDt  = $row['delivery_type_id'] !== null ? (int) $row['delivery_type_id'] : null;
            $rCat = $row['category_id'] !== null ? (int) $row['category_id'] : null;
            if (($rDt !== null && $rDt === $deliveryTypeId) || ($rCat !== null && $rCat === $categoryId)) {
                return (float) $row['value'];
            }
        }
        foreach ($rows as $row) {
            if ($row['delivery_type_id'] === null && $row['category_id'] === null) {
                return (float) $row['value'];
            }
        }
        return null;
    }

    /** Курс валюты к базовой (TJS). */
    private function rateToBase(string $currencyCode): ?float
    {
        $cur = $this->db->one('SELECT * FROM currencies WHERE code = :c', ['c' => $currencyCode]);
        if (!$cur) {
            return null;
        }
        if ((int) $cur['is_base'] === 1) {
            return 1.0;
        }
        $rate = $this->db->one(
            'SELECT rate FROM exchange_rates WHERE currency_id = :i ORDER BY updated_at DESC, id DESC LIMIT 1',
            ['i' => (int) $cur['id']]
        );
        return $rate ? (float) $rate['rate'] : null;
    }

    private function applyRounding(float $value, string $mode, float $step): float
    {
        if ($mode === 'none' || $step <= 0) {
            return round($value, 2);
        }
        $q = $value / $step;
        if ($mode === 'up') {
            $q = ceil($q);
        } elseif ($mode === 'down') {
            $q = floor($q);
        } else {
            $q = round($q);
        }
        return round($q * $step, 2);
    }
}
