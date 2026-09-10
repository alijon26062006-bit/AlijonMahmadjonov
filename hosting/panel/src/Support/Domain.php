<?php
declare(strict_types=1);

namespace Hosting\Support;

/** Проверка доменов и имён поддоменов. */
final class Domain
{
    /** Слова, которые нельзя занимать под поддомен клиента. */
    public const RESERVED = [
        'www', 'panel', 'cp', 'mail', 'smtp', 'imap', 'pop', 'ns1', 'ns2',
        'ftp', 'admin', 'api', 'billing', 'whois', 'dns', 'mysql', 'db',
        'localhost', 'root', 'support', 'status',
    ];

    public static function isValidLabel(string $label): bool
    {
        $label = strtolower($label);
        if (strlen($label) < 3 || strlen($label) > 30) {
            return false;
        }
        if (in_array($label, self::RESERVED, true)) {
            return false;
        }
        return preg_match('~^[a-z0-9]([a-z0-9-]*[a-z0-9])?$~', $label) === 1;
    }

    public static function isValidFqdn(string $domain): bool
    {
        $domain = strtolower(trim($domain, '.'));
        if ($domain === '' || strlen($domain) > 253) {
            return false;
        }
        $labels = explode('.', $domain);
        if (count($labels) < 2) {
            return false;
        }
        foreach ($labels as $label) {
            if (strlen($label) < 1 || strlen($label) > 63) {
                return false;
            }
            if (preg_match('~^[a-z0-9]([a-z0-9-]*[a-z0-9])?$~', $label) !== 1) {
                return false;
            }
        }
        return true;
    }

    public static function normalize(string $domain): string
    {
        return strtolower(trim(trim($domain), '.'));
    }
}
