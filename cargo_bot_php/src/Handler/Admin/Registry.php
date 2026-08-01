<?php

namespace CargoBot\Handler\Admin;

use CargoBot\Util\Format;

/**
 * Реестр управляемых справочников админ-панели.
 *
 * Каждая сущность описана декларативно: таблица + список полей.
 * Универсальный движок (CrudHandler) по этому описанию строит списки,
 * карточки, добавление, редактирование, вкл/выкл и удаление.
 * Чтобы добавить новый справочник, достаточно описать его здесь.
 *
 * Типы полей: str | text | int | dec | bool | fk | choice | currency
 */
class Registry
{
    /** @return array<string,array<string,mixed>> */
    public static function all(): array
    {
        $e = [];

        $e['trf'] = [
            'title' => '💰 Тарифы',
            'one'   => 'Тариф',
            'table' => 'tariffs',
            'order' => 'delivery_type_id, id',
            'has_active' => true,
            'fields' => [
                ['name' => 'name', 'label' => 'Название', 'type' => 'str'],
                ['name' => 'delivery_type_id', 'label' => 'Тип доставки', 'type' => 'fk', 'fk' => 'dtp'],
                ['name' => 'category_id', 'label' => 'Категория товара', 'type' => 'fk', 'fk' => 'cat',
                 'required' => false, 'hint' => 'Пропустить = общий тариф для всех категорий'],
                ['name' => 'price_per_kg', 'label' => 'Стоимость за 1 кг', 'type' => 'dec'],
                ['name' => 'min_order_cost', 'label' => 'Минимальная стоимость заказа', 'type' => 'dec'],
                ['name' => 'min_weight', 'label' => 'Минимальный оплачиваемый вес, кг', 'type' => 'dec'],
                ['name' => 'currency_code', 'label' => 'Валюта расчёта', 'type' => 'currency'],
                ['name' => 'delivery_time', 'label' => 'Срок доставки', 'type' => 'str',
                 'required' => false, 'hint' => 'Например: 7–12 дней'],
            ],
            'row' => fn(array $r) => $r['name'] . ' — ' . Format::money($r['price_per_kg']) . ' ' . $r['currency_code'] . '/кг',
        ];

        $e['dtp'] = [
            'title' => '🚚 Типы доставки',
            'one'   => 'Тип доставки',
            'table' => 'delivery_types',
            'order' => 'sort_order, id',
            'has_active' => true,
            'fields' => [
                ['name' => 'name', 'label' => 'Название', 'type' => 'str'],
                ['name' => 'emoji', 'label' => 'Эмодзи', 'type' => 'str', 'required' => false],
                ['name' => 'sort_order', 'label' => 'Порядок сортировки', 'type' => 'int'],
            ],
            'row' => fn(array $r) => trim(($r['emoji'] ?? '') . ' ' . $r['name']),
        ];

        $e['cat'] = [
            'title' => '🗂 Категории товаров',
            'one'   => 'Категория',
            'table' => 'categories',
            'order' => 'sort_order, id',
            'has_active' => true,
            'fields' => [
                ['name' => 'name', 'label' => 'Название', 'type' => 'str'],
                ['name' => 'sort_order', 'label' => 'Порядок сортировки', 'type' => 'int'],
            ],
            'row' => fn(array $r) => (string) $r['name'],
        ];

        $e['cur'] = [
            'title' => '💱 Валюты',
            'one'   => 'Валюта',
            'table' => 'currencies',
            'order' => 'id',
            'has_active' => true,
            'fields' => [
                ['name' => 'code', 'label' => 'Код (например USD)', 'type' => 'str'],
                ['name' => 'name', 'label' => 'Название', 'type' => 'str'],
                ['name' => 'symbol', 'label' => 'Символ', 'type' => 'str', 'required' => false],
                ['name' => 'is_base', 'label' => 'Базовая валюта?', 'type' => 'bool'],
            ],
            'row' => fn(array $r) => $r['code'] . ' — ' . $r['name'],
        ];

        $e['rate'] = [
            'title' => '📈 Курсы валют',
            'one'   => 'Курс валюты',
            'table' => 'exchange_rates',
            'order' => 'currency_id, id',
            'has_active' => false,
            'stamp_updater' => true,
            'fields' => [
                ['name' => 'currency_id', 'label' => 'Валюта', 'type' => 'fk', 'fk' => 'cur'],
                ['name' => 'rate', 'label' => 'Курс к TJS (1 валюта = X TJS)', 'type' => 'dec'],
            ],
            'row' => fn(array $r) => 'Курс #' . $r['id'] . ' = ' . Format::num($r['rate']),
        ];

        $e['cof'] = [
            'title' => '🧮 Коэффициенты',
            'one'   => 'Коэффициент',
            'table' => 'coefficients',
            'order' => 'code, id',
            'has_active' => true,
            'fields' => [
                ['name' => 'name', 'label' => 'Название', 'type' => 'str'],
                ['name' => 'code', 'label' => 'Тип', 'type' => 'choice', 'choices' => [
                    'volumetric' => 'Объёмный вес (кг/м³)',
                    'density'    => 'Плотный груз (множитель цены)',
                    'custom'     => 'Другой',
                ]],
                ['name' => 'delivery_type_id', 'label' => 'Тип доставки', 'type' => 'fk', 'fk' => 'dtp',
                 'required' => false, 'hint' => 'Пропустить = для всех типов'],
                ['name' => 'category_id', 'label' => 'Категория', 'type' => 'fk', 'fk' => 'cat',
                 'required' => false, 'hint' => 'Пропустить = для всех категорий'],
                ['name' => 'value', 'label' => 'Значение', 'type' => 'dec'],
            ],
            'row' => fn(array $r) => $r['name'] . ' [' . $r['code'] . '] = ' . Format::num($r['value']),
        ];

        $e['svc'] = [
            'title' => '➕ Доп. услуги / скидки / наценки',
            'one'   => 'Услуга или скидка',
            'table' => 'extra_services',
            'order' => 'kind, id',
            'has_active' => true,
            'fields' => [
                ['name' => 'name', 'label' => 'Название', 'type' => 'str'],
                ['name' => 'kind', 'label' => 'Вид', 'type' => 'choice', 'choices' => [
                    'fee'      => 'Сбор (упаковка, страховка...)',
                    'discount' => 'Скидка',
                    'markup'   => 'Наценка',
                ]],
                ['name' => 'calc_type', 'label' => 'Способ расчёта', 'type' => 'choice', 'choices' => [
                    'fixed'   => 'Фиксированная сумма',
                    'percent' => '% от стоимости',
                    'per_kg'  => 'Сумма за каждый кг',
                ]],
                ['name' => 'value', 'label' => 'Значение', 'type' => 'dec'],
                ['name' => 'delivery_type_id', 'label' => 'Тип доставки', 'type' => 'fk', 'fk' => 'dtp',
                 'required' => false, 'hint' => 'Пропустить = для всех типов'],
                ['name' => 'category_id', 'label' => 'Категория', 'type' => 'fk', 'fk' => 'cat',
                 'required' => false, 'hint' => 'Пропустить = для всех категорий'],
            ],
            'row' => function (array $r) {
                $sign = $r['kind'] === 'discount' ? '−' : '+';
                $unit = ['percent' => '%', 'per_kg' => '/кг', 'fixed' => ''][$r['calc_type']] ?? '';
                return $r['name'] . ' (' . $sign . Format::num($r['value']) . $unit . ')';
            },
        ];

        $e['faq'] = [
            'title' => '❓ FAQ',
            'one'   => 'Вопрос',
            'table' => 'faq',
            'order' => 'sort_order, id',
            'has_active' => true,
            'fields' => [
                ['name' => 'question', 'label' => 'Вопрос', 'type' => 'str'],
                ['name' => 'answer', 'label' => 'Ответ', 'type' => 'text'],
                ['name' => 'sort_order', 'label' => 'Порядок сортировки', 'type' => 'int'],
            ],
            'row' => fn(array $r) => (string) $r['question'],
        ];

        $e['whs'] = [
            'title' => '📍 Склады',
            'one'   => 'Склад',
            'table' => 'warehouses',
            'order' => 'sort_order, id',
            'has_active' => true,
            'fields' => [
                ['name' => 'name', 'label' => 'Название', 'type' => 'str'],
                ['name' => 'address', 'label' => 'Адрес', 'type' => 'text'],
                ['name' => 'note', 'label' => 'Примечание', 'type' => 'text', 'required' => false],
                ['name' => 'sort_order', 'label' => 'Порядок сортировки', 'type' => 'int'],
            ],
            'row' => fn(array $r) => (string) $r['name'],
        ];

        $e['cnt'] = [
            'title' => '☎ Контакты',
            'one'   => 'Контакт',
            'table' => 'contacts',
            'order' => 'sort_order, id',
            'has_active' => true,
            'fields' => [
                ['name' => 'title', 'label' => 'Название (Телефон, Telegram...)', 'type' => 'str'],
                ['name' => 'value', 'label' => 'Значение', 'type' => 'text'],
                ['name' => 'sort_order', 'label' => 'Порядок сортировки', 'type' => 'int'],
            ],
            'row' => fn(array $r) => $r['title'] . ': ' . $r['value'],
        ];

        $e['adm'] = [
            'title' => '👮 Администраторы',
            'one'   => 'Администратор',
            'table' => 'admins',
            'order' => 'id',
            'has_active' => true,
            'fields' => [
                ['name' => 'tg_id', 'label' => 'Telegram ID', 'type' => 'int'],
                ['name' => 'name', 'label' => 'Имя', 'type' => 'str', 'required' => false],
            ],
            'row' => fn(array $r) => ($r['name'] ?: 'админ') . ' (' . $r['tg_id'] . ')',
        ];

        $e['set'] = [
            'title' => '⚙️ Настройки',
            'one'   => 'Настройка',
            'table' => 'settings',
            'order' => 'id',
            'has_active' => false,
            'can_add' => false,
            'fields' => [
                ['name' => 'value', 'label' => 'Значение', 'type' => 'text'],
                ['name' => 'description', 'label' => 'Описание', 'type' => 'text', 'required' => false],
            ],
            'row' => fn(array $r) => $r['key'] . ' = ' . Format::trunc((string) $r['value'], 24),
        ];

        return $e;
    }

    /** @return array<string,mixed>|null */
    public static function get(string $key): ?array
    {
        return self::all()[$key] ?? null;
    }

    /** Значение поля описания с настройками по умолчанию. */
    public static function field(array $entity, int $index): ?array
    {
        $f = $entity['fields'][$index] ?? null;
        if ($f === null) {
            return null;
        }
        $f['required'] = $f['required'] ?? true;
        $f['hint'] = $f['hint'] ?? '';
        $f['choices'] = $f['choices'] ?? [];
        return $f;
    }
}
