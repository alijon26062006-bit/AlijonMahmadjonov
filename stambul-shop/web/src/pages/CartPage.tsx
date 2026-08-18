/** Корзина и оформление заказа — один экран в два шага. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, fmtPrice, photoUrl } from '../api/client';
import type { CartOut, OrderOut, ShopConfig } from '../api/types';
import { Icon } from '../components/icons';
import { Empty, useAuth } from '../components/ui';

export default function CartPage({ cfg }: { cfg?: ShopConfig }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const user = useAuth();
  const [step, setStep] = useState<'cart' | 'form'>('cart');
  const [error, setError] = useState('');

  const { data: cart, isLoading } = useQuery<CartOut>({
    queryKey: ['cart'], queryFn: () => api('/api/cart'), enabled: Boolean(user),
  });

  const [form, setForm] = useState({
    customer_name: '', phone: '', city_id: '', address: '',
    delivery: 'courier', comment: '',
  });
  // адрес прошлого заказа подставляется сам — второй раз вводить не нужно
  useEffect(() => {
    if (!user) return;
    setForm((f) => ({
      ...f,
      customer_name: f.customer_name || user.name || '',
      phone: f.phone || user.phone || '',
      city_id: f.city_id || (user.city_id ? String(user.city_id) : ''),
      address: f.address || user.address || '',
    }));
  }, [user]);

  const change = useMutation({
    mutationFn: ({ id, qty }: { id: number; qty: number }) =>
      api(`/api/cart/${id}`, { method: 'PATCH', body: JSON.stringify({ qty }) }),
    onSuccess: (data) => qc.setQueryData(['cart'], data),
  });
  const drop = useMutation({
    mutationFn: (id: number) => api(`/api/cart/${id}`, { method: 'DELETE' }),
    onSuccess: (data) => qc.setQueryData(['cart'], data),
  });

  const [done, setDone] = useState<OrderOut | null>(null);
  const submit = useMutation({
    mutationFn: () => api<OrderOut>('/api/orders', {
      method: 'POST',
      body: JSON.stringify({
        customer_name: form.customer_name,
        phone: form.phone,
        city_id: form.city_id ? Number(form.city_id) : null,
        address: form.address || null,
        delivery: form.delivery,
        comment: form.comment || null,
      }),
    }),
    onSuccess: (order) => {
      setDone(order);
      qc.invalidateQueries({ queryKey: ['cart'] });
      qc.invalidateQueries({ queryKey: ['orders'] });
    },
    onError: (e: unknown) => {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { navigate('/login?back=/cart'); return; }
      setError(err.message || 'Не получилось оформить заказ');
    },
  });

  if (!user) {
    return (
      <div className="page">
        <Empty icon="shopping-bag" title="Войдите, чтобы оформить заказ"
               note="Собранная корзина сохранится за вами"
               action={{ label: 'Войти', to: '/login?back=/cart' }} />
      </div>
    );
  }
  if (done) return <OrderDone order={done} cfg={cfg} />;
  if (isLoading) {
    return (
      <div className="page">
        <div className="skeleton" style={{ height: 240 }} />
      </div>
    );
  }
  if (!cart || cart.items.length === 0) {
    return (
      <div className="page">
        <Empty icon="shopping-bag" title="Корзина пуста"
               note="Загляните в каталог — там много хорошего"
               action={{ label: 'В каталог', to: '/catalog' }} />
      </div>
    );
  }

  const pickup = cfg?.delivery.pickup_address;
  const free = cfg?.delivery.free_from ?? 0;
  const shipping = form.delivery === 'pickup' ? 0
    : (free > 0 && cart.goods_total >= free) ? 0
    : form.delivery === 'courier' ? (cfg?.delivery.city_price ?? 0)
    : (cfg?.delivery.country_price ?? 0);

  return (
    <div className="page fade-in">
      <h1>Корзина</h1>

      {cart.issues.length > 0 && (
        <div className="notice" style={{ marginBottom: 12 }}>
          <b>Кое-что изменилось</b>
          {cart.issues.map((i) => <p key={i}>{i}</p>)}
        </div>
      )}

      {cart.items.map((i) => (
        <div key={i.variant_id} className="line">
          <Link to={`/p/${i.product_id}`} className="line-photo">
            {i.photo
              ? <img src={photoUrl(i.photo)} alt={i.title} loading="lazy" />
              : <span className="line-noimg"><Icon name="image" size={20} /></span>}
          </Link>
          <div className="line-info">
            <Link to={`/p/${i.product_id}`}><b>{i.title}</b></Link>
            <div className="subtitle">{i.variant}</div>
            <div className="price">{fmtPrice(i.price)}</div>
          </div>
          <div className="qty">
            <button onClick={() => change.mutate({ id: i.variant_id, qty: i.qty - 1 })}>
              <Icon name="minus" size={14} strokeWidth={2.6} />
            </button>
            <span>{i.qty}</span>
            <button disabled={i.qty >= i.available}
                    onClick={() => change.mutate({ id: i.variant_id, qty: i.qty + 1 })}>
              <Icon name="plus" size={14} strokeWidth={2.6} />
            </button>
            <button className="line-drop" onClick={() => drop.mutate(i.variant_id)}>
              <Icon name="trash" size={15} />
            </button>
          </div>
        </div>
      ))}

      <div className="summary">
        <div className="row-between"><span>Товары</span>
          <span>{fmtPrice(cart.goods_total)}</span></div>
        <div className="row-between"><span>Доставка</span>
          <span>{shipping === 0 ? 'бесплатно' : fmtPrice(shipping)}</span></div>
        <div className="row-between total"><span>Итого</span>
          <span>{fmtPrice(cart.goods_total + shipping)}</span></div>
      </div>

      {step === 'cart' ? (
        <button className="btn btn-primary btn-lg btn-block" style={{ marginTop: 14 }}
                onClick={() => setStep('form')}>
          Оформить заказ
        </button>
      ) : (
        <div className="section">
          <h2 style={{ marginBottom: 16 }}>Куда доставить</h2>

          <div className="field">
            <label>Способ доставки</label>
            <div className="chips">
              {[['courier', 'Курьером'], ['post', 'Почтой'],
                ...(pickup ? [['pickup', 'Самовывоз']] : [])].map(([v, l]) => (
                <button key={v} className={`chip ${form.delivery === v ? 'active' : ''}`}
                        onClick={() => setForm({ ...form, delivery: v as string })}>
                  {l}
                </button>
              ))}
            </div>
            {form.delivery === 'pickup' && pickup && (
              <div className="caption">Забрать: {pickup}</div>
            )}
          </div>

          <div className="field">
            <label>Имя <span style={{ color: 'var(--danger)' }}>*</span></label>
            <input className="input" value={form.customer_name}
                   onChange={(e) => setForm({ ...form, customer_name: e.target.value })} />
          </div>
          <div className="field">
            <label>Телефон <span style={{ color: 'var(--danger)' }}>*</span></label>
            <input className="input" inputMode="tel" placeholder="+7 701 123 45 67" value={form.phone}
                   onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </div>

          {form.delivery !== 'pickup' && (
            <>
              <div className="field">
                <label>Город <span style={{ color: 'var(--danger)' }}>*</span></label>
                <select className="select" value={form.city_id}
                        onChange={(e) => setForm({ ...form, city_id: e.target.value })}>
                  <option value="">Выберите город</option>
                  {(cfg?.cities ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} · {c.days} дн.
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Адрес <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input className="input" placeholder="Улица, дом, квартира" value={form.address}
                       onChange={(e) => setForm({ ...form, address: e.target.value })} />
              </div>
            </>
          )}

          <div className="field">
            <label>Комментарий</label>
            <textarea className="textarea" rows={2} placeholder="Например: позвонить за час"
                      value={form.comment}
                      onChange={(e) => setForm({ ...form, comment: e.target.value })} />
          </div>

          {error && <div className="field-error" style={{ marginBottom: 10 }}>{error}</div>}
          <button className="btn btn-primary btn-lg btn-block" disabled={submit.isPending}
                  onClick={() => { setError(''); submit.mutate(); }}>
            {submit.isPending ? 'Отправляем…'
              : `Заказать на ${fmtPrice(cart.goods_total + shipping)}`}
          </button>
          <button className="btn btn-ghost btn-block" style={{ marginTop: 8 }}
                  onClick={() => setStep('cart')}>
            Назад в корзину
          </button>
        </div>
      )}
    </div>
  );
}

function OrderDone({ order, cfg }: { order: OrderOut; cfg?: ShopConfig }) {
  return (
    <div className="page fade-in">
      <div className="empty">
        <div className="empty-icon"><Icon name="check" size={34} strokeWidth={2.4} /></div>
        <h1  style={{ marginBottom: 4 }}>
          Заказ №{order.number} принят
        </h1>
        <p className="subtitle">Мы свяжемся с вами для подтверждения.</p>
      </div>

      <div className="summary" style={{ marginTop: 16 }}>
        {order.items.map((i, n) => (
          <div key={n} className="row-between">
            <span>{i.title} · {i.variant} × {i.qty}</span>
            <span>{fmtPrice(i.line_total)}</span>
          </div>
        ))}
        <div className="row-between"><span>Доставка</span>
          <span>{order.delivery_price === 0 ? 'бесплатно'
            : fmtPrice(order.delivery_price)}</span></div>
        <div className="row-between total"><span>Итого</span>
          <span>{fmtPrice(order.total)}</span></div>
      </div>

      {order.payment && (
        <div className="notice" style={{ marginTop: 14 }}>
          <b>Оплата через Kaspi</b>
          <p>Номер: <b>{order.payment.phone}</b></p>
          {order.payment.name && <p>Получатель: {order.payment.name}</p>}
          <p>В комментарии к переводу укажите номер заказа {order.number}.</p>
          {order.payment.link && (
            <a className="btn btn-primary btn-lg btn-block" style={{ marginTop: 10 }}
               href={order.payment.link} target="_blank" rel="noreferrer">
              Открыть Kaspi
            </a>
          )}
        </div>
      )}

      <Link to="/orders" className="btn btn-block" style={{ marginTop: 14 }}>
        Мои заказы
      </Link>
      <Link to="/" className="btn btn-ghost btn-block" style={{ marginTop: 8 }}>
        За покупками
      </Link>
    </div>
  );
}
