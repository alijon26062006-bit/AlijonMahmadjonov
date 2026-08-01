<?php

namespace CargoBot;

use CargoBot\Repository\SettingsRepo;

/**
 * Первичное наполнение базы демо-данными.
 * Все значения — примеры, администратор меняет их через /admin.
 * Повторный запуск безопасен: справочники не дублируются.
 */
class Seeder
{
    private Database $db;

    public function __construct(Database $db)
    {
        $this->db = $db;
    }

    public static function defaultSettings(): array
    {
        return [
            'rounding_mode'  => ['up', 'Округление итога: none | up | down | nearest'],
            'rounding_step'  => ['1', 'Шаг округления, например 1, 0.5, 10'],
            'order_statuses' => [
                json_encode(['Новая', 'В обработке', 'Подтверждена', 'Выкуплена', 'Отменена', 'Завершена'],
                    JSON_UNESCAPED_UNICODE),
                'Статусы заявок (список JSON)',
            ],
            'track_statuses' => [
                json_encode(['Получен на складе', 'Проверяется', 'Упакован', 'Отправлен', 'В пути',
                             'Прибыл', 'Проходит таможню', 'Готов к выдаче', 'Выдан'],
                    JSON_UNESCAPED_UNICODE),
                'Статусы грузов (список JSON)',
            ],
            'welcome_text' => [
                "👋 Добро пожаловать в бот карго-доставки Китай → Таджикистан!\nВыберите действие в меню ниже.",
                'Приветственное сообщение /start',
            ],
        ];
    }

    public function run(): void
    {
        $settings = new SettingsRepo($this->db);
        foreach (self::defaultSettings() as $key => [$value, $descr]) {
            if ($settings->get($key) === null) {
                $settings->set($key, $value, $descr);
            }
        }

        if ((int) $this->db->value('SELECT COUNT(*) FROM delivery_types') > 0) {
            return; // справочники уже заполнены
        }

        $dt = [];
        foreach ([['Авиа', '✈️', 1], ['Авто', '🚛', 2], ['Море', '🚢', 3], ['Железная дорога', '🚂', 4]] as [$n, $e, $s]) {
            $dt[$n] = $this->db->insert('delivery_types', ['name' => $n, 'emoji' => $e, 'sort_order' => $s]);
        }

        $cats = [];
        $catNames = ['Одежда', 'Обувь', 'Электроника', 'Телефоны', 'Бытовая техника',
                     'Косметика', 'Плотный груз', 'Объёмный груз', 'Другое'];
        foreach ($catNames as $i => $name) {
            $cats[$name] = $this->db->insert('categories', ['name' => $name, 'sort_order' => $i + 1]);
        }

        $cur = [];
        $cur['TJS'] = $this->db->insert('currencies', ['code' => 'TJS', 'name' => 'Сомони', 'symbol' => 'смн', 'is_base' => 1]);
        $cur['USD'] = $this->db->insert('currencies', ['code' => 'USD', 'name' => 'Доллар США', 'symbol' => '$']);
        $cur['CNY'] = $this->db->insert('currencies', ['code' => 'CNY', 'name' => 'Юань', 'symbol' => '¥']);

        foreach ([['TJS', 1], ['USD', 10.9], ['CNY', 1.5]] as [$code, $rate]) {
            $this->db->insert('exchange_rates', [
                'currency_id' => $cur[$code],
                'rate'        => $rate,
                'updated_at'  => $this->db->now(),
            ]);
        }

        // Коэффициенты объёмного веса (кг за 1 м³)
        foreach ([['Объёмный вес: Авиа', 'Авиа', 167], ['Объёмный вес: Авто', 'Авто', 200],
                  ['Объёмный вес: Море', 'Море', 100], ['Объёмный вес: ЖД', 'Железная дорога', 150]] as [$n, $type, $v]) {
            $this->db->insert('coefficients', [
                'name' => $n, 'code' => 'volumetric', 'delivery_type_id' => $dt[$type], 'value' => $v,
            ]);
        }
        $this->db->insert('coefficients', [
            'name' => 'Множитель: плотный груз', 'code' => 'density',
            'category_id' => $cats['Плотный груз'], 'value' => 1.2,
        ]);

        $tariffs = [
            ['Авиа / Одежда', 'Авиа', 'Одежда', 5.5, 10, 1, 'USD', '7–12 дней'],
            ['Авиа / Обувь', 'Авиа', 'Обувь', 6.0, 10, 1, 'USD', '7–12 дней'],
            ['Авиа / Электроника', 'Авиа', 'Электроника', 8.0, 15, 1, 'USD', '7–12 дней'],
            ['Авиа / Общий', 'Авиа', null, 6.5, 10, 1, 'USD', '7–12 дней'],
            ['Авто / Одежда', 'Авто', 'Одежда', 3.2, 5, 1, 'USD', '18–25 дней'],
            ['Авто / Общий', 'Авто', null, 3.8, 5, 1, 'USD', '18–25 дней'],
            ['Море / Общий', 'Море', null, 2.0, 5, 5, 'USD', '35–50 дней'],
            ['ЖД / Общий', 'Железная дорога', null, 2.8, 5, 3, 'USD', '25–35 дней'],
        ];
        foreach ($tariffs as [$name, $type, $cat, $price, $minCost, $minW, $code, $time]) {
            $this->db->insert('tariffs', [
                'name'             => $name,
                'delivery_type_id' => $dt[$type],
                'category_id'      => $cat ? $cats[$cat] : null,
                'price_per_kg'     => $price,
                'min_order_cost'   => $minCost,
                'min_weight'       => $minW,
                'currency_code'    => $code,
                'delivery_time'    => $time,
                'created_at'       => $this->db->now(),
            ]);
        }

        $this->db->insert('extra_services', [
            'name' => 'Упаковка', 'kind' => 'fee', 'calc_type' => 'fixed', 'value' => 2,
        ]);
        $this->db->insert('extra_services', [
            'name' => 'Страховка', 'kind' => 'fee', 'calc_type' => 'percent', 'value' => 1, 'is_active' => 0,
        ]);
        $this->db->insert('extra_services', [
            'name' => 'Оформление', 'kind' => 'fee', 'calc_type' => 'fixed', 'value' => 1, 'is_active' => 0,
        ]);

        $this->db->insert('faq', [
            'question' => 'Сколько идёт доставка?',
            'answer'   => 'Авиа — 7–12 дней, Авто — 18–25 дней, ЖД — 25–35 дней, Море — 35–50 дней.',
            'sort_order' => 1,
        ]);
        $this->db->insert('faq', [
            'question' => 'Как оплатить?',
            'answer'   => 'Оплата при получении груза на складе в Душанбе: наличными или переводом.',
            'sort_order' => 2,
        ]);

        $this->db->insert('warehouses', [
            'name'    => 'Склад в Гуанчжоу',
            'address' => 'Guangzhou, Baiyun District, ... (укажите адрес через /admin)',
            'note'    => 'Указывайте ваш код клиента на каждой коробке.',
            'sort_order' => 1,
        ]);

        foreach ([['Телефон', '+992 00 000 0000', 1], ['Telegram менеджера', '@manager', 2],
                  ['Адрес офиса', 'г. Душанбе, ул. ...', 3]] as [$title, $value, $sort]) {
            $this->db->insert('contacts', ['title' => $title, 'value' => $value, 'sort_order' => $sort]);
        }
    }
}
