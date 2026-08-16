/** Мелкие общие компоненты: шапка, нижняя навигация, пустые состояния, скелетоны. */
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useSyncExternalStore } from 'react';
import { getUser, isAuthed, onAuthChange } from '../api/client';
import { inTelegram, tg, toggleTheme } from '../telegram/tg';
import { Icon } from './icons';

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
        <button className="btn btn-ghost" onClick={toggleTheme} title="Тема">
          <Icon name="sun-moon" size={19} />
        </button>
        <Link to="/post" className="btn btn-primary">
          <Icon name="circle-plus" size={17} /> Подать
        </Link>
        {user?.is_admin && (
          <Link to="/admin" className="btn" title="Администрирование">
            <Icon name="sliders-horizontal" size={17} />
          </Link>
        )}
        {user
          ? <Link to="/my" className="btn">{user.first_name || 'Профиль'}</Link>
          : <Link to="/login" className="btn">Войти</Link>}
      </div>
    </header>
  );
}

const NAV = [
  { to: '/', icon: 'house', label: 'Главная' },
  { to: '/catalog', icon: 'search', label: 'Каталог' },
  { to: '/post', icon: 'circle-plus', label: 'Подать' },
  { to: '/favorites', icon: 'heart', label: 'Избранное' },
  { to: '/my', icon: 'user', label: 'Мои' },
];

const ADMIN_NAV = { to: '/admin', icon: 'sliders-horizontal', label: 'Админка' };

export function BottomNav() {
  const { pathname } = useLocation();
  const user = useAuth();
  // Внутри Telegram своей шапки нет, а значит и ссылки на админку — без этого
  // пункта администратор просто не мог попасть в панель с телефона.
  const items = user?.is_admin ? [...NAV, ADMIN_NAV] : NAV;
  return (
    <nav className="bottomnav">
      {items.map((n) => (
        <Link key={n.to} to={n.to}
              className={pathname === n.to ? 'active' : ''}>
          <span className="ico"><Icon name={n.icon} size={22} strokeWidth={pathname === n.to ? 2.4 : 1.9} /></span>
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

export function Empty({ icon, title, note, action }: {
  icon: string; title: string; note?: string;
  /** кнопка действия — чтобы из пустого экрана был выход */
  action?: { label: string; to: string };
}) {
  return (
    <div className="empty fade-in">
      <div className="empty-icon"><Icon name={icon} size={34} strokeWidth={1.6} /></div>
      <h3>{title}</h3>
      {note && <p className="subtitle">{note}</p>}
      {action && (
        <Link to={action.to} className="btn btn-primary" style={{ marginTop: 18 }}>
          {action.label}
        </Link>
      )}
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
  pending: { cls: 'badge-amber', label: 'На модерации' },
  approved: { cls: 'badge-green', label: 'Опубликовано' },
  rejected: { cls: 'badge-red', label: 'Отклонено' },
  archived: { cls: 'badge-gray', label: 'Архив' },
  sold: { cls: 'badge-gray', label: 'Продано' },
  occupied: { cls: 'badge-amber', label: 'Занято' },
};
