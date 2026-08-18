/** Знакомство для того, кто пришёл по ссылке и не знает, куда попал.

    На телефоне это три экрана с листанием, на большом мониторе — те же три
    мысли подряд: листать страницу мышью никто не любит, а прокрутить
    привычно. Разметка одна, различается только раскладка.
*/
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getUser, isAuthed, updateMe } from '../api/client';
import { Icon } from '../components/icons';

const SEEN_KEY = 'stambul.welcome';

export function welcomeSeen(): boolean {
  return localStorage.getItem(SEEN_KEY) === '1' || Boolean(getUser()?.onboarding_done);
}

export function markWelcomeSeen(): void {
  localStorage.setItem(SEEN_KEY, '1');
  if (isAuthed() && !getUser()?.onboarding_done) {
    updateMe({ onboarding_done: true }).catch(() => { /* не критично */ });
  }
}

const SLIDES = [
  {
    icon: 'store',
    title: 'Всё для себя и для дома',
    text: 'Одежда, обувь, аксессуары, детские вещи, посуда и техника — '
        + 'в одном месте.',
  },
  {
    icon: 'ruler',
    title: 'Размер и цвет — честно',
    text: 'Показываем только то, что действительно есть на складе. '
        + 'Кончился размер — вы увидите это сразу.',
  },
  {
    icon: 'truck',
    title: 'Доставка по Казахстану',
    text: 'Курьером, почтой или самовывозом. Оплата через Kaspi после '
        + 'подтверждения заказа.',
  },
];

export default function WelcomePage() {
  const navigate = useNavigate();
  const [index, setIndex] = useState(0);
  const track = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = track.current;
    if (!el) return;
    const onScroll = () => {
      const width = el.clientWidth || 1;
      setIndex(Math.round(el.scrollLeft / width));
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  const go = (to: string) => { markWelcomeSeen(); navigate(to); };

  const next = () => {
    const el = track.current;
    if (!el) return;
    if (index >= SLIDES.length - 1) { go('/catalog'); return; }
    el.scrollTo({ left: el.clientWidth * (index + 1), behavior: 'smooth' });
  };

  return (
    <div className="welcome">
      <div className="row-between" style={{ padding: '16px var(--pad) 0' }}>
        <Link to="/" className="logo" onClick={markWelcomeSeen}>
          <span className="logo-mark">S</span>
          <span>Stambul Shop</span>
        </Link>
        <button className="btn btn-ghost" onClick={() => go('/catalog')}>
          Пропустить
        </button>
      </div>

      <div className="welcome-slides" ref={track}>
        {SLIDES.map((s) => (
          <section className="welcome-slide" key={s.title}>
            <div className="welcome-art" aria-hidden="true">
              <Icon name={s.icon} size={64} strokeWidth={1.1} />
            </div>
            <h1>{s.title}</h1>
            <p>{s.text}</p>
          </section>
        ))}
      </div>

      <div className="welcome-foot">
        <div className="welcome-dots" aria-hidden="true">
          {SLIDES.map((s, i) => <i key={s.title} className={i === index ? 'on' : ''} />)}
        </div>
        <div className="spacer" />
        <button className="btn btn-primary btn-lg" onClick={next}>
          {index >= SLIDES.length - 1 ? 'Смотреть каталог' : 'Далее'}
        </button>
      </div>

      <div style={{ textAlign: 'center', paddingBottom: 32 }}>
        <button className="btn btn-ghost" onClick={() => go('/login')}>
          Уже покупали здесь? Войти
        </button>
      </div>
    </div>
  );
}
