'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import styles from './TopBar.module.css';
import { Wordmark } from './Logo';
import { Avatar } from '@/components/ui/Avatar';
import { Sheet } from '@/components/ui/Sheet';
import { Button } from '@/components/ui/Button';
import { IconArrowLeft, IconBell, IconMoon, IconSearch, IconSun, IconSettings } from '@/components/ui/Icon';
import { get } from '@/lib/api';
import { roleLabel } from '@/lib/labels';
import { useSession } from '@/lib/session';
import { useTheme } from '@/lib/theme';

const DESKTOP_LINKS: Record<string, { href: string; label: string }[]> = {
  developer: [
    { href: '/feed', label: 'Заказы' },
    { href: '/proposals', label: 'Отклики' },
    { href: '/contracts', label: 'Сделки' },
    { href: '/messages', label: 'Сообщения' },
    { href: '/earnings', label: 'Доходы' },
  ],
  client: [
    { href: '/dashboard', label: 'Мои заказы' },
    { href: '/freelancers', label: 'Исполнители' },
    { href: '/services', label: 'Услуги' },
    { href: '/messages', label: 'Сообщения' },
  ],
  admin: [
    { href: '/admin', label: 'Обзор' },
    { href: '/admin/moderation', label: 'Модерация' },
    { href: '/admin/payments', label: 'Платежи' },
    { href: '/admin/users', label: 'Пользователи' },
  ],
  moderator: [
    { href: '/admin', label: 'Обзор' },
    { href: '/admin/moderation', label: 'Модерация' },
  ],
  anonymous: [
    { href: '/freelancers', label: 'Исполнители' },
    { href: '/services', label: 'Услуги' },
  ],
};

/**
 * Шапка. На телефоне — тонкая полоса с «назад» и двумя главными кнопками;
 * от ноутбука и шире несёт те же разделы, что нижняя панель на мобильном.
 */
export function TopBar({
  title,
  back,
  action,
}: {
  title?: string;
  back?: string | true;
  action?: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, signOut, switchRole } = useSession();
  const { choice, setChoice } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    get<{ unread: number }>('/notifications/unread')
      .then((data) => !cancelled && setUnread(data.unread))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [session, pathname]);

  const links = DESKTOP_LINKS[session?.active_role ?? 'anonymous'] ?? [];
  const otherRoles = (session?.roles ?? []).filter((role) => role !== session?.active_role);

  return (
    <>
      <header className={styles.header}>
        <div className={styles.inner}>
          <div className={styles.left}>
            {back ? (
              <button
                type="button"
                className={styles.back}
                onClick={() => (typeof back === 'string' ? router.push(back) : router.back())}
                aria-label="Назад"
              >
                <IconArrowLeft size={20} />
              </button>
            ) : (
              <Link href={session ? defaultHome(session.active_role) : '/'} className={styles.brand}>
                <Wordmark size={18} />
              </Link>
            )}
            {title ? <h1 className={styles.title}>{title}</h1> : null}
          </div>

          <nav className={styles.desktopNav} aria-label="Разделы">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={[
                  styles.navLink,
                  pathname === link.href || (link.href !== '/admin' && pathname.startsWith(`${link.href}/`))
                    ? styles.navActive
                    : '',
                ].join(' ')}
              >
                {link.label}
              </Link>
            ))}
          </nav>

          <div className={styles.right}>
            {action}
            {session ? (
              <>
                <Link href="/search" className={styles.iconButton} aria-label="Поиск">
                  <IconSearch size={19} />
                </Link>
                <Link href="/notifications" className={styles.iconButton} aria-label={unread ? `Уведомления: ${unread} новых` : 'Уведомления'}>
                  <IconBell size={19} />
                  {unread ? <span className={styles.bellBadge}>{unread > 9 ? '9+' : unread}</span> : null}
                </Link>
                <button
                  type="button"
                  className={styles.avatarButton}
                  onClick={() => setMenuOpen(true)}
                  aria-label="Меню аккаунта"
                >
                  <Avatar src={session.photo_url} name={session.full_name} size={32} />
                </button>
              </>
            ) : (
              <>
                <Link href="/login" className={styles.plainLink}>
                  Войти
                </Link>
                <Button size="sm" onClick={() => router.push('/register')}>
                  Регистрация
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      <Sheet open={menuOpen} onClose={() => setMenuOpen(false)} title="Аккаунт" size="sm">
        {session ? (
          <div className="av-stack">
            <div className={styles.identity}>
              <Avatar src={session.photo_url} name={session.full_name} size={48} verified={session.identity_verified} />
              <div>
                <p className="av-strong">{session.full_name}</p>
                <p className="av-small av-muted">@{session.username} · {roleLabel(session.active_role)}</p>
              </div>
            </div>

            <div className="av-stack-sm">
              {otherRoles.length > 0 ? (
                <p className="av-small av-muted">
                  Вы в режиме «{roleLabel(session.active_role)}». Переключение меняет, что вы видите и
                  что можете делать — стороны не смешиваются.
                </p>
              ) : null}
              {otherRoles.map((role) => (
                <Button
                  key={role}
                  variant="secondary"
                  block
                  onClick={async () => {
                    await switchRole(role);
                    setMenuOpen(false);
                    router.push(defaultHome(role));
                  }}
                >
                  Переключиться: {roleLabel(role)}
                </Button>
              ))}
              {!session.roles.includes('client') || !session.roles.includes('developer') ? (
                <Link href="/settings#roles" className={styles.menuLink} onClick={() => setMenuOpen(false)}>
                  {session.roles.includes('client') ? 'Стать исполнителем' : 'Стать заказчиком'}
                </Link>
              ) : null}
            </div>

            <div className="av-stack-sm">
              <p className="av-small av-muted">Оформление</p>
              <div className={styles.themeRow}>
                {(['light', 'dark', 'system'] as const).map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={[styles.themeOption, choice === option ? styles.themeActive : ''].join(' ')}
                    onClick={() => setChoice(option)}
                    aria-pressed={choice === option}
                  >
                    {option === 'light' ? <IconSun size={16} /> : option === 'dark' ? <IconMoon size={16} /> : <IconSettings size={16} />}
                    {option === 'light' ? 'Светлая' : option === 'dark' ? 'Тёмная' : 'Как в системе'}
                  </button>
                ))}
              </div>
            </div>

            <div className="av-stack-sm">
              <Link href="/profile" className={styles.menuLink} onClick={() => setMenuOpen(false)}>
                Мой профиль
              </Link>
              {session.active_role === 'developer' ? (
                <Link href="/services/mine" className={styles.menuLink} onClick={() => setMenuOpen(false)}>
                  Мои услуги
                </Link>
              ) : null}
              {session.active_role === 'client' ? (
                <Link href="/freelancers/saved" className={styles.menuLink} onClick={() => setMenuOpen(false)}>
                  Избранные исполнители
                </Link>
              ) : null}
              <Link href="/settings" className={styles.menuLink} onClick={() => setMenuOpen(false)}>
                Настройки
              </Link>
              <button
                type="button"
                className={styles.menuLink}
                onClick={async () => {
                  await signOut();
                  setMenuOpen(false);
                  router.push('/login');
                }}
              >
                Выйти
              </button>
            </div>
          </div>
        ) : null}
      </Sheet>
    </>
  );
}

export function defaultHome(role: string) {
  if (role === 'client') return '/dashboard';
  if (role === 'admin' || role === 'moderator') return '/admin';
  return '/feed';
}
