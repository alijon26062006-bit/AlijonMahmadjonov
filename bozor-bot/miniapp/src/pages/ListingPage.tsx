/** Карточка объявления: галерея, спеки из схемы, карта, связь с автором. */
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, fmtDate, fmtPrice, photoUrl } from '../api/client';
import type { ListingDetail } from '../api/types';
import { Icon } from '../components/icons';
import { MiniMap } from '../components/MapView';
import { Empty, useAuth, useTgBackButton } from '../components/ui';
import { hapticSuccess, openTgLink } from '../telegram/tg';

export default function ListingPage() {
  useTgBackButton(true);
  const { id } = useParams();
  const navigate = useNavigate();
  const user = useAuth();
  const [contact, setContact] = useState<{ telegram?: string; phone?: string } | null>(null);
  const [reported, setReported] = useState(false);

  const { data: item, isLoading, error } = useQuery<ListingDetail>({
    queryKey: ['listing', id],
    queryFn: () => api(`/api/listings/${id}`),
  });

  if (isLoading) return <div className="skeleton" style={{ height: 400, marginTop: 12 }} />;
  if (error || !item) return <Empty icon="search" title="Объявление не найдено"
                                    note="Возможно, оно снято с публикации" />;

  const askContact = async () => {
    try {
      const c = await api<{ telegram?: string; phone?: string }>(
        `/api/listings/${item.public_id}/contact`, { method: 'POST' });
      setContact(c);
      hapticSuccess();
    } catch (e) {
      const err = e as { status?: number };
      if (err.status === 401) navigate('/login');
    }
  };

  const report = async () => {
    try {
      await api(`/api/listings/${item.public_id}/report`, {
        method: 'POST', body: JSON.stringify({ reason: 'spam' }),
      });
    } catch { /* 409 — уже жаловался */ }
    setReported(true);
  };

  return (
    <div className="fade-in section">
      <div className="gallery">
        {item.photos.length
          ? item.photos.map((p, i) => (
              <img key={i} src={photoUrl(p.full)} alt="" loading={i > 0 ? 'lazy' : undefined}
                   onLoad={(e) => e.currentTarget.classList.add('loaded')}
                   onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }} />
            ))
          : <div className="skeleton" style={{ width: '100%', aspectRatio: '4/3' }} />}
      </div>

      <div className="section">
        <div className="listing-price">
          {fmtPrice(item.price, item.currency)}
          {item.is_negotiable && <span className="badge badge-green" style={{ marginLeft: 10 }}>торг</span>}
        </div>
        <h1 style={{ fontSize: 'var(--fs-lg)', marginTop: 4 }}>{item.title}</h1>
        <p className="subtitle" style={{ marginTop: 4, display: 'flex',
                                         alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
          <Icon name="map-pin" size={13} />
          {[item.city, item.district, item.address].filter(Boolean).join(', ')}
          {item.published_at && <span>· {fmtDate(item.published_at)}</span>}
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
            · <Icon name="eye" size={13} /> {item.views_count}
          </span>
        </p>
      </div>

      {item.specs.length > 0 && (
        <div className="specs">
          {item.specs.map((s) => (
            <div key={s.key} className="spec-row">
              <span className="k">{s.label}</span>
              <span className="v">
                {/^\d+(\.\d+)?$/.test(s.value)
                  ? Number(s.value).toLocaleString('ru-RU') + (s.unit ? ` ${s.unit}` : '')
                  : s.value}
                {s.verified && <span className="badge badge-green" style={{ marginLeft: 6 }}>✓</span>}
              </span>
            </div>
          ))}
        </div>
      )}

      {item.description && <p className="desc">{item.description}</p>}

      {item.lat != null && item.lon != null && <MiniMap lat={item.lat} lon={item.lon} />}

      <div className="contact-bar">
        <div className="contact-bar-inner">
          {contact ? (
            <>
              {contact.telegram && (
                <button className="btn btn-primary btn-block"
                        onClick={() => openTgLink(contact.telegram!)}>
                  <Icon name="send" size={17} /> Написать в Telegram
                </button>
              )}
              {contact.phone && (
                <a className="btn btn-primary btn-block" href={`tel:${contact.phone}`}>
                  <Icon name="phone" size={17} /> {contact.phone}
                </a>
              )}
            </>
          ) : (
            <button className="btn btn-primary btn-block" onClick={askContact}>
              <Icon name="message-circle" size={17} /> Связаться с продавцом
            </button>
          )}
          <button className="btn" title="Пожаловаться" onClick={report}>
            <Icon name={reported ? 'check' : 'flag'} size={17} />
          </button>
        </div>
      </div>
      <div className="contact-spacer" />
    </div>
  );
}
