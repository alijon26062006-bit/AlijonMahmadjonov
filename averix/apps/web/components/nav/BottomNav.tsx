'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './BottomNav.module.css';
import {
  IconBriefcase,
  IconCompass,
  IconMessage,
  IconPlus,
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
 * The bottom bar is the product's spine on a phone: five destinations, thumb
 * height, always there. It is not a shrunken desktop menu — the desktop header
 * carries the same destinations in a row instead, and this disappears.
 */
export function BottomNav({ unread = 0 }: { unread?: number }) {
  const pathname = usePathname();
  const { session } = useSession();
  if (!session) return null;

  const role = session.active_role;
  const items: Item[] =
    role === 'client'
      ? [
          { href: '/dashboard', label: 'Work', icon: IconBriefcase },
          { href: '/talent', label: 'Talent', icon: IconCompass },
          { href: '/projects/new', label: 'Post', icon: IconPlus },
          { href: '/messages', label: 'Messages', icon: IconMessage, badge: unread },
          { href: '/profile', label: 'Profile', icon: IconUser },
        ]
      : role === 'admin' || role === 'moderator'
        ? [
            { href: '/admin', label: 'Overview', icon: IconBriefcase },
            { href: '/admin/payments', label: 'Payments', icon: IconWallet },
            { href: '/messages', label: 'Messages', icon: IconMessage, badge: unread },
            { href: '/profile', label: 'Profile', icon: IconUser },
          ]
        : [
            { href: '/feed', label: 'Find work', icon: IconCompass },
            { href: '/contracts', label: 'Contracts', icon: IconBriefcase },
            { href: '/messages', label: 'Messages', icon: IconMessage, badge: unread },
            { href: '/earnings', label: 'Earnings', icon: IconWallet },
            { href: '/profile', label: 'Profile', icon: IconUser },
          ];

  // The most specific destination wins: on /admin/payments only Payments is
  // current, not Overview as well.
  const currentHref = items
    .filter((item) => pathname === item.href || pathname.startsWith(`${item.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <nav className={styles.nav} aria-label="Main">
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
