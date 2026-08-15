import { Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import { BottomNav, Header } from './components/ui';
import CatalogPage from './pages/CatalogPage';
import FavoritesPage from './pages/FavoritesPage';
import HomePage from './pages/HomePage';
import ListingPage from './pages/ListingPage';
import LoginPage from './pages/LoginPage';
import MyListingsPage from './pages/MyListingsPage';
import PostPage from './pages/PostPage';
import { bootstrapAuth } from './api/client';
import { parseStartParam } from './telegram/tg';

export default function App() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => {
    (async () => {
      await bootstrapAuth();
      // Переход из поста в канале: сразу на карточку
      const target = parseStartParam();
      if (target) navigate(`/listing/${target}`, { replace: true });
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="app">
      <Header />
      {/* key по маршруту — каждый экран въезжает с анимацией, как в Telegram */}
      <div key={pathname} className="app-view">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/listing/:id" element={<ListingPage />} />
        <Route path="/favorites" element={<FavoritesPage />} />
        <Route path="/my" element={<MyListingsPage />} />
        <Route path="/post" element={<PostPage />} />
        <Route path="/login" element={<LoginPage />} />
      </Routes>
      </div>
      <BottomNav />
    </div>
  );
}
