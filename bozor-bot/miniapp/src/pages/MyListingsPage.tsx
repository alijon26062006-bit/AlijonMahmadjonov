/** Мои объявления: статусы, снятие, «продано», цикл аренды занято/свободно. */
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, fmtPrice, photoUrl } from '../api/client';
import type { Card } from '../api/types';
import { Icon } from '../components/icons';
import { Empty, STATUS_BADGE, useAuth, useTgBackButton } from '../components/ui';
import { logout } from '../api/client';
import { inTelegram } from '../telegram/tg';

export default function MyListingsPage() {
  useTgBackButton(true);
  const user = useAuth();
  const { data, isLoading, refetch } = useQuery<{ items: Card[] }>({
    queryKey: ['my'],
    queryFn: () => api('/api/listings/my'),
    enabled: Boolean(user),
  });

  if (!user) {
    return <Empty icon="lock" title="Нужен вход"
                  note="Войдите, чтобы управлять своими объявлениями"
                  action={{ label: 'Войти', to: '/login' }} />;
  }

  const patch = async (id: string, status: string) => {
    await api(`/api/listings/${id}`, {
      method: 'PATCH', body: JSON.stringify({ status }),
    });
    refetch();
  };

  const items = data?.items ?? [];
  return (
    <div className="section fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 className="section-title" style={{ marginBottom: 0 }}>Мои объявления</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          {user.is_admin && (
            <Link to="/admin" className="btn">
              <Icon name="sliders-horizontal" size={15} /> Админка
            </Link>
          )}
          {!inTelegram && (
            <button className="btn btn-ghost" onClick={logout}>Выйти</button>
          )}
        </div>
      </div>
      <p className="subtitle" style={{ margin: '6px 0 14px' }}>
        {user.first_name}{user.username ? ` · @${user.username}` : ''}
      </p>

      {isLoading && <div className="skeleton" style={{ height: 90 }} />}
      {!isLoading && !items.length && (
        <Empty icon="archive" title="Объявлений пока нет"
               note="Подайте первое — через бота или кнопкой «Подать»"
               action={{ label: 'Подать объявление', to: '/post' }} />
      )}

      {items.map((item) => {
        const badge = STATUS_BADGE[item.status] ?? { cls: 'badge-gray', label: item.status };
        return (
          <div key={item.public_id} className="my-item fade-in">
            {item.photos[0]
              ? <img className="thumb" src={photoUrl(item.photos[0].thumb)} alt="" />
              : <div className="thumb" />}
            <div style={{ minWidth: 0, flex: 1 }}>
              <span className={`badge ${badge.cls}`}>{badge.label}</span>
              <div style={{ fontWeight: 700, marginTop: 4 }}>
                <Link to={`/listing/${item.public_id}`} style={{ color: 'var(--text)' }}>
                  {item.title}
                </Link>
              </div>
              <div className="subtitle">{fmtPrice(item.price, item.currency)}</div>
              {item.status === 'rejected' && item.reject_reason && (
                <div className="field-error">Причина: {item.reject_reason}</div>
              )}
              <div className="my-actions">
                {item.status === 'approved' && (
                  <>
                    {item.is_rent
                      ? <button className="btn" onClick={() => patch(item.public_id, 'occupied')}><Icon name="lock" size={14} /> Занято</button>
                      : <button className="btn" onClick={() => patch(item.public_id, 'sold')}><Icon name="handshake" size={14} /> Продано</button>}
                    <button className="btn" onClick={() => patch(item.public_id, 'archived')}><Icon name="archive" size={14} /> Снять</button>
                  </>
                )}
                {item.status === 'occupied' && (
                  <button className="btn btn-primary" onClick={() => patch(item.public_id, 'approved')}>
                    <Icon name="lock-open" size={14} /> Снова свободно
                  </button>
                )}
                {(item.status === 'sold' || item.status === 'archived') && (
                  <button className="btn" onClick={() => patch(item.public_id, 'approved')}>
                    <Icon name="rotate-ccw" size={14} /> Вернуть в каталог
                  </button>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
