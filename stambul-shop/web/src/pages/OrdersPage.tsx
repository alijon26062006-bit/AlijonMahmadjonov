/** Мои заказы. */
import { useQuery } from '@tanstack/react-query';
import { api, fmtDate, fmtPrice } from '../api/client';
import type { OrderOut } from '../api/types';
import { Empty, ORDER_BADGE, useAuth } from '../components/ui';

export default function OrdersPage() {
  const user = useAuth();
  const { data, isLoading } = useQuery<{ items: OrderOut[] }>({
    queryKey: ['orders'], queryFn: () => api('/api/orders/mine'),
    enabled: Boolean(user),
  });

  if (!user) {
    return (
      <div className="page">
        <Empty icon="package" title="Войдите, чтобы видеть заказы"
               action={{ label: 'Войти', to: '/login?back=/orders' }} />
      </div>
    );
  }
  if (isLoading) return <div className="skeleton" style={{ height: 200, marginTop: 12 }} />;
  const items = data?.items ?? [];

  return (
    <div className="page fade-in">
      <h1>Мои заказы</h1>

      {items.length === 0 ? (
        <Empty icon="package" title="Заказов пока нет"
               note="Загляните в каталог — там много хорошего"
               action={{ label: 'В каталог', to: '/catalog' }} />
      ) : items.map((o) => (
        <div key={o.public_id} className="line" style={{ gridTemplateColumns: "1fr auto" }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <b>Заказ №{o.number}</b>
              <span className={`badge ${ORDER_BADGE[o.status] ?? 'badge-gray'}`}>
                {o.status_label}
              </span>
            </div>
            <div className="subtitle" style={{ marginTop: 4 }}>
              {o.items.map((i) => `${i.title} · ${i.variant} × ${i.qty}`).join('; ')}
            </div>
            <div className="subtitle" style={{ marginTop: 4 }}>
              {o.delivery_label}
              {o.city ? ` · ${o.city}` : ''}
              {o.created_at ? ` · ${fmtDate(o.created_at)}` : ''}
            </div>
            {o.tracking && (
              <div className="subtitle">Трек: <b>{o.tracking}</b></div>
            )}
          </div>
          <div style={{ textAlign: 'right', fontWeight: 800 }}>
            {fmtPrice(o.total)}
          </div>
        </div>
      ))}
    </div>
  );
}
