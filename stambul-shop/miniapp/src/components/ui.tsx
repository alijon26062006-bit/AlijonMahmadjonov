/** Общие мелочи: шапка, нижняя навигация, пустые состояния, скелетоны. */
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useSyncExternalStore } from 'react';
import { getUser, isAuthed, onAuthChange } from '../api/client';
import { inTelegram, tg, toggleTheme } from '../telegram/tg';
import { Icon } from './icons';

export function useAuth() {
  return useSyncExternalStore(onAuthChange, () => (isAuthed() ? getUser() : null));
}

export function Header({ shop, cartCount }: { shop: string; cartCount: number }) {
  const user = useAuth();
  if (inTelegram) return null;
  return (
    <header className="header">
      <Link to="/" className="logo">
        <span className="logo-mark">S</span> {shop}
      </Link>
      <div className="header-actions">
        <button className="btn btn-ghost" onClick={toggleTheme} title="Тема">
          <Icon name="sun-moon" size={19} />
        </button>
        <Link to="/cart" className="btn">
          <Icon name="shopping-bag" size={17} />
          {cartCount > 0 && <span className="count">{cartCount}</span>}
        </Link>
        {user?.is_admin && (
          <Link to="/admin" className="btn" title="Управление">
            <Icon name="sliders-horizontal" size={17} />
          </Link>
        )}
        {user
          ? <Link to="/orders" className="btn">{user.first_name || 'Профиль'}</Link>
          : <Link to="/login" className="btn">Войти</Link>}
      </div>
    </header>
  );
}

const NAV = [
  { to: '/', icon: 'house', label: 'Магазин' },
  { to: '/catalog', icon: 'search', label: 'Каталог' },
  { to: '/cart', icon: 'shopping-bag', label: 'Корзина' },
  { to: '/favorites', icon: 'heart', label: 'Избранное' },
  { to: '/orders', icon: 'package', label: 'Заказы' },
];
const ADMIN_NAV = { to: '/admin', icon: 'sliders-horizontal', label: 'Товары' };

export function BottomNav({ cartCount }: { cartCount: number }) {
  const { pathname } = useLocation();
  const user = useAuth();
  // Внутри Telegram своей шапки нет — без этого пункта владелец не попал бы
  // в управление с телефона
  const items = user?.is_admin ? [...NAV, ADMIN_NAV] : NAV;
  return (
    <nav className="bottomnav">
      {items.map((n) => (
        <Link key={n.to} to={n.to} className={pathname === n.to ? 'active' : ''}>
          <span className="ico">
            <Icon name={n.icon} size={22}
                  strokeWidth={pathname === n.to ? 2.4 : 1.9} />
            {n.to === '/cart' && cartCount > 0 && (
              <span className="nav-badge">{cartCount}</span>
            )}
          </span>
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

export const ORDER_BADGE: Record<string, string> = {
  new: 'badge-amber', confirmed: 'badge-blue', paid: 'badge-green',
  shipped: 'badge-blue', done: 'badge-green', canceled: 'badge-gray',
};
