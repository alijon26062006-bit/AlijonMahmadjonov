import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import {
  Navigate, Route, Routes, useLocation, useNavigationType,
} from 'react-router-dom';
import { api, bootstrapAuth, setCurrencySign } from './api/client';
import type { CartOut, ShopConfig } from './api/types';
import { BottomNav, Footer, Header, useAuth } from './components/ui';
import AdminPage from './pages/AdminPage';
import CartPage from './pages/CartPage';
import CatalogPage from './pages/CatalogPage';
import DeliveryPage from './pages/DeliveryPage';
import FavoritesPage from './pages/FavoritesPage';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import OrdersPage from './pages/OrdersPage';
import ProductPage from './pages/ProductPage';
import ProfilePage from './pages/ProfilePage';
import VerifyPage from './pages/VerifyPage';
import WelcomePage, { welcomeSeen } from './pages/WelcomePage';

export default function App() {
  const { pathname, search } = useLocation();
  const navType = useNavigationType();
  const user = useAuth();

  // Новая страница открывается сверху, возврат — на прежнем месте
  const scrollTop = useRef<Record<string, number>>({});
  useEffect(() => {
    const key = pathname + search;
    window.scrollTo({
      top: navType === 'POP' ? (scrollTop.current[key] ?? 0) : 0,
      behavior: 'auto',
    });
    return () => { scrollTop.current[key] = window.scrollY; };
  }, [pathname, search, navType]);

  useEffect(() => { bootstrapAuth(); }, []);

  const { data: cfg } = useQuery<ShopConfig>({
    queryKey: ['config'], queryFn: () => api('/api/config'),
    staleTime: 10 * 60_000,
  });
  useEffect(() => { if (cfg) setCurrencySign(cfg.currency_sign); }, [cfg]);

  const { data: cart } = useQuery<CartOut>({
    queryKey: ['cart'], queryFn: () => api('/api/cart'), enabled: Boolean(user),
  });
  const count = cart?.count ?? 0;

  // Знакомство — только для тех, кто здесь впервые и ещё не вошёл
  const firstVisit = pathname === '/' && !user && !welcomeSeen();
  const bare = pathname.startsWith('/login') || pathname === '/welcome';

  if (firstVisit) return <Navigate to="/welcome" replace />;

  return (
    <div className="app">
      {!bare && <Header cfg={cfg} cartCount={count} />}
      <div key={pathname} className="app-view">
        <Routes>
          <Route path="/welcome" element={<WelcomePage />} />
          <Route path="/" element={<HomePage cfg={cfg} />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/p/:id" element={<ProductPage />} />
          <Route path="/cart" element={<CartPage cfg={cfg} />} />
          <Route path="/favorites" element={<FavoritesPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/profile" element={<ProfilePage cfg={cfg} />} />
          <Route path="/delivery" element={<DeliveryPage cfg={cfg} />} />
          <Route path="/login" element={<LoginPage cfg={cfg} />} />
          <Route path="/login/code" element={<VerifyPage />} />
          <Route path="/admin" element={<AdminPage cfg={cfg} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      {!bare && <Footer cfg={cfg} />}
      {!bare && <BottomNav cartCount={count} />}
    </div>
  );
}
