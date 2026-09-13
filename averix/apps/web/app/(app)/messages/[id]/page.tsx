'use client';

import { use, useEffect } from 'react';
import { useRouter } from 'next/navigation';

/** Ссылки из уведомлений ведут на /messages/<id>; сам экран живёт на /messages. */
export default function MessageThreadRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  useEffect(() => {
    router.replace(`/messages?thread=${encodeURIComponent(id)}`);
  }, [id, router]);
  return null;
}
