<?php
declare(strict_types=1);

namespace Hosting\Service;

/**
 * Проверка «работает ли сайт» — обычный HTTP-запрос по публичному адресу,
 * ровно такой же, какой сделает посетитель.
 *
 * Запрос идёт с сервера, но НЕ на произвольный адрес: домен берётся из записи
 * сайта в базе, а не из формы, поэтому это не превращается в SSRF-инструмент.
 */
final class SiteHealth
{
    public function __construct(private int $timeoutSeconds = 10)
    {
    }

    /**
     * @return array{ok:bool,url:string,status:int,ms:int,ssl:bool,error:string|null,hint:string|null}
     */
    public function check(string $domain): array
    {
        $https = 'https://' . $domain . '/';
        $result = $this->request($https);

        // Нет HTTPS — пробуем HTTP: сайт может работать, просто сертификат ещё не выпущен.
        if ($result['status'] === 0) {
            $plain = $this->request('http://' . $domain . '/');
            $plain['ssl'] = false;
            if ($plain['status'] > 0) {
                $plain['hint'] = 'Сайт отвечает только по http — сертификат ещё не выпущен';
                return $this->finish($plain);
            }
            return $this->finish($result);
        }

        $result['ssl'] = true;

        return $this->finish($result);
    }

    /** @return array{ok:bool,url:string,status:int,ms:int,ssl:bool,error:string|null,hint:string|null} */
    private function request(string $url): array
    {
        $started = microtime(true);
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_NOBODY         => false,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_MAXREDIRS      => 3,
            CURLOPT_TIMEOUT        => $this->timeoutSeconds,
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_USERAGENT      => 'HostingPanel-HealthCheck/1.0',
        ]);
        curl_exec($ch);
        $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $error = curl_errno($ch) !== 0 ? curl_error($ch) : null;
        curl_close($ch);

        return [
            'ok'     => $status >= 200 && $status < 400,
            'url'    => $url,
            'status' => $status,
            'ms'     => (int) round((microtime(true) - $started) * 1000),
            'ssl'    => str_starts_with($url, 'https://'),
            'error'  => $error,
            'hint'   => null,
        ];
    }

    /** Добавляет человеческое объяснение вместо кода ошибки. */
    private function finish(array $r): array
    {
        if ($r['hint'] !== null) {
            return $r;
        }

        $r['hint'] = match (true) {
            $r['status'] === 0   => 'Сайт не отвечает. Проверьте, что адрес указывает на сервер и провижининг завершён.',
            $r['status'] === 403 => 'Доступ запрещён. Проверьте права на файлы сайта.',
            $r['status'] === 404 => 'Файл не найден. Создайте public/index.php в файловом менеджере.',
            $r['status'] >= 500  => 'Ошибка в коде сайта. Откройте «Логи» — там текст ошибки PHP.',
            default              => null,
        };

        return $r;
    }
}
