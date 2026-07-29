<?php
// ============================================
// QAZ Messenger — простой мессенджер как Telegram
// Поиск по номеру · личные чаты · ответы (reply) · группы · звонки
// Один файл. Использует общую базу (db.php) и звонок (call.php/call.js)
// ============================================
require __DIR__ . '/db.php';
require __DIR__ . '/tg.php';

// ============================================================================
// ВСТРОЕННАЯ ЗАЩИТА ОТ СПАМА (Rate Limiting / Throttling) — В САМОМ ВЕРХУ ФАЙЛА
// ----------------------------------------------------------------------------
// Проблема: из-за ошибки в клиентском опросе браузер мог слать сотни запросов
// в секунду. Это перегружало CPU и БД, чат «зависал» и мигал.
//
// Решение: для КАЖДОГО API-запроса (?action=...) проверяем частоту ЕЩЁ ДО
// миграций схемы и любых обращений к базе. При превышении лимита — сразу
// отдаём HTTP 429 и завершаем скрипт. Сам лимитер работает на файловой
// «корзине токенов» (token bucket) и НЕ трогает БД.
//
// Алгоритм «корзины токенов»:
//   • в корзине не больше $burst токенов (разрешённый короткий всплеск);
//   • каждую секунду добавляется $rate токенов (устойчивый темп);
//   • каждый запрос забирает 1 токен; токенов нет -> 429.
// $rate = 3 -> в среднем ~2–3 запроса/сек на клиента (как в задаче),
// $burst = 15 -> но обычные короткие всплески (открытие чата шлёт сразу
// несколько разных запросов) не блокируются.
// ============================================================================
if (!function_exists('rl_check')) {
    function rl_check($clientKey, $rate = 3.0, $burst = 15.0)
    {
        // Каталог для «корзин». Если он недоступен для записи — НЕ мешаем
        // работе приложения (fail-open): лучше пропустить, чем сломать чат.
        $dir = sys_get_temp_dir() . '/qaz_rl';
        if (!is_dir($dir)) { @mkdir($dir, 0700, true); }
        if (!is_dir($dir) || !is_writable($dir)) { return true; }

        // Отдельный файл на каждого клиента (ключ хэшируем — безопасное имя).
        $file = $dir . '/' . hash('crc32b', (string)$clientKey) . '.rl';

        $fp = @fopen($file, 'c+');
        if (!$fp) { return true; } // не смогли открыть — пропускаем (fail-open)

        $allowed = true;
        if (flock($fp, LOCK_EX)) {                 // блокировка от гонок между процессами
            $now  = microtime(true);
            $data = stream_get_contents($fp);
            // В файле хранится строка «токены|время_последнего_обновления».
            if ($data !== '' && strpos($data, '|') !== false) {
                [$tokens, $last] = explode('|', $data, 2);
                $tokens = (float)$tokens;
                $last   = (float)$last;
            } else {
                $tokens = $burst;                  // первый запрос — корзина полная
                $last   = $now;
            }

            // Пополняем корзину пропорционально прошедшему времени.
            $elapsed = $now - $last;
            if ($elapsed > 0) {
                $tokens = min($burst, $tokens + $elapsed * $rate);
            }

            if ($tokens >= 1.0) {
                $tokens -= 1.0;                     // запрос разрешён — забираем токен
                $allowed = true;
            } else {
                $allowed = false;                  // токенов нет — превышен лимит
            }

            // Сохраняем новое состояние корзины.
            ftruncate($fp, 0);
            rewind($fp);
            fwrite($fp, $tokens . '|' . $now);
            fflush($fp);
            flock($fp, LOCK_UN);
        }
        fclose($fp);
        return $allowed;
    }
}

// Гейт срабатывает только для API-запросов (?action=...). Обычная загрузка
// страницы и статические ресурсы (иконки, манифест, sw) сюда не попадают.
// Ключ — IP клиента (на этом этапе пользователь ещё не авторизован в БД).
if (isset($_GET['action']) && $_GET['action'] !== '') {
    $rlKey = 'ip:' . ($_SERVER['REMOTE_ADDR'] ?? 'unknown');
    if (!rl_check($rlKey)) {
        // Превышен лимит: 429 + Retry-After, выходим ДО обращения к БД.
        http_response_code(429);
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: no-store');
        header('Retry-After: 3');
        echo json_encode(['error' => 'rate_limited', 'retry_after' => 3]);
        exit;
    }
}

// ==== PWA: манифест и иконки приложения Payom (без входа) ====
$APP_NAME = 'Payom';
if (isset($_GET['apk'])) {
    $f = __DIR__ . '/payom.apk';
    if (file_exists($f)) {
        header('Content-Type: application/vnd.android.package-archive');
        header('Content-Disposition: attachment; filename="Payom.apk"');
        header('Content-Length: ' . filesize($f));
        header('Cache-Control: public, max-age=3600');
        readfile($f); exit;
    }
    http_response_code(404); header('Content-Type: text/plain; charset=utf-8'); echo 'APK ещё не загружен'; exit;
}
if (isset($_GET['sw'])) {
    header('Content-Type: application/javascript; charset=utf-8');
    header('Service-Worker-Allowed: /');
    header('Cache-Control: no-cache');
    echo <<<'JS'
const V='payom-cache-v1';
const SHELL=['mcall.js','messenger.php?micon=192'];
self.addEventListener('install', e=>{ self.skipWaiting(); e.waitUntil(caches.open(V).then(c=>c.addAll(SHELL).catch(()=>{}))); });
self.addEventListener('activate', e=>{ e.waitUntil((async()=>{ const ks=await caches.keys(); await Promise.all(ks.filter(k=>k!==V && k.indexOf('payom-')===0).map(k=>caches.delete(k))); await self.clients.claim(); })()); });
self.addEventListener('fetch', e=>{
    const req=e.request; if(req.method!=='GET') return;
    let url; try{ url=new URL(req.url); }catch(_){ return; }
    // API и загрузки — всегда из сети, не кэшируем
    if(url.origin===location.origin && (url.searchParams.has('action')||url.searchParams.has('sw')||url.pathname.indexOf('/uploads/')!==-1)) return;
    const isDoc = req.mode==='navigate' || (url.origin===location.origin && /messenger\.php$/.test(url.pathname) && !url.search);
    if(isDoc){
        // документ: сеть-сначала (правильный вход), кэш — только запас для оффлайна
        e.respondWith((async()=>{ try{ const net=await fetch(req); try{ const c=await caches.open(V); c.put('__doc__', net.clone()); }catch(_){}; return net; }catch(err){ const c=await caches.open(V); const f=await c.match('__doc__'); return f || new Response('<h3 style="font-family:sans-serif;text-align:center;margin-top:40px">Нет связи</h3>',{headers:{'Content-Type':'text/html'}}); } })());
        return;
    }
    // шрифты, mcall.js, иконки, картинки — из кэша сразу + фоновое обновление
    e.respondWith((async()=>{ const c=await caches.open(V); const cached=await c.match(req); const net=fetch(req).then(r=>{ if(r&&r.status===200&&(r.type==='basic'||r.type==='cors')){ try{c.put(req,r.clone());}catch(_){}} return r; }).catch(()=>null); return cached || (await net) || new Response('',{status:504}); })());
});
self.addEventListener('push', e=>{
    let d={}; try{ d=e.data.json(); }catch(_){ try{ d={title:'Payom', body:(e.data&&e.data.text())||''}; }catch(__){} }
    const t=d.title||'Payom';
    e.waitUntil(self.registration.showNotification(t,{ body:d.body||'', tag:d.tag||'qaz-msg', renotify:true, icon:'messenger.php?micon=192', badge:'messenger.php?micon=192', data:{url:d.url||'messenger.php'} }));
});
self.addEventListener('notificationclick', e=>{
    e.notification.close();
    const url=(e.notification.data&&e.notification.data.url)||'messenger.php';
    e.waitUntil((async()=>{ const all=await self.clients.matchAll({type:'window',includeUncontrolled:true}); for(const cl of all){ if(cl.url.indexOf('messenger.php')!==-1){ try{return cl.focus();}catch(_){}} } if(self.clients.openWindow) return self.clients.openWindow(url); })());
});
JS;
    exit;
}
if (isset($_GET['manifest'])) {
    header('Content-Type: application/manifest+json; charset=utf-8');
    echo json_encode([
        'name' => 'Payom — мессенджер',
        'short_name' => 'Payom',
        'id' => '/messenger.php',
        'start_url' => 'messenger.php',
        'scope' => './',
        'display' => 'standalone',
        'orientation' => 'portrait',
        'background_color' => '#141420',
        'theme_color' => '#1E1E2C',
        'icons' => [
            ['src' => 'messenger.php?micon=192', 'sizes' => '192x192', 'type' => 'image/png', 'purpose' => 'any'],
            ['src' => 'messenger.php?micon=512', 'sizes' => '512x512', 'type' => 'image/png', 'purpose' => 'any'],
            ['src' => 'messenger.php?micon=512', 'sizes' => '512x512', 'type' => 'image/png', 'purpose' => 'maskable'],
        ],
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}
/* Аватарка официального канала — вшита в файл, грузить никуда не надо */
if (isset($_GET['chicon'])) {
    header('Content-Type: image/jpeg');
    header('Cache-Control: public, max-age=31536000, immutable');
    echo base64_decode('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAQDAwMDAgQDAwMEBAQFBgoGBgUFBgwICQcKDgwPDg4MDQ0PERYTDxAVEQ0NExoTFRcYGRkZDxIbHRsYHRYYGRj/2wBDAQQEBAYFBgsGBgsYEA0QGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBj/wAARCAEAAQADASIAAhEBAxEB/8QAHQAAAQQDAQEAAAAAAAAAAAAAAwABAgQFBwgGCf/EAEsQAAEDAgMEBQcHCAkEAwAAAAEAAgMEEQUGIQcSMUETIlFhcQgUUoGRobIVIyUyQnOCJENEYnJ0ksEWJjNjZIOisbM0U1Thk8Lw/8QAHAEAAQUBAQEAAAAAAAAAAAAAAwABAgQFBgcI/8QANxEAAgEDAQUGAwcEAwEAAAAAAAECAwQRIQUSMUFxBlFhkaHREyIyFCMzgbHh8CRiwfEHQlJy/9oADAMBAAIRAxEAPwDgJJJThhlqKhkEET5ZZHBjGMbdziTYAAcSVYwIGtoZI2IZkzRDFiOKu+RMLf1myTsvNKO1kemh7XWHZdbF2a7IKHLUEOO5rgiqsYNnxUj7OjpOy44Ok9w5XOq2q6pfK4lziu72L2RdVKte6L/z7+3+jTtrDe+ap5HmsubLMgZYYx1NgkeIVTeNViHzzie0NPVb6gvcMmLWNaxrWNAsGtFgPAKgw9qsMOnFd5b2NC2ju0YKK8EbVKlGCxFYLzZ3nmjsnk9JUmHVWGWKJKKLKLrJ5O1HZUSekVTjVhh1QZRQWKLbZ5PSRWzyD7SqtICKCLIDigqLHnEnpKQqZLfWKrghTCG4ruHwHFTJ6RTmpeftIOlktO1R3USwF84k47yY1EnNyh7FFxCfdQsEnVMnpIZqJDzUHWUSpqKIsczyX4oTp3+kkUJxHBFjFEGRfNJfigOmfa+8puI5qvIdNEeMUDYKSd/pIDpn3vvKbxdAeAFZjFA2M6YkEPaHA6EEcV4rMezLIeZmPdV4JFR1Lv0qh+YfftIHVd6wV695VWTRRr2VC5juVoKS8UV6lOM1iSyc0Z02I5hy6ySvwV5xrDm3cTEy08Y/WZzHe2/gFq/gu4RO+J1wStY7R9lFBmeCbGsvRxUmMgF74RZsdV48mv8A1uB59q4LbfYz4cXWsdf7fb2fnyMa5sMfNT8jmxMi1FPPSVUlLUwvhmicWPjkG65rhoQRyKEvPmsPDMofiuhdi+QIsHwuLOuNQA11Q29BE8f2MZ/O29J3LsGvPTVWzLKbc4bQaWgqWk0MANTVntjbbq/iJDfWV1NUTh8u6wBrG9VrWiwAHAALtux+x1cVHeVVpHh17/y5ePQv2VHee+whldLJvOKPGdbFU2EX4qyw3Xp2MaG1AusVmMdW91SjPaVajcotB4lpissIVRjrcEdjtUNoKi4w96Mw68VUY5WGOQJIKmWWm/FGaqzXIrSUCSCJhwLG6kNUIPKmHaIbRNMJrayV+SYOSuokskrqDuKYuTXunSGyI8VFxCRdZDe7TRTSItjON9AhPFknO1Q3PuEWKINg3nVV33RXlAe5HigbYJ11XkOiM86qu/jxViKBSBP4XVaQ6I73WBVaQo8QUmVZeKrOe5j94FWJCqcx0RcZBSNZbXsjRY3hkmasKh+kaZl6qNg/t4wPrftNHtHgFz+uxo5SyTU6HtXNW0zK7Mr55mhpWbtDVDzmmA4NaTqz8JuPCy8w7abFjRkr6itHpLryf58/HqYt9RSfxIm0dh2FDDshV2OPbaXEKjomO/u49Pe4u9i2O19zqV57JtOKDZXl6laLXo2ykd7yXn4lmo3a3XZ7CtVb2FKCXJP83q/Vlu3W7BIvRlWWO4WVGN2qtMctbBciy9G+6sxu14qgx9uCsMf2KLQaLMg11kZj7lUmPJsrDXd6G4hky612qO06Ki12qO154IMok0y411uaM2RUmu1RQ9BlEImXA6+qk19lVElgnEgQ3AmpFwPuUi7VV2yaJzJ3qO6PvB9+5US9B6QWUd/VPuiyGLr80NztVB0iC6S6mokd4k46lCc8hIv70BzrlFjEg2Se9Aceqne7RBc7qo0YkGyLnILiLJ3PAQXv00R4xBtkJHaKq9x4Kb3EmyBI6zUdIFJgpHBVJHXKNIVVkNlJIEyu8kOWv9smFtxHZ/DijW3lw+cEutr0b+qffuFe9kOqwuaqfz7Z/jdIRfeo5CPFo3h7wszbVqrmxq0nzi/Nar1KteO9BoyeGsEeVMGjbwbQwgf/ABtVpp4KnRP/AKs4SB/4UP8AxtRmu14o1kvuIdENT4IutcLhWo3GyoMdqrMblawWIsuscrTHBUGHvVhkiZoMmXmPR2vVFj+1GY+6G4hEy+2RGY/VUWPR2PHJDlEmmXQ/VT31TEmvFEEiG4E1ItteLqW8Aqok0S3+xQcCSkXN+wS6S5VXpdEukUfhj7xaEiYvseKrGTVRMlyn3BbxZ6QFQc8KuZLc0N0tlJQG3g7pNVBzwgGS44oRktzRVAg2Fc+4QnPHahvk70EyCyLGANyJvk0QHyXWQwjAcezHV+a4BhFbiUvMU0ReG+LuA9ZC2rlvyas2YluTZkxKjwWE6uhj/KZreohg9pVO82rZ2K/qaij4c/Ja+hWq3EIfUzSbnDmfWgvddu9cEHge1dkZV2J7OsJma6mwo4zLGevXYm4TN3hxDI9GE99iB3rnbbxmCnxbbTiFHRNjZR4SxmGwsjaGtBZcvsB+u5w9SobL7R0tpXTt7eDwllt6eC014+OOhWp3iqz3Yo1tI7VVZHIj33VeRy6bBYbAylVK4B2DVreTqeQH+Ao8jtdVVrHfRVXr+jyfAUGuvu5dGBnwJ0Z/q5hI/wAFD/xtRWO1sq1K++XMK0/Qof8AjaiNdre6BZL7iHREIcC61ysxv1WPbIrEcugVvAaLMgx3IlWGOA5rHtkRmSacU26ETL4fqjRuVFj0Vsuqi4hEzINf3orZO9UWya8UVr9FFxJpl0P71MSaqk2SyI2TvUHAlku9IE/SaaFU+kTdKe1NuEt4uiS/FP0gA4qj03enMw7U3wxbxbMl+aiZO9UzP3qJn706picy26XTihmXvVeHpquqbS0sUs87zZsUTS97vBo1K2PlzYVtDzAWTVVBFgdKdelxJ26+3dE27vbZV7q7trOO9cTUV4v9Fz/IDUrxgsyeDXxmA0uiUFHiOL1wo8JoKqvqXaCGmidK72NGi6by55OeTcLDJseqazHZxqWPd0EF/wBhpuR4uW1cLwjCsDoBRYNhtJh9MPzVLE2Nvrtx9a5G+7c2tL5bWDm+96L39EZ1XacV9Cycu5c8nvPGMbk2NSUuA051Ind001vu2Gw9bgtuZb2A5BwQsmxCmqMdqW679e75u/dE2zfbdbTAWHxnMdHhDXQtInqv+0Do39o8vDiuRu+0207+W5Ge6nyjp68fUz6l7Vnzx0L18MwPCwxsdPRUkejIoWBjfBrW81i4KiszLKbB9LhTTY2Nnz91+ztt4a8sDhlLX5rxA1+IyPFEw2uOr0h9BnYO0/zXvIY2RRtiiY1jGANa1osAOwBY1aKoaN5n3937lTOTH5kxuiyjkPE8emayOmwyjkqNzgOo0kNHibD1r5wzYjUYhXTVtW8vqJ5HTSuPN7iXOPtJXWnlcZu+RNj1FluCTdqMdrGsc2/GCG0j/a7ox61xzSPJAXpfYCy+HazuXxm/Rfu2aNlHCbMnvHd4oUjkt+wQZHkr0A0cg5HKpVu+jKsX/MSfAUV77lVqs/R1X9xJ8BQa6+7l0BzegalP9XMK1/Q4f+MKTXoFO7+r2F/ucPwNS3lXsvwIdEQg9EW2u1VhruCpNd2ozXHkVcwFTLrXGyOx/aqLX8kZhT4CJl9siK14KoiSyI2TvTbpNMvtkIRWyXCoNk0RBKBzScSW8XBIe1EEunFY8za6FN0/em3B94yPTapjKO1Y81G6LkgDmSvUZW2fZ5zm5py9l2sqICbedyN6GAf5j7A+q6DWqUqEPiVZKMe9vC9RpVFFZbMKZe9R6c7wbxJNgOZ8F0RlfyWXncqM55j73UeFt9xleP8AZvrW6sr7NskZOa12AZepIJwNaqRvSzn/ADH3PssuQ2h242fb5jQzUl4aLzf+EynU2jTjpHU5Jyzsd2i5qDJaTApKCjfr53iR83ZbtDSN93qaty5Y8mTAqRrJs2Y1U4rKNTT0Y83hHcXavd/pW+iNe1NZcTf9tNoXXy02qcf7ePm9fLBn1L+rPhoYXAMp5byvTeb5ewShw5trF1PEA937T/rH1lZYjVEslu6rlqlWdSTnNtt83qU3Jt5YLd1ScWRROkle1jGi7nONgB2kqtimLUGDUfnFbLu3+pG3Vzz2Afz4LWOYM1VmLvIe7oaUHq07Tp4uPMq1aWVS4eVou8bJ6DH87Cz6XCHFreDqk6E/s9nisDl7Bp8xVrp5y9lBG752S9jK70Gn/c8vFY3L+C1WZsRc3efFQRH5+ccf2G/rH3DXsvtelp4KSkjpaWJsUMTd1kbeDR/+5rTuJ07KHwqP1c33fuMtQ8EcUMLIIY2xxsaGtYwWDQOQVlhQGqvi2LUmA5dr8cxB+5S0FNJVTO7GRtLj7gsTdcnhatjnDvlU5r/pH5QsuDwS79LgFKyiAabjpnfOSnx6zG/hWraTSMLF1eLVuYczYhmDEHF1XiNVJWTE+lI4uI9V7epZKA2avoTZFkrS1p0F/wBUl+fP1NmhDdikWydEKR+iTnFBebi91qNB2Qe7kqtU76Oqh/cSfCVN7rFVql30fVfcSfCUCuvkl0ByehYhcRl/C/3OH4AkHocbrYBhf7nF8DVEElV7L8GHREYvRFtrkZjwqTHHmjByupBEy4Hi+iK2SypB6mH6cU+CSZeEikH6cVTEosi07aiqq46WkglnqJDZkMLC97z2Bo1KfRLLJb2C2JrBP03YVtDKHk4bTM0blRX0EWXaN2vS4mbSkd0Let/FurfeUvJg2fYDuT46arMlW3U+dno4Ae6JvH8RcuZ2j2u2ZY5Tqb8u6Ovrw9QFS7pw55OSMCwHH80V/mWXcGrsUnvYtpIi8N/adwb6yFuvKnksZsxLcqM2YtS4JCdTT09qmfwJ0Y32uXV+H4bh+E0DKHC6GmoqVmjIKaJsbG+DWgBW1we0f+QLytmNpBU138X66ej6lOpfzf06Gt8qbDNm+UzHNBgbcSrGairxQiofftDSNxvqatjBoa0NaAA0WAHAeClZK11xV1e17ue/cTcn4vJSlOU3mTyMknslZVSIya3JSshzzQ01O+eolZFEwXc95sAO8p1roImAvMZizhSYQH0tHuVNaNCL3ZGf1jzPd7V53MmepavfosGc6GnOjqjg+Tw9Ee/wXhpajdablbtlslyxOt5e42S5iWKVFbVPqq2d0szuLnHh3DsHcgYJhNZmbGDS07jFTR2NRUWuIx2DtceQ9fAKnh2H1+ZMbbhuHjd+1NM4XbCz0j/IcytyYThVFguExYdQRlsTNS531pHc3OPMn/0tW8uY2kNyH1fp/OQy1D0FFS4bh0VDRRCKCIWa0e8k8yeJKtBQThczJtvLJBmnVaO8rTNwy75Pk2DwyhtVmCqZh7QDr0Q+clPhutDfxrd7e0rhjywc2/Lm3GjytBJvU+X6JrXtB084ntI/1hgiHtW52YsvtW0aafCPzP8ALh64C0Y700aRoQNCVmYyA1YmjbZgWSaerqvdqccI2I6Bi5AkckX6oUjhZEY7ZB5BVeocPk+p+5f8JTudqgVDx5hU/cv+EqrcfRLoClwLMLvoHDAf/Ei+AKDXdZQYfoLDdf0SL4AoNPW1QLP8GHRDR4FsOUw/kFWD9FIPsrqCJhzJutuSAO0le7ybsj2j573JMAyxVeZu/TqwebU9u0Pf9b8IK2/5KmX9mVbTVWMY6+hr81R1Jjp6Gr3XmniDQWyRxn6znEuu4A23bac+vo5YZdIpGutpYHUerkuB7Q9tKmz60ra3pfMucs4/Jc+uSpWunF7qRzLk7yQcNp9ypz1mSaueNTRYWDDF4GV3Wd6g1b9yvkXKGS6MU+V8vUOGttZ0kMfzj/2pDdzvWV6Cyey812jt2/2g/wCoqtru4LyWhSnWnP6mMnASsnWQDFZIBOkkIVkk6SYQySXJeMzRn2kwkvocMLKqtHVc7jHCe/tPcPWj0LepXluU1liM/jeP4dgNH0tbLeRw+bhZq+TwHZ3nRanx/M+IY/UXqHdHTtN2U7D1W957T3rCVmIVVdWvqqyd88zzdz3m58O4dyrPm3W3uursdlwofM9Zd/sRbDyThrOKp00FdjmMRYXhse/NJxJ+rG0cXOPID/1xKqjzvE8Shw7DYnT1Mzt1jBp4knkANSeS3HlfLNJlnCugjcJqqWzqmpt/aO7B2NHIes6lW7y5jaQzxk+C/wAsZalvL+BUWXcGZQUnXcTvTTuFnTP9I/yHIetZUdqiNdVL1rlJzlOTlJ5bJkhqnuo+CccUNiI1NXTYfh1RiFbII6WmifPM88GsY0ucfYCvldmDMVTm/PuM5qrSemxStlrCD9kPcS1vqbuj1LvDyo83HKvk24tTwy7lZjb2YTDY2O7Jd0pH+Wx4/EF8/KRvCy9L7B2WKdS5fN4XRcfV+hctY8WZqn0aFc39OKpQmzUYu04r02K0NDkFLxwQZH6Ji/RBe5RkM2Rc9AqHfkNTf/sv+EqROqFOR5lUfcv+EqrX+iXQhLgHjNsFw791i+AKIcFFjvobDh/hYvgChvaoNn+DDoho8Cy0py5AbIQVIuV1EsjOmdFK2WNxa9hu1zTYtPaDyK2DlXyitp+TjHCzHPlmij0FJi4M9h2NkuJG/wAR8FriW7gVjZ2OBKo31rSuIbtaCkvFEJxUuJ23kryz8o4iY6XNlNWZdqDoZXg1lLf9toD2DxafFdB5fz9gGZMKbiWD19HidG4aVWHTtnYPGxu3wOq+R1QClhGPY9ljFm4pl3GK7Cq1puKiimdE8+JadR3G4XAbR7IWtRuVD5X5r3/UqToLkfZOnr6Kp0hqY3H0SbH2FWbFfNjJflkZ7wUxUudMLosz0rdDUNtSVYHbvNG48+LR4rpjIHlRbNM4GKmoc2HBa59gMOx20BJ7GvJMbvU6/cuNvOztzb64yu/j+/mivKDjxOj0681T5oeGtNVShzHC7ZITo4dovoR4FZWmxvDKohsdS1rz9iTqn3rEnb1IcUQMgg1VVTUVJJVVc7IYYxvPkebABYvMGZsLy5Q9PWy70rh83Txm75PAch3nRaZzDmnE8yVvSVkm5TtN4qZh6jO/vPefcrljs2pcveeke/2GbwekzVtCqcSD6HBHPpqQ9V831ZJR3eiPf4Lw2/ohntuhveALhdfbWlOhHcprCBthXSixuqUks1TUx0lJE+eeVwZHHGLue48AEKpqnaRxtc97iGhrRcuJ4ADmVtPI+TxgVP8AKWIsDsUmbYg6+bNP2B+sftH1Dncl1cQtKe/LjyQ6WS9k7KcOW6Ayzbk2JTt+fmbqGjj0bO4czzPdZenGtrqItZTAXH1qsqs3Oby2ERLgnTcEroQiSkFBIvjjjdJNII4mgue8nRrQLk+oXKixHFHloZu+UtqGB5Mp5bw4PRmrnaOHTznS/eI2N/jXPFKLNCyOfc1SZ62t5izc8ktxKvkmhB+zCDuxD1MaxUqa26Lr3nYNj9ks6dFrVLXq9X6mpRjuxSL0Z0UnO7EIO00SL10HIPkcuIQ3vSc/RAc7VDkRZJz9eKFOfyKo+5f8JTFwQ5n2o6j7p/wlVa/0S6EGGY4jB8P/AHWL4AobyZp+hsP/AHWP4AhB2qBZ/hR6IaL0LDXIgdfiqzXKbXaq7EkmEcbqtM0FGJCG86JSjlDmMni7ljpobclm5GXubKlLFxNln1qKYNowEsRBOiqSR8QRoVmpor30WOmjtfRZFajgG0eoyVtk2l7OnNjytmqtp6Np1oJz09M7u6J9wPw2Peujck+W1h04jpNoeVZKR9gHYhgx6RhPa6F53gP2XHwXHsrO5VXt4jt0WDd2FGrrKOveV5wTPqzm+GL5So6mn60c9Ix4ff6w1sfYQvN7hUck4x/Sryadn2Y3SGWaTDI6aZ5P5yNvRu98RRX6BYdpn4ai+KyvJlKXEDIbaLH1dSImHUKzUy7jCV7LZ9k0VbmZkxeEOja69HA7UEj844d3Ies8laq14W1P4lT/AGJLJbyHkx9DuY/jEJFa8Xp4Hj+waftEemR/CO86bADe5ELde9NaxXIXNzO4m6k/9BEsDWUglZIquOOlzTX1SvbRMIldav8AKKze7Jvk25jroJejrK6IYVSkHXfnO4SPBnSH1LZwN1xx5bWbunx/LGQ6eUltLE/FqpgOm++8cQPg1sh/EFrbCs/td9SpvhnL6LX14fmTpx3pJHLVLGA0NaLADRZSE2asfTaWWQZwC94oRwjUiWN5QLlC9lHeN1YbHySc8ob3aJi431Q3OB0QmyLYi5Dmd+Rz/dP+EpE6IUrj5pP90/4Sqtf6JdCLehZ3vonDx/hY/gCETZLe+iqD92j+AKAddBtPwo9EJBWlS3kHeT72iuxY+QxdchIkIW8n3kQfInWVeRtwbIxKG7VCnHIihKzjosfNFe+iy8jbqnLHfkqFajkg0YWWLuVCZlrrNTRrHTxrDuaWAUkdzeSli/y15I9ThL3XkwLG5IwOyOUNkb73v9i2RMywN1zx5EeL3rdoGUHP/wCqw6HEYmfrQvLHW9UrfYuj6ttoyeS4/d3K9SHjnzSf6mdVWJGCkibU17IZCRCLulcOTALuPsBWAwbaZi+Sc/VNaGOqcHrZelq8PBsNdN+P0XgADsIFjyI9TBA44XW1ltJT5uzvaLOefgHtWscz08cfTTyPayKNpe97zYNaNSSTwACsuMKzdOayuA0e868wLHMIzPl+DG8DrGVdDOLskboQRxa4cWuHAg8FfLV8zMseVNjuzvaq2ryxEKzKm/uV2GzdXz8cDI0/m3j7B/iBBsPojkLP+Vdp2RqTNuT8RbWYfUdVzT1ZaeQDrRSs+w8cxz0IuCCuRv7GVrPTWL4P3/moQ9DZR0RCFAjVUUIYqPinSJCkIdjSXBoIBJsCV8wNsGbv6d7fcz5kjkL6WWtdT0mtwIIvmo7eIZvfiX0A215vORdgOaMxRSblUyjdTUhvY9PN81HbwL978K+Y9MzdY1oPAWv2rv8AsPZ5lUuX/wDK/V/4LNutcmRgFgrTXaAKpGexWA7qr1Knoi6mFLkMuN7qBfqol2ik2M2Sc6/NQJUS63FRJQWxsjuKHI78kn+6f8JSLtVCUjzSf7p/wlVq7+R9CLZYdphVB+7R/AEIHRSc4/JVB+7R/AEIHVBtX91HohJ6Bb96V1DeCa6uJj5DAp76oQOnFPcoqYshDYqBSuokpDkXNugSMu1HJ1UHC6HOIzMdNGFjahnFZmZmix88fFZV1RyiEja3kl4yMG8rHAaaR27Di0NThcmtr9JES0fxsau0MVBiic0NJI6obzJ4WXzmyZjT8rbUMu5kjcWnDcTpqskdjJWl3uuvqDUYSKvP0jYN2SGnldU2Gu8L3YPWS32LgtqJW9z8R8Gv0f7ooV46mAxKhbQ4PFRmw6CPdceADuLz7SfUFwht22tx5nxefK+V6i+DQPLairjP/WvB4N/uweHpHXhZbL8qPb5HiFXWbN8j1u9AwuhxfEoXaSuGjqeNw+yOD3DieqNL35PbCoWVGbjvy5ihDJX3L6lbG2N7Y82bFs8tx3L03T0U+6zEcKmcRDWxA8Hei8a7rxq09oJB8L0XcomLuV6dqpxcZrKYXdPsHs12mZU2sZDgzXlKsMtO89HUU0thPRy2uYpW8nDkeDhqCQvWO0K+Q2yvanmzZBn2HM2V6njaOsoJSegrYr3McgHucNWnUc7/AFD2WbVcp7X8hRZlyvUkObaOtw+Zw6ehlt9SQDiDruuGjhqOYHG7R2ZO0lvLWD9PBgmsHsybKHEp3DVJrS5waBck2CzUMcleW7m7osJyvkKnls6olfi1WwH7DLxRA/idKfwrkSEdULYXlDZwGdfKVzLiEEvSUVFMMLpDy6ODqEjxf0jvWtexnQL2ns3Z/ZrKnB8Wsvq9f2LtJYiWmFE3tOKCHKV7hdPENkmT3qG9bmmvpxUCUzY2SbnXCgSok2TFwQmxmx796hLrSzfdu+EpiUzz+TTfdu+EqvWfyMbkWHE/JVD+7x/AEG/apscH4Jh8g1DqaM/6QhX1QbV5pR6ISYQHtTod1IO0VyLHyTT35Ie+nBRELIS6a6jdNdTyLJJMeCjcpX1TNiyDkFwqcrL30V5wugPBJVarDKGZh6mIlrgNLgi66a2keVO2t2KYTl3IstZTZkr8Mp6fHMUcwxOptyERvihPNzyHEyDQNOnWPV5ymjvyVN8AvwXNbQ2ZCvOMprh/PYDOKfExYg1vZFbD3K6IO5EEPcmhaCSKIhTGG/JZHolAxdyM7bQfBi3w2XqNm+0fNmynPdPmnKdd0NQwbk9PJd0NXFe5ilb9pp9oNiCCFhXxdyA6I9ipV7SM4uMllMi4n1c2Q7X8rbZsjtxvL8nm9dAGsxHCpXgzUUh5H0mHXdeND3EEDL7SM2R5E2R5kza9wD8OoJJYQftTEbsQ9b3MXytyJnbNGzjO1LmnKWIvoq+DqnTejnjP1opG8HsdzB8RYgFb020eVJU7XdmVFk+hys7A43TR1WJSOqum6Z7NWsjs0WZvHe61zo0ciTyb7M1PtcFT1pt6+C5rx8AW5qaGiMj3F8ry+RxLnvOpc46k+s6q9FwVOEK41er0I4RbiFun3tEMlLeVvOB8ky6yjvXUL6pE6aKLY2SRKiSo3TcChNjZJbyi8/k033bvhKZRmduUNQ88BE8/6Sq9eWISb7hskMCn87yNh0o1McfQu8Wkj/ayPdedyBWiWircIees0+cRju4O/wDqV6JwsSLLK2DdK5saU1xSw+q0FCWYoQN0/BRBsn3ltpjj31UgdVC6fgURMWSV9U1ymJSv3qaFklftS5KG8nvcJ0xZEdVFwT6pHUKMlkfIF7AUF0QI71ZsolmqrTpZIlbo1PoxbgjFibdCgqKEgG5omMenBWCNNFAtSlSEVHR9yC+JXi3uUCwEqrOgmMURFqrMUdiNETotUZjAAmpW+GMgsTRZGCGzRSvotWCwieSdxZNy0ULpFynkbI99bJ72UL6pt7VQbGySJ1SJ5KJPNMShNjZHvdUsbqPN8r10hNiYiweLjb+auDivN51rOjoqfDmnrPd0r/AaD339iyNt3StrGrUfdhdXohpPCZ5fCcSlwnGYK+IXMbus30mnQj1hbWkdFUU0dZTO34Zmh7HDmCtOr1eUMxMoXnCsQfaklN45HcInHt/VPuPrXA9ltsKzquhVeIS9H7P2BUp4eGevJSvZTnidC/Xh2oN16nF5DsnvJw5DvrZOToiJjZJkpX0Q95PvKaYshLpj2KG8ldOmLJMHwSJ1UAU5KlkWSSSiCkSmwLIuaa6c8FEnRPgWSSiQkDole5UGkLIxGmqjYXUkgBdR3ELIt0JxZIpxZOoJCyTaRZIlDul61LgNklcJE2UL6Jr3KZsWSRKSgTYpXUGyLZLeTXuUykxpc6wUGIlvRwwvqJnhkUbS5zjyAWs8VxB+J4tNWPBAebMafstGgHsWazRjrao/JlG+8DD849p0kcOQ7h7yvMry/tVthXVRW1F5hHi+9+y9/AHOWdBApaJk91xyYM9Zl3NvmkLcOxbekpRpHNxdF3Htb7wvYGNkkLaimkZNC8Xa9huCtRq/hmM4jhMpdRVBa0m7o3dZjvEfz4rsNi9qalolRuVvQXB817r+eAWNTGjNjnQ6puKwdJnTD6kBuI0r6Z/OSLrs9nEe9ZeCtwqq1pcTpnk/ZL90+w2Xf2m2bO6SdKos93B+T1J5T4MNwCZF83e4dQhw7QbpeazW1aVqKSfAfAK9k5KJ5tMR9VP5tLzaVLIsMDe6e6L5tKB9UpjTyeiU+8LDB3SJRPN5fQKXm8tvqlPvCwwVykidBL6KRp5bfVKfIsMHcJX5BF82lt9Upeby+iU28LDB3TXIKJ0EvolP5vL6BTZFgHvJrovm8g+yVEwS+iUsjYYMnVJEFPJ6JS83l9Ept4WGDJTA80Q08nolN0L2jraDtOii2hsMgSlfVCnrsNpQTU4hTxkct8E+warDVmbqCAFtBA+pf6cnUb7OJ9yzLva9narNWol4cX5LUbRcT0HVZE6aZ7Y42i7nvNgB3leSx7NAqGOocLLmwHR8/B0ncOwe8rC4ji9fikgNXOSwG7Y29VjfAfzVFcDtntVUuk6Nst2D4vm/ZfzwIufJCSS1SuuObBn/2Q==');
    exit;
}
if (isset($_GET['micon'])) {
    $s = (int)$_GET['micon']; if ($s < 32) $s = 192; if ($s > 512) $s = 512;
    header('Content-Type: image/png');
    header('Cache-Control: public, max-age=604800');
    $im = imagecreatetruecolor($s, $s);
    imagealphablending($im, true); imagesavealpha($im, true);
    // фиолетовый градиент
    for ($y = 0; $y < $s; $y++) {
        $t = $y / $s;
        $r = (int)(0x7C + (0x5B - 0x7C) * $t);
        $g = (int)(0x5C + (0x3F - 0x5C) * $t);
        $b = (int)(0xFF + (0xE0 - 0xFF) * $t);
        $col = imagecolorallocate($im, $r, $g, $b);
        imagefilledrectangle($im, 0, $y, $s, $y + 1, $col);
    }
    // белый речевой пузырь (оригинальный значок, не самолётик)
    $w = imagecolorallocate($im, 255, 255, 255);
    $bx1 = $s * 0.23; $by1 = $s * 0.25; $bx2 = $s * 0.77; $by2 = $s * 0.58; $rad = (int)($s * 0.11);
    imagefilledrectangle($im, $bx1 + $rad, $by1, $bx2 - $rad, $by2, $w);
    imagefilledrectangle($im, $bx1, $by1 + $rad, $bx2, $by2 - $rad, $w);
    imagefilledellipse($im, $bx1 + $rad, $by1 + $rad, $rad * 2, $rad * 2, $w);
    imagefilledellipse($im, $bx2 - $rad, $by1 + $rad, $rad * 2, $rad * 2, $w);
    imagefilledellipse($im, $bx1 + $rad, $by2 - $rad, $rad * 2, $rad * 2, $w);
    imagefilledellipse($im, $bx2 - $rad, $by2 - $rad, $rad * 2, $rad * 2, $w);
    // хвостик пузыря
    imagefilledpolygon($im, [(int)($bx1 + $s * 0.09), (int)($by2 - 3), (int)($bx1 + $s * 0.22), (int)($by2 - 3), (int)($bx1 + $s * 0.11), (int)($by2 + $s * 0.11)], 3, $w);
    // три точки-акцента
    $dot = imagecolorallocate($im, 0x7C, 0x5C, 0xFF);
    $cyy = (int)(($by1 + $by2) / 2); $dr = (int)($s * 0.037);
    imagefilledellipse($im, (int)($s * 0.38), $cyy, $dr * 2, $dr * 2, $dot);
    imagefilledellipse($im, (int)($s * 0.50), $cyy, $dr * 2, $dr * 2, $dot);
    imagefilledellipse($im, (int)($s * 0.62), $cyy, $dr * 2, $dr * 2, $dot);
    imagepng($im); imagedestroy($im); exit;
}

// ==== Безопасность: заголовки и защищённые cookie ====
// Не показывать ошибки/пути наружу (пишем в лог, а не на экран)
@ini_set('display_errors', '0'); @ini_set('log_errors', '1'); error_reporting(E_ALL);
// Простое ограничение частоты (анти-перебор) по IP
function rate_ok($key, $max, $window) {
    $ip = $_SERVER['REMOTE_ADDR'] ?? '0';
    $f = sys_get_temp_dir() . '/pl_' . md5($key . '|' . $ip) . '.json';
    $now = time(); $arr = [];
    if (@file_exists($f)) { $arr = json_decode(@file_get_contents($f), true) ?: []; }
    $arr = array_values(array_filter($arr, function ($t) use ($now, $window) { return $t > $now - $window; }));
    if (count($arr) >= $max) return false;
    $arr[] = $now; @file_put_contents($f, json_encode($arr));
    return true;
}
$__https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') || (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https');
if (!headers_sent()) {
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: SAMEORIGIN');
    header('Referrer-Policy: strict-origin-when-cross-origin');
    header('Permissions-Policy: geolocation=(), interest-cohort=()');
    if ($__https) header('Strict-Transport-Security: max-age=31536000; includeSubDomains');
}
if (session_status() !== PHP_SESSION_ACTIVE) {
    session_set_cookie_params(['lifetime' => 0, 'path' => '/', 'httponly' => true, 'secure' => $__https, 'samesite' => 'Lax']);
}
/* Сжатие ответа — страница уходит в несколько раз меньше по размеру */
if (extension_loaded('zlib') && stripos($_SERVER['HTTP_ACCEPT_ENCODING'] ?? '', 'gzip') !== false) {
    if (!ini_get('zlib.output_compression')) {
        @ini_set('zlib.output_compression', 'On');
        @ini_set('zlib.output_compression_level', '5');
    }
    if (!ini_get('zlib.output_compression') && !ob_get_level()) @ob_start('ob_gzhandler');
}
session_start();
qaz_remember_login($pdo);

// Часовой пояс: Астана (UTC+5)
date_default_timezone_set('Asia/Almaty');
try { $pdo->exec("SET time_zone = '+05:00'"); } catch (\Throwable $e) {}

// --- Таблицы мессенджера ---
/* ==== СХЕМА БАЗЫ: выполняется ОДИН РАЗ ====
   Раньше эти проверки шли при каждом запросе — больше сотни обращений
   к базе на каждое обновление чата. Теперь после первого успешного
   прохода рядом создаётся файл-метка, и блок пропускается. Чтобы
   выполнить схему заново (после обновления кода) — удалите файл. */
$__schemaFlag = __DIR__ . '/.payom_schema_v5';
$__needSchema = !is_file($__schemaFlag);
if ($__needSchema) {
    /* Если папка сайта закрыта на запись, файл-метку создать нельзя —
       тогда держим отметку в самой базе, иначе схема гонялась бы
       при каждом запросе и тормозила всё приложение. */
    try {
        $pdo->exec("CREATE TABLE IF NOT EXISTS msg_meta (k VARCHAR(40) PRIMARY KEY, v VARCHAR(40)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
        $__mv = $pdo->query("SELECT v FROM msg_meta WHERE k = 'schema'")->fetchColumn();
        if ($__mv === 'v5') $__needSchema = false;
    } catch (\Throwable $e) {}
}
if ($__needSchema) {
try {
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_chats (
        id INT PRIMARY KEY AUTO_INCREMENT,
        type VARCHAR(10) DEFAULT 'private',
        name VARCHAR(120) NULL,
        created_by INT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_members (
        id INT PRIMARY KEY AUTO_INCREMENT,
        chat_id INT NOT NULL,
        user_id INT NOT NULL,
        last_read_id INT DEFAULT 0,
        UNIQUE KEY uniq_cm (chat_id, user_id),
        INDEX(chat_id), INDEX(user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_messages (
        id INT PRIMARY KEY AUTO_INCREMENT,
        chat_id INT NOT NULL,
        sender_id INT NOT NULL,
        text TEXT NULL,
        type VARCHAR(10) DEFAULT 'text',
        file VARCHAR(255) NULL,
        filename VARCHAR(255) NULL,
        reply_to INT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX(chat_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
} catch (PDOException $e) { /* тихо */ }

// миграции для старых установок
qaz_ensure_column($pdo, 'qaz_users', 'last_seen', "last_seen TIMESTAMP NULL");
qaz_ensure_column($pdo, 'qaz_users', 'avatar', "avatar VARCHAR(255) NULL");
qaz_ensure_column($pdo, 'qaz_users', 'username', "username VARCHAR(40) NULL");
qaz_ensure_column($pdo, 'qaz_users', 'bio', "bio VARCHAR(300) NULL");
qaz_ensure_column($pdo, 'qaz_users', 'birthday', "birthday DATE NULL");
qaz_ensure_column($pdo, 'qaz_users', 'priv_lastseen', "priv_lastseen VARCHAR(10) DEFAULT 'all'");
qaz_ensure_column($pdo, 'qaz_users', 'priv_calls', "priv_calls VARCHAR(10) DEFAULT 'all'");
qaz_ensure_column($pdo, 'qaz_users', 'priv_phone', "priv_phone VARCHAR(10) DEFAULT 'all'");
qaz_ensure_column($pdo, 'qaz_users', 'tg_chat_id', "tg_chat_id VARCHAR(32) NULL");
qaz_ensure_column($pdo, 'qaz_users', 'face_descriptor', "face_descriptor MEDIUMTEXT NULL");
qaz_ensure_column($pdo, 'qaz_users', 'deleted', "deleted TINYINT DEFAULT 0");
qaz_ensure_column($pdo, 'qaz_users', 'pubkey', "pubkey TEXT NULL");
qaz_ensure_column($pdo, 'msg_messages', 'enc', "enc TINYINT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_messages', 'played', "played TINYINT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_chats', 'auto_delete', "auto_delete INT DEFAULT 0");
try {
    $pdo->exec("CREATE TABLE IF NOT EXISTS tg_verify (
        id INT PRIMARY KEY AUTO_INCREMENT,
        token VARCHAR(40) NOT NULL,
        phone VARCHAR(20) NULL,
        verified_phone VARCHAR(20) NULL,
        chat_id VARCHAR(32) NULL,
        tg_name VARCHAR(120) NULL,
        status VARCHAR(10) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_tok (token), INDEX(chat_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
} catch (PDOException $e) {}
try {
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_blocks (
        id INT PRIMARY KEY AUTO_INCREMENT, blocker_id INT NOT NULL, blocked_id INT NOT NULL,
        UNIQUE KEY uniq_b (blocker_id, blocked_id), INDEX(blocker_id), INDEX(blocked_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
} catch (PDOException $e) {}
qaz_ensure_column($pdo, 'msg_messages', 'type', "type VARCHAR(10) DEFAULT 'text'");
qaz_ensure_column($pdo, 'msg_messages', 'file', "file VARCHAR(255) NULL");
qaz_ensure_column($pdo, 'msg_messages', 'filename', "filename VARCHAR(255) NULL");
qaz_ensure_column($pdo, 'msg_messages', 'edited', "edited TINYINT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_messages', 'deleted', "deleted TINYINT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_messages', 'dur', "dur INT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_messages', 'once', "once TINYINT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_messages', 'viewed', "viewed TINYINT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_chats', 'pinned_msg', "pinned_msg INT NULL");
qaz_ensure_column($pdo, 'msg_chats', 'avatar', "avatar VARCHAR(255) NULL");
qaz_ensure_column($pdo, 'msg_chats', 'about', "about VARCHAR(300) NULL");
qaz_ensure_column($pdo, 'msg_members', 'is_admin', "is_admin TINYINT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_members', 'muted', "muted TINYINT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_members', 'pinned', "pinned TINYINT DEFAULT 0");
/* Индексы ускорения — создаются один раз, потом пропускаются */
try {
    $__idxDone = false;
    $__db = $pdo->query("SELECT DATABASE()")->fetchColumn();
    $__chk = $pdo->prepare("SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=? AND TABLE_NAME='msg_messages' AND INDEX_NAME='idx_chat_id_id'");
    $__chk->execute([$__db]);
    if (!$__chk->fetchColumn()) {
        foreach ([
            "ALTER TABLE msg_messages ADD INDEX idx_chat_id_id (chat_id, id)",
            "ALTER TABLE msg_messages ADD INDEX idx_chat_sender (chat_id, sender_id, id)",
            "ALTER TABLE msg_members  ADD INDEX idx_user_chat (user_id, chat_id)",
            "ALTER TABLE msg_reactions ADD INDEX idx_rx_msg (message_id, user_id)",
            "ALTER TABLE msg_typing   ADD INDEX idx_tp (chat_id, updated_at)",
            "ALTER TABLE qaz_users    ADD INDEX idx_uname (name)",
        ] as $__q) { try { $pdo->exec($__q); } catch (\Throwable $e) {} }
    }
} catch (\Throwable $e) {}
/* PAYOM-CHANNELS: таблицы каналов */
try {
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_channels(
        id INT PRIMARY KEY AUTO_INCREMENT, owner_id INT NOT NULL, title VARCHAR(120) NOT NULL,
        username VARCHAR(40) NULL, about VARCHAR(300) NULL, avatar VARCHAR(255) NULL,
        is_public TINYINT DEFAULT 1, invite_code VARCHAR(32) NULL, subs_count INT DEFAULT 0,
        pinned_post INT NULL, is_official TINYINT DEFAULT 0, comments_on TINYINT DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_chun (username), UNIQUE KEY uq_chcode (invite_code),
        INDEX idx_chowner (owner_id), INDEX idx_chpub (is_public, subs_count)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_channel_subs(
        channel_id INT NOT NULL, user_id INT NOT NULL, role VARCHAR(10) DEFAULT 'sub',
        muted TINYINT DEFAULT 0, last_read_id INT DEFAULT 0,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_cs (channel_id, user_id), INDEX idx_csu (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_channel_posts(
        id INT PRIMARY KEY AUTO_INCREMENT, channel_id INT NOT NULL, author_id INT NOT NULL,
        text TEXT NULL, type VARCHAR(10) DEFAULT 'text', file VARCHAR(255) NULL,
        filename VARCHAR(255) NULL, dur INT DEFAULT 0, views INT DEFAULT 0,
        pinned TINYINT DEFAULT 0, deleted TINYINT DEFAULT 0, scheduled_at DATETIME NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_chp (channel_id, id), INDEX idx_chsch (scheduled_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_channel_reacts(
        post_id INT NOT NULL, user_id INT NOT NULL, emoji VARCHAR(16) NOT NULL,
        UNIQUE KEY uq_chr (post_id, user_id), INDEX idx_chrp (post_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_channel_views(
        post_id INT NOT NULL, user_id INT NOT NULL,
        UNIQUE KEY uq_chv (post_id, user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
} catch (\Throwable $e) {}
/* колонки каналов — уже после создания таблиц */
qaz_ensure_column($pdo, 'msg_channels', 'is_official', "is_official TINYINT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_channels', 'comments_on', "comments_on TINYINT DEFAULT 1");


    qaz_ensure_column($pdo, 'msg_members', 'archived', "archived TINYINT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_chats', 'invite_code', "invite_code VARCHAR(32) NULL");
qaz_ensure_column($pdo, 'msg_messages', 'fwd_from', "fwd_from INT DEFAULT 0");
qaz_ensure_column($pdo, 'msg_messages', 'fwd_name', "fwd_name VARCHAR(120) NULL");
try { $pdo->exec("ALTER TABLE msg_chats ADD UNIQUE INDEX uq_invite (invite_code)"); } catch (\Throwable $e) {}
try {
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_reactions (
        id INT PRIMARY KEY AUTO_INCREMENT, message_id INT NOT NULL, user_id INT NOT NULL, emoji VARCHAR(16) NOT NULL,
        UNIQUE KEY uniq_r (message_id, user_id), INDEX(message_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_typing (
        chat_id INT NOT NULL, user_id INT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_t (chat_id, user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_sticker_packs (
        id INT PRIMARY KEY AUTO_INCREMENT, owner_id INT NOT NULL, title VARCHAR(80) NOT NULL, slug VARCHAR(60) NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, INDEX(owner_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_stickers (
        id INT PRIMARY KEY AUTO_INCREMENT, pack_id INT NOT NULL, file VARCHAR(255) NOT NULL, mtype VARCHAR(10) DEFAULT 'image',
        ord INT DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, INDEX(pack_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_user_packs (
        user_id INT NOT NULL, pack_id INT NOT NULL, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_up (user_id, pack_id), INDEX(user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_stories (
        id INT PRIMARY KEY AUTO_INCREMENT, user_id INT NOT NULL, type VARCHAR(10) DEFAULT 'image',
        file VARCHAR(255), text VARCHAR(300), audience VARCHAR(10) DEFAULT 'all',
        expires_at DATETIME, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX(user_id), INDEX(expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_story_views (
        story_id INT NOT NULL, user_id INT NOT NULL, reaction VARCHAR(16) NULL,
        viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_sv (story_id, user_id), INDEX(story_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_story_audience (
        story_id INT NOT NULL, user_id INT NOT NULL,
        UNIQUE KEY uniq_sa (story_id, user_id), INDEX(story_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_contacts (
        id INT PRIMARY KEY AUTO_INCREMENT, owner_id INT NOT NULL, user_id INT NOT NULL,
        name VARCHAR(120), note VARCHAR(300), share_number TINYINT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_ct (owner_id, user_id), INDEX(owner_id), INDEX(user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    // синяя галочка (верификация)
    qaz_ensure_column($pdo, 'qaz_users', 'verified', "verified TINYINT DEFAULT 0");
    // ссылка на историю в сообщении-ответе
    qaz_ensure_column($pdo, 'msg_messages', 'story_ref', "story_ref INT DEFAULT 0");
    // опрос в истории (JSON: {q, options:[...]})
    qaz_ensure_column($pdo, 'msg_stories', 'poll', "poll TEXT NULL");
    // голоса в опросах историй
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_story_poll (
        story_id INT NOT NULL, user_id INT NOT NULL, choice INT NOT NULL,
        voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_sp (story_id, user_id), INDEX(story_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    // активные сеансы (устройства)
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_sessions (
        id INT PRIMARY KEY AUTO_INCREMENT, user_id INT NOT NULL, device_id VARCHAR(64) NOT NULL,
        ua VARCHAR(400), ip VARCHAR(64), last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT '1970-01-01 00:00:01',
        UNIQUE KEY uniq_sess (user_id, device_id), INDEX(user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
} catch (PDOException $e) { /* тихо */ }

    qaz_ensure_column($pdo, 'msg_channels', 'comments_on', "comments_on TINYINT DEFAULT 1");
try {
    $pdo->exec("CREATE TABLE IF NOT EXISTS msg_channel_comments(
        id INT PRIMARY KEY AUTO_INCREMENT, post_id INT NOT NULL, channel_id INT NOT NULL,
        user_id INT NOT NULL, text TEXT NOT NULL, deleted TINYINT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_post (post_id, id), INDEX idx_ch (channel_id, id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
} catch (\Throwable $e) {}
    @file_put_contents($__schemaFlag, date('Y-m-d H:i:s'));
    try { $pdo->prepare("INSERT INTO msg_meta (k,v) VALUES ('schema','v5')
                          ON DUPLICATE KEY UPDATE v='v5'")->execute(); } catch (\Throwable $e) {}
}

function mphone($p) {
    $p = preg_replace('/[^0-9+]/', '', $p);
    if (strlen($p) == 11 && $p[0] == '8') $p = '+7' . substr($p, 1);
    if (strlen($p) == 11 && $p[0] == '7') $p = '+' . $p;
    if (strlen($p) == 9 && $p[0] == '9' && strpos($p, '+') === false) $p = '+992' . $p;
    return $p;
}

// ==== Модуль сканера лица (общий: экран входа и приложение) ====
function face_module() {
    return <<<'FACE'
<style>
.face-ov{display:none;position:fixed;inset:0;z-index:400;background:#0b0f14;flex-direction:column;align-items:center;justify-content:center;gap:18px;padding:24px}
.face-cam{position:relative;width:min(78vw,320px);height:min(78vw,320px);border-radius:50%;overflow:hidden;background:#000}
.face-cam video{width:100%;height:100%;object-fit:cover;transform:scaleX(-1)}
.face-frame{position:absolute;inset:0;border-radius:50%;box-shadow:0 0 0 4px rgba(255,255,255,.25),0 0 0 2000px rgba(11,15,20,.72);border:0 solid transparent;transition:box-shadow .2s}
.face-frame.ok{box-shadow:0 0 0 6px #2ED66A,0 0 0 2000px rgba(11,15,20,.72)}
.face-dots{display:flex;gap:8px}
.fdot{width:26px;height:5px;border-radius:3px;background:rgba(255,255,255,.2);transition:background .2s}
.fdot.cur{background:#7C5CFF}
.fdot.done{background:#2ED66A}
.face-msg{color:#fff;font-size:19px;font-weight:800;text-align:center;min-height:26px;padding:0 10px}
.face-sub{color:rgba(255,255,255,.6);font-size:13px;font-weight:600;text-align:center;min-height:18px}
.face-close{background:rgba(255,255,255,.12);color:#fff;border:none;border-radius:14px;padding:13px 30px;font-weight:800;font-size:15px;cursor:pointer;font-family:inherit}
</style>
<div id="faceOv" class="face-ov">
    <div class="face-cam"><video id="faceVid" playsinline muted></video><div id="faceFrame" class="face-frame"></div></div>
    <div id="faceDots" class="face-dots"></div>
    <div id="faceMsg" class="face-msg">Загрузка…</div>
    <div id="faceSub" class="face-sub"></div>
    <button class="face-close" onclick="closeFace()">Отмена</button>
</div>
<script>
(function(){
  let faceReady=false,faceStream=null,faceRAF=null,faceState='idle',faceMode='login',faceBusy=false,capturedDesc=null,faceErr='',grabFails=0,hasExpr=true;
  let chSeq=[],chIdx=0,alignFrames=0,challengeStart=0,lastDet=0,grabDescs=[];
  function avgDesc(list){ const n=list.length,L=list[0].length,out=new Array(L).fill(0); for(const d of list)for(let i=0;i<L;i++)out[i]+=d[i]; for(let i=0;i<L;i++)out[i]/=n; return out; }
  // Источники библиотеки и моделей: основной CDN + запасной.
  // Если один CDN недоступен (медленный интернет/блокировки в регионе) —
  // автоматически пробуем второй. Это главная причина, почему вход по лицу
  // раньше «висел на загрузке».
  const LIB_SOURCES=[
    'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/dist/face-api.js',
    'https://unpkg.com/@vladmandic/face-api/dist/face-api.js'
  ];
  const MODEL_SOURCES=[
    'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model',
    'https://unpkg.com/@vladmandic/face-api/model'
  ];
  // Загрузка внешнего скрипта с ТАЙМАУТОМ — чтобы не «висло» вечно на плохой сети.
  function ls(src){return new Promise((res,rej)=>{const s=document.createElement('script');let done=false;
    const to=setTimeout(()=>{if(!done){done=true;try{s.remove();}catch(e){}rej(new Error('таймаут загрузки'));}},15000);
    s.src=src;s.onload=()=>{if(!done){done=true;clearTimeout(to);res();}};
    s.onerror=()=>{if(!done){done=true;clearTimeout(to);rej(new Error('ошибка загрузки'));}};
    document.head.appendChild(s);});}
  // Пробуем загрузить библиотеку по очереди со всех источников.
  async function loadLib(){ if(window.faceapi)return; let last;
    for(const url of LIB_SOURCES){ try{ await ls(url); if(window.faceapi)return; }catch(e){ last=e; } }
    throw last||new Error('библиотека не загрузилась'); }
  // Пробуем загрузить модель по очереди со всех источников.
  async function loadNet(net){ let last;
    for(const base of MODEL_SOURCES){ try{ await net.loadFromUri(base); return; }catch(e){ last=e; } }
    throw last||new Error('модель не загрузилась'); }
  function fmsg(t){const e=document.getElementById('faceMsg');if(e)e.textContent=t;}
  function fsub(t){const e=document.getElementById('faceSub');if(e)e.textContent=t||'';}
  function frame(c){const e=document.getElementById('faceFrame');if(e)e.className='face-frame'+(c?' '+c:'');}
  function dots(){const d=document.getElementById('faceDots');if(!d)return;d.innerHTML=chSeq.map((c,i)=>'<span class="fdot '+(i<chIdx?'done':(i===chIdx?'cur':''))+'"></span>').join('');}
  async function ensureFace(){ if(faceReady)return true;
    try{
      fmsg('Загрузка библиотеки…'); await loadLib();
      if(faceapi.tf){ try{await faceapi.tf.setBackend('webgl');}catch(e){} try{await faceapi.tf.ready();}catch(e){} }
      // Три модели обязательны (детектор, точки лица, распознавание).
      fmsg('Загрузка модели 1/4…'); await loadNet(faceapi.nets.tinyFaceDetector);
      fmsg('Загрузка модели 2/4…'); await loadNet(faceapi.nets.faceLandmark68Net);
      fmsg('Загрузка модели 3/4…'); await loadNet(faceapi.nets.faceRecognitionNet);
      // Четвёртая (эмоции) — НЕобязательная: нужна только для проверки «улыбнитесь».
      // Если не загрузилась — вход всё равно работает через «моргните».
      fmsg('Загрузка модели 4/4…'); try{ await loadNet(faceapi.nets.faceExpressionNet); hasExpr=true; }catch(e){ hasExpr=false; }
      faceReady=true;return true;
    }catch(e){ faceErr=(e&&e.message)?e.message:String(e); return false; } }
  function pickCh(){ const a=[{k:'blink',t:'Моргните'}]; if(hasExpr)a.push({k:'smile',t:'Улыбнитесь'}); return [a[Math.floor(Math.random()*a.length)]]; }
  window.openFace=async function(mode){ faceMode=mode||'login'; faceErr=''; grabFails=0; capturedDesc=null;
    document.getElementById('faceOv').style.display='flex'; frame(''); fsub(''); fmsg('Загрузка…');
    const ok=await ensureFace(); if(!ok){fmsg('Ошибка загрузки сканера');fsub(faceErr||'Проверьте интернет');return;}
    try{ faceStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:480},height:{ideal:480}}}); }
    catch(e){ fmsg('Нет доступа к камере'); fsub('Разрешите камеру в настройках браузера'); return; }
    const v=document.getElementById('faceVid'); v.srcObject=faceStream; v.muted=true; v.setAttribute('playsinline','');
    try{await v.play();}catch(e){}
    fmsg('Запуск камеры…'); let tries=0; while((!v.videoWidth||v.videoWidth<10)&&tries<50){ await new Promise(r=>setTimeout(r,60)); tries++; }
    if(!v.videoWidth){ fmsg('Камера не запустилась'); fsub('Обновите страницу'); return; }
    chSeq=pickCh(); chIdx=0; alignFrames=0; grabDescs=[]; faceState='align'; dots();
    fmsg('Поместите лицо в овал'); fsub('Смотрите прямо в камеру'); loopFace(); };
  window.closeFace=function(){ faceState='idle'; if(faceRAF)cancelAnimationFrame(faceRAF); faceRAF=null;
    if(faceStream){faceStream.getTracks().forEach(t=>t.stop());faceStream=null;}
    const v=document.getElementById('faceVid'); if(v)v.srcObject=null;
    document.getElementById('faceOv').style.display='none'; };
  function d2(a,b){return Math.hypot(a.x-b.x,a.y-b.y);}
  function ear(p){return (d2(p[1],p[5])+d2(p[2],p[4]))/(2*d2(p[0],p[3])+.0001);}
  function fEAR(lm){return (ear(lm.getLeftEye())+ear(lm.getRightEye()))/2;}
  function fYaw(lm){const j=lm.getJawOutline(),n=lm.getNose();const tip=n[n.length-1];const ld=Math.abs(tip.x-j[0].x),rd=Math.abs(j[16].x-tip.x);return ld/(rd||1);}
  async function loopFace(){ if(faceState==='idle')return; faceRAF=requestAnimationFrame(loopFace);
    const now=performance.now(); if(faceBusy||now-lastDet<150)return; lastDet=now; faceBusy=true;
    const v=document.getElementById('faceVid');
    try{
      if(faceState==='align'){
        const det=await faceapi.detectSingleFace(v,new faceapi.TinyFaceDetectorOptions({inputSize:160,scoreThreshold:0.4}));
        if(!det){ fmsg('Лицо не видно'); frame(''); alignFrames=0; faceBusy=false; return; }
        const b=det.box,vw=v.videoWidth||480,vh=v.videoHeight||480;
        const cx=b.x+b.width/2,cy=b.y+b.height/2;
        const centered=Math.abs(cx-vw/2)<vw*0.27&&Math.abs(cy-vh/2)<vh*0.27;
        const sized=b.width>vw*0.30&&b.width<vw*0.96;
        if(centered&&sized){ frame('ok'); fmsg('Отлично, держите');
          let g=null; try{ g=await faceapi.detectSingleFace(v,new faceapi.TinyFaceDetectorOptions({inputSize:224,scoreThreshold:0.4})).withFaceLandmarks().withFaceDescriptor(); }catch(e){ faceErr=e.message||String(e); }
          if(g&&g.descriptor&&g.descriptor.length>=100){ grabDescs.push(Array.from(g.descriptor)); grabFails=0; fsub('Снимаем лицо… '+grabDescs.length+'/5');
            if(grabDescs.length>=5){ capturedDesc=avgDesc(grabDescs); grabDescs=[]; faceState='challenge'; showCh(); }
          } else { grabFails++; if(grabFails>18){ fmsg('Не получается снять лицо'); fsub(faceErr?('Ошибка: '+faceErr):'Больше света, лицо ближе, не двигайтесь'); } }
        } else { grabFails=0; grabDescs=[]; frame(''); fmsg(!sized?(b.width<=vw*0.30?'Придвиньтесь ближе':'Отодвиньтесь немного'):'Лицо в центр овала'); fsub(''); }
      } else if(faceState==='challenge'){
        // Эмоции запрашиваем только если 4-я модель загружена (иначе упадёт).
        let _q=faceapi.detectSingleFace(v,new faceapi.TinyFaceDetectorOptions({inputSize:160,scoreThreshold:0.4})).withFaceLandmarks();
        if(hasExpr) _q=_q.withFaceExpressions();
        const det=await _q;
        if(det){ const ch=chSeq[chIdx]; let ok=false;
          if(ch.k==='smile') ok=det.expressions&&det.expressions.happy>0.5;
          else ok=fEAR(det.landmarks)<0.22;
          if(ok){ faceState='idle'; if(faceRAF)cancelAnimationFrame(faceRAF); submitFace(); }
          else if(performance.now()-challengeStart>12000){ fmsg('Ещё раз'); faceState='align'; alignFrames=0; capturedDesc=null; chSeq=pickCh(); }
        }
      }
    }catch(e){}
    faceBusy=false; }
  function showCh(){ challengeStart=performance.now(); fmsg(chSeq[chIdx].t); fsub('Подтвердите, что вы живой'); dots(); }
  async function submitFace(){ const desc=capturedDesc;
    if(!desc){ faceState='align'; alignFrames=0; chSeq=pickCh(); loopFace(); return; }
    if(faceMode==='enroll'){ fmsg('Сохранение…'); frame('ok'); fsub('');
      const r=await fetch('messenger.php?action=face_enroll',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({descriptor:desc})}).then(x=>x.json()).catch(e=>({error:'network'}));
      if(r&&r.ok){ fmsg('Лицо сохранено ✓'); fsub('Готово, образцов: '+r.samples); setTimeout(()=>{closeFace(); if(window.afterFaceEnroll)window.afterFaceEnroll();},1100); }
      else{ fmsg('Ошибка сохранения'); fsub('Сервер: '+((r&&r.error)||'нет ответа')); setTimeout(()=>{faceState='align';alignFrames=0;capturedDesc=null;chSeq=pickCh();loopFace();},2600); }
      return;
    }
    // умный вход: есть лицо в базе → сразу входим; нет → просим номер
    fmsg('Проверка лица…'); frame('ok'); fsub('');
    const r=await fetch('messenger.php?action=face_login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({descriptor:desc})}).then(x=>x.json()).catch(e=>({error:'network'}));
    if(r&&r.ok){ fmsg('Добро пожаловать'); setTimeout(()=>{location.href='messenger.php';},600); }
    else if(r&&r.error==='nomatch'){ window.pendingFaceDesc=desc; fmsg('Лицо новое'); fsub('Подтвердите номер — и лицо сохранится'); setTimeout(()=>{ closeFace(); if(window.afterFaceNeedsPhone)window.afterFaceNeedsPhone(); },1400); }
    else{ fmsg('Ошибка'); fsub('Сервер: '+((r&&r.error)||'нет ответа')); setTimeout(()=>{faceState='align';alignFrames=0;capturedDesc=null;chSeq=pickCh();fmsg('Попробуйте снова');loopFace();},2600); }
  }
})();
</script>
FACE;
}

// ============================================
// Вход через Telegram-бота (доступно без входа)
// ============================================
$preAction = $_GET['action'] ?? '';
if ($preAction === 'tg_start' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/json');
    if (!rate_ok('tgstart', 8, 60)) { echo json_encode(['error' => 'Слишком много попыток, подождите минуту']); exit; }
    $phone = mphone($_POST['phone'] ?? '');
    if (strlen($phone) < 10) { echo json_encode(['error' => 'Введите правильный номер']); exit; }
    $token = bin2hex(random_bytes(16));
    $pdo->prepare("INSERT INTO tg_verify (token, phone, status) VALUES (?,?,'pending')")->execute([$token, $phone]);
    // уже привязан к Telegram?
    $u = $pdo->prepare("SELECT id, tg_chat_id FROM qaz_users WHERE phone = ? AND tg_chat_id IS NOT NULL AND tg_chat_id <> ''");
    $u->execute([$phone]); $row = $u->fetch();
    if ($row) {
        // отправляем кнопку подтверждения в бот
        $pdo->prepare("UPDATE tg_verify SET chat_id = ? WHERE token = ?")->execute([$row['tg_chat_id'], $token]);
        tg_api('sendMessage', [
            'chat_id' => $row['tg_chat_id'],
            'text' => "Вход в Payom\nНомер: $phone\n\nЭто вы хотите войти?",
            'reply_markup' => json_encode(['inline_keyboard' => [[['text' => '✅ Да, это я — войти', 'callback_data' => 'ok:' . $token]], [['text' => '❌ Это не я', 'callback_data' => 'no:' . $token]]]])
        ]);
        echo json_encode(['token' => $token, 'mode' => 'confirm']); exit;
    } else {
        echo json_encode(['token' => $token, 'mode' => 'link', 'bot' => 'https://t.me/' . TG_BOT_USERNAME . '?start=' . $token]); exit;
    }
}

// Вход по лицу (без входа) — сравнение отпечатка со всеми аккаунтами
// ==== Шифрование чувствительных данных «в покое» (защита от утечки БД) ====
// Ключ лежит в коде (не в базе) — при утечке ТОЛЬКО базы биометрию не прочитать.
// ВАЖНО: замените строку ниже на свой длинный случайный секрет (32+ символов).
/* Ключ шифрования сообщений в базе.
   ВАЖНО: APP_ENC_KEY_OLD нужен, чтобы читались сообщения,
   зашифрованные прежним ключом. Удалять его нельзя. */
if (!defined('APP_ENC_KEY')) define('APP_ENC_KEY', 'payom_Pkhe5Bp9qi6efW5BUM2DoaOaVmTLgLGs0bkNuHUJMQ4wzzKh1UPkNOWa');

/* ==== МГНОВЕННАЯ ДОСТАВКА (сервер реального времени на VPS) ====
   Если WS_URL пуст — приложение работает по-старому, опросом.
   Значения выдаёт install-vps.sh при установке. */
if (!defined('WS_URL'))    define('WS_URL',    '');   // например wss://ws.example.com/ws
if (!defined('WS_SECRET')) define('WS_SECRET', '');

/* Отправляет событие в комнату чата. Не задерживает ответ пользователю:
   таймаут короткий, любые сбои молча игнорируются. */
function ws_publish($chatId, array $payload, $type = 'message') {
    if (WS_URL === '' || WS_SECRET === '') return;
    $base = preg_replace('~^wss?://~', 'https://', WS_URL);
    $base = preg_replace('~/ws$~', '', $base);
    $body = json_encode(['chat_id' => (int)$chatId, 'type' => $type, 'payload' => $payload],
                        JSON_UNESCAPED_UNICODE);
    $ch = curl_init($base . '/internal/publish');
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $body,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 2,
        CURLOPT_CONNECTTIMEOUT => 1,
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json', 'X-Payom-Secret: ' . WS_SECRET],
    ]);
    @curl_exec($ch);
    @curl_close($ch);
}

if (!defined('APP_ENC_KEY_OLD')) define('APP_ENC_KEY_OLD', 'Payom_change_this_to_your_own_long_random_secret_2026!!');
function enc_at_rest($plain) {
    if ($plain === null || $plain === '') return $plain;
    if (!function_exists('openssl_encrypt')) return $plain;
    $key = hash('sha256', APP_ENC_KEY, true);
    $iv = random_bytes(12); $tag = '';
    $ct = openssl_encrypt($plain, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag);
    if ($ct === false) return $plain;
    return 'v1:' . base64_encode($iv . $tag . $ct);
}
function dec_at_rest($data) {
    if (!is_string($data) || strncmp($data, 'v1:', 3) !== 0) return $data; // старый формат (открытый) — как есть
    if (!function_exists('openssl_decrypt')) return null;
    $raw = base64_decode(substr($data, 3), true);
    if ($raw === false || strlen($raw) < 28) return null;
    $iv = substr($raw, 0, 12); $tag = substr($raw, 12, 16); $ct = substr($raw, 28);

    /* Сначала пробуем текущий ключ. Если не подошёл — прежний:
       так читаются сообщения, записанные до смены ключа. */
    $pt = openssl_decrypt($ct, 'aes-256-gcm', hash('sha256', APP_ENC_KEY, true), OPENSSL_RAW_DATA, $iv, $tag);
    if ($pt === false && defined('APP_ENC_KEY_OLD') && APP_ENC_KEY_OLD !== APP_ENC_KEY) {
        $pt = openssl_decrypt($ct, 'aes-256-gcm', hash('sha256', APP_ENC_KEY_OLD, true), OPENSSL_RAW_DATA, $iv, $tag);
    }
    return $pt === false ? null : $pt;
}
function face_dist($a, $b) {
    $n = min(count($a), count($b)); if ($n < 100) return 999;
    $s = 0; for ($i = 0; $i < $n; $i++) { $d = (float)$a[$i] - (float)$b[$i]; $s += $d * $d; } return sqrt($s);
}
if ($preAction === 'face_login' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/json');
    if (!rate_ok('face', 30, 60)) { echo json_encode(['error' => 'too_many', 'msg' => 'Слишком много попыток, подождите минуту']); exit; }
    $d = json_decode(file_get_contents('php://input'), true);
    $desc = $d['descriptor'] ?? null;
    if (!is_array($desc) || count($desc) < 100) { echo json_encode(['error' => 'bad']); exit; }
    $rows = $pdo->query("SELECT id, name, phone, face_descriptor FROM qaz_users WHERE face_descriptor IS NOT NULL AND face_descriptor <> ''")->fetchAll();
    // считаем ЛУЧШЕЕ расстояние по КАЖДОМУ пользователю
    $perUser = []; $rowById = [];
    foreach ($rows as $r) {
        $samples = json_decode(dec_at_rest($r['face_descriptor']), true); if (!is_array($samples)) continue;
        if (isset($samples[0]) && !is_array($samples[0])) $samples = [$samples]; // одиночный формат
        $ud = 999;
        foreach ($samples as $smp) { $dist = face_dist($desc, $smp); if ($dist < $ud) $ud = $dist; }
        $perUser[(int)$r['id']] = $ud; $rowById[(int)$r['id']] = $r;
    }
    asort($perUser);
    $ids = array_keys($perUser);
    $bestId   = $ids[0] ?? 0;
    $bestDist = $bestId ? $perUser[$bestId] : 999;
    $secondDist = isset($ids[1]) ? $perUser[$ids[1]] : 999; // ближайший ДРУГОЙ человек
    // Безопасность: пускаем только если лицо близко (строгий порог)
    // И заметно ближе, чем любой другой аккаунт (запас) — иначе не угадываем, просим номер.
    $STRICT = 0.46;  // строгий порог совпадения
    $MARGIN = 0.06;  // насколько наше лицо должно быть ближе следующего
    $best = $bestId ? $rowById[$bestId] : null;
    if ($best && $bestDist < $STRICT && ($secondDist - $bestDist) >= $MARGIN) {
        session_regenerate_id(true);
        $_SESSION['user_id'] = (int)$best['id']; $_SESSION['user_name'] = $best['name']; $_SESSION['user_phone'] = $best['phone'];
        qaz_set_remember($pdo, (int)$best['id']);
        echo json_encode(['ok' => true, 'dist' => round($bestDist, 3)]); exit;
    }
    // если лицо близко к двум людям сразу (сомнение) — тоже не пускаем
    echo json_encode(['error' => 'nomatch', 'dist' => round($bestDist, 3), 'ambiguous' => ($bestDist < $STRICT && ($secondDist - $bestDist) < $MARGIN)]); exit;
}

if ($preAction === 'tg_check') {
    header('Content-Type: application/json');
    $token = $_GET['token'] ?? '';
    $v = $pdo->prepare("SELECT * FROM tg_verify WHERE token = ? AND created_at > (NOW() - INTERVAL 15 MINUTE)");
    $v->execute([$token]); $row = $v->fetch();
    if (!$row) { echo json_encode(['status' => 'expired']); exit; }
    if ($row['status'] === 'declined') { echo json_encode(['status' => 'declined']); exit; }
    if ($row['status'] !== 'verified') { echo json_encode(['status' => 'pending']); exit; }
    // верифицировано — входим
    $phone = $row['verified_phone'] ?: $row['phone'];
    $uq = $pdo->prepare("SELECT * FROM qaz_users WHERE phone = ?"); $uq->execute([$phone]); $u = $uq->fetch();
    if (!$u) {
        $nm = trim($row['tg_name'] ?: '') ?: 'Пользователь';
        $pdo->prepare("INSERT INTO qaz_users (phone, name, password) VALUES (?,?,'')")->execute([$phone, $nm]);
        $uid = $pdo->lastInsertId();
    } else { $uid = $u['id']; }
    if (!empty($row['chat_id'])) $pdo->prepare("UPDATE qaz_users SET tg_chat_id = ? WHERE id = ?")->execute([$row['chat_id'], $uid]);
    $nameQ = $pdo->prepare("SELECT name, phone FROM qaz_users WHERE id = ?"); $nameQ->execute([$uid]); $ui = $nameQ->fetch();
    session_regenerate_id(true);
    $_SESSION['user_id'] = $uid; $_SESSION['user_name'] = $ui['name']; $_SESSION['user_phone'] = $ui['phone'];
    qaz_set_remember($pdo, $uid);
    $pdo->prepare("DELETE FROM tg_verify WHERE token = ?")->execute([$token]);
    echo json_encode(['status' => 'ok']); exit;
}

// ============================================
// ВХОД (по номеру + имя)
// ============================================
if (isset($_GET['logout'])) { qaz_clear_remember($pdo); session_destroy(); header('Location: messenger.php'); exit; }

if (empty($_SESSION['user_id'])) {
    ?>
    <!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#1E1E2C">
    <title>Payom — вход</title>
    <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap" rel="stylesheet">
    <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{min-height:100vh;font-family:'Manrope',system-ui,sans-serif;background:radial-gradient(1100px 560px at 50% -8%,#2C2350 0%,#171626 45%,#111019 100%);display:flex;align-items:center;justify-content:center;padding:18px}
    .box{width:100%;max-width:380px;background:linear-gradient(180deg,#22222F,#1A1A26);border:1px solid rgba(255,255,255,.06);border-radius:26px;padding:36px 26px;text-align:center;box-shadow:0 30px 70px rgba(0,0,0,.55),0 0 0 1px rgba(124,92,255,.05);display:flex;flex-direction:column;align-items:stretch}
    .box>*{width:100%}
    .logo{width:88px;height:88px;border-radius:26px;margin:0 auto 22px;background:linear-gradient(140deg,#9575FF,#5B3FE0);display:flex;align-items:center;justify-content:center;box-shadow:0 14px 34px rgba(124,92,255,.5),inset 0 1px 0 rgba(255,255,255,.25)}
    .logo svg{width:46px;height:46px;color:#fff;filter:drop-shadow(0 2px 4px rgba(0,0,0,.2))}
    h1{color:#fff;font-size:23px;font-weight:800;letter-spacing:.3px}
    p.s{color:#8B8B9E;font-size:13.5px;font-weight:600;margin:8px 0 24px;line-height:1.5}
    input{width:100%;padding:15px 16px;border:1.5px solid #33334A;border-radius:14px;background:#15151F;color:#fff;font-size:16px;outline:none;margin-bottom:12px;font-weight:600;font-family:inherit;transition:border-color .2s}
    input:focus{border-color:#7C5CFF;box-shadow:0 0 0 3px rgba(124,92,255,.15)}
    .btn{width:100%;padding:16px;border:none;border-radius:14px;background:linear-gradient(135deg,#8E6BFF,#5B3FE0);color:#fff;font-size:15px;font-weight:800;cursor:pointer;font-family:inherit;display:block;text-decoration:none;text-align:center;box-shadow:0 8px 22px rgba(124,92,255,.38);transition:transform .15s,box-shadow .15s}
    .btn:active{transform:scale(.97)}
    .btn.tg{background:linear-gradient(135deg,#6E56E8,#4E3AC0);margin-bottom:12px}
    .err{background:#3A2226;color:#FF6B6B;padding:11px;border-radius:11px;font-size:13px;font-weight:700;margin-bottom:12px}
    .spin{width:44px;height:44px;border:4px solid #2A2A3C;border-top-color:#7C5CFF;border-radius:50%;margin:16px auto;animation:sp 1s linear infinite}
    @keyframes sp{to{transform:rotate(360deg)}}
    </style></head><body>
    <div class="box">
        <div class="logo"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 5a3 3 0 013-3h10a3 3 0 013 3v7a3 3 0 01-3 3H9l-4 4v-4a3 3 0 01-1-2V5z"/></svg></div>
        <h1>Payom</h1>
        <!-- шаг 1: номер -->
        <div id="step1">
            <p class="s">Быстрый вход по лицу.<br>Первый раз — подтвердите номер телефона.</p>
            <div id="regHint" class="err" style="display:none;background:#1E3A2A;color:#4ADE80">Лицо новое — подтвердите номер, и оно сохранится.</div>
            <div id="err1" class="err" style="display:none"></div>
            <button class="btn" style="padding:18px;font-size:16px" onclick="openFace('smart')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:20px;height:20px;vertical-align:-5px;margin-right:8px"><path d="M7 3H5a2 2 0 00-2 2v2M17 3h2a2 2 0 012 2v2M7 21H5a2 2 0 01-2-2v-2M17 21h2a2 2 0 002-2v-2M9 10h.01M15 10h.01M9 15c.8.7 1.9 1 3 1s2.2-.3 3-1"/></svg>Войти по лицу</button>
            <div id="phoneBlock" style="display:none;margin-top:14px">
                <input type="tel" id="loginPhone" placeholder="+7 777 123 45 67">
                <button class="btn" onclick="tgStart()">Продолжить</button>
            </div>
            <button id="phoneToggle" class="btn" style="background:#2A2A3C;margin-top:10px" onclick="showPhone()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:17px;height:17px;vertical-align:-3px;margin-right:7px"><path d="M22 16.9v3a2 2 0 01-2.2 2 19.8 19.8 0 01-8.6-3.1 19.5 19.5 0 01-6-6A19.8 19.8 0 012 4.2 2 2 0 014.1 2h3a2 2 0 012 1.7c.1.9.4 1.8.7 2.7a2 2 0 01-.5 2.1L8.1 9.9a16 16 0 006 6l1.4-1.2a2 2 0 012.1-.5c.9.3 1.8.6 2.7.7a2 2 0 011.7 2z"/></svg>Войти по номеру телефона</button>
            <div style="margin-top:16px;padding:13px 14px;background:rgba(124,92,255,.1);border:1px solid rgba(124,92,255,.28);border-radius:14px;text-align:left">
                <div style="display:flex;align-items:center;gap:8px;font-weight:800;font-size:13.5px;color:#B9A9FF;margin-bottom:7px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:17px;height:17px;flex-shrink:0"><path d="M12 2l8 4v6c0 5-3.4 8.3-8 10-4.6-1.7-8-5-8-10V6l8-4z"/><path d="M9 12l2 2 4-4"/></svg>Это безопасно</div>
                <div style="font-size:12.5px;color:var(--sub);line-height:1.55">Сохраняется не фото, а зашифрованный код (AES-256). По нему нельзя восстановить лицо. Используется только для вашего личного входа — ни владелец, ни разработчик не могут его посмотреть или где-либо применить.</div>
            </div>
        </div>
        <!-- шаг 2: подтверждение -->
        <div id="step2" style="display:none">
            <div class="spin"></div>
            <p class="s" id="step2text"></p>
            <a id="botLink" class="btn tg" href="#" target="_blank" style="display:none">Открыть Telegram-бот</a>
            <button class="btn" style="background:#2A2A3C" onclick="tgBack()">← Назад</button>
        </div>
    </div>
    <script>
    let tgToken=null, tgPoll=null;
    window.pendingFaceDesc=null;
    function showPhone(){ document.getElementById('phoneBlock').style.display='block'; document.getElementById('phoneToggle').style.display='none'; document.getElementById('loginPhone').focus(); }
    window.afterFaceNeedsPhone=function(){ document.getElementById('regHint').style.display='block'; showPhone(); };
    document.getElementById('loginPhone').addEventListener('input',e=>{ e.target.value=e.target.value.replace(/[^\d+]/g,''); });
    document.getElementById('loginPhone').addEventListener('keydown',e=>{ if(e.key==='Enter')tgStart(); });
    async function tgStart(){
        const phone=document.getElementById('loginPhone').value.trim();
        if(phone.replace(/\D/g,'').length<10){ showErr('Введите правильный номер'); return; }
        const fd=new FormData(); fd.append('phone',phone);
        const r=await fetch('messenger.php?action=tg_start',{method:'POST',body:fd}).then(x=>x.json()).catch(()=>({error:'Ошибка сети'}));
        if(r.error){ showErr(r.error); return; }
        tgToken=r.token;
        document.getElementById('step1').style.display='none';
        document.getElementById('step2').style.display='block';
        if(r.mode==='confirm'){
            document.getElementById('step2text').innerHTML='Мы отправили запрос в Telegram-бот <b>@'+'<?= TG_BOT_USERNAME ?>'+'</b>.<br>Откройте бот и нажмите <b>«Да, это я»</b>.';
            document.getElementById('botLink').href='https://t.me/<?= TG_BOT_USERNAME ?>';
            document.getElementById('botLink').style.display='block';
        } else {
            document.getElementById('step2text').innerHTML='Откройте наш Telegram-бот и нажмите <b>«Поделиться номером»</b> — так мы подтвердим, что номер ваш.';
            document.getElementById('botLink').href=r.bot;
            document.getElementById('botLink').style.display='block';
        }
        tgPoll=setInterval(checkTg,2500);
    }
    async function checkTg(){
        if(!tgToken) return;
        const r=await fetch('messenger.php?action=tg_check&token='+tgToken).then(x=>x.json()).catch(()=>({}));
        if(r.status==='ok'){ clearInterval(tgPoll);
            if(window.pendingFaceDesc){ document.getElementById('step2text').innerHTML='Сохраняем ваше лицо…';
                fetch('messenger.php?action=face_enroll',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({descriptor:window.pendingFaceDesc})}).catch(()=>{}).finally(()=>{ location.href='messenger.php'; });
            } else { location.href='messenger.php'; }
        }
        else if(r.status==='declined'){ clearInterval(tgPoll); showErr('Вход отклонён в Telegram'); tgBack(); }
        else if(r.status==='expired'){ clearInterval(tgPoll); showErr('Время вышло, попробуйте снова'); tgBack(); }
    }
    function tgBack(){ if(tgPoll)clearInterval(tgPoll); tgToken=null; document.getElementById('step2').style.display='none'; document.getElementById('step1').style.display='block'; }
    function showErr(t){ const e=document.getElementById('err1'); e.textContent=t; e.style.display='block'; }
    </script>
    <?= face_module() ?>
    </body></html>
    <?php exit;
}

$ME = (int)$_SESSION['user_id'];
$MYNAME = $_SESSION['user_name'] ?? 'Я';

/* ==== ОФИЦИАЛЬНЫЙ КАНАЛ PAYOM: создаётся сам, подписка автоматическая ==== */
function ensure_official_channel($pdo, $me) {
    static $checked = false;
    if ($checked || !$me) return 0;
    $checked = true;
    /* Раз проверили за сессию — больше не дёргаем базу на каждый запрос.
       Но один раз за сессию убеждаемся, что канал не пустой. */
    if (!empty($_SESSION['off_ch']) && !empty($_SESSION['off_ready'])) return (int)$_SESSION['off_ch'];
    try {
        $chid = (int)$pdo->query("SELECT id FROM msg_channels WHERE is_official = 1 LIMIT 1")->fetchColumn();

        if (!$chid) {   // канала ещё нет — создаём
            $owner = (int)trim(explode(',', ADMIN_IDS)[0]);
            if (!$owner) $owner = $me;
            $code = substr(str_replace(['+','/','='], '', base64_encode(random_bytes(12))), 0, 14);
            $pdo->prepare("INSERT INTO msg_channels (owner_id, title, username, about, avatar, is_public, invite_code, subs_count, is_official)
                           VALUES (?,?,?,?,'messenger.php?chicon=1',1,?,1,1)")
                ->execute([$owner, 'Payom', 'payom',
                           'Официальный канал Payom: обновления, новые функции, важные объявления.', $code]);
            $chid = (int)$pdo->lastInsertId();
            $pdo->prepare("INSERT IGNORE INTO msg_channel_subs (channel_id, user_id, role) VALUES (?,?,'owner')")
                ->execute([$chid, $owner]);
            $pdo->prepare("INSERT INTO msg_channel_posts (channel_id, author_id, text) VALUES (?,?,?)")
                ->execute([$chid, $owner,
                    "Добро пожаловать в Payom!\n\nЗдесь мы публикуем обновления приложения, новые функции, "
                  . "исправления и важные объявления.\n\nЭтот канал нельзя удалить, но уведомления можно "
                  . "отключить в настройках канала."]);
        }

        // если канал есть, но пустой — добавляем приветственную публикацию
        $__pc = $pdo->prepare("SELECT COUNT(*) FROM msg_channel_posts WHERE channel_id = ? AND deleted = 0");
        $__pc->execute([$chid]);
        if (!(int)$__pc->fetchColumn()) {
            $__ow = $pdo->prepare("SELECT owner_id FROM msg_channels WHERE id = ?");
            $__ow->execute([$chid]);
            $pdo->prepare("INSERT INTO msg_channel_posts (channel_id, author_id, text) VALUES (?,?,?)")
                ->execute([$chid, (int)$__ow->fetchColumn(),
                    "Добро пожаловать в Payom!\n\nЗдесь мы публикуем обновления приложения, новые функции, "
                  . "исправления и важные объявления.\n\nЭтот канал нельзя удалить, но уведомления можно "
                  . "отключить в настройках канала."]);
        }

        // приводим название к «Payom» (раньше было PAYOM Official)
        $pdo->prepare("UPDATE msg_channels SET title = 'Payom'
                       WHERE id = ? AND title = 'PAYOM Official'")->execute([$chid]);

        // если канал уже был создан без аватарки — ставим встроенную
        $pdo->prepare("UPDATE msg_channels SET avatar = 'messenger.php?chicon=1'
                       WHERE id = ? AND (avatar IS NULL OR avatar = '')")->execute([$chid]);

        // подписываем текущего пользователя, если ещё не подписан
        $ins = $pdo->prepare("INSERT IGNORE INTO msg_channel_subs (channel_id, user_id, role) VALUES (?,?,'sub')");
        $ins->execute([$chid, $me]);
        if ($ins->rowCount()) $pdo->prepare("UPDATE msg_channels SET subs_count = subs_count + 1 WHERE id = ?")->execute([$chid]);

        $_SESSION['off_ch'] = $chid;
        $_SESSION['off_ready'] = 1;
        return $chid;
    } catch (\Throwable $e) { return 0; }
}


// отметить, что пользователь сейчас в сети
/* last_seen пишем не чаще раза в минуту — иначе запись в базу на каждый опрос */
if (empty($_SESSION['ls_touch']) || time() - (int)$_SESSION['ls_touch'] > 60) {
    $_SESSION['ls_touch'] = time();
    try { $pdo->prepare("UPDATE qaz_users SET last_seen = NOW() WHERE id = ?")->execute([$ME]); } catch (\Throwable $e) {}
}

// ==== Админы (кто ставит синюю галочку) ====
if (!defined('ADMIN_IDS')) define('ADMIN_IDS', '1'); // ID через запятую — впишите свой ID
function is_site_admin($me) { return in_array((string)$me, array_map('trim', explode(',', ADMIN_IDS)), true); }
ensure_official_channel($pdo, $ME);

// ==== Устройства / активные сеансы (как в Telegram) ====
function device_name($ua) {
    $ua = $ua ?: ''; $os = 'Устройство';
    if (preg_match('/iPhone/i', $ua)) $os = 'iPhone';
    elseif (preg_match('/iPad/i', $ua)) $os = 'iPad';
    elseif (preg_match('/Android/i', $ua)) { $os = 'Android'; if (preg_match('/;\s*([^;\)]+)\s+Build/i', $ua, $m)) $os = trim($m[1]); }
    elseif (preg_match('/Windows/i', $ua)) $os = 'Windows';
    elseif (preg_match('/Mac OS X|Macintosh/i', $ua)) $os = 'Mac';
    elseif (preg_match('/Linux/i', $ua)) $os = 'Linux';
    $br = '';
    if (preg_match('/Chrome\//i', $ua) && !preg_match('/Edg|OPR/i', $ua)) $br = 'Chrome';
    elseif (preg_match('/CriOS/i', $ua)) $br = 'Chrome';
    elseif (preg_match('/Firefox|FxiOS/i', $ua)) $br = 'Firefox';
    elseif (preg_match('/Edg/i', $ua)) $br = 'Edge';
    elseif (preg_match('/Safari/i', $ua)) $br = 'Safari';
    return trim($os . ($br ? ' · ' . $br : ''));
}
$DEVICE_ID = $_COOKIE['pd_dev'] ?? '';
$curUA = substr($_SERVER['HTTP_USER_AGENT'] ?? '', 0, 400);
$curIP = trim(explode(',', ($_SERVER['HTTP_X_FORWARDED_FOR'] ?? ($_SERVER['REMOTE_ADDR'] ?? '')))[0]);
if ($DEVICE_ID === '' || !preg_match('/^[a-f0-9]{16,64}$/i', $DEVICE_ID)) {
    $DEVICE_ID = bin2hex(random_bytes(16));
    if (!headers_sent()) setcookie('pd_dev', $DEVICE_ID, ['expires' => time() + 63072000, 'path' => '/', 'secure' => $__https, 'httponly' => true, 'samesite' => 'Lax']);
    try { $pdo->prepare("INSERT IGNORE INTO msg_sessions (user_id, device_id, ua, ip, created_at) VALUES (?,?,?,?,NOW())")->execute([$ME, $DEVICE_ID, $curUA, $curIP]); } catch (\Throwable $e) {}
} else {
    try {
        $sq = $pdo->prepare("SELECT id FROM msg_sessions WHERE user_id=? AND device_id=?"); $sq->execute([$ME, $DEVICE_ID]);
        if ($sq->fetch()) {
            $pdo->prepare("UPDATE msg_sessions SET ua=?, ip=?, last_active=NOW() WHERE user_id=? AND device_id=?")->execute([$curUA, $curIP, $ME, $DEVICE_ID]);
        } else {
            $cq = $pdo->prepare("SELECT COUNT(*) FROM msg_sessions WHERE user_id=?"); $cq->execute([$ME]);
            if ((int)$cq->fetchColumn() > 0) { // сеанс завершён удалённо → выходим
                qaz_clear_remember($pdo); session_destroy();
                header('Location: messenger.php'); exit;
            } else {
                $pdo->prepare("INSERT IGNORE INTO msg_sessions (user_id, device_id, ua, ip, created_at) VALUES (?,?,?,?,NOW())")->execute([$ME, $DEVICE_ID, $curUA, $curIP]);
            }
        }
    } catch (\Throwable $e) {}
}

// текст статуса по last_seen
function status_text($lastSeen) {
    if (!$lastSeen) return 'был(а) давно';
    $t = strtotime($lastSeen);
    $diff = time() - $t;
    if ($diff < 65) return 'в сети';
    if ($diff < 3600) return 'был(а) ' . max(1, floor($diff / 60)) . ' мин назад';
    if ($diff < 86400) return 'был(а) ' . floor($diff / 3600) . ' ч назад';
    if ($diff < 172800) return 'был(а) вчера';
    return 'был(а) ' . date('d.m', $t);
}

// проверка членства в чате
function is_member($pdo, $chatId, $me) {
    $st = $pdo->prepare("SELECT 1 FROM msg_members WHERE chat_id = ? AND user_id = ?");
    $st->execute([$chatId, $me]);
    return (bool)$st->fetchColumn();
}
function is_admin($pdo, $chatId, $me) {
    $st = $pdo->prepare("SELECT is_admin FROM msg_members WHERE chat_id = ? AND user_id = ?");
    $st->execute([$chatId, $me]);
    return (bool)$st->fetchColumn();
}
function sys_msg($pdo, $chatId, $text) {
    $pdo->prepare("INSERT INTO msg_messages (chat_id, sender_id, text, type) VALUES (?,0,?,'system')")->execute([$chatId, enc_at_rest($text)]);
}
function uname($pdo, $uid) {
    $s = $pdo->prepare("SELECT name FROM qaz_users WHERE id = ?"); $s->execute([$uid]); return $s->fetchColumn() ?: 'Пользователь';
}
function has_private_chat($pdo, $a, $b) {
    $q = $pdo->prepare("SELECT c.id FROM msg_chats c JOIN msg_members m1 ON m1.chat_id=c.id AND m1.user_id=? JOIN msg_members m2 ON m2.chat_id=c.id AND m2.user_id=? WHERE c.type='private' LIMIT 1");
    $q->execute([$a, $b]); return (bool)$q->fetchColumn();
}
function open_private($pdo, $a, $b) {
    $q = $pdo->prepare("SELECT c.id FROM msg_chats c JOIN msg_members m1 ON m1.chat_id=c.id AND m1.user_id=? JOIN msg_members m2 ON m2.chat_id=c.id AND m2.user_id=? WHERE c.type='private' LIMIT 1");
    $q->execute([$a, $b]); $cid = $q->fetchColumn();
    if (!$cid) {
        $pdo->prepare("INSERT INTO msg_chats (type, created_by) VALUES ('private', ?)")->execute([$a]);
        $cid = $pdo->lastInsertId();
        $pdo->prepare("INSERT IGNORE INTO msg_members (chat_id, user_id) VALUES (?,?),(?,?)")->execute([$cid, $a, $cid, $b]);
    }
    return (int)$cid;
}
// Виден ли номер владельца $owner (массив с id, priv_phone) зрителю $viewer.
// Видно если priv_phone='all' ИЛИ владелец сам поделился номером с этим человеком (share_number=1).
function phone_visible($pdo, $owner, $viewer) {
    if (($owner['priv_phone'] ?? 'all') === 'all') return true;
    $q = $pdo->prepare("SELECT 1 FROM msg_contacts WHERE owner_id=? AND user_id=? AND share_number=1 LIMIT 1");
    $q->execute([(int)$owner['id'], (int)$viewer]); return (bool)$q->fetchColumn();
}
// Собственное имя контакта, которое $owner дал пользователю $uid (если есть)
function contact_name($pdo, $owner, $uid) {
    $q = $pdo->prepare("SELECT name FROM msg_contacts WHERE owner_id=? AND user_id=? LIMIT 1");
    $q->execute([$owner, $uid]); $n = $q->fetchColumn();
    return ($n !== false && trim($n) !== '') ? $n : null;
}
function story_visible($pdo, $story, $me) {
    if ((int)$story['user_id'] === $me) return true;
    $aud = $story['audience'] ?? 'all';
    if ($aud === 'all') return true;
    if ($aud === 'contacts') return has_private_chat($pdo, (int)$story['user_id'], $me);
    if ($aud === 'select') { $c = $pdo->prepare("SELECT 1 FROM msg_story_audience WHERE story_id=? AND user_id=?"); $c->execute([$story['id'], $me]); return (bool)$c->fetchColumn(); }
    return false;
}

// ============================================
// API (JSON)
// ============================================
$action = $_GET['action'] ?? '';

if ($action) {
    header('Content-Type: application/json');
    // ------------------------------------------------------------------
    // ЗАЩИТА ОТ КЭШИРОВАНИЯ (устраняет «мигание»/пропадание чата).
    // Браузер и промежуточные прокси НЕ должны отдавать старые JSON-ответы:
    // из-за кэша чат мог показывать устаревший список и «моргать».
    // ------------------------------------------------------------------
    // Само ограничение частоты (429) уже отработало в самом верху файла —
    // ДО миграций схемы и любых запросов к БД (см. rl_check рядом с require db.php).
    header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
    header('Pragma: no-cache');
    header('Expires: 0');

    /* Кто я — по этому запросу ядро на VPS узнаёт, кому принадлежит токен.
       Нужно, когда база закрыта снаружи и ядро работает только на доставку. */
    if ($action === 'whoami') {
        echo json_encode(['ok' => true, 'id' => $ME, 'name' => $MYNAME], JSON_UNESCAPED_UNICODE);
        exit;
    }

    /* ЛЁГКАЯ ПРОВЕРКА: есть ли новое. Дёшево — вместо тяжёлой загрузки каждые 2.5 сек */
    if ($action === 'ping') {
        $out = ['ok' => true];
        $pcid = (int)($_GET['chat'] ?? 0);
        if ($pcid && is_member($pdo, $pcid, $ME)) {
            $pq = $pdo->prepare("SELECT MAX(id) FROM msg_messages WHERE chat_id = ?");
            $pq->execute([$pcid]);
            $out['last'] = (int)$pq->fetchColumn();
            $ptp = $pdo->prepare("SELECT COUNT(*) FROM msg_typing WHERE chat_id = ? AND user_id <> ? AND updated_at > (NOW() - INTERVAL 6 SECOND)");
            $ptp->execute([$pcid, $ME]);
            $out['typing'] = (int)$ptp->fetchColumn();
        }
        $pu = $pdo->prepare("SELECT COUNT(*) FROM msg_messages mm
                             JOIN msg_members m ON m.chat_id = mm.chat_id AND m.user_id = ?
                             WHERE mm.id > m.last_read_id AND mm.sender_id <> ?");
        $pu->execute([$ME, $ME]);
        $out['unread'] = (int)$pu->fetchColumn();
        echo json_encode($out); exit;
    }

    /* PAYOM-CHANNELS-API */

    /* ---------- комментарии к публикациям ---------- */
    if ($action === 'ch_comments') {
        $pid = (int)($_GET['post'] ?? 0);
        $pq = $pdo->prepare("SELECT p.channel_id, c.comments_on, c.is_public FROM msg_channel_posts p
                             JOIN msg_channels c ON c.id = p.channel_id WHERE p.id = ?");
        $pq->execute([$pid]); $pi = $pq->fetch();
        if (!$pi) { echo json_encode(['error' => 'not_found']); exit; }

        $ms = $pdo->prepare("SELECT role FROM msg_channel_subs WHERE channel_id=? AND user_id=?");
        $ms->execute([$pi['channel_id'], $ME]); $role = $ms->fetchColumn();
        if (!$role && !(int)$pi['is_public']) { echo json_encode(['error' => 'no_access']); exit; }

        $q = $pdo->prepare("SELECT cm.id, cm.user_id, cm.text, UNIX_TIMESTAMP(cm.created_at) ts,
                                   u.name, u.avatar, u.verified
                            FROM msg_channel_comments cm LEFT JOIN qaz_users u ON u.id = cm.user_id
                            WHERE cm.post_id = ? AND cm.deleted = 0 ORDER BY cm.id ASC LIMIT 200");
        $q->execute([$pid]);
        echo json_encode(['ok' => true, 'comments' => $q->fetchAll(), 'me' => $ME,
                          'can_write' => (int)$pi['comments_on'] === 1 && $role !== false && $role !== null,
                          'is_admin' => in_array($role, ['owner','admin'], true),
                          'comments_on' => (int)$pi['comments_on']], JSON_UNESCAPED_UNICODE); exit;
    }

    if ($action === 'ch_comment_add' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $pid = (int)($d['post'] ?? 0);
        $txt = trim($d['text'] ?? '');
        if ($txt === '' || mb_strlen($txt) > 1000) { echo json_encode(['error' => 'bad']); exit; }

        $pq = $pdo->prepare("SELECT p.channel_id, c.comments_on FROM msg_channel_posts p
                             JOIN msg_channels c ON c.id = p.channel_id WHERE p.id = ? AND p.deleted = 0");
        $pq->execute([$pid]); $pi = $pq->fetch();
        if (!$pi) { echo json_encode(['error' => 'not_found']); exit; }
        if (!(int)$pi['comments_on']) { echo json_encode(['error' => 'closed']); exit; }

        $ms = $pdo->prepare("SELECT 1 FROM msg_channel_subs WHERE channel_id=? AND user_id=?");
        $ms->execute([$pi['channel_id'], $ME]);
        if (!$ms->fetchColumn()) { echo json_encode(['error' => 'not_sub']); exit; }

        /* защита от спама: не чаще одного комментария в 5 секунд */
        $fl = $pdo->prepare("SELECT UNIX_TIMESTAMP(MAX(created_at)) FROM msg_channel_comments WHERE user_id = ?");
        $fl->execute([$ME]);
        if ((int)$fl->fetchColumn() > time() - 5) { echo json_encode(['error' => 'slow']); exit; }

        $pdo->prepare("INSERT INTO msg_channel_comments (post_id, channel_id, user_id, text) VALUES (?,?,?,?)")
            ->execute([$pid, $pi['channel_id'], $ME, $txt]);

        /* владельцу канала — уведомление */
        $ow = $pdo->prepare("SELECT owner_id, title FROM msg_channels WHERE id = ?");
        $ow->execute([$pi['channel_id']]); $och = $ow->fetch();
        if ($och && (int)$och['owner_id'] !== $ME)
            qaz_push_send($pdo, (int)$och['owner_id'], $och['title'],
                          $MYNAME . ': ' . mb_substr($txt, 0, 80), 'messenger.php', 'qaz-cmt');

        echo json_encode(['ok' => true, 'id' => (int)$pdo->lastInsertId()]); exit;
    }

    if ($action === 'ch_comment_del' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $cid = (int)($d['id'] ?? 0);
        $q = $pdo->prepare("SELECT cm.user_id, cm.channel_id, s.role FROM msg_channel_comments cm
                            LEFT JOIN msg_channel_subs s ON s.channel_id = cm.channel_id AND s.user_id = ?
                            WHERE cm.id = ?");
        $q->execute([$ME, $cid]); $row = $q->fetch();
        if (!$row) { echo json_encode(['error' => 'not_found']); exit; }
        $mine = (int)$row['user_id'] === $ME;
        $adm  = in_array($row['role'], ['owner','admin'], true);
        if (!$mine && !$adm) { echo json_encode(['error' => 'no_access']); exit; }
        $pdo->prepare("UPDATE msg_channel_comments SET deleted = 1 WHERE id = ?")->execute([$cid]);
        echo json_encode(['ok' => true]); exit;
    }

    if ($action === 'ch_comments_toggle' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $chid = (int)($d['channel'] ?? 0);
        $ms = $pdo->prepare("SELECT role FROM msg_channel_subs WHERE channel_id=? AND user_id=?");
        $ms->execute([$chid, $ME]);
        if (!in_array($ms->fetchColumn(), ['owner','admin'], true)) { echo json_encode(['error' => 'no_access']); exit; }
        $pdo->prepare("UPDATE msg_channels SET comments_on = ? WHERE id = ?")
            ->execute([!empty($d['val']) ? 1 : 0, $chid]);
        echo json_encode(['ok' => true]); exit;
    }

    /* ---------- создать канал ---------- */
    if ($action === 'channel_create' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $title = mb_substr(trim($d['title'] ?? ''), 0, 120);
        $about = mb_substr(trim($d['about'] ?? ''), 0, 300);
        $isPub = !empty($d['public']) ? 1 : 0;
        $uname = preg_replace('/[^A-Za-z0-9_]/', '', ltrim(trim($d['username'] ?? ''), '@'));

        if (mb_strlen($title) < 2) { echo json_encode(['error' => 'Введите название канала']); exit; }
        if ($isPub && mb_strlen($uname) < 4) { echo json_encode(['error' => 'Для публичного канала нужен @username (от 4 символов)']); exit; }
        if ($uname !== '') {
            $ck = $pdo->prepare("SELECT id FROM msg_channels WHERE username = ?"); $ck->execute([$uname]);
            if ($ck->fetchColumn()) { echo json_encode(['error' => 'Этот @username уже занят']); exit; }
            $cu = $pdo->prepare("SELECT id FROM qaz_users WHERE username = ?"); $cu->execute([$uname]);
            if ($cu->fetchColumn()) { echo json_encode(['error' => 'Этот @username уже занят']); exit; }
        }

        $code = substr(str_replace(['+','/','='], '', base64_encode(random_bytes(12))), 0, 14);
        $pdo->prepare("INSERT INTO msg_channels (owner_id, title, username, about, is_public, invite_code, subs_count)
                       VALUES (?,?,?,?,?,?,1)")
            ->execute([$ME, $title, $uname ?: null, $about ?: null, $isPub, $code]);
        $chid = (int)$pdo->lastInsertId();
        $pdo->prepare("INSERT INTO msg_channel_subs (channel_id, user_id, role) VALUES (?,?,'owner')")->execute([$chid, $ME]);
        echo json_encode(['ok' => true, 'id' => $chid, 'username' => $uname, 'code' => $code], JSON_UNESCAPED_UNICODE); exit;
    }

    /* ---------- мои каналы (созданные + подписки) ---------- */
    if ($action === 'channel_list') {
        $st = $pdo->prepare("SELECT c.id, c.title, c.username, c.avatar, c.is_public, c.subs_count, c.is_official, s.role, s.muted, s.last_read_id
                             FROM msg_channel_subs s JOIN msg_channels c ON c.id = s.channel_id
                             WHERE s.user_id = ? ORDER BY c.id DESC");
        $st->execute([$ME]);
        $chRows = $st->fetchAll();
        /* Собираем данные пачкой: 2 запроса на все каналы вместо 2 на каждый */
        $chIds = array_map('intval', array_column($chRows, 'id'));
        $lastBy = []; $unreadBy = [];
        if ($chIds) {
            $in = implode(',', $chIds);
            $q1 = $pdo->query("SELECT id, channel_id, text, type, UNIX_TIMESTAMP(created_at) ts
                               FROM msg_channel_posts
                               WHERE id IN (SELECT MAX(id) FROM msg_channel_posts
                                            WHERE channel_id IN ($in) AND deleted = 0 GROUP BY channel_id)");
            foreach ($q1->fetchAll() as $r) $lastBy[(int)$r['channel_id']] = $r;
            $q2 = $pdo->prepare("SELECT p.channel_id, COUNT(*) c FROM msg_channel_posts p
                                 JOIN msg_channel_subs s ON s.channel_id = p.channel_id AND s.user_id = ?
                                 WHERE p.channel_id IN ($in) AND p.id > s.last_read_id AND p.deleted = 0
                                 GROUP BY p.channel_id");
            $q2->execute([$ME]);
            foreach ($q2->fetchAll() as $r) $unreadBy[(int)$r['channel_id']] = (int)$r['c'];
        }
        $out = [];
        foreach ($chRows as $c) {
            $last = $lastBy[(int)$c['id']] ?? null;
            $unread = $unreadBy[(int)$c['id']] ?? 0;
            $prev = '';
            if ($last) {
                $t = $last['type'];
                $prev = $t === 'image' ? 'Фото' : ($t === 'video' ? 'Видео' : ($t === 'audio' ? 'Голосовое'
                      : ($t === 'file' ? 'Файл' : mb_substr((string)$last['text'], 0, 90))));
            }
            $out[] = ['id' => (int)$c['id'], 'title' => $c['title'], 'username' => $c['username'],
                      'avatar' => $c['avatar'], 'is_public' => (int)$c['is_public'], 'subs' => (int)$c['subs_count'],
                      'official' => (int)($c['is_official'] ?? 0), 'role' => $c['role'], 'muted' => (int)$c['muted'], 'last' => $prev,
                      'ts' => $last ? (int)$last['ts'] : 0, 'unread' => $unread];
        }
        usort($out, fn($a, $b) => $b['ts'] - $a['ts']);
        echo json_encode(['ok' => true, 'channels' => $out], JSON_UNESCAPED_UNICODE); exit;
    }

    /* ---------- инфо о канале (по id, @username или коду) ---------- */
    if ($action === 'channel_get') {
        $id   = (int)($_GET['id'] ?? 0);
        $un   = preg_replace('/[^A-Za-z0-9_]/', '', ltrim($_GET['u'] ?? '', '@'));
        $code = preg_replace('/[^A-Za-z0-9]/', '', $_GET['code'] ?? '');

        if ($id)        { $q = $pdo->prepare("SELECT * FROM msg_channels WHERE id = ?"); $q->execute([$id]); }
        elseif ($un)    { $q = $pdo->prepare("SELECT * FROM msg_channels WHERE username = ?"); $q->execute([$un]); }
        elseif ($code)  { $q = $pdo->prepare("SELECT * FROM msg_channels WHERE invite_code = ?"); $q->execute([$code]); }
        else { echo json_encode(['error' => 'bad']); exit; }

        $c = $q->fetch();
        if (!$c) { echo json_encode(['error' => 'not_found']); exit; }

        $ms = $pdo->prepare("SELECT role, muted FROM msg_channel_subs WHERE channel_id = ? AND user_id = ?");
        $ms->execute([$c['id'], $ME]); $mine = $ms->fetch();

        // приватный канал без подписки и без ссылки — не показываем содержимое
        $canSee = $mine || (int)$c['is_public'] === 1 || $code !== '';

        echo json_encode(['ok' => true, 'channel' => [
            'id' => (int)$c['id'], 'title' => $c['title'], 'username' => $c['username'],
            'about' => $c['about'], 'avatar' => $c['avatar'], 'is_public' => (int)$c['is_public'],
            'subs' => (int)$c['subs_count'], 'pinned_post' => (int)$c['pinned_post'],
            'role' => $mine['role'] ?? null, 'subscribed' => (bool)$mine, 'official' => (int)($c['is_official'] ?? 0),
            'muted' => (int)($mine['muted'] ?? 0), 'can_see' => $canSee,
            'is_admin' => in_array($mine['role'] ?? '', ['owner', 'admin'], true),
            'invite' => in_array($mine['role'] ?? '', ['owner', 'admin'], true) ? $c['invite_code'] : null,
            'comments_on' => (int)($c['comments_on'] ?? 1),
        ]], JSON_UNESCAPED_UNICODE); exit;
    }

    /* ---------- подписаться / отписаться ---------- */
    if ($action === 'channel_sub' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $chid = (int)($d['channel'] ?? 0);
        $code = preg_replace('/[^A-Za-z0-9]/', '', $d['code'] ?? '');
        if (!$chid && $code) { $q = $pdo->prepare("SELECT id FROM msg_channels WHERE invite_code = ?"); $q->execute([$code]); $chid = (int)$q->fetchColumn(); }
        if (!$chid) { echo json_encode(['error' => 'not_found']); exit; }

        $c = $pdo->prepare("SELECT is_public, title FROM msg_channels WHERE id = ?"); $c->execute([$chid]); $ch = $c->fetch();
        if (!$ch) { echo json_encode(['error' => 'not_found']); exit; }
        if (!(int)$ch['is_public'] && !$code) { echo json_encode(['error' => 'private']); exit; }

        $ins = $pdo->prepare("INSERT IGNORE INTO msg_channel_subs (channel_id, user_id, role) VALUES (?,?,'sub')");
        $ins->execute([$chid, $ME]);
        if ($ins->rowCount()) $pdo->prepare("UPDATE msg_channels SET subs_count = subs_count + 1 WHERE id = ?")->execute([$chid]);

        // владельцу — уведомление о новом подписчике
        $ow = $pdo->prepare("SELECT owner_id FROM msg_channels WHERE id = ?"); $ow->execute([$chid]); $owner = (int)$ow->fetchColumn();
        if ($owner && $owner !== $ME) qaz_push_send($pdo, $owner, $ch['title'], 'Новый подписчик: ' . $MYNAME, 'messenger.php', 'qaz-ch');

        echo json_encode(['ok' => true, 'id' => $chid, 'title' => $ch['title']], JSON_UNESCAPED_UNICODE); exit;
    }
    if ($action === 'channel_unsub' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $chid = (int)($d['channel'] ?? 0);
        $of = $pdo->prepare("SELECT is_official FROM msg_channels WHERE id=?"); $of->execute([$chid]);
        if ((int)$of->fetchColumn() === 1) { echo json_encode(['error' => 'official']); exit; }   // официальный не отписывается
        $r = $pdo->prepare("SELECT role FROM msg_channel_subs WHERE channel_id=? AND user_id=?"); $r->execute([$chid, $ME]);
        if ($r->fetchColumn() === 'owner') { echo json_encode(['error' => 'owner']); exit; }
        $del = $pdo->prepare("DELETE FROM msg_channel_subs WHERE channel_id = ? AND user_id = ?");
        $del->execute([$chid, $ME]);
        if ($del->rowCount()) $pdo->prepare("UPDATE msg_channels SET subs_count = GREATEST(0, subs_count - 1) WHERE id = ?")->execute([$chid]);
        echo json_encode(['ok' => true]); exit;
    }

    /* ---------- лента канала ---------- */
    if ($action === 'channel_posts') {
        $chid = (int)($_GET['channel'] ?? 0);
        $c = $pdo->prepare("SELECT * FROM msg_channels WHERE id = ?"); $c->execute([$chid]); $ch = $c->fetch();
        if (!$ch) { echo json_encode(['error' => 'not_found']); exit; }
        $ms = $pdo->prepare("SELECT role FROM msg_channel_subs WHERE channel_id=? AND user_id=?");
        $ms->execute([$chid, $ME]); $role = $ms->fetchColumn();
        if (!$role && !(int)$ch['is_public']) { echo json_encode(['error' => 'no_access']); exit; }

        // отложенные посты, у которых пришло время — публикуем
        $pdo->prepare("UPDATE msg_channel_posts SET scheduled_at = NULL
                       WHERE channel_id = ? AND scheduled_at IS NOT NULL AND scheduled_at <= NOW()")->execute([$chid]);

        $st = $pdo->prepare("SELECT p.id, p.author_id, p.text, p.type, p.file, p.filename, p.dur, p.views, p.pinned,
                                    UNIX_TIMESTAMP(p.created_at) ts, u.name AS aname,
                                    (SELECT COUNT(*) FROM msg_channel_comments cc WHERE cc.post_id = p.id AND cc.deleted = 0) AS cmt
                             FROM msg_channel_posts p LEFT JOIN qaz_users u ON u.id = p.author_id
                             WHERE p.channel_id = ? AND p.deleted = 0 AND p.scheduled_at IS NULL
                             ORDER BY p.id DESC LIMIT 200");
        $st->execute([$chid]);
        $posts = array_reverse($st->fetchAll());

        if ($posts) {
            $ids = array_column($posts, 'id');
            $ph  = implode(',', array_fill(0, count($ids), '?'));
            $rx  = $pdo->prepare("SELECT post_id, emoji, COUNT(*) cnt, MAX(CASE WHEN user_id = ? THEN 1 ELSE 0 END) mine
                                  FROM msg_channel_reacts WHERE post_id IN ($ph) GROUP BY post_id, emoji");
            $rx->execute(array_merge([$ME], $ids));
            $byPost = [];
            foreach ($rx->fetchAll() as $r) $byPost[$r['post_id']][] = ['emoji' => $r['emoji'], 'cnt' => (int)$r['cnt'], 'mine' => (int)$r['mine']];
            foreach ($posts as &$p) { $p['reactions'] = $byPost[$p['id']] ?? []; } unset($p);

            $lastId = (int)$posts[count($posts) - 1]['id'];
            if ($role) $pdo->prepare("UPDATE msg_channel_subs SET last_read_id = ? WHERE channel_id = ? AND user_id = ? AND last_read_id < ?")
                            ->execute([$lastId, $chid, $ME, $lastId]);
        }

        echo json_encode(['ok' => true, 'posts' => $posts, 'me' => $ME,
                          'is_admin' => in_array($role, ['owner', 'admin'], true),
                          'pinned_post' => (int)$ch['pinned_post'], 'comments_on' => (int)($ch['comments_on'] ?? 1)], JSON_UNESCAPED_UNICODE); exit;
    }

    /* ---------- опубликовать пост ---------- */
    if ($action === 'channel_post' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $chid = (int)($_POST['channel'] ?? 0);
        $text = trim($_POST['text'] ?? '');
        $ms = $pdo->prepare("SELECT role FROM msg_channel_subs WHERE channel_id=? AND user_id=?");
        $ms->execute([$chid, $ME]); $role = $ms->fetchColumn();
        if (!in_array($role, ['owner', 'admin'], true)) { echo json_encode(['error' => 'no_access']); exit; }

        $att = !empty($_FILES['file']['tmp_name']) ? qaz_save_chat_file($_FILES['file']) : null;
        if ($text === '' && !$att) { echo json_encode(['error' => 'empty']); exit; }
        if (mb_strlen($text) > 4000) $text = mb_substr($text, 0, 4000);

        $type = $att ? $att['type'] : 'text';
        if ($att && $type === 'file') {
            $ext = strtolower(pathinfo($att['filename'] ?? $att['file'], PATHINFO_EXTENSION));
            if (in_array($ext, ['mp4','mov','m4v','webm','3gp','avi','mkv'])) $type = 'video';
        }
        $dur = max(0, (int)($_POST['dur'] ?? 0));

        // отложенная публикация: минуты от текущего момента
        $delay = max(0, (int)($_POST['delay_min'] ?? 0));
        $sched = $delay > 0 ? date('Y-m-d H:i:s', time() + $delay * 60) : null;

        $pdo->prepare("INSERT INTO msg_channel_posts (channel_id, author_id, text, type, file, filename, dur, scheduled_at)
                       VALUES (?,?,?,?,?,?,?,?)")
            ->execute([$chid, $ME, $text ?: null, $type, $att['file'] ?? null, $att['filename'] ?? null, $dur, $sched]);
        $pid = (int)$pdo->lastInsertId();

        if (!$sched) { ws_publish($chid, ['post_id' => $pid], 'channel_post'); }

        if (!$sched) {
            $cn = $pdo->prepare("SELECT title FROM msg_channels WHERE id = ?"); $cn->execute([$chid]); $ctitle = $cn->fetchColumn();
            $prev = $text !== '' ? mb_substr($text, 0, 100)
                  : ($type === 'image' ? 'Фото' : ($type === 'video' ? 'Видео' : ($type === 'audio' ? 'Голосовое' : 'Файл')));
            $subs = $pdo->prepare("SELECT user_id FROM msg_channel_subs WHERE channel_id = ? AND user_id <> ? AND muted = 0 LIMIT 500");
            $subs->execute([$chid, $ME]);
            foreach ($subs->fetchAll(PDO::FETCH_COLUMN) as $uid) qaz_push_send($pdo, (int)$uid, $ctitle, $prev, 'messenger.php', 'qaz-ch');
        }
        echo json_encode(['ok' => true, 'id' => $pid, 'scheduled' => (bool)$sched]); exit;
    }

    /* ---------- удалить пост / закрепить ---------- */
    if ($action === 'channel_post_delete' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $pid = (int)($d['post'] ?? 0);
        $q = $pdo->prepare("SELECT p.channel_id, s.role FROM msg_channel_posts p
                            LEFT JOIN msg_channel_subs s ON s.channel_id = p.channel_id AND s.user_id = ?
                            WHERE p.id = ?");
        $q->execute([$ME, $pid]); $row = $q->fetch();
        if (!$row || !in_array($row['role'], ['owner', 'admin'], true)) { echo json_encode(['error' => 'no_access']); exit; }
        $pdo->prepare("UPDATE msg_channel_posts SET deleted = 1, text = NULL, file = NULL WHERE id = ?")->execute([$pid]);
        $pdo->prepare("UPDATE msg_channels SET pinned_post = NULL WHERE pinned_post = ?")->execute([$pid]);
        echo json_encode(['ok' => true]); exit;
    }
    if ($action === 'channel_pin' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $chid = (int)($d['channel'] ?? 0); $pid = (int)($d['post'] ?? 0) ?: null;
        $ms = $pdo->prepare("SELECT role FROM msg_channel_subs WHERE channel_id=? AND user_id=?");
        $ms->execute([$chid, $ME]);
        if (!in_array($ms->fetchColumn(), ['owner', 'admin'], true)) { echo json_encode(['error' => 'no_access']); exit; }
        $pdo->prepare("UPDATE msg_channels SET pinned_post = ? WHERE id = ?")->execute([$pid, $chid]);
        echo json_encode(['ok' => true]); exit;
    }

    /* ---------- реакция на пост ---------- */
    if ($action === 'channel_react' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $pid = (int)($d['post'] ?? 0); $emoji = mb_substr(trim($d['emoji'] ?? ''), 0, 8);
        if (!$pid || $emoji === '') { echo json_encode(['error' => 'bad']); exit; }
        $cur = $pdo->prepare("SELECT emoji FROM msg_channel_reacts WHERE post_id = ? AND user_id = ?");
        $cur->execute([$pid, $ME]); $has = $cur->fetchColumn();
        if ($has === $emoji) $pdo->prepare("DELETE FROM msg_channel_reacts WHERE post_id = ? AND user_id = ?")->execute([$pid, $ME]);
        else $pdo->prepare("INSERT INTO msg_channel_reacts (post_id, user_id, emoji) VALUES (?,?,?)
                            ON DUPLICATE KEY UPDATE emoji = VALUES(emoji)")->execute([$pid, $ME, $emoji]);
        echo json_encode(['ok' => true]); exit;
    }

    /* ---------- засчитать просмотр ---------- */
    if ($action === 'channel_view' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $ids = array_slice(array_map('intval', (array)($d['posts'] ?? [])), 0, 50);
        foreach ($ids as $pid) {
            if (!$pid) continue;
            /* просмотр засчитываем только тем, кто имеет доступ к каналу */
            $vc = $pdo->prepare("SELECT c.is_public, s.user_id FROM msg_channel_posts p
                                 JOIN msg_channels c ON c.id = p.channel_id
                                 LEFT JOIN msg_channel_subs s ON s.channel_id = c.id AND s.user_id = ?
                                 WHERE p.id = ? AND p.deleted = 0 AND p.scheduled_at IS NULL");
            $vc->execute([$ME, $pid]); $vi = $vc->fetch();
            if (!$vi || (!(int)$vi['is_public'] && !$vi['user_id'])) continue;
            $ins = $pdo->prepare("INSERT IGNORE INTO msg_channel_views (post_id, user_id) VALUES (?,?)");
            $ins->execute([$pid, $ME]);
            if ($ins->rowCount()) $pdo->prepare("UPDATE msg_channel_posts SET views = views + 1 WHERE id = ?")->execute([$pid]);
        }
        echo json_encode(['ok' => true]); exit;
    }

    /* ---------- настройки канала ---------- */
    if ($action === 'channel_edit' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $chid = (int)($d['channel'] ?? 0);
        $ms = $pdo->prepare("SELECT role FROM msg_channel_subs WHERE channel_id=? AND user_id=?");
        $ms->execute([$chid, $ME]);
        if (!in_array($ms->fetchColumn(), ['owner', 'admin'], true)) { echo json_encode(['error' => 'no_access']); exit; }
        $title = mb_substr(trim($d['title'] ?? ''), 0, 120);
        $about = mb_substr(trim($d['about'] ?? ''), 0, 300);
        if (mb_strlen($title) < 2) { echo json_encode(['error' => 'Введите название']); exit; }
        $pdo->prepare("UPDATE msg_channels SET title = ?, about = ? WHERE id = ?")->execute([$title, $about ?: null, $chid]);
        echo json_encode(['ok' => true]); exit;
    }
    if ($action === 'channel_avatar' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $chid = (int)($_POST['channel'] ?? 0);
        $ms = $pdo->prepare("SELECT role FROM msg_channel_subs WHERE channel_id=? AND user_id=?");
        $ms->execute([$chid, $ME]);
        if (!in_array($ms->fetchColumn(), ['owner', 'admin'], true)) { echo json_encode(['ok' => false]); exit; }
        $img = null;
        if (!empty($_FILES['file']['tmp_name'])) {
            $img = qaz_upload_image($_FILES['file'], 'chav_', 500, 85);
            if (!$img) { $s = qaz_save_chat_file($_FILES['file']); if ($s && $s['type'] === 'image') $img = $s['file']; }
        }
        if ($img) $pdo->prepare("UPDATE msg_channels SET avatar = ? WHERE id = ?")->execute([$img, $chid]);
        echo json_encode(['ok' => (bool)$img, 'avatar' => $img]); exit;
    }
    if ($action === 'channel_mute' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $chid = (int)($d['channel'] ?? 0); $val = !empty($d['val']) ? 1 : 0;
        $pdo->prepare("UPDATE msg_channel_subs SET muted = ? WHERE channel_id = ? AND user_id = ?")->execute([$val, $chid, $ME]);
        echo json_encode(['ok' => true]); exit;
    }

    /* ---------- подписчики (только админ) ---------- */
    if ($action === 'channel_subs') {
        $chid = (int)($_GET['channel'] ?? 0);
        $ms = $pdo->prepare("SELECT role FROM msg_channel_subs WHERE channel_id=? AND user_id=?");
        $ms->execute([$chid, $ME]);
        if (!in_array($ms->fetchColumn(), ['owner', 'admin'], true)) { echo json_encode(['error' => 'no_access']); exit; }
        $q = $pdo->prepare("SELECT u.id, u.name, u.avatar, s.role FROM msg_channel_subs s
                            JOIN qaz_users u ON u.id = s.user_id
                            WHERE s.channel_id = ? ORDER BY FIELD(s.role,'owner','admin','sub'), u.name LIMIT 500");
        $q->execute([$chid]);
        echo json_encode(['ok' => true, 'subs' => $q->fetchAll()], JSON_UNESCAPED_UNICODE); exit;
    }

    /* ---------- поиск публичных каналов ---------- */
    if ($action === 'channel_search') {
        $q = trim($_GET['q'] ?? '');
        if (mb_strlen($q) < 2) { echo json_encode(['channels' => []]); exit; }
        $like = '%' . $q . '%';
        $st = $pdo->prepare("SELECT id, title, username, avatar, subs_count FROM msg_channels
                             WHERE is_public = 1 AND (title LIKE ? OR username LIKE ?)
                             ORDER BY subs_count DESC LIMIT 20");
        $st->execute([$like, $like]);
        echo json_encode(['channels' => $st->fetchAll()], JSON_UNESCAPED_UNICODE); exit;
    }

    /* PAYOM-PACK1 */

    /* --- ПЕРЕСЫЛКА сообщений в другой чат --- */
    if ($action === 'forward' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $to = (int)($d['to'] ?? 0);
        $ids = array_slice(array_map('intval', (array)($d['ids'] ?? [])), 0, 30);
        if (!$to || !$ids || !is_member($pdo, $to, $ME)) { echo json_encode(['error' => 'no_access']); exit; }

        $ok = 0;
        foreach ($ids as $mid) {
            $q = $pdo->prepare("SELECT mm.*, u.name AS sname FROM msg_messages mm LEFT JOIN qaz_users u ON u.id = mm.sender_id WHERE mm.id = ? AND mm.deleted = 0");
            $q->execute([$mid]); $m = $q->fetch();
            if (!$m || !is_member($pdo, (int)$m['chat_id'], $ME)) continue;
            if (!empty($m['once'])) continue;                    // одноразовые не пересылаем
            $fwdFrom = (int)($m['fwd_from'] ?: $m['sender_id']);
            $fwdName = $m['fwd_name'] ?: ($m['sname'] ?: 'Пользователь');
            $pdo->prepare("INSERT INTO msg_messages (chat_id, sender_id, text, type, file, filename, dur, enc, fwd_from, fwd_name)
                           VALUES (?,?,?,?,?,?,?,?,?,?)")
                ->execute([$to, $ME, $m['text'], $m['type'], $m['file'], $m['filename'],
                           (int)$m['dur'], (int)$m['enc'], $fwdFrom, mb_substr($fwdName, 0, 120)]);
            $ok++;
        }
        if ($ok) {
            $lastMid = (int)$pdo->lastInsertId();
            $pdo->prepare("UPDATE msg_members SET last_read_id = ? WHERE chat_id = ? AND user_id = ?")->execute([$lastMid, $to, $ME]);
            $others = $pdo->prepare("SELECT user_id, muted FROM msg_members WHERE chat_id = ? AND user_id <> ?");
            $others->execute([$to, $ME]);
            foreach ($others->fetchAll() as $om) {
                if (!empty($om['muted'])) continue;
                qaz_push_send($pdo, (int)$om['user_id'], $MYNAME, 'Пересланное сообщение', 'messenger.php', 'qaz-msg');
            }
        }
        echo json_encode(['ok' => true, 'sent' => $ok]); exit;
    }

    /* --- ЗАКРЕПИТЬ чат наверху / АРХИВ --- */
    if ($action === 'chat_flag' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $cid = (int)($d['chat'] ?? 0);
        $what = ($d['what'] ?? '') === 'archived' ? 'archived' : 'pinned';
        $val = !empty($d['val']) ? 1 : 0;
        if (!is_member($pdo, $cid, $ME)) { echo json_encode(['error' => 'no_access']); exit; }
        $pdo->prepare("UPDATE msg_members SET `$what` = ? WHERE chat_id = ? AND user_id = ?")->execute([$val, $cid, $ME]);
        echo json_encode(['ok' => true]); exit;
    }

    /* --- ССЫЛКА-ПРИГЛАШЕНИЕ: создать (только админ группы) --- */
    if ($action === 'invite_create' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $cid = (int)($d['chat'] ?? 0);
        if (!is_admin($pdo, $cid, $ME)) { echo json_encode(['error' => 'no_access']); exit; }
        $t = $pdo->prepare("SELECT type, invite_code FROM msg_chats WHERE id = ?"); $t->execute([$cid]); $ch = $t->fetch();
        if (!$ch || $ch['type'] !== 'group') { echo json_encode(['error' => 'not_group']); exit; }
        $code = $ch['invite_code'];
        if (empty($code) || !empty($d['renew'])) {
            do {
                $code = substr(str_replace(['+', '/', '='], '', base64_encode(random_bytes(12))), 0, 14);
                $c = $pdo->prepare("SELECT id FROM msg_chats WHERE invite_code = ?"); $c->execute([$code]);
            } while ($c->fetchColumn());
            $pdo->prepare("UPDATE msg_chats SET invite_code = ? WHERE id = ?")->execute([$code, $cid]);
        }
        echo json_encode(['ok' => true, 'code' => $code]); exit;
    }

    /* --- ССЫЛКА-ПРИГЛАШЕНИЕ: что за группа --- */
    if ($action === 'invite_info') {
        $code = preg_replace('/[^A-Za-z0-9]/', '', $_GET['code'] ?? '');
        if ($code === '') { echo json_encode(['error' => 'bad']); exit; }
        $q = $pdo->prepare("SELECT id, name, avatar, about FROM msg_chats WHERE invite_code = ? AND type = 'group'");
        $q->execute([$code]); $ch = $q->fetch();
        if (!$ch) { echo json_encode(['error' => 'not_found']); exit; }
        $cnt = $pdo->prepare("SELECT COUNT(*) FROM msg_members WHERE chat_id = ?"); $cnt->execute([$ch['id']]);
        $mine = $pdo->prepare("SELECT 1 FROM msg_members WHERE chat_id = ? AND user_id = ?"); $mine->execute([$ch['id'], $ME]);
        echo json_encode(['ok' => true, 'chat_id' => (int)$ch['id'], 'name' => $ch['name'], 'avatar' => $ch['avatar'],
                          'about' => $ch['about'], 'count' => (int)$cnt->fetchColumn(),
                          'member' => (bool)$mine->fetchColumn()], JSON_UNESCAPED_UNICODE); exit;
    }

    /* --- ССЫЛКА-ПРИГЛАШЕНИЕ: вступить --- */
    if ($action === 'invite_join' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $code = preg_replace('/[^A-Za-z0-9]/', '', $d['code'] ?? '');
        $q = $pdo->prepare("SELECT id, name FROM msg_chats WHERE invite_code = ? AND type = 'group'");
        $q->execute([$code]); $ch = $q->fetch();
        if (!$ch) { echo json_encode(['error' => 'not_found']); exit; }
        $cid = (int)$ch['id'];
        if (!is_member($pdo, $cid, $ME)) {
            $pdo->prepare("INSERT IGNORE INTO msg_members (chat_id, user_id) VALUES (?,?)")->execute([$cid, $ME]);
            sys_msg($pdo, $cid, uname($pdo, $ME) . ' присоединился(ась) по ссылке');
        }
        echo json_encode(['ok' => true, 'chat_id' => $cid, 'name' => $ch['name']], JSON_UNESCAPED_UNICODE); exit;
    }

    /* --- ГЛОБАЛЬНЫЙ ПОИСК по всем моим чатам --- */
    if ($action === 'search_all') {
        $q = trim($_GET['q'] ?? '');
        if (mb_strlen($q) < 2) { echo json_encode(['results' => []]); exit; }
        $st = $pdo->prepare("SELECT mm.id, mm.chat_id, mm.text, mm.sender_id, UNIX_TIMESTAMP(mm.created_at) AS ts,
                                    c.type, c.name AS cname, u.name AS sname
                             FROM msg_messages mm
                             JOIN msg_members me ON me.chat_id = mm.chat_id AND me.user_id = ?
                             JOIN msg_chats c ON c.id = mm.chat_id
                             LEFT JOIN qaz_users u ON u.id = mm.sender_id
                             WHERE mm.deleted = 0 AND mm.type = 'text' AND mm.text IS NOT NULL
                             ORDER BY mm.id DESC LIMIT 1200");
        $st->execute([$ME]);
        $ql = mb_strtolower($q); $res = [];
        foreach ($st->fetchAll() as $r) {
            $txt = dec_at_rest($r['text']);
            if ($txt === null || mb_stripos($txt, $ql) === false) continue;
            $title = $r['cname'];
            if ($r['type'] === 'private') {
                $pe = $pdo->prepare("SELECT u.id, u.name, u.avatar FROM msg_members mb JOIN qaz_users u ON u.id = mb.user_id WHERE mb.chat_id = ? AND mb.user_id <> ? LIMIT 1");
                $pe->execute([$r['chat_id'], $ME]); $p = $pe->fetch();
                $title = $p['name'] ?? 'Пользователь';
                $res[] = ['msg_id' => (int)$r['id'], 'chat_id' => (int)$r['chat_id'], 'type' => 'private',
                          'title' => $title, 'peer_id' => (int)($p['id'] ?? 0), 'avatar' => $p['avatar'] ?? '',
                          'sender' => $r['sname'], 'text' => mb_substr($txt, 0, 140), 'ts' => (int)$r['ts']];
            } else {
                $res[] = ['msg_id' => (int)$r['id'], 'chat_id' => (int)$r['chat_id'], 'type' => 'group',
                          'title' => $title, 'peer_id' => 0, 'avatar' => '',
                          'sender' => $r['sname'], 'text' => mb_substr($txt, 0, 140), 'ts' => (int)$r['ts']];
            }
            if (count($res) >= 30) break;
        }
        echo json_encode(['ok' => true, 'results' => $res], JSON_UNESCAPED_UNICODE); exit;
    }


    // поиск пользователей по номеру, имени или @username
    if ($action === 'search') {
        $q = ltrim(trim($_GET['q'] ?? ''), '@');
        if (mb_strlen($q) < 1) { echo json_encode(["users" => []]); exit; }
        $like = '%' . $q . '%';
        /* PAYOM-UPDATE-v2: номер виден только если человек это разрешил */
        $digits = preg_replace('/\D/', '', $q);
        $rows = [];
        if (strlen($digits) >= 9) {
            $st = $pdo->prepare("SELECT id, name, phone, username, avatar, priv_phone FROM qaz_users WHERE phone = ? AND id <> ? AND (deleted IS NULL OR deleted = 0) LIMIT 1");
            $st->execute([mphone($q), $ME]);
            $rows = $st->fetchAll();
        }
        if (!$rows) {
            $st = $pdo->prepare("SELECT id, name, phone, username, avatar, priv_phone FROM qaz_users WHERE (name LIKE ? OR username LIKE ?) AND id <> ? AND (deleted IS NULL OR deleted = 0) ORDER BY name LIMIT 25");
            $st->execute([$like, $like, $ME]);
            $rows = $st->fetchAll();
        }
        $outU = [];
        foreach ($rows as $su) {
            $outU[] = ['id' => (int)$su['id'], 'name' => $su['name'], 'username' => $su['username'],
                       'avatar' => $su['avatar'], 'phone' => phone_visible($pdo, $su, $ME) ? $su['phone'] : ''];
        }
        echo json_encode(['users' => $outU], JSON_UNESCAPED_UNICODE); exit;
    }

    // открыть (или создать) личный чат с пользователем
    if ($action === 'open') {
        $uid = (int)($_GET['user'] ?? 0);
        if (!$uid || $uid === $ME) { echo json_encode(['error' => 'bad']); exit; }
        $st = $pdo->prepare("SELECT c.id FROM msg_chats c
            JOIN msg_members m1 ON m1.chat_id = c.id AND m1.user_id = ?
            JOIN msg_members m2 ON m2.chat_id = c.id AND m2.user_id = ?
            WHERE c.type = 'private' LIMIT 1");
        $st->execute([$ME, $uid]);
        $cid = $st->fetchColumn();
        if (!$cid) {
            $pdo->prepare("INSERT INTO msg_chats (type, created_by) VALUES ('private', ?)")->execute([$ME]);
            $cid = $pdo->lastInsertId();
            $pdo->prepare("INSERT IGNORE INTO msg_members (chat_id, user_id) VALUES (?,?),(?,?)")->execute([$cid, $ME, $cid, $uid]);
        }
        echo json_encode(['chat_id' => (int)$cid]); exit;
    }

    // ===== КОНТАКТЫ =====
    // список контактов
    if ($action === 'contacts_list') {
        $st = $pdo->prepare("SELECT ct.user_id, ct.name AS cname, ct.share_number, u.name AS uname, u.avatar, u.phone, u.last_seen, u.priv_phone, u.priv_lastseen, u.deleted
            FROM msg_contacts ct JOIN qaz_users u ON u.id = ct.user_id
            WHERE ct.owner_id = ? ORDER BY ct.name, u.name");
        $st->execute([$ME]);
        $out = [];
        foreach ($st->fetchAll() as $r) {
            if (!empty($r['deleted'])) continue;
            $out[] = [
                'user_id' => (int)$r['user_id'],
                'name' => ($r['cname'] && trim($r['cname']) !== '') ? $r['cname'] : $r['uname'],
                'avatar' => $r['avatar'],
                'phone' => phone_visible($pdo, $r, $ME) ? $r['phone'] : '',
                'status' => status_text($r['last_seen']),
            ];
        }
        echo json_encode(['contacts' => $out], JSON_UNESCAPED_UNICODE); exit;
    }

    // добавить контакт по номеру телефона (ручное «Создать контакт»)
    if ($action === 'contact_add' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $phone = mphone($d['phone'] ?? '');
        $name = trim(($d['name'] ?? '')); $name = mb_substr($name, 0, 120);
        $note = mb_substr(trim($d['note'] ?? ''), 0, 300);
        $share = !empty($d['share']) ? 1 : 0;
        if (!$phone) { echo json_encode(['error' => 'Введите номер телефона']); exit; }
        $u = $pdo->prepare("SELECT id, name FROM qaz_users WHERE phone = ? AND (deleted IS NULL OR deleted=0) LIMIT 1");
        $u->execute([$phone]); $usr = $u->fetch();
        if (!$usr) { echo json_encode(['error' => 'notfound', 'msg' => 'Пользователь с этим номером не найден в Payom']); exit; }
        if ((int)$usr['id'] === $ME) { echo json_encode(['error' => 'Это ваш номер']); exit; }
        if ($name === '') $name = $usr['name'];
        $pdo->prepare("INSERT INTO msg_contacts (owner_id, user_id, name, note, share_number) VALUES (?,?,?,?,?)
            ON DUPLICATE KEY UPDATE name=VALUES(name), note=VALUES(note), share_number=VALUES(share_number)")
            ->execute([$ME, (int)$usr['id'], $name, $note, $share]);
        $cid = open_private($pdo, $ME, (int)$usr['id']);
        echo json_encode(['ok' => true, 'user_id' => (int)$usr['id'], 'chat_id' => $cid], JSON_UNESCAPED_UNICODE); exit;
    }

    // добавить существующего пользователя в контакты (из чата/профиля)
    if ($action === 'contact_add_user' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $uid = (int)($d['user'] ?? 0);
        $name = mb_substr(trim($d['name'] ?? ''), 0, 120);
        $note = mb_substr(trim($d['note'] ?? ''), 0, 300);
        $share = !empty($d['share']) ? 1 : 0;
        if (!$uid || $uid === $ME) { echo json_encode(['error' => 'bad']); exit; }
        $u = $pdo->prepare("SELECT name FROM qaz_users WHERE id = ? AND (deleted IS NULL OR deleted=0)");
        $u->execute([$uid]); $un = $u->fetchColumn();
        if ($un === false) { echo json_encode(['error' => 'notfound']); exit; }
        if ($name === '') $name = $un;
        $pdo->prepare("INSERT INTO msg_contacts (owner_id, user_id, name, note, share_number) VALUES (?,?,?,?,?)
            ON DUPLICATE KEY UPDATE name=VALUES(name), note=VALUES(note), share_number=VALUES(share_number)")
            ->execute([$ME, $uid, $name, $note, $share]);
        echo json_encode(['ok' => true], JSON_UNESCAPED_UNICODE); exit;
    }

    // удалить из контактов
    if ($action === 'contact_remove' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $uid = (int)($d['user'] ?? 0);
        if ($uid) $pdo->prepare("DELETE FROM msg_contacts WHERE owner_id=? AND user_id=?")->execute([$ME, $uid]);
        echo json_encode(['ok' => true]); exit;
    }

    // сохранить публичный ключ шифрования (E2E). Секретный ключ остаётся на устройстве.
    if ($action === 'key_set' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $pk = trim($d['pubkey'] ?? '');
        if ($pk !== '' && strlen($pk) < 400) $pdo->prepare("UPDATE qaz_users SET pubkey = ? WHERE id = ?")->execute([$pk, $ME]);
        echo json_encode(['ok' => true]); exit;
    }

    // список активных сеансов (устройств)
    if ($action === 'sessions_list') {
        $q = $pdo->prepare("SELECT id, device_id, ua, ip, last_active FROM msg_sessions WHERE user_id=? ORDER BY last_active DESC");
        $q->execute([$ME]); $rows = $q->fetchAll();
        $out = [];
        foreach ($rows as $r) {
            $out[] = ['id' => (int)$r['id'], 'name' => device_name($r['ua']), 'ip' => $r['ip'] ?: '—',
                'last' => status_text($r['last_active']), 'current' => ($r['device_id'] === $DEVICE_ID)];
        }
        echo json_encode(['ok' => true, 'sessions' => $out], JSON_UNESCAPED_UNICODE); exit;
    }
    // завершить один сеанс
    if ($action === 'session_terminate' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $sid = (int)($d['id'] ?? 0);
        if ($sid) $pdo->prepare("DELETE FROM msg_sessions WHERE id=? AND user_id=?")->execute([$sid, $ME]);
        echo json_encode(['ok' => true]); exit;
    }
    // завершить все кроме текущего
    if ($action === 'sessions_terminate_others' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $pdo->prepare("DELETE FROM msg_sessions WHERE user_id=? AND device_id<>?")->execute([$ME, $DEVICE_ID]);
        echo json_encode(['ok' => true]); exit;
    }
    // синяя галочка (только админ)
    if ($action === 'verify_toggle' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        if (!is_site_admin($ME)) { echo json_encode(['error' => 'no_access']); exit; }
        $d = json_decode(file_get_contents('php://input'), true);
        $uid = (int)($d['user'] ?? 0); $val = !empty($d['val']) ? 1 : 0;
        if ($uid) $pdo->prepare("UPDATE qaz_users SET verified=? WHERE id=?")->execute([$val, $uid]);
        echo json_encode(['ok' => true, 'verified' => $val]); exit;
    }

    // автоудаление сообщений в чате (0=выкл, иначе секунды)
    if ($action === 'set_autodelete' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $cid = (int)($d['chat'] ?? 0); $sec = max(0, (int)($d['seconds'] ?? 0));
        if (!is_member($pdo, $cid, $ME)) { echo json_encode(['error' => 'no_access']); exit; }
        $pdo->prepare("UPDATE msg_chats SET auto_delete = ? WHERE id = ?")->execute([$sec, $cid]);
        $labels = [0 => 'выключено', 3600 => '1 час', 86400 => '1 день', 604800 => '1 неделя', 2592000 => '1 месяц', 31536000 => '1 год'];
        $lbl = $labels[$sec] ?? ($sec . ' сек');
        sys_msg($pdo, $cid, uname($pdo, $ME) . ' установил(а) автоудаление: ' . $lbl);
        echo json_encode(['ok' => true]); exit;
    }

    // отметить голосовое как прослушанное (получатель)
    if ($action === 'mark_played' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $mid = (int)($d['id'] ?? 0);
        if ($mid) {
            $m = $pdo->prepare("SELECT chat_id, sender_id FROM msg_messages WHERE id = ?"); $m->execute([$mid]); $mr = $m->fetch();
            if ($mr && (int)$mr['sender_id'] !== $ME && is_member($pdo, (int)$mr['chat_id'], $ME)) {
                $pdo->prepare("UPDATE msg_messages SET played = 1 WHERE id = ?")->execute([$mid]);
            }
        }
        echo json_encode(['ok' => true]); exit;
    }

    // создать группу
    if ($action === 'create_group' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $name = trim($d['name'] ?? '');
        $members = $d['members'] ?? [];
        if ($name === '' || !is_array($members) || !count($members)) { echo json_encode(['error' => 'bad']); exit; }
        $pdo->prepare("INSERT INTO msg_chats (type, name, created_by) VALUES ('group', ?, ?)")->execute([$name, $ME]);
        $cid = $pdo->lastInsertId();
        $pdo->prepare("INSERT IGNORE INTO msg_members (chat_id, user_id, is_admin) VALUES (?,?,1)")->execute([$cid, $ME]);
        $ins = $pdo->prepare("INSERT IGNORE INTO msg_members (chat_id, user_id) VALUES (?,?)");
        foreach ($members as $uid) { $uid = (int)$uid; if ($uid && $uid !== $ME) $ins->execute([$cid, $uid]); }
        sys_msg($pdo, $cid, uname($pdo, $ME) . ' создал(а) группу «' . $name . '»');
        echo json_encode(['chat_id' => (int)$cid]); exit;
    }

    // список моих чатов
    if ($action === 'chats') {
        $st = $pdo->prepare("SELECT c.id, c.type, c.name, m.last_read_id, m.muted, m.pinned, m.archived FROM msg_members m JOIN msg_chats c ON c.id = m.chat_id WHERE m.user_id = ?");
        $st->execute([$ME]);
        $rows = $st->fetchAll();
        /* PAYOM-FAST-CHATS: собираем данные пачкой, а не по запросу на каждый чат */
        $__ids = array_map('intval', array_column($rows, 'id'));
        $__lastBy = []; $__unreadBy = []; $__peerBy = [];
        if ($__ids) {
            $__in = implode(',', $__ids);
            /* последнее сообщение каждого чата — одним запросом */
            $__q = $pdo->prepare("SELECT mm.chat_id, mm.text, mm.type, mm.enc, UNIX_TIMESTAMP(mm.created_at) AS ts,
                                         mm.sender_id, u.name AS sname
                                  FROM msg_messages mm LEFT JOIN qaz_users u ON u.id = mm.sender_id
                                  WHERE mm.id IN (SELECT MAX(id) FROM msg_messages WHERE chat_id IN ($__in) GROUP BY chat_id)");
            $__q->execute();
            foreach ($__q->fetchAll() as $__r) $__lastBy[(int)$__r['chat_id']] = $__r;

            /* непрочитанные по всем чатам — одним запросом */
            $__q2 = $pdo->prepare("SELECT mm.chat_id, COUNT(*) AS c FROM msg_messages mm
                                   JOIN msg_members m ON m.chat_id = mm.chat_id AND m.user_id = ?
                                   WHERE mm.chat_id IN ($__in) AND mm.id > m.last_read_id AND mm.sender_id <> ?
                                   GROUP BY mm.chat_id");
            $__q2->execute([$ME, $ME]);
            foreach ($__q2->fetchAll() as $__r) $__unreadBy[(int)$__r['chat_id']] = (int)$__r['c'];

            /* собеседники личных чатов — одним запросом */
            $__q3 = $pdo->prepare("SELECT mb.chat_id, u.id, u.name, u.avatar, u.verified
                                   FROM msg_members mb JOIN qaz_users u ON u.id = mb.user_id
                                   WHERE mb.chat_id IN ($__in) AND mb.user_id <> ?");
            $__q3->execute([$ME]);
            foreach ($__q3->fetchAll() as $__r) if (!isset($__peerBy[(int)$__r['chat_id']])) $__peerBy[(int)$__r['chat_id']] = $__r;
        }
        $out = [];
        foreach ($rows as $c) {
            $cid = (int)$c['id'];
            // последнее сообщение
            $last = $__lastBy[$cid] ?? null;
            // непрочитанные
            $unread = $__unreadBy[$cid] ?? 0;
            // имя чата + собеседник (для личных)
            $title = $c['name']; $peerId = 0; $avatar = 'G'; $avImg = null; $verified = 0;
            if ($c['type'] === 'private') {
                $peer = $__peerBy[$cid] ?? null;
                $title = $peer['name'] ?? 'Пользователь'; $peerId = (int)($peer['id'] ?? 0); $avImg = $peer['avatar'] ?? null; $verified = (int)($peer['verified'] ?? 0);
                $avatar = mb_strtoupper(mb_substr($title, 0, 1));
            } else { $avatar = mb_strtoupper(mb_substr($title ?: 'Г', 0, 1)); }
            $lastPreview = '';
            if ($last) {
                if (($last['type'] ?? 'text') === 'image') $lastPreview = 'Фото';
                elseif (($last['type'] ?? 'text') === 'video') $lastPreview = 'Видео';
                elseif (($last['type'] ?? 'text') === 'circle') $lastPreview = 'Видео-кружок';
                elseif (($last['type'] ?? 'text') === 'audio') $lastPreview = 'Голосовое';
                elseif (($last['type'] ?? 'text') === 'sticker') $lastPreview = 'Стикер';
                elseif (($last['type'] ?? 'text') === 'file') $lastPreview = 'Файл';
                elseif (!empty($last['enc'])) $lastPreview = 'Сообщение';
                else $lastPreview = dec_at_rest($last['text'] ?? '');
            }
            $out[] = [
                'id' => $cid, 'type' => $c['type'], 'title' => $title, 'peer_id' => $peerId, 'avatar' => $avatar, 'avatar_img' => $avImg,
                'last' => $lastPreview,
                'last_sender' => $last['sname'] ?? '', 'last_me' => $last && (int)$last['sender_id'] === $ME,
                'ts' => $last ? (int)$last['ts'] : 0, 'unread' => $unread, 'verified' => $verified, 'muted' => (int)($c['muted'] ?? 0)
            ];
        }
        /* PAYOM-PACK1: закреплённые наверху, архив отдельно */
        $wantArch = !empty($_GET['arch']);
        $archCnt = 0;
        foreach ($out as $oc) if (!empty($oc['archived'])) $archCnt++;
        $out = array_values(array_filter($out, function($c) use ($wantArch) { return $wantArch ? !empty($c['archived']) : empty($c['archived']); }));
        usort($out, function($a, $b) { if (($b['pinned'] ?? 0) !== ($a['pinned'] ?? 0)) return ($b['pinned'] ?? 0) - ($a['pinned'] ?? 0); return $b['ts'] - $a['ts']; });
        echo json_encode(['chats' => $out, 'me' => $ME, 'myname' => $MYNAME, 'archived_count' => $archCnt], JSON_UNESCAPED_UNICODE); exit;
    }

    // сообщения чата
    if ($action === 'messages') {
        $cid = (int)($_GET['chat'] ?? 0);
        if (!is_member($pdo, $cid, $ME)) { echo json_encode(['error' => 'no_access']); exit; }
        $ci = $pdo->prepare("SELECT * FROM msg_chats WHERE id = ?"); $ci->execute([$cid]); $chat = $ci->fetch();
        $autoDel = (int)($chat['auto_delete'] ?? 0);
        if ($autoDel > 0) { $pdo->prepare("DELETE FROM msg_messages WHERE chat_id = ? AND type <> 'system' AND created_at < (NOW() - INTERVAL " . (int)$autoDel . " SECOND)")->execute([$cid]); }
        $title = $chat['name']; $peerId = 0; $status = ''; $peerCanCall = false; $peerPubkey = null; $peerVerified = 0;
        if ($chat['type'] === 'private') {
            $pe = $pdo->prepare("SELECT u.id, u.name, u.last_seen, u.priv_lastseen, u.priv_calls, u.pubkey, u.verified FROM msg_members mb JOIN qaz_users u ON u.id = mb.user_id WHERE mb.chat_id = ? AND mb.user_id <> ? LIMIT 1");
            $pe->execute([$cid, $ME]); $peer = $pe->fetch(); $title = $peer['name'] ?? 'Пользователь'; $peerId = (int)($peer['id'] ?? 0);
            $peerPubkey = $peer['pubkey'] ?? null; $peerVerified = (int)($peer['verified'] ?? 0);
            if (($peer['priv_lastseen'] ?? 'all') === 'nobody') {
                $online = $peer['last_seen'] && (strtotime($peer['last_seen']) > time() - 65);
                $status = $online ? 'в сети' : 'был(а) недавно';
            } else $status = status_text($peer['last_seen'] ?? null);
            // может ли звонить: собеседник разрешает звонки и не заблокировал меня
            $blk = $pdo->prepare("SELECT 1 FROM msg_blocks WHERE blocker_id = ? AND blocked_id = ?"); $blk->execute([$peerId, $ME]);
            $peerCanCall = (($peer['priv_calls'] ?? 'all') !== 'nobody') && !$blk->fetchColumn();
        } else {
            // группа: сколько участников и сколько в сети
            $cnt = (int)$pdo->query("SELECT COUNT(*) FROM msg_members WHERE chat_id = " . (int)$cid)->fetchColumn();
            $online = (int)$pdo->query("SELECT COUNT(*) FROM msg_members mb JOIN qaz_users u ON u.id = mb.user_id WHERE mb.chat_id = " . (int)$cid . " AND u.last_seen > (NOW() - INTERVAL 65 SECOND)")->fetchColumn();
            $status = $cnt . ' участник(ов)' . ($online > 0 ? ', ' . $online . ' в сети' : '');
        }
        $st = $pdo->prepare("SELECT mm.id, mm.sender_id, mm.text, mm.type, mm.file, mm.filename, mm.reply_to, mm.edited, mm.deleted, mm.dur, mm.once, mm.viewed, mm.enc, mm.played, mm.story_ref, mm.fwd_from, mm.fwd_name,
            UNIX_TIMESTAMP(mm.created_at) AS ts, u.name AS sname, u.avatar AS savatar,
            r.text AS r_text, r.type AS r_type, ru.name AS r_name,
            ms.file AS story_file, ms.type AS story_mtype, (ms.expires_at >= NOW()) AS story_alive
            FROM msg_messages mm
            LEFT JOIN qaz_users u ON u.id = mm.sender_id
            LEFT JOIN msg_messages r ON r.id = mm.reply_to
            LEFT JOIN qaz_users ru ON ru.id = r.sender_id
            LEFT JOIN msg_stories ms ON ms.id = mm.story_ref
            WHERE mm.chat_id = ? ORDER BY mm.id DESC LIMIT 300");
        $st->execute([$cid]);
        $msgs = array_reverse($st->fetchAll());
        // реакции
        $rx = $pdo->prepare("SELECT message_id, emoji, COUNT(*) AS cnt, MAX(CASE WHEN user_id = ? THEN 1 ELSE 0 END) AS mine
            FROM msg_reactions WHERE message_id IN (" . ($msgs ? implode(',', array_map('intval', array_column($msgs, 'id'))) : '0') . ") GROUP BY message_id, emoji");
        $rx->execute([$ME]);
        $reacts = [];
        foreach ($rx->fetchAll() as $rr) { $reacts[$rr['message_id']][] = ['emoji' => $rr['emoji'], 'cnt' => (int)$rr['cnt'], 'mine' => (int)$rr['mine']]; }
        foreach ($msgs as &$mrow) { $mrow['reactions'] = $reacts[$mrow['id']] ?? []; } unset($mrow);
        // расшифровка текста «из базы» (at-rest) — для показа в чате
        foreach ($msgs as &$mrow) {
            if (isset($mrow['text']) && $mrow['text'] !== null) $mrow['text'] = dec_at_rest($mrow['text']);
            if (isset($mrow['r_text']) && $mrow['r_text'] !== null) $mrow['r_text'] = dec_at_rest($mrow['r_text']);
        } unset($mrow);
        // печатает
        $tp = $pdo->prepare("SELECT u.name FROM msg_typing t JOIN qaz_users u ON u.id = t.user_id WHERE t.chat_id = ? AND t.user_id <> ? AND t.updated_at > (NOW() - INTERVAL 6 SECOND)");
        $tp->execute([$cid, $ME]);
        $typing = $tp->fetchAll(PDO::FETCH_COLUMN);
        // закреплённое
        $pinned = null;
        if (!empty($chat['pinned_msg'])) {
            $pm = $pdo->prepare("SELECT mm.id, mm.text, mm.type, u.name FROM msg_messages mm LEFT JOIN qaz_users u ON u.id = mm.sender_id WHERE mm.id = ? AND mm.deleted = 0");
            $pm->execute([$chat['pinned_msg']]); $pinned = $pm->fetch() ?: null;
            if ($pinned && isset($pinned['text'])) $pinned['text'] = dec_at_rest($pinned['text']);
        }
        if ($msgs) {
            $lastId = (int)$msgs[count($msgs) - 1]['id'];
            $pdo->prepare("UPDATE msg_members SET last_read_id = ? WHERE chat_id = ? AND user_id = ? AND last_read_id < ?")->execute([$lastId, $cid, $ME, $lastId]);
        }
        $peerRead = 0;
        if ($chat['type'] === 'private' && $peerId) {
            $pr = $pdo->prepare("SELECT last_read_id FROM msg_members WHERE chat_id = ? AND user_id = ?"); $pr->execute([$cid, $peerId]);
            $peerRead = (int)$pr->fetchColumn();
        }
        echo json_encode([
            'ok' => true, 'me' => $ME, 'type' => $chat['type'], 'title' => $title, 'peer_id' => $peerId,
            'status' => $status, 'peer_read' => $peerRead, 'messages' => $msgs,
            'typing' => $typing, 'pinned' => $pinned, 'peer_can_call' => $peerCanCall, 'peer_pubkey' => $peerPubkey, 'auto_delete' => $autoDel, 'peer_verified' => $peerVerified
        ], JSON_UNESCAPED_UNICODE); exit;
    }

    // отправить сообщение (текст / фото / голос / файл, с ответом)
    if ($action === 'send' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $cid = (int)($_POST['chat'] ?? 0);
        $text = trim($_POST['text'] ?? '');
        $reply = (int)($_POST['reply_to'] ?? 0) ?: null;
        if (!is_member($pdo, $cid, $ME)) { echo json_encode(['error' => 'no_access']); exit; }
        // если личный чат и собеседник меня заблокировал — не отправляем
        $ct = $pdo->prepare("SELECT type FROM msg_chats WHERE id = ?"); $ct->execute([$cid]);
        if ($ct->fetchColumn() === 'private') {
            $peerB = $pdo->prepare("SELECT mb.user_id FROM msg_members mb WHERE mb.chat_id = ? AND mb.user_id <> ? LIMIT 1"); $peerB->execute([$cid, $ME]); $pid = (int)$peerB->fetchColumn();
            if ($pid) { $bq = $pdo->prepare("SELECT 1 FROM msg_blocks WHERE blocker_id = ? AND blocked_id = ?"); $bq->execute([$pid, $ME]); if ($bq->fetchColumn()) { echo json_encode(['error' => 'blocked']); exit; } }
        }
        $att = !empty($_FILES['file']['tmp_name']) ? qaz_save_chat_file($_FILES['file']) : null;
        if ($text === '' && !$att) { echo json_encode(['error' => 'empty']); exit; }
        if (mb_strlen($text) > 4000) $text = mb_substr($text, 0, 4000);
        $type = $att ? $att['type'] : 'text';
        // распознаём видео (qaz_save_chat_file помечает его как file)
        if ($att && $type === 'file') {
            $ext = strtolower(pathinfo($att['filename'] ?? $att['file'], PATHINFO_EXTENSION));
            if (in_array($ext, ['mp4', 'mov', 'm4v', 'webm', '3gp', 'avi', 'mkv'])) $type = 'video';
        }
        // видео-кружок
        if ($att && !empty($_POST['circle'])) $type = 'circle';
        /* Защита от флуда: не больше 12 сообщений за 10 секунд.
           Живой человек столько не отправит, а скрипт отсекается. */
        $fl = $pdo->prepare("SELECT COUNT(*) FROM msg_messages
                             WHERE sender_id = ? AND created_at > (NOW() - INTERVAL 10 SECOND)");
        $fl->execute([$ME]);
        if ((int)$fl->fetchColumn() >= 12) { echo json_encode(['error' => 'flood']); exit; }

        $dur = (int)($_POST['dur'] ?? 0);
        $once = !empty($_POST['once']) ? 1 : 0;
        $enc = !empty($_POST['enc']) ? 1 : 0;
        // для шифрованных медиа тип приходит от клиента (файл — шифр, определить нельзя)
        $mediaType = $_POST['media_type'] ?? '';
        if ($enc && $att && in_array($mediaType, ['image', 'audio', 'video', 'circle', 'file'])) $type = $mediaType;
        $pdo->prepare("INSERT INTO msg_messages (chat_id, sender_id, text, type, file, filename, reply_to, dur, once, enc) VALUES (?,?,?,?,?,?,?,?,?,?)")
            ->execute([$cid, $ME, enc_at_rest($text ?: null), $type, $att['file'] ?? null, $att['filename'] ?? null, $reply, $dur, $once, $enc]);
        $mid = $pdo->lastInsertId();
        $pdo->prepare("UPDATE msg_members SET last_read_id = ? WHERE chat_id = ? AND user_id = ?")->execute([$mid, $cid, $ME]);
        /* мгновенно уведомляем всех, кто открыл этот чат */
        ws_publish($cid, ['id' => (int)$mid, 'sender_id' => $ME, 'sender' => $MYNAME]);
        // превью для списка/пуша: у шифрованных не показываем содержимое
        if ($enc && $text !== '') $preview = 'Сообщение';
        else $preview = $text !== '' ? mb_substr($text, 0, 100) : ($type === 'image' ? 'Фото' : ($type === 'video' ? 'Видео' : ($type === 'circle' ? 'Видео-кружок' : ($type === 'audio' ? 'Голосовое' : ($type === 'sticker' ? 'Стикер' : 'Файл')))));
        // упоминания @username в группе → отдельное уведомление (даже если чат в тихом режиме)
        $mentionIds = [];
        if ($text !== '' && strpos($text, '@') !== false && preg_match_all('/@([A-Za-z0-9_]{3,32})/u', $text, $mm2)) {
            $unames = array_values(array_unique($mm2[1]));
            if ($unames) {
                $ph = implode(',', array_fill(0, count($unames), '?'));
                $mq = $pdo->prepare("SELECT u.id FROM msg_members m JOIN qaz_users u ON u.id = m.user_id WHERE m.chat_id = ? AND u.username IN ($ph) AND u.id <> ?");
                $mq->execute(array_merge([$cid], $unames, [$ME]));
                foreach ($mq->fetchAll(PDO::FETCH_COLUMN) as $mid2) $mentionIds[(int)$mid2] = true;
            }
        }
        $chatName = '';
        if ($mentionIds) { $cn = $pdo->prepare("SELECT name FROM msg_chats WHERE id = ?"); $cn->execute([$cid]); $chatName = $cn->fetchColumn() ?: 'группе'; }
        $others = $pdo->prepare("SELECT user_id, muted FROM msg_members WHERE chat_id = ? AND user_id <> ?");
        $others->execute([$cid, $ME]);
        foreach ($others->fetchAll() as $om) {
            $uid2 = (int)$om['user_id'];
            if (isset($mentionIds[$uid2])) { qaz_push_send($pdo, $uid2, $MYNAME . ' упомянул вас в «' . $chatName . '»', $preview, 'messenger.php', 'qaz-msg'); continue; }
            if (!empty($om['muted'])) continue;
            qaz_push_send($pdo, $uid2, $MYNAME, $preview, 'messenger.php', 'qaz-msg');
        }
        echo json_encode(['ok' => true, 'id' => (int)$mid]); exit;
    }

    // загрузить свой аватар
    if ($action === 'avatar' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $img = null;
        if (!empty($_FILES['file']['tmp_name'])) {
            $img = qaz_upload_image($_FILES['file'], 'ava_', 500, 85);   // обычные форматы (сжатие)
            if (!$img) { $saved = qaz_save_chat_file($_FILES['file']); if ($saved && $saved['type'] === 'image') $img = $saved['file']; } // запас (HEIC и пр.)
        }
        if ($img) $pdo->prepare("UPDATE qaz_users SET avatar = ? WHERE id = ?")->execute([$img, $ME]);
        echo json_encode(['ok' => (bool)$img, 'avatar' => $img]); exit;
    }

    // живая проверка username (свободен/занят)
    if ($action === 'username_check') {
        $u = ltrim(trim($_GET['u'] ?? ''), '@');
        $u = preg_replace('/[^A-Za-z0-9_]/', '', $u);
        if ($u === '') { echo json_encode(['state' => 'empty']); exit; }
        if (mb_strlen($u) < 3) { echo json_encode(['state' => 'short', 'clean' => $u]); exit; }
        $ck = $pdo->prepare("SELECT id FROM qaz_users WHERE username = ? AND id <> ?");
        $ck->execute([$u, $ME]);
        echo json_encode(['state' => $ck->fetch() ? 'taken' : 'free', 'clean' => $u], JSON_UNESCAPED_UNICODE); exit;
    }

    // мой профиль
    if ($action === 'profile_get') {
        $st = $pdo->prepare("SELECT id, name, phone, username, bio, avatar, birthday, priv_lastseen, priv_calls, priv_phone FROM qaz_users WHERE id = ?");
        $st->execute([$ME]);
        echo json_encode(['profile' => $st->fetch()], JSON_UNESCAPED_UNICODE); exit;
    }

    // сохранить профиль
    if ($action === 'profile_save' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $name = trim($d['name'] ?? ''); $bio = trim($d['bio'] ?? '');
        $username = ltrim(trim($d['username'] ?? ''), '@');
        $username = preg_replace('/[^A-Za-z0-9_]/', '', $username);
        $birthday = trim($d['birthday'] ?? '');
        $birthday = preg_match('/^\d{4}-\d{2}-\d{2}$/', $birthday) ? $birthday : null;
        $pls = in_array($d['priv_lastseen'] ?? 'all', ['all', 'nobody']) ? $d['priv_lastseen'] : 'all';
        $pc = in_array($d['priv_calls'] ?? 'all', ['all', 'nobody']) ? $d['priv_calls'] : 'all';
        $pp = in_array($d['priv_phone'] ?? 'all', ['all', 'nobody']) ? $d['priv_phone'] : 'all';
        if (mb_strlen($name) < 1) { echo json_encode(['error' => 'Введите имя']); exit; }
        if ($username !== '') {
            $ck = $pdo->prepare("SELECT id FROM qaz_users WHERE username = ? AND id <> ?"); $ck->execute([$username, $ME]);
            if ($ck->fetch()) { echo json_encode(['error' => 'Этот username занят']); exit; }
        }
        $pdo->prepare("UPDATE qaz_users SET name = ?, username = ?, bio = ?, birthday = ?, priv_lastseen = ?, priv_calls = ?, priv_phone = ? WHERE id = ?")
            ->execute([mb_substr($name, 0, 100), $username ?: null, mb_substr($bio, 0, 300), $birthday, $pls, $pc, $pp, $ME]);
        $_SESSION['user_name'] = mb_substr($name, 0, 100);
        echo json_encode(['ok' => true]); exit;
    }

    // ссылка на сообщение: найти чат (если я участник)
    if ($action === 'msg_locate') {
        $mid = (int)($_GET['id'] ?? 0);
        $q = $pdo->prepare("SELECT chat_id FROM msg_messages WHERE id = ? AND deleted = 0"); $q->execute([$mid]); $cid = (int)$q->fetchColumn();
        if (!$cid || !is_member($pdo, $cid, $ME)) { echo json_encode(['error' => 'no_access']); exit; }
        $c = $pdo->prepare("SELECT type, name FROM msg_chats WHERE id = ?"); $c->execute([$cid]); $ch = $c->fetch();
        $peerId = 0; $title = $ch['name']; $avatar = '';
        if ($ch['type'] === 'private') {
            $pe = $pdo->prepare("SELECT u.id, u.name, u.avatar FROM msg_members mb JOIN qaz_users u ON u.id = mb.user_id WHERE mb.chat_id = ? AND mb.user_id <> ? LIMIT 1"); $pe->execute([$cid, $ME]); $p = $pe->fetch();
            $peerId = (int)($p['id'] ?? 0); $title = $p['name'] ?? 'Пользователь'; $avatar = $p['avatar'] ?? '';
        }
        echo json_encode(['ok' => true, 'chat_id' => $cid, 'type' => $ch['type'], 'peer_id' => $peerId, 'title' => $title, 'avatar' => $avatar, 'msg_id' => $mid], JSON_UNESCAPED_UNICODE); exit;
    }
    // ссылка на профиль по username: вернуть id
    if ($action === 'uid_by_username') {
        $un = preg_replace('/[^A-Za-z0-9_]/', '', ltrim(trim($_GET['u'] ?? ''), '@'));
        if ($un === '') { echo json_encode(['error' => 'bad']); exit; }
        $q = $pdo->prepare("SELECT id FROM qaz_users WHERE username = ? AND (deleted IS NULL OR deleted = 0)"); $q->execute([$un]);
        echo json_encode(['ok' => true, 'id' => (int)$q->fetchColumn()]); exit;
    }
    // участники группы для @-подсказок
    if ($action === 'mention_members') {
        $cid = (int)($_GET['chat'] ?? 0);
        if (!is_member($pdo, $cid, $ME)) { echo json_encode(['members' => []]); exit; }
        $ms = $pdo->prepare("SELECT u.id, u.name, u.username, u.avatar FROM msg_members m JOIN qaz_users u ON u.id = m.user_id WHERE m.chat_id = ? AND u.id <> ? AND (u.deleted IS NULL OR u.deleted = 0) ORDER BY u.name LIMIT 300");
        $ms->execute([$cid, $ME]);
        echo json_encode(['members' => $ms->fetchAll(PDO::FETCH_ASSOC)], JSON_UNESCAPED_UNICODE); exit;
    }

    // ===== СТИКЕРЫ =====
    if ($action === 'sticker_packs_my') {
        $ps = $pdo->prepare("SELECT p.id, p.title, p.slug, p.owner_id FROM msg_sticker_packs p WHERE p.owner_id = ? OR p.id IN (SELECT pack_id FROM msg_user_packs WHERE user_id = ?) ORDER BY p.id DESC");
        $ps->execute([$ME, $ME]); $packs = $ps->fetchAll(PDO::FETCH_ASSOC);
        foreach ($packs as &$p) {
            $ss = $pdo->prepare("SELECT id, file, mtype FROM msg_stickers WHERE pack_id = ? ORDER BY ord, id"); $ss->execute([$p['id']]);
            $p['stickers'] = $ss->fetchAll(PDO::FETCH_ASSOC); $p['owner'] = ((int)$p['owner_id'] === $ME);
        } unset($p);
        echo json_encode(['packs' => $packs], JSON_UNESCAPED_UNICODE); exit;
    }
    if ($action === 'sticker_pack_create' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $title = mb_substr(trim($d['title'] ?? ''), 0, 80);
        if ($title === '') { echo json_encode(['error' => 'Введите название']); exit; }
        $slug = substr(preg_replace('/[^a-z0-9]+/', '', strtolower($title)), 0, 40); if ($slug === '') $slug = 'pack';
        $orig = $slug; $i = 0;
        while (true) { $chk = $pdo->prepare("SELECT id FROM msg_sticker_packs WHERE slug = ?"); $chk->execute([$slug]); if (!$chk->fetchColumn()) break; $slug = $orig . (++$i); }
        $pdo->prepare("INSERT INTO msg_sticker_packs (owner_id, title, slug) VALUES (?,?,?)")->execute([$ME, $title, $slug]);
        $pid = (int)$pdo->lastInsertId();
        $pdo->prepare("INSERT IGNORE INTO msg_user_packs (user_id, pack_id) VALUES (?,?)")->execute([$ME, $pid]);
        echo json_encode(['ok' => true, 'id' => $pid, 'slug' => $slug, 'title' => $title]); exit;
    }
    if ($action === 'sticker_add' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $pid = (int)($_POST['pack'] ?? 0);
        $own = $pdo->prepare("SELECT owner_id FROM msg_sticker_packs WHERE id = ?"); $own->execute([$pid]);
        if ((int)$own->fetchColumn() !== $ME) { echo json_encode(['error' => 'Нет доступа']); exit; }
        $saved = !empty($_FILES['file']['tmp_name']) ? qaz_save_chat_file($_FILES['file']) : null;
        if (!$saved) { echo json_encode(['error' => 'Не удалось загрузить']); exit; }
        $ext = strtolower(pathinfo($saved['file'], PATHINFO_EXTENSION));
        $mtype = in_array($ext, ['mp4','webm','mov','m4v']) ? 'video' : 'image';
        $pdo->prepare("INSERT INTO msg_stickers (pack_id, file, mtype) VALUES (?,?,?)")->execute([$pid, $saved['file'], $mtype]);
        echo json_encode(['ok' => true, 'id' => (int)$pdo->lastInsertId(), 'file' => $saved['file'], 'mtype' => $mtype]); exit;
    }
    if ($action === 'sticker_del') {
        $d = json_decode(file_get_contents('php://input'), true); $sid = (int)($d['id'] ?? 0);
        $q = $pdo->prepare("SELECT p.owner_id FROM msg_stickers s JOIN msg_sticker_packs p ON p.id = s.pack_id WHERE s.id = ?"); $q->execute([$sid]);
        if ((int)$q->fetchColumn() === $ME) $pdo->prepare("DELETE FROM msg_stickers WHERE id = ?")->execute([$sid]);
        echo json_encode(['ok' => true]); exit;
    }
    if ($action === 'sticker_pack_get') {
        $slug = preg_replace('/[^a-z0-9]+/', '', strtolower($_GET['slug'] ?? ''));
        $p = $pdo->prepare("SELECT id, title, slug, owner_id FROM msg_sticker_packs WHERE slug = ?"); $p->execute([$slug]);
        $pack = $p->fetch(PDO::FETCH_ASSOC); if (!$pack) { echo json_encode(['error' => 'not_found']); exit; }
        $ss = $pdo->prepare("SELECT id, file, mtype FROM msg_stickers WHERE pack_id = ? ORDER BY ord, id"); $ss->execute([$pack['id']]);
        $pack['stickers'] = $ss->fetchAll(PDO::FETCH_ASSOC);
        $has = $pdo->prepare("SELECT 1 FROM msg_user_packs WHERE user_id = ? AND pack_id = ?"); $has->execute([$ME, $pack['id']]);
        $pack['added'] = (bool)$has->fetchColumn() || ((int)$pack['owner_id'] === $ME);
        echo json_encode(['pack' => $pack], JSON_UNESCAPED_UNICODE); exit;
    }
    if ($action === 'sticker_pack_add' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $slug = preg_replace('/[^a-z0-9]+/', '', strtolower($d['slug'] ?? ''));
        $p = $pdo->prepare("SELECT id FROM msg_sticker_packs WHERE slug = ?"); $p->execute([$slug]); $pid = (int)$p->fetchColumn();
        if (!$pid) { echo json_encode(['error' => 'not_found']); exit; }
        $pdo->prepare("INSERT IGNORE INTO msg_user_packs (user_id, pack_id) VALUES (?,?)")->execute([$ME, $pid]);
        echo json_encode(['ok' => true]); exit;
    }
    if ($action === 'sticker_pack_remove' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $pid = (int)($d['pack'] ?? 0);
        $pdo->prepare("DELETE FROM msg_user_packs WHERE user_id = ? AND pack_id = ?")->execute([$ME, $pid]);
        echo json_encode(['ok' => true]); exit;
    }
    if ($action === 'sticker_send' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $cid = (int)($d['chat'] ?? 0); $sid = (int)($d['sticker'] ?? 0);
        if (!is_member($pdo, $cid, $ME)) { echo json_encode(['error' => 'no_access']); exit; }
        $s = $pdo->prepare("SELECT file, mtype FROM msg_stickers WHERE id = ?"); $s->execute([$sid]); $st = $s->fetch();
        if (!$st) { echo json_encode(['error' => 'not_found']); exit; }
        $pdo->prepare("INSERT INTO msg_messages (chat_id, sender_id, type, file, filename) VALUES (?,?,?,?,?)")->execute([$cid, $ME, 'sticker', $st['file'], $st['mtype']]);
        $mid = (int)$pdo->lastInsertId();
        $mn = $pdo->prepare("SELECT name FROM qaz_users WHERE id = ?"); $mn->execute([$ME]); $MYNAME = $mn->fetchColumn() ?: 'Пользователь';
        $others = $pdo->prepare("SELECT user_id, muted FROM msg_members WHERE chat_id = ? AND user_id <> ?"); $others->execute([$cid, $ME]);
        foreach ($others->fetchAll() as $om) { if (!empty($om['muted'])) continue; qaz_push_send($pdo, (int)$om['user_id'], $MYNAME, 'Стикер', 'messenger.php', 'qaz-msg'); }
        echo json_encode(['ok' => true, 'id' => $mid]); exit;
    }

    if ($action === 'sticker_pack_by_file') {
        $file = $_GET['file'] ?? '';
        $q = $pdo->prepare("SELECT p.id, p.title, p.slug, p.owner_id FROM msg_stickers s JOIN msg_sticker_packs p ON p.id = s.pack_id WHERE s.file = ? LIMIT 1");
        $q->execute([$file]); $pack = $q->fetch(PDO::FETCH_ASSOC);
        if (!$pack) { echo json_encode(['error' => 'not_found']); exit; }
        $ss = $pdo->prepare("SELECT id, file, mtype FROM msg_stickers WHERE pack_id = ? ORDER BY ord, id"); $ss->execute([$pack['id']]);
        $pack['stickers'] = $ss->fetchAll(PDO::FETCH_ASSOC);
        $has = $pdo->prepare("SELECT 1 FROM msg_user_packs WHERE user_id = ? AND pack_id = ?"); $has->execute([$ME, $pack['id']]);
        $pack['owner'] = ((int)$pack['owner_id'] === $ME);
        $pack['added'] = (bool)$has->fetchColumn() || $pack['owner'];
        echo json_encode(['pack' => $pack], JSON_UNESCAPED_UNICODE); exit;
    }

    // публичный профиль пользователя (для тапа в группе)
    if ($action === 'user_profile') {
        $uid = (int)($_GET['user'] ?? 0);
        if (!$uid) { echo json_encode(['error' => 'bad']); exit; }
        $st = $pdo->prepare("SELECT id, name, avatar, username, bio, phone, last_seen, priv_lastseen, priv_phone, priv_calls, deleted, verified FROM qaz_users WHERE id = ?");
        $st->execute([$uid]); $u = $st->fetch();
        if (!$u) { echo json_encode(['error' => 'notfound']); exit; }
        if (!empty($u['deleted'])) {
            echo json_encode(['ok' => true, 'profile' => ['id' => (int)$u['id'], 'name' => 'Пользователь Payom', 'avatar' => null, 'username' => null, 'bio' => null, 'status' => 'аккаунт удалён', 'blocked' => false, 'is_me' => false, 'has_story' => false, 'deleted' => true]], JSON_UNESCAPED_UNICODE); exit;
        }
        $status = (($u['priv_lastseen'] ?? 'all') === 'nobody') ? (($u['last_seen'] && strtotime($u['last_seen']) > time() - 65) ? 'в сети' : 'был(а) недавно') : status_text($u['last_seen']);
        $blk = $pdo->prepare("SELECT 1 FROM msg_blocks WHERE blocker_id = ? AND blocked_id = ?"); $blk->execute([$ME, $uid]);
        // моё имя для этого контакта (если добавлен)
        $cn = contact_name($pdo, $ME, $uid);
        $isContact = ($cn !== null) || (function() use ($pdo, $ME, $uid) { $q=$pdo->prepare("SELECT 1 FROM msg_contacts WHERE owner_id=? AND user_id=?"); $q->execute([$ME,$uid]); return (bool)$q->fetchColumn(); })();
        $prof = ['id' => (int)$u['id'], 'name' => $cn ?: $u['name'], 'real_name' => $u['name'], 'avatar' => $u['avatar'], 'username' => $u['username'], 'bio' => $u['bio'], 'status' => $status, 'blocked' => (bool)$blk->fetchColumn(), 'is_me' => ($uid === $ME), 'is_contact' => $isContact, 'verified' => (int)($u['verified'] ?? 0), 'viewer_admin' => is_site_admin($ME)];
        // номер: показываем если видно, иначе помечаем «Скрыт»
        if (phone_visible($pdo, $u, $ME)) { $prof['phone'] = $u['phone']; $prof['phone_hidden'] = false; }
        else { $prof['phone'] = ''; $prof['phone_hidden'] = true; }
        // есть ли активная история, видимая мне
        $hasStory = false;
        $sst = $pdo->prepare("SELECT * FROM msg_stories WHERE user_id=? AND expires_at>=NOW() ORDER BY id");
        $sst->execute([$uid]);
        foreach ($sst->fetchAll() as $srow) { if (story_visible($pdo, $srow, $ME)) { $hasStory = true; break; } }
        $prof['has_story'] = $hasStory;
        echo json_encode(['ok' => true, 'profile' => $prof], JSON_UNESCAPED_UNICODE); exit;
    }

    // заблокировать / разблокировать
    if ($action === 'block' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $uid = (int)($d['user'] ?? 0);
        if ($uid && $uid !== $ME) $pdo->prepare("INSERT IGNORE INTO msg_blocks (blocker_id, blocked_id) VALUES (?,?)")->execute([$ME, $uid]);
        echo json_encode(['ok' => true]); exit;
    }
    if ($action === 'unblock' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $uid = (int)($d['user'] ?? 0);
        if ($uid) $pdo->prepare("DELETE FROM msg_blocks WHERE blocker_id = ? AND blocked_id = ?")->execute([$ME, $uid]);
        echo json_encode(['ok' => true]); exit;
    }
    if ($action === 'blocked_list') {
        $st = $pdo->prepare("SELECT u.id, u.name, u.phone, u.avatar FROM msg_blocks b JOIN qaz_users u ON u.id = b.blocked_id WHERE b.blocker_id = ? ORDER BY u.name");
        $st->execute([$ME]);
        echo json_encode(['users' => $st->fetchAll()], JSON_UNESCAPED_UNICODE); exit;
    }

    // выйти на всех устройствах
    if ($action === 'logout_all' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $pdo->prepare("UPDATE qaz_users SET remember_token = NULL WHERE id = ?")->execute([$ME]);
        setcookie('qaz_r', '', ['expires' => time() - 3600, 'path' => '/']);
        session_destroy();
        echo json_encode(['ok' => true]); exit;
    }

    // удалить аккаунт
    if ($action === 'delete_account' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        try {
            // мягкое удаление: чаты и сообщения у собеседников остаются,
            // но профиль и имя показываются как «Пользователь Payom»
            $pdo->prepare("UPDATE qaz_users SET deleted=1, name='Пользователь Payom', avatar=NULL, username=NULL, bio=NULL, birthday=NULL, face_descriptor=NULL, tg_chat_id=NULL, remember_token=NULL, phone=CONCAT('deleted_', id) WHERE id = ?")->execute([$ME]);
            $pdo->prepare("DELETE FROM msg_stories WHERE user_id = ?")->execute([$ME]);
            $pdo->prepare("DELETE FROM msg_story_views WHERE user_id = ?")->execute([$ME]);
            $pdo->prepare("DELETE FROM msg_blocks WHERE blocker_id = ? OR blocked_id = ?")->execute([$ME, $ME]);
            $pdo->prepare("DELETE FROM qaz_push_subs WHERE user_id = ?")->execute([$ME]);
            $pdo->prepare("DELETE FROM msg_typing WHERE user_id = ?")->execute([$ME]);
        } catch (\Throwable $e) {}
        qaz_clear_remember($pdo); session_destroy();
        echo json_encode(['ok' => true]); exit;
    }

    // редактировать своё сообщение
    if ($action === 'edit' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $mid = (int)($d['id'] ?? 0); $text = trim($d['text'] ?? '');
        if ($mid && $text !== '') $pdo->prepare("UPDATE msg_messages SET text = ?, edited = 1 WHERE id = ? AND sender_id = ? AND deleted = 0")->execute([enc_at_rest(mb_substr($text,0,4000)), $mid, $ME]);
        echo json_encode(['ok' => true]); exit;
    }

    // удалить своё сообщение
    if ($action === 'delete' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $mid = (int)($d['id'] ?? 0);
        if ($mid) $pdo->prepare("UPDATE msg_messages SET deleted = 1, text = NULL, file = NULL, type = 'text' WHERE id = ? AND sender_id = ?")->execute([$mid, $ME]);
        echo json_encode(['ok' => true]); exit;
    }

    // реакция (тап — поставить/снять)
    if ($action === 'react' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $mid = (int)($d['id'] ?? 0); $emoji = mb_substr(trim($d['emoji'] ?? ''), 0, 8);
        if ($mid && $emoji) {
            $st = $pdo->prepare("SELECT emoji FROM msg_reactions WHERE message_id = ? AND user_id = ?"); $st->execute([$mid, $ME]); $cur = $st->fetchColumn();
            if ($cur === $emoji) $pdo->prepare("DELETE FROM msg_reactions WHERE message_id = ? AND user_id = ?")->execute([$mid, $ME]);
            else $pdo->prepare("INSERT INTO msg_reactions (message_id, user_id, emoji) VALUES (?,?,?) ON DUPLICATE KEY UPDATE emoji = VALUES(emoji)")->execute([$mid, $ME, $emoji]);
        }
        echo json_encode(['ok' => true]); exit;
    }

    // «печатает…»
    if ($action === 'typing' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $cid = (int)($d['chat'] ?? 0);
        if ($cid && is_member($pdo, $cid, $ME)) $pdo->prepare("INSERT INTO msg_typing (chat_id, user_id) VALUES (?,?) ON DUPLICATE KEY UPDATE updated_at = NOW()")->execute([$cid, $ME]);
        echo json_encode(['ok' => true]); exit;
    }

    // поиск сообщений в чате (текст в базе зашифрован — расшифровываем и ищем в PHP)
    if ($action === 'search_msg') {
        $cid = (int)($_GET['chat'] ?? 0); $q = trim($_GET['q'] ?? '');
        if (!is_member($pdo, $cid, $ME) || mb_strlen($q) < 1) { echo json_encode(['results' => []]); exit; }
        $st = $pdo->prepare("SELECT id, text, UNIX_TIMESTAMP(created_at) AS ts FROM msg_messages WHERE chat_id = ? AND deleted = 0 AND text IS NOT NULL AND type='text' ORDER BY id DESC LIMIT 800");
        $st->execute([$cid]);
        $ql = mb_strtolower($q); $res = [];
        foreach ($st->fetchAll() as $row) {
            $txt = dec_at_rest($row['text']);
            if ($txt !== null && mb_stripos($txt, $ql) !== false) { $res[] = ['id' => (int)$row['id'], 'text' => $txt, 'ts' => (int)$row['ts']]; if (count($res) >= 40) break; }
        }
        echo json_encode(['results' => $res], JSON_UNESCAPED_UNICODE); exit;
    }

    // закрепить/открепить сообщение
    if ($action === 'pin_msg' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $cid = (int)($d['chat'] ?? 0); $mid = (int)($d['id'] ?? 0) ?: null;
        if ($cid && is_member($pdo, $cid, $ME)) $pdo->prepare("UPDATE msg_chats SET pinned_msg = ? WHERE id = ?")->execute([$mid, $cid]);
        echo json_encode(['ok' => true]); exit;
    }

    // информация о чате (профиль собеседника / группа)
    if ($action === 'chat_info') {
        $cid = (int)($_GET['chat'] ?? 0);
        if (!is_member($pdo, $cid, $ME)) { echo json_encode(['error' => 'no_access']); exit; }
        $ci = $pdo->prepare("SELECT * FROM msg_chats WHERE id = ?"); $ci->execute([$cid]); $chat = $ci->fetch();
        $myAdmin = is_admin($pdo, $cid, $ME);
        $muted = (int)($pdo->query("SELECT muted FROM msg_members WHERE chat_id = " . (int)$cid . " AND user_id = " . (int)$ME)->fetchColumn());
        $resp = ['ok' => true, 'type' => $chat['type'], 'name' => $chat['name'], 'avatar' => $chat['avatar'], 'about' => $chat['about'], 'my_admin' => $myAdmin, 'muted' => $muted];
        if ($chat['type'] === 'group') {
            $ms = $pdo->prepare("SELECT u.id, u.name, u.avatar, u.last_seen, m.is_admin FROM msg_members m JOIN qaz_users u ON u.id = m.user_id WHERE m.chat_id = ? ORDER BY m.is_admin DESC, u.name");
            $ms->execute([$cid]); $members = [];
            foreach ($ms->fetchAll() as $mm) {
                $members[] = ['id' => (int)$mm['id'], 'name' => $mm['name'], 'avatar' => $mm['avatar'], 'is_admin' => (int)$mm['is_admin'], 'online' => ($mm['last_seen'] && strtotime($mm['last_seen']) > time() - 65)];
            }
            $resp['members'] = $members; $resp['count'] = count($members);
        } else {
            $pe = $pdo->prepare("SELECT u.id, u.name, u.phone, u.username, u.bio, u.avatar, u.last_seen, u.priv_lastseen, u.priv_phone FROM msg_members m JOIN qaz_users u ON u.id = m.user_id WHERE m.chat_id = ? AND m.user_id <> ? LIMIT 1");
            $pe->execute([$cid, $ME]); $p = $pe->fetch();
            if ($p) {
                $status = (($p['priv_lastseen'] ?? 'all') === 'nobody') ? (($p['last_seen'] && strtotime($p['last_seen']) > time() - 65) ? 'в сети' : 'был(а) недавно') : status_text($p['last_seen']);
                $blk = $pdo->prepare("SELECT 1 FROM msg_blocks WHERE blocker_id = ? AND blocked_id = ?"); $blk->execute([$ME, (int)$p['id']]);
                $resp['peer'] = ['id' => (int)$p['id'], 'name' => $p['name'], 'phone' => (($p['priv_phone'] ?? 'all') !== 'nobody' ? $p['phone'] : ''), 'username' => $p['username'], 'bio' => $p['bio'], 'avatar' => $p['avatar'], 'status' => $status, 'blocked' => (bool)$blk->fetchColumn()];
            }
        }
        echo json_encode($resp, JSON_UNESCAPED_UNICODE); exit;
    }

    // добавить участника (админ)
    if ($action === 'group_add' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $cid = (int)($d['chat'] ?? 0); $uid = (int)($d['user'] ?? 0);
        if (is_admin($pdo, $cid, $ME) && $uid) {
            $ex = $pdo->prepare("SELECT 1 FROM msg_members WHERE chat_id = ? AND user_id = ?"); $ex->execute([$cid, $uid]);
            if (!$ex->fetchColumn()) { $pdo->prepare("INSERT IGNORE INTO msg_members (chat_id, user_id) VALUES (?,?)")->execute([$cid, $uid]); sys_msg($pdo, $cid, uname($pdo, $ME) . ' добавил(а) ' . uname($pdo, $uid)); }
        }
        echo json_encode(['ok' => true]); exit;
    }
    // удалить участника (админ)
    if ($action === 'group_remove' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $cid = (int)($d['chat'] ?? 0); $uid = (int)($d['user'] ?? 0);
        if (is_admin($pdo, $cid, $ME) && $uid && $uid !== $ME) { $pdo->prepare("DELETE FROM msg_members WHERE chat_id = ? AND user_id = ?")->execute([$cid, $uid]); sys_msg($pdo, $cid, uname($pdo, $ME) . ' удалил(а) ' . uname($pdo, $uid)); }
        echo json_encode(['ok' => true]); exit;
    }
    // назначить/снять админа
    if ($action === 'group_admin' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $cid = (int)($d['chat'] ?? 0); $uid = (int)($d['user'] ?? 0); $val = !empty($d['val']) ? 1 : 0;
        if (is_admin($pdo, $cid, $ME) && $uid) $pdo->prepare("UPDATE msg_members SET is_admin = ? WHERE chat_id = ? AND user_id = ?")->execute([$val, $cid, $uid]);
        echo json_encode(['ok' => true]); exit;
    }
    // редактировать группу (название/описание) — админ
    if ($action === 'group_edit' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $cid = (int)($d['chat'] ?? 0);
        $name = trim($d['name'] ?? ''); $about = trim($d['about'] ?? '');
        if (is_admin($pdo, $cid, $ME) && $name !== '') {
            $pdo->prepare("UPDATE msg_chats SET name = ?, about = ? WHERE id = ?")->execute([mb_substr($name, 0, 120), mb_substr($about, 0, 300), $cid]);
            sys_msg($pdo, $cid, uname($pdo, $ME) . ' изменил(а) данные группы');
        }
        echo json_encode(['ok' => true]); exit;
    }
    // аватар группы (админ)
    if ($action === 'group_avatar' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $cid = (int)($_POST['chat'] ?? 0);
        if (is_admin($pdo, $cid, $ME) && !empty($_FILES['file']['tmp_name'])) {
            $img = qaz_upload_image($_FILES['file'], 'gava_', 500, 85);
            if (!$img) { $s = qaz_save_chat_file($_FILES['file']); if ($s && $s['type'] === 'image') $img = $s['file']; }
            if ($img) $pdo->prepare("UPDATE msg_chats SET avatar = ? WHERE id = ?")->execute([$img, $cid]);
            echo json_encode(['ok' => (bool)$img, 'avatar' => $img]); exit;
        }
        echo json_encode(['ok' => false]); exit;
    }
    // выйти из чата/группы
    if ($action === 'leave_chat' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $cid = (int)($d['chat'] ?? 0);
        if (is_member($pdo, $cid, $ME)) {
            $t = $pdo->prepare("SELECT type FROM msg_chats WHERE id = ?"); $t->execute([$cid]); $type = $t->fetchColumn();
            if ($type === 'group') sys_msg($pdo, $cid, uname($pdo, $ME) . ' вышел(ла) из группы');
            $pdo->prepare("DELETE FROM msg_members WHERE chat_id = ? AND user_id = ?")->execute([$cid, $ME]);
            $left = (int)$pdo->query("SELECT COUNT(*) FROM msg_members WHERE chat_id = " . (int)$cid)->fetchColumn();
            if ($left === 0) { $pdo->prepare("DELETE FROM msg_messages WHERE chat_id = ?")->execute([$cid]); $pdo->prepare("DELETE FROM msg_chats WHERE id = ?")->execute([$cid]); }
        }
        echo json_encode(['ok' => true]); exit;
    }
    // очистить историю
    if ($action === 'clear_history' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $cid = (int)($d['chat'] ?? 0);
        if (is_member($pdo, $cid, $ME)) { $pdo->prepare("DELETE FROM msg_messages WHERE chat_id = ?")->execute([$cid]); $pdo->prepare("UPDATE msg_chats SET pinned_msg = NULL WHERE id = ?")->execute([$cid]); }
        echo json_encode(['ok' => true]); exit;
    }
    // мьют чата
    if ($action === 'mute_chat' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $cid = (int)($d['chat'] ?? 0); $val = !empty($d['val']) ? 1 : 0;
        if (is_member($pdo, $cid, $ME)) $pdo->prepare("UPDATE msg_members SET muted = ? WHERE chat_id = ? AND user_id = ?")->execute([$val, $cid, $ME]);
        echo json_encode(['ok' => true]); exit;
    }

    // посмотреть одноразовое (отдаёт ссылку и помечает просмотренным)
    if ($action === 'view_once') {
        $id = (int)($_GET['id'] ?? 0);
        $m = $pdo->prepare("SELECT * FROM msg_messages WHERE id = ?"); $m->execute([$id]); $msg = $m->fetch();
        if (!$msg || !is_member($pdo, $msg['chat_id'], $ME)) { echo json_encode(['error' => 'no']); exit; }
        if (empty($msg['once'])) { echo json_encode(['url' => $msg['file'], 'mtype' => $msg['type']]); exit; }
        if ((int)$msg['sender_id'] === $ME) { echo json_encode(['error' => 'own']); exit; }
        if (!empty($msg['viewed']) || empty($msg['file'])) { echo json_encode(['expired' => true]); exit; }
        $pdo->prepare("UPDATE msg_messages SET viewed = 1 WHERE id = ?")->execute([$id]);
        echo json_encode(['url' => $msg['file'], 'mtype' => $msg['type']]); exit;
    }
    // после просмотра — удалить файл с диска
    if ($action === 'once_seen' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $id = (int)($d['id'] ?? 0);
        $m = $pdo->prepare("SELECT * FROM msg_messages WHERE id = ?"); $m->execute([$id]); $msg = $m->fetch();
        if ($msg && is_member($pdo, $msg['chat_id'], $ME) && !empty($msg['once']) && !empty($msg['viewed']) && (int)$msg['sender_id'] !== $ME) {
            if (!empty($msg['file']) && file_exists(__DIR__ . '/' . $msg['file'])) @unlink(__DIR__ . '/' . $msg['file']);
            $pdo->prepare("UPDATE msg_messages SET file = NULL WHERE id = ?")->execute([$id]);
        }
        echo json_encode(['ok' => true]); exit;
    }

    // ===== ИСТОРИИ (Stories) =====
    if ($action === 'stories_feed') {
        // файлы истёкших удаляем, строки держим сутки (для лимита 2/день)
        $exp = $pdo->query("SELECT file FROM msg_stories WHERE expires_at < NOW() AND file IS NOT NULL AND file <> ''");
        foreach ($exp->fetchAll() as $e) { if (!empty($e['file']) && file_exists(__DIR__ . '/' . $e['file'])) @unlink(__DIR__ . '/' . $e['file']); }
        $pdo->exec("UPDATE msg_stories SET file = NULL WHERE expires_at < NOW() AND file IS NOT NULL");
        $pdo->exec("DELETE FROM msg_stories WHERE created_at < (NOW() - INTERVAL 25 HOUR)");
        $st = $pdo->query("SELECT s.*, u.name, u.avatar FROM msg_stories s JOIN qaz_users u ON u.id = s.user_id WHERE s.expires_at >= NOW() ORDER BY s.user_id, s.id");
        $rows = $st->fetchAll();
        $byUser = [];
        foreach ($rows as $r) {
            $uid = (int)$r['user_id'];
            // в ленте — только я и мои контакты (с кем есть личный чат)
            if ($uid !== $ME && !has_private_chat($pdo, $uid, $ME)) continue;
            if (!story_visible($pdo, $r, $ME)) continue;
            if (!isset($byUser[$uid])) $byUser[$uid] = ['user_id' => $uid, 'name' => $r['name'], 'avatar' => $r['avatar'], 'count' => 0, 'unseen' => 0, 'is_me' => ($uid === $ME)];
            $byUser[$uid]['count']++;
            $sv = $pdo->prepare("SELECT 1 FROM msg_story_views WHERE story_id=? AND user_id=?"); $sv->execute([$r['id'], $ME]);
            if (!$sv->fetchColumn() && $uid !== $ME) $byUser[$uid]['unseen']++;
        }
        $meEntry = $byUser[$ME] ?? null; unset($byUser[$ME]);
        $list = array_values($byUser);
        usort($list, function ($a, $b) { return ($b['unseen'] > 0 ? 1 : 0) - ($a['unseen'] > 0 ? 1 : 0); });
        echo json_encode(['ok' => true, 'me' => $meEntry, 'users' => $list], JSON_UNESCAPED_UNICODE); exit;
    }

    if ($action === 'story_get') {
        $uid = (int)($_GET['user'] ?? 0);
        $st = $pdo->prepare("SELECT * FROM msg_stories WHERE user_id=? AND expires_at>=NOW() ORDER BY id");
        $st->execute([$uid]); $rows = $st->fetchAll(); $out = [];
        foreach ($rows as $r) {
            if (!story_visible($pdo, $r, $ME)) continue;
            $mv = $pdo->prepare("SELECT reaction FROM msg_story_views WHERE story_id=? AND user_id=?"); $mv->execute([$r['id'], $ME]); $mvr = $mv->fetch();
            $vc = ($uid === $ME) ? (int)$pdo->query("SELECT COUNT(*) FROM msg_story_views WHERE story_id=" . (int)$r['id'])->fetchColumn() : 0;
            // опрос
            $poll = null;
            if (!empty($r['poll'])) {
                $pd = json_decode($r['poll'], true);
                if (is_array($pd) && !empty($pd['options'])) {
                    $n = count($pd['options']); $counts = array_fill(0, $n, 0);
                    $vq = $pdo->prepare("SELECT choice, COUNT(*) c FROM msg_story_poll WHERE story_id=? GROUP BY choice"); $vq->execute([$r['id']]);
                    foreach ($vq->fetchAll() as $vr) { $ci = (int)$vr['choice']; if ($ci >= 0 && $ci < $n) $counts[$ci] = (int)$vr['c']; }
                    $myv = $pdo->prepare("SELECT choice FROM msg_story_poll WHERE story_id=? AND user_id=?"); $myv->execute([$r['id'], $ME]); $mvc = $myv->fetchColumn();
                    $poll = ['q' => $pd['q'], 'options' => $pd['options'], 'counts' => $counts, 'total' => array_sum($counts), 'my' => ($mvc === false ? null : (int)$mvc)];
                }
            }
            $out[] = ['id' => (int)$r['id'], 'type' => $r['type'], 'file' => $r['file'], 'text' => $r['text'], 'ts' => strtotime($r['created_at']), 'my_reaction' => $mvr ? $mvr['reaction'] : null, 'viewers' => $vc, 'is_me' => ($uid === $ME), 'poll' => $poll];
        }
        $uq = $pdo->prepare("SELECT name, avatar FROM qaz_users WHERE id=?"); $uq->execute([$uid]); $u = $uq->fetch();
        echo json_encode(['ok' => true, 'user' => ['id' => $uid, 'name' => $u['name'] ?? '', 'avatar' => $u['avatar'] ?? ''], 'stories' => $out], JSON_UNESCAPED_UNICODE); exit;
    }

    if ($action === 'story_add' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        if (empty($_FILES['file']['tmp_name'])) { echo json_encode(['error' => 'no_file']); exit; }
        $att = qaz_save_chat_file($_FILES['file']);
        if (!$att) { echo json_encode(['error' => 'upload']); exit; }
        $type = $att['type'];
        if ($type === 'file') { $ext = strtolower(pathinfo($att['filename'] ?? $att['file'], PATHINFO_EXTENSION)); if (in_array($ext, ['mp4', 'mov', 'm4v', 'webm', '3gp'])) $type = 'video'; }
        if (!in_array($type, ['image', 'video'])) { echo json_encode(['error' => 'bad_type']); exit; }
        // лимит: 2 истории в сутки
        $cnt = $pdo->prepare("SELECT COUNT(*) FROM msg_stories WHERE user_id=? AND created_at > (NOW() - INTERVAL 1 DAY)");
        $cnt->execute([$ME]);
        if ((int)$cnt->fetchColumn() >= 2) {
            if (!empty($att['file']) && file_exists(__DIR__ . '/' . $att['file'])) @unlink(__DIR__ . '/' . $att['file']);
            echo json_encode(['error' => 'limit', 'msg' => 'Можно добавлять только 2 истории в день']); exit;
        }
        $hours = (int)($_POST['hours'] ?? 24); if (!in_array($hours, [1, 6, 24])) $hours = 24;
        $aud = in_array($_POST['audience'] ?? 'all', ['all', 'contacts', 'select']) ? $_POST['audience'] : 'all';
        $text = mb_substr(trim($_POST['text'] ?? ''), 0, 300);
        // опрос (необязательно)
        $poll = null;
        if (!empty($_POST['poll'])) {
            $pj = json_decode($_POST['poll'], true);
            if (is_array($pj) && !empty($pj['q']) && !empty($pj['options']) && is_array($pj['options'])) {
                $opts = array_values(array_filter(array_map(function ($o) { return mb_substr(trim((string)$o), 0, 60); }, $pj['options']), function ($o) { return $o !== ''; }));
                $opts = array_slice($opts, 0, 4);
                if (count($opts) >= 2) $poll = json_encode(['q' => mb_substr(trim($pj['q']), 0, 120), 'options' => $opts], JSON_UNESCAPED_UNICODE);
            }
        }
        $pdo->prepare("INSERT INTO msg_stories (user_id, type, file, text, audience, poll, expires_at) VALUES (?,?,?,?,?,?, DATE_ADD(NOW(), INTERVAL ? HOUR))")
            ->execute([$ME, $type, $att['file'], $text ?: null, $aud, $poll, $hours]);
        $sid = (int)$pdo->lastInsertId();
        if ($aud === 'select' && !empty($_POST['viewers'])) {
            $ids = json_decode($_POST['viewers'], true);
            if (is_array($ids)) { $ins = $pdo->prepare("INSERT IGNORE INTO msg_story_audience (story_id, user_id) VALUES (?,?)"); foreach ($ids as $vid) { $vid = (int)$vid; if ($vid) $ins->execute([$sid, $vid]); } }
        }
        echo json_encode(['ok' => true, 'id' => $sid]); exit;
    }

    if ($action === 'story_view' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $sid = (int)($d['id'] ?? 0);
        $ow = $pdo->prepare("SELECT user_id FROM msg_stories WHERE id=?"); $ow->execute([$sid]); $owner = (int)$ow->fetchColumn();
        if ($sid && $owner && $owner !== $ME) $pdo->prepare("INSERT IGNORE INTO msg_story_views (story_id, user_id) VALUES (?,?)")->execute([$sid, $ME]);
        echo json_encode(['ok' => true]); exit;
    }

    if ($action === 'story_react' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $sid = (int)($d['id'] ?? 0); $emoji = mb_substr($d['emoji'] ?? '', 0, 16);
        $pdo->prepare("INSERT INTO msg_story_views (story_id, user_id, reaction) VALUES (?,?,?) ON DUPLICATE KEY UPDATE reaction=VALUES(reaction)")->execute([$sid, $ME, $emoji ?: null]);
        $ow = $pdo->prepare("SELECT user_id FROM msg_stories WHERE id=?"); $ow->execute([$sid]); $owner = (int)$ow->fetchColumn();
        if ($owner && $owner !== $ME && $emoji) qaz_push_send($pdo, $owner, $MYNAME, 'реакция на вашу историю: ' . $emoji, 'messenger.php', 'qaz-msg');
        echo json_encode(['ok' => true]); exit;
    }

    if ($action === 'story_reply' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $sid = (int)($d['id'] ?? 0); $text = trim($d['text'] ?? '');
        if ($text === '') { echo json_encode(['error' => 'empty']); exit; }
        $ow = $pdo->prepare("SELECT user_id FROM msg_stories WHERE id=?"); $ow->execute([$sid]); $owner = (int)$ow->fetchColumn();
        if (!$owner || $owner === $ME) { echo json_encode(['error' => 'no']); exit; }
        $cid = open_private($pdo, $ME, $owner);
        $pdo->prepare("INSERT INTO msg_messages (chat_id, sender_id, text, type, story_ref) VALUES (?,?,?,'text',?)")->execute([$cid, $ME, enc_at_rest(mb_substr($text, 0, 1000)), $sid]);
        qaz_push_send($pdo, $owner, $MYNAME, 'ответил(а) на вашу историю', 'messenger.php', 'qaz-msg');
        echo json_encode(['ok' => true]); exit;
    }

    if ($action === 'story_vote' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $sid = (int)($d['id'] ?? 0); $ch = (int)($d['choice'] ?? -1);
        $s = $pdo->prepare("SELECT user_id, poll FROM msg_stories WHERE id=? AND expires_at>=NOW()"); $s->execute([$sid]); $sr = $s->fetch();
        if ($sr && !empty($sr['poll'])) {
            $pd = json_decode($sr['poll'], true);
            if (is_array($pd) && $ch >= 0 && $ch < count($pd['options'])) {
                $pdo->prepare("INSERT INTO msg_story_poll (story_id, user_id, choice) VALUES (?,?,?) ON DUPLICATE KEY UPDATE choice=VALUES(choice)")->execute([$sid, $ME, $ch]);
                if ((int)$sr['user_id'] !== $ME) $pdo->prepare("INSERT IGNORE INTO msg_story_views (story_id, user_id) VALUES (?,?)")->execute([$sid, $ME]);
            }
        }
        echo json_encode(['ok' => true]); exit;
    }

    if ($action === 'story_viewers') {
        $sid = (int)($_GET['id'] ?? 0);
        $ow = $pdo->prepare("SELECT user_id FROM msg_stories WHERE id=?"); $ow->execute([$sid]);
        if ((int)$ow->fetchColumn() !== $ME) { echo json_encode(['error' => 'no']); exit; }
        $v = $pdo->prepare("SELECT v.user_id, v.reaction, UNIX_TIMESTAMP(v.viewed_at) AS ts, u.name, u.avatar FROM msg_story_views v JOIN qaz_users u ON u.id=v.user_id WHERE v.story_id=? ORDER BY v.viewed_at DESC");
        $v->execute([$sid]);
        echo json_encode(['ok' => true, 'viewers' => $v->fetchAll()], JSON_UNESCAPED_UNICODE); exit;
    }

    if ($action === 'story_delete' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true); $sid = (int)($d['id'] ?? 0);
        $s = $pdo->prepare("SELECT user_id, file FROM msg_stories WHERE id=?"); $s->execute([$sid]); $row = $s->fetch();
        if ($row && (int)$row['user_id'] === $ME) {
            if (!empty($row['file']) && file_exists(__DIR__ . '/' . $row['file'])) @unlink(__DIR__ . '/' . $row['file']);
            $pdo->prepare("DELETE FROM msg_stories WHERE id=?")->execute([$sid]);
            $pdo->prepare("DELETE FROM msg_story_views WHERE story_id=?")->execute([$sid]);
            $pdo->prepare("DELETE FROM msg_story_audience WHERE story_id=?")->execute([$sid]);
        }
        echo json_encode(['ok' => true]); exit;
    }

    // ===== ВХОД ПО ЛИЦУ (управление) =====
    if ($action === 'face_has') {
        $q = $pdo->prepare("SELECT face_descriptor FROM qaz_users WHERE id=?"); $q->execute([$ME]); $fd = $q->fetchColumn();
        $has = false; $cnt = 0;
        if ($fd) { $arr = json_decode(dec_at_rest($fd), true); if (is_array($arr)) { if (isset($arr[0]) && !is_array($arr[0])) $arr = [$arr]; $cnt = count($arr); $has = $cnt > 0; } }
        echo json_encode(['ok' => true, 'has' => $has, 'samples' => $cnt]); exit;
    }
    if ($action === 'face_enroll' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true);
        $desc = $d['descriptor'] ?? null;
        if (!is_array($desc) || count($desc) < 100) { echo json_encode(['error' => 'bad']); exit; }
        $q = $pdo->prepare("SELECT face_descriptor FROM qaz_users WHERE id=?"); $q->execute([$ME]);
        $existing = json_decode(dec_at_rest($q->fetchColumn() ?: '[]') ?: '[]', true); if (!is_array($existing)) $existing = [];
        if (isset($existing[0]) && !is_array($existing[0])) $existing = [$existing];
        $existing[] = array_map('floatval', $desc);
        $existing = array_slice($existing, -3); // храним до 3 образцов лица
        $pdo->prepare("UPDATE qaz_users SET face_descriptor=? WHERE id=?")->execute([enc_at_rest(json_encode($existing)), $ME]);
        echo json_encode(['ok' => true, 'samples' => count($existing)]); exit;
    }
    if ($action === 'face_disable' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $pdo->prepare("UPDATE qaz_users SET face_descriptor=NULL WHERE id=?")->execute([$ME]);
        echo json_encode(['ok' => true]); exit;
    }

    // подписка на push
    if ($action === 'push_subscribe' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $data = json_decode(file_get_contents('php://input'), true);
        $endpoint = $data['endpoint'] ?? ''; $p256dh = $data['keys']['p256dh'] ?? ''; $auth = $data['keys']['auth'] ?? '';
        if ($endpoint && $p256dh && $auth) {
            $pdo->prepare("DELETE FROM qaz_push_subs WHERE user_id = ? AND endpoint <> ?")->execute([$ME, $endpoint]);
            $pdo->prepare("INSERT INTO qaz_push_subs (user_id, endpoint, p256dh, auth) VALUES (?,?,?,?)
                ON DUPLICATE KEY UPDATE user_id=VALUES(user_id), p256dh=VALUES(p256dh), auth=VALUES(auth)")
                ->execute([$ME, $endpoint, $p256dh, $auth]);
        }
        echo json_encode(['ok' => true]); exit;
    }

    echo json_encode(['error' => 'unknown']); exit;
}
?>
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=1, interactive-widget=resizes-content">
<meta name="theme-color" content="#1E1E2C">
<title>Payom</title>
<link rel="manifest" href="messenger.php?manifest=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Payom">
<link rel="apple-touch-icon" href="messenger.php?micon=180">
<link rel="icon" type="image/png" href="messenger.php?micon=192">
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
:root{--bg:#141420;--panel:#1E1E2C;--panel2:#2A2A3C;--line:#2E2E42;--txt:#fff;--sub:#9090A8;--blue:#7C5CFF;--blue2:#5B3FE0;--out:#463A82;--in:#26263A}
body{font-family:'Manrope',system-ui,sans-serif;background:var(--bg);color:var(--txt);height:100dvh;overflow:hidden}
#msgsArea{background:radial-gradient(900px 500px at 80% 0%,rgba(124,92,255,.06),transparent 60%),var(--bg)}
.screen{position:fixed;top:var(--vv-top,0);left:0;right:0;height:var(--app-h,100dvh);display:flex;flex-direction:column;background:var(--bg);transition:transform .25s ease}
#scChat,#scGroup,#scSettings,#scInfo,#scContacts,#scContact{transform:translateX(100%)}
#scChat.show,#scGroup.show,#scSettings.show,#scInfo.show,#scContacts.show,#scContact.show{transform:translateX(0)}
.top{display:flex;align-items:center;gap:12px;padding:calc(12px + env(safe-area-inset-top)) 14px 12px;background:var(--panel);border-bottom:1px solid var(--line);flex-shrink:0}
.top h2{font-size:17px;font-weight:800;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.top .sub{font-size:12px;color:var(--sub);font-weight:600}
.icon-btn{width:40px;height:40px;border-radius:50%;border:none;background:transparent;color:var(--blue);cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.icon-btn svg{width:23px;height:23px}
.icon-btn:active{background:var(--panel2)}
.search-wrap{padding:10px 14px;background:var(--panel);flex-shrink:0}
.search-wrap input{width:100%;padding:11px 15px;border:none;border-radius:20px;background:var(--panel2);color:#fff;font-size:15px;outline:none;font-weight:600;font-family:inherit}
.list{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch}
.row{display:flex;align-items:center;gap:13px;padding:11px 15px;cursor:pointer;border-bottom:1px solid rgba(36,48,60,.5)}
.row:active{background:var(--panel)}
/* iOS-свайп в списке чатов */
.row-wrap{position:relative;overflow:hidden}
.row-actions{position:absolute;top:0;right:0;bottom:0;display:flex}
.ra{border:none;width:80px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;color:#fff;font-size:11px;font-weight:700;cursor:pointer;font-family:inherit}
.ra svg{width:22px;height:22px}
.ra-mute{background:#586170}
.ra-del{background:#E5484D}
.row-wrap .row{position:relative;z-index:1;background:var(--bg);transition:transform .22s cubic-bezier(.3,1.1,.5,1);will-change:transform;border-bottom:1px solid rgba(36,48,60,.5)}
.ava{width:52px;height:52px;border-radius:50%;background:linear-gradient(140deg,#7C5CFF,#5B3FE0);display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:800;flex-shrink:0;color:#fff}
.ava.g{background:linear-gradient(140deg,#E8A03D,#D2691E)}
.row-main{flex:1;min-width:0}
.row-top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.row-name{font-size:16px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row-time{font-size:12px;color:var(--sub);font-weight:600;flex-shrink:0}
.row-bot{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:3px}
.row-last{font-size:14px;color:var(--sub);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
.badge{background:var(--blue);color:#fff;font-size:12px;font-weight:800;min-width:22px;height:22px;border-radius:11px;padding:0 6px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.hint{text-align:center;color:var(--sub);font-size:14px;font-weight:600;padding:40px 30px;line-height:1.7}
/* лента историй */
.stories-bar{display:flex;gap:14px;overflow-x:auto;padding:12px 14px;border-bottom:1px solid var(--line);flex-shrink:0;-webkit-overflow-scrolling:touch}
.stories-bar::-webkit-scrollbar{display:none}
.story-item{display:flex;flex-direction:column;align-items:center;gap:5px;cursor:pointer;flex-shrink:0;width:66px;position:relative}
.story-ring{width:62px;height:62px;border-radius:50%;padding:2.5px;background:var(--panel2)}
.story-ring.unseen{background:linear-gradient(140deg,#7C5CFF,#8E5BEA,#E23B7A)}
.story-ring.me-add{background:var(--panel2)}
.story-ring .si{width:100%;height:100%;border-radius:50%;overflow:hidden;background:linear-gradient(140deg,#7C5CFF,#5B3FE0);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:20px;border:2px solid var(--bg)}
.story-ring .si img{width:100%;height:100%;object-fit:cover}
.story-add-badge{position:absolute;right:1px;top:41px;width:22px;height:22px;border-radius:50%;background:var(--blue);border:2.5px solid var(--bg);display:flex;align-items:center;justify-content:center;color:#fff;font-size:15px;font-weight:800;line-height:1;z-index:3}
.story-name{font-size:11px;color:var(--sub);font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:64px;text-align:center}
.seg{display:flex;gap:8px}
.seg button{flex:1;padding:11px;border:none;border-radius:11px;background:var(--panel2);color:var(--sub);font-weight:700;font-size:14px;cursor:pointer;font-family:inherit}
.seg button.on{background:var(--blue);color:#fff}
.sv-reax{width:40px;height:40px;border-radius:50%;background:rgba(255,255,255,.15);border:none;font-size:20px;cursor:pointer;display:flex;align-items:center;justify-content:center}
.sbar{flex:1;height:3px;background:rgba(255,255,255,.3);border-radius:2px;overflow:hidden}
.sbar .fill{height:100%;width:0;background:#fff;border-radius:2px}
.msgs{flex:1;overflow-y:auto;padding:12px 12px 6px;-webkit-overflow-scrolling:touch;display:flex;flex-direction:column;gap:2px;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='150' height='150'%3E%3Cg fill='none' stroke='%23fff' stroke-opacity='.035' stroke-width='2' stroke-linecap='round'%3E%3Ccircle cx='24' cy='28' r='10'/%3E%3Cpath d='M74 20c-5-7-16-2-11 6l11 10 11-10c5-8-6-13-11-6z'/%3E%3Cpath d='M118 36l3 7 8 1-6 5 2 8-7-4-7 4 2-8-6-5 8-1z'/%3E%3Ccircle cx='36' cy='100' r='7'/%3E%3Cpath d='M96 96q9-11 18 0'/%3E%3Crect x='60' y='86' width='18' height='18' rx='5'/%3E%3Cpath d='M18 126q10-12 20 0'/%3E%3Cpath d='M128 116l4-4 4 4-4 4z'/%3E%3C/g%3E%3C/svg%3E")}
.m{max-width:75%;padding:6px 11px;border-radius:15px;font-size:15px;font-weight:400;line-height:1.35;word-wrap:break-word;position:relative}
.m.out{background:linear-gradient(160deg,#9270FF,#6D4AE6);align-self:flex-end;border-bottom-right-radius:7px}
body.light .m.out{background:linear-gradient(135deg,#EBE4FF,#DAD0FF);color:#241C3A}
.m.in{background:var(--in);align-self:flex-start;border-top-left-radius:7px}
.m .sname{font-size:12.5px;font-weight:800;color:#A99BFF;margin-bottom:2px;cursor:pointer}
.m .msg-link{font-weight:700;text-decoration:none;word-break:break-word;cursor:pointer}
.m.out .msg-link{color:#F0EBFF;text-decoration:underline;text-decoration-color:rgba(255,255,255,.5)}
.m.in .msg-link{color:#7FB4F2}
.grp-row{display:flex;align-items:flex-end;gap:7px;align-self:flex-start;max-width:90%}
.grp-row .m{max-width:100%;min-width:52px}
.m .reply{border-left:3px solid #A99BFF;padding:3px 8px;margin-bottom:4px;background:rgba(0,0,0,.18);border-radius:6px;font-size:13px;cursor:pointer}
.m .reply b{color:#A99BFF;display:block;font-size:12.5px}
.m .reply span{color:var(--sub);display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.m .meta{float:right;margin:6px 0 -2px 9px;font-size:11px;color:rgba(255,255,255,.55);font-weight:600;line-height:1;display:inline-flex;gap:4px;align-items:center;position:relative;top:4px}
.m::after{content:'';display:table;clear:both}
.m .reactions{clear:both}
.m.media .meta{float:none;top:0;display:flex;justify-content:flex-end;margin:5px 0 0 0}
.m .rbtn{position:absolute;top:50%;transform:translateY(-50%);opacity:0;width:30px;height:30px;border:none;background:var(--panel);border-radius:50%;color:var(--sub);cursor:pointer;display:flex;align-items:center;justify-content:center}
.m.out .rbtn{left:-38px}.m.in .rbtn{right:-38px}
.m:active .rbtn{opacity:1}
.rbtn svg{width:16px;height:16px}
.reply-bar{display:none;align-items:center;gap:10px;padding:9px 14px;background:var(--panel);border-top:1px solid var(--line);flex-shrink:0}
.reply-bar.show{display:flex}
.reply-bar .rb-line{width:3px;align-self:stretch;background:var(--blue);border-radius:2px}
.reply-bar .rb-main{flex:1;min-width:0}
.reply-bar .rb-main b{color:var(--blue);font-size:13px;display:block}
.reply-bar .rb-main span{color:var(--sub);font-size:13px;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.composer{display:flex;align-items:flex-end;gap:9px;padding:9px 12px calc(9px + var(--kb-safe, env(safe-area-inset-bottom)));background:var(--panel);border-top:1px solid var(--line);flex-shrink:0}
.composer textarea{flex:1;border:none;border-radius:20px;background:var(--panel2);color:#fff;font-size:15px;padding:11px 15px;outline:none;resize:none;max-height:110px;font-family:inherit;font-weight:600}
.cbtn{width:44px;height:44px;border-radius:50%;border:none;background:transparent;color:var(--sub);cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:transform .2s cubic-bezier(.34,1.56,.64,1)}
.cbtn svg{width:24px;height:24px}
.cbtn:active{background:var(--panel2)}
.am-item{display:flex;align-items:center;gap:12px;width:170px;padding:14px 18px;background:none;border:none;color:var(--txt);font-size:15px;font-weight:700;cursor:pointer;font-family:inherit;text-align:left}
.am-item:active{background:var(--panel2)}
.am-item svg{width:20px;height:20px;color:var(--sub)}
.send{width:46px;height:46px;border-radius:50%;border:none;background:linear-gradient(135deg,#8E6BFF,#5B3FE0);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;box-shadow:0 4px 14px rgba(124,92,255,.45);transition:transform .2s cubic-bezier(.34,1.56,.64,1)}
.send:active{transform:scale(.85)}
.cbtn:active{transform:scale(.85)}
.send svg{width:21px;height:21px}
#micBtn{background:var(--blue)}
#micBtn.rec{background:#FF3B30;transform:scale(1.15)}
@keyframes recpulse{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes instpulse{0%,100%{box-shadow:0 0 0 0 rgba(255,255,255,.55)}70%{box-shadow:0 0 0 9px rgba(255,255,255,0)}}
#instBtn{animation:instpulse 1.8s ease-out infinite}
/* голосовое сообщение */
.voice{display:flex;align-items:center;gap:11px;min-width:200px;max-width:264px;padding:2px 0}
.vplay{width:48px;height:48px;border-radius:50%;border:none;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;box-shadow:0 2px 8px rgba(0,0,0,.18)}
.m.in .vplay{background:var(--blue)}
.vplay svg{width:22px;height:22px}
.m.out .vplay svg{color:#7C5CFF}
.m.in .vplay svg{color:#fff}
.vright{flex:1;display:flex;flex-direction:column;gap:5px;min-width:0}
.vwave{display:flex;align-items:center;gap:2.5px;height:23px;cursor:pointer}
.vb{flex:1;min-width:2px;max-width:3px;border-radius:2px;background:rgba(255,255,255,.45)}
.m.in .vb{background:rgba(255,255,255,.32)}
.vb.on{background:#fff}
.vmeta{display:flex;align-items:center;gap:8px}
.vdur{font-size:12px;font-weight:600;color:rgba(255,255,255,.85);font-variant-numeric:tabular-nums;flex-shrink:0}
/* медиа: фото/видео с загрузкой */
.media-wrap{position:relative;border-radius:12px;overflow:hidden;background:rgba(0,0,0,.25);min-width:150px;min-height:110px;max-width:230px;cursor:pointer;display:flex;align-items:center;justify-content:center}
.media-wrap img{display:block;max-width:230px;max-height:280px;width:100%;opacity:0;transition:opacity .35s}
.media-wrap img.loaded{opacity:1}
.media-spin{position:absolute;width:34px;height:34px;border:3px solid rgba(255,255,255,.25);border-top-color:#fff;border-radius:50%;animation:sp 0.9s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.vid-play{position:absolute;width:56px;height:56px;border-radius:50%;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:2}
.vid-play svg{width:26px;height:26px;color:#fff;margin-left:3px}
.vid-badge{position:absolute;left:8px;bottom:8px;background:rgba(0,0,0,.6);color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:8px;z-index:2}
#imgViewer{display:none;position:fixed;inset:0;z-index:300;background:rgba(0,0,0,.95);align-items:center;justify-content:center}
.once-ph{display:flex;align-items:center;font-size:14px;font-weight:700;padding:4px 2px;color:inherit}
.once-ph.tap{cursor:pointer;color:#A99BFF}
.once-ph.viewed{opacity:.6;font-style:italic}
#imgViewer img{max-width:100%;max-height:100%}
/* видео-кружок */
.m.bare{background:none!important;box-shadow:none!important;padding:0!important;border-radius:0!important}
.m.bare .meta{float:none;top:0;position:static;justify-content:flex-end;margin:5px 6px 0 0;padding-right:6px;color:var(--sub);display:flex}
.circle-msg{position:relative;width:200px;height:200px;border-radius:50%;overflow:hidden;cursor:pointer;background:#000;box-shadow:0 4px 16px rgba(0,0,0,.3)}
.circle-msg video{width:100%;height:100%;object-fit:cover;display:block}
.circle-dur{position:absolute;left:50%;bottom:12px;transform:translateX(-50%);background:rgba(0,0,0,.55);color:#fff;font-size:11px;font-weight:700;padding:2px 9px;border-radius:10px}
.circle-mute{position:absolute;right:14px;top:14px;width:28px;height:28px;background:rgba(0,0,0,.5);border-radius:50%;display:flex;align-items:center;justify-content:center}
/* анимация появления сообщений (как в Telegram) */
/* анимация появления — пружинистый отскок (как Telegram) */
@keyframes msgInR{0%{opacity:0;transform:translate(26px,20px) scale(.45)}55%{opacity:1;transform:translate(-4px,-3px) scale(1.05)}78%{transform:translate(1px,1px) scale(.98)}100%{transform:none}}
@keyframes msgInL{0%{opacity:0;transform:translate(-26px,20px) scale(.45)}55%{opacity:1;transform:translate(4px,-3px) scale(1.05)}78%{transform:translate(-1px,1px) scale(.98)}100%{transform:none}}
.m.msg-in-r{animation:msgInR .44s cubic-bezier(.3,1.2,.5,1);transform-origin:bottom right}
.m.msg-in-l{animation:msgInL .44s cubic-bezier(.3,1.2,.5,1);transform-origin:bottom left}
/* пружинистое нажатие на сообщение */
.m{transition:transform .25s cubic-bezier(.34,1.56,.64,1)}
.m:active{transform:scale(.93)}
.fab{position:fixed;right:18px;bottom:calc(20px + env(safe-area-inset-bottom));width:60px;height:60px;border-radius:20px;border:none;background:linear-gradient(135deg,#9575FF,#5B3FE0);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 10px 28px rgba(124,92,255,.55),inset 0 1px 0 rgba(255,255,255,.2);z-index:20;transition:transform .2s cubic-bezier(.34,1.56,.64,1)}
.fab:active{transform:scale(.9)}
.fab svg{width:26px;height:26px}
.gm-pick{display:flex;flex-wrap:wrap;gap:8px;padding:10px 15px}
.gm-chip{background:var(--blue);color:#fff;font-size:13px;font-weight:700;padding:6px 12px;border-radius:16px;display:flex;gap:6px;align-items:center}
.gm-chip span{cursor:pointer}
.chk{width:24px;height:24px;border-radius:50%;border:2px solid var(--blue);flex-shrink:0;display:flex;align-items:center;justify-content:center;color:#fff}
.chk.on{background:var(--blue)}
.ava img{width:100%;height:100%;border-radius:50%;object-fit:cover}
.reax{background:var(--panel2);border:none;font-size:26px;width:48px;height:48px;border-radius:50%;cursor:pointer}
.reax:active{transform:scale(.9)}
.mmi{display:flex;align-items:center;gap:13px;width:100%;padding:14px 16px;background:none;border:none;color:#fff;font-size:15.5px;font-weight:700;cursor:pointer;font-family:inherit;text-align:left;border-radius:12px}
.mmi:active{background:var(--panel2)}
.mmi svg{width:21px;height:21px;color:var(--sub)}
.mmi.del{color:#FF6B6B}.mmi.del svg{color:#FF6B6B}
.reactions{display:flex;gap:5px;flex-wrap:wrap;margin-top:5px}
.reaction{background:rgba(51,144,236,.18);border:1px solid transparent;border-radius:12px;padding:2px 8px;font-size:13px;font-weight:700;cursor:pointer;animation:reactPop .3s cubic-bezier(.3,1.4,.5,1);transition:transform .12s}
.reaction:active{transform:scale(.86)}
.reaction.mine{background:rgba(51,144,236,.4);border-color:var(--blue)}
@keyframes reactPop{0%{transform:scale(.4);opacity:0}60%{transform:scale(1.18)}100%{transform:scale(1)}}
.emoji-big{display:inline-block;line-height:1.1;animation:emojiPop .4s cubic-bezier(.3,1.5,.5,1)}
.emoji-big.e1{font-size:54px}
.emoji-big.e2{font-size:44px}
.emoji-big.e3{font-size:36px}
@keyframes emojiPop{0%{transform:scale(.3);opacity:0}55%{transform:scale(1.18)}100%{transform:scale(1)}}
.m.emojimsg{background:transparent!important;padding:2px 6px 2px 2px;box-shadow:none}
.m.emojimsg .meta{color:var(--sub);top:2px}
.m.emojimsg::after{content:'';display:table;clear:both}
.sticker{width:150px;height:150px;object-fit:contain;display:block;animation:emojiPop .4s cubic-bezier(.3,1.5,.5,1)}
.m.stickermsg{background:transparent!important;padding:0 4px 0 0;box-shadow:none}
.m.stickermsg .meta{color:var(--sub);top:2px}
.m.stickermsg::after{content:'';display:table;clear:both}
.typing{color:var(--blue) !important}
.sr-item{padding:10px 4px;border-bottom:1px solid var(--line);cursor:pointer;font-size:14px;color:#fff}
.sr-item .t{color:var(--sub);font-size:12px}
/* светлая тема */
body.light{--bg:#FFFFFF;--panel:#F4F2FB;--panel2:#EAE7F6;--line:#E1DEEF;--txt:#161320;--sub:#6E6B82;--in:#EEEBF9;--out:#E5DEFF}
body.light .m .meta{color:rgba(0,0,0,.45)}
body.light .m.out .meta span{color:#5B3FE0 !important}
/* размер шрифта сообщений */
body.fs-small .m{font-size:13.5px}
body.fs-large .m{font-size:17px}
/* строки настроек */
.st-h{font-size:12px;font-weight:800;color:var(--sub);text-transform:uppercase;padding:16px 16px 6px}
.st-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:14px 16px;border-bottom:1px solid var(--line);background:var(--panel)}
.st-row label{font-size:15px;font-weight:700;display:flex;align-items:center;gap:9px}
.st-row label svg{width:19px;height:19px;color:var(--sub);flex-shrink:0}
.st-btn svg{width:18px;height:18px;vertical-align:-3px;margin-right:7px}
.st-row .rr{color:var(--sub);font-size:14px;font-weight:700}
.st-row select,.st-row input[type=date]{background:var(--panel2);color:var(--txt);border:none;border-radius:9px;padding:9px 10px;font-size:14px;font-weight:700;font-family:inherit;outline:none}
.st-sw{width:50px;height:30px;border-radius:15px;background:var(--panel2);position:relative;cursor:pointer;flex-shrink:0;transition:background .2s}
.st-sw.on{background:var(--blue)}
.st-sw::after{content:'';position:absolute;top:3px;left:3px;width:24px;height:24px;border-radius:50%;background:#fff;transition:left .2s}
.st-sw.on::after{left:23px}
.st-btn{width:100%;padding:14px;border:none;border-radius:12px;font-size:15px;font-weight:800;cursor:pointer;font-family:inherit;margin-bottom:10px}
.st-btn svg{width:19px;height:19px;vertical-align:-4px;margin-right:9px}
.tgl{width:48px;height:29px;border-radius:15px;background:var(--panel2);position:relative;transition:.2s;flex-shrink:0;display:inline-block}
.tgl::after{content:"";position:absolute;top:3px;left:3px;width:23px;height:23px;border-radius:50%;background:#fff;transition:.2s;box-shadow:0 1px 3px rgba(0,0,0,.3)}
input:checked + .tgl{background:#4ADE80}
input:checked + .tgl::after{transform:translateX(19px)}

/* ===== PAYOM-UPDATE-v2: плавность и исправления ===== */
.row-title{font-size:16px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--txt)}
.row-sub{font-size:14px;color:var(--sub);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:3px}
.screen{transition:transform .32s cubic-bezier(.32,.72,0,1);will-change:transform;backface-visibility:hidden}
.msgs,.list{scroll-behavior:smooth;overscroll-behavior:contain}
.m{box-shadow:0 1px 2px rgba(0,0,0,.18);transition:transform .22s cubic-bezier(.34,1.56,.64,1),opacity .2s}
.m:active{transform:scale(.965)}
.m.out{box-shadow:0 2px 8px rgba(124,92,255,.22)}
.media-wrap img,.sticker{opacity:0;transition:opacity .32s ease}
.media-wrap img.loaded,.media-wrap img.img-ready,.sticker.img-ready{opacity:1}
.row{transition:background .18s,transform .16s cubic-bezier(.34,1.56,.64,1)}
.row:active{transform:scale(.985)}
.icon-btn,.cbtn,.send,.st-btn,.reax,.mmi{transition:transform .18s cubic-bezier(.34,1.56,.64,1),background .18s,opacity .18s}
.icon-btn:active,.mmi:active{transform:scale(.9)}
.st-btn:active{transform:scale(.975)}
.composer textarea{transition:background .2s,box-shadow .2s}
.composer textarea:focus{box-shadow:0 0 0 2px rgba(124,92,255,.25)}
#msgMenuOv>div,#stickerSheet>div,#packView>div,#autoDelSheet>div,#installSheet>div,
#lockSetSheet>div,#devSheet>div,#storyOpts>div,#viewersOv>div{animation:sheetUp .28s cubic-bezier(.32,.72,0,1)}
@keyframes sheetUp{from{transform:translateY(100%)}to{transform:translateY(0)}}
#msgMenuOv,#stickerSheet,#packView,#autoDelSheet,#installSheet,#lockSetSheet,
#devSheet,#storyOpts,#viewersOv{animation:fadeIn .22s ease}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
#scrollDownBtn{position:absolute;right:14px;bottom:88px;width:44px;height:44px;border-radius:50%;
 border:none;background:var(--panel2);color:var(--txt);display:flex;align-items:center;justify-content:center;
 box-shadow:0 4px 16px rgba(0,0,0,.4);cursor:pointer;z-index:15;opacity:0;transform:translateY(14px) scale(.8);
 pointer-events:none;transition:opacity .24s,transform .24s cubic-bezier(.34,1.56,.64,1)}
#scrollDownBtn.show{opacity:1;transform:none;pointer-events:auto}
#scrollDownBtn svg{width:22px;height:22px}
.heart-burst{position:fixed;font-size:32px;z-index:500;pointer-events:none;
 animation:heartUp .7s cubic-bezier(.3,1.2,.5,1) forwards}
@keyframes heartUp{0%{transform:scale(.3);opacity:0}35%{transform:scale(1.25);opacity:1}
 100%{transform:scale(1) translateY(-52px);opacity:0}}
.ava,.story-ring,.circle-msg{transform:translateZ(0)}
.typing{animation:typingBlink 1.4s ease-in-out infinite}
@keyframes typingBlink{0%,100%{opacity:1}50%{opacity:.55}}
.top{backdrop-filter:saturate(160%) blur(12px);-webkit-backdrop-filter:saturate(160%) blur(12px)}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}}
/* ===== конец PAYOM-UPDATE-v2 ===== */

/* ===== PAYOM-CHANNELS: стили ===== */
#scChannel{transform:translateX(100%)}
#scChannel.show{transform:translateX(0)}
#chFeed{display:block}
.ch-post{background:var(--panel);border-radius:16px;padding:13px 14px 10px;margin-bottom:12px;
 box-shadow:0 1px 3px rgba(0,0,0,.2);animation:chIn .32s cubic-bezier(.3,1.2,.5,1)}
@keyframes chIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
.ch-body{font-size:15px;line-height:1.45;word-wrap:break-word}
.ch-body img,.ch-body video{max-width:100%;border-radius:12px;display:block}
.ch-meta{display:flex;justify-content:space-between;align-items:center;margin-top:9px;
 font-size:12px;font-weight:600;color:var(--sub)}
.ch-views{display:flex;align-items:center;gap:5px}
.ch-views svg{width:14px;height:14px}
.ch-reacts{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px;align-items:center;position:relative}
.ch-react{background:var(--panel2);border-radius:14px;padding:4px 10px;font-size:13.5px;font-weight:700;
 cursor:pointer;transition:transform .14s cubic-bezier(.34,1.56,.64,1),background .18s}
.ch-react:active{transform:scale(.88)}
.ch-react.mine{background:rgba(124,92,255,.32);box-shadow:inset 0 0 0 1px var(--blue)}
.ch-addreact{width:30px;height:26px;border-radius:13px;background:var(--panel2);color:var(--sub);
 display:flex;align-items:center;justify-content:center;font-size:17px;font-weight:700;cursor:pointer}
.ch-addreact:active{transform:scale(.88)}
.ch-reactbar{position:absolute;bottom:34px;left:0;background:var(--panel2);border-radius:22px;
 padding:7px 10px;display:flex;gap:6px;box-shadow:0 6px 22px rgba(0,0,0,.45);z-index:40;
 animation:chIn .2s ease}
.ch-reactbar span{font-size:24px;cursor:pointer;transition:transform .15s cubic-bezier(.34,1.56,.64,1)}
.ch-reactbar span:active{transform:scale(1.35)}
.ch-acts{display:flex;gap:8px;margin-top:10px;padding-top:9px;border-top:1px solid var(--line)}
.ch-act{background:none;border:none;color:var(--sub);font-size:12.5px;font-weight:700;cursor:pointer;
 font-family:inherit;padding:3px 0}
.ch-act.del{color:#FF6B6B}
.ch-tag{background:var(--panel2);color:var(--sub);font-size:10.5px;font-weight:800;
 padding:2px 7px;border-radius:8px;text-transform:uppercase;vertical-align:1px}
#chComposer textarea{flex:1;border:none;border-radius:20px;background:var(--panel2);color:var(--txt);
 font-size:15px;padding:11px 15px;outline:none;resize:none;max-height:110px;font-family:inherit;font-weight:600}

/* PAYOM-PACK1: пересылка и списки */
.fwd-lbl{font-size:12.5px;font-weight:700;color:#A99BFF;margin-bottom:4px}
.row-title{font-size:16px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--txt)}
.row-sub{font-size:14px;color:var(--sub);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:3px}
#fwdSheet .row,#archSheet .row{cursor:pointer}

.ch-tag.off{background:rgba(124,92,255,.28);color:#B9A9FF}

/* Сердечко по двойному тапу */
.heart-pop{position:fixed;width:88px;height:88px;z-index:600;pointer-events:none;color:#FF3B5C;
 filter:drop-shadow(0 6px 18px rgba(255,59,92,.45));animation:heartPop .9s cubic-bezier(.2,1.3,.4,1) forwards}
.heart-pop svg{width:100%;height:100%}
@keyframes heartPop{
    0%{transform:scale(.2) rotate(-14deg);opacity:0}
    28%{transform:scale(1.15) rotate(4deg);opacity:1}
    45%{transform:scale(.95) rotate(0)}
    60%{transform:scale(1) rotate(0);opacity:1}
    100%{transform:scale(.9) translateY(-64px);opacity:0}
}
.m.liked,.ch-post.liked{animation:likedPulse .42s cubic-bezier(.34,1.56,.64,1)}
@keyframes likedPulse{0%{transform:scale(1)}45%{transform:scale(1.035)}100%{transform:scale(1)}}

/* Комментарии к публикациям */
.ch-cmt{display:inline-flex;align-items:center;gap:5px;background:var(--panel2);border-radius:14px;
 padding:4px 11px;font-size:13px;font-weight:700;color:var(--sub);cursor:pointer;
 transition:transform .14s cubic-bezier(.34,1.56,.64,1),background .18s}
.ch-cmt svg{width:15px;height:15px}
.ch-cmt:active{transform:scale(.9)}
#cmtSheet textarea{flex:1;border:none;border-radius:18px;background:var(--panel2);color:var(--txt);
 font-size:15px;padding:10px 14px;outline:none;resize:none;max-height:90px;font-family:inherit;font-weight:600}
</style>
</head>
<body>

<!-- ЭКРАН: СПИСОК ЧАТОВ -->
<div class="screen" id="scList">
    <div class="top">
        <div class="ava" id="myAva" style="width:38px;height:38px;font-size:15px;cursor:pointer" onclick="openSettings()" title="Настройки"><?= mb_strtoupper(mb_substr($MYNAME, 0, 1)) ?></div>
        <input type="file" id="avaFile" accept="image/*" style="display:none" onchange="uploadAva(this)">
        <h2>Payom</h2>
        <button class="icon-btn" onclick="location.href='messenger.php?logout=1'" title="Выйти">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/></svg>
        </button>
    </div>
    <div class="search-wrap"><input id="searchInput" type="text" placeholder="Поиск по имени или номеру…" oninput="onSearch(this.value)"></div>
    <input type="file" id="storyFile" accept="image/*,video/*" style="display:none" onchange="pickStory(this)">
    <div id="installBanner" style="display:none;align-items:center;gap:10px;padding:10px 14px;background:linear-gradient(135deg,#7C5CFF,#5B3FE0);color:#fff">
        <div style="width:36px;height:36px;border-radius:9px;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;flex-shrink:0"><svg viewBox="0 0 24 24" fill="#fff" width="20" height="20"><path d="M4 5a3 3 0 013-3h10a3 3 0 013 3v7a3 3 0 01-3 3H9l-4 4v-4a3 3 0 01-1-2V5z"/></svg></div>
        <div style="flex:1;min-width:0"><div id="installBigTxt" style="font-weight:800;font-size:14px">Установить Payom</div><div style="font-size:12px;opacity:.85">Быстрый доступ с экрана телефона</div></div>
        <button id="instBtn" onclick="doInstall()" style="background:#fff;color:#5B3FE0;border:none;border-radius:10px;padding:8px 16px;font-weight:800;font-size:13px;cursor:pointer;flex-shrink:0">Установить</button>
        <button onclick="dismissInstall()" style="background:none;border:none;color:#fff;font-size:22px;cursor:pointer;flex-shrink:0;padding:0 4px;line-height:1">×</button>
    </div>
    <div id="storiesBar" class="stories-bar"></div>
    <div class="list" id="listArea"></div>
    <button class="fab" onclick="toggleFabMenu(event)" title="Новое">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
    </button>
    <div id="fabMenu" style="display:none;position:fixed;right:18px;bottom:calc(90px + env(safe-area-inset-bottom));z-index:21;background:var(--panel);border:1px solid var(--line);border-radius:16px;box-shadow:0 12px 34px rgba(0,0,0,.45);overflow:hidden;min-width:210px">
        <button onclick="openContacts()" style="width:100%;display:flex;align-items:center;gap:14px;padding:14px 16px;background:none;border:none;color:var(--txt);font-size:15px;font-weight:700;cursor:pointer;font-family:inherit"><svg viewBox="0 0 24 24" fill="none" stroke="var(--blue)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="22" height="22"><path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/></svg>Контакты</button>
        <div style="height:1px;background:var(--line);margin:0 16px"></div>
        <button onclick="fabNewGroup()" style="width:100%;display:flex;align-items:center;gap:14px;padding:14px 16px;background:none;border:none;color:var(--txt);font-size:15px;font-weight:700;cursor:pointer;font-family:inherit"><svg viewBox="0 0 24 24" fill="none" stroke="var(--blue)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="22" height="22"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>Создать группу</button>
        <div style="height:1px;background:var(--line);margin:0 16px"></div>
        <button onclick="fabNewChannel()" style="width:100%;display:flex;align-items:center;gap:14px;padding:14px 16px;background:none;border:none;color:var(--txt);font-size:15px;font-weight:700;cursor:pointer;font-family:inherit"><svg viewBox="0 0 24 24" fill="none" stroke="var(--blue)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:22px;height:22px;flex-shrink:0"><path d="M3 11l18-8-8 18-2-7-8-3z"/></svg>Создать канал</button>
    </div>
</div>

<!-- ЭКРАН: ЧАТ -->
<div class="screen" id="scChat">
    <div class="top">
        <button class="icon-btn" onclick="closeChat()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button>
        <div class="ava" id="chatAva" style="width:40px;height:40px;font-size:16px">Ч</div>
        <div style="flex:1;min-width:0" onclick="chatHeaderTap()"><h2 id="chatTitle" style="font-size:16px">Чат</h2><div class="sub" id="chatSub"></div></div>
        <button class="icon-btn" onclick="toggleChatSearch()" title="Поиск"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.3-4.3"/></svg></button>
        <button class="icon-btn" id="videoBtn" onclick="videoCall()" title="Видеозвонок">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
        </button>
        <button class="icon-btn" id="callBtn" onclick="callPeer()" title="Позвонить">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.9v3a2 2 0 01-2.2 2 19.8 19.8 0 01-8.6-3.1 19.5 19.5 0 01-6-6 19.8 19.8 0 01-3.1-8.7A2 2 0 014.1 2h3a2 2 0 012 1.7c.1.9.4 1.8.7 2.7a2 2 0 01-.5 2.1L8.1 9.9a16 16 0 006 6l1.4-1.2a2 2 0 012.1-.5c.9.3 1.8.6 2.7.7a2 2 0 011.7 2z"/></svg>
        </button>
    </div>
    <div id="chatSearchBar" style="display:none;padding:9px 14px;background:var(--panel);border-bottom:1px solid var(--line)">
        <input id="chatSearchInput" type="text" placeholder="Поиск в чате…" oninput="searchInChat(this.value)" style="width:100%;padding:10px 14px;border:none;border-radius:18px;background:var(--panel2);color:#fff;font-size:15px;outline:none;font-weight:600;font-family:inherit">
        <div id="chatSearchResults"></div>
    </div>
    <div id="pinBar" style="display:none;align-items:center;gap:10px;padding:9px 14px;background:var(--panel);border-bottom:1px solid var(--line);cursor:pointer" onclick="jumpPinned()">
        <div style="width:3px;align-self:stretch;background:var(--blue);border-radius:2px"></div>
        <div style="flex:1;min-width:0"><div style="color:var(--blue);font-size:12px;font-weight:800">Закреплённое</div><div id="pinText" style="color:var(--sub);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"></div></div>
        <button class="icon-btn" style="width:34px;height:34px" onclick="event.stopPropagation();unpin()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
    </div>
    <div class="msgs" id="msgsArea"></div>
    <div class="reply-bar" id="replyBar">
        <div class="rb-line"></div>
        <div class="rb-main"><b id="rbName"></b><span id="rbText"></span></div>
        <button class="icon-btn" onclick="clearReply()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
    </div>
    <div id="attachPrev" style="display:none;padding:8px 14px 0;font-size:12.5px;font-weight:700;color:var(--blue)"></div>
    <div id="recBar" style="display:none;align-items:center;gap:12px;padding:12px 16px;background:var(--panel);border-top:1px solid var(--line)">
        <span style="width:12px;height:12px;border-radius:50%;background:#FF3B30;animation:recpulse 1s infinite"></span>
        <span id="recTime" style="font-size:16px;font-weight:800;font-variant-numeric:tabular-nums">0:00</span>
        <span id="recHint" style="flex:1;color:var(--sub);font-size:13px;font-weight:600;text-align:center">← отпустите для отправки</span>
        <span style="color:var(--sub);font-size:13px;font-weight:700">отмена</span>
    </div>
    <div id="mentionBox" style="display:none;position:absolute;left:8px;right:8px;bottom:100%;margin-bottom:6px;max-height:230px;overflow-y:auto;background:var(--panel);border:1px solid var(--line);border-radius:14px;box-shadow:0 -6px 20px rgba(0,0,0,.35);z-index:30"></div>
    <div class="composer" style="position:relative">
        <input type="file" id="fileImg" accept="image/*,video/*" style="display:none" onchange="pickFile(this)">
        <input type="file" id="fileDoc" style="display:none" onchange="pickFile(this)">
        <button class="cbtn" id="attachBtn" onclick="toggleAttachMenu()" title="Прикрепить">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.4 11l-8.5 8.5a5 5 0 01-7.1-7.1l8.5-8.5a3.3 3.3 0 014.7 4.7l-8.5 8.5a1.7 1.7 0 01-2.4-2.4l7.8-7.8"/></svg>
        </button>
        <button class="cbtn" id="stickerBtn" onclick="openStickers()" title="Стикеры">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16v10l-6 6H4z"/><path d="M14 20v-4a2 2 0 012-2h4"/><path d="M9 10h.01M15 10h.01"/></svg>
        </button>
        <textarea id="msgInput" rows="1" placeholder="Сообщение"></textarea>
        <button class="cbtn" id="circleBtn" title="Видео-кружок">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M10 9l5 3-5 3z" fill="currentColor"/></svg>
        </button>
        <button class="send" id="micBtn" title="Удерживайте для записи">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0014 0"/><path d="M12 17v4"/></svg>
        </button>
        <button class="send" id="sendBtn" style="display:none" onclick="sendMsg()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg>
        </button>
    </div>
    <div id="attachMenu" style="display:none;position:absolute;left:10px;bottom:70px;background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden;z-index:30;box-shadow:0 8px 30px rgba(0,0,0,.4)">
        <button class="am-item" onclick="document.getElementById('fileImg').click();toggleAttachMenu()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.6"/><path d="M21 15l-5-5L5 21"/></svg> Фото</button>
        <button class="am-item" onclick="document.getElementById('fileDoc').click();toggleAttachMenu()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/></svg> Файл</button>
    </div>
</div>
<!-- ПРОСМОТР НАБОРА СТИКЕРОВ (по тапу на стикер) -->
<div id="packView" style="display:none;position:fixed;inset:0;z-index:245;background:rgba(0,0,0,.5)" onclick="if(event.target===this)closePackView()">
    <div style="position:absolute;left:0;right:0;bottom:0;max-height:78vh;background:var(--bg);border-radius:18px 18px 0 0;display:flex;flex-direction:column">
        <div style="display:flex;align-items:center;gap:10px;padding:13px 16px;border-bottom:1px solid var(--line)">
            <div style="flex:1;min-width:0"><div id="pvTitle" style="font-weight:800;font-size:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Набор</div><div id="pvCount" style="color:var(--sub);font-size:12.5px;font-weight:700"></div></div>
            <button class="icon-btn" style="width:34px;height:34px" onclick="closePackView()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
        </div>
        <div id="pvBody" style="flex:1;overflow-y:auto;padding:12px 14px"></div>
        <div style="padding:12px 16px;border-top:1px solid var(--line)"><button id="pvBtn" class="st-btn" style="margin:0" onclick="pvToggle()">Добавить</button></div>
    </div>
</div>
<audio id="voicePlayer" style="display:none"></audio>
<!-- ПАНЕЛЬ СТИКЕРОВ -->
<input type="file" id="stickerFile" accept="image/*,video/*,.webm,.gif" style="display:none" onchange="uploadSticker(this)">
<div id="stickerSheet" style="display:none;position:fixed;inset:0;z-index:240;background:rgba(0,0,0,.5)" onclick="if(event.target===this)closeStickers()">
    <div style="position:absolute;left:0;right:0;bottom:0;max-height:70vh;background:var(--bg);border-radius:18px 18px 0 0;display:flex;flex-direction:column">
        <div style="display:flex;align-items:center;gap:10px;padding:13px 16px;border-bottom:1px solid var(--line)">
            <div style="font-weight:800;font-size:16px;flex:1">Стикеры</div>
            <button class="icon-btn" style="width:34px;height:34px" onclick="addPackPrompt()" title="Добавить набор"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg></button>
            <button class="icon-btn" style="width:34px;height:34px" onclick="createPackPrompt()" title="Создать набор"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.1 2.1 0 013 3L12 15l-4 1 1-4z"/></svg></button>
            <button class="icon-btn" style="width:34px;height:34px" onclick="closeStickers()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
        </div>
        <div id="stickerBody" style="flex:1;overflow-y:auto;padding:12px 14px"><div class="hint">Загрузка…</div></div>
    </div>
</div>
<div id="circleRec" style="display:none;position:fixed;inset:0;z-index:250;background:rgba(0,0,0,.85);flex-direction:column;align-items:center;justify-content:center;gap:20px">
    <div style="position:relative;width:260px;height:260px;border-radius:50%;overflow:hidden;box-shadow:0 0 0 4px #7C5CFF,0 20px 60px rgba(0,0,0,.6)">
        <video id="circlePreview" autoplay playsinline muted style="width:100%;height:100%;object-fit:cover;transform:scaleX(-1)"></video>
    </div>
    <div id="circleTime" style="color:#fff;font-size:20px;font-weight:800;font-variant-numeric:tabular-nums">0:00</div>
    <div style="color:rgba(255,255,255,.7);font-size:14px;font-weight:600">отпустите чтобы отправить · ↓ вниз для отмены</div>
</div>

<!-- ЭКРАН: НОВАЯ ГРУППА -->
<div class="screen" id="scGroup">
    <div class="top">
        <button class="icon-btn" onclick="closeNewGroup()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button>
        <h2>Новая группа</h2>
        <button class="icon-btn" onclick="createGroup()" title="Создать"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg></button>
    </div>
    <div class="search-wrap"><input id="groupName" type="text" placeholder="Название группы"></div>
    <div id="groupChips" class="gm-pick"></div>
    <div class="search-wrap"><input id="groupSearch" type="text" placeholder="Добавить участников по номеру…" oninput="onGroupSearch(this.value)"></div>
    <div class="list" id="groupResults"></div>
</div>

<!-- ЭКРАН: КОНТАКТЫ (список) -->
<div class="screen" id="scContacts">
    <div class="top">
        <button class="icon-btn" onclick="closeContacts()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button>
        <h2>Контакты</h2>
        <button class="icon-btn" onclick="openNewContact()" title="Создать контакт"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 8v6M22 11h-6M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8z"/></svg></button>
    </div>
    <div class="list" id="contactsList" style="padding:0"></div>
</div>

<!-- ЭКРАН: НОВЫЙ КОНТАКТ -->
<div class="screen" id="scContact">
    <div class="top">
        <button class="icon-btn" onclick="closeContact()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
        <h2 id="contactTitle">Новый контакт</h2>
        <button class="icon-btn" onclick="saveContact()" title="Сохранить" style="background:var(--blue);color:#fff;border-radius:50%"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg></button>
    </div>
    <div class="list" style="padding:0">
        <div style="display:flex;gap:14px;align-items:center;padding:18px 16px;background:var(--panel);margin-bottom:14px">
            <div class="ava" id="contactAva" style="width:64px;height:64px;font-size:26px;flex-shrink:0">?</div>
            <div style="flex:1;min-width:0">
                <input id="contactFirst" type="text" placeholder="Имя" oninput="contactAvaUpd()" style="width:100%;padding:10px 0;border:none;border-bottom:1.5px solid var(--line);background:none;color:var(--txt);font-size:17px;outline:none;font-weight:700;font-family:inherit">
                <input id="contactLast" type="text" placeholder="Фамилия" style="width:100%;padding:10px 0;border:none;background:none;color:var(--txt);font-size:16px;outline:none;font-weight:600;font-family:inherit">
            </div>
        </div>

        <div id="contactPhoneWrap" style="padding:14px 16px;background:var(--panel)">
            <div style="font-size:12px;font-weight:700;color:var(--sub);margin-bottom:6px">mobile</div>
            <input id="contactPhone" type="tel" placeholder="+992 …" style="width:100%;padding:6px 0;border:none;background:none;color:var(--txt);font-size:17px;outline:none;font-weight:700;font-family:inherit">
            <div id="contactPhoneHidden" style="display:none;color:var(--blue);font-size:17px;font-weight:700">Скрыт</div>
        </div>
        <div style="padding:8px 16px 16px;color:var(--sub);font-size:12.5px;font-weight:600;line-height:1.5" id="contactPhoneHint"></div>

        <div style="background:var(--panel);border-top:1px solid var(--line);border-bottom:1px solid var(--line)">
            <label style="display:flex;align-items:center;justify-content:space-between;padding:15px 16px;cursor:pointer">
                <span style="font-size:15px;font-weight:600">Показать номер телефона</span>
                <input type="checkbox" id="contactShare" checked style="width:0;height:0;opacity:0;position:absolute">
                <span class="tgl" id="contactShareTgl"></span>
            </label>
        </div>
        <div style="padding:8px 16px 16px;color:var(--sub);font-size:12.5px;font-weight:600;line-height:1.5">Вы можете разрешить этому человеку видеть Ваш номер телефона.</div>

        <div style="padding:0 16px">
            <input id="contactNote" type="text" placeholder="Заметка (будет видна только Вам)" style="width:100%;padding:15px;border:none;border-radius:14px;background:var(--panel);color:var(--txt);font-size:15px;outline:none;font-weight:600;font-family:inherit">
        </div>
    </div>
</div>

<!-- ЭКРАН: НАСТРОЙКИ / ПРОФИЛЬ -->
<div class="screen" id="scSettings">
    <div class="top">
        <button class="icon-btn" onclick="closeSettings()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button>
        <h2>Настройки</h2>
        <button class="icon-btn" onclick="saveProfile()" title="Сохранить"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg></button>
    </div>
    <div class="list" style="padding:0">
        <div style="text-align:center;padding:26px 20px 20px;background:var(--panel);border-bottom:1px solid var(--line)">
            <div style="position:relative;width:110px;height:110px;margin:0 auto 8px">
                <div class="ava" id="setAva" style="width:110px;height:110px;font-size:44px">?</div>
                <button onclick="document.getElementById('avaFile').click()" style="position:absolute;right:0;bottom:0;width:36px;height:36px;border-radius:50%;border:3px solid var(--panel);background:var(--blue);color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="17" height="17"><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/><circle cx="12" cy="13" r="4"/></svg>
                </button>
            </div>
            <div style="color:var(--sub);font-size:13px;font-weight:600" id="setPhone"></div>
        </div>
        <div style="padding:16px">
            <label style="font-size:12px;font-weight:800;color:var(--blue);text-transform:uppercase">Имя</label>
            <input id="setName" type="text" placeholder="Ваше имя" style="width:100%;padding:13px 0;border:none;border-bottom:1.5px solid var(--line);background:none;color:#fff;font-size:16px;outline:none;font-weight:600;font-family:inherit;margin-bottom:18px">
            <label style="font-size:12px;font-weight:800;color:var(--blue);text-transform:uppercase">Имя пользователя (username)</label>
            <div style="display:flex;align-items:center;border-bottom:1.5px solid var(--line)">
                <span style="color:var(--sub);font-size:16px;font-weight:700">@</span>
                <input id="setUsername" type="text" placeholder="username" oninput="checkUsername()" autocapitalize="off" autocorrect="off" spellcheck="false" style="flex:1;padding:13px 4px;border:none;background:none;color:#fff;font-size:16px;outline:none;font-weight:600;font-family:inherit">
            </div>
            <div id="unameStatus" style="font-size:12.5px;font-weight:700;margin:6px 0 18px;min-height:16px"></div>
            <label style="font-size:12px;font-weight:800;color:var(--blue);text-transform:uppercase">О себе</label>
            <textarea id="setBio" rows="2" placeholder="Напишите несколько строк о себе" style="width:100%;padding:13px 0;border:none;border-bottom:1.5px solid var(--line);background:none;color:#fff;font-size:16px;outline:none;font-weight:600;font-family:inherit;resize:none;margin-bottom:8px"></textarea>
        </div>
        <div class="st-h">Личное</div>
        <div class="st-row"><label><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-8H4v8M4 13c0-1.5 1-2.5 2.5-2.5S9 11.5 9 13m0 0c0-1.5 1-2.5 2.5-2.5S14 11.5 14 13m0 0c0-1.5 1-2.5 2.5-2.5S19 11.5 19 13M12 8V4M9 5a3 3 0 006 0"/></svg>День рождения</label><input type="date" id="setBday"></div>

        <div class="st-h">Приватность</div>
        <div class="st-row"><label>Кто видит «был в сети»</label>
            <select id="setPls"><option value="all">Все</option><option value="nobody">Никто</option></select></div>
        <div class="st-row"><label>Кто может звонить</label>
            <select id="setPc"><option value="all">Все</option><option value="nobody">Никто</option></select></div>
        <div class="st-row"><label>Кто видит мой номер</label>
            <select id="setPp"><option value="all">Все</option><option value="nobody">Никто</option></select></div>
        <div class="st-row" onclick="openBlocked()" style="cursor:pointer"><label><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M5.6 5.6l12.8 12.8"/></svg>Заблокированные</label><span class="rr" id="blockedCount">›</span></div>

        <div class="st-h">Оформление</div>
        <div class="st-row"><label><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg>Светлая тема</label><div class="st-sw" id="swTheme" onclick="toggleTheme()"></div></div>
        <div class="st-row"><label><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7V5h16v2M9 20h6M12 5v15"/></svg>Размер текста</label>
            <select id="setFont" onchange="setFont(this.value)"><option value="small">Мелкий</option><option value="normal">Обычный</option><option value="large">Крупный</option></select></div>

        <div class="st-h">Уведомления</div>
        <div class="st-row"><label><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 00-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0"/></svg>Звук и вибрация</label><div class="st-sw" id="swNotif" onclick="toggleNotif()"></div></div>

        <div class="st-h">Безопасность</div>
        <div style="padding:14px 16px;background:var(--panel)">
            <button class="st-btn" id="installRow" style="background:linear-gradient(135deg,#8E6BFF,#5B3FE0);color:#fff" onclick="doInstall()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M8 11l4 4 4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"/></svg><span id="installRowTxt">Установить приложение</span></button>
            <button class="st-btn" id="faceBtn" style="background:var(--panel2);color:var(--txt)" onclick="faceSetting()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3H5a2 2 0 00-2 2v2M17 3h2a2 2 0 012 2v2M7 21H5a2 2 0 01-2-2v-2M17 21h2a2 2 0 002-2v-2M9 10h.01M15 10h.01M9 15c.8.7 1.9 1 3 1s2.2-.3 3-1"/></svg><span id="faceBtnTxt">Вход по лицу</span></button>
            <button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="openLockSettings()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/></svg>Блокировка приложения</button>
            <button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="openDevices()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/></svg>Устройства (активные сеансы)</button>
            <button class="st-btn" id="sndBtn" style="background:var(--panel2);color:var(--txt);display:flex;align-items:center;justify-content:space-between" onclick="toggleSnd()"><span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;vertical-align:-4px;margin-right:9px"><path d="M11 5L6 9H2v6h4l5 4V5zM15.5 8.5a5 5 0 010 7M19 5a9 9 0 010 14"/></svg>Звук сообщений</span><span id="sndState" style="color:var(--blue)">Вкл</span></button>
            <button class="st-btn" id="e2eBtn" style="background:var(--panel2);color:var(--txt);display:flex;align-items:center;justify-content:space-between" onclick="toggleE2E()"><span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;vertical-align:-4px;margin-right:9px"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/></svg>Сквозное шифрование</span><span id="e2eState" style="color:var(--sub)">Выкл</span></button>
            <button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="shareMyProfile()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;vertical-align:-4px;margin-right:9px"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>Моя ссылка на профиль</button>
            <button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="logoutAll()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>Выйти на всех устройствах</button>
            <button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="clearCacheAll()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>Очистить кэш</button>
        </div>

        <div class="st-h">Аккаунт</div>
        <div style="padding:14px 16px 40px;background:var(--panel)">
            <button class="st-btn" style="background:#3A2226;color:#FF6B6B" onclick="location.href='messenger.php?logout=1'">Выйти из аккаунта</button>
            <button class="st-btn" style="background:none;color:#FF6B6B;border:1.5px solid #FF6B6B" onclick="deleteAccount()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>Удалить аккаунт навсегда</button>
        </div>

        <!-- список заблокированных -->
        <div id="blockedOv" style="display:none;position:fixed;inset:0;z-index:210;background:var(--bg)">
            <div class="top"><button class="icon-btn" onclick="document.getElementById('blockedOv').style.display='none'"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button><h2>Заблокированные</h2></div>
            <div class="list" id="blockedList"></div>
        </div>
    </div>
</div>

<!-- ЭКРАН: ИНФО О ЧАТЕ / ПРОФИЛЬ -->
<div class="screen" id="scInfo">
    <div class="top">
        <button class="icon-btn" onclick="closeInfo()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button>
        <h2 id="infoTitle">Информация</h2>
        <button class="icon-btn" id="infoEditBtn" style="display:none" onclick="editGroup()" title="Редактировать"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/></svg></button>
    </div>
    <input type="file" id="gavaFile" accept="image/*" style="display:none" onchange="uploadGroupAva(this)">
    <div class="list" id="infoBody"></div>
</div>

<!-- Оверлей: добавить участника -->
<div id="addMemberOv" style="display:none;position:fixed;inset:0;z-index:210;background:var(--bg)">
    <div class="top"><button class="icon-btn" onclick="document.getElementById('addMemberOv').style.display='none'"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button><h2>Добавить участника</h2></div>
    <div class="search-wrap"><input id="addMemberSearch" type="text" placeholder="Поиск по номеру или имени…" oninput="addMemberSearch(this.value)"></div>
    <div class="list" id="addMemberResults"></div>
</div>

<!-- Оверлей: профиль пользователя (тап в группе) -->
<div id="userProfileOv" style="display:none;position:fixed;inset:0;z-index:215;background:var(--bg)">
    <div class="top"><button class="icon-btn" onclick="document.getElementById('userProfileOv').style.display='none'"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button><h2>Профиль</h2><button class="icon-btn" id="profChatBtn" style="margin-left:auto;display:none;color:var(--blue)" onclick="profWrite()" title="Написать"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 01-8.5 8.5 8.4 8.4 0 01-3.8-.9L3 21l1.9-5.7A8.4 8.4 0 013.5 12 8.4 8.4 0 0112 3.5h.5A8.4 8.4 0 0121 11.5z"/></svg></button></div>
    <div class="list" id="userProfileBody"></div>
</div>

<!-- Настройки добавления истории -->
<div id="storyOpts" style="display:none;position:fixed;inset:0;z-index:290;background:rgba(0,0,0,.6);align-items:flex-end;justify-content:center">
    <div style="background:var(--panel);width:100%;max-width:520px;border-radius:20px 20px 0 0;padding:18px 18px calc(20px + env(safe-area-inset-bottom))">
        <div style="width:40px;height:4px;background:var(--panel2);border-radius:2px;margin:0 auto 16px"></div>
        <div style="text-align:center;margin-bottom:14px"><img id="storyPrev" style="max-width:120px;max-height:150px;border-radius:12px"></div>
        <input id="storyCaption" type="text" placeholder="Подпись (необязательно)" maxlength="300" style="width:100%;padding:12px 14px;border:none;border-radius:12px;background:var(--panel2);color:#fff;font-size:15px;outline:none;font-weight:600;margin-bottom:14px;font-family:inherit">
        <div style="color:var(--sub);font-size:12px;font-weight:800;text-transform:uppercase;margin-bottom:8px">Сколько хранить</div>
        <div class="seg" id="storyHours">
            <button data-v="1" onclick="segPick('storyHours',this)">1 час</button>
            <button data-v="6" onclick="segPick('storyHours',this)">6 часов</button>
            <button data-v="24" class="on" onclick="segPick('storyHours',this)">24 часа</button>
        </div>
        <div style="color:var(--sub);font-size:12px;font-weight:800;text-transform:uppercase;margin:14px 0 8px">Кто увидит</div>
        <div class="seg" id="storyAud">
            <button data-v="all" class="on" onclick="segPick('storyAud',this)">Все</button>
            <button data-v="contacts" onclick="segPick('storyAud',this)">Контакты</button>
        </div>
        <div style="margin-top:14px">
            <button id="pollToggle" class="st-btn" style="background:var(--panel2);color:var(--txt);margin:0" onclick="togglePollForm()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;vertical-align:-4px;margin-right:8px"><path d="M4 20V10M12 20V4M20 20v-6"/></svg>Добавить опрос</button>
            <div id="pollForm" style="display:none;margin-top:10px">
                <input id="pollQ" type="text" placeholder="Вопрос" maxlength="120" style="width:100%;padding:11px 13px;border:none;border-radius:11px;background:var(--panel2);color:#fff;font-size:14px;outline:none;font-weight:600;margin-bottom:8px;font-family:inherit">
                <input class="pollOpt" type="text" placeholder="Вариант 1" maxlength="60" style="width:100%;padding:10px 13px;border:none;border-radius:11px;background:var(--panel2);color:#fff;font-size:14px;outline:none;font-weight:600;margin-bottom:7px;font-family:inherit">
                <input class="pollOpt" type="text" placeholder="Вариант 2" maxlength="60" style="width:100%;padding:10px 13px;border:none;border-radius:11px;background:var(--panel2);color:#fff;font-size:14px;outline:none;font-weight:600;margin-bottom:7px;font-family:inherit">
                <input class="pollOpt" type="text" placeholder="Вариант 3 (необязательно)" maxlength="60" style="width:100%;padding:10px 13px;border:none;border-radius:11px;background:var(--panel2);color:#fff;font-size:14px;outline:none;font-weight:600;margin-bottom:7px;font-family:inherit">
                <input class="pollOpt" type="text" placeholder="Вариант 4 (необязательно)" maxlength="60" style="width:100%;padding:10px 13px;border:none;border-radius:11px;background:var(--panel2);color:#fff;font-size:14px;outline:none;font-weight:600;font-family:inherit">
            </div>
        </div>
        <button class="st-btn" style="background:var(--blue);color:#fff;margin-top:18px" onclick="publishStory()">Опубликовать</button>
        <button class="st-btn" style="background:var(--panel2);color:var(--txt);margin-bottom:0" onclick="document.getElementById('storyOpts').style.display='none'">Отмена</button>
    </div>
</div>

<!-- Просмотр историй -->
<div id="storyViewer" style="display:none;position:fixed;top:var(--vv-top,0);left:0;right:0;height:var(--app-h,100dvh);z-index:310;background:#000;flex-direction:column">
    <div id="storyBars" style="display:flex;gap:4px;padding:10px 12px 6px;position:relative;z-index:3"></div>
    <div style="display:flex;align-items:center;gap:10px;padding:2px 14px 10px;position:relative;z-index:3">
        <div class="ava" id="svAva" style="width:38px;height:38px;font-size:15px"></div>
        <div style="flex:1;min-width:0"><div id="svName" style="color:#fff;font-weight:800;font-size:15px"></div><div id="svTime" style="color:rgba(255,255,255,.6);font-size:12px;font-weight:600"></div></div>
        <button class="icon-btn" id="svDel" style="color:#fff;display:none" onclick="deleteCurStory()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg></button>
        <button class="icon-btn" style="color:#fff" onclick="closeStoryViewer()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
    </div>
    <div id="storyStage" style="flex:1;position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden">
        <img id="svImg" style="max-width:100%;max-height:100%;display:none">
        <video id="svVid" playsinline style="max-width:100%;max-height:100%;display:none"></video>
        <div id="svCaption" style="position:absolute;left:0;right:0;bottom:14px;padding:0 18px;color:#fff;font-size:15px;font-weight:600;text-shadow:0 2px 8px rgba(0,0,0,.7);text-align:center"></div>
        <div id="svPoll" onpointerdown="event.stopPropagation()" onpointerup="event.stopPropagation()" style="display:none;position:absolute;left:16px;right:16px;bottom:70px;background:rgba(0,0,0,.55);backdrop-filter:blur(10px);border-radius:16px;padding:14px 14px 12px;z-index:4"></div>
        <div style="position:absolute;left:0;top:0;bottom:0;width:33%"></div>
        <div style="position:absolute;right:0;top:0;bottom:0;width:33%"></div>
    </div>
    <div id="svFooter" style="padding:12px 14px calc(14px + env(safe-area-inset-bottom));position:relative;z-index:3">
        <div id="svOwnerBar" style="display:none;text-align:center"><button class="st-btn" style="background:rgba(255,255,255,.15);color:#fff;margin:0" onclick="openViewers()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="17" height="17" style="vertical-align:-3px;margin-right:6px"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/></svg><span id="svViewCount">0</span> просмотров</button></div>
        <div id="svViewerBar" style="display:none;align-items:center;gap:8px">
            <input id="svReply" type="text" placeholder="Ответить…" style="flex:1;padding:11px 15px;border:none;border-radius:20px;background:rgba(255,255,255,.15);color:#fff;font-size:15px;outline:none;font-weight:600;font-family:inherit">
            <button class="cbtn" style="color:#fff" onclick="sendStoryReply()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg></button>
            <div style="display:flex;gap:6px" id="svReax"></div>
        </div>
    </div>
</div>

<!-- Зрители истории -->
<div id="viewersOv" style="display:none;position:fixed;inset:0;z-index:320;background:rgba(0,0,0,.6);align-items:flex-end;justify-content:center" onclick="if(event.target===this)this.style.display='none'">
    <div style="background:var(--panel);width:100%;max-width:520px;border-radius:20px 20px 0 0;max-height:70vh;display:flex;flex-direction:column">
        <div style="padding:16px;text-align:center;font-weight:800;border-bottom:1px solid var(--line)">Просмотры</div>
        <div class="list" id="viewersList" style="padding:6px 0"></div>
    </div>
</div>

<!-- Экран блокировки приложения -->
<div id="lockScreen" style="display:none;position:fixed;inset:0;z-index:400;background:radial-gradient(1100px 560px at 50% -8%,#2C2350 0%,#171626 45%,#111019 100%);flex-direction:column;align-items:center;justify-content:center;padding:28px">
    <div style="width:78px;height:78px;border-radius:22px;background:linear-gradient(140deg,#9575FF,#5B3FE0);display:flex;align-items:center;justify-content:center;box-shadow:0 14px 34px rgba(124,92,255,.5);margin-bottom:18px"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" width="34" height="34"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/></svg></div>
    <div style="font-size:20px;font-weight:800;color:#fff;margin-bottom:6px">Payom заблокирован</div>
    <div style="font-size:13.5px;font-weight:600;color:#9090A8;margin-bottom:22px">Введите пароль для входа</div>
    <input id="lockPin" type="password" inputmode="numeric" maxlength="12" placeholder="Пароль" style="width:100%;max-width:280px;padding:15px;border:1.5px solid #33334A;border-radius:14px;background:#15151F;color:#fff;font-size:20px;text-align:center;letter-spacing:6px;outline:none;font-weight:700;font-family:inherit" onkeydown="if(event.key==='Enter')tryUnlockPin()">
    <div id="lockErr" style="color:#FF6B6B;font-size:13px;font-weight:700;margin-top:10px;height:16px"></div>
    <button onclick="tryUnlockPin()" style="width:100%;max-width:280px;padding:15px;border:none;border-radius:14px;background:linear-gradient(135deg,#8E6BFF,#5B3FE0);color:#fff;font-size:15px;font-weight:800;cursor:pointer;font-family:inherit;margin-top:14px">Разблокировать</button>
    <button id="lockBioBtn" onclick="tryUnlockBio()" style="display:none;width:100%;max-width:280px;padding:14px;border:none;border-radius:14px;background:rgba(255,255,255,.08);color:#fff;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;margin-top:10px;align-items:center;justify-content:center;gap:8px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="20" height="20" style="vertical-align:-5px;margin-right:6px"><path d="M12 11v4M8.5 8a5 5 0 017 0M5.5 5.5a9 9 0 0113 0M8 15a4 4 0 018 0M6 18a7 7 0 0112 0"/></svg>Face ID / отпечаток</button>
</div>

<!-- Устройства (активные сеансы) -->
<div id="devSheet" style="display:none;position:fixed;inset:0;z-index:330;background:rgba(0,0,0,.6);align-items:flex-end;justify-content:center" onclick="if(event.target===this)this.style.display='none'">
    <div style="background:var(--panel);width:100%;max-width:520px;border-radius:22px 22px 0 0;padding:20px 18px calc(24px + env(safe-area-inset-bottom));max-height:82vh;overflow-y:auto">
        <div style="width:40px;height:4px;background:var(--panel2);border-radius:2px;margin:0 auto 16px"></div>
        <div style="font-size:18px;font-weight:800;text-align:center;margin-bottom:6px">Устройства</div>
        <div style="font-size:13px;font-weight:600;color:var(--sub);text-align:center;margin-bottom:16px">Где выполнен вход в ваш аккаунт</div>
        <div id="devBody"><div class="hint">Загрузка…</div></div>
    </div>
</div>

<!-- Настройка блокировки -->
<div id="lockSetSheet" style="display:none;position:fixed;inset:0;z-index:330;background:rgba(0,0,0,.6);align-items:flex-end;justify-content:center" onclick="if(event.target===this)this.style.display='none'">
    <div style="background:var(--panel);width:100%;max-width:520px;border-radius:22px 22px 0 0;padding:20px 18px calc(24px + env(safe-area-inset-bottom))">
        <div style="width:40px;height:4px;background:var(--panel2);border-radius:2px;margin:0 auto 16px"></div>
        <div style="font-size:18px;font-weight:800;text-align:center;margin-bottom:16px">Блокировка приложения</div>
        <div id="lockSetBody"></div>
    </div>
</div>

<!-- Окно выбора автоудаления -->
<div id="autoDelSheet" style="display:none;position:fixed;inset:0;z-index:330;background:rgba(0,0,0,.6);align-items:flex-end;justify-content:center" onclick="if(event.target===this)this.style.display='none'">
    <div style="background:var(--panel);width:100%;max-width:520px;border-radius:22px 22px 0 0;padding:20px 18px calc(24px + env(safe-area-inset-bottom))">
        <div style="width:40px;height:4px;background:var(--panel2);border-radius:2px;margin:0 auto 16px"></div>
        <div style="font-size:18px;font-weight:800;text-align:center;margin-bottom:6px">Автоудаление сообщений</div>
        <div style="font-size:13px;font-weight:600;color:var(--sub);text-align:center;margin-bottom:16px">Новые сообщения будут удаляться у всех через выбранное время</div>
        <div id="autoDelOpts"></div>
    </div>
</div>

<!-- Окно установки: Android + iPhone -->
<div id="installSheet" style="display:none;position:fixed;inset:0;z-index:330;background:rgba(0,0,0,.6);align-items:flex-end;justify-content:center" onclick="if(event.target===this)closeInstallSheet()">
    <div style="background:var(--panel);width:100%;max-width:520px;border-radius:22px 22px 0 0;padding:22px 20px calc(26px + env(safe-area-inset-bottom))">
        <div style="width:40px;height:4px;background:var(--panel2);border-radius:2px;margin:0 auto 18px"></div>
        <div style="width:64px;height:64px;border-radius:18px;margin:0 auto 12px;background:linear-gradient(140deg,#9575FF,#5B3FE0);display:flex;align-items:center;justify-content:center;box-shadow:0 10px 26px rgba(124,92,255,.5)"><svg viewBox="0 0 24 24" fill="#fff" width="34" height="34"><path d="M4 5a3 3 0 013-3h10a3 3 0 013 3v7a3 3 0 01-3 3H9l-4 4v-4a3 3 0 01-1-2V5z"/></svg></div>
        <div style="font-size:20px;font-weight:800;text-align:center">Установить Payom</div>
        <div style="font-size:13.5px;font-weight:600;color:var(--sub);text-align:center;margin:4px 0 18px">Выберите ваше устройство</div>

        <button onclick="chooseAndroid()" style="width:100%;display:flex;align-items:center;gap:14px;background:var(--panel2);border:1px solid var(--line);border-radius:16px;padding:14px 16px;margin-bottom:12px;cursor:pointer;color:var(--txt);text-align:left">
            <svg viewBox="0 0 24 24" fill="#3DDC84" width="30" height="30" style="flex-shrink:0"><path d="M17.6 9.5 19 7a.4.4 0 0 0-.15-.55.4.4 0 0 0-.54.15L16.87 9.1A11 11 0 0 0 12 8a11 11 0 0 0-4.87 1.1L5.7 6.6a.4.4 0 0 0-.54-.15A.4.4 0 0 0 5 7l1.4 2.5A9.2 9.2 0 0 0 2 16h20a9.2 9.2 0 0 0-4.4-6.5ZM7.5 13.6a.9.9 0 1 1 .9-.9.9.9 0 0 1-.9.9Zm9 0a.9.9 0 1 1 .9-.9.9.9 0 0 1-.9.9Z"/></svg>
            <div style="flex:1"><div style="font-weight:800;font-size:15px">Android</div><div style="font-size:12.5px;color:var(--sub);font-weight:600" id="andSub">Скачать приложение (APK)</div></div>
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--sub)" stroke-width="2.4" width="18" height="18"><path d="M9 6l6 6-6 6"/></svg>
        </button>

        <button onclick="chooseIOS()" style="width:100%;display:flex;align-items:center;gap:14px;background:var(--panel2);border:1px solid var(--line);border-radius:16px;padding:14px 16px;cursor:pointer;color:var(--txt);text-align:left">
            <svg viewBox="0 0 24 24" fill="var(--txt)" width="28" height="28" style="flex-shrink:0"><path d="M16.4 12.8c0-2.3 1.9-3.4 2-3.5-1.1-1.6-2.8-1.8-3.4-1.8-1.4-.1-2.8.9-3.5.9s-1.8-.8-3-.8c-1.5 0-2.9.9-3.7 2.3-1.6 2.7-.4 6.8 1.1 9 .7 1.1 1.6 2.3 2.8 2.2 1.1 0 1.5-.7 2.9-.7s1.7.7 2.9.7 2-1.1 2.7-2.1c.8-1.2 1.2-2.4 1.2-2.5-.1 0-2.3-.9-2.3-3.6ZM14.2 5.9c.6-.8 1-1.8.9-2.9-.9 0-2 .6-2.6 1.4-.6.7-1.1 1.7-.9 2.7 1 .1 2-.5 2.6-1.2Z"/></svg>
            <div style="flex:1"><div style="font-weight:800;font-size:15px">iPhone</div><div style="font-size:12.5px;color:var(--sub);font-weight:600">Установить на экран «Домой»</div></div>
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--sub)" stroke-width="2.4" width="18" height="18"><path d="M9 6l6 6-6 6"/></svg>
        </button>

        <div id="installSteps" style="display:none;margin-top:16px;background:var(--panel2);border-radius:14px;padding:16px;text-align:left;font-size:14.5px;font-weight:600;line-height:1.9"></div>

        <button class="st-btn" style="background:var(--blue);color:#fff;margin-top:16px" onclick="closeInstallSheet()">Закрыть</button>
    </div>
</div>

<!-- Просмотр фото на весь экран -->
<div id="imgViewer" onclick="closeViewer(event)"><img id="imgViewerImg" src=""><video id="imgViewerVid" playsinline controls style="display:none;max-width:100%;max-height:100%"></video></div>

<!-- Меню действий над сообщением -->
<div id="msgMenuOv" style="display:none;position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.5)" onclick="if(event.target===this)closeMsgMenu()">
    <div style="position:absolute;left:0;right:0;bottom:0;background:var(--panel);border-radius:20px 20px 0 0;padding:12px 10px calc(14px + env(safe-area-inset-bottom))">
        <div style="display:flex;justify-content:space-around;padding:8px 4px 14px;border-bottom:1px solid var(--line);margin-bottom:6px">
            <button class="reax" onclick="doReact('👍')">👍</button>
            <button class="reax" onclick="doReact('❤️')">❤️</button>
            <button class="reax" onclick="doReact('😂')">😂</button>
            <button class="reax" onclick="doReact('🔥')">🔥</button>
            <button class="reax" onclick="doReact('😮')">😮</button>
            <button class="reax" onclick="doReact('😢')">😢</button>
        </div>
        <button class="mmi" onclick="menuReply()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 17l-5-5 5-5"/><path d="M4 12h11a4 4 0 014 4v2"/></svg> Ответить</button>
        <button class="mmi" onclick="menuCopy()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg> Копировать</button>
        <button class="mmi" onclick="menuLink()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 007 0l3-3a5 5 0 00-7-7l-1 1"/><path d="M14 11a5 5 0 00-7 0l-3 3a5 5 0 007 7l1-1"/></svg> Копировать ссылку</button>
        <button class="mmi" onclick="menuPin()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 17v5M5 9l7-7 7 7-3 3v4H8v-4z"/></svg> Закрепить</button>
        <button class="mmi" id="mmiEdit" onclick="menuEdit()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/></svg> Редактировать</button>
        <button class="mmi del" id="mmiDel" onclick="menuDelete()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg> Удалить</button>
    </div>
</div>

<script>
const ME = <?= $ME ?>;
// Цвета имён участников в группах (разный цвет каждому — как в Telegram)
const NAME_COLORS=['#E17076','#EE9CBF','#A695E7','#7BC862','#6EC9CB','#65AADD','#EE7AAE','#F2A63F','#D389E0','#82C74B'];
function userColor(id){ id=Math.abs(parseInt(id)||0); return NAME_COLORS[id % NAME_COLORS.length]; }
const SVG_BELL='<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 00-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 01-3.4 0"/></svg>';
const SVG_BELLOFF='<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.7 21a2 2 0 01-3.4 0"/><path d="M18.6 13A9 9 0 0018 8a6 6 0 00-9.3-5"/><path d="M6 8a6 6 0 00-.3 2c0 7-3 9-3 9h13"/><path d="M2 2l20 20"/></svg>';
const SVG_BELLOFF_SM='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px;vertical-align:-2px"><path d="M18.6 13A9 9 0 0018 8a6 6 0 00-9.3-5"/><path d="M6 8a6 6 0 00-.3 2c0 7-3 9-3 9h13"/><path d="M2 2l20 20"/></svg>';
const SVG_TRASH='<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>';
window.HAS_APK = <?= file_exists(__DIR__ . '/payom.apk') ? 'true' : 'false' ?>;
const MYNAME = <?= json_encode($MYNAME, JSON_UNESCAPED_UNICODE) ?>;
const VAPID_PUBLIC = '<?= defined('VAPID_PUBLIC') ? VAPID_PUBLIC : '' ?>';
let curChat = null, curType = 'private', curPeer = 0, curTitle = '', curAvatar = '', replyTo = null, seenMaxId = 0;
// ===== Звуки сообщений (как в Telegram, без файла — Web Audio) =====
function e2eEnabled(){ return localStorage.getItem('e2e')==='on'; } // по умолчанию ВЫКЛ — чтобы сообщения были видны
let _actx=null;
function _sndCtx(){ if(!_actx){ try{ _actx=new (window.AudioContext||window.webkitAudioContext)(); }catch(e){} } return _actx; }
function playSnd(kind){
    if(localStorage.getItem('sndOff')==='1') return;    const ctx=_sndCtx(); if(!ctx) return;
    try{ if(ctx.state==='suspended') ctx.resume(); }catch(e){}
    try{
        const t=ctx.currentTime; const o=ctx.createOscillator(), g=ctx.createGain();
        o.connect(g); g.connect(ctx.destination); o.type='sine';
        if(kind==='send'){ // короткий восходящий «поп»
            o.frequency.setValueAtTime(620,t); o.frequency.exponentialRampToValueAtTime(1020,t+0.09);
            g.gain.setValueAtTime(0.0001,t); g.gain.exponentialRampToValueAtTime(0.15,t+0.012); g.gain.exponentialRampToValueAtTime(0.0001,t+0.17);
            o.start(t); o.stop(t+0.19);
        } else { // мягкий нисходящий «дзинь» при получении
            o.frequency.setValueAtTime(900,t); o.frequency.exponentialRampToValueAtTime(560,t+0.13);
            g.gain.setValueAtTime(0.0001,t); g.gain.exponentialRampToValueAtTime(0.17,t+0.014); g.gain.exponentialRampToValueAtTime(0.0001,t+0.24);
            o.start(t); o.stop(t+0.26);
        }
    }catch(e){}
}
function updSndState(){ const s=document.getElementById('sndState'); if(s) s.textContent=(localStorage.getItem('sndOff')==='1')?'Выкл':'Вкл'; }
function toggleSnd(){ localStorage.setItem('sndOff', localStorage.getItem('sndOff')==='1'?'0':'1'); updSndState(); if(localStorage.getItem('sndOff')!=='1') playSnd('send'); }
function updE2EState(){ const s=document.getElementById('e2eState'); if(s){ const on=e2eEnabled(); s.textContent=on?'Вкл':'Выкл'; s.style.color=on?'var(--blue)':'var(--sub)'; } }
function toggleE2E(){
    if(e2eEnabled()){ localStorage.setItem('e2e','off'); }
    else { if(!confirm('Включить сквозное шифрование?\n\nСообщения будут шифроваться так, что сервер их не прочитает. НО если у вас или собеседника разойдутся ключи (смена телефона, очистка кэша) — часть сообщений может не расшифроваться и покажет «зашифровано».\n\nДля обычного общения шифрование можно не включать.')) return; localStorage.setItem('e2e','on'); ensureE2E(); }
    updE2EState();
}
let msgPoll = null, lastMsgId = 0, listPoll = null;

function esc(s){const d=document.createElement('div');d.textContent=s||'';return d.innerHTML;}
// сообщение только из эмодзи (1-3) → крупно
function emojiOnly(t){
    if(!t) return 0;
    const s=t.trim(); if(!s) return 0;
    let rest;
    try{ rest=s.replace(/\s/g,'').replace(/[\u200d\uFE0F]/gu,'').replace(/\p{Extended_Pictographic}/gu,''); }
    catch(e){ return 0; }
    if(rest!=='') return 0;
    const m=s.match(/\p{Extended_Pictographic}/gu);
    return m ? m.length : 0;
}
// Кликабельные ссылки и @username в тексте (жирным)
function linkify(raw){
    if(!raw) return '';
    const re=/((?:https?:\/\/|www\.)[^\s<]+)|(@[A-Za-z0-9_]{3,32})/g;
    let out='', last=0, m;
    while((m=re.exec(raw))){
        out += esc(raw.slice(last, m.index));
        if(m[1]){
            let url=m[1], trail='';
            const tm=url.match(/[.,!?;:)\]]+$/); if(tm){ trail=tm[0]; url=url.slice(0, url.length-trail.length); }
            let href = /^www\./i.test(url) ? ('https://'+url) : url;
            out += `<a class="msg-link" href="${esc(href)}" target="_blank" rel="noopener" onclick="return onMsgLink(event,'${esc(href).replace(/'/g,"\\'")}')">${esc(url)}</a>`+esc(trail);
        } else if(m[2]){
            const un=m[2].slice(1);
            out += `<a class="msg-link" onclick="event.stopPropagation();openByUsername('${un}')">${esc(m[2])}</a>`;
        }
        last = m.index + m[0].length;
    }
    out += esc(raw.slice(last));
    return out.replace(/\n/g,'<br>');
}
function onMsgLink(e,href){
    e.stopPropagation();
    try{
        const u=new URL(href, location.href);
        if(u.origin===location.origin && u.pathname===location.pathname){
            const q=u.searchParams, mid=q.get('m'), uid=q.get('user'), uname=q.get('u');
            if(mid||uid||uname){
                e.preventDefault();
                if(mid){ api('msg_locate&id='+encodeURIComponent(mid)).then(r=>{ if(r&&r.ok){ openChat(r.chat_id,r.type,r.peer_id,r.title,r.avatar||''); setTimeout(()=>scrollToMsg(+mid),700);} else toast('Сообщение недоступно'); }); }
                else if(uid){ openUserProfile(+uid); }
                else if(uname){ openByUsername(uname); }
                return false;
            }
        }
    }catch(_){}
    return true; // внешняя ссылка — откроется в браузере
}
async function openByUsername(un){
    un=(un||'').replace(/^@/,'');
    if(!un){ return; }
    const r=await api('uid_by_username&u='+encodeURIComponent(un));
    if(r&&r.id){ openUserProfile(r.id); }
    else { toast('Пользователь @'+un+' не найден'); }
}
// ===== Стикеры =====
let curPack=null;
function openStickers(){ if(!curChat){ toast('Откройте чат'); return; } document.getElementById('stickerSheet').style.display='block'; loadMyPacks(); }
function closeStickers(){ document.getElementById('stickerSheet').style.display='none'; }
async function loadMyPacks(){
    const body=document.getElementById('stickerBody');
    const r=await api('sticker_packs_my');
    const packs=(r&&r.packs)||[];
    if(!packs.length){ body.innerHTML='<div class="hint">У вас пока нет стикеров.<br><br>Нажмите ✎ чтобы <b>создать свой набор</b>, или + чтобы <b>добавить чужой по ссылке</b>.</div>'; return; }
    body.innerHTML=packs.map(p=>{
        const items=(p.stickers||[]).map(s=>{
            const el=(s.mtype==='video')?`<video src="${s.file}" muted loop playsinline onmouseenter="this.play()" style="width:100%;height:100%;object-fit:contain"></video>`:`<img src="${s.file}" loading="lazy" style="width:100%;height:100%;object-fit:contain">`;
            return `<div onclick="sendSticker(${s.id})" style="aspect-ratio:1;background:var(--panel);border-radius:12px;padding:6px;cursor:pointer;position:relative">${el}${p.owner?`<span onclick="event.stopPropagation();delSticker(${s.id})" style="position:absolute;top:-4px;right:-4px;width:20px;height:20px;background:#E5484D;color:#fff;border-radius:50%;font-size:13px;display:flex;align-items:center;justify-content:center">×</span>`:''}</div>`;
        }).join('');
        const addBtn=p.owner?`<div onclick="curPack=${p.id};document.getElementById('stickerFile').click()" style="aspect-ratio:1;background:var(--panel2);border-radius:12px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:var(--blue);font-size:30px">+</div>`:'';
        return `<div style="margin-bottom:16px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                <div style="font-weight:800;font-size:14px;flex:1">${esc(p.title)}</div>
                <button onclick="sharePack('${p.slug}')" style="background:none;border:none;color:var(--blue);font-size:12.5px;font-weight:700;cursor:pointer">Поделиться</button>
                ${!p.owner?`<button onclick="removePack(${p.id})" style="background:none;border:none;color:var(--sub);font-size:12.5px;font-weight:700;cursor:pointer">Убрать</button>`:''}
            </div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">${items}${addBtn}</div>
        </div>`;
    }).join('');
}
async function sendSticker(id){ if(!curChat)return; closeStickers(); await api('sticker_send','POST',{chat:curChat,sticker:id}); loadMsgs(true); playSnd('send'); }
async function delSticker(id){ if(!confirm('Удалить стикер?'))return; await api('sticker_del','POST',{id:id}); loadMyPacks(); }
async function createPackPrompt(){
    const title=prompt('Название набора стикеров:'); if(!title||!title.trim())return;
    const r=await api('sticker_pack_create','POST',{title:title.trim()});
    if(r&&r.ok){ curPack=r.id; toast('Набор создан! Теперь добавьте стикеры'); await loadMyPacks(); setTimeout(()=>document.getElementById('stickerFile').click(),300); }
    else toast((r&&r.error)||'Ошибка');
}
function uploadSticker(input){
    const f=input.files[0]; input.value=''; if(!f||!curPack)return;
    const fd=new FormData(); fd.append('pack',curPack); fd.append('file',f);
    toast('Загрузка стикера…');
    fetch('messenger.php?action=sticker_add',{method:'POST',body:fd}).then(x=>x.json()).then(r=>{
        if(r&&r.ok){ loadMyPacks(); } else toast((r&&r.error)||'Не удалось');
    }).catch(()=>toast('Ошибка загрузки'));
}
async function addPackPrompt(){
    const v=prompt('Ссылка или название набора (например payom или ссылка ?stickers=payom):'); if(!v)return;
    let slug=v.trim(); const m=slug.match(/stickers=([a-z0-9]+)/i); if(m)slug=m[1];
    const r=await api('sticker_pack_add','POST',{slug:slug});
    if(r&&r.ok){ toast('Набор добавлен'); loadMyPacks(); } else toast('Набор не найден');
}
async function removePack(id){ await api('sticker_pack_remove','POST',{pack:id}); loadMyPacks(); }
function sharePack(slug){ copyText(baseUrl()+'?stickers='+slug); toast('Ссылка на набор скопирована'); }
// ===== Просмотр набора по тапу на стикер =====
let pvPack=null;
async function openStickerPack(file){
    const r=await api('sticker_pack_by_file&file='+encodeURIComponent(file));
    if(!r||!r.pack){ toast('Набор не найден'); return; }
    pvPack=r.pack;
    document.getElementById('pvTitle').textContent=pvPack.title;
    document.getElementById('pvCount').textContent=(pvPack.stickers||[]).length+' стикеров';
    document.getElementById('pvBody').innerHTML='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">'+(pvPack.stickers||[]).map(s=>{
        const el=(s.mtype==='video')?`<video src="${s.file}" muted loop autoplay playsinline style="width:100%;height:100%;object-fit:contain"></video>`:`<img src="${s.file}" loading="lazy" style="width:100%;height:100%;object-fit:contain">`;
        const tap=curChat?`onclick="sendSticker(${s.id});closePackView()"`:'';
        return `<div ${tap} style="aspect-ratio:1;background:var(--panel);border-radius:12px;padding:6px;cursor:${curChat?'pointer':'default'}">${el}</div>`;
    }).join('')+'</div>';
    pvRenderBtn();
    document.getElementById('packView').style.display='block';
}
function pvRenderBtn(){
    const b=document.getElementById('pvBtn');
    if(pvPack.owner){ b.textContent='Это ваш набор'; b.style.background='var(--panel2)'; b.style.color='var(--sub)'; b.onclick=null; return; }
    b.onclick=pvToggle;
    if(pvPack.added){ b.textContent='Убрать набор'; b.style.background='var(--panel2)'; b.style.color='#E5484D'; }
    else { b.textContent='Добавить набор ('+((pvPack.stickers||[]).length)+')'; b.style.background='var(--blue)'; b.style.color='#fff'; }
}
async function pvToggle(){
    if(!pvPack||pvPack.owner)return;
    if(pvPack.added){ await api('sticker_pack_remove','POST',{pack:pvPack.id}); pvPack.added=false; toast('Набор убран'); }
    else { await api('sticker_pack_add','POST',{slug:pvPack.slug}); pvPack.added=true; toast('Набор добавлен'); }
    pvRenderBtn();
}
function closePackView(){ document.getElementById('packView').style.display='none'; pvPack=null; }
function relTime(ts){ if(!ts)return''; const s=Math.floor(Date.now()/1000)-ts; if(s<45)return'только что'; const m=Math.floor(s/60); if(m<60)return m+' мин'; const h=Math.floor(m/60); if(h<24)return h+' ч'; const dd=Math.floor(h/24); if(dd===1)return'вчера'; if(dd<7)return dd+' дн'; return new Date(ts*1000).toLocaleDateString('ru',{day:'2-digit',month:'2-digit',timeZone:'Asia/Almaty'}); }
function hhmm(ts){ if(!ts)return''; return new Date(ts*1000).toLocaleTimeString('ru',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Almaty'}); }
/* Единая обёртка над fetch для всех запросов к API.
   Здесь сосредоточена защита клиента: анти-кэш, обработка 429 и авто-пауза.
   ВАЖНО: при любой ошибке возвращаем объект (никогда не throw) — вызывающий
   код проверяет r.ok / нужные поля, поэтому ошибка просто «ничего не делает»
   и чат НЕ перерисовывается (это убирает мигание при сбоях сети). */
function api(a,m,b){
    // Если сервер недавно ответил 429 (перегрузка/спам) — держим паузу и
    // вообще не выходим в сеть, пока не истечёт «время остывания».
    if(window._apiCooldownUntil && Date.now() < window._apiCooldownUntil){
        return Promise.resolve({error:'cooldown'});
    }
    return fetch('messenger.php?action='+a,{
        method: m||'GET',
        cache: 'no-store',                                   // не берём ответ из кэша браузера
        headers: b?{'Content-Type':'application/json'}:{},
        body: b?JSON.stringify(b):undefined
    }).then(function(r){
        if(r.status === 429){
            // Сработала серверная защита от спама. Делаем автоматическую паузу
            // на время, указанное сервером (Retry-After), иначе — 3 секунды.
            var ra = parseInt(r.headers.get('Retry-After'), 10);
            var wait = (ra > 0 ? ra : 3) * 1000;
            window._apiCooldownUntil = Date.now() + wait;
            return {error:'rate_limited', retry_after: wait};
        }
        // Разбираем JSON аккуратно: если тело не JSON — не роняем поток.
        return r.json().catch(function(){ return {error:'bad_json'}; });
    }).catch(function(){ return {error:'network'}; });
}
function avaHtml(name,img,cls){ if(img)return `<div class="ava ${cls||''}"><img src="${img}"></div>`; return `<div class="ava ${cls||''}">${esc((name||'?').charAt(0).toUpperCase())}</div>`; }
function userSub(u){ return u.username ? '@'+esc(u.username)+(u.phone?' · '+esc(u.phone):'') : esc(u.phone||''); }

/* ---------- Список чатов ---------- */
async function loadChats(){
    // Анти-наложение: не запускаем параллельную загрузку списка чатов
    // (иначе список моргает при одновременных вызовах опроса и событий).
    if(window._chatsBusy){ window._chatsPending = true; return; }
    window._chatsBusy = true;
    try {
    /* при возврате в список показываем прошлый вариант мгновенно */
    try { const _b = document.getElementById('listArea');
          if (window._chatsHtml && _b && !_b.innerHTML.trim()) _b.innerHTML = window._chatsHtml; } catch(e){}
    const r = await api('chats');
    if(!r || !r.chats) return;
    if(document.getElementById('searchInput').value.trim().length >= 2) return; // идёт поиск
    const box = document.getElementById('listArea');
    if(!r.chats.length){ box.innerHTML='<div class="hint">Нет чатов.<br>Найдите человека по номеру телефона выше или создайте группу.</div>'; return; }
    // Сигнатура списка: если состав/счётчики не изменились — DOM не перерисовываем
    // (это убирает «мигание» списка чатов при периодическом опросе).
    const _sig = JSON.stringify(r.chats.map(c=>[c.id,c.ts,c.unread,c.last,c.last_me,c.muted]));
    if(_sig === box.dataset.sig) return;
    box.dataset.sig = _sig;
    box.innerHTML = r.chats.map(c=>{
        const last = c.last_me ? 'Вы: '+esc(c.last) : (c.type==='group' && c.last ? esc(c.last_sender)+': '+esc(c.last) : esc(c.last));
        const tt = esc(c.title).replace(/'/g,"\\'");
        return `<div class="row-wrap" data-cid="${c.id}">
            <div class="row-actions">
                <button class="ra ra-mute" onclick="event.stopPropagation();rowMute(${c.id},${c.muted?1:0})">${c.muted?SVG_BELL:SVG_BELLOFF}<span>${c.muted?'Звук':'Тихо'}</span></button>
                <button class="ra ra-del" onclick="event.stopPropagation();rowDelete(${c.id},'${tt}')">${SVG_TRASH}<span>Удалить</span></button>
            </div>
            <div class="row" onclick="rowTap(${c.id},'${c.type}',${c.peer_id},'${tt}','${c.avatar_img||''}')">
                ${avaHtml(c.title,c.avatar_img,c.type==='group'?'g':'')}
                <div class="row-main">
                    <div class="row-top"><div class="row-name">${esc(c.title)}${c.verified?VBADGE:''}${c.muted?' <span style=\"color:var(--sub)\">'+SVG_BELLOFF_SM+'</span>':''}</div><div class="row-time">${relTime(c.ts)}</div></div>
                    <div class="row-bot"><div class="row-last">${last||'Нет сообщений'}</div>${c.unread?`<div class="badge">${c.unread}</div>`:''}</div>
                </div>
            </div></div>`;
    }).join('');
    window._chatsHtml = box.innerHTML;   /* запомнили список */
    } finally {
        // снимаем флаг занятости и выполняем отложенный вызов, если он был
        window._chatsBusy = false;
        if(window._chatsPending){ window._chatsPending = false; loadChats(); }
    }
}

/* ---------- iOS-свайп строки чата ---------- */
const ROW_REVEAL=160; // ширина двух кнопок
let openRow=null;
function closeOpenRow(){ if(openRow){ const rw=openRow.querySelector('.row'); if(rw)rw.style.transform=''; openRow=null; } }
function rowTap(id,type,peer,title,avatar){ if(openRow){ closeOpenRow(); return; } openChat(id,type,peer,title,avatar); }
async function rowMute(id,muted){ closeOpenRow(); await api('mute_chat','POST',{chat:id,val:muted?0:1}); toast(muted?'Уведомления включены':'Уведомления отключены'); loadChats(); }
async function rowDelete(id,title){ closeOpenRow(); if(confirm('Удалить чат «'+(title||'')+'»?')){ await api('leave_chat','POST',{chat:id}); if(curChat===id)closeChat(); loadChats(); } }
(function(){
    const area=document.getElementById('listArea'); if(!area) return;
    let wrap=null, row=null, sx=0, sy=0, dx=0, base=0, active=false, decided=false, horiz=false;
    area.addEventListener('touchstart',e=>{
        const w=e.target.closest('.row-wrap'); 
        if(openRow && openRow!==w){ closeOpenRow(); }
        if(!w){ wrap=null; active=false; return; }
        wrap=w; row=w.querySelector('.row'); sx=e.touches[0].clientX; sy=e.touches[0].clientY; dx=0;
        base = (openRow===w)? -ROW_REVEAL : 0;
        active=true; decided=false; horiz=false;
    },{passive:true});
    area.addEventListener('touchmove',e=>{
        if(!active||!row) return;
        const cx=e.touches[0].clientX, cy=e.touches[0].clientY, ddx=cx-sx, ddy=cy-sy;
        if(!decided){ if(Math.abs(ddx)>8||Math.abs(ddy)>8){ decided=true; horiz=Math.abs(ddx)>Math.abs(ddy)*1.3; } else return; }
        if(!horiz) return;
        e.preventDefault();
        let x=base+ddx; if(x>0)x=0; if(x<-ROW_REVEAL-30)x=-ROW_REVEAL-30;
        row.style.transition='none'; row.style.transform='translateX('+x+'px)';
    },{passive:false});
    function end(){
        if(!active||!row){ active=false; return; }
        active=false;
        const cur=dxFromTransform(row);
        row.style.transition='transform .22s cubic-bezier(.3,1.1,.5,1)';
        if(cur < -ROW_REVEAL/2){ row.style.transform='translateX(-'+ROW_REVEAL+'px)'; openRow=wrap; }
        else { row.style.transform=''; if(openRow===wrap)openRow=null; }
        row=null; wrap=null;
    }
    function dxFromTransform(el){ const m=(el.style.transform||'').match(/-?\d+\.?\d*/); return m?parseFloat(m[0]):0; }
    area.addEventListener('touchend',end);
    area.addEventListener('touchcancel',end);
})();

/* ---------- Поиск людей ---------- */
let searchTimer=null;
function onSearch(q){
    clearTimeout(searchTimer);
    if(q.trim().length<1){ loadChats(); return; }
    searchTimer=setTimeout(async()=>{
        const r=await api('search&q='+encodeURIComponent(q.trim()));
        const box=document.getElementById('listArea');
        if(!r.users || !r.users.length){ box.innerHTML='<div class="hint">Никого не найдено по «'+esc(q)+'»</div>'; return; }
        box.innerHTML=r.users.map(u=>`<div class="row" onclick="startChat(${u.id},'${esc(u.name).replace(/'/g,"\\'")}','${u.avatar||''}')">
            ${avaHtml(u.name,u.avatar,'')}
            <div class="row-main"><div class="row-name">${esc(u.name)}</div><div class="row-last">${userSub(u)}</div></div></div>`).join('');
    },300);
}
async function startChat(uid,name,avatar){
    const r=await api('open&user='+uid);
    if(r.chat_id){ document.getElementById('searchInput').value=''; openChat(r.chat_id,'private',uid,name,avatar||''); }
}

/* ---------- Чат ---------- */
function openChat(id,type,peer,title,avatar){
    curChat=id; curType=type; curPeer=peer; curTitle=title; curAvatar=avatar||''; replyTo=null; lastMsgId=0; seenMaxId=0;
    document.getElementById('chatTitle').textContent=title;
    document.getElementById('chatSub').textContent = type==='group'?'группа':'…';
    document.getElementById('chatAva').innerHTML = avatar ? `<img src="${avatar}">` : esc((title||'?').charAt(0).toUpperCase());
    document.getElementById('chatAva').className = 'ava'+(type==='group'?' g':'');
    const showCall = (type==='private' && peer);
    document.getElementById('callBtn').style.display = showCall?'flex':'none';
    document.getElementById('videoBtn').style.display = showCall?'flex':'none';
    /* Кэш: если чат уже открывали — показываем сразу, без ожидания.
       Свежие сообщения подтянутся фоном и заменят содержимое. */
    const _cache = window._msgCache && window._msgCache[id];
    const _area = document.getElementById('msgsArea');
    if (_cache) { _area.innerHTML = _cache.html; _area.dataset.sig = _cache.sig || ''; _area.scrollTop = _area.scrollHeight; }
    else { _area.innerHTML = ''; _area.dataset.sig = ''; }
    document.getElementById('chatSearchBar').style.display='none';
    document.getElementById('pinBar').style.display='none';
    clearReply();
    hideMentions(); window._grpMembers=[];
    if(type==='group'){ api('mention_members&chat='+id).then(r=>{ window._grpMembers=(r&&r.members)||[]; }); }
    document.getElementById('scChat').classList.add('show');
    loadMsgs(true);
    if(msgPoll) clearInterval(msgPoll);
    msgPoll=setInterval(()=>loadMsgs(false),2500);
}
function closeChat(){
    document.getElementById('scChat').classList.remove('show');
    if(msgPoll){clearInterval(msgPoll);msgPoll=null;}
    curChat=null; loadChats();
}
async function loadMsgs(scroll){
    if(!curChat) return;
    // --- Защита от наложения запросов (флаг isFetching) ---------------
    // Пока не завершилась предыдущая загрузка сообщений — новую НЕ запускаем.
    // Раньше несколько источников (опрос, WebSocket, «печатает…», возврат во
    // вкладку) могли одновременно дёргать loadMsgs → двойная перерисовка DOM
    // и «мигание» чата. Теперь параллельные вызовы схлопываются: если во время
    // загрузки пришёл ещё запрос — он выполнится РОВНО один раз после текущего.
    if(window._msgsBusy){
        window._msgsPending = true;
        if(scroll) window._msgsPendingScroll = true;
        return;
    }
    window._msgsBusy = true;
    const _chatAtStart = curChat;   // запомним чат: вдруг пользователь переключится во время запроса
    try{
    const r=await api('messages&chat='+curChat);
    if(!r || !r.ok) return;
    if(curChat !== _chatAtStart) return;   // чат сменился, пока шёл запрос — не рисуем чужие сообщения
    document.getElementById('chatSub').textContent = r.status || '';
    window._autoDel = +r.auto_delete||0;
    // синяя галочка в шапке
    document.getElementById('chatTitle').innerHTML = esc(curTitle||'') + (curType==='private' && +r.peer_verified===1 ? VBADGE : '');
    // печатает…
    if(r.typing && r.typing.length){ document.getElementById('chatSub').innerHTML='<span class="typing">'+esc(r.typing.join(', '))+' печатает…</span>'; }
    else document.getElementById('chatSub').textContent = r.status || '';
    // звонок только если разрешено
    if(curType==='private'){ const sc=(curPeer && r.peer_can_call!==false); document.getElementById('callBtn').style.display = sc?'flex':'none'; document.getElementById('videoBtn').style.display = sc?'flex':'none'; }
    // закреплённое
    const pb=document.getElementById('pinBar');
    if(r.pinned){ pb.style.display='flex'; document.getElementById('pinText').textContent = r.pinned.text || (r.pinned.type==='image'?'Фото':r.pinned.type==='video'?'Видео':r.pinned.type==='circle'?'Кружок':r.pinned.type==='audio'?'Голосовое':'Файл'); pb.dataset.mid=r.pinned.id; }
    else pb.style.display='none';
    const box=document.getElementById('msgsArea');
    const lastId=r.messages.length?r.messages[r.messages.length-1].id:0;
    const sig=lastId+'_'+JSON.stringify(r.messages.map(m=>[m.id,m.edited,m.deleted,(m.reactions||[]).length]))+'_'+r.peer_read;
    if(sig===box.dataset.sig && !scroll) return;
    box.dataset.sig=sig; lastMsgId=lastId;
    // расшифровка E2E (личные чаты)
    if(curType==='private'){
        window._lastPeerPubkey = r.peer_pubkey || null;
        await ensurePeerKey(r.peer_pubkey);
        for(const m of r.messages){
            if(+m.enc===1 && m.text){ m.text=await e2eDecrypt(m.text); }
            if(+m.enc===1 && m.file){ const b=await e2eFetchBlob(m.file); if(b){ m.file=b; } else { m._enclock=1; m.file=''; } }
        }
    } else { window._lastPeerPubkey=null; }
    const firstLoad = (seenMaxId===0);
    let gotIncoming=false;
    box.innerHTML=r.messages.map(m=>{
        if(m.type==='system'){ return `<div style="text-align:center;margin:7px 0"><span style="background:var(--panel2);color:var(--sub);font-size:12px;font-weight:700;padding:4px 12px;border-radius:12px">${esc(m.text||'')}</span></div>`; }
        const out = (+m.sender_id===ME);
        const isNew = !firstLoad && (+m.id > seenMaxId);
        if(isNew && !out) gotIncoming=true;
        const anim = isNew ? (out?' msg-in-r':' msg-in-l') : '';
        if(+m.deleted===1){ return `<div class="m ${out?'out':'in'}${anim}" style="opacity:.6"><i style="font-weight:600">Сообщение удалено</i><div class="meta">${hhmm(m.ts)}</div></div>`; }
        let reply='';
        if(m.reply_to && (m.r_text!==null&&m.r_text!==undefined || m.r_type)){
            let rp = m.r_text || (m.r_type==='image'?'Фото':(m.r_type==='video'?'Видео':(m.r_type==='circle'?'Видео-кружок':(m.r_type==='audio'?'Голосовое':(m.r_type==='file'?'Файл':'')))));
            reply=`<div class="reply" onclick="event.stopPropagation();scrollToMsg(${m.reply_to})"><b>${esc(m.r_name||'')}</b><span>${esc(rp)}</span></div>`;
        }
        const grp = (curType==='group' && !out);
        const sname = grp?`<div class="sname" style="color:${userColor(m.sender_id)}" onclick="event.stopPropagation();openUserProfile(${m.sender_id})">${esc(m.sname||'')}</div>`:'';
        let body='';
        if(+m.fwd_from>0){ body+=`<div class="fwd-lbl">Переслано от ${esc(m.fwd_name||'')}</div>`; }
        if(+m.story_ref>0){
            const alive = +m.story_alive===1 && m.story_file;
            const storyOwner = out ? curPeer : ME;
            const thumb = alive
                ? `<img src="${m.story_file}" style="width:34px;height:48px;object-fit:cover;border-radius:6px;flex-shrink:0">`
                : `<div style="width:34px;height:48px;border-radius:6px;background:var(--panel2);display:flex;align-items:center;justify-content:center;flex-shrink:0"><svg viewBox="0 0 24 24" fill="none" stroke="var(--sub)" stroke-width="2" width="16" height="16"><circle cx="12" cy="12" r="9"/></svg></div>`;
            body+=`<div ${alive?`onclick="event.stopPropagation();openStoryUser(${storyOwner})"`:''} style="display:flex;align-items:center;gap:8px;background:rgba(124,92,255,.14);border-left:3px solid var(--accent);border-radius:8px;padding:6px 8px;margin-bottom:5px;cursor:${alive?'pointer':'default'}">
                ${thumb}
                <div style="font-size:12.5px;font-weight:700;color:var(--accent)">Ответ на историю${alive?'':' · истекла'}</div>
            </div>`;
        }
        if(m._enclock){ body+='<div style="color:var(--sub);font-weight:600;padding:4px 0">🔒 Зашифрованное медиа</div>'; }
        const isOnce = (+m.once===1 && m.type!=='text' && m.type!=='file');
        if(isOnce){
            const viewed = (+m.viewed===1) || !m.file;
            const lbl = (m.type==='video'||m.type==='circle')?'видео':'фото';
            const eye='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18" style="vertical-align:-4px;margin-right:6px"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/></svg>';
            if(viewed) body=`<div class="once-ph viewed">${eye}Просмотрено</div>`;
            else if(out) body=`<div class="once-ph">${eye}Одноразовое ${lbl} · отправлено</div>`;
            else body=`<div class="once-ph tap" onclick="event.stopPropagation();openOnce(${m.id},'${m.type}')">${eye}Посмотреть ${lbl} (1 раз)</div>`;
        }
        else if(m.type==='image'&&m.file) body+=`<div class="media-wrap" onclick="event.stopPropagation();openImg('${m.file}')"><div class="media-spin"></div><img src="${m.file}" loading="lazy" onload="this.classList.add('loaded');const s=this.parentElement.querySelector('.media-spin');if(s)s.remove()" onerror="const s=this.parentElement.querySelector('.media-spin');if(s)s.innerHTML=''"></div>`;
        else if(m.type==='video'&&m.file) body+=`<div class="media-wrap" onclick="event.stopPropagation();playVid(this,'${m.file}')"><div class="vid-play"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></div><span class="vid-badge">Видео</span></div>`;
        else if(m.type==='circle'&&m.file) body+=`<div class="circle-msg" onclick="event.stopPropagation();toggleCircle(this)"><video src="${m.file}" playsinline loop muted autoplay preload="metadata"></video><span class="circle-dur">${fmtV(+m.dur||0)}</span><span class="circle-mute"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M22 9l-6 6M16 9l6 6"/></svg></span></div>`;
        else if(m.type==='audio'&&m.file) body+=voiceHtml(m);
        else if(m.type==='sticker'&&m.file){ body+=(m.filename==='video')?`<video class="sticker" src="${m.file}" playsinline autoplay loop muted preload="metadata" onclick="event.stopPropagation();openStickerPack('${m.file}')"></video>`:`<img class="sticker" src="${m.file}" loading="lazy" onclick="event.stopPropagation();openStickerPack('${m.file}')">`; }
        else if(m.type==='file'&&m.file) body+=`<a href="${m.file}" download target="_blank" onclick="event.stopPropagation()" style="color:inherit;text-decoration:none;display:flex;align-items:center;gap:7px;font-weight:700"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" style="vertical-align:-3px;margin-right:5px"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/></svg>${esc(m.filename||'Файл')}</a>`;
        let emo=0;
        if(m.text){ emo=(m.type==='text')?emojiOnly(m.text):0; if(emo){ body+=(body?'<div style="margin-top:4px"></div>':'')+`<div class="emoji-big e${Math.min(emo,3)}">${esc(m.text.trim())}</div>`; } else body+=(body?'<div style="margin-top:4px"></div>':'')+linkify(m.text); }
        let reacts='';
        if(m.reactions && m.reactions.length){ reacts='<div class="reactions">'+m.reactions.map(x=>`<span class="reaction ${x.mine?'mine':''}" onclick="event.stopPropagation();quickReact(${m.id},'${x.emoji}')">${x.emoji} ${x.cnt}</span>`).join('')+'</div>'; }
        let tick='';
        if(out && curType==='private'){ tick = (r.peer_read>=+m.id)?'✓✓':'✓'; }
        const edited = (+m.edited===1)?'<span style="opacity:.6">изм. </span>':'';
        const dtxt = esc(m.text||(m.type==='image'?'Фото':m.type==='video'?'Видео':m.type==='circle'?'Видео-кружок':m.type==='audio'?'Голосовое':m.type==='sticker'?'Стикер':m.type==='file'?'Файл':''));
        const bare = (m.type==='circle' && !isOnce);
        const isSticker = (m.type==='sticker');
        const hasMedia = !['text','system'].includes(m.type);
        const bubble=`<div class="m ${out?'out':'in'}${bare?' bare':''}${hasMedia?' media':''}${emo?' emojimsg':''}${isSticker?' stickermsg':''}${anim}" id="m${m.id}" onclick="openMsgMenu(${m.id},${out?1:0})" data-id="${m.id}" data-name="${esc(out?'Вы':(m.sname||''))}" data-text="${dtxt}">
            ${sname}${reply}${body}<span class="meta">${edited}${hhmm(m.ts)}${tick?'<span style="color:#fff">'+tick+'</span>':''}</span>${reacts}
        </div>`;
        if(grp){ const hasImg=!!m.savatar; const av=hasImg?`<img src="${m.savatar}">`:esc((m.sname||'?').charAt(0).toUpperCase()); const avBg=hasImg?'':`background:${userColor(m.sender_id)};`; return `<div class="grp-row"><div class="ava" style="width:30px;height:30px;font-size:12px;flex-shrink:0;${avBg}" onclick="event.stopPropagation();openUserProfile(${m.sender_id})">${av}</div>${bubble}</div>`; }
        return bubble;
    }).join('');
    r.messages.forEach(mm=>{ if(+mm.id>seenMaxId) seenMaxId=+mm.id; });
    /* запоминаем чат — при следующем открытии покажется мгновенно */
    window._msgCache = window._msgCache || {};
    window._msgCache[curChat] = { html: box.innerHTML, sig: box.dataset.sig || '' };
    const _ks = Object.keys(window._msgCache);
    if (_ks.length > 12) delete window._msgCache[_ks[0]];   // держим последние 12 чатов
    if(gotIncoming) playSnd('recv');
    if(scroll || box.scrollHeight-box.scrollTop-box.clientHeight<250) box.scrollTop=box.scrollHeight;
    } finally {
        // Снимаем флаг занятости и, если за это время был отложенный запрос,
        // выполняем его один раз (актуально, например, после WebSocket-события).
        window._msgsBusy = false;
        if(window._msgsPending){
            window._msgsPending = false;
            var _s = window._msgsPendingScroll; window._msgsPendingScroll = false;
            loadMsgs(_s);
        }
    }
}
function scrollToMsg(id){ const el=document.getElementById('m'+id); if(el){ el.scrollIntoView({behavior:'smooth',block:'center'}); const o=el.style.background; el.style.transition='background .5s'; el.style.background='rgba(51,144,236,.3)'; setTimeout(()=>el.style.background=o,900);} }

/* ---------- Меню сообщения ---------- */
let menuMsg=null;
function openMsgMenu(id,own){
    if(window._swiped){ return; } // был свайп — не открываем меню
    const el=document.getElementById('m'+id); if(!el) return;
    menuMsg={id:id, own:!!own, text:el.dataset.text, name:el.dataset.name};
    document.getElementById('mmiEdit').style.display = own?'flex':'none';
    document.getElementById('mmiDel').style.display = own?'flex':'none';
    document.getElementById('msgMenuOv').style.display='block';
}
function closeMsgMenu(){ document.getElementById('msgMenuOv').style.display='none'; menuMsg=null; }
async function doReact(emoji){ if(!menuMsg)return; await api('react','POST',{id:menuMsg.id,emoji:emoji}); closeMsgMenu(); document.getElementById('msgsArea').dataset.sig=''; loadMsgs(false); }
let _rxBusy={};
async function quickReact(id,emoji){
    if(_rxBusy[id]) return;                 // запрос уже летит — второй не шлём
    _rxBusy[id]=1;
    try{
        await api('react','POST',{id:id,emoji:emoji});
        const box=document.getElementById('msgsArea'); if(box) box.dataset.sig='';
        await loadMsgs(false);
    }catch(e){}
    finally{ setTimeout(()=>{ delete _rxBusy[id]; }, 400); }
}
function menuReply(){ if(!menuMsg)return; setReply(menuMsg.id); closeMsgMenu(); }
function menuCopy(){ if(!menuMsg)return; navigator.clipboard&&navigator.clipboard.writeText(menuMsg.text||''); closeMsgMenu(); }
function copyText(t){ try{ navigator.clipboard.writeText(t); }catch(e){ const ta=document.createElement('textarea'); ta.value=t; ta.style.position='fixed'; ta.style.opacity='0'; document.body.appendChild(ta); ta.select(); try{document.execCommand('copy');}catch(_){} ta.remove(); } }
function toast(msg){ let t=document.getElementById('_toast'); if(!t){ t=document.createElement('div'); t.id='_toast'; t.style.cssText='position:fixed;left:50%;bottom:100px;transform:translateX(-50%);background:rgba(0,0,0,.86);color:#fff;padding:11px 20px;border-radius:22px;font-size:14px;font-weight:700;z-index:500;transition:opacity .3s;max-width:82%;text-align:center'; document.body.appendChild(t); } t.textContent=msg; t.style.opacity='1'; clearTimeout(window._tt); window._tt=setTimeout(()=>{t.style.opacity='0';},1900); }
function baseUrl(){ return location.origin+location.pathname; }
function shareMyProfile(){ const un=(myProfile&&myProfile.username)?('?u='+encodeURIComponent(myProfile.username)):('?user='+ME); const link=baseUrl()+un; copyText(link); toast('Ваша ссылка скопирована: '+link); }function menuLink(){ if(!menuMsg)return; copyText(baseUrl()+'?m='+menuMsg.id); closeMsgMenu(); toast('Ссылка на сообщение скопирована'); }
async function menuPin(){ if(!menuMsg)return; await api('pin_msg','POST',{chat:curChat,id:menuMsg.id}); closeMsgMenu(); document.getElementById('msgsArea').dataset.sig=''; loadMsgs(false); }
async function menuEdit(){ if(!menuMsg)return; const t=prompt('Редактировать сообщение:',menuMsg.text||''); if(t!==null&&t.trim()!==''){ await api('edit','POST',{id:menuMsg.id,text:t.trim()}); document.getElementById('msgsArea').dataset.sig=''; loadMsgs(false); } closeMsgMenu(); }
async function menuDelete(){ if(!menuMsg)return; if(confirm('Удалить сообщение?')){ await api('delete','POST',{id:menuMsg.id}); document.getElementById('msgsArea').dataset.sig=''; loadMsgs(false); } closeMsgMenu(); }

/* ---------- Закреплённое ---------- */
function jumpPinned(){ const mid=document.getElementById('pinBar').dataset.mid; if(mid)scrollToMsg(mid); }
async function unpin(){ await api('pin_msg','POST',{chat:curChat,id:0}); document.getElementById('msgsArea').dataset.sig=''; loadMsgs(false); }

/* ---------- Поиск в чате ---------- */
function toggleChatSearch(){ const b=document.getElementById('chatSearchBar'); const show=b.style.display==='none'; b.style.display=show?'block':'none'; if(show){document.getElementById('chatSearchInput').focus();}else{document.getElementById('chatSearchInput').value='';document.getElementById('chatSearchResults').innerHTML='';} }
let csTimer=null;
function searchInChat(q){
    clearTimeout(csTimer);
    if(q.trim().length<1){ document.getElementById('chatSearchResults').innerHTML=''; return; }
    csTimer=setTimeout(async()=>{
        const r=await api('search_msg&chat='+curChat+'&q='+encodeURIComponent(q.trim()));
        const box=document.getElementById('chatSearchResults');
        box.innerHTML=(r.results||[]).length?r.results.map(m=>`<div class="sr-item" onclick="toggleChatSearch();scrollToMsg(${m.id})">${esc((m.text||'').substring(0,80))}<div class="t">${hhmm(m.ts)}</div></div>`).join(''):'<div class="sr-item" style="color:var(--sub)">Ничего не найдено</div>';
    },300);
}

/* ---------- Мой аватар ---------- */
/* ---------- Настройки / профиль ---------- */
let myProfile=null;
async function openSettings(){
    document.getElementById('scSettings').classList.add('show');
    refreshFaceStatus(); maybeShowInstall(); updSndState(); updE2EState();
    const r=await api('profile_get'); const p=r.profile||{}; myProfile=p;
    document.getElementById('setName').value=p.name||'';
    document.getElementById('setUsername').value=p.username||'';
    document.getElementById('unameStatus').textContent=''; unameFree=true;
    document.getElementById('setBio').value=p.bio||'';
    document.getElementById('setPhone').textContent=p.phone||'';
    document.getElementById('setBday').value=p.birthday||'';
    document.getElementById('setPls').value=p.priv_lastseen||'all';
    document.getElementById('setPc').value=p.priv_calls||'all';
    document.getElementById('setPp').value=p.priv_phone||'all';
    document.getElementById('setAva').innerHTML = p.avatar?`<img src="${p.avatar}">`:esc((p.name||'?').charAt(0).toUpperCase());
    // тема/шрифт/уведомления из памяти
    document.getElementById('swTheme').classList.toggle('on', localStorage.getItem('theme')==='light');
    document.getElementById('setFont').value = localStorage.getItem('font')||'normal';
    document.getElementById('swNotif').classList.toggle('on', localStorage.getItem('mute')!=='1');
}
function closeSettings(){ document.getElementById('scSettings').classList.remove('show'); loadChats(); }
let unameFree=true, unameTimer=null;
function checkUsername(){
    const inp=document.getElementById('setUsername');
    inp.value=inp.value.replace(/[^A-Za-z0-9_]/g,''); // только буквы/цифры/_
    const st=document.getElementById('unameStatus');
    const u=inp.value.trim();
    clearTimeout(unameTimer);
    if(u===''){ st.textContent=''; unameFree=true; return; }
    if(u.length<3){ st.textContent='Минимум 3 символа'; st.style.color='#E8A03D'; unameFree=false; return; }
    st.textContent='Проверяю…'; st.style.color='var(--sub)'; unameFree=false;
    unameTimer=setTimeout(async()=>{
        const r=await api('username_check&u='+encodeURIComponent(u));
        if(r.state==='free'){ st.textContent='✓ @'+u+' — свободно'; st.style.color='#4CD964'; unameFree=true; }
        else if(r.state==='taken'){ st.textContent='✕ @'+u+' — уже занято'; st.style.color='#FF6B6B'; unameFree=false; }
        else if(r.state==='short'){ st.textContent='Минимум 3 символа'; st.style.color='#E8A03D'; unameFree=false; }
        else { st.textContent=''; unameFree=true; }
    },350);
}
async function saveProfile(){
    const name=document.getElementById('setName').value.trim();
    const username=document.getElementById('setUsername').value.trim();
    const bio=document.getElementById('setBio').value.trim();
    if(name.length<1){ alert('Введите имя'); return; }
    if(username!=='' && !unameFree){ alert('Этот username занят или некорректен — выберите другой'); return; }
    const r=await api('profile_save','POST',{name:name,username:username,bio:bio,
        birthday:document.getElementById('setBday').value,
        priv_lastseen:document.getElementById('setPls').value,
        priv_calls:document.getElementById('setPc').value,
        priv_phone:document.getElementById('setPp').value});
    if(r.error){ alert(r.error); return; }
    document.getElementById('myAva').innerHTML = myProfile&&myProfile.avatar?`<img src="${myProfile.avatar}">`:esc(name.charAt(0).toUpperCase());
    closeSettings();
}
/* тема / шрифт / уведомления */
function applyPrefs(){
    document.body.classList.toggle('light', localStorage.getItem('theme')==='light');
    document.body.classList.remove('fs-small','fs-large');
    const f=localStorage.getItem('font'); if(f==='small')document.body.classList.add('fs-small'); if(f==='large')document.body.classList.add('fs-large');
    const tm=document.querySelector('meta[name=theme-color]'); if(tm)tm.content = localStorage.getItem('theme')==='light'?'#FFFFFF':'#1E1E2C';
}
function toggleTheme(){ const on=localStorage.getItem('theme')==='light'; localStorage.setItem('theme',on?'dark':'light'); document.getElementById('swTheme').classList.toggle('on',!on); applyPrefs(); }
function setFont(v){ localStorage.setItem('font',v); applyPrefs(); }
function toggleNotif(){ const muted=localStorage.getItem('mute')==='1'; localStorage.setItem('mute',muted?'0':'1'); document.getElementById('swNotif').classList.toggle('on',muted); }
/* заблокированные */
async function openBlocked(){ document.getElementById('blockedOv').style.display='block'; renderBlocked(); }
async function renderBlocked(){
    const r=await api('blocked_list'); const box=document.getElementById('blockedList');
    box.innerHTML=(r.users||[]).length?r.users.map(u=>`<div class="row">${avaHtml(u.name,u.avatar,'')}
        <div class="row-main"><div class="row-name">${esc(u.name)}</div><div class="row-last">${userSub(u)}</div></div>
        <button class="st-btn" style="width:auto;padding:8px 14px;margin:0;background:var(--panel2);color:var(--txt)" onclick="unblockUser(${u.id})">Разблокировать</button></div>`).join(''):'<div class="hint">Список пуст</div>';
    document.getElementById('blockedCount').textContent = (r.users&&r.users.length)?r.users.length:'›';
}
async function unblockUser(id){ await api('unblock','POST',{user:id}); renderBlocked(); }
/* безопасность / аккаунт */
async function logoutAll(){ if(confirm('Выйти на всех устройствах? Нужно будет войти заново.')){ await api('logout_all','POST',{}); location.href='messenger.php'; } }
let faceEnabled=false;
async function refreshFaceStatus(){ const r=await api('face_has'); faceEnabled=!!(r&&r.has); const t=document.getElementById('faceBtnTxt'); if(t)t.textContent=faceEnabled?('Вход по лицу: включён ('+r.samples+') — настроить'):'Настроить вход по лицу'; }
window.afterFaceEnroll=function(){ refreshFaceStatus(); };
function faceSetting(){
    if(faceEnabled){
        if(confirm('Добавить ещё один образец лица? (точнее распознавание)\n\nОК — добавить · Отмена — меню')){ openFace('enroll'); }
        else if(confirm('Отключить вход по лицу и удалить сохранённые данные лица?')){ api('face_disable','POST',{}).then(()=>refreshFaceStatus()); }
    } else {
        if(confirm('Включить быстрый вход по лицу?\n\nПройдите проверку: улыбка, моргание, поворот головы (защита от входа по фото).\n\nБезопасность: сохраняется не фото, а зашифрованный код (AES-256), по нему нельзя восстановить лицо. Только для вашего личного входа — ни владелец, ни разработчик не могут его посмотреть или где-либо использовать.')){ openFace('enroll'); }
    }
}
async function clearCacheAll(){ try{ if('serviceWorker'in navigator){const rs=await navigator.serviceWorker.getRegistrations(); for(const r of rs)await r.unregister();} if(window.caches){const ks=await caches.keys(); for(const k of ks)await caches.delete(k);} }catch(e){} alert('Кэш очищен'); location.reload(true); }
async function deleteAccount(){ if(!confirm('Удалить аккаунт? Вы выйдете, а для других вы станете «Пользователь Payom». Войти снова по этому лицу/номеру будет нельзя.'))return; if(!confirm('Точно удалить аккаунт?'))return; await api('delete_account','POST',{}); alert('Аккаунт удалён'); location.href='messenger.php'; }
async function uploadAva(inp){
    const f=inp.files[0]; if(!f)return; if(f.size>20*1024*1024){alert('Файл большой');return;}
    document.getElementById('setAva').innerHTML='<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center">⏳</div>';
    const fd=new FormData(); fd.append('file',f);
    const r=await fetch('messenger.php?action=avatar',{method:'POST',body:fd}).then(x=>x.json()).catch(()=>({}));
    if(r&&r.avatar){ if(myProfile)myProfile.avatar=r.avatar; document.getElementById('setAva').innerHTML=`<img src="${r.avatar}">`; document.getElementById('myAva').innerHTML=`<img src="${r.avatar}">`; }
    else { alert('Не удалось загрузить фото. Попробуйте другое фото (JPEG/PNG).'); openSettings(); }
    inp.value='';
}

function setReply(id){
    const el=document.getElementById('m'+id); if(!el) return;
    replyTo=id;
    document.getElementById('rbName').textContent='Ответ '+el.dataset.name;
    document.getElementById('rbText').textContent=el.dataset.text;
    document.getElementById('replyBar').classList.add('show');
    document.getElementById('msgInput').focus();
}
function clearReply(){ replyTo=null; document.getElementById('replyBar').classList.remove('show'); }
/* ===== Свайп сообщения влево/вправо → ответить (как Telegram) ===== */
(function(){
    const area=document.getElementById('msgsArea'); if(!area) return;
    let el=null, sx=0, sy=0, dx=0, active=false, decided=false, horiz=false, mid=0;
    function hint(){ let h=document.getElementById('swHint'); if(!h){ h=document.createElement('div'); h.id='swHint'; h.style.cssText='position:fixed;z-index:60;width:34px;height:34px;border-radius:50%;background:var(--panel2);display:flex;align-items:center;justify-content:center;opacity:0;transition:opacity .12s;pointer-events:none'; h.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="#A99BFF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><path d="M9 17l-5-5 5-5"/><path d="M4 12h11a4 4 0 014 4v2"/></svg>'; document.body.appendChild(h); } return h; }
    area.addEventListener('touchstart',e=>{
        const t=e.target.closest('.m'); if(!t||!t.dataset.id){ el=null; active=false; return; }
        el=t; mid=+t.dataset.id; sx=e.touches[0].clientX; sy=e.touches[0].clientY; dx=0; active=true; decided=false; horiz=false;
    },{passive:true});
    area.addEventListener('touchmove',e=>{
        if(!active||!el) return;
        const cx=e.touches[0].clientX, cy=e.touches[0].clientY, ddx=cx-sx, ddy=cy-sy;
        if(!decided){ if(Math.abs(ddx)>8||Math.abs(ddy)>8){ decided=true; horiz=Math.abs(ddx)>Math.abs(ddy)*1.3; } else return; }
        if(!horiz){ return; } // вертикаль — обычный скролл
        e.preventDefault();
        dx=Math.max(-96,Math.min(96,ddx));
        el.style.transition='none'; el.style.transform='translateX('+(dx*0.7)+'px)';
        const h=hint(); const r=el.getBoundingClientRect();
        h.style.top=(r.top+r.height/2-17)+'px';
        h.style.left=(dx>0? (r.left-44) : (r.right+10))+'px';
        h.style.opacity=Math.min(1,Math.abs(dx)/58);
    },{passive:false});
    function end(){
        if(!active||!el){ active=false; return; }
        active=false;
        const trig=Math.abs(dx)>=54;
        el.style.transition='transform .2s cubic-bezier(.3,1.2,.5,1)'; el.style.transform='';
        const h=document.getElementById('swHint'); if(h)h.style.opacity='0';
        if(trig){ window._swiped=true; if(navigator.vibrate)try{navigator.vibrate(15);}catch(e){} setReply(mid); setTimeout(()=>{window._swiped=false;},450); }
        el=null; dx=0;
    }
    area.addEventListener('touchend',end);
    area.addEventListener('touchcancel',end);
})();

let pendingFile=null, pendingOnce=false, mrec=null, rchunks=[], recording=false, rcancel=false, recStream=null;
function pickFile(inp){ const f=inp.files[0]; if(!f)return; if(f.size>20*1024*1024){alert('Файл больше 20 МБ');inp.value='';return;} pendingFile=f; pendingOnce=false; const kind=f.type.startsWith('image')?'Фото: ':(f.type.startsWith('video')?'Видео: ':'Файл: '); showPrev(kind+f.name); updSendBtn(); }
function showPrev(t){ const p=document.getElementById('attachPrev'); p.style.display='flex'; p.style.justifyContent='space-between'; p.style.alignItems='center';
    const canOnce = pendingFile && (pendingFile.type.startsWith('image')||pendingFile.type.startsWith('video'));
    const onceBtn = canOnce ? `<button id="onceTgl" onclick="toggleOnce()" style="border:none;background:${pendingOnce?'var(--blue)':'var(--panel2)'};color:${pendingOnce?'#fff':'var(--sub)'};font-weight:700;font-size:12px;padding:5px 10px;border-radius:12px;cursor:pointer">1 раз</button>` : '';
    p.innerHTML=`<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(t)}</span><span style="display:flex;gap:10px;align-items:center;flex-shrink:0">${onceBtn}<button onclick="clrFile()" style="border:none;background:none;color:#FF6B6B;font-weight:800;cursor:pointer;font-size:16px">✕</button></span>`;
}
function toggleOnce(){ pendingOnce=!pendingOnce; const b=document.getElementById('onceTgl'); if(b){ b.style.background=pendingOnce?'var(--blue)':'var(--panel2)'; b.style.color=pendingOnce?'#fff':'var(--sub)'; } }
function clrFile(){ pendingFile=null; pendingOnce=false; document.getElementById('fileImg').value=''; document.getElementById('fileDoc').value=''; document.getElementById('attachPrev').style.display='none'; updSendBtn(); }
function toggleAttachMenu(){ const m=document.getElementById('attachMenu'); m.style.display = m.style.display==='block'?'none':'block'; }
document.addEventListener('click',e=>{ const m=document.getElementById('attachMenu'); if(m&&m.style.display==='block'&&!e.target.closest('#attachMenu')&&!e.target.closest('#attachBtn'))m.style.display='none'; });

/* показывать отправку когда есть текст/файл, иначе микрофон */
function updSendBtn(){
    const has = document.getElementById('msgInput').value.trim()!=='' || pendingFile;
    document.getElementById('sendBtn').style.display = has?'flex':'none';
    document.getElementById('micBtn').style.display = has?'none':'flex';
    const cb=document.getElementById('circleBtn'); if(cb) cb.style.display = has?'none':'flex';
}

/* ---------- Запись голоса зажатием ---------- */
async function startRec(){
    if(recording || !curChat) return;
    if(!navigator.mediaDevices||!window.MediaRecorder){ alert('Запись не поддерживается'); return; }
    try{
        recStream=await navigator.mediaDevices.getUserMedia({audio:true});
        rchunks=[]; rcancel=false; let mime=''; if(MediaRecorder.isTypeSupported('audio/webm'))mime='audio/webm'; else if(MediaRecorder.isTypeSupported('audio/mp4'))mime='audio/mp4';
        mrec=new MediaRecorder(recStream, mime?{mimeType:mime}:undefined);
        mrec.ondataavailable=e=>{if(e.data.size)rchunks.push(e.data);};
        mrec.onstop=()=>{ if(recStream)recStream.getTracks().forEach(t=>t.stop());
            if(rchunks.length&&!rcancel){ const rm=(mrec.mimeType||mime||'audio/webm'); const ext=rm.includes('mp4')?'m4a':'webm'; const blob=new Blob(rchunks,{type:rm}); const vf=new File([blob],'voice_'+Date.now()+'.'+ext,{type:rm}); sendVoice(vf, recSecs); }
        };
        mrec.start(); recording=true; recSecs=0;
        document.getElementById('micBtn').classList.add('rec');
        document.getElementById('recBar').style.display='flex';
        document.getElementById('recTime').textContent='0:00';
        recTimer=setInterval(()=>{ recSecs++; document.getElementById('recTime').textContent=Math.floor(recSecs/60)+':'+String(recSecs%60).padStart(2,'0'); },1000);
    }catch(e){ alert('Нет доступа к микрофону'); }
}
let recTimer=null, recSecs=0;
function stopRec(cancel){
    if(!recording) return;
    rcancel=!!cancel || recSecs<1; // меньше 1 сек — отмена
    recording=false; clearInterval(recTimer);
    document.getElementById('micBtn').classList.remove('rec');
    document.getElementById('recBar').style.display='none';
    try{ if(mrec&&mrec.state!=='inactive')mrec.stop(); }catch(e){}
}
async function sendVoice(file, dur){
    if(!curChat) return; const rt=replyTo; clearReply();
    const e=await encFileForSend(file,'audio');
    const fd=new FormData(); fd.append('chat',curChat); fd.append('text',''); if(rt)fd.append('reply_to',rt); fd.append('file',e.file); fd.append('dur', dur||0); if(e.enc){fd.append('enc','1');fd.append('media_type',e.mt);}
    const resp=await fetch('messenger.php?action=send',{method:'POST',body:fd}).then(x=>x.json()).catch(()=>({}));
    if(resp&&resp.error==='blocked'){ alert('Вы не можете писать этому пользователю.'); return; }
    document.getElementById('msgsArea').dataset.sig=''; await loadMsgs(true);
}
/* привязка зажатия к микрофону */
(function(){
    const mic=document.getElementById('micBtn'); if(!mic) return;
    let startX=0;
    mic.addEventListener('pointerdown',e=>{ e.preventDefault(); startX=e.clientX; startRec(); });
    mic.addEventListener('pointermove',e=>{ if(recording){ const dx=startX-e.clientX; document.getElementById('recHint').textContent = dx>60?'отпустите для отмены':'← отпустите для отправки'; } });
    window.addEventListener('pointerup',e=>{ if(recording){ const cancel=(startX-e.clientX)>60; stopRec(cancel); } });
    mic.addEventListener('pointercancel',()=>{ if(recording)stopRec(true); });
})();

/* ---------- Видео-кружок ---------- */
let crec=null, cchunks=[], crecording=false, ccancel=false, cstream=null, cTimer=null, cSecs=0, cStartY=0;
async function startCircleRec(){
    if(crecording || !curChat) return;
    if(!navigator.mediaDevices||!window.MediaRecorder){ alert('Запись видео не поддерживается'); return; }
    try{
        cstream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:480},height:{ideal:480}},audio:true});
        const pv=document.getElementById('circlePreview'); pv.srcObject=cstream; pv.play&&pv.play().catch(()=>{});
        document.getElementById('circleRec').style.display='flex';
        cchunks=[]; ccancel=false;
        let mime=''; if(MediaRecorder.isTypeSupported('video/mp4'))mime='video/mp4'; else if(MediaRecorder.isTypeSupported('video/webm'))mime='video/webm';
        crec=new MediaRecorder(cstream, mime?{mimeType:mime}:undefined);
        crec.ondataavailable=e=>{if(e.data.size)cchunks.push(e.data);};
        crec.onstop=()=>{ if(cstream)cstream.getTracks().forEach(t=>t.stop());
            document.getElementById('circleRec').style.display='none';
            if(cchunks.length&&!ccancel){ const rm=(crec.mimeType||mime||'video/webm'); const ext=rm.includes('mp4')?'mp4':'webm'; const blob=new Blob(cchunks,{type:rm}); const cf=new File([blob],'circle_'+Date.now()+'.'+ext,{type:rm}); sendCircle(cf, cSecs); }
        };
        crec.start(); crecording=true; cSecs=0;
        document.getElementById('circleTime').textContent='0:00';
        cTimer=setInterval(()=>{ cSecs++; document.getElementById('circleTime').textContent=Math.floor(cSecs/60)+':'+String(cSecs%60).padStart(2,'0'); if(cSecs>=60)stopCircleRec(false); },1000);
    }catch(e){ alert('Нет доступа к камере'); }
}
function stopCircleRec(cancel){
    if(!crecording) return;
    ccancel=!!cancel || cSecs<1;
    crecording=false; clearInterval(cTimer);
    try{ if(crec&&crec.state!=='inactive')crec.stop(); }catch(e){}
}
// шифруем файл для отправки в личном чате (иначе — как есть)
async function encFileForSend(file, mediaType){
    if(curType!=='private' || !e2eEnabled()) return {file:file, mt:'', enc:''};
    await ensurePeerKey(window._lastPeerPubkey);
    const eb=await e2eEncryptBlob(file);
    if(eb) return {file:new File([eb],'m.enc',{type:'application/octet-stream'}), mt:mediaType, enc:'1'};
    return {file:file, mt:'', enc:''};
}
async function sendCircle(file, dur){
    if(!curChat) return; const rt=replyTo; clearReply();
    const e=await encFileForSend(file,'circle');
    const fd=new FormData(); fd.append('chat',curChat); fd.append('text',''); if(rt)fd.append('reply_to',rt); fd.append('file',e.file); fd.append('circle','1'); fd.append('dur',dur||0); if(e.enc){fd.append('enc','1');fd.append('media_type',e.mt);}
    const resp=await fetch('messenger.php?action=send',{method:'POST',body:fd}).then(x=>x.json()).catch(()=>({}));
    if(resp&&resp.error==='blocked'){ alert('Вы не можете писать этому пользователю.'); return; }
    document.getElementById('msgsArea').dataset.sig=''; await loadMsgs(true);
}
(function(){
    const cb=document.getElementById('circleBtn'); if(!cb) return;
    cb.addEventListener('pointerdown',e=>{ e.preventDefault(); cStartY=e.clientY; startCircleRec(); });
    window.addEventListener('pointermove',e=>{ if(crecording){ /* свайп вниз для отмены */ } });
    window.addEventListener('pointerup',e=>{ if(crecording){ const cancel=(e.clientY-cStartY)>90; stopCircleRec(cancel); } });
    cb.addEventListener('pointercancel',()=>{ if(crecording)stopCircleRec(true); });
})();

/* ---------- Плеер голосового ---------- */
function genWave(id,n){ let s=(id*9301+49297)%233280; const a=[]; for(let i=0;i<n;i++){ s=(s*9301+49297)%233280; a.push(0.22+(s/233280)*0.78); } return a; }
function voiceHtml(m){
    const dur=+m.dur||0;
    const out=(+m.sender_id===ME);
    const n=Math.max(24,Math.min(54, 22+Math.round(dur*1.1))); // длиннее голос — больше полосок
    const bars=genWave(+m.id,n);
    const w=bars.map(h=>`<span class="vb" style="height:${Math.round(h*100)}%"></span>`).join('');
    const minW=Math.min(258, 148+dur*3); // длиннее голос — шире плеер
    // непрослушанное входящее голосовое — синяя точка
    const unp = (!out && +m.played!==1) ? `<span id="vu${m.id}" style="width:9px;height:9px;border-radius:50%;background:var(--blue);flex-shrink:0"></span>` : '';
    return `<div class="voice" data-id="${m.id}" data-dur="${dur}" style="min-width:${minW}px">
        <button class="vplay" id="vp${m.id}" onclick="event.stopPropagation();playVoice('${m.file}',${m.id})">${SVG_PLAY}</button>
        <div class="vright">
            <div class="vwave" id="vw${m.id}" onclick="event.stopPropagation()">${w}</div>
            <div class="vmeta"><span class="vdur" id="vd${m.id}">${fmtV(dur)}</span>${unp}</div>
        </div>
    </div>`;
}
let vAudio=null, vCur=null;
const SVG_PLAY='<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
const SVG_PAUSE='<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';
function setVPlay(id,playing){ const b=document.getElementById('vp'+id); if(b)b.innerHTML=playing?SVG_PAUSE:SVG_PLAY; }
function fmtV(s){ s=Math.floor(s||0); return Math.floor(s/60)+':'+String(s%60).padStart(2,'0'); }
function updWave(id,cur,dur){ const wr=document.getElementById('vw'+id); if(!wr)return; const bars=wr.querySelectorAll('.vb'); const p=dur?cur/dur:0; const k=Math.floor(p*bars.length); bars.forEach((b,i)=>b.classList.toggle('on',i<=k)); const d=document.getElementById('vd'+id); if(d)d.textContent=fmtV(dur?dur-cur:0); }
function resetWave(id){ const wr=document.getElementById('vw'+id); if(wr)wr.querySelectorAll('.vb').forEach(b=>b.classList.remove('on')); }
function playVoice(src,id){
    if(vCur===id && vAudio && !vAudio.paused){ vAudio.pause(); setVPlay(id,false); return; }
    if(vAudio){ vAudio.pause(); if(vCur!==null)setVPlay(vCur,false); }
    vAudio=new Audio(src); vCur=id;
    vAudio.onloadedmetadata=()=>{ const d=document.getElementById('vd'+id); if(d&&isFinite(vAudio.duration))d.textContent=fmtV(vAudio.duration); };
    vAudio.ontimeupdate=()=>updWave(id,vAudio.currentTime,vAudio.duration);
    vAudio.onended=()=>{ setVPlay(id,false); resetWave(id); const d=document.getElementById('vd'+id); if(d&&isFinite(vAudio.duration))d.textContent=fmtV(vAudio.duration); vCur=null; };
    vAudio.play().then(()=>setVPlay(id,true)).catch(()=>{});
    // отметить как прослушанное (если было непрослушанное входящее)
    const dot=document.getElementById('vu'+id);
    if(dot){ dot.remove(); api('mark_played','POST',{id:id}); }
}

async function sendMsg(){
    const ta=document.getElementById('msgInput'); const text=ta.value.trim();
    if((!text && !pendingFile) || !curChat) return;
    ta.value=''; ta.style.height='auto'; hideMentions();
    const rt=replyTo; clearReply();
    // шифруем текст и файл в личных чатах (кроме одноразовых)
    let outText=text, encFlag='', fileToSend=pendingFile, mediaTypeFlag='';
    const canEnc = (curType==='private' && !pendingOnce && e2eEnabled());
    if(canEnc) await ensurePeerKey(window._lastPeerPubkey);
    if(text && canEnc){ try{ const c=await e2eEncrypt(text); if(c){ outText=c; encFlag='1'; } }catch(e){} }
    if(pendingFile && canEnc){ try{ const eb=await e2eEncryptBlob(pendingFile); if(eb){ const t=pendingFile.type||''; mediaTypeFlag=t.startsWith('image/')?'image':(t.startsWith('video/')?'video':(t.startsWith('audio/')?'audio':'file')); fileToSend=new File([eb],'m.enc',{type:'application/octet-stream'}); encFlag='1'; } }catch(e){} }
    const fd=new FormData(); fd.append('chat',curChat); fd.append('text',outText); if(encFlag)fd.append('enc','1'); if(mediaTypeFlag)fd.append('media_type',mediaTypeFlag); if(rt)fd.append('reply_to',rt); if(fileToSend)fd.append('file',fileToSend); if(pendingOnce)fd.append('once','1');
    clrFile();
    const resp=await fetch('messenger.php?action=send',{method:'POST',body:fd}).then(x=>x.json()).catch(()=>({}));
    if(resp&&resp.error==='blocked'){ alert('Вы не можете писать этому пользователю (вас заблокировали).'); return; }
    playSnd('send');
    document.getElementById('msgsArea').dataset.sig='';
    await loadMsgs(true);
    updSendBtn();
}

/* ---------- Просмотр фото / видео ---------- */
let onceSeenId=null;
function showViewerImage(src){ const v=document.getElementById('imgViewer'),img=document.getElementById('imgViewerImg'),vid=document.getElementById('imgViewerVid'); vid.pause&&vid.pause(); vid.style.display='none'; vid.src=''; img.src=src; img.style.display='block'; v.style.display='flex'; }
function showViewerVideo(src){ const v=document.getElementById('imgViewer'),img=document.getElementById('imgViewerImg'),vid=document.getElementById('imgViewerVid'); img.style.display='none'; img.src=''; vid.src=src; vid.style.display='block'; v.style.display='flex'; vid.play&&vid.play().catch(()=>{}); }
function closeViewer(e){ if(e&&e.target&&e.target.id!=='imgViewer') return; const v=document.getElementById('imgViewer'),vid=document.getElementById('imgViewerVid'); v.style.display='none'; if(vid){vid.pause();vid.src='';vid.style.display='none';} document.getElementById('imgViewerImg').style.display='none';
    if(onceSeenId){ const id=onceSeenId; onceSeenId=null; api('once_seen','POST',{id:id}).then(()=>{ document.getElementById('msgsArea').dataset.sig=''; loadMsgs(true); }); }
}
function openImg(src){ onceSeenId=null; showViewerImage(src); }
async function openOnce(id,type){
    const r=await api('view_once&id='+id);
    if(r&&r.expired){ alert('Уже просмотрено — сообщение удалено'); document.getElementById('msgsArea').dataset.sig=''; loadMsgs(true); return; }
    if(!r||!r.url){ alert('Недоступно'); return; }
    onceSeenId=id;
    if(type==='image') showViewerImage(r.url); else showViewerVideo(r.url);
}
function toggleCircle(el){ const v=el.querySelector('video'); const m=el.querySelector('.circle-mute'); if(!v)return; if(v.muted){ v.muted=false; v.currentTime=0; v.play(); if(m)m.style.display='none'; } else { v.muted=true; if(m)m.style.display='flex'; } }

/* ===================== ИСТОРИИ ===================== */
let storyQueue=[], curStories=[], csIdx=0, curStoryUser=null, storyTimer=null, storyStart=0, storyDur=5000, storyPaused=false, storyElapsed=0, pendingStoryFile=null, storyHours=24, storyAud='all';
function myAvatarImg(){ const el=document.getElementById('myAva'); return el?el.innerHTML:'Я'; }
async function loadStories(){
    const r=await api('stories_feed'); if(!r||!r.ok) return;
    const bar=document.getElementById('storiesBar'); let html='';
    const me=r.me;
    html+=`<div class="story-item" onclick="myStoryClick(${me?1:0})"><div class="story-ring ${me?'unseen':'me-add'}"><div class="si">${myAvatarImg()}</div></div><span class="story-add-badge" onclick="event.stopPropagation();addStory()">+</span><div class="story-name">Моя</div></div>`;
    storyQueue=[];
    (r.users||[]).forEach(u=>{
        storyQueue.push(u.user_id);
        html+=`<div class="story-item" onclick="openStoryUser(${u.user_id})"><div class="story-ring ${u.unseen>0?'unseen':''}"><div class="si">${u.avatar?`<img src="${u.avatar}">`:esc((u.name||'?').charAt(0).toUpperCase())}</div></div><div class="story-name">${esc(u.name||'')}</div></div>`;
    });
    bar.innerHTML=html;
}
function myStoryClick(has){ if(has) openStoryUser(ME); else addStory(); }
function addStory(){ document.getElementById('storyFile').click(); }
function pickStory(inp){ const f=inp.files[0]; if(!f)return; if(f.size>25*1024*1024){alert('Файл больше 25 МБ');inp.value='';return;} pendingStoryFile=f; storyHours=24; storyAud='all';
    const pv=document.getElementById('storyPrev'); if(f.type.startsWith('image')){ pv.src=URL.createObjectURL(f); pv.style.display='inline-block'; } else { pv.style.display='none'; }
    document.getElementById('storyCaption').value='';
    document.getElementById('storyOpts').style.display='flex';
}
function segPick(group,btn){ document.querySelectorAll('#'+group+' button').forEach(b=>b.classList.remove('on')); btn.classList.add('on'); const v=btn.dataset.v; if(group==='storyHours')storyHours=+v; else storyAud=v; }
function togglePollForm(){ const f=document.getElementById('pollForm'); const on=f.style.display==='none'; f.style.display=on?'block':'none'; document.getElementById('pollToggle').style.background=on?'rgba(124,92,255,.2)':'var(--panel2)'; }
async function publishStory(){
    if(!pendingStoryFile) return;
    const fd=new FormData(); fd.append('file',pendingStoryFile); fd.append('hours',storyHours); fd.append('audience',storyAud); fd.append('text',document.getElementById('storyCaption').value.trim());
    // опрос
    if(document.getElementById('pollForm').style.display!=='none'){
        const q=document.getElementById('pollQ').value.trim();
        const opts=Array.from(document.querySelectorAll('#pollForm .pollOpt')).map(i=>i.value.trim()).filter(v=>v);
        if(q && opts.length>=2){ fd.append('poll',JSON.stringify({q:q,options:opts})); }
        else if(q||opts.length){ alert('Для опроса нужен вопрос и минимум 2 варианта'); return; }
    }
    document.getElementById('storyOpts').style.display='none';
    const r=await fetch('messenger.php?action=story_add',{method:'POST',body:fd}).then(x=>x.json()).catch(()=>({}));
    pendingStoryFile=null;
    // сброс формы опроса
    document.getElementById('pollForm').style.display='none'; document.getElementById('pollQ').value=''; document.querySelectorAll('#pollForm .pollOpt').forEach(i=>i.value='');
    if(r&&r.ok){ loadStories(); } else if(r&&r.error==='limit'){ alert(r.msg||'Можно добавлять только 2 истории в день'); } else { alert('Не удалось опубликовать'); }
}
/* просмотр */
async function openStoryUser(uid){
    const r=await api('story_get&user='+uid); if(!r||!r.ok||!r.stories.length){ return; }
    curStoryUser=r.user; curStories=r.stories; csIdx=0;
    document.getElementById('svAva').innerHTML=r.user.avatar?`<img src="${r.user.avatar}">`:esc((r.user.name||'?').charAt(0).toUpperCase());
    document.getElementById('svName').textContent=r.user.name;
    document.getElementById('storyViewer').style.display='flex';
    buildBars(); playStory();
}
function buildBars(){ const b=document.getElementById('storyBars'); b.innerHTML=curStories.map(()=>`<div class="sbar"><div class="fill"></div></div>`).join(''); }
function setBar(i,p){ const bars=document.querySelectorAll('#storyBars .sbar .fill'); bars.forEach((f,idx)=>{ f.style.width = idx<i?'100%':(idx===i?(p*100)+'%':'0%'); }); }
function playStory(){
    clearInterval(storyTimer); storyPaused=false; storyElapsed=0;
    const s=curStories[csIdx]; if(!s){ closeStoryViewer(); return; }
    const img=document.getElementById('svImg'), vid=document.getElementById('svVid');
    document.getElementById('svTime').textContent=storyAge(s.ts);
    document.getElementById('svCaption').textContent=s.text||'';
    renderPoll(s);
    // мой/чужой интерфейс
    const mine=s.is_me;
    document.getElementById('svDel').style.display=mine?'flex':'none';
    document.getElementById('svOwnerBar').style.display=mine?'block':'none';
    document.getElementById('svViewerBar').style.display=mine?'none':'flex';
    if(mine){ document.getElementById('svViewCount').textContent=s.viewers||0; }
    else { renderReax(s); document.getElementById('svReply').value=''; api('story_view','POST',{id:s.id}); }
    if(s.type==='video'){
        img.style.display='none'; vid.style.display='block'; vid.src=s.file; vid.currentTime=0;
        vid.onloadedmetadata=()=>{ storyDur=(vid.duration&&isFinite(vid.duration))?vid.duration*1000:8000; };
        vid.ontimeupdate=()=>{ if(vid.duration)setBar(csIdx, vid.currentTime/vid.duration); };
        vid.onended=()=>nextStory();
        vid.play().catch(()=>{});
    } else {
        vid.style.display='none'; vid.pause&&vid.pause(); img.style.display='block'; img.src=s.file;
        storyDur=s.poll?15000:5000; storyStart=Date.now();
        storyTimer=setInterval(()=>{ if(storyPaused)return; const el=Date.now()-storyStart; setBar(csIdx,Math.min(1,el/storyDur)); if(el>=storyDur){ clearInterval(storyTimer); nextStory(); } },50);
    }
}
function nextStory(){ clearInterval(storyTimer); const v=document.getElementById('svVid'); v.pause&&v.pause();
    if(csIdx<curStories.length-1){ csIdx++; buildBars(); playStory(); }
    else { // следующий пользователь
        const qi=storyQueue.indexOf(curStoryUser?curStoryUser.id:-1);
        if(qi>=0 && qi<storyQueue.length-1){ openStoryUser(storyQueue[qi+1]); }
        else closeStoryViewer();
    }
}
function prevStory(){ clearInterval(storyTimer); if(csIdx>0){ csIdx--; buildBars(); playStory(); } else { storyStart=Date.now(); if(curStories[csIdx].type!=='video')playStory(); } }
function storyPause(){ storyPaused=true; storyElapsed=Date.now()-storyStart; const v=document.getElementById('svVid'); if(v&&!v.paused)v.pause(); }
function storyResume(){ if(!storyPaused)return; storyPaused=false; storyStart=Date.now()-storyElapsed; const v=document.getElementById('svVid'); if(v&&document.getElementById('svVid').style.display==='block')v.play().catch(()=>{}); }
function closeStoryViewer(){ clearInterval(storyTimer); const v=document.getElementById('svVid'); if(v){v.pause();v.src='';} document.getElementById('storyViewer').style.display='none'; loadStories(); }
function storyAge(ts){ const d=Math.floor(Date.now()/1000)-ts; if(d<60)return 'только что'; if(d<3600)return Math.floor(d/60)+' мин'; if(d<86400)return Math.floor(d/3600)+' ч'; return Math.floor(d/86400)+' дн'; }
const STORY_REAX=['❤️','👍','🔥','😮','😢'];
function renderReax(s){ document.getElementById('svReax').innerHTML=STORY_REAX.map(e=>`<button class="sv-reax" onclick="reactStory('${e}')" style="${s.my_reaction===e?'background:rgba(255,255,255,.4)':''}">${e}</button>`).join(''); }
async function reactStory(e){ const s=curStories[csIdx]; if(!s)return; s.my_reaction=e; renderReax(s); await api('story_react','POST',{id:s.id,emoji:e}); }
async function sendStoryReply(){ const s=curStories[csIdx]; if(!s)return; const inp=document.getElementById('svReply'); const t=inp.value.trim(); if(!t)return; inp.value=''; await api('story_reply','POST',{id:s.id,text:t}); inp.placeholder='Отправлено ✓'; setTimeout(()=>inp.placeholder='Ответить…',1500); }
function renderPoll(s){
    const box=document.getElementById('svPoll');
    if(!s.poll){ box.style.display='none'; box.innerHTML=''; return; }
    const p=s.poll; const voted=(p.my!==null && p.my!==undefined) || s.is_me; const total=p.total||0;
    let h=`<div style="color:#fff;font-weight:800;font-size:15px;margin-bottom:10px;text-align:center">${esc(p.q)}</div>`;
    p.options.forEach((opt,i)=>{
        const cnt=(p.counts&&p.counts[i])||0; const pct=total?Math.round(cnt/total*100):0; const mine=(p.my===i);
        if(voted){
            h+=`<div style="position:relative;margin-bottom:7px;border-radius:10px;overflow:hidden;background:rgba(255,255,255,.14)">
                <div style="position:absolute;inset:0;width:${pct}%;background:${mine?'rgba(124,92,255,.75)':'rgba(255,255,255,.22)'}"></div>
                <div style="position:relative;display:flex;justify-content:space-between;padding:10px 13px;color:#fff;font-weight:700;font-size:14px"><span>${esc(opt)}${mine?' ✓':''}</span><span>${pct}%</span></div>
            </div>`;
        } else {
            h+=`<button onclick="voteStory(${i})" style="display:block;width:100%;text-align:left;margin-bottom:7px;padding:11px 13px;border:none;border-radius:10px;background:rgba(255,255,255,.16);color:#fff;font-weight:700;font-size:14px;cursor:pointer;font-family:inherit">${esc(opt)}</button>`;
        }
    });
    if(voted && total>0) h+=`<div style="text-align:center;color:rgba(255,255,255,.65);font-size:12px;font-weight:600;margin-top:3px">${total} голос(ов)</div>`;
    box.innerHTML=h; box.style.display='block';
}
async function voteStory(i){
    const s=curStories[csIdx]; if(!s||!s.poll)return;
    s.poll.my=i; if(!s.poll.counts)s.poll.counts=s.poll.options.map(()=>0); s.poll.counts[i]++; s.poll.total=(s.poll.total||0)+1;
    renderPoll(s);
    await api('story_vote','POST',{id:s.id,choice:i});
}
async function deleteCurStory(){ const s=curStories[csIdx]; if(!s)return; if(!confirm('Удалить историю?'))return; await api('story_delete','POST',{id:s.id}); curStories.splice(csIdx,1); if(!curStories.length){ closeStoryViewer(); return; } if(csIdx>=curStories.length)csIdx=curStories.length-1; buildBars(); playStory(); }
async function openViewers(){ const s=curStories[csIdx]; if(!s)return; storyPause(); const r=await api('story_viewers&id='+s.id); const box=document.getElementById('viewersList');
    box.innerHTML=(r.viewers&&r.viewers.length)?r.viewers.map(v=>`<div class="row"><div class="ava" style="width:44px;height:44px;font-size:17px">${v.avatar?`<img src="${v.avatar}">`:esc((v.name||'?').charAt(0).toUpperCase())}</div><div class="row-main"><div class="row-name">${esc(v.name)}</div><div class="row-last">${storyAge(v.ts)}</div></div>${v.reaction?`<span style="font-size:20px">${v.reaction}</span>`:''}</div>`).join(''):'<div class="hint">Пока никто не смотрел</div>';
    document.getElementById('viewersOv').style.display='flex';
}
/* удержание = пауза, тап слева/справа = навигация */
(function(){ const st=document.getElementById('storyStage'); if(!st)return; let t=null,held=false,downT=0,downX=0;
    st.addEventListener('pointerdown',e=>{ downT=Date.now(); downX=e.clientX; held=false; t=setTimeout(()=>{held=true;storyPause();},260); });
    st.addEventListener('pointerup',e=>{ clearTimeout(t); if(held){ storyResume(); held=false; return; } const dt=Date.now()-downT; if(dt<260){ const rect=st.getBoundingClientRect(); const x=e.clientX-rect.left; if(x<rect.width*0.35)prevStory(); else nextStory(); } });
    st.addEventListener('pointercancel',()=>{ clearTimeout(t); if(held){storyResume();held=false;} });
})();
function playVid(wrap,src){
    wrap.onclick=null;
    wrap.innerHTML=`<video src="${src}" controls autoplay playsinline style="max-width:230px;max-height:300px;border-radius:12px;display:block"></video>`;
    wrap.style.minHeight='0';
}

function callPeer(){ if(curPeer && window.QAZCALL) QAZCALL.startCall(curPeer, curTitle, curAvatar, false); }
function videoCall(){ if(curPeer && window.QAZCALL) QAZCALL.startCall(curPeer, curTitle, curAvatar, true); }
function chatHeaderTap(){ openInfo(); }

/* ---------- Профиль пользователя (тап в группе) ---------- */
async function openUserProfile(uid){
    if(!uid) return;
    window.curProfileUid=uid;
    document.getElementById('userProfileOv').style.display='block';
    document.getElementById('userProfileBody').innerHTML='<div class="hint">Загрузка…</div>';
    const r=await api('user_profile&user='+uid); if(!r.ok){ document.getElementById('userProfileBody').innerHTML='<div class="hint">Профиль не найден</div>'; return; }
    const p=r.profile;
    // значок чата в шапке (для чужого профиля)
    const chatBtn=document.getElementById('profChatBtn');
    if(chatBtn){ if(!p.is_me && !p.deleted){ window._profChat={id:p.id,name:p.name,avatar:p.avatar||''}; chatBtn.style.display='flex'; } else { chatBtn.style.display='none'; } }
    const avaInner=p.avatar?`<img src="${p.avatar}">`:esc((p.name||'?').charAt(0).toUpperCase());
    const avaHtml=p.has_story
        ? `<div class="story-ring unseen" style="width:120px;height:120px;margin:0 auto 12px;padding:4px;cursor:pointer" onclick="openStoryUser(${p.id})"><div class="si" style="font-size:48px">${avaInner}</div></div>`
        : `<div class="ava" style="width:120px;height:120px;font-size:48px;margin:0 auto 12px">${avaInner}</div>`;
    let html=`<div style="text-align:center;padding:26px 20px 18px;background:var(--panel);border-bottom:1px solid var(--line)">
        ${avaHtml}
        <div style="font-size:21px;font-weight:800">${esc(p.name)}${+p.verified===1?VBADGE:''}</div>
        <div style="color:var(--sub);font-size:13px;font-weight:600;margin-top:3px">${esc(p.status||'')}</div>
        ${p.has_story?`<div onclick="openStoryUser(${p.id})" style="color:var(--blue);font-size:13px;font-weight:700;margin-top:6px;cursor:pointer">Посмотреть историю</div>`:''}
    </div>`;
    html+='<div style="background:var(--panel);margin-top:12px">';
    let any=false;
    if(p.phone){ html+=infoRow('Телефон', esc(p.phone), 'tel:'+p.phone); any=true; }
    else if(p.phone_hidden){ html+=infoRow('Телефон', '<span style="color:var(--blue);font-weight:700">Скрыт</span>'); any=true; }
    if(p.username){ html+=infoRow('Имя пользователя', '@'+esc(p.username)); any=true; }
    if(p.bio){ html+=infoRow('О себе', esc(p.bio)); any=true; }
    if(!any) html+='<div style="padding:16px;color:var(--sub);font-size:14px">Нет дополнительной информации</div>';
    html+='</div>';
    if(!p.is_me && !p.deleted){
        html+='<div style="padding:14px 16px;background:var(--panel);margin-top:12px">';
        html+=`<button class="st-btn" style="background:var(--blue);color:#fff" onclick="pmUser(${p.id},'${esc(p.name).replace(/'/g,"\\'")}','${p.avatar||''}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 01-8.5 8.5 8.4 8.4 0 01-3.8-.9L3 21l1.9-5.7A8.4 8.4 0 013.5 12 8.4 8.4 0 0112 3.5h.5A8.4 8.4 0 0121 11.5z"/></svg> Написать</button>`;
        html+=`<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="callUser(${p.id},'${esc(p.name).replace(/'/g,"\\'")}','${p.avatar||''}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.9v3a2 2 0 01-2.2 2 19.8 19.8 0 01-8.6-3.1 19.5 19.5 0 01-6-6 19.8 19.8 0 01-3.1-8.7A2 2 0 014.1 2h3a2 2 0 012 1.7c.1.9.4 1.8.7 2.7a2 2 0 01-.5 2.1L8.1 9.9a16 16 0 006 6l1.4-1.2a2 2 0 012.1-.5c.9.3 1.8.6 2.7.7a2 2 0 011.7 2z"/></svg> Позвонить</button>`;
        html+= p.is_contact
            ? `<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="if(confirm('Удалить из контактов?')){api('contact_remove','POST',{user:${p.id}}).then(()=>openUserProfile(${p.id}));}"><svg viewBox="0 0 24 24" fill="none" stroke="#4ADE80" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M16 11l2 2 4-4"/></svg> В контактах</button>`
            : `<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="addToContacts(${p.id},'${esc(p.name).replace(/'/g,"\\'")}',${p.phone_hidden?1:0},'${p.phone||''}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/></svg> Добавить в контакты</button>`;
        html+= p.blocked
            ? `<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="unblockPeer(${p.id});setTimeout(()=>openUserProfile(${p.id}),200)">${ICO.check} Разблокировать</button>`
            : `<button class="st-btn" style="background:#3A2226;color:#FF6B6B" onclick="if(confirm('Заблокировать?')){api('block','POST',{user:${p.id}}).then(()=>openUserProfile(${p.id}));}">${ICO.ban} Заблокировать</button>`;
        if(p.viewer_admin){
            html+=`<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="toggleVerify(${p.id},${+p.verified===1?0:1})">${VBADGE} ${+p.verified===1?'Снять галочку':'Выдать синюю галочку'}</button>`;
        }
        html+='</div>';
    }
    if(!p.deleted){
        const plink = p.username ? ('?u='+encodeURIComponent(p.username)) : ('?user='+p.id);
        html+='<div style="padding:14px 16px;background:var(--panel);margin-top:12px">';
        html+=`<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="copyText(baseUrl()+'${plink}');toast('Ссылка на профиль скопирована')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg> Поделиться профилем</button>`;
        html+='</div>';
    }
    document.getElementById('userProfileBody').innerHTML=html;
}
async function pmUser(id,name,avatar){ document.getElementById('userProfileOv').style.display='none'; const r=await api('open&user='+id); if(r.chat_id) openChat(r.chat_id,'private',id,name,avatar||''); }
function profWrite(){ const c=window._profChat; if(c) pmUser(c.id,c.name,c.avatar); }
function callUser(id,name,avatar){ document.getElementById('userProfileOv').style.display='none'; if(window.QAZCALL) QAZCALL.startCall(id,name,avatar||'',false); }
async function toggleVerify(uid,val){ await api('verify_toggle','POST',{user:uid,val:val}); openUserProfile(uid); document.getElementById('msgsArea').dataset.sig=''; loadChats(); }
async function openDevices(){
    document.getElementById('devSheet').style.display='flex';
    document.getElementById('devBody').innerHTML='<div class="hint">Загрузка…</div>';
    const r=await api('sessions_list');
    if(!r.ok){ document.getElementById('devBody').innerHTML='<div class="hint">Ошибка загрузки</div>'; return; }
    const phoneIco='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="22" height="22"><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/></svg>';
    let h='';
    const others=r.sessions.filter(s=>!s.current).length;
    r.sessions.forEach(s=>{
        h+=`<div style="display:flex;align-items:center;gap:12px;padding:12px 4px;border-bottom:1px solid var(--line)">
            <div style="color:${s.current?'var(--blue)':'var(--sub)'}">${phoneIco}</div>
            <div style="flex:1;min-width:0">
                <div style="font-weight:700;font-size:15px">${esc(s.name)}${s.current?' <span style="color:var(--blue);font-size:12px;font-weight:800">· это устройство</span>':''}</div>
                <div style="color:var(--sub);font-size:12.5px;font-weight:600;margin-top:2px">${esc(s.ip)} · ${esc(s.last)}</div>
            </div>
            ${s.current?'':`<button onclick="termSession(${s.id})" style="background:#3A2226;color:#FF6B6B;border:none;border-radius:9px;padding:8px 12px;font-weight:700;font-size:13px;cursor:pointer;font-family:inherit">Выйти</button>`}
        </div>`;
    });
    if(others>0){ h+=`<button class="st-btn" style="background:#3A2226;color:#FF6B6B;margin-top:14px" onclick="termOthers()">Завершить все другие сеансы</button>`; }
    document.getElementById('devBody').innerHTML=h||'<div class="hint">Нет активных сеансов</div>';
}
async function termSession(id){ if(!confirm('Выйти на этом устройстве?'))return; await api('session_terminate','POST',{id:id}); openDevices(); }
async function termOthers(){ if(!confirm('Завершить все другие сеансы? На всех других устройствах потребуется войти заново.'))return; await api('sessions_terminate_others','POST',{}); openDevices(); }

/* ---------- Информация о чате ---------- */
let infoData=null;
const ICO={
    bell:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 00-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0"/></svg>',
    bellOff:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.7 21a2 2 0 01-3.4 0M18.6 13A17 17 0 0118 8M6 8a6 6 0 019.7-4.7M3 3l18 18"/></svg>',
    broom:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>',
    ban:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M5.6 5.6l12.8 12.8"/></svg>',
    check:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>',
    trash:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>',
    door:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>'
};
// Синяя галочка верификации (как в Telegram) — рисуется рядом с именем
const VBADGE='<svg viewBox="0 0 24 24" style="width:17px;height:17px;vertical-align:-3px;margin-left:5px;flex-shrink:0" aria-label="verified"><path fill="#3B9EFF" d="M12 1.6l2.3 1.7 2.9-.2 1 2.7 2.5 1.4-.7 2.8L22 12l-1.7 2.3.7 2.8-2.5 1.4-1 2.7-2.9-.2L12 22.4l-2.3-1.7-2.9.2-1-2.7-2.5-1.4.7-2.8L2 12l1.7-2.3-.7-2.8 2.5-1.4 1-2.7 2.9.2z"/><path fill="#fff" d="M10.6 15.2l-2.7-2.7 1.3-1.3 1.4 1.4 3.6-3.6 1.3 1.3z"/></svg>';
function closeInfo(){ document.getElementById('scInfo').classList.remove('show'); }
async function openInfo(){
    if(!curChat) return;
    document.getElementById('scInfo').classList.add('show');
    document.getElementById('infoBody').innerHTML='<div class="hint">Загрузка…</div>';
    const r=await api('chat_info&chat='+curChat); infoData=r; if(!r.ok) return;
    document.getElementById('infoEditBtn').style.display=(r.type==='group'&&r.my_admin)?'flex':'none';
    document.getElementById('infoTitle').textContent = r.type==='group'?'Инфо о группе':'Профиль';
    const muteLabel = r.muted?(ICO.bellOff+' Включить уведомления'):(ICO.bell+' Выключить уведомления');
    let html='';
    if(r.type==='private' && r.peer){
        const p=r.peer;
        html+=`<div style="text-align:center;padding:26px 20px 18px;background:var(--panel);border-bottom:1px solid var(--line)">
            <div class="ava" style="width:120px;height:120px;font-size:48px;margin:0 auto 12px">${p.avatar?`<img src="${p.avatar}">`:esc((p.name||'?').charAt(0).toUpperCase())}</div>
            <div style="font-size:21px;font-weight:800">${esc(p.name)}</div>
            <div style="color:var(--sub);font-size:13px;font-weight:600;margin-top:3px">${esc(p.status||'')}</div>
        </div>`;
        html+='<div style="background:var(--panel);margin-top:12px">';
        html+=infoRow('Телефон', esc(p.phone||''), 'tel:'+p.phone);
        if(p.username) html+=infoRow('Имя пользователя', '@'+esc(p.username));
        if(p.bio) html+=infoRow('О себе', esc(p.bio));
        html+='</div>';
        html+='<div style="padding:14px 16px;background:var(--panel);margin-top:12px">';
        html+=`<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="toggleMute()">${muteLabel}</button>`;
        html+=`<button class="st-btn" style="background:var(--panel2);color:var(--txt);display:flex;align-items:center;justify-content:space-between" onclick="chooseAutoDelete()"><span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;vertical-align:-4px;margin-right:9px"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M9 2h6"/></svg>Автоудаление</span><span style="color:var(--blue)">${autoDelLabel(window._autoDel||0)}</span></button>`;
        html+=`<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="clearHistory()">${ICO.broom} Очистить историю</button>`;
        html+=p.blocked
            ? `<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="unblockPeer(${p.id})">${ICO.check} Разблокировать</button>`
            : `<button class="st-btn" style="background:#3A2226;color:#FF6B6B" onclick="blockPeer(${p.id})">${ICO.ban} Заблокировать</button>`;
        html+=`<button class="st-btn" style="background:#3A2226;color:#FF6B6B" onclick="deleteChat()">${ICO.trash} Удалить чат</button>`;
        html+='</div>';
    } else if(r.type==='group'){
        html+=`<div style="text-align:center;padding:26px 20px 18px;background:var(--panel);border-bottom:1px solid var(--line)">
            <div style="position:relative;width:120px;height:120px;margin:0 auto 12px">
                <div class="ava g" style="width:120px;height:120px;font-size:48px">${r.avatar?`<img src="${r.avatar}">`:esc((r.name||'Г').charAt(0).toUpperCase())}</div>
                ${r.my_admin?`<button onclick="document.getElementById('gavaFile').click()" style="position:absolute;right:0;bottom:0;width:36px;height:36px;border-radius:50%;border:3px solid var(--panel);background:var(--blue);color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="17" height="17"><circle cx="12" cy="13" r="4"/><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/></svg></button>`:''}
            </div>
            <div style="font-size:21px;font-weight:800">${esc(r.name||'')}</div>
            <div style="color:var(--sub);font-size:13px;font-weight:600;margin-top:3px">${r.count} участник(ов)</div>
            ${r.about?`<div style="color:var(--sub);font-size:14px;margin-top:8px">${esc(r.about)}</div>`:''}
        </div>`;
        html+=`<div class="st-h" style="display:flex;justify-content:space-between;align-items:center">Участники ${r.my_admin?`<span style="color:var(--blue);cursor:pointer;text-transform:none;font-size:14px" onclick="openAddMember()">+ Добавить</span>`:''}</div>`;
        html+='<div style="background:var(--panel)">';
        html+=r.members.map(m=>{
            const dot=m.online?'<span style="width:9px;height:9px;border-radius:50%;background:#4CD964;display:inline-block;margin-left:6px"></span>':'';
            const badge=m.is_admin?'<span style="color:var(--blue);font-size:12px;font-weight:700">админ</span>':'';
            let ctrls='';
            if(r.my_admin && m.id!==ME){ ctrls=`<button class="icon-btn" style="width:34px;height:34px;color:${m.is_admin?'var(--blue)':'var(--sub)'}" onclick="toggleAdmin(${m.id},${m.is_admin?0:1})" title="Админ">★</button><button class="icon-btn" style="width:34px;height:34px;color:#FF6B6B" onclick="removeMember(${m.id},'${esc(m.name).replace(/'/g,"\\'")}')">✕</button>`; }
            return `<div class="row"><div class="ava" style="width:46px;height:46px;font-size:18px">${m.avatar?`<img src="${m.avatar}">`:esc(m.name.charAt(0).toUpperCase())}</div>
                <div class="row-main"><div class="row-name">${esc(m.name)}${dot}</div><div class="row-last">${badge||(m.online?'в сети':'')}</div></div>${ctrls}</div>`;
        }).join('');
        html+='</div>';
        html+='<div style="padding:14px 16px 40px;background:var(--panel);margin-top:12px">';
        html+=`<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="toggleMute()">${muteLabel}</button>`;
        if(r.my_admin) html+=`<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="clearHistory()">${ICO.broom} Очистить историю</button>`;
        html+=`<button class="st-btn" style="background:#3A2226;color:#FF6B6B" onclick="leaveChat()">${ICO.door} Выйти из группы</button>`;
        html+='</div>';
    }
    document.getElementById('infoBody').innerHTML=html;
}
function infoRow(label,val,href){ const inner=`<div><div style="color:var(--sub);font-size:12px;font-weight:700">${label}</div><div style="font-size:15px;font-weight:600;margin-top:2px">${val}</div></div>`; return `<div class="st-row" style="display:block">${href?`<a href="${href}" style="color:var(--blue);text-decoration:none">${inner}</a>`:inner}</div>`; }

async function toggleMute(){ if(!infoData)return; await api('mute_chat','POST',{chat:curChat,val:infoData.muted?0:1}); openInfo(); }
const AUTODEL_OPTS=[[0,'Выключено'],[3600,'1 час'],[86400,'1 день'],[604800,'1 неделя'],[2592000,'1 месяц'],[31536000,'1 год']];
function autoDelLabel(sec){ const o=AUTODEL_OPTS.find(x=>x[0]===+sec); return o?(o[0]===0?'Выкл':o[1]):'Выкл'; }
function chooseAutoDelete(){
    const cur=+window._autoDel||0;
    document.getElementById('autoDelOpts').innerHTML=AUTODEL_OPTS.map(o=>
        `<button class="st-btn" style="background:${o[0]===cur?'var(--blue)':'var(--panel2)'};color:${o[0]===cur?'#fff':'var(--txt)'};display:flex;align-items:center;justify-content:space-between" onclick="setAutoDelete(${o[0]})"><span>${o[1]}</span>${o[0]===cur?'<svg viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'#fff\' stroke-width=\'2.4\' stroke-linecap=\'round\' stroke-linejoin=\'round\' width=\'18\' height=\'18\'><path d=\'M20 6L9 17l-5-5\'/></svg>':''}</button>`
    ).join('');
    document.getElementById('autoDelSheet').style.display='flex';
}
async function setAutoDelete(sec){
    document.getElementById('autoDelSheet').style.display='none';
    await api('set_autodelete','POST',{chat:curChat,seconds:sec});
    window._autoDel=sec; document.getElementById('msgsArea').dataset.sig=''; loadMsgs(true); openInfo();
}async function clearHistory(){ if(confirm('Очистить всю историю этого чата?')){ await api('clear_history','POST',{chat:curChat}); document.getElementById('msgsArea').dataset.sig=''; closeInfo(); loadMsgs(true); } }
async function deleteChat(){ if(confirm('Удалить этот чат?')){ await api('leave_chat','POST',{chat:curChat}); closeInfo(); closeChat(); } }
async function leaveChat(){ if(confirm('Выйти из группы?')){ await api('leave_chat','POST',{chat:curChat}); closeInfo(); closeChat(); } }
async function blockPeer(id){ if(confirm('Заблокировать пользователя?')){ await api('block','POST',{user:id}); openInfo(); } }
async function unblockPeer(id){ await api('unblock','POST',{user:id}); openInfo(); }
/* группа: управление */
async function toggleAdmin(id,val){ await api('group_admin','POST',{chat:curChat,user:id,val:val}); openInfo(); }
async function removeMember(id,name){ if(confirm('Удалить '+name+' из группы?')){ await api('group_remove','POST',{chat:curChat,user:id}); openInfo(); } }
function editGroup(){ const name=prompt('Название группы:',infoData?infoData.name:''); if(name===null)return; const about=prompt('Описание группы:',infoData&&infoData.about?infoData.about:''); api('group_edit','POST',{chat:curChat,name:name.trim(),about:(about||'').trim()}).then(()=>openInfo()); }
async function uploadGroupAva(inp){ const f=inp.files[0]; if(!f)return; const fd=new FormData(); fd.append('chat',curChat); fd.append('file',f); const r=await fetch('messenger.php?action=group_avatar',{method:'POST',body:fd}).then(x=>x.json()).catch(()=>({})); if(r&&r.avatar)openInfo(); else alert('Не удалось загрузить'); inp.value=''; }
/* добавить участника */
function openAddMember(){ document.getElementById('addMemberOv').style.display='block'; document.getElementById('addMemberSearch').value=''; document.getElementById('addMemberResults').innerHTML=''; }
let amTimer=null;
function addMemberSearch(q){ clearTimeout(amTimer); if(q.trim().length<1){document.getElementById('addMemberResults').innerHTML='';return;} amTimer=setTimeout(async()=>{ const r=await api('search&q='+encodeURIComponent(q.trim())); document.getElementById('addMemberResults').innerHTML=(r.users||[]).map(u=>`<div class="row" onclick="addMember(${u.id},'${esc(u.name).replace(/'/g,"\\'")}')">${avaHtml(u.name,u.avatar,'')}<div class="row-main"><div class="row-name">${esc(u.name)}</div><div class="row-last">${userSub(u)}</div></div></div>`).join(''); },300); }
async function addMember(id,name){ await api('group_add','POST',{chat:curChat,user:id}); document.getElementById('addMemberOv').style.display='none'; openInfo(); }

/* ---------- Новая группа ---------- */
let groupPicked={};
function openNewGroup(){ groupPicked={}; document.getElementById('groupName').value=''; document.getElementById('groupSearch').value=''; document.getElementById('groupResults').innerHTML=''; renderChips(); document.getElementById('scGroup').classList.add('show'); }
function closeNewGroup(){ document.getElementById('scGroup').classList.remove('show'); }

/* ---------- Меню FAB ---------- */
function toggleFabMenu(e){ if(e)e.stopPropagation(); const m=document.getElementById('fabMenu'); const open=m.style.display==='block'; m.style.display=open?'none':'block'; if(!open){ setTimeout(()=>document.addEventListener('click',closeFabMenu),0); } }
function fabNewChannel(){ closeFabMenu(); if (typeof window.createChannel === "function") window.createChannel(); else alert("Каналы не загрузились. Обновите страницу."); }
function closeFabMenu(){ document.getElementById('fabMenu').style.display='none'; document.removeEventListener('click',closeFabMenu); }
function fabNewGroup(){ closeFabMenu(); openNewGroup(); }

/* ---------- Список контактов ---------- */
function openContacts(){ closeFabMenu(); document.getElementById('scContacts').classList.add('show'); loadContacts(); }
function closeContacts(){ document.getElementById('scContacts').classList.remove('show'); }
async function loadContacts(){
    const box=document.getElementById('contactsList');
    box.innerHTML='<div class="hint">Загрузка…</div>';
    const r=await api('contacts_list');
    const cs=(r&&r.contacts)||[];
    let html='<button class="row" onclick="openNewContact()" style="width:100%;border:none;background:none;text-align:left;cursor:pointer;font-family:inherit;border-bottom:1px solid var(--line)"><div class="ava" style="background:linear-gradient(140deg,#9575FF,#5B3FE0)"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="24" height="24"><path d="M19 8v6M22 11h-6M14 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2M8 11a4 4 0 100-8 4 4 0 000 8z"/></svg></div><div class="row-main"><div class="row-title" style="color:var(--blue);font-weight:800">Создать контакт</div></div></button>';
    if(!cs.length){ html+='<div class="hint" style="padding:26px 16px">У вас пока нет контактов.<br>Нажмите «Создать контакт».</div>'; }
    for(const c of cs){
        const ava=c.avatar?`<img src="${c.avatar}">`:esc((c.name||'?').charAt(0).toUpperCase());
        const sub=c.phone?esc(c.phone):esc(c.status||'');
        html+=`<button class="row" onclick="openContactChat(${c.user_id},'${esc(c.name).replace(/'/g,"\\'")}','${c.avatar||''}')" style="width:100%;border:none;background:none;text-align:left;cursor:pointer;font-family:inherit"><div class="ava">${ava}</div><div class="row-main"><div class="row-title">${esc(c.name)}</div><div class="row-sub">${sub}</div></div></button>`;
    }
    box.innerHTML=html;
}
async function openContactChat(uid,name,avatar){ const r=await api('open&user='+uid); if(r.chat_id){ closeContacts(); openChat(r.chat_id,'private',uid,name,avatar||''); } }

/* ---------- Новый контакт ---------- */
window.contactEditUser = 0; // если добавляем существующего пользователя из профиля
function contactAvaUpd(){ const v=(document.getElementById('contactFirst').value||'').trim(); document.getElementById('contactAva').textContent = v?v[0].toUpperCase():'?'; }
function openNewContact(){ closeFabMenu();
    window.contactEditUser=0;
    document.getElementById('contactTitle').textContent='Новый контакт';
    document.getElementById('contactFirst').value=''; document.getElementById('contactLast').value='';
    document.getElementById('contactNote').value=''; document.getElementById('contactShare').checked=true;
    document.getElementById('contactAva').textContent='?'; document.getElementById('contactAva').style.background='';
    // ручной ввод — поле номера активно
    document.getElementById('contactPhone').style.display='block'; document.getElementById('contactPhone').value='';
    document.getElementById('contactPhoneHidden').style.display='none';
    document.getElementById('contactPhoneHint').textContent='Введите номер телефона пользователя Payom.';
    document.getElementById('scContact').classList.add('show');
    setTimeout(()=>document.getElementById('contactFirst').focus(),200);
}
// открыть «Новый контакт» для существующего пользователя (из профиля/чата)
function addToContacts(uid,name,phoneHidden,phone){ 
    window.contactEditUser=uid;
    document.getElementById('contactTitle').textContent='Добавить в контакты';
    const parts=(name||'').split(' ');
    document.getElementById('contactFirst').value=parts.shift()||name||'';
    document.getElementById('contactLast').value=parts.join(' ');
    document.getElementById('contactNote').value=''; document.getElementById('contactShare').checked=true;
    contactAvaUpd();
    if(phoneHidden){ document.getElementById('contactPhone').style.display='none'; document.getElementById('contactPhoneHidden').style.display='block';
        document.getElementById('contactPhoneHint').textContent='Номер телефона будет виден, когда '+(name||'пользователь')+' добавит Вас в контакты.'; }
    else { document.getElementById('contactPhone').style.display='block'; document.getElementById('contactPhoneHidden').style.display='none';
        document.getElementById('contactPhone').value=phone||''; document.getElementById('contactPhone').readOnly=true;
        document.getElementById('contactPhoneHint').textContent=''; }
    document.getElementById('scContact').classList.add('show');
}
function closeContact(){ document.getElementById('scContact').classList.remove('show'); document.getElementById('contactPhone').readOnly=false; }
async function saveContact(){
    const first=(document.getElementById('contactFirst').value||'').trim();
    const last=(document.getElementById('contactLast').value||'').trim();
    const name=(first+' '+last).trim();
    const note=document.getElementById('contactNote').value.trim();
    const share=document.getElementById('contactShare').checked?1:0;
    if(!name){ alert('Введите имя'); return; }
    if(window.contactEditUser){
        const r=await api('contact_add_user','POST',{user:window.contactEditUser,name,note,share});
        if(r&&r.ok){ closeContact(); if(window.curProfileUid===window.contactEditUser) openUserProfile(window.contactEditUser); }
        else alert('Не удалось добавить');
        return;
    }
    const phone=(document.getElementById('contactPhone').value||'').trim();
    if(phone.replace(/\D/g,'').length<7){ alert('Введите номер телефона'); return; }
    const r=await api('contact_add','POST',{phone,name,note,share});
    if(r&&r.ok){ closeContact(); loadChats(); if(document.getElementById('scContacts').classList.contains('show'))loadContacts(); if(r.chat_id) openChat(r.chat_id,'private',r.user_id,name,''); }
    else alert(r&&r.msg?r.msg:'Пользователь с этим номером не найден в Payom');
}
function renderChips(){ const box=document.getElementById('groupChips'); const ids=Object.keys(groupPicked); box.innerHTML=ids.length?ids.map(id=>`<div class="gm-chip">${esc(groupPicked[id])}<span onclick="unpick(${id})">✕</span></div>`).join(''):'<span style="color:var(--sub);font-size:13px;font-weight:600">Пока никого не выбрано</span>'; }
function unpick(id){ delete groupPicked[id]; renderChips(); }
let gsTimer=null;
function onGroupSearch(q){
    clearTimeout(gsTimer);
    if(q.trim().length<1){ document.getElementById('groupResults').innerHTML=''; return; }
    gsTimer=setTimeout(async()=>{
        const r=await api('search&q='+encodeURIComponent(q.trim()));
        const box=document.getElementById('groupResults');
        box.innerHTML=(r.users||[]).map(u=>{
            const on=groupPicked[u.id]?'on':'';
            return `<div class="row" onclick="togglePick(${u.id},'${esc(u.name).replace(/'/g,"\\'")}')">
                <div class="ava">${esc(u.name.charAt(0).toUpperCase())}</div>
                <div class="row-main"><div class="row-name">${esc(u.name)}</div><div class="row-last">${userSub(u)}</div></div>
                <div class="chk ${on}" id="chk${u.id}">${on?'✓':''}</div></div>`;
        }).join('');
    },300);
}
function togglePick(id,name){ if(groupPicked[id]) delete groupPicked[id]; else groupPicked[id]=name; renderChips(); const c=document.getElementById('chk'+id); if(c){ c.classList.toggle('on'); c.textContent=groupPicked[id]?'✓':''; } }
async function createGroup(){
    const name=document.getElementById('groupName').value.trim();
    const members=Object.keys(groupPicked).map(Number);
    if(name.length<2){ alert('Введите название группы'); return; }
    if(!members.length){ alert('Добавьте хотя бы одного участника'); return; }
    const r=await api('create_group','POST',{name:name,members:members});
    if(r.chat_id){ closeNewGroup(); openChat(r.chat_id,'group',0,name); }
}

/* ---------- Ввод ---------- */
const inp=document.getElementById('msgInput');
// ===== @-упоминания участников группы =====
function hideMentions(){ const b=document.getElementById('mentionBox'); if(b){ b.style.display='none'; b.innerHTML=''; } }
function checkMention(){
    if(curType!=='group'){ hideMentions(); return; }
    const ta=inp, pos=ta.selectionStart, val=ta.value.slice(0,pos);
    const m=val.match(/(^|\s)@([A-Za-z0-9_]*)$/);
    if(!m){ hideMentions(); return; }
    const q=m[2].toLowerCase();
    const list=(window._grpMembers||[]).filter(u=>{
        const un=(u.username||'').toLowerCase(), nm=(u.name||'').toLowerCase();
        return q==='' || un.startsWith(q) || nm.includes(q);
    }).slice(0,20);
    const box=document.getElementById('mentionBox');
    if(!list.length){ hideMentions(); return; }
    box.innerHTML=list.map(u=>{
        const av=u.avatar?`<img src="${u.avatar}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`:esc((u.name||'?').charAt(0).toUpperCase());
        const uname=u.username?('@'+esc(u.username)):'';
        const val=u.username?('@'+u.username):('@'+(u.name||''));
        return `<div class="mrow" onclick="pickMention('${esc(val).replace(/'/g,"\\'")}')" style="display:flex;align-items:center;gap:11px;padding:9px 13px;cursor:pointer;border-bottom:1px solid var(--line)">
            <div class="ava" style="width:36px;height:36px;font-size:15px;background:${userColor(u.id)}">${av}</div>
            <div style="min-width:0"><div style="font-weight:700;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(u.name||'')}</div>${uname?`<div style="color:var(--sub);font-size:12.5px">${uname}</div>`:''}</div>
        </div>`;
    }).join('');
    box.style.display='block';
}
function pickMention(mention){
    const ta=inp, pos=ta.selectionStart, before=ta.value.slice(0,pos), after=ta.value.slice(pos);
    const nb=before.replace(/(^|\s)@([A-Za-z0-9_]*)$/, (mm,p1)=>p1+mention+' ');
    ta.value=nb+after;
    const np=nb.length; ta.setSelectionRange(np,np);
    hideMentions(); ta.focus(); updSendBtn();
}
let lastTyping=0;
inp.addEventListener('input',()=>{ inp.style.height='auto'; inp.style.height=Math.min(110,inp.scrollHeight)+'px'; updSendBtn();
    const now=Date.now(); if(curChat && now-lastTyping>3000){ lastTyping=now; api('typing','POST',{chat:curChat}); }
    checkMention(); });
inp.addEventListener('keydown',e=>{ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); sendMsg(); } });

/* клавиатура не ломает верстку */
if(window.visualViewport){ visualViewport.addEventListener('resize',()=>{ if(curChat){ const b=document.getElementById('msgsArea'); b.scrollTop=b.scrollHeight; } }); }

/* ---------- Push ---------- */
if('serviceWorker' in navigator){ navigator.serviceWorker.register('messenger.php?sw=1',{scope:location.pathname}).catch(()=>{ navigator.serviceWorker.register('sw.js').catch(()=>{}); }); }

/* ===== Установка приложения (PWA) ===== */
let deferredPrompt=null;
function isStandalone(){ return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone===true; }
function isIOSdev(){ return /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream; }
function isAndroid(){ return /android/i.test(navigator.userAgent); }
function hideInstall(){ const b=document.getElementById('installBanner'); if(b)b.style.display='none'; }
function maybeShowInstall(){
    // показываем всегда, пока приложение не установлено (не запущено как приложение)
    installLabel();
    if(isStandalone()){ hideInstall(); const s=document.getElementById('installRow'); if(s)s.style.display='none'; return; }
    const b=document.getElementById('installBanner'); if(b)b.style.display='flex';
}
function installLabel(){
    const big=document.getElementById('installBigTxt'), row=document.getElementById('installRowTxt');
    const txt = isIOSdev() ? 'Установить на iPhone' : (window.HAS_APK ? 'Скачать приложение' : 'Установить приложение');
    if(big)big.textContent=txt; if(row)row.textContent=txt;
    const as=document.getElementById('andSub'); if(as) as.textContent = window.HAS_APK ? 'Скачать приложение (APK)' : 'Установить приложение';
}
function dismissInstall(){ hideInstall(); } // скрыть на время сессии
function closeInstallSheet(){ const s=document.getElementById('installSheet'); if(s)s.style.display='none'; const st=document.getElementById('installSteps'); if(st)st.style.display='none'; }
async function doInstall(){ // один тап: сразу системная установка / APK / инструкция
    installLabel();
    // Android Chrome — сразу системное окно установки (иконка на экран)
    if(deferredPrompt){ deferredPrompt.prompt(); const c=await deferredPrompt.userChoice; deferredPrompt=null; if(c&&c.outcome==='accepted'){ hideInstall(); const s=document.getElementById('installRow'); if(s)s.style.display='none'; } return; }
    // APK загружен — скачиваем сразу
    if(window.HAS_APK){ window.location.href='messenger.php?apk=1'; return; }
    // iPhone или Android без готового окна — показываем инструкцию
    const st=document.getElementById('installSteps'); if(st){ st.style.display='none'; st.innerHTML=''; }
    document.getElementById('installSheet').style.display='flex';
    if(isIOSdev()) chooseIOS();
}
async function chooseAndroid(){
    // если APK загружен на сервер — скачиваем его
    if(window.HAS_APK){ window.location.href='messenger.php?apk=1'; return; }
    // иначе системная установка PWA или инструкция
    if(deferredPrompt){ deferredPrompt.prompt(); const c=await deferredPrompt.userChoice; deferredPrompt=null; if(c&&c.outcome==='accepted'){ hideInstall(); closeInstallSheet(); } return; }
    const st=document.getElementById('installSteps');
    st.innerHTML='<b>Как установить на Android:</b><br>1. Откройте меню браузера <b>⋮</b> (вверху справа)<br>2. Выберите <b>«Установить приложение»</b> или <b>«Добавить на главный экран»</b><br>3. Подтвердите';
    st.style.display='block';
}
function chooseIOS(){
    const st=document.getElementById('installSteps');
    st.innerHTML='<b>Как установить на iPhone:</b><br>1. Откройте сайт в <b>Safari</b><br>2. Нажмите <b>«Поделиться»</b> внизу экрана<br>3. Выберите <b>«На экран „Домой“»</b><br>4. Нажмите <b>«Добавить»</b>';
    st.style.display='block';
}
window.addEventListener('beforeinstallprompt',e=>{ e.preventDefault(); deferredPrompt=e; maybeShowInstall(); });
window.addEventListener('appinstalled',()=>{ deferredPrompt=null; hideInstall(); const s=document.getElementById('installRow'); if(s)s.style.display='none'; });
maybeShowInstall();
function uB64(b){const p='='.repeat((4-b.length%4)%4);const s=(b+p).replace(/-/g,'+').replace(/_/g,'/');const r=atob(s);const a=new Uint8Array(r.length);for(let i=0;i<r.length;i++)a[i]=r.charCodeAt(i);return a;}
async function subPush(){ if(!VAPID_PUBLIC||!('serviceWorker'in navigator)||!('PushManager'in window))return; if(!('Notification'in window)||Notification.permission!=='granted')return; try{ const reg=await navigator.serviceWorker.ready; let s=await reg.pushManager.getSubscription(); if(!s)s=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:uB64(VAPID_PUBLIC)}); await api('push_subscribe','POST',s.toJSON?s.toJSON():s);}catch(e){} }
document.addEventListener('click',function once(){ if('Notification'in window && Notification.permission==='default'){ Notification.requestPermission().then(p=>{if(p==='granted')subPush();}); } else subPush(); document.removeEventListener('click',once); },{once:true});

/* ===== Сквозное шифрование личных чатов (E2E: ECDH P-256 + AES-GCM) =====
   Секретный ключ хранится ТОЛЬКО на этом устройстве. Сервер видит лишь шифр. */
let myPriv=null, myPubB64=null, peerKeyCache={};
function _b64(u){ let s=''; const a=new Uint8Array(u); for(let i=0;i<a.length;i++) s+=String.fromCharCode(a[i]); return btoa(s); }
function _unb64(b){ return Uint8Array.from(atob(b),c=>c.charCodeAt(0)); }
async function ensureE2E(){
    if(myPriv) return;
    if(!window.crypto||!crypto.subtle) return; 
    try{
        const pj=localStorage.getItem('e2ePriv'), pb=localStorage.getItem('e2ePub');
        if(pj && pb){
            myPriv=await crypto.subtle.importKey('jwk',JSON.parse(pj),{name:'ECDH',namedCurve:'P-256'},false,['deriveKey']);
            myPubB64=pb;
            console.log('[E2E] Ключи загружены из localStorage');
        } else {
            const kp=await crypto.subtle.generateKey({name:'ECDH',namedCurve:'P-256'},true,['deriveKey']);
            myPriv=kp.privateKey;
            myPubB64=_b64(await crypto.subtle.exportKey('raw',kp.publicKey));
            localStorage.setItem('e2ePriv',JSON.stringify(await crypto.subtle.exportKey('jwk',kp.privateKey)));
            localStorage.setItem('e2ePub',myPubB64);
            console.log('[E2E] Новые ключи созданы и сохранены');
        }
        await api('key_set','POST',{pubkey:myPubB64});
        console.log('[E2E] Публичный ключ отправлен на сервер:', myPubB64.slice(0,20)+'...');
    }catch(e){ myPriv=null; console.error('[E2E] Ошибка при инициализации:', e); }
}
async function ensurePeerKey(peerPubB64){
    window._sharedKey=null;
    await ensureE2E();
    if(!myPriv) { console.log('[E2E] Свой приватный ключ не готов'); return; }
    if(!peerPubB64) { console.log('[E2E] Нет ключа собеседника'); return; }
    if(!curPeer) { console.log('[E2E] Нет текущего собеседника'); return; }
    if(peerKeyCache[curPeer]){ window._sharedKey=peerKeyCache[curPeer]; console.log('[E2E] Ключ получен из кэша'); return; }
    try{
        const peerPub=await crypto.subtle.importKey('raw',_unb64(peerPubB64),{name:'ECDH',namedCurve:'P-256'},false,[]);
        const key=await crypto.subtle.deriveKey({name:'ECDH',public:peerPub},myPriv,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
        peerKeyCache[curPeer]=key; window._sharedKey=key;
        console.log('[E2E] Общий AES-GCM ключ вычислен с собеседником', curPeer);
    }catch(e){ window._sharedKey=null; console.error('[E2E] Ошибка при вычислении ключа:', e); }
}
async function e2eEncrypt(text){
    if(!window._sharedKey) return null;
    try{ const iv=crypto.getRandomValues(new Uint8Array(12));
        const ct=await crypto.subtle.encrypt({name:'AES-GCM',iv},window._sharedKey,new TextEncoder().encode(text));
        return 'e1:'+_b64(iv)+'.'+_b64(ct);
    }catch(e){ return null; }
}
async function e2eDecrypt(payload){
    if(!payload || payload.indexOf('e1:')!==0) return payload;
    if(!window._sharedKey) { console.log('[E2E] Нет общего ключа, не могу расшифровать'); return '🔒 зашифровано'; }
    try{ const p=payload.slice(3).split('.'); const iv=_unb64(p[0]); const ct=_unb64(p[1]);
        const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv},window._sharedKey,ct);
        const text=new TextDecoder().decode(pt);
        console.log('[E2E] Текст расшифрован');
        return text;
    }catch(e){ console.error('[E2E] Ошибка расшифровки:', e); return '🔒 зашифровано'; }
}
// шифруем файл/блоб перед загрузкой: [iv(12) | шифртекст+тег]
async function e2eEncryptBlob(blob){
    if(!window._sharedKey) return null;
    try{ const buf=new Uint8Array(await blob.arrayBuffer());
        const iv=crypto.getRandomValues(new Uint8Array(12));
        const ct=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},window._sharedKey,buf));
        const out=new Uint8Array(iv.length+ct.length); out.set(iv,0); out.set(ct,iv.length);
        return new Blob([out],{type:'application/octet-stream'});
    }catch(e){ return null; }
}
// скачиваем шифр, расшифровываем в blob-URL (кэшируем по исходной ссылке)
let emediaCache={};
async function e2eFetchBlob(url){
    if(emediaCache[url]) return emediaCache[url];
    if(!window._sharedKey) return null;
    try{ const resp=await fetch(url); const buf=new Uint8Array(await resp.arrayBuffer());
        const iv=buf.slice(0,12); const ct=buf.slice(12);
        const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv},window._sharedKey,ct);
        const u=URL.createObjectURL(new Blob([pt])); emediaCache[url]=u; return u;
    }catch(e){ return null; }
}

/* ===== Блокировка приложения (пароль + Face ID/отпечаток) ===== */
async function sha256hex(t){ const b=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(t)); return Array.from(new Uint8Array(b)).map(x=>x.toString(16).padStart(2,'0')).join(''); }
function lockOn(){ return localStorage.getItem('lockOn')==='1'; }
function bioOn(){ return localStorage.getItem('lockBio')==='1' && !!localStorage.getItem('lockCred'); }
function openLockSettings(){ lockRender(); document.getElementById('lockSetSheet').style.display='flex'; }
function lockRender(){
    const on=lockOn(); let h='';
    if(!on){
        h+='<div style="color:var(--sub);font-size:13.5px;font-weight:600;text-align:center;margin-bottom:16px">Требовать пароль при каждом открытии приложения.</div>';
        h+='<button class="st-btn" style="background:var(--blue);color:#fff" onclick="enableLock()">Включить и задать пароль</button>';
    } else {
        h+='<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="changeLockPin()">Сменить пароль</button>';
        h+=`<button class="st-btn" style="background:var(--panel2);color:var(--txt);display:flex;align-items:center;justify-content:space-between" onclick="toggleLockBio()"><span>Face ID / отпечаток</span><span style="color:var(--blue)">${bioOn()?'Вкл':'Выкл'}</span></button>`;
        h+='<button class="st-btn" style="background:#3A2226;color:#FF6B6B" onclick="disableLock()">Выключить блокировку</button>';
    }
    document.getElementById('lockSetBody').innerHTML=h;
}
async function enableLock(){
    const p=prompt('Придумайте пароль (минимум 4 символа):'); if(p===null) return;
    if((p||'').length<4){ alert('Минимум 4 символа'); return; }
    if(prompt('Повторите пароль:')!==p){ alert('Пароли не совпадают'); return; }
    localStorage.setItem('lockHash',await sha256hex(p)); localStorage.setItem('lockOn','1');
    alert('Блокировка включена'); lockRender();
}
async function changeLockPin(){
    const cur=prompt('Текущий пароль:'); if(cur===null) return;
    if(await sha256hex(cur||'')!==localStorage.getItem('lockHash')){ alert('Неверный пароль'); return; }
    const p=prompt('Новый пароль:'); if(!p||p.length<4){ alert('Минимум 4 символа'); return; }
    localStorage.setItem('lockHash',await sha256hex(p)); alert('Пароль изменён');
}
async function disableLock(){
    const cur=prompt('Введите пароль для отключения:'); if(cur===null) return;
    if(await sha256hex(cur||'')!==localStorage.getItem('lockHash')){ alert('Неверный пароль'); return; }
    ['lockOn','lockHash','lockBio','lockCred'].forEach(k=>localStorage.removeItem(k));
    alert('Блокировка выключена'); lockRender();
}
async function toggleLockBio(){
    if(bioOn()){ localStorage.removeItem('lockBio'); localStorage.removeItem('lockCred'); lockRender(); return; }
    if(await bioRegister()){ localStorage.setItem('lockBio','1'); alert('Разблокировка по Face ID / отпечатку включена'); }
    else alert('Биометрия недоступна на этом устройстве/браузере');
    lockRender();
}
async function bioRegister(){
    if(!window.PublicKeyCredential) return false;
    try{ const cred=await navigator.credentials.create({publicKey:{
        challenge:crypto.getRandomValues(new Uint8Array(32)), rp:{name:'Payom'},
        user:{id:crypto.getRandomValues(new Uint8Array(16)),name:'payom',displayName:'Payom'},
        pubKeyCredParams:[{type:'public-key',alg:-7},{type:'public-key',alg:-257}],
        authenticatorSelection:{authenticatorAttachment:'platform',userVerification:'required'}, timeout:60000
    }}); localStorage.setItem('lockCred',_b64(cred.rawId)); return true;
    }catch(e){ return false; }
}
async function bioAuth(){
    const id=localStorage.getItem('lockCred'); if(!id||!window.PublicKeyCredential) return false;
    try{ await navigator.credentials.get({publicKey:{
        challenge:crypto.getRandomValues(new Uint8Array(32)),
        allowCredentials:[{type:'public-key',id:_unb64(id)}], userVerification:'required', timeout:60000
    }}); return true;
    }catch(e){ return false; }
}
function showLock(){
    if(!lockOn()) return;
    window._locked=true;
    const pin=document.getElementById('lockPin'); if(pin)pin.value=''; document.getElementById('lockErr').textContent='';
    document.getElementById('lockScreen').style.display='flex';
    document.getElementById('lockBioBtn').style.display=bioOn()?'flex':'none';
    if(bioOn()) setTimeout(tryUnlockBio,350);
}
function hideLock(){ window._locked=false; document.getElementById('lockScreen').style.display='none'; }
async function tryUnlockPin(){
    const v=document.getElementById('lockPin').value;
    if(await sha256hex(v||'')===localStorage.getItem('lockHash')) hideLock();
    else { document.getElementById('lockErr').textContent='Неверный пароль'; document.getElementById('lockPin').value=''; }
}
async function tryUnlockBio(){ if(await bioAuth()) hideLock(); }
document.addEventListener('visibilitychange',()=>{
    if(document.visibilityState==='hidden'){ if(lockOn()) window._locked=true; }
    else if(lockOn() && window._locked){ showLock(); }
});

/* старт */
// ===== Фикс клавиатуры (iPhone/Android): подгоняем высоту под видимую область =====
(function(){
    const root=document.documentElement;
    const vv=window.visualViewport;
    if(!vv){ root.style.setProperty('--app-h','100dvh'); root.style.setProperty('--vv-top','0px'); return; }
    function fit(){
        // реальная видимая высота = высота visualViewport (без клавиатуры)
        const h=Math.round(vv.height);
        root.style.setProperty('--app-h', h+'px');
        root.style.setProperty('--vv-top', Math.round(vv.offsetTop)+'px');
        // клавиатура открыта? тогда убрать нижний отступ safe-area (иначе зазор над клавиатурой)
        const kbOpen = (window.innerHeight - h) > 120;
        root.style.setProperty('--kb-safe', kbOpen ? '0px' : 'env(safe-area-inset-bottom)');
    }
    fit();
    vv.addEventListener('resize', fit);
    vv.addEventListener('scroll', fit);
    // при открытии клавиатуры в чате — прокрутить к последнему сообщению
    vv.addEventListener('resize', function(){
        const sc=document.getElementById('scChat');
        if(sc && sc.classList.contains('show')){ const m=document.getElementById('msgsArea'); if(m) setTimeout(()=>{ m.scrollTop=m.scrollHeight; }, 60); }
    });
    // когда фокусируешься на поле ввода — тоже прокрутить вниз
    document.addEventListener('focusin', function(e){
        if(e.target && (e.target.tagName==='TEXTAREA' || e.target.tagName==='INPUT')){
            const sc=document.getElementById('scChat');
            if(sc && sc.classList.contains('show')){ const m=document.getElementById('msgsArea'); if(m) setTimeout(()=>{ m.scrollTop=m.scrollHeight; }, 250); }
        }
    });
})();
(async function(){
    if(lockOn()) showLock();
    applyPrefs();
    updSendBtn();
    await ensureE2E(); // дождись загрузки ключей перед всем остальным!
    loadChats();
    loadStories();
    setInterval(loadStories, 60000);
    api('profile_get').then(r=>{ if(r.profile&&r.profile.avatar) document.getElementById('myAva').innerHTML=`<img src="${r.profile.avatar}">`; });
    listPoll=setInterval(()=>{ if(!curChat) loadChats(); },5000);
    // ===== Открытие по ссылке (сообщение / профиль) =====
    handleDeepLink();
})();
async function handleDeepLink(){
    const q=new URLSearchParams(location.search);
    const mid=q.get('m'), uid=q.get('user'), uname=q.get('u'), spack=q.get('stickers');
    if(!mid && !uid && !uname && !spack) return;
    // чистим адрес, чтобы при обновлении не открывалось снова
    try{ history.replaceState(null,'',location.pathname); }catch(e){}
    if(spack){
        const r=await api('sticker_pack_get&slug='+encodeURIComponent(spack));
        if(r&&r.pack){ if(r.pack.added){ toast('Набор «'+r.pack.title+'» уже у вас'); } else if(confirm('Добавить набор стикеров «'+r.pack.title+'» ('+((r.pack.stickers||[]).length)+' шт.)?')){ await api('sticker_pack_add','POST',{slug:r.pack.slug}); toast('Набор добавлен'); } }
        else toast('Набор не найден');
        return;
    }
    if(mid){
        const r=await api('msg_locate&id='+encodeURIComponent(mid));
        if(r&&r.ok){ openChat(r.chat_id,r.type,r.peer_id,r.title,r.avatar||''); setTimeout(()=>scrollToMsg(+mid),800); }
        else toast('Сообщение недоступно');
    } else if(uid){
        openUserProfile(+uid);
    } else if(uname){
        const r=await api('uid_by_username&u='+encodeURIComponent(uname));
        if(r&&r.id) openUserProfile(r.id); else toast('Пользователь не найден');
    }
}
</script>

<!-- Звонок (WebRTC, твой TURN) -->
<script>
/* ==== МГНОВЕННАЯ ДОСТАВКА: подключение к серверу реального времени ====
   Если адрес не задан — блок ничего не делает, работает прежний опрос. */
window.WS_URL = '<?= addslashes(WS_URL) ?>';
window.WS_TOKEN = '<?= addslashes($_COOKIE['qaz_r'] ?? '') ?>';
(function(){
'use strict';
if (!window.WS_URL || !window.WS_TOKEN) return;

var sock = null, tries = 0, alive = null, closing = false;

function connect(){
    if (closing) return;
    try { sock = new WebSocket(window.WS_URL + '?token=' + encodeURIComponent(window.WS_TOKEN)); }
    catch(e){ retry(); return; }

    sock.onopen = function(){
        tries = 0;
        window._wsOn = true;
        /* пока соединение живо, опрос сервера не нужен */
        try { if (window.msgPoll) { clearInterval(window.msgPoll); window.msgPoll = null; } } catch(e){}
        /* держим соединение живым */
        if (alive) clearInterval(alive);
        alive = setInterval(function(){
            if (sock && sock.readyState === 1) sock.send('{"type":"ping"}');
        }, 25000);
        /* подписываемся на открытый чат */
        if (window.curChat) subscribe(window.curChat);
    };

    sock.onmessage = function(ev){
        var m;
        try { m = JSON.parse(ev.data); } catch(e){ return; }

        if (m.type === 'message' && m.chat_id) {
            if (window.curChat === m.chat_id) {
                var box = document.getElementById('msgsArea');
                if (box) box.dataset.sig = '';
                if (typeof loadMsgs === 'function') loadMsgs(false);
            } else if (typeof loadChats === 'function' && !window.curChat) loadChats();
        }
        else if (m.type === 'channel_post') {
            if (window.curCh && typeof loadPosts === 'function') {
                var f = document.getElementById('chFeed'); if (f) f.dataset.sig = '';
                loadPosts();
            }
        }
        else if (m.type === 'typing' && window.curChat === m.chat_id) {
            var sub = document.getElementById('chatSub');
            if (sub) {
                sub.innerHTML = '<span class="typing">' + (m.name || '') + ' печатает…</span>';
                clearTimeout(window._typTm);
                window._typTm = setTimeout(function(){ if (typeof loadMsgs === 'function') loadMsgs(false); }, 4000);
            }
        }
    };

    sock.onclose = function(){ window._wsOn = false; retry(); };
    sock.onerror = function(){ try { sock.close(); } catch(e){} };
}

function retry(){
    if (closing) return;
    tries++;
    if (tries > 12) return;                       // сдались — остаётся обычный опрос
    var wait = Math.min(30000, 1000 * Math.pow(1.6, tries));
    setTimeout(connect, wait);
}

function subscribe(chatId){
    if (sock && sock.readyState === 1)
        sock.send(JSON.stringify({ type: 'subscribe', chat_id: chatId }));
}
window.wsSubscribe = subscribe;

/* при открытии чата подписываемся на его комнату */
if (typeof openChat === 'function') {
    var _oc = openChat;
    window.openChat = function(id){
        var r = _oc.apply(this, arguments);
        subscribe(id);
        return r;
    };
}

/* вернулись в приложение — если связь оборвалась, поднимаем заново */
document.addEventListener('visibilitychange', function(){
    if (document.visibilityState === 'visible' && (!sock || sock.readyState > 1)) { tries = 0; connect(); }
});

window.addEventListener('beforeunload', function(){ closing = true; if (sock) try { sock.close(); } catch(e){} });

connect();
})();
</script>
<script>window.CALL_CFG = { role: 'user', myId: <?= $ME ?>, url: 'messenger.php', app: 'messenger' };</script>
<script src="mcall.js">
/* PAYOM-UPDATE-v2 */
(function(){
'use strict';
var pingOk=true, idleSteps=0, lastUnread=-1, smartTimer=null;
function pollDelay(){ if(idleSteps>24)return 8000; if(idleSteps>8)return 5000; return 2500; }
async function smartTick(){
    if(document.hidden) return;
    if(!pingOk){ try{ if(window.curChat) await loadMsgs(false); else await loadChats(); }catch(e){} return; }
    try{
        var r=await api('ping'+(window.curChat?'&chat='+window.curChat:''));
        if(!r||r.error==='unknown'){ pingOk=false; return; }
        var changed=false;
        if(window.curChat&&typeof r.last==='number'&&r.last>(window.seenMaxId||0)){ await loadMsgs(false); changed=true; }
        if(typeof r.unread==='number'&&r.unread!==lastUnread){ lastUnread=r.unread; if(!window.curChat) await loadChats(); changed=true; }
        if(window.curChat&&r.typing){ await loadMsgs(false); changed=true; }
        idleSteps=changed?0:idleSteps+1;
    }catch(e){}
}
function startSmart(){ if(smartTimer)clearTimeout(smartTimer);
    (function loop(){ smartTimer=setTimeout(async function(){ await smartTick(); loop(); },pollDelay()); })(); }
setTimeout(function(){
    try{ if(window.msgPoll){clearInterval(window.msgPoll);window.msgPoll=null;} }catch(e){}
    try{ if(window.listPoll){clearInterval(window.listPoll);window.listPoll=null;} }catch(e){}
    startSmart();
},1500);
if(typeof openChat==='function'){ var _oc=openChat; window.openChat=function(){ idleSteps=0;
    var res=_oc.apply(this,arguments);
    try{ if(window.msgPoll){clearInterval(window.msgPoll);window.msgPoll=null;} }catch(e){} return res; }; }
if(typeof closeChat==='function'){ var _cc=closeChat; window.closeChat=function(){ idleSteps=0; return _cc.apply(this,arguments); }; }
if(typeof sendMsg==='function'){ var _sm=sendMsg; window.sendMsg=function(){ idleSteps=0;
    if(navigator.vibrate){try{navigator.vibrate(8);}catch(e){}} return _sm.apply(this,arguments); }; }
document.addEventListener('visibilitychange',function(){
    if(document.visibilityState==='visible'){ idleSteps=0;
        try{ if(window.curChat) loadMsgs(false); else loadChats(); }catch(e){} }
});
window.scrollMsgsBottom=function(smooth){ var b=document.getElementById('msgsArea'); if(!b)return;
    if(smooth&&b.scrollTo)b.scrollTo({top:b.scrollHeight,behavior:'smooth'}); else b.scrollTop=b.scrollHeight; };
try{ var mo=new MutationObserver(function(ms){ ms.forEach(function(m){ m.addedNodes.forEach(function(n){
    if(n.nodeType!==1||!n.querySelectorAll)return;
    n.querySelectorAll('img').forEach(function(img){ if(img.dataset._fade)return; img.dataset._fade='1';
        if(img.complete)img.classList.add('img-ready');
        else img.addEventListener('load',function(){img.classList.add('img-ready');},{once:true}); });
}); }); }); mo.observe(document.body,{childList:true,subtree:true}); }catch(e){}
(function(){ var b=document.getElementById('msgsArea'); if(!b)return; var sy=0;
    b.addEventListener('touchstart',function(e){ sy=e.touches[0].clientY; },{passive:true});
    b.addEventListener('touchmove',function(e){ var i=document.getElementById('msgInput');
        if(e.touches[0].clientY-sy>60&&i&&document.activeElement===i)i.blur(); },{passive:true}); })();
(function(){
/* ===== Двойной тап = сердечко (как в Instagram) =====
   Ловим именно жест: два коротких касания подряд, без сдвига пальца.
   Защита от случайных срабатываний и от спама запросами. */
'use strict';

var REACT = '\u2764\uFE0F';
var busy = {};              // по каким сообщениям запрос уже летит
var lastFire = {};          // когда последний раз ставили реакцию
var tapTime = 0, tapId = 0, tapX = 0, tapY = 0;
var downX = 0, downY = 0, downT = 0, moved = false;

/* тап по этим элементам — не реакция, а их собственное действие */
function interactive(el){
    return !!el.closest('a,button,input,textarea,video,audio,.vplay,.vwave,.reax,.reactions,.sticker,.rbtn,.media-wrap');
}

function onDown(e){
    var t = e.touches ? e.touches[0] : e;
    downX = t.clientX; downY = t.clientY; downT = Date.now(); moved = false;
}
function onMove(e){
    var t = e.touches ? e.touches[0] : e;
    if (Math.abs(t.clientX - downX) > 12 || Math.abs(t.clientY - downY) > 12) moved = true;
}
function onUp(e){
    if (moved || Date.now() - downT > 400) return;      // это была прокрутка или долгое нажатие
    var t = e.changedTouches ? e.changedTouches[0] : e;
    var el = document.elementFromPoint(t.clientX, t.clientY);
    if (!el || interactive(el)) return;

    var box = el.closest('.m[data-id]') || el.closest('.ch-post[data-pid]');
    if (!box) return;

    var isPost = box.classList.contains('ch-post');
    var id = isPost ? +box.dataset.pid : +box.dataset.id;
    var now = Date.now();

    var near = Math.abs(t.clientX - tapX) < 40 && Math.abs(t.clientY - tapY) < 40;
    if (id === tapId && now - tapTime < 320 && near) {
        tapTime = 0; tapId = 0;
        fire(box, id, isPost, t.clientX, t.clientY);
    } else {
        tapTime = now; tapId = id; tapX = t.clientX; tapY = t.clientY;
    }
}

function fire(box, id, isPost, x, y){
    var key = (isPost ? 'p' : 'm') + id;
    if (busy[key]) return;                              // запрос уже летит
    if (Date.now() - (lastFire[key] || 0) < 1200) return;   // не чаще раза в 1.2 сек
    lastFire[key] = Date.now();
    busy[key] = true;

    burst(x, y);                                        // сердце сразу, не ждём сервер
    if (navigator.vibrate) { try { navigator.vibrate(14); } catch(_){} }
    box.classList.add('liked');
    setTimeout(function(){ box.classList.remove('liked'); }, 420);

    var done = function(){ busy[key] = false; };
    try {
        if (isPost && typeof reactPost === 'function') Promise.resolve(reactPost(id, REACT)).then(done, done);
        else if (!isPost && typeof quickReact === 'function') Promise.resolve(quickReact(id, REACT)).then(done, done);
        else done();
    } catch (err) { done(); }
}

/* Крупное сердце в точке касания */
function burst(x, y){
    var h = document.createElement('div');
    h.className = 'heart-pop';
    h.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 21s-7.5-4.7-9.6-9C.9 8.6 2.4 5 5.8 5c2 0 3.4 1.1 4.2 2.3C10.8 6.1 12.2 5 14.2 5c3.4 0 4.9 3.6 3.4 7-2.1 4.3-9.6 9-9.6 9z"/></svg>';
    h.style.left = (x - 44) + 'px';
    h.style.top  = (y - 44) + 'px';
    document.body.appendChild(h);
    setTimeout(function(){ h.remove(); }, 900);
}

/* вешаем один раз на весь документ — работает и в чате, и в канале */
document.addEventListener('touchstart', onDown, { passive: true });
document.addEventListener('touchmove',  onMove, { passive: true });
document.addEventListener('touchend',   onUp,   { passive: true });
document.addEventListener('mousedown',  onDown);
document.addEventListener('mousemove',  onMove);
document.addEventListener('mouseup',    onUp);
})();
(function(){ var b=document.getElementById('msgsArea'); if(!b||!b.parentElement)return;
    var t=document.createElement('button'); t.id='scrollDownBtn';
    t.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M19 12l-7 7-7-7"/></svg>';
    t.onclick=function(){ scrollMsgsBottom(true); };
    b.parentElement.appendChild(t);
    b.addEventListener('scroll',function(){ t.classList.toggle('show', b.scrollHeight-b.scrollTop-b.clientHeight>400); },{passive:true}); })();
})();
/* конец PAYOM-UPDATE-v2 */
</script>
<?= face_module() ?>
<script>

/* PAYOM-CHANNELS */
/* ==== PAYOM-CHANNELS: интерфейс ==== */
(function(){
'use strict';

var curCh = null;          // текущий открытый канал
var chAdmin = false;
var chPoll = null;
var seenPosts = {};

/* ------------------------------------------------------------------
   Экран канала — создаём один раз
   ------------------------------------------------------------------ */
function buildScreen(){
    if (document.getElementById('scChannel')) return;
    var s = document.createElement('div');
    s.className = 'screen'; s.id = 'scChannel';
    s.innerHTML =
    '<div class="top">' +
      '<button class="icon-btn" onclick="closeChannel()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button>' +
      '<div class="ava g" id="chAva" style="width:40px;height:40px;font-size:16px"></div>' +
      '<div style="flex:1;min-width:0;cursor:pointer" onclick="openChannelInfo()">' +
        '<h2 id="chTitle" style="font-size:16px">Канал</h2><div class="sub" id="chSub"></div></div>' +
      '<button class="icon-btn" onclick="openChannelInfo()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></svg></button>' +
    '</div>' +
    '<div id="chPinBar" style="display:none;align-items:center;gap:10px;padding:9px 14px;background:var(--panel);border-bottom:1px solid var(--line)">' +
      '<div style="width:3px;align-self:stretch;background:var(--blue);border-radius:2px"></div>' +
      '<div style="flex:1;min-width:0"><div style="color:var(--blue);font-size:12px;font-weight:800">Закреплённое</div>' +
      '<div id="chPinText" style="color:var(--sub);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"></div></div></div>' +
    '<div class="msgs" id="chFeed" style="padding:14px 12px"></div>' +
    '<div id="chSubBar" style="display:none;padding:12px 16px calc(14px + env(safe-area-inset-bottom));background:var(--panel);border-top:1px solid var(--line)">' +
      '<button class="st-btn" style="background:var(--blue);color:#fff;margin:0" onclick="subChannel()">Подписаться</button></div>' +
    '<div id="chComposer" class="composer" style="display:none">' +
      '<input type="file" id="chFile" accept="image/*,video/*" style="display:none" onchange="chPickFile(this)">' +
      '<button class="cbtn" onclick="document.getElementById(\'chFile\').click()">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.6"/><path d="M21 15l-5-5L5 21"/></svg></button>' +
      '<textarea id="chInput" rows="1" placeholder="Написать в канал"></textarea>' +
      '<button class="send" onclick="publishPost()">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg></button></div>' +
    '<div id="chPrev" style="display:none;padding:8px 14px;font-size:12.5px;font-weight:700;color:var(--blue);background:var(--panel)"></div>';
    document.body.appendChild(s);

    var inp = document.getElementById('chInput');
    inp.addEventListener('input', function(){ inp.style.height='auto'; inp.style.height=Math.min(110,inp.scrollHeight)+'px'; });
}

/* ------------------------------------------------------------------
   Открыть канал
   ------------------------------------------------------------------ */
window.openChannel = async function(id){
    buildScreen();
    curCh = id; seenPosts = {};
    /* Кэш ленты: при повторном заходе публикации видны сразу,
       свежие подтянутся фоном и заменят содержимое */
    var _cf = document.getElementById('chFeed');
    var _cc = window._postCache && window._postCache[id];
    if (_cc) { _cf.innerHTML = _cc.html; _cf.dataset.sig = _cc.sig || ''; }
    else { _cf.innerHTML = '<div class="hint">Загрузка…</div>'; _cf.dataset.sig = ''; }
    document.getElementById('scChannel').classList.add('show');

    /* название и аватарку берём из кэша списка — шапка не мигает */
    var _hint = window._chHint && window._chHint[id];
    if (_hint) {
        document.getElementById('chTitle').innerHTML = esc(_hint.title) + (_hint.official ? VBADGE : '');
        document.getElementById('chAva').innerHTML = _hint.avatar ? '<img src="' + _hint.avatar + '">' : esc((_hint.title||'К').charAt(0).toUpperCase());
    }

    var r = await api('channel_get&id=' + id);
    if (!r || !r.ok) { toast('Канал не найден'); closeChannel(); return; }
    var c = r.channel;
    chAdmin = !!c.is_admin;
    window._curChData = c;

    document.getElementById('chTitle').innerHTML = esc(c.title) + (c.official ? VBADGE : '');
    document.getElementById('chSub').textContent = c.subs + ' подписчик(ов)' + (c.official ? '' : (c.is_public ? '' : ' · закрытый'));
    document.getElementById('chAva').innerHTML = c.avatar ? '<img src="' + c.avatar + '">' : esc((c.title||'К').charAt(0).toUpperCase());

    document.getElementById('chComposer').style.display = chAdmin ? 'flex' : 'none';
    document.getElementById('chSubBar').style.display  = (!c.subscribed && !chAdmin) ? 'block' : 'none';

    await loadPosts();
    if (chPoll) clearInterval(chPoll);
    chPoll = setInterval(function(){ if (!document.hidden && curCh) loadPosts(); }, 6000);
};

window.closeChannel = function(){
    var s = document.getElementById('scChannel');
    if (s) s.classList.remove('show');
    curCh = null;
    if (chPoll) { clearInterval(chPoll); chPoll = null; }
    if (typeof loadChats === 'function') loadChats();
};

/* ------------------------------------------------------------------
   Лента постов
   ------------------------------------------------------------------ */
async function loadPosts(){
    if (!curCh) return;
    // Анти-наложение: не запускаем параллельную загрузку ленты канала.
    if (window._postsBusy) { window._postsPending = true; return; }
    window._postsBusy = true;
    try {
    var r = await api('channel_posts&channel=' + curCh);
    if (!r || !r.ok) return;
    var box = document.getElementById('chFeed');
    if (!box) return;

    var sig = JSON.stringify(r.posts.map(function(p){ return [p.id, p.views, (p.reactions||[]).length]; }));
    if (sig === box.dataset.sig) return;
    box.dataset.sig = sig;
    window._chCommentsOn = (r.comments_on !== 0);

    if (!r.posts.length) {
        box.innerHTML = '<div class="hint">' + (r.is_admin
            ? 'Канал пуст.<br>Напишите первый пост внизу.'
            : 'В канале пока нет публикаций.') + '</div>';
        return;
    }

    box.innerHTML = r.posts.map(function(p){ return postHtml(p, r.is_admin, r.pinned_post); }).join('');
    box.scrollTop = box.scrollHeight;
    /* запоминаем ленту — следующий заход будет мгновенным */
    window._postCache = window._postCache || {};
    window._postCache[curCh] = { html: box.innerHTML, sig: sig };
    var _pk = Object.keys(window._postCache);
    if (_pk.length > 8) delete window._postCache[_pk[0]];

    // закреплённое
    var pinBar = document.getElementById('chPinBar');
    var pin = r.posts.filter(function(p){ return p.id === r.pinned_post; })[0];
    if (pin) {
        pinBar.style.display = 'flex';
        document.getElementById('chPinText').textContent = pin.text || 'Медиа';
    } else pinBar.style.display = 'none';

    // засчитать просмотры
    var fresh = r.posts.filter(function(p){ return !seenPosts[p.id]; }).map(function(p){ seenPosts[p.id]=1; return p.id; });
    if (fresh.length) api('channel_view', 'POST', { posts: fresh });
    } finally {
        window._postsBusy = false;
        if (window._postsPending) { window._postsPending = false; loadPosts(); }
    }
}

function postHtml(p, isAdmin, pinnedId){
    var body = '';
    if (p.type === 'image' && p.file)
        body += '<div class="media-wrap" style="max-width:100%" onclick="openImg(\'' + p.file + '\')"><img src="' + p.file + '" loading="lazy" onload="this.classList.add(\'loaded\')"></div>';
    else if (p.type === 'video' && p.file)
        body += '<video src="' + p.file + '" controls playsinline style="width:100%;border-radius:12px;display:block"></video>';
    else if (p.type === 'audio' && p.file)
        body += '<audio src="' + p.file + '" controls style="width:100%"></audio>';
    else if (p.type === 'file' && p.file)
        body += '<a href="' + p.file + '" download style="color:var(--blue);font-weight:700;text-decoration:none">📎 ' + esc(p.filename||'Файл') + '</a>';

    if (p.text) body += (body ? '<div style="margin-top:8px"></div>' : '') +
        (typeof linkify === 'function' ? linkify(p.text) : esc(p.text));

    var reacts = CH_REAX.map(function(e){
        var r = (p.reactions||[]).filter(function(x){ return x.emoji === e; })[0];
        var cnt = r ? r.cnt : 0;
        var mine = r && r.mine;
        if (!cnt && !isAdmin) return '';       // подписчикам показываем только использованные + все при тапе
        return '<span class="ch-react' + (mine ? ' mine' : '') + '" onclick="reactPost(' + p.id + ',\'' + e + '\')">' +
               e + (cnt ? ' ' + cnt : '') + '</span>';
    }).join('');

    var used = (p.reactions||[]).map(function(x){
        return '<span class="ch-react' + (x.mine ? ' mine' : '') + '" onclick="reactPost(' + p.id + ',\'' + x.emoji + '\')">' + x.emoji + ' ' + x.cnt + '</span>';
    }).join('');

    var admin = isAdmin
        ? '<button class="ch-act" onclick="pinPost(' + p.id + ')">' + (p.id === pinnedId ? 'Открепить' : 'Закрепить') + '</button>' +
          '<button class="ch-act del" onclick="delPost(' + p.id + ')">Удалить</button>'
        : '';

    return '<div class="ch-post" id="p' + p.id + '" data-pid="' + p.id + '">' +
        '<div class="ch-body">' + body + '</div>' +
        '<div class="ch-meta">' +
            '<span class="ch-views"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/></svg>' + (p.views||0) + '</span>' +
            '<span>' + (typeof hhmm === 'function' ? hhmm(p.ts) : '') + '</span>' +
        '</div>' +
        '<div class="ch-reacts">' + (used || '') +
            '<span class="ch-addreact" onclick="showReactBar(' + p.id + ',this)">+</span>' +
            (window._chCommentsOn ? '<span class="ch-cmt" onclick="openComments(' + p.id + ')">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 01-9 8.4 8.6 8.6 0 01-3.8-.9L3 21l2-4.9A8.4 8.4 0 0112 3a8.4 8.4 0 019 8.5z"/></svg>' +
                (p.cmt > 0 ? p.cmt : '') + '</span>' : '') + '</div>' +
        (admin ? '<div class="ch-acts">' + admin + '</div>' : '') +
    '</div>';
}

var CH_REAX = ['❤️','👍','🔥','😂','😍','😢','👎'];

window.showReactBar = function(pid, el){
    var old = document.getElementById('chReactBar');
    if (old) old.remove();
    var bar = document.createElement('div');
    bar.id = 'chReactBar';
    bar.className = 'ch-reactbar';
    bar.innerHTML = CH_REAX.map(function(e){
        return '<span onclick="reactPost(' + pid + ',\'' + e + '\');document.getElementById(\'chReactBar\').remove()">' + e + '</span>';
    }).join('');
    el.parentElement.appendChild(bar);
    setTimeout(function(){
        document.addEventListener('click', function once(ev){
            if (!ev.target.closest('#chReactBar') && !ev.target.closest('.ch-addreact')) {
                var b = document.getElementById('chReactBar'); if (b) b.remove();
                document.removeEventListener('click', once);
            }
        });
    }, 10);
};

var _pxBusy = {};
window.reactPost = async function(pid, emoji){
    if (_pxBusy[pid]) return;                  // запрос уже летит — второй не шлём
    _pxBusy[pid] = 1;
    if (navigator.vibrate) { try { navigator.vibrate(10); } catch(e){} }
    try {
        await api('channel_react', 'POST', { post: pid, emoji: emoji });
        var box = document.getElementById('chFeed'); if (box) box.dataset.sig = '';
        await loadPosts();
    } catch(e){}
    finally { setTimeout(function(){ delete _pxBusy[pid]; }, 400); }
};
window.pinPost = async function(pid){
    var cur = window._curChData || {};
    await api('channel_pin', 'POST', { channel: curCh, post: (cur.pinned_post === pid ? 0 : pid) });
    cur.pinned_post = (cur.pinned_post === pid ? 0 : pid);
    var box = document.getElementById('chFeed'); if (box) box.dataset.sig = '';
    loadPosts();
};
window.delPost = async function(pid){
    if (!confirm('Удалить публикацию?')) return;
    await api('channel_post_delete', 'POST', { post: pid });
    var box = document.getElementById('chFeed'); if (box) box.dataset.sig = '';
    loadPosts();
};

/* ------------------------------------------------------------------
   Публикация
   ------------------------------------------------------------------ */
var chPending = null;
window.chPickFile = function(inp){
    var f = inp.files[0]; if (!f) return;
    if (f.size > 20 * 1024 * 1024) { alert('Файл больше 20 МБ'); inp.value=''; return; }
    chPending = f;
    var p = document.getElementById('chPrev');
    p.style.display = 'block';
    p.innerHTML = esc(f.name) + ' <span style="color:#FF6B6B;cursor:pointer" onclick="chClearFile()">✕</span>';
};
window.chClearFile = function(){
    chPending = null;
    document.getElementById('chFile').value = '';
    document.getElementById('chPrev').style.display = 'none';
};
window.publishPost = async function(){
    var ta = document.getElementById('chInput');
    var text = ta.value.trim();
    if (!text && !chPending) return;
    var delay = 0;
    if (window._chDelay) { delay = window._chDelay; window._chDelay = 0; }

    var fd = new FormData();
    fd.append('channel', curCh); fd.append('text', text);
    if (chPending) fd.append('file', chPending);
    if (delay) fd.append('delay_min', delay);

    ta.value = ''; ta.style.height = 'auto'; chClearFile();
    var r = await fetch('messenger.php?action=channel_post', { method:'POST', body:fd }).then(function(x){return x.json();}).catch(function(){return {};});
    if (r && r.ok) {
        if (r.scheduled) toast('Опубликуется позже');
        else { if (typeof playSnd === 'function') playSnd('send');
               var box = document.getElementById('chFeed'); if (box) box.dataset.sig = ''; loadPosts(); }
    } else toast('Не удалось опубликовать');
};

/* ------------------------------------------------------------------
   Информация о канале
   ------------------------------------------------------------------ */
window.openChannelInfo = async function(){
    var r = await api('channel_get&id=' + curCh);
    if (!r || !r.ok) return;
    var c = r.channel;

    var sheet = document.getElementById('chInfoSheet');
    if (!sheet) {
        sheet = document.createElement('div');
        sheet.id = 'chInfoSheet';
        sheet.style.cssText = 'display:none;position:fixed;inset:0;z-index:260;background:var(--bg);overflow-y:auto';
        document.body.appendChild(sheet);
    }

    var link = baseUrl() + (c.username ? '?ch=' + c.username : '?joinch=' + (c.invite||''));
    var h =
    '<div class="top"><button class="icon-btn" onclick="document.getElementById(\'chInfoSheet\').style.display=\'none\'">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button><h2>О канале</h2></div>' +
    '<div style="text-align:center;padding:26px 20px 18px;background:var(--panel)">' +
      '<div style="position:relative;width:120px;height:120px;margin:0 auto 12px">' +
        '<div class="ava g" style="width:120px;height:120px;font-size:48px">' +
          (c.avatar ? '<img src="' + c.avatar + '">' : esc((c.title||'К').charAt(0).toUpperCase())) + '</div>' +
        (c.is_admin ? '<button onclick="document.getElementById(\'chAvaFile\').click()" style="position:absolute;right:0;bottom:0;width:36px;height:36px;border-radius:50%;border:3px solid var(--panel);background:var(--blue);color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="17" height="17"><circle cx="12" cy="13" r="4"/><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/></svg></button>' : '') +
      '</div>' +
      '<div style="font-size:21px;font-weight:800">' + esc(c.title) + (c.official ? VBADGE : '') + '</div>' +
      (c.username ? '<div style="color:var(--blue);font-size:14px;font-weight:700;margin-top:3px">@' + esc(c.username) + '</div>' : '') +
      '<div style="color:var(--sub);font-size:13px;font-weight:600;margin-top:4px">' + c.subs + ' подписчик(ов)' + (c.is_public ? '' : ' · закрытый') + '</div>' +
      (c.about ? '<div style="color:var(--sub);font-size:14px;margin-top:10px">' + esc(c.about) + '</div>' : '') +
    '</div>' +
    '<input type="file" id="chAvaFile" accept="image/*" style="display:none" onchange="uploadChAvatar(this)">' +
    '<div style="padding:14px 16px 40px;background:var(--panel);margin-top:12px">';

    if (c.is_admin) {
        h += '<button class="st-btn" style="background:var(--blue);color:#fff" onclick="shareChannel(\'' + link.replace(/'/g,"\\'") + '\')">Поделиться · ссылка и QR</button>';
        h += '<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="editChannel()">Изменить название и описание</button>';
        h += '<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="showSubs()">Подписчики</button>';
        h += '<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="schedulePost()">Отложенная публикация</button>';
        h += '<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="toggleComments()">' +
             (c.comments_on === 0 ? 'Включить комментарии' : 'Отключить комментарии') + '</button>';
    } else {
        h += '<button class="st-btn" style="background:var(--blue);color:#fff" onclick="shareChannel(\'' + link.replace(/'/g,"\\'") + '\')">Поделиться каналом</button>';
    }
    h += '<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="muteChannel(' + (c.muted?0:1) + ')">' +
         (c.muted ? 'Включить уведомления' : 'Выключить уведомления') + '</button>';
    if (c.official)
        h += '<div style="margin-top:10px;padding:12px 14px;background:rgba(124,92,255,.1);border:1px solid rgba(124,92,255,.28);border-radius:13px;font-size:13px;color:var(--sub);line-height:1.5">Это официальный канал Payom. Здесь публикуются обновления и важные объявления. Отписаться нельзя, но уведомления можно выключить.</div>';
    else if (c.subscribed && c.role !== 'owner')
        h += '<button class="st-btn" style="background:#3A2226;color:#FF6B6B" onclick="unsubChannel()">Отписаться</button>';
    h += '</div><div id="chSubsList"></div>';

    sheet.innerHTML = h;
    sheet.style.display = 'block';
};

window.uploadChAvatar = async function(inp){
    var f = inp.files[0]; if (!f) return;
    var fd = new FormData(); fd.append('channel', curCh); fd.append('file', f);
    var r = await fetch('messenger.php?action=channel_avatar', { method:'POST', body:fd }).then(function(x){return x.json();}).catch(function(){return {};});
    if (r && r.avatar) { openChannelInfo(); openChannel(curCh); } else toast('Не удалось загрузить');
    inp.value = '';
};
window.editChannel = async function(){
    var c = window._curChData || {};
    var t = prompt('Название канала:', c.title || ''); if (t === null) return;
    var a = prompt('Описание:', c.about || '');
    var r = await api('channel_edit', 'POST', { channel: curCh, title: t.trim(), about: (a||'').trim() });
    if (r && r.ok) { toast('Сохранено'); openChannelInfo(); openChannel(curCh); }
    else toast((r && r.error) || 'Ошибка');
};
window.muteChannel = async function(v){
    await api('channel_mute', 'POST', { channel: curCh, val: v });
    toast(v ? 'Уведомления выключены' : 'Уведомления включены');
    openChannelInfo();
};
window.unsubChannel = async function(){
    if (!confirm('Отписаться от канала?')) return;
    await api('channel_unsub', 'POST', { channel: curCh });
    document.getElementById('chInfoSheet').style.display = 'none';
    closeChannel();
};
window.subChannel = async function(){
    var r = await api('channel_sub', 'POST', { channel: curCh });
    if (r && r.ok) { toast('Вы подписались'); openChannel(curCh); }
    else toast('Не удалось подписаться');
};
window.showSubs = async function(){
    var r = await api('channel_subs&channel=' + curCh);
    var box = document.getElementById('chSubsList');
    if (!r || !r.ok) { box.innerHTML = '<div class="hint">Нет доступа</div>'; return; }
    box.innerHTML = '<div class="st-h">Подписчики (' + r.subs.length + ')</div><div style="background:var(--panel)">' +
        r.subs.map(function(s){
            var role = s.role === 'owner' ? 'владелец' : (s.role === 'admin' ? 'админ' : '');
            return '<div class="row">' + (typeof avaHtml === 'function' ? avaHtml(s.name, s.avatar, '') : '') +
                   '<div class="row-main"><div class="row-name">' + esc(s.name) + '</div>' +
                   '<div class="row-last">' + role + '</div></div></div>';
        }).join('') + '</div>';
};
window.schedulePost = function(){
    var m = prompt('Через сколько минут опубликовать? (например 60)');
    if (!m) return;
    window._chDelay = Math.max(1, parseInt(m) || 0);
    document.getElementById('chInfoSheet').style.display = 'none';
    toast('Следующий пост выйдет через ' + window._chDelay + ' мин');
    document.getElementById('chInput').focus();
};

/* ------------------------------------------------------------------
   Ссылка и QR-код
   ------------------------------------------------------------------ */
window.shareChannel = function(link){
    copyText(link);
    var ov = document.getElementById('qrOv');
    if (!ov) {
        ov = document.createElement('div');
        ov.id = 'qrOv';
        ov.style.cssText = 'display:none;position:fixed;inset:0;z-index:300;background:rgba(0,0,0,.7);align-items:center;justify-content:center;padding:24px';
        ov.onclick = function(e){ if (e.target === ov) ov.style.display='none'; };
        document.body.appendChild(ov);
    }
    ov.innerHTML =
        '<div style="background:#fff;border-radius:22px;padding:24px;text-align:center;max-width:320px;width:100%">' +
        '<div id="qrBox" style="display:flex;justify-content:center;margin-bottom:14px"></div>' +
        '<div style="color:#161320;font-size:13px;font-weight:700;word-break:break-all;margin-bottom:14px">' + esc(link) + '</div>' +
        '<div style="color:#6E6B82;font-size:12.5px;font-weight:600;margin-bottom:14px">Ссылка скопирована</div>' +
        '<button onclick="document.getElementById(\'qrOv\').style.display=\'none\'" style="width:100%;padding:13px;border:none;border-radius:12px;background:#7C5CFF;color:#fff;font-weight:800;font-size:15px;cursor:pointer;font-family:inherit">Закрыть</button></div>';
    ov.style.display = 'flex';

    function draw(){
        try {
            var qr = qrcode(0, 'M'); qr.addData(link); qr.make();
            document.getElementById('qrBox').innerHTML = qr.createImgTag(6, 8);
        } catch(e){ document.getElementById('qrBox').innerHTML = '<div style="color:#6E6B82;font-size:13px">QR недоступен</div>'; }
    }
    if (window.qrcode) draw();
    else {
        var s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.js';
        s.onload = draw;
        s.onerror = function(){ document.getElementById('qrBox').innerHTML = '<div style="color:#6E6B82;font-size:13px">QR недоступен, ссылка скопирована</div>'; };
        document.head.appendChild(s);
    }
};

/* ------------------------------------------------------------------
   Каналы в общем списке чатов
   ------------------------------------------------------------------ */
if (typeof loadChats === 'function') {
    var _lc = loadChats;
    window.loadChats = async function(){
        var res = await _lc.apply(this, arguments);
        try { await appendChannels(); } catch(e){}
        return res;
    };
}
async function appendChannels(){
    var si = document.getElementById('searchInput');
    if (si && si.value.trim().length >= 1) return;
    var r = await api('channel_list');
    if (!r || !r.channels || !r.channels.length) return;
    var list = document.getElementById('listArea'); if (!list) return;

    window._chHint = window._chHint || {};
    r.channels.forEach(function(c){ window._chHint[c.id] = { title: c.title, avatar: c.avatar, official: c.official }; });
    var old = document.getElementById('chListBlock'); if (old) old.remove();
    var box = document.createElement('div');
    box.id = 'chListBlock';
    box.innerHTML = r.channels.map(function(c){
        var av = c.avatar ? '<div class="ava g"><img src="' + c.avatar + '"></div>'
                          : '<div class="ava g">' + esc((c.title||'К').charAt(0).toUpperCase()) + '</div>';
        return '<div class="row" onclick="openChannel(' + c.id + ')">' + av +
            '<div class="row-main"><div class="row-top">' +
            '<div class="row-name">' + esc(c.title) + (c.official ? VBADGE : '') + (c.official ? '' : ' <span class="ch-tag">канал</span>') + '</div>' +
            '<div class="row-time">' + (typeof relTime==='function'?relTime(c.ts):'') + '</div></div>' +
            '<div class="row-bot"><div class="row-last">' + esc(c.last || 'Нет публикаций') + '</div>' +
            (c.unread ? '<div class="badge">' + c.unread + '</div>' : '') + '</div></div></div>';
    }).join('');
    list.insertBefore(box, list.firstChild);
}

/* ------------------------------------------------------------------
   Создать канал — пункт в меню «+»
   ------------------------------------------------------------------ */
(function(){
    var menu = null;   /* пункт меню теперь в HTML */
    if (!menu) return;
    var b = document.createElement('button');
    b.className = 'fab-ch';
    b.style.cssText = 'width:100%;display:flex;align-items:center;gap:14px;padding:14px 16px;background:none;border:none;color:var(--txt);font-size:15px;font-weight:700;cursor:pointer;font-family:inherit';
    b.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="var(--blue)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="22" height="22"><path d="M3 11l18-8-8 18-2-7-8-3z"/></svg>Создать канал';
    b.onclick = function(){ if (typeof window.createChannel === "function") window.createChannel(); };
    menu.appendChild(document.createElement('div')).style.cssText = 'height:1px;background:var(--line);margin:0 16px';
    menu.appendChild(b);
})();

window.createChannel = async function(){
    if (typeof closeFabMenu === 'function') closeFabMenu();
    var title = prompt('Название канала:'); if (!title || title.trim().length < 2) return;
    var isPub = confirm('Сделать канал публичным?\n\nОК — публичный (можно найти поиском)\nОтмена — закрытый (только по ссылке)');
    var uname = '';
    if (isPub) {
        uname = prompt('@username канала (латиница, от 4 символов):');
        if (!uname || uname.replace(/[^A-Za-z0-9_]/g,'').length < 4) { alert('Нужен @username от 4 символов'); return; }
    }
    var about = prompt('Описание (необязательно):') || '';
    var r = await api('channel_create', 'POST', { title: title.trim(), username: uname, about: about.trim(), public: isPub ? 1 : 0 });
    if (r && r.ok) { toast('Канал создан'); loadChats(); openChannel(r.id); }
    else toast((r && r.error) || 'Не удалось создать');
};

/* ------------------------------------------------------------------
   Каналы в поиске
   ------------------------------------------------------------------ */
(function(){
    var inp = document.getElementById('searchInput'); if (!inp) return;
    var t = null;
    inp.addEventListener('input', function(){
        clearTimeout(t);
        var q = inp.value.trim();
        if (q.length < 2) { var b = document.getElementById('chSearchRes'); if (b) b.remove(); return; }
        t = setTimeout(function(){ searchChannels(q); }, 400);
    });
})();
async function searchChannels(q){
    var r = await api('channel_search&q=' + encodeURIComponent(q));
    var list = document.getElementById('listArea'); if (!list) return;
    var old = document.getElementById('chSearchRes'); if (old) old.remove();
    if (!r || !r.channels || !r.channels.length) return;
    var box = document.createElement('div');
    box.id = 'chSearchRes';
    box.innerHTML = '<div style="padding:12px 16px 6px;font-size:12px;font-weight:800;color:var(--sub);text-transform:uppercase">Каналы</div>' +
        r.channels.map(function(c){
            var av = c.avatar ? '<div class="ava g"><img src="' + c.avatar + '"></div>'
                              : '<div class="ava g">' + esc((c.title||'К').charAt(0).toUpperCase()) + '</div>';
            return '<div class="row" onclick="document.getElementById(\'searchInput\').value=\'\';openChannel(' + c.id + ')">' + av +
                '<div class="row-main"><div class="row-name">' + esc(c.title) + '</div>' +
                '<div class="row-last">@' + esc(c.username||'') + ' · ' + c.subs_count + ' подписчик(ов)</div></div></div>';
        }).join('');
    list.appendChild(box);
}

/* ------------------------------------------------------------------
   Открытие по ссылке: ?ch=username или ?joinch=КОД
   ------------------------------------------------------------------ */
(function(){
    var q = new URLSearchParams(location.search);
    var un = q.get('ch'), code = q.get('joinch');
    if (!un && !code) return;
    try { history.replaceState(null, '', location.pathname); } catch(e){}
    setTimeout(async function(){
        var r = await api('channel_get' + (un ? '&u=' + encodeURIComponent(un) : '&code=' + encodeURIComponent(code)));
        if (!r || !r.ok) { toast('Канал не найден'); return; }
        var c = r.channel;
        if (c.subscribed) { openChannel(c.id); return; }
        if (!confirm('Подписаться на канал «' + c.title + '»?\nПодписчиков: ' + c.subs)) { if (c.can_see) openChannel(c.id); return; }
        var s = await api('channel_sub', 'POST', code ? { code: code } : { channel: c.id });
        if (s && s.ok) { toast('Вы подписались'); loadChats(); openChannel(c.id); }
        else toast('Не удалось подписаться');
    }, 1300);
})();

})();
</script>
<script>
/* PAYOM-PACK1 */
/* ==== PAYOM-PACK1: интерфейс (вставляется установщиком) ==== */
(function(){
'use strict';

/* ------------------------------------------------------------------
   1. ПЕРЕСЫЛКА СООБЩЕНИЯ
   ------------------------------------------------------------------ */

/* добавляем пункт «Переслать» в меню сообщения */
(function(){
    var menu = document.querySelector('#msgMenuOv > div');
    if (!menu || menu.querySelector('.mmi-fwd')) return;
    var btn = document.createElement('button');
    btn.className = 'mmi mmi-fwd';
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 17l5-5-5-5"/><path d="M20 12H9a4 4 0 00-4 4v2"/></svg> Переслать';
    btn.onclick = function(){ if (window.menuMsg) openForward(window.menuMsg.id); };
    var copyBtn = menu.querySelector('.mmi:nth-of-type(2)');
    if (copyBtn && copyBtn.parentElement) copyBtn.parentElement.insertBefore(btn, copyBtn.nextSibling);
    else menu.appendChild(btn);
})();

var fwdIds = [];
window.openForward = async function(msgId){
    fwdIds = [msgId];
    if (typeof closeMsgMenu === 'function') closeMsgMenu();

    var sheet = document.getElementById('fwdSheet');
    if (!sheet) {
        sheet = document.createElement('div');
        sheet.id = 'fwdSheet';
        sheet.style.cssText = 'display:none;position:fixed;inset:0;z-index:260;background:rgba(0,0,0,.5)';
        sheet.onclick = function(e){ if (e.target === sheet) sheet.style.display = 'none'; };
        sheet.innerHTML =
            '<div style="position:absolute;left:0;right:0;bottom:0;max-height:74vh;background:var(--bg);' +
            'border-radius:18px 18px 0 0;display:flex;flex-direction:column">' +
            '<div style="display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--line)">' +
            '<div style="font-weight:800;font-size:16px;flex:1">Переслать в…</div>' +
            '<button class="icon-btn" style="width:34px;height:34px" onclick="document.getElementById(\'fwdSheet\').style.display=\'none\'">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button></div>' +
            '<div id="fwdList" style="flex:1;overflow-y:auto"></div></div>';
        document.body.appendChild(sheet);
    }
    sheet.style.display = 'block';
    var box = document.getElementById('fwdList');
    box.innerHTML = '<div class="hint">Загрузка…</div>';

    var r = await api('chats');
    var chats = (r && r.chats) || [];
    if (!chats.length) { box.innerHTML = '<div class="hint">Нет чатов</div>'; return; }
    box.innerHTML = chats.map(function(c){
        var av = c.avatar_img
            ? '<div class="ava" style="width:44px;height:44px"><img src="' + c.avatar_img + '"></div>'
            : '<div class="ava ' + (c.type === 'group' ? 'g' : '') + '" style="width:44px;height:44px;font-size:17px">' +
              esc((c.title || '?').charAt(0).toUpperCase()) + '</div>';
        return '<div class="row" onclick="doForward(' + c.id + ')">' + av +
               '<div class="row-main"><div class="row-name">' + esc(c.title) + '</div>' +
               '<div class="row-last">' + (c.type === 'group' ? 'группа' : 'личный чат') + '</div></div></div>';
    }).join('');
};

window.doForward = async function(chatId){
    var s = document.getElementById('fwdSheet');
    if (s) s.style.display = 'none';
    var r = await api('forward', 'POST', { to: chatId, ids: fwdIds });
    if (r && r.ok && r.sent) {
        toast('Переслано');
        if (typeof playSnd === 'function') playSnd('send');
        if (window.curChat === chatId) { document.getElementById('msgsArea').dataset.sig = ''; loadMsgs(true); }
    } else toast('Не удалось переслать');
};

/* ------------------------------------------------------------------
   2. ЗАКРЕПИТЬ ЧАТ / АРХИВ  — кнопки в информации о чате
   ------------------------------------------------------------------ */
window._chatFlags = {};

if (typeof loadChats === 'function') {
    var _loadChats = loadChats;
    window.loadChats = async function(){
        var res = await _loadChats.apply(this, arguments);
        try { injectArchiveRow(); } catch(e){}
        return res;
    };
}

function injectArchiveRow(){
    var n = window._archivedCount || 0;
    var old = document.getElementById('archRow');
    if (old) old.remove();
    if (!n) return;
    var list = document.getElementById('listArea');
    if (!list) return;
    var row = document.createElement('div');
    row.id = 'archRow';
    row.className = 'row';
    row.onclick = openArchive;
    row.innerHTML =
        '<div class="ava" style="background:var(--panel2)"><svg viewBox="0 0 24 24" fill="none" stroke="var(--sub)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="22" height="22"><rect x="2" y="4" width="20" height="5" rx="1"/><path d="M4 9v10a1 1 0 001 1h14a1 1 0 001-1V9M10 13h4"/></svg></div>' +
        '<div class="row-main"><div class="row-name">Архив</div><div class="row-last">' + n + ' чат(ов)</div></div>';
    list.insertBefore(row, list.firstChild);
}

window.openArchive = async function(){
    var sheet = document.getElementById('archSheet');
    if (!sheet) {
        sheet = document.createElement('div');
        sheet.id = 'archSheet';
        sheet.style.cssText = 'display:none;position:fixed;inset:0;z-index:260;background:var(--bg)';
        sheet.innerHTML =
            '<div class="top"><button class="icon-btn" onclick="document.getElementById(\'archSheet\').style.display=\'none\'">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button><h2>Архив</h2></div>' +
            '<div class="list" id="archList"></div>';
        document.body.appendChild(sheet);
    }
    sheet.style.display = 'block';
    var box = document.getElementById('archList');
    box.innerHTML = '<div class="hint">Загрузка…</div>';
    var r = await api('chats&arch=1');
    var chats = (r && r.chats) || [];
    if (!chats.length) { box.innerHTML = '<div class="hint">Архив пуст</div>'; return; }
    box.innerHTML = chats.map(function(c){
        var tt = esc(c.title).replace(/'/g, "\\'");
        var av = c.avatar_img
            ? '<div class="ava"><img src="' + c.avatar_img + '"></div>'
            : '<div class="ava ' + (c.type === 'group' ? 'g' : '') + '">' + esc((c.title || '?').charAt(0).toUpperCase()) + '</div>';
        return '<div class="row">' +
            '<div style="display:flex;gap:13px;align-items:center;flex:1;min-width:0" onclick="document.getElementById(\'archSheet\').style.display=\'none\';openChat(' +
            c.id + ",'" + c.type + "'," + c.peer_id + ",'" + tt + "','" + (c.avatar_img || '') + "')\">" + av +
            '<div class="row-main"><div class="row-name">' + esc(c.title) + '</div>' +
            '<div class="row-last">' + esc(c.last || '') + '</div></div></div>' +
            '<button class="st-btn" style="width:auto;margin:0;padding:8px 12px;background:var(--panel2);color:var(--txt);font-size:13px" onclick="event.stopPropagation();unarchive(' + c.id + ')">Вернуть</button></div>';
    }).join('');
};

window.unarchive = async function(id){
    await api('chat_flag', 'POST', { chat: id, what: 'archived', val: 0 });
    toast('Чат возвращён в список');
    openArchive(); loadChats();
};

/* кнопки «Закрепить» и «В архив» в экране информации о чате */
if (typeof openInfo === 'function') {
    var _openInfo = openInfo;
    window.openInfo = async function(){
        var res = await _openInfo.apply(this, arguments);
        try { injectChatFlagBtns(); } catch(e){}
        return res;
    };
}

function injectChatFlagBtns(){
    var body = document.getElementById('infoBody');
    if (!body || body.querySelector('.flagBtns')) return;
    var blocks = body.querySelectorAll('div[style*="padding:14px 16px"]');
    var target = blocks.length ? blocks[blocks.length - 1] : body;
    var f = window._chatFlags[window.curChat] || {};
    var wrap = document.createElement('div');
    wrap.className = 'flagBtns';
    wrap.innerHTML =
        '<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="toggleFlag(\'pinned\')">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5M5 9l7-7 7 7-3 3v4H8v-4z"/></svg> ' +
        (f.pinned ? 'Открепить' : 'Закрепить наверху') + '</button>' +
        '<button class="st-btn" style="background:var(--panel2);color:var(--txt)" onclick="toggleFlag(\'archived\')">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="5" rx="1"/><path d="M4 9v10a1 1 0 001 1h14a1 1 0 001-1V9M10 13h4"/></svg> ' +
        (f.archived ? 'Убрать из архива' : 'В архив') + '</button>';
    target.insertBefore(wrap, target.firstChild);
}

window.toggleFlag = async function(what){
    var f = window._chatFlags[window.curChat] || {};
    var val = f[what] ? 0 : 1;
    await api('chat_flag', 'POST', { chat: window.curChat, what: what, val: val });
    f[what] = val; window._chatFlags[window.curChat] = f;
    toast(what === 'pinned' ? (val ? 'Чат закреплён' : 'Откреплён') : (val ? 'Убран в архив' : 'Возвращён из архива'));
    if (what === 'archived' && val) { if (typeof closeInfo === 'function') closeInfo(); if (typeof closeChat === 'function') closeChat(); }
    else { openInfo(); }
    loadChats();
};

/* ------------------------------------------------------------------
   3. ССЫЛКА-ПРИГЛАШЕНИЕ В ГРУППУ
   ------------------------------------------------------------------ */
function injectInviteBtn(){
    var body = document.getElementById('infoBody');
    if (!body || body.querySelector('.inviteBtn')) return;
    if (!body.innerHTML || body.innerHTML.indexOf('участник(ов)') === -1) return;   // только группы
    var blocks = body.querySelectorAll('div[style*="padding:14px 16px"]');
    var target = blocks.length ? blocks[blocks.length - 1] : body;
    var b = document.createElement('button');
    b.className = 'st-btn inviteBtn';
    b.style.cssText = 'background:var(--blue);color:#fff';
    b.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 007 0l3-3a5 5 0 00-7-7l-1 1"/><path d="M14 11a5 5 0 00-7 0l-3 3a5 5 0 007 7l1-1"/></svg> Пригласить по ссылке';
    b.onclick = shareInvite;
    target.insertBefore(b, target.firstChild);
}
if (typeof openInfo === 'function') {
    var _openInfo2 = window.openInfo;
    window.openInfo = async function(){
        var res = await _openInfo2.apply(this, arguments);
        try { injectInviteBtn(); } catch(e){}
        return res;
    };
}

window.shareInvite = async function(){
    var r = await api('invite_create', 'POST', { chat: window.curChat });
    if (!r || !r.ok) { toast(r && r.error === 'no_access' ? 'Только админ может создать ссылку' : 'Не удалось'); return; }
    var link = baseUrl() + '?join=' + r.code;
    copyText(link);
    toast('Ссылка скопирована: ' + link);
};

/* открытие по ссылке ?join=КОД */
(function(){
    var code = new URLSearchParams(location.search).get('join');
    if (!code) return;
    try { history.replaceState(null, '', location.pathname); } catch(e){}
    setTimeout(async function(){
        var info = await api('invite_info&code=' + encodeURIComponent(code));
        if (!info || !info.ok) { toast('Ссылка недействительна'); return; }
        if (info.member) {
            openChat(info.chat_id, 'group', 0, info.name, info.avatar || '');
            return;
        }
        if (!confirm('Вступить в группу «' + info.name + '»?\nУчастников: ' + info.count)) return;
        var j = await api('invite_join', 'POST', { code: code });
        if (j && j.ok) { toast('Вы в группе'); loadChats(); openChat(j.chat_id, 'group', 0, j.name, ''); }
        else toast('Не удалось вступить');
    }, 1200);
})();

/* ------------------------------------------------------------------
   4. ГЛОБАЛЬНЫЙ ПОИСК ПО ВСЕМ ЧАТАМ
   ------------------------------------------------------------------ */
(function(){
    var inp = document.getElementById('searchInput');
    if (!inp) return;
    var timer = null;
    inp.addEventListener('input', function(){
        clearTimeout(timer);
        var q = inp.value.trim();
        if (q.length < 2) { var b = document.getElementById('globalRes'); if (b) b.remove(); return; }
        timer = setTimeout(function(){ runGlobalSearch(q); }, 420);
    });
})();

async function runGlobalSearch(q){
    var r = await api('search_all&q=' + encodeURIComponent(q));
    var list = document.getElementById('listArea');
    if (!list) return;
    var old = document.getElementById('globalRes');
    if (old) old.remove();
    if (!r || !r.results || !r.results.length) return;

    var box = document.createElement('div');
    box.id = 'globalRes';
    box.innerHTML =
        '<div style="padding:12px 16px 6px;font-size:12px;font-weight:800;color:var(--sub);text-transform:uppercase">' +
        'Сообщения (' + r.results.length + ')</div>' +
        r.results.map(function(m){
            var tt = esc(m.title).replace(/'/g, "\\'");
            var av = m.avatar
                ? '<div class="ava" style="width:44px;height:44px"><img src="' + m.avatar + '"></div>'
                : '<div class="ava ' + (m.type === 'group' ? 'g' : '') + '" style="width:44px;height:44px;font-size:17px">' +
                  esc((m.title || '?').charAt(0).toUpperCase()) + '</div>';
            return '<div class="row" onclick="jumpToMsg(' + m.chat_id + ",'" + m.type + "'," + m.peer_id + ",'" + tt +
                   "','" + (m.avatar || '') + "'," + m.msg_id + ')">' + av +
                   '<div class="row-main"><div class="row-top"><div class="row-name">' + esc(m.title) +
                   '</div><div class="row-time">' + relTime(m.ts) + '</div></div>' +
                   '<div class="row-last">' + esc(m.sender ? m.sender + ': ' : '') + esc(m.text) + '</div></div></div>';
        }).join('');
    list.appendChild(box);
}

window.jumpToMsg = function(chatId, type, peerId, title, avatar, msgId){
    var inp = document.getElementById('searchInput');
    if (inp) inp.value = '';
    var g = document.getElementById('globalRes');
    if (g) g.remove();
    openChat(chatId, type, peerId, title, avatar);
    setTimeout(function(){ if (typeof scrollToMsg === 'function') scrollToMsg(msgId); }, 900);
};


/* ---------------- Комментарии к публикациям ---------------- */
var cmtPost = 0;
window.openComments = async function(pid){
    cmtPost = pid;
    var sh = document.getElementById('cmtSheet');
    if (!sh) {
        sh = document.createElement('div');
        sh.id = 'cmtSheet';
        sh.style.cssText = 'display:none;position:fixed;inset:0;z-index:270;background:rgba(0,0,0,.5)';
        sh.onclick = function(e){ if (e.target === sh) sh.style.display = 'none'; };
        sh.innerHTML =
            '<div style="position:absolute;left:0;right:0;bottom:0;height:78vh;background:var(--bg);' +
            'border-radius:18px 18px 0 0;display:flex;flex-direction:column">' +
            '<div style="display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--line)">' +
            '<div style="font-weight:800;font-size:16px;flex:1" id="cmtTitle">Комментарии</div>' +
            '<button class="icon-btn" style="width:34px;height:34px" onclick="document.getElementById(\'cmtSheet\').style.display=\'none\'">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button></div>' +
            '<div id="cmtList" style="flex:1;overflow-y:auto;padding:12px 14px"></div>' +
            '<div id="cmtBar" class="composer" style="border-top:1px solid var(--line)">' +
            '<textarea id="cmtInput" rows="1" placeholder="Комментарий…"></textarea>' +
            '<button class="send" onclick="sendComment()">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg></button></div></div>';
        document.body.appendChild(sh);
        var ta = document.getElementById('cmtInput');
        ta.addEventListener('input', function(){ ta.style.height='auto'; ta.style.height=Math.min(90,ta.scrollHeight)+'px'; });
        ta.addEventListener('keydown', function(e){ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendComment(); } });
    }
    sh.style.display = 'block';
    await loadComments();
};

async function loadComments(){
    var box = document.getElementById('cmtList');
    box.innerHTML = '<div class="hint">Загрузка…</div>';
    var r = await api('ch_comments&post=' + cmtPost);
    if (!r || !r.ok) { box.innerHTML = '<div class="hint">Не удалось загрузить</div>'; return; }

    document.getElementById('cmtTitle').textContent = 'Комментарии' + (r.comments.length ? ' · ' + r.comments.length : '');
    document.getElementById('cmtBar').style.display = r.can_write ? 'flex' : 'none';

    if (!r.comments.length) {
        box.innerHTML = '<div class="hint">' + (r.comments_on ? 'Пока никто не написал.<br>Будьте первым.' : 'Комментарии отключены.') + '</div>';
        return;
    }
    box.innerHTML = r.comments.map(function(c){
        var canDel = (+c.user_id === +r.me) || r.is_admin;
        var av = c.avatar ? '<div class="ava" style="width:36px;height:36px"><img src="' + c.avatar + '"></div>'
                          : '<div class="ava" style="width:36px;height:36px;font-size:14px">' + esc((c.name||'?').charAt(0).toUpperCase()) + '</div>';
        return '<div style="display:flex;gap:10px;margin-bottom:14px">' + av +
            '<div style="flex:1;min-width:0">' +
            '<div style="display:flex;align-items:center;gap:6px">' +
            '<span style="font-weight:800;font-size:13.5px">' + esc(c.name || 'Пользователь') + '</span>' +
            (+c.verified === 1 ? VBADGE : '') +
            '<span style="font-size:11.5px;color:var(--sub)">' + (typeof relTime==='function'?relTime(c.ts):'') + '</span>' +
            (canDel ? '<span style="margin-left:auto;font-size:11.5px;color:#FF6B6B;cursor:pointer" onclick="delComment(' + c.id + ')">удалить</span>' : '') +
            '</div>' +
            '<div style="font-size:14.5px;line-height:1.45;margin-top:2px;word-break:break-word">' +
            (typeof linkify==='function' ? linkify(c.text) : esc(c.text)) + '</div></div></div>';
    }).join('');
    box.scrollTop = box.scrollHeight;
}

var cmtBusy = false;
window.sendComment = async function(){
    if (cmtBusy) return;
    var ta = document.getElementById('cmtInput');
    var t = ta.value.trim();
    if (!t) return;
    cmtBusy = true;
    ta.value = ''; ta.style.height = 'auto';
    var r = await api('ch_comment_add', 'POST', { post: cmtPost, text: t });
    cmtBusy = false;
    if (r && r.ok) {
        await loadComments();
        var fb = document.getElementById('chFeed'); if (fb) fb.dataset.sig = '';
        loadPosts();
    } else {
        var e = r && r.error;
        toast(e === 'slow' ? 'Слишком часто, подождите' :
              e === 'closed' ? 'Комментарии отключены' :
              e === 'not_sub' ? 'Сначала подпишитесь на канал' : 'Не удалось отправить');
        ta.value = t;
    }
};

window.delComment = async function(id){
    if (!confirm('Удалить комментарий?')) return;
    await api('ch_comment_del', 'POST', { id: id });
    await loadComments();
    var fb = document.getElementById('chFeed'); if (fb) fb.dataset.sig = '';
    loadPosts();
};

window.toggleComments = async function(){
    var c = window._curChData || {};
    var val = c.comments_on ? 0 : 1;
    var r = await api('ch_comments_toggle', 'POST', { channel: curCh, val: val });
    if (r && r.ok) { c.comments_on = val; toast(val ? 'Комментарии включены' : 'Комментарии отключены'); openChannelInfo(); }
    else toast('Не удалось');
};

})();
</script>
</body>
</html>
<!-- PAYOM-UPDATE-v2 -->
<!-- PAYOM-CHANNELS -->
