/** Оболочка сайта: шапка, подвал, нижняя навигация и общие мелочи. */
import { useEffect, useState, useSyncExternalStore } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { getUser, isAuthed, logout, onAuthChange } from '../api/client';
import type { ShopConfig } from '../api/types';
import { Icon } from './icons';
import SearchBox from './SearchBox';

export function useAuth() {
  return useSyncExternalStore(onAuthChange, () => (isAuthed() ? getUser() : null));
}

/* ─────────────────────────── Тема ─────────────────────────── */

const THEME_KEY = 'stambul.theme';
type Theme = 'auto' | 'light' | 'dark';

export function applySavedTheme(): void {
  const saved = (localStorage.getItem(THEME_KEY) as Theme | null) ?? 'auto';
  setTheme(saved);
}

function setTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === 'auto') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', theme);
  localStorage.setItem(THEME_KEY, theme);
}

function ThemeButton() {
  const [theme, set] = useState<Theme>(
    () => (localStorage.getItem(THEME_KEY) as Theme | null) ?? 'auto');
  // Три положения по кругу: авто → светлая → тёмная. Отдельного меню ради
  // одной настройки заводить незачем.
  const next: Record<Theme, Theme> = { auto: 'light', light: 'dark', dark: 'auto' };
  const title = { auto: 'Тема: как в системе', light: 'Тема: светлая',
                  dark: 'Тема: тёмная' }[theme];
  return (
    <button className="btn btn-ghost btn-icon" title={title}
            aria-label={title}
            onClick={() => { const t = next[theme]; set(t); setTheme(t); }}>
      <Icon name="sun-moon" size={19} />
    </button>
  );
}

/* ─────────────────────────── Шапка ─────────────────────────── */

export function Header({ cfg, cartCount }: {
  cfg?: ShopConfig; cartCount: number;
}) {
  const user = useAuth();
  const shop = cfg?.shop_name ?? 'Stambul Shop';
  return (
    <header className="header">
      <div className="header-inner">
        <Link to="/" className="logo" aria-label={`${shop} — на главную`}>
          <span className="logo-mark">S</span>
          <span>{shop}</span>
        </Link>

        <div className="header-search"><SearchBox /></div>

        <div className="header-actions">
          <ThemeButton />
          <Link to="/favorites" className="btn btn-ghost btn-icon"
                aria-label="Избранное">
            <Icon name="heart" size={19} />
          </Link>
          <Link to="/cart" className="btn btn-ghost btn-icon" aria-label="Корзина">
            <Icon name="shopping-bag" size={19} />
            {cartCount > 0 && <span className="count">{cartCount}</span>}
          </Link>
          {user
            ? (
              <Link to="/profile" className="btn" aria-label="Профиль">
                <Icon name="user" size={17} />
                <span className="hide-sm">{user.name || 'Профиль'}</span>
              </Link>
            )
            : <Link to="/login" className="btn btn-primary">Войти</Link>}
        </div>
      </div>
    </header>
  );
}

/* ─────────────────────────── Нижняя навигация ─────────────────────────── */

const NAV = [
  { to: '/', icon: 'house', label: 'Главная' },
  { to: '/catalog', icon: 'search', label: 'Каталог' },
  { to: '/cart', icon: 'shopping-bag', label: 'Корзина' },
  { to: '/favorites', icon: 'heart', label: 'Избранное' },
  { to: '/profile', icon: 'user', label: 'Профиль' },
];

export function BottomNav({ cartCount }: { cartCount: number }) {
  const { pathname } = useLocation();
  return (
    <nav className="bottomnav" aria-label="Разделы">
      {NAV.map((n) => {
        const active = n.to === '/' ? pathname === '/' : pathname.startsWith(n.to);
        return (
          <Link key={n.to} to={n.to} className={active ? 'active' : ''}>
            <span className="ico">
              <Icon name={n.icon} size={21} strokeWidth={active ? 2.3 : 1.8} />
              {n.to === '/cart' && cartCount > 0 && (
                <span className="nav-badge">{cartCount}</span>
              )}
            </span>
            {n.label}
          </Link>
        );
      })}
    </nav>
  );
}

