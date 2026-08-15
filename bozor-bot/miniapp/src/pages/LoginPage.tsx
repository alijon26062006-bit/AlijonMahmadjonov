/** Браузерный вход: код → подтверждение в боте → сессия. */
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { pollLoginCode, requestLoginCode } from '../api/client';
import { useAuth } from '../components/ui';

export default function LoginPage() {
  const navigate = useNavigate();
  const user = useAuth();
  const [link, setLink] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'waiting' | 'expired'>('idle');
  const timer = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    if (user) navigate('/', { replace: true });
  }, [user, navigate]);

  useEffect(() => () => clearInterval(timer.current), []);

  const start = async () => {
    const { code, link } = await requestLoginCode();
    setLink(link);
    setStatus('waiting');
    window.open(link, '_blank');
    timer.current = setInterval(async () => {
      try {
        const ok = await pollLoginCode(code);
        if (ok) {
          clearInterval(timer.current);
          navigate('/', { replace: true });
        }
      } catch {
        clearInterval(timer.current);
        setStatus('expired');
      }
    }, 2000);
  };

  return (
    <div className="section fade-in" style={{ maxWidth: 420, margin: '40px auto' }}>
      <div style={{ textAlign: 'center' }}>
        <div className="logo-mark" style={{ width: 56, height: 56, fontSize: 28, margin: '0 auto 16px' }}>Б</div>
        <h1 className="section-title">Вход через Telegram</h1>
        <p className="subtitle" style={{ marginBottom: 24 }}>
          Аккаунт один и тот же в боте, приложении и на сайте.
          Пароль не нужен — вход подтверждается в Telegram.
        </p>

        {status === 'idle' && (
          <button className="btn btn-primary btn-block" onClick={start}>
            ✈️ Войти через Telegram
          </button>
        )}
        {status === 'waiting' && (
          <>
            <div className="skeleton" style={{ height: 8, borderRadius: 4, marginBottom: 14 }} />
            <p className="subtitle">
              Открыли Telegram? Нажмите в боте «Подтвердить вход».<br />
              Страница обновится сама.
            </p>
            {link && (
              <p style={{ marginTop: 12 }}>
                <a href={link} target="_blank" rel="noreferrer">Открыть бота ещё раз</a>
              </p>
            )}
          </>
        )}
        {status === 'expired' && (
          <>
            <p className="field-error" style={{ marginBottom: 12 }}>Код устарел (5 минут).</p>
            <button className="btn btn-primary btn-block" onClick={start}>Попробовать снова</button>
          </>
        )}
      </div>
    </div>
  );
}
