/** Экран кода: ссылка на бота, QR для тех, кто с компьютера, шесть клеток.

    Вкладка всё это время спрашивает сервер, не подтвердил ли человек номер
    в боте. Подтвердил — впускаем сразу, вводить цифры уже незачем. Код
    остаётся нужен, если сюда вернулись с другого устройства.
*/
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  maskPhone, pollPhoneStatus, requestPhoneCode, verifyPhoneCode,
} from '../api/client';
import { Icon } from '../components/icons';
import Qr from '../components/Qr';
import { useAuth } from '../components/ui';

const LEN = 6;
const POLL_MS = 2000;
const RESEND_S = 60;

type Saved = { key: string; phone: string; link: string; back: string };

function saved(): Saved | null {
  try { return JSON.parse(sessionStorage.getItem('stambul.auth') ?? 'null'); }
  catch { return null; }
}

export default function VerifyPage() {
  const navigate = useNavigate();
  const user = useAuth();
  const [data, setData] = useState<Saved | null>(saved);
  const [digits, setDigits] = useState<string[]>(Array(LEN).fill(''));
  const [error, setError] = useState('');
  const [left, setLeft] = useState(RESEND_S);
  const boxes = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => { if (!data) navigate('/login', { replace: true }); }, [data, navigate]);
  useEffect(() => {
    if (user) navigate(data?.back || '/', { replace: true });
  }, [user, data, navigate]);

  // Ждём кнопку в боте
  useEffect(() => {
    if (!data) return;
    const id = setInterval(() => {
      pollPhoneStatus(data.key).catch(() => { /* сеть моргнула — повторим */ });
    }, POLL_MS);
    return () => clearInterval(id);
  }, [data]);

  useEffect(() => {
    if (left <= 0) return;
    const id = setTimeout(() => setLeft((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [left]);

  const submit = async (code: string) => {
    if (!data || code.length < LEN) return;
    setError('');
    try {
      await verifyPhoneCode(data.key, code);
    } catch (e) {
      setError((e as Error).message || 'Неверный код');
      setDigits(Array(LEN).fill(''));
      boxes.current[0]?.focus();
    }
  };

  const put = (i: number, raw: string) => {
    const chars = raw.replace(/\D/g, '');
    if (!chars) {
      const next = [...digits];
      next[i] = '';
      setDigits(next);
      return;
    }
    // вставка из буфера заполняет все клетки разом — так код из сообщения
    // переносится одним движением
    const next = [...digits];
    for (let k = 0; k < chars.length && i + k < LEN; k += 1) next[i + k] = chars[k];
    setDigits(next);
    const filled = Math.min(i + chars.length, LEN - 1);
    boxes.current[filled]?.focus();
    const code = next.join('');
    if (code.length === LEN && !code.includes('')) submit(code);
  };

  const resend = async () => {
    if (!data || left > 0) return;
    try {
      const req = await requestPhoneCode(data.phone);
      const fresh = { ...req, back: data.back };
      sessionStorage.setItem('stambul.auth', JSON.stringify(fresh));
      setData(fresh);
      setDigits(Array(LEN).fill(''));
      setError('');
      setLeft(RESEND_S);
    } catch (e) {
      setError((e as Error).message || 'Не получилось отправить заново');
    }
  };

  if (!data) return null;

  return (
    <div className="auth fade-in">
      <button className="btn btn-ghost" style={{ alignSelf: 'flex-start' }}
              onClick={() => navigate('/login')}>
        <Icon name="arrow-left" size={17} /> Изменить номер
      </button>

      <div>
        <h1>Подтвердите номер</h1>
        <p className="subtitle" style={{ marginTop: 8 }}>
          Откройте бота и нажмите «Отправить мой номер» — он пришлёт код
          для <b>{maskPhone(data.phone)}</b>.
        </p>
      </div>

      <a className="btn btn-primary btn-lg btn-block" href={data.link}
         target="_blank" rel="noreferrer">
        <Icon name="send" size={18} /> Получить код в Telegram
      </a>

      {/* На телефоне QR не нужен — человек уже держит телефон в руках */}
      <div className="only-wide">
        <div className="qr"><Qr value={data.link} /></div>
        <p className="caption" style={{ textAlign: 'center', marginTop: 8 }}>
          Наведите камеру телефона на код
        </p>
      </div>

      <div className="code-boxes">
        {digits.map((d, i) => (
          <input
            key={i}
            ref={(el) => { boxes.current[i] = el; }}
            value={d}
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={LEN}
            aria-label={`Цифра ${i + 1}`}
            onChange={(e) => put(i, e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Backspace' && !digits[i] && i > 0) {
                boxes.current[i - 1]?.focus();
              }
            }} />
        ))}
      </div>

      {error && <div className="notice notice-error">{error}</div>}

      <div className="row-between" style={{ flexWrap: 'wrap' }}>
        <span className="waiting"><i className="pulse" /> Ждём подтверждения</span>
        <button className="btn btn-ghost" disabled={left > 0} onClick={resend}>
          {left > 0 ? `Отправить снова через ${left} с` : 'Отправить снова'}
        </button>
      </div>
    </div>
  );
}
