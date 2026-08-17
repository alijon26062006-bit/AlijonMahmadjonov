/** Витрина: поиск, разделы полосой, новинки. */
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Card, Group, ShopConfig } from '../api/types';
import { Icon } from '../components/icons';
import { ProductCard } from '../components/ProductCard';
import { SearchBox } from '../components/SearchBox';
import { CardSkeletons, Empty, useAuth } from '../components/ui';

type Page = { items: Card[]; has_more: boolean; page: number };

export default function HomePage({ cfg }: { cfg?: ShopConfig }) {
  const navigate = useNavigate();
  const user = useAuth();

  const { data: cats } = useQuery<{ groups: Group[] }>({
    queryKey: ['categories'], queryFn: () => api('/api/categories'),
    staleTime: 10 * 60_000,
  });

  const feed = useInfiniteQuery<Page>({
    queryKey: ['home-feed'],
    queryFn: ({ pageParam }) => api(`/api/products?sort=new&page=${pageParam}`),
    initialPageParam: 0,
    getNextPageParam: (last) => (last.has_more ? last.page + 1 : undefined),
    staleTime: 60_000,
  });
  const items = feed.data?.pages.flatMap((p) => p.items) ?? [];

  const favQuery = useQuery<{ ids: string[] }>({
    queryKey: ['fav-ids'], queryFn: () => api('/api/favorites/ids'),
    enabled: Boolean(user),
  });
  const [favs, setFavs] = useState<Set<string>>(new Set());
  useEffect(() => { if (favQuery.data) setFavs(new Set(favQuery.data.ids)); },
    [favQuery.data]);
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

  const groups = cats?.groups ?? [];
  const free = cfg?.delivery.free_from ?? 0;

  return (
    <div className="fade-in">
      <div className="section">
        <h1 className="section-title">{cfg?.shop_name ?? 'Магазин'}</h1>
        {cfg?.tagline && <p className="subtitle" style={{ marginBottom: 10 }}>
          {cfg.tagline}</p>}
        <SearchBox placeholder="Платье, кроссовки, сервиз…"
                   onSearch={(q) => navigate(
                     q ? `/catalog?q=${encodeURIComponent(q)}` : '/catalog')} />
      </div>

      {free > 0 && (
        <div className="promo">
          <Icon name="truck" size={18} />
          Доставка бесплатно при заказе от {free.toLocaleString('ru-RU')} ₸
        </div>
      )}

      {groups.map((g) => (
        <section key={g.title} className="dir-block">
          <div className="dir-head">{g.title}</div>
          <div className="cat-strip">
            {g.categories.map((c) => (
              <Link key={c.slug} to={`/catalog?category=${c.slug}`}
                    className="cat-pill">
                <span className="icon-wrap tone-green">
                  <Icon name={c.icon} size={20} />
                </span>
                <span className="cat-pill-label">{c.title}</span>
              </Link>
            ))}
          </div>
        </section>
      ))}

      <section className="section">
        <h2 className="section-title">Новинки</h2>
        {feed.isLoading ? (
          <CardSkeletons />
        ) : items.length === 0 ? (
          <Empty icon="store" title="Товаров пока нет"
                 note="Загляните позже — витрина скоро наполнится" />
        ) : (
          <>
            <div className="grid">
              {items.map((item) => (
                <ProductCard key={item.id} item={item}
                             isFav={favs.has(item.id)}
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
