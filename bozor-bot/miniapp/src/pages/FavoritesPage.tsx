import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Card } from '../api/types';
import { ListingCard } from '../components/ListingCard';
import { CardSkeletons, Empty, useAuth, useTgBackButton } from '../components/ui';

export default function FavoritesPage() {
  useTgBackButton(true);
  const user = useAuth();
  const { data, isLoading, refetch } = useQuery<{ items: Card[] }>({
    queryKey: ['favorites'],
    queryFn: () => api('/api/favorites'),
    enabled: Boolean(user),
  });

  if (!user) {
    return <Empty icon="lock" title="Нужен вход"
                  note="Избранное привязано к вашему Telegram-аккаунту"
                  action={{ label: 'Войти', to: '/login' }} />;
  }
  if (isLoading) return <div className="section"><CardSkeletons /></div>;
  const items = data?.items ?? [];
  if (!items.length) {
    return <Empty icon="heart" title="Пока пусто"
                  note="Нажимайте на сердечко в каталоге — объявления появятся здесь"
                  action={{ label: 'В каталог', to: '/catalog' }} />;
  }
  return (
    <div className="section fade-in">
      <h1 className="section-title">Избранное</h1>
      <div className="grid">
        {items.map((item) => (
          <ListingCard key={item.public_id} item={item} isFav
                       onFav={async (id) => {
                         await api(`/api/favorites/${id}`, { method: 'DELETE' });
                         refetch();
                       }} />
        ))}
      </div>
    </div>
  );
}
