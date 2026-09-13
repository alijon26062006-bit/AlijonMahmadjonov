'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { BottomNav } from '@/components/nav/BottomNav';
import { useSession } from '@/lib/session';
import { get } from '@/lib/api';

/**
 * The signed-in shell.
 *
 * Anyone who lands here without a session is sent to sign in, carrying where
 * they were going so they arrive there afterwards rather than at a generic
 * home screen.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { session, loading } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (loading) return;
    if (!session) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    // Зарегистрировался и закрыл вкладку на вопросе «работать или заказывать».
    // Пока на него нет ответа, ни один из двух интерфейсов не покажет ничего
    // осмысленного — и API их всё равно не отдаст.
    if (session.active_role === 'pending') {
      router.replace('/welcome');
    }
  }, [loading, session, router, pathname]);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    get<{ unread: number }>('/conversations/unread')
      .then((data) => !cancelled && setUnread(data.unread))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [session, pathname]);

  // Нижняя навигация принадлежит роли; пока роли нет, показывать нечего.
  if (session?.active_role === 'pending') {
    return <main id="main">{children}</main>;
  }

  return (
    <>
      <main id="main">{children}</main>
      <BottomNav unread={unread} />
    </>
  );
}
