<?php

namespace CargoBot;

/**
 * Тексты интерфейса.
 * Мультиязычность: добавьте массив для нового языка в $lex
 * и укажите язык в поле users.language.
 */
class Texts
{
    private static array $lex = [
        'ru' => [
            'btn_calc'       => '📦 Рассчитать стоимость доставки',
            'btn_track'      => '🔍 Отследить груз',
            'btn_order'      => '📝 Оставить заявку',
            'btn_tariffs'    => '💰 Тарифы',
            'btn_warehouses' => '📍 Склады',
            'btn_contacts'   => '☎ Контакты',
            'btn_faq'        => '❓ FAQ',
            'btn_cancel'     => '❌ Отмена',
            'cancelled'      => 'Действие отменено.',

            'calc_delivery_type' => 'Выберите тип доставки:',
            'calc_category'      => 'Выберите категорию товара:',
            'calc_weight'        => '⚖️ Введите вес груза в кг (например: 12.5):',
            'calc_volume'        => "📐 Введите объём в м³ (например: 0.15).\nЕсли объём неизвестен — отправьте 0:",
            'calc_bad_number'    => 'Пожалуйста, введите число, например: 12.5',
            'calc_no_tariff'     => "😔 Для выбранных параметров нет активного тарифа.\n"
                                    . 'Свяжитесь с менеджером — раздел «☎ Контакты».',
            'btn_make_order'     => '📝 Оформить заявку',

            'track_ask'       => 'Введите ваш трек-номер:',
            'track_not_found' => "Трек-номер не найден. Проверьте правильность ввода\nили свяжитесь с менеджером.",

            'order_name'        => 'Как вас зовут?',
            'order_phone'       => '📱 Ваш номер телефона (например: +992 900 00 00 00):',
            'order_url'         => '🔗 Ссылка на товар (или отправьте «-», если нет):',
            'order_description' => '📄 Опишите товар:',
            'order_weight'      => '⚖️ Примерный вес в кг (или «-», если неизвестен):',
            'order_volume'      => '📐 Примерный объём в м³ (или «-», если неизвестен):',
            'order_comment'     => '💬 Комментарий (или «-»):',
            'order_done'        => "✅ Заявка <b>%s</b> принята!\nМенеджер свяжется с вами в ближайшее время.",

            'no_data'   => 'Раздел пока пуст.',
            'faq_title' => '❓ Часто задаваемые вопросы — выберите вопрос:',
        ],
    ];

    public static function get(string $key, string $lang = 'ru'): string
    {
        return self::$lex[$lang][$key] ?? self::$lex['ru'][$key] ?? $key;
    }

    /** Главное меню клиента. */
    public static function mainMenu(string $lang = 'ru'): array
    {
        return Telegram\Keyboard::reply([
            [self::get('btn_calc', $lang)],
            [self::get('btn_track', $lang), self::get('btn_order', $lang)],
            [self::get('btn_tariffs', $lang), self::get('btn_warehouses', $lang)],
            [self::get('btn_contacts', $lang), self::get('btn_faq', $lang)],
        ]);
    }

    public static function cancelMenu(string $lang = 'ru'): array
    {
        return Telegram\Keyboard::reply([[self::get('btn_cancel', $lang)]]);
    }
}
