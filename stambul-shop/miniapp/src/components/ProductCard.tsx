import { useState } from 'react';
import { Link } from 'react-router-dom';
import { fmtPrice, photoUrl } from '../api/client';
import type { Card } from '../api/types';
import { haptic } from '../telegram/tg';
import { CATEGORY_SHORT, Icon } from './icons';

export function ProductCard({ item, isFav, onFav }: {
  item: Card;
  isFav?: boolean;
  onFav?: (id: string, next: boolean) => void;
}) {
  // мерцание снимаем и при ошибке загрузки: вечная заглушка читается как поломка
  const [shown, setShown] = useState(!item.photo);
  const out = item.in_stock === 0;
  const discount = item.old_price && item.old_price > item.price
    ? Math.round((1 - item.price / item.old_price) * 100) : 0;

  return (
    <Link to={`/p/${item.id}`} className={`card fade-in${out ? ' card-out' : ''}`}>
      <div className={`card-photo${shown ? ' ready' : ''}`}>
        <div className="noimg"><Icon name="image" size={30} strokeWidth={1.5} /></div>
        {item.photo && (
          <img src={photoUrl(item.photo)} alt="" loading="lazy" decoding="async"
               style={{ position: 'relative' }}
               onLoad={(e) => { e.currentTarget.classList.add('loaded'); setShown(true); }}
               onError={(e) => { e.currentTarget.style.visibility = 'hidden'; setShown(true); }} />
        )}
        {discount > 0 && !out && <span className="card-sale">−{discount}%</span>}
        {out && <span className="card-cat card-out-label">Закончился</span>}
        {!out && !discount && CATEGORY_SHORT[item.category] && (
          <span className="card-cat">{CATEGORY_SHORT[item.category]}</span>
        )}
        {onFav && (
          <button className={`card-fav ${isFav ? 'on' : ''}`}
                  onClick={(e) => { e.preventDefault(); haptic(); onFav(item.id, !isFav); }}>
            <Icon name="heart" size={17} strokeWidth={2.2} />
          </button>
        )}
      </div>
      <div className="card-body">
        <div className="card-price">
          {fmtPrice(item.price)}
          {discount > 0 && (
            <span className="card-old">{fmtPrice(item.old_price!)}</span>
          )}
        </div>
        <div className="card-title">{item.title}</div>
        <div className="card-meta">
          {item.brand && <span>{item.brand}</span>}
          {item.sizes.length > 0 && (
            <span>· {item.sizes.slice(0, 4).join(' ')}
              {item.sizes.length > 4 ? '…' : ''}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
