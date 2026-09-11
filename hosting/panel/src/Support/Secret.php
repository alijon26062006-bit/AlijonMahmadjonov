<?php
declare(strict_types=1);

namespace Hosting\Support;

/**
 * Обратимое шифрование для секретов, которые панель обязана уметь ПОКАЗАТЬ.
 *
 * Пароли входа в панель хранятся хешем и никогда не расшифровываются — это
 * правильно. Но пароль от базы клиента ему нужно видеть: иначе после первого
 * показа взять его негде, а менять — значит ломать все уже настроенные сайты.
 *
 * Открытым текстом такой пароль в базе панели лежать не должен: один дамп
 * панельной базы дал бы доступ ко всем базам всех клиентов. Поэтому AES-256-GCM,
 * ключ — в .env (APP_KEY), то есть вне базы: утёкший дамп без файла настроек
 * бесполезен.
 *
 * GCM, а не CBC: он сам проверяет целостность, и подменённый шифротекст не
 * расшифруется молча в мусор.
 */
final class Secret
{
    private const CIPHER = 'aes-256-gcm';

    public static function encrypt(string $plain, string $key): string
    {
        $binKey = self::normalizeKey($key);
        $iv = random_bytes(12);
        $tag = '';

        $cipher = openssl_encrypt($plain, self::CIPHER, $binKey, OPENSSL_RAW_DATA, $iv, $tag);
        if ($cipher === false) {
            throw new \RuntimeException('Не удалось зашифровать секрет');
        }

        return base64_encode($iv . $tag . $cipher);
    }

    /** @return string|null null, если расшифровать нельзя (нет ключа, другой ключ, испорченные данные) */
    public static function decrypt(string $stored, string $key): ?string
    {
        $raw = base64_decode($stored, true);
        if ($raw === false || strlen($raw) < 29) {
            return null;
        }

        $iv = substr($raw, 0, 12);
        $tag = substr($raw, 12, 16);
        $cipher = substr($raw, 28);

        $plain = openssl_decrypt($cipher, self::CIPHER, self::normalizeKey($key), OPENSSL_RAW_DATA, $iv, $tag);

        return $plain === false ? null : $plain;
    }

    /**
     * Приводит ключ из .env к 32 байтам.
     *
     * Хеширование, а не обрезка: в .env лежит человекочитаемая строка, и её
     * длина не обязана совпадать с длиной ключа шифра.
     */
    private static function normalizeKey(string $key): string
    {
        if ($key === '') {
            throw new \RuntimeException('APP_KEY не задан — без него секреты не шифруются');
        }

        return hash('sha256', $key, true);
    }
}