/* ─────────────────────────── Подвал ─────────────────────────── */

export function Footer({ cfg }: { cfg?: ShopConfig }) {
  // Подвал у сайта не украшение: по нему судят, настоящий магазин или нет
  const year = new Date().getFullYear();
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div>
          <Link to="/" className="logo" style={{ marginBottom: 10 }}>
            <span className="logo-mark">S</span>
            <span>{cfg?.shop_name ?? 'Stambul Shop'}</span>
          </Link>
          <p className="subtitle">{cfg?.tagline}</p>
        </div>

        <div>
          <h4>Каталог</h4>
          <ul>
            <li><Link to="/catalog?category=women_clothes">Женская одежда</Link></li>
            <li><Link to="/catalog?category=men_clothes">Мужская одежда</Link></li>
            <li><Link to="/catalog?category=shoes">Обувь</Link></li>
            <li><Link to="/catalog">Все разделы</Link></li>
          </ul>
        </div>

        <div>
          <h4>Покупателю</h4>
          <ul>
            <li><Link to="/delivery">Доставка и оплата</Link></li>
            <li><Link to="/orders">Мои заказы</Link></li>
            <li><Link to="/favorites">Избранное</Link></li>
          </ul>
        </div>

        <div>
          <h4>Связь</h4>
          <ul>
            {cfg?.support && (
              <li><a href={cfg.support} target="_blank" rel="noreferrer">Написать нам</a></li>
            )}
            {cfg?.bot_link && (
              <li><a href={cfg.bot_link} target="_blank" rel="noreferrer">Наш бот</a></li>
            )}
          </ul>
        </div>
      </div>
      <div className="footer-bottom">© {year} {cfg?.shop_name ?? 'Stambul Shop'}</div>
    </footer>
  );
}

/* ─────────────────────────── Мелочи ─────────────────────────── */

export function Empty({ icon, title, note, action }: {
  icon: string; title: string; note?: string;
  action?: { label: string; to: string };
}) {
  return (
    <div className="empty fade-in">
      <div className="empty-icon"><Icon name={icon} size={30} strokeWidth={1.6} /></div>
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

export function CardSkeletons({ n = 8 }: { n?: number }) {
  return (
    <div className="grid">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i}>
          <div className="skeleton" style={{ aspectRatio: '3 / 4' }} />
          <div className="skeleton" style={{ height: 14, margin: '10px 0 6px', borderRadius: 6 }} />
          <div className="skeleton" style={{ height: 14, width: '55%', borderRadius: 6 }} />
        </div>
      ))}
    </div>
  );
}

/** Нижний лист: на телефоне поднимается снизу, на широком экране — сбоку. */
export function Sheet({ title, onClose, children, actions }: {
  title: string; onClose: () => void;
  children: React.ReactNode; actions?: React.ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title}>
        <div className="sheet-grip" />
        <div className="row-between" style={{ marginBottom: 16 }}>
          <h2>{title}</h2>
          <button className="btn btn-ghost btn-icon" onClick={onClose}
                  aria-label="Закрыть">
            <Icon name="x" size={19} />
          </button>
        </div>
        {children}
        {actions && <div className="sheet-actions">{actions}</div>}
      </div>
    </>
  );
}

/** Короткое сообщение внизу экрана вместо диалогов «ОК». */
export function useToast() {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    if (!text) return;
    const id = setTimeout(() => setText(null), 2200);
    return () => clearTimeout(id);
  }, [text]);
  const node = text ? <div className="toast">{text}</div> : null;
  return { toast: setText, node };
}

export function signOut() {
  logout();
  window.location.href = '/';
}

export const ORDER_BADGE: Record<string, string> = {
  new: 'badge', confirmed: 'badge', paid: 'badge-green',
  shipped: 'badge', done: 'badge-green', canceled: 'badge-gray',
};
