<?php
declare(strict_types=1);

namespace Hosting\Support;

/**
 * Проверяет, что домен клиента реально указывает на наш сервер, ПЕРЕД тем как
 * панель поставит в очередь issue_ssl. Заодно защита от SSRF/внутренних имён:
 * если бы мы доверяли произвольному указанному домену вслепую, злоумышленник
 * мог бы направить certbot/воркер дёргать localhost или внутренний IP через
 * специально сконфигурированный DNS-ответ.
 */
final class DnsVerifier
{
    /** @return array{ok:bool,error:string} */
    public static function pointsToServer(string $domain, string $serverIp): array
    {
        $domain = Domain::normalize($domain);

        if (!Domain::isValidFqdn($domain)) {
            return ['ok' => false, 'error' => 'Некорректное доменное имя'];
        }

        // Запрещённые для этого механизма имена: localhost, .local, .internal и т.п.
        // — их разрешение может быть подделано локальным резолвером.
        foreach (['localhost', 'localdomain', 'internal', 'local', 'lan'] as $bad) {
            if ($domain === $bad || str_ends_with($domain, '.' . $bad)) {
                return ['ok' => false, 'error' => 'Служебные псевдо-домены запрещены'];
            }
        }

        if ($serverIp === '') {
            return ['ok' => false, 'error' => 'HOSTING_SERVER_IP не задан в конфигурации панели'];
        }

        $records = @dns_get_record($domain, DNS_A + DNS_AAAA);
        if ($records === false || $records === []) {
            return ['ok' => false, 'error' => 'Не удалось получить DNS A/AAAA записи для домена'];
        }

        $resolvedIps = [];
        foreach ($records as $record) {
            $ip = $record['ip'] ?? $record['ipv6'] ?? null;
            if (is_string($ip)) {
                $resolvedIps[] = $ip;
            }
        }

        foreach ($resolvedIps as $ip) {
            // Каждый резолвнутый адрес обязан быть публичным — иначе кто-то мог бы
            // указать A-запись на 127.0.0.1 / 169.254.x.x / 10.x.x.x и заставить
            // воркер обратиться туда (SSRF) вместо настоящего внешнего домена.
            $isPublic = filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE) !== false;
            if (!$isPublic) {
                return ['ok' => false, 'error' => "DNS-запись указывает на непубличный адрес: {$ip}"];
            }
        }

        if (!in_array($serverIp, $resolvedIps, true)) {
            return [
                'ok' => false,
                'error' => 'Домен не указывает на IP этого сервера (' . $serverIp . '), '
                    . 'найдено: ' . implode(', ', $resolvedIps),
            ];
        }

        return ['ok' => true, 'error' => ''];
    }
}
