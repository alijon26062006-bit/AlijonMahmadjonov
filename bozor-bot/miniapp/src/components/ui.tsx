/** Мелкие общие компоненты: шапка, нижняя навигация, пустые состояния, скелетоны. */
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useSyncExternalStore } from 'react';
import { getUser, isAuthed, onAuthChange } from '../api/client';
import { inTelegram, tg, toggleTheme } from '../telegram/tg';

export function useAuth() {
  return useSyncExternalStore(
    onAuthChange,
    () => (isAuthed() ? getUser() : null),
  );
}

export function Header() {
  const user = useAuth();
  if (inTelegram) return null;
  return (
    <header className="header">
      <Link to="/" className="logo">
        <span className="logo-mark">Б</span> Бозор
      </Link>
      <div className="header-actions">
        <button className="btn btn-ghost" onClick={toggleTheme} title="Тема">◐</button>
        <Link to="/post" className="btn btn-primary">+ Подать</Link>
        {user
          ? <Link to="/my" className="btn">{user.first_name || 'Профиль'}</Link>
          : <Link to="/login" className="btn">Войти</Link>}
      </div>
    </header>
  );
}

const NAV = [
  { to: '/', ico: '🏠', label: 'Главная' },
  { to: '/catalog', ico: '🔍', label: 'Каталог' },
  { to: '/post', ico: '➕', label: 'Подать' },
  { to: '/favorites', ico: '❤️', label: 'Избранное' },
  { to: '/my', ico: '👤', label: 'Мои' },
];

export function BottomNav() {
  const { pathname } = useLocation();
  return (
    <nav className="bottomnav">
      {NAV.map((n) => (
        <Link key={n.to} to={n.to}
              className={pathname === n.to ? 'active' : ''}>
          <span className="ico">{n.ico}</span>
          {n.label}
        </Link>
      ))}
    </nav>
  );
}

/** Системная кнопка «Назад» Telegram синхронно с роутером. */
export function useTgBackButton(show: boolean) {
  const navigate = useNavigate();
  useEffect(() => {
    const wa = tg;
    if (!inTelegram || !wa) return;
    if (!show) { wa.BackButton.hide(); return; }
    const cb = () => navigate(-1);
    wa.BackButton.show();
    wa.BackButton.onClick(cb);
    return () => { wa.BackButton.offClick(cb); wa.BackButton.hide(); };
  }, [show, navigate]);
}

export function Empty({ emoji, title, note }: { emoji: string; title: string; note?: string }) {
  return (
    <div className="empty fade-in">
      <div className="emoji">{emoji}</div>
      <h3>{title}</h3>
      {note && <p className="subtitle">{note}</p>}
    </div>
  );
}

export function CardSkeletons({ n = 6 }: { n?: number }) {
  return (
    <div className="grid">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="skeleton" style={{ aspectRatio: '3 / 4' }} />
      ))}
    </div>
  );
}

export const STATUS_BADGE: Record<string, { cls: string; label: string }> = {
  pending: { cls: 'badge-amber', label: '⏳ На модерации' },
  approved: { cls: 'badge-green', label: '✅ Опубликовано' },
  rejected: { cls: 'badge-red', label: '❌ Отклонено' },
  archived: { cls: 'badge-gray', label: '📦 Архив' },
  sold: { cls: 'badge-gray', label: '🤝 Продано' },
  occupied: { cls: 'badge-amber', label: '🔒 Занято' },
};
