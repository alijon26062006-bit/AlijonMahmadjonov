import { Link } from 'react-router-dom';
import { fmtDate, fmtPrice, photoUrl } from '../api/client';
import type { Card } from '../api/types';
import { haptic } from '../telegram/tg';

export function ListingCard({ item, isFav, onFav }: {
  item: Card;
  isFav?: boolean;
  onFav?: (id: string, next: boolean) => void;
}) {
  const photo = item.photos[0];
  return (
    <Link to={`/listing/${item.public_id}`} className="card fade-in">
      <div className="card-photo">
        <div className="noimg">🏷</div>
        {photo && (
          <img src={photoUrl(photo.thumb)} alt="" loading="lazy"
               style={{ position: 'relative' }}
               onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }} />
        )}
        {onFav && (
          <button
            className="card-fav"
            onClick={(e) => {
              e.preventDefault();
              haptic();
              onFav(item.public_id, !isFav);
            }}>
            {isFav ? '❤️' : '🤍'}
          </button>
        )}
      </div>
      <div className="card-body">
        <div className="card-price">{fmtPrice(item.price, item.currency)}</div>
        <div className="card-title">{item.title}</div>
        <div className="card-meta">
          {item.city && <span>{item.city}</span>}
          {item.published_at && <span>· {fmtDate(item.published_at)}</span>}
        </div>
      </div>
    </Link>
  );
}
