/** Главная: баннер, разделы, ленты новинок и того, что заканчивается. */
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { api, fmtPrice } from '../api/client';
import type { Card, Group, ShopConfig } from '../api/types';
import { Icon } from '../components/icons';
import { ProductCard } from '../components/ProductCard';
import SearchBox from '../components/SearchBox';
import { CardSkeletons, Empty, useAuth } from '../components/ui';
import { useFavorites } from '../hooks/useFavorites';

type Page = { items: Card[]; has_more: boolean; page: number };

export default function HomePage({ cfg }: { cfg?: ShopConfig }) {
  const user = useAuth();
  const { ids: favs, toggle } = useFavorites(Boolean(user));

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

  const categories = (cats?.groups ?? []).flatMap((g) => g.categories);
  const sale = items
    .filter((p) => p.old_price && p.old_price > p.price && p.in_stock > 0)
    .slice(0, 10);
  const free = cfg?.delivery.free_from ?? 0;

  return (
    <div className="page fade-in">
      {/* Поиск на телефоне живёт здесь: в шапке для него нет места */}
      <div style={{ marginBottom: 20 }} className="only-sm"><SearchBox /></div>

      <section style={{
        border: '1px solid var(--border)', borderRadius: 18,
        padding: '40px var(--pad)', background: 'var(--surface)',
      }}>
        <div className="eyebrow">{cfg?.shop_name ?? 'Stambul Shop'}</div>
        <h1 style={{ marginTop: 10, maxWidth: '14ch' }}>
          {cfg?.tagline ?? 'Одежда, обувь и всё для дома'}
        </h1>
        <div className="row" style={{ marginTop: 24, flexWrap: 'wrap' }}>
          <Link to="/catalog" className="btn btn-primary btn-lg">
            Смотреть каталог
          </Link>
          {free > 0 && (
            <span className="subtitle">
              <Icon name="truck" size={15} /> Доставка бесплатно
              от {fmtPrice(free)}
            </span>
          )}
        </div>
      </section>

      {categories.length > 0 && (
        <div className="chips" style={{ marginTop: 24 }}>
          {categories.map((c) => (
            <Link key={c.slug} to={`/catalog?category=${c.slug}`} className="chip">
              <Icon name={c.icon} size={16} /> {c.title}
            </Link>
          ))}
        </div>
      )}

      {/* Лента скидок собирается из уже загруженной ленты: отдельный запрос
          ради тех же товаров был бы лишним */}
      {sale.length >= 3 && (
        <section className="section">
          <div className="section-head">
            <h2>Со скидкой</h2>
            <Link to="/catalog">Весь каталог →</Link>
          </div>
          <div className="rail">
            {sale.map((p) => (
              <ProductCard key={p.id} item={p} isFav={favs.has(p.id)}
                           onFav={user ? toggle : undefined} />
            ))}
          </div>
        </section>
      )}

      <section className="section">
        <div className="section-head">
          <h2>Новинки</h2>
          <Link to="/catalog?sort=new">Все →</Link>
        </div>
        {feed.isLoading ? <CardSkeletons />
          : items.length === 0 ? (
            <Empty icon="store" title="Товаров пока нет"
                   note="Загляните позже — витрина скоро наполнится" />
          ) : (
            <>
              <div className="grid">
                {items.map((item) => (
                  <ProductCard key={item.id} item={item} isFav={favs.has(item.id)}
                               onFav={user ? toggle : undefined} />
                ))}
              </div>
              <div ref={sentinel} />
              {feed.isFetchingNextPage && (
                <div style={{ marginTop: 16 }}><CardSkeletons n={4} /></div>
              )}
            </>
          )}
      </section>
    </div>
  );
}
