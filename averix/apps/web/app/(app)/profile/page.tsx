'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/lib/session';

/** Your own profile is the public one — seen exactly as a client sees it. */
export default function ProfileRedirect() {
  const { session, loading } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (loading || !session) return;
    router.replace(
      session.active_role === 'developer' ? `/developers/${session.username}` : '/settings',
    );
  }, [session, loading, router]);

  return null;
}
