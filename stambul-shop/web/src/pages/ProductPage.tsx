/** Карточка товара: галерея, выбор размера и цвета, кнопка в корзину. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, fmtPrice, photoUrl } from '../api/client';
import type { Card, ProductDetail } from '../api/types';
import { Icon } from '../components/icons';
import { ProductCard } from '../components/ProductCard';
import { Empty, useAuth, useTgBackButton } from '../components/ui';
import { hapticSuccess } from '../telegram/tg';

export default function ProductPage() {
  useTgBackButton(true);
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const user = useAuth();
  const [size, setSize] = useState<string | null>(null);
  const [color, setColor] = useState<string | null>(null);
  const [added, setAdded] = useState(false);
  const [error, setError] = useState('');

  const { data: item, isLoading } = useQuery<ProductDetail>({
    queryKey: ['product', id], queryFn: () => api(`/api/products/${id}`),
  });
  const { data: similar } = useQuery<{ items: Card[] }>({
    queryKey: ['similar', id], queryFn: () => api(`/api/products/${id}/similar`),
    enabled: Boolean(item),
  });

  // Доступные размеры и цвета считаем из вариантов: то, чего нет на складе,
  // показываем зачёркнутым, а не прячем — человек видит, что вещь существует.
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
      (v) => (size === null || v.size === size) && (color === null || v.color === color));
    return fit.length === 1 ? fit[0] : null;
  }, [item, size, color]);

  const needsSize = sizes.length > 1 || (sizes[0]?.value ?? '') !== '';
  const needsColor = colors.length > 1 || (colors[0]?.value ?? '') !== '';

  // Выбор из одного варианта — не выбор: проставляем сами, чтобы кнопка
  // «В корзину» не требовала лишнего нажатия.
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
      setAdded(true); setError(''); hapticSuccess();
      qc.invalidateQueries({ queryKey: ['cart'] });
    },
    onError: (e: unknown) => {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { navigate('/login'); return; }
      setError(err.message || 'Не получилось добавить');
    },
  });

  if (isLoading) return <div className="skeleton" style={{ height: 420, marginTop: 12 }} />;
  if (!item) return <Empty icon="search" title="Товар не найден"
                           note="Возможно, он снят с продажи"
                           action={{ label: 'В каталог', to: '/catalog' }} />;

  const out = item.in_stock === 0;
  const price = chosen ? chosen.price : item.price;

  return (
    <div className="fade-in section">
      <div className="gallery">
        {item.photos.length
          ? item.photos.map((p, i) => (
              <img key={i} src={photoUrl(p.full)} alt=""
                   loading={i > 0 ? 'lazy' : undefined}
                   onLoad={(e) => e.currentTarget.classList.add('loaded')}
                   onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }} />
            ))
          : <div className="skeleton" style={{ width: '100%', aspectRatio: '3/4' }} />}
      </div>

      <div className="section">
        <div className="listing-price">
          {fmtPrice(price)}
          {item.old_price && item.old_price > price && (
            <span className="card-old" style={{ fontSize: '0.6em' }}>
              {fmtPrice(item.old_price)}
            </span>
          )}
        </div>
        <h1 style={{ fontSize: 'var(--fs-lg)', marginTop: 4 }}>{item.title}</h1>
        <p className="subtitle" style={{ marginTop: 4 }}>
          {[item.brand, item.category_title].filter(Boolean).join(' · ')}
        </p>
      </div>

      {out && (
        <div className="notice">
          <b>Товар закончился</b>
          <p>Напишите нам — подскажем, когда будет завоз.</p>
        </div>
      )}

      {!out && needsSize && (
        <div className="section">
          <b>Размер</b>
          <div className="chips" style={{ marginTop: 8 }}>
            {sizes.map((s) => (
              <button key={s.value}
                      className={`chip ${size === s.value ? 'on' : ''}${s.stock === 0 ? ' chip-out' : ''}`}
                      disabled={s.stock === 0}
                      onClick={() => { setSize(s.value); setColor(null); setAdded(false); }}>
                {s.value || 'Один размер'}
              </button>
            ))}
          </div>
        </div>
      )}

      {!out && needsColor && (
        <div className="section">
          <b>Цвет</b>
          <div className="chips" style={{ marginTop: 8 }}>
            {colors.map((c) => (
              <button key={c.value}
                      className={`chip ${color === c.value ? 'on' : ''}${c.stock === 0 ? ' chip-out' : ''}`}
                      disabled={c.stock === 0}
                      onClick={() => { setColor(c.value); setAdded(false); }}>
                {c.value || 'Один цвет'}
              </button>
            ))}
          </div>
        </div>
      )}

      {!out && (
        <div className="section">
          {error && <div className="field-error" style={{ marginBottom: 8 }}>{error}</div>}
          {added ? (
            <div className="range-row">
              <Link to="/cart" className="btn btn-primary btn-block">
                <Icon name="shopping-bag" size={17} /> Перейти в корзину
              </Link>
              <button className="btn" onClick={() => setAdded(false)}>Ещё</button>
            </div>
          ) : (
            <button className="btn btn-primary btn-block"
                    disabled={!chosen || addToCart.isPending}
                    onClick={() => addToCart.mutate()}>
              {chosen
                ? (addToCart.isPending ? 'Добавляем…' : 'В корзину')
                : 'Выберите размер и цвет'}
            </button>
          )}
          {chosen && chosen.stock <= 3 && (
            <p className="subtitle" style={{ marginTop: 8 }}>
              Осталось {chosen.stock} шт.
            </p>
          )}
        </div>
      )}

      {item.description && (
        <div className="section">
          <b>Описание</b>
          <p style={{ marginTop: 6, whiteSpace: 'pre-line' }}>{item.description}</p>
        </div>
      )}

      {item.specs.length > 0 && (
        <div className="section">
          <b>Характеристики</b>
          <div className="specs" style={{ marginTop: 8 }}>
            {item.specs.map((s) => (
              <div key={s.label} className="spec-row">
                <span className="subtitle">{s.label}</span>
                <span>{s.value}{s.unit ? ` ${s.unit}` : ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {similar && similar.items.length > 0 && (
        <section className="section">
          <h2 className="section-title">Похожее</h2>
          <div className="grid">
            {similar.items.map((p) => <ProductCard key={p.id} item={p} />)}
          </div>
        </section>
      )}
    </div>
  );
}
