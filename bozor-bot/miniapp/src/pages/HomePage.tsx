/** Главная: категории + перемешанная лента с меткой категории у карточек. */
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Card, Direction } from '../api/types';
import { CATEGORY_ICON, DIRECTION_ICON, Icon } from '../components/icons';
import { ListingCard } from '../components/ListingCard';
import { CardSkeletons, Empty, useAuth } from '../components/ui';

type FeedPage = { items: Card[]; has_more: boolean };

export default function HomePage() {
  const navigate = useNavigate();
  const user = useAuth();
  const [showAllCats, setShowAllCats] = useState(false);

  const { data: cats } = useQuery<{ directions: Direction[] }>({
    queryKey: ['categories'],
    queryFn: () => api('/api/categories'),
    staleTime: 10 * 60_000,
  });

  const feed = useInfiniteQuery<FeedPage>({
    queryKey: ['feed'],
    queryFn: ({ pageParam }) => api(`/api/feed?limit=20&offset=${pageParam}`),
    initialPageParam: 0,
    getNextPageParam: (last, all) =>
      last.has_more ? all.reduce((n, p) => n + p.items.length, 0) : undefined,
    staleTime: 60_000,
  });
  const items = feed.data?.pages.flatMap((p) => p.items) ?? [];

  // избранное
  const favQuery = useQuery<{ ids: string[] }>({
    queryKey: ['fav-ids'], queryFn: () => api('/api/favorites/ids'),
    enabled: Boolean(user),
  });
  const [favs, setFavs] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (favQuery.data) setFavs(new Set(favQuery.data.ids));
  }, [favQuery.data]);
  const toggleFav = async (id: string, next: boolean) => {
    setFavs((prev) => {
      const s = new Set(prev);
      next ? s.add(id) : s.delete(id);
      return s;
    });
    try {
      await api(`/api/favorites/${id}`, { method: next ? 'PUT' : 'DELETE' });
    } catch { /* оптимистично */ }
  };

  // догрузка при прокрутке
  const sentinel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver((e) => {
      if (e[0].isIntersecting && feed.hasNextPage && !feed.isFetchingNextPage) {
        feed.fetchNextPage();
      }
    }, { rootMargin: '400px' });
    io.observe(el);
    return () => io.disconnect();
  }, [feed]);

  const directions = cats?.directions ?? [];
  const visible = showAllCats ? directions : directions.slice(0, 2);

  return (
    <div className="fade-in">
      <div className="section">
        <h1 className="section-title">Что ищете?</h1>
        <div className="searchbar">
          <input placeholder="Поиск: Camry, квартира, дисплей…"
                 onKeyDown={(e) => {
                   if (e.key === 'Enter') {
                     const q = (e.target as HTMLInputElement).value.trim();
                     navigate(q ? `/catalog?q=${encodeURIComponent(q)}` : '/catalog');
                   }
                 }} />
        </div>
      </div>

      {visible.map((d) => {
        const dir = DIRECTION_ICON[d.slug] ?? DIRECTION_ICON.parts;
        return (
          <section key={d.slug} className="dir-block">
            <div className="dir-head">
              <span className={`dir-ico ${dir.tone}`}>
                <Icon name={dir.icon} size={17} strokeWidth={2.2} />
              </span>
              {d.title}
            </div>
            <div className="cat-grid">
              {d.categories.map((c) => (
                <Link key={c.slug} to={`/catalog?category=${c.slug}`} className="cat-tile">
                  <span className={`icon-wrap ${dir.tone}`}>
                    <Icon name={CATEGORY_ICON[c.slug] ?? dir.icon} size={21} />
                  </span>
                  {c.title}
                </Link>
              ))}
            </div>
          </section>
        );
      })}

      {directions.length > 2 && (
        <button className="btn btn-ghost btn-block" style={{ marginTop: 12 }}
                onClick={() => setShowAllCats(!showAllCats)}>
          {showAllCats ? 'Свернуть категории' : 'Показать все категории'}
        </button>
      )}

      <section className="section">
        <h2 className="section-title">Свежие объявления</h2>
        {feed.isLoading ? (
          <CardSkeletons />
        ) : items.length === 0 ? (
          <Empty icon="archive" title="Объявлений пока нет"
                 note="Будьте первым — подайте объявление"
                 action={{ label: 'Подать объявление', to: '/post' }} />
        ) : (
          <>
            <div className="grid">
              {items.map((item) => (
                <ListingCard key={item.public_id} item={item}
                             isFav={favs.has(item.public_id)}
                             onFav={user ? toggleFav : undefined} />
              ))}
            </div>
            <div ref={sentinel} />
            {feed.isFetchingNextPage && <CardSkeletons n={2} />}
          </>
        )}
      </section>
    </div>
  );
}
