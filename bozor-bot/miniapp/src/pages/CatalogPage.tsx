/** Каталог: лента + фильтры из схемы + карта. Состояние фильтров живёт в URL. */
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import type { Card } from '../api/types';
import { FilterFields, FilterSheet, countActive, useSchema } from '../components/Filters';
import { ListingCard } from '../components/ListingCard';
import { CatalogMap } from '../components/MapView';
import { CardSkeletons, Empty, useAuth, useTgBackButton } from '../components/ui';

type Page = { items: Card[]; next_cursor: string | null };

export default function CatalogPage() {
  useTgBackButton(true);
  const [params, setParams] = useSearchParams();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [view, setView] = useState<'list' | 'map'>('list');
  const user = useAuth();

  const category = params.get('category') ?? '';
  const { data: schema } = useSchema(category || undefined);

  const values = useMemo(() => Object.fromEntries(params.entries()), [params]);
  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    v ? next.set(k, v) : next.delete(k);
    setParams(next, { replace: true });
  };

  const queryString = params.toString();
  const feed = useInfiniteQuery<Page>({
    queryKey: ['catalog', queryString],
    queryFn: ({ pageParam }) => {
      const qs = new URLSearchParams(queryString);
      if (pageParam) qs.set('cursor', String(pageParam));
      return api(`/api/listings?${qs}`);
    },
    initialPageParam: '',
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const items = feed.data?.pages.flatMap((p) => p.items) ?? [];

  // избранное
  const favQuery = useQuery<{ ids: string[] }>({
    queryKey: ['fav-ids'],
    queryFn: () => api('/api/favorites/ids'),
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

  // бесконечная прокрутка
  const sentinel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && feed.hasNextPage && !feed.isFetchingNextPage) {
        feed.fetchNextPage();
      }
    }, { rootMargin: '400px' });
    io.observe(el);
    return () => io.disconnect();
  }, [feed]);

  const activeCount = countActive(schema, values);
  const reset = () => {
    const next = new URLSearchParams();
    if (category) next.set('category', category);
    setParams(next, { replace: true });
  };

  return (
    <div className="fade-in">
      <div className="searchbar">
        <input placeholder="Поиск…" defaultValue={params.get('q') ?? ''}
               onKeyDown={(e) => {
                 if (e.key === 'Enter') set('q', (e.target as HTMLInputElement).value.trim());
               }} />
        {schema && (
          <button className="btn filter-btn" onClick={() => setSheetOpen(true)}>
            ⚙️ Фильтры
            {activeCount > 0 && <span className="count">{activeCount}</span>}
          </button>
        )}
        <button className="btn" onClick={() => setView(view === 'list' ? 'map' : 'list')}>
          {view === 'list' ? '🗺' : '📃'}
        </button>
      </div>

      {schema && (
        <p className="subtitle" style={{ marginTop: 8 }}>
          {schema.emoji} {schema.title}
        </p>
      )}

      <div className="section catalog-layout">
        {schema && (
          <aside className="filters-desktop" style={{ display: undefined }}>
            <div className="only-desktop">
              <b style={{ display: 'block', marginBottom: 12 }}>Фильтры</b>
              <FilterFields schema={schema} values={values} set={set} />
              <button className="btn btn-ghost btn-block" onClick={reset}>Сбросить</button>
            </div>
          </aside>
        )}

        <div>
          {view === 'map' ? (
            <CatalogMap items={items}
                        onBounds={(b) => {
                          const next = new URLSearchParams(params);
                          for (const [k, v] of Object.entries(b)) next.set(k, v.toFixed(5));
                          setParams(next, { replace: true });
                        }} />
          ) : feed.isLoading ? (
            <CardSkeletons />
          ) : items.length === 0 ? (
            <Empty emoji="🔍" title="Ничего не найдено"
                   note="Попробуйте смягчить фильтры" />
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
        </div>
      </div>

      {sheetOpen && schema && (
        <FilterSheet schema={schema} values={values} set={set}
                     total={items.length}
                     onReset={reset}
                     onClose={() => setSheetOpen(false)} />
      )}
    </div>
  );
}
