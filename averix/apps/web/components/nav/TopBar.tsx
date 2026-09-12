'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';
import styles from './TopBar.module.css';
import { Wordmark } from './Logo';
import { Avatar } from '@/components/ui/Avatar';
import { Sheet } from '@/components/ui/Sheet';
import { Button } from '@/components/ui/Button';
import {
  IconArrowLeft,
  IconBell,
  IconMoon,
  IconSearch,
  IconSun,
  IconSettings,
} from '@/components/ui/Icon';
import { useSession } from '@/lib/session';
import { useTheme } from '@/lib/theme';

const DESKTOP_LINKS: Record<string, { href: string; label: string }[]> = {
  developer: [
    { href: '/feed', label: 'Find work' },
    { href: '/contracts', label: 'Contracts' },
    { href: '/messages', label: 'Messages' },
    { href: '/earnings', label: 'Earnings' },
  ],
  client: [
    { href: '/dashboard', label: 'My work' },
    { href: '/talent', label: 'Find developers' },
    { href: '/messages', label: 'Messages' },
  ],
  admin: [
    { href: '/admin', label: 'Overview' },
    { href: '/admin/payments', label: 'Payments' },
  ],
};

/**
 * The header. On a phone it is a thin bar with a back affordance and the two
 * things a person reaches for; from laptop up it carries the destinations the
 * bottom bar shows on mobile.
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

  const links = DESKTOP_LINKS[session?.active_role === 'moderator' ? 'admin' : session?.active_role ?? 'developer'] ?? [];
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
                aria-label="Back"
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

          <nav className={styles.desktopNav} aria-label="Sections">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={[
                  styles.navLink,
                  pathname === link.href || pathname.startsWith(`${link.href}/`) ? styles.navActive : '',
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
                <Link href="/search" className={styles.iconButton} aria-label="Search">
                  <IconSearch size={19} />
                </Link>
                <Link href="/notifications" className={styles.iconButton} aria-label="Notifications">
                  <IconBell size={19} />
                </Link>
                <button
                  type="button"
                  className={styles.avatarButton}
                  onClick={() => setMenuOpen(true)}
                  aria-label="Account menu"
                >
                  <Avatar src={session.photo_url} name={session.full_name} size={32} />
                </button>
              </>
            ) : (
              <>
                <Link href="/login" className={styles.plainLink}>
                  Sign in
                </Link>
                <Button size="sm" onClick={() => router.push('/register')}>
                  Join
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      <Sheet open={menuOpen} onClose={() => setMenuOpen(false)} title="Account" size="sm">
        {session ? (
          <div className="av-stack">
            <div className={styles.identity}>
              <Avatar src={session.photo_url} name={session.full_name} size={48} verified={session.identity_verified} />
              <div>
                <p className="av-strong">{session.full_name}</p>
                <p className="av-small av-muted">@{session.username}</p>
              </div>
            </div>

            {otherRoles.length > 0 ? (
              <div className="av-stack-sm">
                <p className="av-small av-muted">
                  You are in the {label(session.active_role)} interface. Switching changes what you
                  see and what you can do — the two sides stay separate.
                </p>
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
                    Switch to {label(role)}
                  </Button>
                ))}
              </div>
            ) : null}

            <div className="av-stack-sm">
              <p className="av-small av-muted">Appearance</p>
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
                    {option === 'light' ? 'Light' : option === 'dark' ? 'Dark' : 'System'}
                  </button>
                ))}
              </div>
            </div>

            <div className="av-stack-sm">
              <Link href="/profile" className={styles.menuLink} onClick={() => setMenuOpen(false)}>
                Your profile
              </Link>
              <Link href="/settings" className={styles.menuLink} onClick={() => setMenuOpen(false)}>
                Settings
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
                Sign out
              </button>
            </div>
          </div>
        ) : null}
      </Sheet>
    </>
  );
}

function label(role: string) {
  return role === 'client' ? 'client' : role === 'developer' ? 'developer' : role;
}

export function defaultHome(role: string) {
  if (role === 'client') return '/dashboard';
  if (role === 'admin' || role === 'moderator') return '/admin';
  return '/feed';
}
