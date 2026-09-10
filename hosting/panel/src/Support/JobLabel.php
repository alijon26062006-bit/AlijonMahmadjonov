<?php
declare(strict_types=1);

namespace Hosting\Support;

/**
 * Человеческие названия для очереди заданий.
 *
 * В базе тип задания — это имя обработчика (create_site, apply_quota). Показывать
 * его клиенту нельзя: он ничего не говорит и выглядит как утечка внутренностей.
 * Незнакомый тип не выдумываем — показываем нейтральное «Операция».
 */
final class JobLabel
{
    private const TYPES = [
        'create_user'     => 'Подготовка аккаунта',
        'create_site'     => 'Создание сайта',
        'delete_site'     => 'Удаление сайта',
        'suspend_site'    => 'Приостановка сайта',
        'unsuspend_site'  => 'Возобновление сайта',
        'create_database' => 'Создание базы данных',
        'delete_database' => 'Удаление базы данных',
        'apply_nginx'     => 'Настройка веб-сервера',
        'apply_php_fpm'   => 'Настройка PHP',
        'issue_ssl'       => 'Выпуск SSL-сертификата',
        'create_backup'   => 'Создание резервной копии',
        'restore_backup'  => 'Восстановление из копии',
        'apply_quota'     => 'Обновление дискового лимита',
        'ping'            => 'Проверка связи',
    ];

    private const STATUSES = [
        'pending' => 'В очереди',
        'running' => 'Выполняется',
        'success' => 'Готово',
        'failed'  => 'Ошибка',
    ];

    public static function type(string $type): string
    {
        return self::TYPES[$type] ?? 'Операция';
    }

    public static function status(string $status): string
    {
        return self::STATUSES[$status] ?? $status;
    }

    /** Этапы создания сайта — то, что видит клиент на странице «Сайт создаётся». */
    public static function siteStages(): array
    {
        return [
            'Создание системного пользователя',
            'Создание каталогов сайта',
            'Настройка PHP',
            'Настройка веб-сервера',
            'Проверка адреса и SSL',
            'Готово',
        ];
    }
}
