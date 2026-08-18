import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import {
  Route, Routes, useLocation, useNavigate, useNavigationType,
} from 'react-router-dom';
import { api, bootstrapAuth, setCurrencySign } from './api/client';
import type { CartOut, ShopConfig } from './api/types';
import { BottomNav, Header, useAuth } from './components/ui';
import AdminPage from './pages/AdminPage';
import CartPage from './pages/CartPage';
import CatalogPage from './pages/CatalogPage';
import FavoritesPage from './pages/FavoritesPage';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import OrdersPage from './pages/OrdersPage';
import ProductPage from './pages/ProductPage';
import { parseStartParam } from './telegram/tg';

export default function App() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const navType = useNavigationType();
  const user = useAuth();

  // Новый экран открывается сверху, возврат — на прежнем месте: так ведут
  // себя нативные экраны Telegram.
  const scrollTop = useRef<Record<string, number>>({});
  useEffect(() => {
    const key = pathname;
    window.scrollTo({
      top: navType === 'POP' ? (scrollTop.current[key] ?? 0) : 0,
      behavior: 'auto',
    });
    return () => { scrollTop.current[key] = window.scrollY; };
  }, [pathname, navType]);

  useEffect(() => {
    (async () => {
      await bootstrapAuth();
      const target = parseStartParam();
      if (target) navigate(`/p/${target}`, { replace: true });
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { data: cfg } = useQuery<ShopConfig>({
    queryKey: ['config'], queryFn: () => api('/api/config'),
    staleTime: 10 * 60_000,
  });
  useEffect(() => { if (cfg) setCurrencySign(cfg.currency_sign); }, [cfg]);

  const { data: cart } = useQuery<CartOut>({
    queryKey: ['cart'], queryFn: () => api('/api/cart'), enabled: Boolean(user),
  });
  const count = cart?.count ?? 0;

  return (
    <div className="app">
      <Header shop={cfg?.shop_name ?? 'Магазин'} cartCount={count} />
      {/* key по маршруту — каждый экран въезжает с анимацией */}
      <div key={pathname} className="app-view">
        <Routes>
          <Route path="/" element={<HomePage cfg={cfg} />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/p/:id" element={<ProductPage />} />
          <Route path="/cart" element={<CartPage cfg={cfg} />} />
          <Route path="/favorites" element={<FavoritesPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/admin" element={<AdminPage cfg={cfg} />} />
        </Routes>
      </div>
      <BottomNav cartCount={count} />
    </div>
  );
}
