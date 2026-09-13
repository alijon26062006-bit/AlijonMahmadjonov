import Link from 'next/link';
import styles from './ServiceCard.module.css';
import { Avatar } from '@/components/ui/Avatar';
import { IconStarFilled } from '@/components/ui/Icon';
import { days } from '@/lib/format';
import type { ServiceCard as ServiceCardType } from '@/lib/types';

/** Одна услуга в каталоге: обложка, название, исполнитель, цена «от». */
export function ServiceCard({ service }: { service: ServiceCardType }) {
  return (
    <Link href={`/services/${service.id}`} className={styles.card}>
      <div className={styles.cover}>
        {service.cover_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={service.cover_url} alt="" loading="lazy" className={styles.coverImage} />
        ) : (
          <span className={styles.coverText}>{service.category.name}</span>
        )}
      </div>
      <div className={styles.body}>
        <div className={styles.seller}>
          <Avatar src={service.seller.photo_url} name={service.seller.full_name} size={24} />
          <span className="av-xs av-muted av-clamp-2">{service.seller.full_name}</span>
        </div>
        <h3 className={`${styles.title} av-clamp-2`}>{service.title}</h3>
        <div className={styles.meta}>
          {service.rating_avg ? (
            <span className={styles.rating}>
              <IconStarFilled size={12} />
              {service.rating_avg.toFixed(1)}
              <span className="av-faint"> ({service.rating_count})</span>
            </span>
          ) : (
            <span className="av-xs av-faint">Без отзывов</span>
          )}
          <span className="av-xs av-faint">{days(service.delivery_days)}</span>
        </div>
        <p className={styles.price}>
          <span className="av-xs av-muted">от </span>
          {service.from_display}
        </p>
      </div>
    </Link>
  );
}
