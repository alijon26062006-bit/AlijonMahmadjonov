<?php
// ============================================================================
// PAYOM — Биометрический вход через WebAuthn / Passkeys
// ----------------------------------------------------------------------------
// Как это работает (безопасная схема, как в банках):
//   • Face ID / Touch ID / отпечаток проверяются ТОЛЬКО на устройстве
//     пользователя. Ни фото, ни отпечаток никуда не передаются.
//   • При включении устройство создаёт пару ключей. Секретный ключ остаётся
//     в защищённом чипе телефона, серверу отдаётся только ПУБЛИЧНЫЙ ключ.
//   • При входе сервер выдаёт случайный challenge, устройство подписывает его
//     секретным ключом (после проверки биометрии), сервер проверяет подпись
//     публичным ключом. Всё.
//
// Файл самодостаточный: чистый PHP 8 + openssl, без composer-библиотек.
// Подключается из messenger.php:  require_once __DIR__.'/webauthn.php';
// ============================================================================

// ---------------------------------------------------------------------------
// Вспомогательные функции
// ---------------------------------------------------------------------------
function wa_b64u_enc($d) { return rtrim(strtr(base64_encode($d), '+/', '-_'), '='); }
function wa_b64u_dec($d) { return base64_decode(strtr($d, '-_', '+/') . str_repeat('=', (4 - strlen($d) % 4) % 4)); }

/* Идентификатор сайта (rpId) — домен без порта. Passkey привязывается к нему. */
function wa_rp_id() {
    $h = $_SERVER['HTTP_HOST'] ?? 'localhost';
    return preg_replace('/:\d+$/', '', $h);
}

