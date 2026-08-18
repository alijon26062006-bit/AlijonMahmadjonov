import { useState } from 'react';
import { Link } from 'react-router-dom';
import { fmtPrice, photoUrl } from '../api/client';
import type { Card } from '../api/types';
import { Icon } from './icons';

export function ProductCard({ item, isFav, onFav }: {
  item: Card;
  isFav?: boolean;
  onFav?: (id: string, next: boolean) => void;
}) {
  const [failed, setFailed] = useState(false);
  const out = item.in_stock === 0;
  const discount = item.old_price && item.old_price > item.price
    ? Math.round((1 - item.price / item.old_price) * 100) : 0;

  return (
    <Link to={`/p/${item.id}`} className="card fade-in">
      <div className="card-photo">
        {item.photo && !failed ? (
          <img src={photoUrl(item.photo)} alt={item.title}
               loading="lazy" decoding="async"
               onLoad={(e) => e.currentTarget.classList.add('loaded')}
               onError={() => setFailed(true)} />
        ) : (
          <div style={{ display: 'grid', placeItems: 'center', height: '100%',
                        color: 'var(--text-3)' }}>
            <Icon name="image" size={28} strokeWidth={1.4} />
          </div>
        )}

        {out
          ? <span className="tag tag-out">Закончился</span>
          : discount > 0 && <span className="tag">−{discount}%</span>}

        {onFav && (
          <button className="fav-btn" aria-label={isFav ? 'Убрать из избранного'
                                                        : 'В избранное'}
                  onClick={(e) => { e.preventDefault(); onFav(item.id, !isFav); }}>
            <Icon name="heart" size={16} strokeWidth={isFav ? 2.6 : 1.9} />
          </button>
        )}
      </div>

      <div className="card-body">
        <div className="card-title">{item.title}</div>
        <div className="card-price">
          <span className="price">{fmtPrice(item.price)}</span>
          {discount > 0 && <span className="old">{fmtPrice(item.old_price!)}</span>}
        </div>
        {item.sizes.length > 0 && (
          <div className="card-sizes">
            {item.sizes.slice(0, 5).join(' · ')}{item.sizes.length > 5 ? ' …' : ''}
          </div>
        )}
      </div>
    </Link>
  );
}
