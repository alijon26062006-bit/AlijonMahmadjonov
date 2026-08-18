/** Каталог раздела: поиск, сортировка, фильтры по полям схемы. */
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import type { Card, CategorySchema } from '../api/types';
import { Icon } from '../components/icons';
import { ProductCard } from '../components/ProductCard';
import { SearchBox } from '../components/SearchBox';
import { CardSkeletons, Empty, useAuth, useTgBackButton } from '../components/ui';

type Page = { items: Card[]; has_more: boolean; page: number };

const SORTS = [
  ['new', 'Новинки'], ['cheap', 'Сначала дешёвые'],
  ['expensive', 'Сначала дорогие'], ['popular', 'Популярные'],
];

export default function CatalogPage() {
  useTgBackButton(true);
  const [params, setParams] = useSearchParams();
  const [sheet, setSheet] = useState(false);
  const user = useAuth();

  const category = params.get('category') ?? '';
  const { data: schema } = useQuery<CategorySchema>({
    queryKey: ['schema', category],
    queryFn: () => api(`/api/categories/${category}`),
    enabled: Boolean(category), staleTime: 5 * 60_000,
  });

  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    v ? next.set(k, v) : next.delete(k);
    setParams(next, { replace: true });
  };

  const qs = params.toString();
  const feed = useInfiniteQuery<Page>({
    queryKey: ['catalog', qs],
    queryFn: ({ pageParam }) => {
      const p = new URLSearchParams(qs);
      p.set('page', String(pageParam));
      return api(`/api/products?${p}`);
    },
    initialPageParam: 0,
    getNextPageParam: (last) => (last.has_more ? last.page + 1 : undefined),
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

  const activeCount = useMemo(() => {
    let n = 0;
    for (const f of schema?.fields ?? []) if (params.get(f.key)) n += 1;
    if (params.get('in_stock')) n += 1;
    if (params.get('size')) n += 1;
    return n;
  }, [schema, params]);

  const sizes = useMemo(
    () => (schema?.size_scales ?? []).flatMap((s) => s.sizes), [schema]);

  return (
    <div className="fade-in">
      <div className="searchbar sticky-search">
        <SearchBox value={params.get('q') ?? ''} placeholder="Поиск"
                   onSearch={(q) => set('q', q)}>
          {schema && (
            <button className="btn filter-btn" onClick={() => setSheet(true)}>
              <Icon name="sliders-horizontal" size={17} />
              {activeCount > 0 && <span className="count">{activeCount}</span>}
            </button>
          )}
        </SearchBox>
      </div>

      <div className="chips" style={{ marginTop: 10 }}>
        {SORTS.map(([v, l]) => (
          <button key={v}
                  className={`chip ${(params.get('sort') ?? 'new') === v ? 'on' : ''}`}
                  onClick={() => set('sort', v)}>{l}</button>
        ))}
      </div>

      {schema && (
        <p className="subtitle" style={{ marginTop: 10, display: 'flex',
                                         alignItems: 'center', gap: 6 }}>
          <Icon name={schema.icon} size={15} /> {schema.title}
        </p>
      )}

      <div className="section">
        {feed.isLoading ? <CardSkeletons />
          : items.length === 0 ? (
            <Empty icon="search" title="Ничего не найдено"
                   note="Попробуйте убрать фильтры или другой запрос"
                   action={{ label: 'Все разделы', to: '/' }} />
          ) : (
            <>
              <div className="grid">
                {items.map((p) => (
                  <ProductCard key={p.id} item={p} isFav={favs.has(p.id)}
                               onFav={user ? toggleFav : undefined} />
                ))}
              </div>
              <div ref={sentinel} />
              {feed.isFetchingNextPage && <CardSkeletons n={2} />}
            </>
          )}
      </div>

      {sheet && schema && (
        <div className="sheet-overlay" onClick={() => setSheet(false)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h2 className="section-title">Фильтры</h2>

            <div className="field">
              <span className="field-label">Наличие</span>
              <div className="chips">
                <button className={`chip ${params.get('in_stock') ? 'on' : ''}`}
                        onClick={() => set('in_stock', params.get('in_stock') ? '' : '1')}>
                  Только в наличии
                </button>
              </div>
            </div>

            {sizes.length > 0 && (
              <div className="field">
                <span className="field-label">Размер</span>
                <div className="chips">
                  {sizes.map((s) => (
                    <button key={s}
                            className={`chip ${params.get('size') === s ? 'on' : ''}`}
                            onClick={() => set('size', params.get('size') === s ? '' : s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {schema.fields.filter((f) => f.filter === 'multiselect' && f.options)
              .map((f) => (
                <div key={f.key} className="field">
                  <span className="field-label">{f.label}</span>
                  <div className="chips">
                    {f.options!.map((o) => (
                      <button key={o}
                              className={`chip ${params.get(f.key) === o ? 'on' : ''}`}
                              onClick={() => set(f.key, params.get(f.key) === o ? '' : o)}>
                        {o}
                      </button>
                    ))}
                  </div>
                </div>
              ))}

            <div className="field">
              <span className="field-label">Цена, ₸</span>
              <div className="range-row">
                <input inputMode="numeric" placeholder="от"
                       defaultValue={params.get('price_min') ?? ''}
                       onBlur={(e) => set('price_min', e.target.value.trim())} />
                <input inputMode="numeric" placeholder="до"
                       defaultValue={params.get('price_max') ?? ''}
                       onBlur={(e) => set('price_max', e.target.value.trim())} />
              </div>
            </div>

            <button className="btn btn-primary btn-block"
                    onClick={() => setSheet(false)}>Показать</button>
            <button className="btn btn-ghost btn-block" style={{ marginTop: 8 }}
                    onClick={() => {
                      const next = new URLSearchParams();
                      if (category) next.set('category', category);
                      setParams(next, { replace: true });
                    }}>Сбросить</button>
          </div>
        </div>
      )}
    </div>
  );
}
