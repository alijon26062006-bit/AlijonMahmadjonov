'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './BottomNav.module.css';
import {
  IconBriefcase,
  IconCompass,
  IconMessage,
  IconPlus,
  IconShield,
  IconUser,
  IconWallet,
} from '@/components/ui/Icon';
import { useSession } from '@/lib/session';

type Item = {
  href: string;
  label: string;
  icon: typeof IconCompass;
  match?: (path: string) => boolean;
  badge?: number;
};

/**
 * Нижняя панель — позвоночник продукта на телефоне: пять разделов на высоте
 * большого пальца, всегда на месте. На десктопе те же разделы несёт шапка,
 * а панель исчезает.
 */
export function BottomNav({ unread = 0 }: { unread?: number }) {
  const pathname = usePathname();
  const { session } = useSession();
  if (!session) return null;

  const role = session.active_role;
  const items: Item[] =
    role === 'client'
      ? [
          { href: '/dashboard', label: 'Заказы', icon: IconBriefcase },
          { href: '/freelancers', label: 'Исполнители', icon: IconCompass },
          { href: '/projects/new', label: 'Создать', icon: IconPlus },
          { href: '/messages', label: 'Чаты', icon: IconMessage, badge: unread },
          { href: '/profile', label: 'Профиль', icon: IconUser },
        ]
      : role === 'admin' || role === 'moderator'
        ? [
            { href: '/admin', label: 'Обзор', icon: IconBriefcase, match: (path) => path === '/admin' },
            { href: '/admin/moderation', label: 'Модерация', icon: IconShield },
            { href: '/admin/payments', label: 'Платежи', icon: IconWallet },
            { href: '/messages', label: 'Чаты', icon: IconMessage, badge: unread },
            { href: '/profile', label: 'Профиль', icon: IconUser },
          ]
        : [
            { href: '/feed', label: 'Заказы', icon: IconCompass },
            { href: '/contracts', label: 'Сделки', icon: IconBriefcase },
            { href: '/messages', label: 'Чаты', icon: IconMessage, badge: unread },
            { href: '/earnings', label: 'Доходы', icon: IconWallet },
            { href: '/profile', label: 'Профиль', icon: IconUser },
          ];

  // Побеждает самый конкретный адрес: на /admin/payments активен только
  // «Платежи», а не «Обзор» вместе с ним.
  const currentHref = items
    .filter((item) => pathname === item.href || pathname.startsWith(`${item.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <nav className={styles.nav} aria-label="Главное меню">
      {items.map((item) => {
        const active = item.match ? item.match(pathname) : item.href === currentHref;
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={[styles.item, active ? styles.active : ''].join(' ')}
            aria-current={active ? 'page' : undefined}
          >
            <span className={styles.iconWrap}>
              <Icon size={22} />
              {item.badge ? (
                <span className={styles.badge} aria-hidden="true">
                  {item.badge > 9 ? '9+' : item.badge}
                </span>
              ) : null}
            </span>
            <span className={styles.label}>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
