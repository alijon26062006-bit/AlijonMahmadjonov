import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Card } from '../api/types';
import { ProductCard } from '../components/ProductCard';
import { CardSkeletons, Empty, useAuth } from '../components/ui';

export default function FavoritesPage() {
  const user = useAuth();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<{ items: Card[] }>({
    queryKey: ['favorites'], queryFn: () => api('/api/favorites'),
    enabled: Boolean(user),
  });

  if (!user) {
    return (
      <div className="page">
        <Empty icon="heart" title="Войдите, чтобы сохранять понравившееся"
               action={{ label: 'Войти', to: '/login?back=/favorites' }} />
      </div>
    );
  }

  const items = data?.items ?? [];
  const remove = async (id: string) => {
    await api(`/api/favorites/${id}`, { method: 'DELETE' }).catch(() => null);
    qc.invalidateQueries({ queryKey: ['favorites'] });
    qc.invalidateQueries({ queryKey: ['fav-ids'] });
  };

  return (
    <div className="page fade-in">
      <h1>Избранное</h1>
      <div style={{ marginTop: 24 }}>
        {isLoading ? <CardSkeletons n={4} />
          : items.length === 0 ? (
            <Empty icon="heart" title="Пока пусто"
                   note="Нажимайте сердечко на товарах, которые понравились"
                   action={{ label: 'В каталог', to: '/catalog' }} />
          ) : (
            <div className="grid">
              {items.map((p) => (
                <ProductCard key={p.id} item={p} isFav onFav={(id) => remove(id)} />
              ))}
            </div>
          )}
      </div>
    </div>
  );
}
