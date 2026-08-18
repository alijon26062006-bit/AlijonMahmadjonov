/** Вход: номер телефона или Google.

    Паролей в магазине нет — ни заводить, ни восстанавливать. Номер
    подтверждает Telegram, почту Google подтвердил до нас.
*/
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  loginWithGoogle, maskPhone, phoneReady, requestPhoneCode,
} from '../api/client';
import type { ShopConfig } from '../api/types';
import { Icon } from '../components/icons';
import { useAuth } from '../components/ui';

declare global {
  interface Window { google?: any }
}

export default function LoginPage({ cfg }: { cfg?: ShopConfig }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const back = params.get('back') || '/';
  const user = useAuth();

  const [phone, setPhone] = useState('+7 ');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { if (user) navigate(back, { replace: true }); }, [user, back, navigate]);

  const submit = async () => {
    if (!phoneReady(phone) || busy) return;
    setBusy(true);
    setError('');
    try {
      const req = await requestPhoneCode(phone);
      sessionStorage.setItem('stambul.auth', JSON.stringify({ ...req, back }));
      navigate('/login/code');
    } catch (e) {
      setError((e as Error).message || 'Не получилось, попробуйте ещё раз');
      setBusy(false);
    }
  };

  return (
    <div className="auth fade-in">
      <div>
        <h1>Вход в магазин</h1>
        <p className="subtitle" style={{ marginTop: 8 }}>
          Нужен, чтобы оформлять заказы и следить за доставкой.
          Смотреть каталог можно и без него.
        </p>
      </div>

      <div className="field">
        <label htmlFor="phone">Номер телефона</label>
        <input id="phone" className={`input${error ? ' input-error' : ''}`}
               inputMode="tel" autoComplete="tel" value={phone}
               onChange={(e) => setPhone(maskPhone(e.target.value))}
               onKeyDown={(e) => { if (e.key === 'Enter') submit(); }} />
        {error && <span className="field-error">{error}</span>}
      </div>

      <button className="btn btn-primary btn-lg btn-block"
              disabled={!phoneReady(phone) || busy} onClick={submit}>
        {busy ? 'Секунду…' : 'Получить код в Telegram'}
      </button>

      <p className="caption">
        Код придёт сообщением от нашего бота — SMS не нужны и денег с вас
        никто не спишет.
      </p>

      {cfg?.google_client_id && (
        <>
          <div className="or">или</div>
          <GoogleButton clientId={cfg.google_client_id}
                        onError={setError} />
        </>
      )}
    </div>
  );
}

/** Кнопка Google. Скрипт подключается только на этом экране: на остальных
    он не нужен, а лишний внешний файл замедляет весь сайт. */
function GoogleButton({ clientId, onError }: {
  clientId: string; onError: (m: string) => void;
}) {
  const [ready, setReady] = useState(Boolean(window.google));

  useEffect(() => {
    if (window.google) { setReady(true); return; }
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.onload = () => setReady(true);
    document.head.appendChild(script);
  }, []);

  useEffect(() => {
    if (!ready || !window.google) return;
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: async (response: { credential: string }) => {
        try { await loginWithGoogle(response.credential); }
        catch (e) { onError((e as Error).message || 'Google не подтвердил вход'); }
      },
    });
    const slot = document.getElementById('google-slot');
    if (slot) {
      window.google.accounts.id.renderButton(slot, {
        theme: 'outline', size: 'large', width: 348, text: 'continue_with',
        shape: 'rectangular', locale: 'ru',
      });
    }
  }, [ready, clientId, onError]);

  return (
    <div>
      <div id="google-slot" style={{ display: 'flex', justifyContent: 'center' }} />
      {!ready && (
        <button className="btn btn-lg btn-block" disabled>
          <Icon name="mail" size={18} /> Загружаем вход через Google…
        </button>
      )}
    </div>
  );
}