/* Ожидаемый origin (протокол+домен) для проверки ответа браузера. */
function wa_origin() {
    $https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
          || (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https');
    return ($https ? 'https://' : 'http://') . ($_SERVER['HTTP_HOST'] ?? 'localhost');
}

/* Таблица публичных ключей. Создаётся один раз (флаг-файл, как в проекте). */
function wa_init($pdo) {
    static $done = false; if ($done) return; $done = true;
    $flag = __DIR__ . '/.payom_webauthn_v1';
    if (is_file($flag)) return;
    try {
        $pdo->exec("CREATE TABLE IF NOT EXISTS qaz_webauthn (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            credential_id VARCHAR(300) NOT NULL,
            public_key TEXT NOT NULL,
            alg INT NOT NULL DEFAULT -7,
            sign_count BIGINT NOT NULL DEFAULT 0,
            device VARCHAR(120) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP NULL,
            UNIQUE KEY uq_wa_cred (credential_id(191)),
            INDEX idx_wa_user (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
        @file_put_contents($flag, date('Y-m-d H:i:s'));
    } catch (\Throwable $e) { /* тихо: таблица могла уже существовать */ }
}

/* Одноразовый challenge в сессии (живёт 5 минут, используется один раз). */
function wa_new_challenge($key) {
    $c = wa_b64u_enc(random_bytes(32));
    $_SESSION[$key] = ['c' => $c, 't' => time()];
    return $c;
}
function wa_take_challenge($key) {
    $v = $_SESSION[$key] ?? null;
    unset($_SESSION[$key]);                      // одноразовый: сразу забываем
    if (!$v || (time() - $v['t']) > 300) return null;   // просрочен
    return $v['c'];
}

// ---------------------------------------------------------------------------
// Минимальный декодер CBOR (формат, в котором браузер отдаёт attestation).
// Поддерживает всё, что реально шлют аутентификаторы (определённые длины).
// ---------------------------------------------------------------------------
function wa_cbor($bin, &$off) {
    if ($off >= strlen($bin)) throw new \Exception('cbor eof');
    $ib = ord($bin[$off++]); $mt = $ib >> 5; $ai = $ib & 0x1f;
    if ($ai < 24)      { $val = $ai; }
    elseif ($ai === 24){ $val = ord($bin[$off]); $off += 1; }
    elseif ($ai === 25){ $val = unpack('n', substr($bin, $off, 2))[1]; $off += 2; }
    elseif ($ai === 26){ $val = unpack('N', substr($bin, $off, 4))[1]; $off += 4; }
    elseif ($ai === 27){ if (PHP_INT_SIZE < 8) throw new \Exception('cbor 64'); $val = unpack('J', substr($bin, $off, 8))[1]; $off += 8; }
    else throw new \Exception('cbor indefinite');
    switch ($mt) {
        case 0: return $val;                       // положительное число
        case 1: return -1 - $val;                  // отрицательное число
        case 2: case 3:                            // байты / текст
            $s = substr($bin, $off, $val); $off += $val; return $s;
        case 4:                                    // массив
            $a = []; for ($i = 0; $i < $val; $i++) $a[] = wa_cbor($bin, $off); return $a;
        case 5:                                    // словарь
            $m = []; for ($i = 0; $i < $val; $i++) { $k = wa_cbor($bin, $off); $v = wa_cbor($bin, $off); $m[$k] = $v; } return $m;
        case 6: return wa_cbor($bin, $off);        // тег — пропускаем
        default:                                   // simple values
            if ($ai === 20) return false; if ($ai === 21) return true; return null;
    }
}

// ---------------------------------------------------------------------------
// DER-помощники: собираем публичный ключ в PEM для openssl_verify.
// ---------------------------------------------------------------------------
function wa_der_len($n) { if ($n < 0x80) return chr($n); $s = ltrim(pack('N', $n), "\x00"); return chr(0x80 | strlen($s)) . $s; }
function wa_der_seq($c) { return "\x30" . wa_der_len(strlen($c)) . $c; }
function wa_der_int($b) { $b = ltrim($b, "\x00"); if ($b === '' || (ord($b[0]) & 0x80)) $b = "\x00" . $b; return "\x02" . wa_der_len(strlen($b)) . $b; }
function wa_der_bits($c){ return "\x03" . wa_der_len(strlen($c) + 1) . "\x00" . $c; }

/* COSE-ключ (из attestation) -> PEM. Поддержка ES256 (iPhone/Android) и
   RS256 (Windows Hello). Возвращает null, если формат неизвестен. */
function wa_cose_to_pem($k, &$alg) {
    if (!is_array($k)) return null;
    $kty = $k[1] ?? 0; $alg = (int)($k[3] ?? 0);
    if ($kty === 2) {                              // EC2 / P-256 (ES256)
        $x = $k[-2] ?? ''; $y = $k[-3] ?? '';
        if (strlen($x) > 32 || strlen($y) > 32 || $x === '' || $y === '') return null;
        $raw = "\x04" . str_pad($x, 32, "\x00", STR_PAD_LEFT) . str_pad($y, 32, "\x00", STR_PAD_LEFT);
        $der = hex2bin('3059301306072a8648ce3d020106082a8648ce3d030107034200') . $raw;
    } elseif ($kty === 3) {                        // RSA (RS256)
        $n = $k[-1] ?? ''; $e = $k[-2] ?? '';
        if ($n === '' || $e === '') return null;
        $der = wa_der_seq(
            wa_der_seq(hex2bin('06092a864886f70d010101') . "\x05\x00") .
            wa_der_bits(wa_der_seq(wa_der_int($n) . wa_der_int($e)))
        );
    } else return null;
    return "-----BEGIN PUBLIC KEY-----\n" . chunk_split(base64_encode($der), 64, "\n") . "-----END PUBLIC KEY-----\n";
}

/* Разбор authenticatorData: rpIdHash, флаги, счётчик, credentialId + COSE. */
function wa_parse_auth_data($auth) {
    if (strlen($auth) < 37) return null;
    $out = [
        'rpIdHash'  => substr($auth, 0, 32),
        'flags'     => ord($auth[32]),
        'signCount' => unpack('N', substr($auth, 33, 4))[1],
        'credId'    => null, 'cose' => null,
    ];
    if ($out['flags'] & 0x40) {                    // AT: есть данные ключа
        if (strlen($auth) < 55) return null;
        $len = unpack('n', substr($auth, 53, 2))[1];
        $out['credId'] = substr($auth, 55, $len);
        $off = 55 + $len;
        try { $out['cose'] = wa_cbor($auth, $off); } catch (\Throwable $e) { return null; }
    }
    return $out;
}

/* Проверка clientDataJSON: тип операции, наш challenge, наш origin. */
function wa_check_client_data($raw, $expectType, $challenge) {
    $cd = json_decode($raw, true);
    if (!is_array($cd)) return 'bad_client_data';
    if (($cd['type'] ?? '') !== $expectType) return 'bad_type';
    if (!hash_equals($challenge, (string)($cd['challenge'] ?? ''))) return 'bad_challenge';
    if (($cd['origin'] ?? '') !== wa_origin()) return 'bad_origin';
    return null;
}

// ===========================================================================
// ОБРАБОТЧИКИ БЕЗ ВХОДА (экран логина)
// ===========================================================================
function wa_handle_preauth($pdo, $action) {
    wa_init($pdo);

    if ($action === 'bio_login_options') {
        // Пустой allowCredentials => браузер сам предложит passkey этого сайта
        // (discoverable credential). Работает на iPhone, Android и ПК.
        echo json_encode(['ok' => true, 'publicKey' => [
            'challenge'        => wa_new_challenge('wa_login_ch'),
            'timeout'          => 60000,
            'rpId'             => wa_rp_id(),
            'userVerification' => 'required',       // обязательно биометрия/ПИН
            'allowCredentials' => [],
        ]]);
        return;
    }

    if ($action === 'bio_login_finish' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true) ?: [];
        $challenge = wa_take_challenge('wa_login_ch');
        if (!$challenge) { echo json_encode(['error' => 'expired']); return; }

        $credId   = (string)($d['rawId'] ?? '');
        $cdRaw    = wa_b64u_dec((string)($d['clientDataJSON'] ?? ''));
        $authData = wa_b64u_dec((string)($d['authenticatorData'] ?? ''));
        $sig      = wa_b64u_dec((string)($d['signature'] ?? ''));
        if ($credId === '' || $cdRaw === '' || $authData === '' || $sig === '') { echo json_encode(['error' => 'bad_request']); return; }

        if ($err = wa_check_client_data($cdRaw, 'webauthn.get', $challenge)) { echo json_encode(['error' => $err]); return; }

        $ad = wa_parse_auth_data($authData);
        if (!$ad || !hash_equals(hash('sha256', wa_rp_id(), true), $ad['rpIdHash'])) { echo json_encode(['error' => 'bad_rp']); return; }
        if (!($ad['flags'] & 0x01)) { echo json_encode(['error' => 'no_user_presence']); return; }
        if (!($ad['flags'] & 0x04)) { echo json_encode(['error' => 'no_user_verification']); return; }  // биометрия не пройдена

        // Ищем ключ. Если не нашли — пользователь сменил устройство/ключ удалён.
        $st = $pdo->prepare("SELECT * FROM qaz_webauthn WHERE credential_id = ?");
        $st->execute([$credId]); $row = $st->fetch();
        if (!$row) { echo json_encode(['error' => 'unknown_credential']); return; }

        // Криптографическая проверка подписи публичным ключом.
        $signed = $authData . hash('sha256', $cdRaw, true);
        $pub = openssl_pkey_get_public($row['public_key']);
        if (!$pub || openssl_verify($signed, $sig, $pub, OPENSSL_ALGO_SHA256) !== 1) { echo json_encode(['error' => 'bad_signature']); return; }

        // Пользователь ещё существует?
        $uq = $pdo->prepare("SELECT id, name, phone, COALESCE(deleted,0) AS deleted FROM qaz_users WHERE id = ?");
        $uq->execute([(int)$row['user_id']]); $u = $uq->fetch();
        if (!$u || (int)$u['deleted'] === 1) {
            $pdo->prepare("DELETE FROM qaz_webauthn WHERE id = ?")->execute([$row['id']]);
            echo json_encode(['error' => 'unknown_credential']); return;
        }

        // Счётчик подписей: обновляем (синхронизируемые passkey часто шлют 0 —
        // это нормально, поэтому по счётчику не блокируем, только фиксируем).
        $pdo->prepare("UPDATE qaz_webauthn SET sign_count = GREATEST(sign_count, ?), last_used = NOW() WHERE id = ?")
            ->execute([(int)$ad['signCount'], $row['id']]);

        // Входим: новая сессия + «запомнить меня» (как при входе по номеру).
        session_regenerate_id(true);
        $_SESSION['user_id']    = (int)$u['id'];
        $_SESSION['user_name']  = $u['name'];
        $_SESSION['user_phone'] = $u['phone'];
        if (function_exists('qaz_set_remember')) qaz_set_remember($pdo, (int)$u['id']);
        echo json_encode(['ok' => true, 'name' => $u['name']], JSON_UNESCAPED_UNICODE);
        return;
    }

    echo json_encode(['error' => 'unknown_action']);
}

// ===========================================================================
// ОБРАБОТЧИКИ ДЛЯ ВОШЕДШЕГО ПОЛЬЗОВАТЕЛЯ (включение/выключение)
// ===========================================================================
function wa_handle_authed($pdo, $action, $me) {
    wa_init($pdo);

    if ($action === 'bio_status') {
        $st = $pdo->prepare("SELECT COUNT(*) FROM qaz_webauthn WHERE user_id = ?");
        $st->execute([$me]);
        $n = (int)$st->fetchColumn();
        echo json_encode(['ok' => true, 'has' => $n > 0, 'count' => $n]);
        return;
    }

    if ($action === 'bio_reg_options') {
        $uq = $pdo->prepare("SELECT name, phone FROM qaz_users WHERE id = ?");
        $uq->execute([$me]); $u = $uq->fetch() ?: ['name' => 'Payom', 'phone' => ''];
        // уже созданные ключи — чтобы устройство не регистрировало дубликат
        $eq = $pdo->prepare("SELECT credential_id FROM qaz_webauthn WHERE user_id = ?");
        $eq->execute([$me]);
        $exclude = [];
        foreach ($eq->fetchAll(PDO::FETCH_COLUMN) as $cid) $exclude[] = ['type' => 'public-key', 'id' => $cid];

        echo json_encode(['ok' => true, 'publicKey' => [
            'rp'   => ['id' => wa_rp_id(), 'name' => 'Payom'],
            'user' => ['id' => wa_b64u_enc((string)$me),
                       'name' => ($u['phone'] ?: ('user' . $me)),
                       'displayName' => ($u['name'] ?: ('Payom ' . $me))],
            'challenge'          => wa_new_challenge('wa_reg_ch'),
            'pubKeyCredParams'   => [['type' => 'public-key', 'alg' => -7],    // ES256 (iPhone/Android)
                                     ['type' => 'public-key', 'alg' => -257]], // RS256 (Windows Hello)
            'timeout'            => 60000,
            'attestation'        => 'none',        // данные производителя не собираем
            'authenticatorSelection' => [
                'authenticatorAttachment' => 'platform',   // встроенная биометрия устройства
                'residentKey'             => 'required',   // passkey: вход без ввода логина
                'requireResidentKey'      => true,
                'userVerification'        => 'required',
            ],
            'excludeCredentials' => $exclude,
        ]], JSON_UNESCAPED_UNICODE);
        return;
    }

    if ($action === 'bio_reg_finish' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $d = json_decode(file_get_contents('php://input'), true) ?: [];
        $challenge = wa_take_challenge('wa_reg_ch');
        if (!$challenge) { echo json_encode(['error' => 'expired']); return; }

        $cdRaw = wa_b64u_dec((string)($d['clientDataJSON'] ?? ''));
        $attB  = wa_b64u_dec((string)($d['attestationObject'] ?? ''));
        if ($cdRaw === '' || $attB === '') { echo json_encode(['error' => 'bad_request']); return; }

        if ($err = wa_check_client_data($cdRaw, 'webauthn.create', $challenge)) { echo json_encode(['error' => $err]); return; }

        try { $off = 0; $att = wa_cbor($attB, $off); } catch (\Throwable $e) { echo json_encode(['error' => 'bad_attestation']); return; }
        $ad = wa_parse_auth_data((string)($att['authData'] ?? ''));
        if (!$ad || $ad['credId'] === null || !$ad['cose']) { echo json_encode(['error' => 'bad_attestation']); return; }
        if (!hash_equals(hash('sha256', wa_rp_id(), true), $ad['rpIdHash'])) { echo json_encode(['error' => 'bad_rp']); return; }
        if (!($ad['flags'] & 0x01) || !($ad['flags'] & 0x04)) { echo json_encode(['error' => 'no_user_verification']); return; }

        $alg = 0;
        $pem = wa_cose_to_pem($ad['cose'], $alg);
        if (!$pem || !openssl_pkey_get_public($pem)) { echo json_encode(['error' => 'unsupported_key']); return; }

        $credB64 = wa_b64u_enc($ad['credId']);
        // Ключ уже есть? (например, повторная регистрация)
        $chk = $pdo->prepare("SELECT user_id FROM qaz_webauthn WHERE credential_id = ?");
        $chk->execute([$credB64]);
        $owner = $chk->fetchColumn();
        if ($owner !== false && (int)$owner !== (int)$me) { echo json_encode(['error' => 'credential_taken']); return; }

        $dev = substr((string)($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 120);
        if ($owner === false) {
            $pdo->prepare("INSERT INTO qaz_webauthn (user_id, credential_id, public_key, alg, sign_count, device) VALUES (?,?,?,?,?,?)")
                ->execute([$me, $credB64, $pem, $alg, (int)$ad['signCount'], $dev]);
        }
        $cnt = $pdo->prepare("SELECT COUNT(*) FROM qaz_webauthn WHERE user_id = ?");
        $cnt->execute([$me]);
        echo json_encode(['ok' => true, 'count' => (int)$cnt->fetchColumn()]);
        return;
    }

    if ($action === 'bio_disable' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $pdo->prepare("DELETE FROM qaz_webauthn WHERE user_id = ?")->execute([$me]);
        echo json_encode(['ok' => true]);
        return;
    }

    echo json_encode(['error' => 'unknown_action']);
}

// ===========================================================================
// КЛИЕНТСКИЙ МОДУЛЬ (JS). Echo-ится и на экране входа, и внутри приложения.
// Вся работа с navigator.credentials — здесь, одним объектом PayomBio.
// ===========================================================================
function bio_client_module() {
    return <<<'BIOJS'
<script>
/* PayomBio — биометрический вход (WebAuthn/Passkeys).
   Биометрия проверяется устройством; сервер видит только подпись. */
window.PayomBio=(function(){
  'use strict';
  var ok = !!(window.PublicKeyCredential && navigator.credentials && window.isSecureContext);
  function d(s){ s=String(s).replace(/-/g,'+').replace(/_/g,'/'); while(s.length%4)s+='='; var b=atob(s),u=new Uint8Array(b.length); for(var i=0;i<b.length;i++)u[i]=b.charCodeAt(i); return u.buffer; }
  function e(buf){ var u=new Uint8Array(buf),s=''; for(var i=0;i<u.length;i++)s+=String.fromCharCode(u[i]); return btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,''); }
  async function post(a,body){
    try{ var r=await fetch('messenger.php?action='+a,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
         if(r.status===429) return {error:'rate_limited'};
         return await r.json().catch(function(){return {error:'bad_json'};});
    }catch(_){ return {error:'network'}; }
  }
  /* Есть ли на устройстве встроенная биометрия (Face ID/отпечаток)? */
  async function platform(){ if(!ok) return false;
    try{ return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable(); }catch(_){ return false; } }
  /* Человекочитаемая классификация ошибок браузера. */
  function fail(err){ if(!err) return 'error';
    if(err.name==='NotAllowedError') return 'cancel';      // отменил или не подтвердил
    if(err.name==='InvalidStateError') return 'exists';    // ключ уже есть на устройстве
    if(err.name==='SecurityError') return 'security';      // не https / чужой домен
    if(err.name==='AbortError') return 'cancel';
    return err.message||'error'; }
  /* Включение биометрии (после входа по номеру). */
  async function enroll(){
    if(!ok) return {error:'unsupported'};
    var o=await post('bio_reg_options'); if(!o||!o.ok) return {error:(o&&o.error)||'server'};
    var pk=o.publicKey;
    pk.challenge=d(pk.challenge); pk.user.id=d(pk.user.id);
    (pk.excludeCredentials||[]).forEach(function(c){ c.id=d(c.id); });
    var cred; try{ cred=await navigator.credentials.create({publicKey:pk}); }catch(err){ return {error:fail(err)}; }
    if(!cred) return {error:'cancel'};
    var r=await post('bio_reg_finish',{ rawId:e(cred.rawId),
        clientDataJSON:e(cred.response.clientDataJSON),
        attestationObject:e(cred.response.attestationObject) });
    if(r&&r.ok){ try{ localStorage.setItem('payomBio','1'); }catch(_){}
    }
    return r||{error:'server'};
  }
  /* Вход по биометрии. */
  async function login(){
    if(!ok) return {error:'unsupported'};
    var o=await post('bio_login_options'); if(!o||!o.ok) return {error:(o&&o.error)||'server'};
    var pk=o.publicKey; pk.challenge=d(pk.challenge);
    (pk.allowCredentials||[]).forEach(function(c){ c.id=d(c.id); });
    var cred; try{ cred=await navigator.credentials.get({publicKey:pk}); }catch(err){ return {error:fail(err)}; }
    if(!cred) return {error:'cancel'};
    return await post('bio_login_finish',{ rawId:e(cred.rawId),
        clientDataJSON:e(cred.response.clientDataJSON),
        authenticatorData:e(cred.response.authenticatorData),
        signature:e(cred.response.signature),
        userHandle:cred.response.userHandle?e(cred.response.userHandle):null });
  }
  return { ok:ok, platform:platform, enroll:enroll, login:login };
})();
</script>
BIOJS;
}
