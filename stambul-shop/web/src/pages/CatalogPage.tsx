/** Каталог: сетка, фильтры и сортировка.

    Всё состояние живёт в адресе страницы — подборку можно переслать
    ссылкой, а «назад» возвращает ровно то, что человек видел.
*/
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import type { Card, CategorySchema, Group } from '../api/types';
import { Icon } from '../components/icons';
import { ProductCard } from '../components/ProductCard';
import SearchBox from '../components/SearchBox';
import { CardSkeletons, Empty, Sheet, useAuth } from '../components/ui';
import { useFavorites } from '../hooks/useFavorites';

type Page = { items: Card[]; has_more: boolean; page: number };

const SORTS: [string, string][] = [
  ['new', 'Новинки'], ['popular', 'Популярные'],
  ['cheap', 'Сначала дешёвые'], ['expensive', 'Сначала дорогие'],
];

export default function CatalogPage() {
  const [params, setParams] = useSearchParams();
  const [sheet, setSheet] = useState(false);
  const user = useAuth();
  const { ids: favs, toggle } = useFavorites(Boolean(user));

  const category = params.get('category') ?? '';

  const { data: cats } = useQuery<{ groups: Group[] }>({
    queryKey: ['categories'], queryFn: () => api('/api/categories'),
    staleTime: 10 * 60_000,
  });
  const { data: schema } = useQuery<CategorySchema>({
    queryKey: ['schema', category],
    queryFn: () => api(`/api/categories/${category}`),
    enabled: Boolean(category), staleTime: 5 * 60_000,
  });

  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    next.delete('page');
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
    for (const k of ['in_stock', 'size', 'price_min', 'price_max']) {
      if (params.get(k)) n += 1;
    }
    return n;
  }, [schema, params]);

  const sizes = useMemo(
    () => (schema?.size_scales ?? []).flatMap((s) => s.sizes), [schema]);
  const categories = (cats?.groups ?? []).flatMap((g) => g.categories);

  const reset = () => {
    const next = new URLSearchParams();
    if (category) next.set('category', category);
    if (params.get('q')) next.set('q', params.get('q')!);
    setParams(next, { replace: true });
  };

  const filters = (
    <>
      <div className="field">
        <label>Наличие</label>
        <div className="chips">
          <button className={`chip ${params.get('in_stock') ? 'active' : ''}`}
                  onClick={() => set('in_stock', params.get('in_stock') ? '' : '1')}>
            Только в наличии
          </button>
        </div>
      </div>

      {sizes.length > 0 && (
        <div className="field">
          <label>Размер</label>
          <div className="chips" style={{ flexWrap: 'wrap' }}>
            {sizes.map((s) => (
              <button key={s}
                      className={`chip ${params.get('size') === s ? 'active' : ''}`}
                      onClick={() => set('size', params.get('size') === s ? '' : s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {(schema?.fields ?? [])
        .filter((f) => f.filter === 'multiselect' && f.options)
        .map((f) => (
          <div key={f.key} className="field">
            <label>{f.label}</label>
            <div className="chips" style={{ flexWrap: 'wrap' }}>
              {f.options!.map((o) => (
                <button key={o}
                        className={`chip ${params.get(f.key) === o ? 'active' : ''}`}
                        onClick={() => set(f.key, params.get(f.key) === o ? '' : o)}>
                  {o}
                </button>
              ))}
            </div>
          </div>
        ))}

      <div className="field">
        <label>Цена</label>
        <div className="row">
          <input className="input" inputMode="numeric" placeholder="от"
                 defaultValue={params.get('price_min') ?? ''}
                 onBlur={(e) => set('price_min', e.target.value.trim())} />
          <input className="input" inputMode="numeric" placeholder="до"
                 defaultValue={params.get('price_max') ?? ''}
                 onBlur={(e) => set('price_max', e.target.value.trim())} />
        </div>
      </div>
    </>
  );

  return (
    <div className="page fade-in">
      <div className="only-sm" style={{ marginBottom: 16 }}>
        <SearchBox initial={params.get('q') ?? ''} />
      </div>

      <div className="row-between" style={{ flexWrap: 'wrap', gap: 12 }}>
        <h1>{schema?.title ?? (params.get('q') ? `«${params.get('q')}»` : 'Каталог')}</h1>
        <div className="row">
          <select className="select" style={{ width: 'auto' }}
                  aria-label="Сортировка"
                  value={params.get('sort') ?? 'new'}
                  onChange={(e) => set('sort', e.target.value)}>
            {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button className="btn" onClick={() => setSheet(true)}>
            <Icon name="sliders-horizontal" size={17} />
            Фильтры
            {activeCount > 0 && <span className="count">{activeCount}</span>}
          </button>
        </div>
      </div>

      <div className="chips" style={{ marginTop: 16 }}>
        <button className={`chip ${!category ? 'active' : ''}`}
                onClick={() => set('category', '')}>Все</button>
        {categories.map((c) => (
          <button key={c.slug}
                  className={`chip ${category === c.slug ? 'active' : ''}`}
                  onClick={() => set('category', c.slug)}>
            <Icon name={c.icon} size={15} /> {c.title}
          </button>
        ))}
      </div>

      <div style={{ marginTop: 24 }}>
        {feed.isLoading ? <CardSkeletons />
          : items.length === 0 ? (
            <Empty icon="search" title="Ничего не нашлось"
                   note={activeCount > 0
                     ? 'Попробуйте убрать часть фильтров'
                     : 'Попробуйте другой запрос'}
                   action={{ label: 'Весь каталог', to: '/catalog' }} />
          ) : (
            <>
              <div className="grid">
                {items.map((p) => (
                  <ProductCard key={p.id} item={p} isFav={favs.has(p.id)}
                               onFav={user ? toggle : undefined} />
                ))}
              </div>
              <div ref={sentinel} />
              {feed.isFetchingNextPage && (
                <div style={{ marginTop: 16 }}><CardSkeletons n={4} /></div>
              )}
            </>
          )}
      </div>

      {sheet && (
        <Sheet title="Фильтры" onClose={() => setSheet(false)}
               actions={(
                 <>
                   <button className="btn btn-block" onClick={reset}>Сбросить</button>
                   <button className="btn btn-primary btn-block"
                           onClick={() => setSheet(false)}>
                     Показать{items.length ? ` (${items.length}${feed.hasNextPage ? '+' : ''})` : ''}
                   </button>
                 </>
               )}>
          <div className="stack">{filters}</div>
        </Sheet>
      )}
    </div>
  );
}
