/** Карточка товара: галерея, размер и цвет, кнопка в корзину. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, fmtPrice, photoUrl } from '../api/client';
import type { Card, ProductDetail } from '../api/types';
import { Icon } from '../components/icons';
import { ProductCard } from '../components/ProductCard';
import { Empty, useAuth, useToast } from '../components/ui';
import { useFavorites } from '../hooks/useFavorites';

export default function ProductPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const user = useAuth();
  const { ids: favs, toggle } = useFavorites(Boolean(user));
  const { toast, node } = useToast();

  const [size, setSize] = useState<string | null>(null);
  const [color, setColor] = useState<string | null>(null);
  const [added, setAdded] = useState(false);
  const [error, setError] = useState('');
  const [shot, setShot] = useState(0);
  const [broken, setBroken] = useState<Set<number>>(new Set());
  const track = useRef<HTMLDivElement>(null);

  const { data: item, isLoading } = useQuery<ProductDetail>({
    queryKey: ['product', id], queryFn: () => api(`/api/products/${id}`),
  });
  const { data: similar } = useQuery<{ items: Card[] }>({
    queryKey: ['similar', id], queryFn: () => api(`/api/products/${id}/similar`),
    enabled: Boolean(item),
  });

  // Заголовок вкладки и описание меняем под товар: так выглядит вкладка в
  // браузере и так его видит поисковик, пришедший по ссылке
  useEffect(() => {
    if (!item) return;
    const prev = document.title;
    document.title = `${item.title} — ${fmtPrice(item.price)}`;
    return () => { document.title = prev; };
  }, [item]);

  useEffect(() => {
    const el = track.current;
    if (!el) return;
    const onScroll = () => setShot(Math.round(el.scrollLeft / (el.clientWidth || 1)));
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, [item]);

  // Что есть на складе, считаем по вариантам. Кончившийся размер не прячем,
  // а зачёркиваем: человек должен видеть, что вещь такая бывает.
  const sizes = useMemo(() => {
    const map = new Map<string, number>();
    for (const v of item?.variants ?? []) {
      map.set(v.size, (map.get(v.size) ?? 0) + v.stock);
    }
    return [...map.entries()].map(([value, stock]) => ({ value, stock }));
  }, [item]);

  const colors = useMemo(() => {
    const map = new Map<string, number>();
    for (const v of item?.variants ?? []) {
      if (size !== null && v.size !== size) continue;
      map.set(v.color, (map.get(v.color) ?? 0) + v.stock);
    }
    return [...map.entries()].map(([value, stock]) => ({ value, stock }));
  }, [item, size]);

  const chosen = useMemo(() => {
    if (!item) return null;
    const fit = item.variants.filter(
      (v) => (size === null || v.size === size)
          && (color === null || v.color === color));
    return fit.length === 1 ? fit[0] : null;
  }, [item, size, color]);

  const needsSize = sizes.length > 1 || (sizes[0]?.value ?? '') !== '';
  const needsColor = colors.length > 1 || (colors[0]?.value ?? '') !== '';

  // Выбор из одного варианта — не выбор: проставляем сами
  useEffect(() => {
    const one = sizes.filter((s) => s.stock > 0);
    if (size === null && one.length === 1) setSize(one[0].value);
  }, [sizes, size]);
  useEffect(() => {
    const one = colors.filter((c) => c.stock > 0);
    if (color === null && one.length === 1) setColor(one[0].value);
  }, [colors, color]);

  const addToCart = useMutation({
    mutationFn: () => api('/api/cart', {
      method: 'POST',
      body: JSON.stringify({ variant_id: chosen!.id, qty: 1 }),
    }),
    onSuccess: () => {
      setAdded(true);
      setError('');
      qc.invalidateQueries({ queryKey: ['cart'] });
    },
    onError: (e: unknown) => {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { navigate(`/login?back=/p/${id}`); return; }
      setError(err.message || 'Не получилось добавить');
    },
  });

  if (isLoading) {
    return (
      <div className="page">
        <div className="product">
          <div className="skeleton" style={{ aspectRatio: '3 / 4' }} />
          <div className="stack">
            <div className="skeleton" style={{ height: 28, borderRadius: 6 }} />
            <div className="skeleton" style={{ height: 20, width: '40%', borderRadius: 6 }} />
            <div className="skeleton" style={{ height: 120, borderRadius: 10 }} />
          </div>
        </div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="page">
        <Empty icon="search" title="Товар не найден"
               note="Возможно, он снят с продажи"
               action={{ label: 'В каталог', to: '/catalog' }} />
      </div>
    );
  }

  const out = item.in_stock === 0;
  const price = chosen ? chosen.price : item.price;
  const discount = item.old_price && item.old_price > price
    ? Math.round((1 - price / item.old_price) * 100) : 0;

  return (
    <div className="page fade-in">
      <button className="btn btn-ghost" onClick={() => navigate(-1)}
              style={{ marginBottom: 16 }}>
        <Icon name="arrow-left" size={17} /> Назад
      </button>

      <div className="product">
        <div>
          <div className="gallery">
            <div className="gallery-track" ref={track}>
              {item.photos.length
                ? item.photos.map((p, i) => (broken.has(i)
                    ? <div key={i} className="gallery-empty">
                        <Icon name="image" size={40} strokeWidth={1.2} />
                      </div>
                    // не подгрузилась — рисуем ту же заглушку, что и в
                    // каталоге: пустое серое поле читается как поломка
                    : <img key={i} src={photoUrl(p.full)} alt={item.title}
                           loading={i > 0 ? 'lazy' : undefined}
                           onError={() => setBroken((b) => new Set(b).add(i))} />
                  ))
                : <div className="gallery-empty">
                    <Icon name="image" size={40} strokeWidth={1.2} />
                  </div>}
            </div>
            {item.photos.length > 1 && (
              <div className="dots" aria-hidden="true">
                {item.photos.map((_, i) => <i key={i} className={i === shot ? 'on' : ''} />)}
              </div>
            )}
          </div>
        </div>

        <div className="product-info stack">
          <div>
            <div className="row" style={{ alignItems: 'baseline' }}>
              <span className="price" style={{ fontSize: 26, fontWeight: 700,
                                               letterSpacing: '-.02em' }}>
                {fmtPrice(price)}
              </span>
              {discount > 0 && (
                <>
                  <span className="old" style={{ color: 'var(--text-3)',
                                                 textDecoration: 'line-through' }}>
                    {fmtPrice(item.old_price!)}
                  </span>
                  <span className="badge">−{discount}%</span>
                </>
              )}
            </div>
            <h1 style={{ fontSize: 22, lineHeight: '28px', marginTop: 8 }}>
              {item.title}
            </h1>
            <p className="subtitle" style={{ marginTop: 6 }}>
              {[item.brand, item.category_title].filter(Boolean).join(' · ')}
            </p>
          </div>

          {out && (
            <div className="notice">
              <b>Товар закончился.</b> Напишите нам — подскажем, когда будет завоз.
            </div>
          )}

          {!out && needsSize && (
            <div className="field">
              <label>Размер</label>
              <div className="size-grid">
                {sizes.map((s) => (
                  <button key={s.value}
                          className={`size ${size === s.value ? 'active' : ''}${s.stock === 0 ? ' out' : ''}`}
                          disabled={s.stock === 0}
                          onClick={() => { setSize(s.value); setColor(null); setAdded(false); }}>
                    {s.value || 'Один размер'}
                  </button>
                ))}
              </div>
            </div>
          )}

          {!out && needsColor && (
            <div className="field">
              <label>Цвет</label>
              <div className="size-grid">
                {colors.map((c) => (
                  <button key={c.value}
                          className={`size ${color === c.value ? 'active' : ''}${c.stock === 0 ? ' out' : ''}`}
                          disabled={c.stock === 0}
                          onClick={() => { setColor(c.value); setAdded(false); }}>
                    {c.value || 'Один цвет'}
                  </button>
                ))}
              </div>
            </div>
          )}

          {error && <div className="notice notice-error">{error}</div>}

          {!out && (
            <div className="sticky-buy">
              {added ? (
                <>
                  <Link to="/cart" className="btn btn-primary btn-lg btn-block">
                    <Icon name="shopping-bag" size={17} /> В корзине — оформить
                  </Link>
                  <button className="btn btn-lg" onClick={() => setAdded(false)}>
                    Ещё
                  </button>
                </>
              ) : (
                <button className="btn btn-primary btn-lg btn-block"
                        disabled={!chosen || addToCart.isPending}
                        onClick={() => addToCart.mutate()}>
                  {chosen
                    ? (addToCart.isPending ? 'Добавляем…' : 'В корзину')
                    : 'Выберите размер и цвет'}
                </button>
              )}
              {user && (
                <button className="btn btn-lg btn-icon"
                        aria-label="В избранное"
                        onClick={() => {
                          const next = !favs.has(item.id);
                          toggle(item.id, next);
                          toast(next ? 'В избранном' : 'Убрали из избранного');
                        }}>
                  <Icon name="heart" size={19}
                        strokeWidth={favs.has(item.id) ? 2.6 : 1.9} />
                </button>
              )}
            </div>
          )}

          {chosen && chosen.stock > 0 && chosen.stock <= 3 && (
            <p className="caption">Осталось {chosen.stock} шт.</p>
          )}

          {item.description && (
            <div>
              <h2 style={{ marginBottom: 8 }}>Описание</h2>
              <p style={{ whiteSpace: 'pre-line', color: 'var(--text-2)' }}>
                {item.description}
              </p>
            </div>
          )}

          {item.specs.length > 0 && (
            <div>
              <h2 style={{ marginBottom: 8 }}>Характеристики</h2>
              <table className="specs">
                <tbody>
                  {item.specs.map((s) => (
                    <tr key={s.label}>
                      <td>{s.label}</td>
                      <td>{s.value}{s.unit ? ` ${s.unit}` : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {similar && similar.items.length > 0 && (
        <section className="section">
          <div className="section-head"><h2>Похожее</h2></div>
          <div className="grid">
            {similar.items.map((p) => (
              <ProductCard key={p.id} item={p} isFav={favs.has(p.id)}
                           onFav={user ? toggle : undefined} />
            ))}
          </div>
        </section>
      )}
      {node}
    </div>
  );
}
