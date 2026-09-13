'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import styles from '../../auth.module.css';
import { Wordmark } from '@/components/nav/Logo';
import { ApiFailure, post } from '@/lib/api';
import { useSession } from '@/lib/session';
import { ButtonLink } from '@/components/ui/Button';

export default function ConfirmEmailChangePage() {
  const { token } = useParams<{ token: string }>();
  const { refresh } = useSession();
  const [state, setState] = useState<'working' | 'done' | 'failed'>('working');
  const [message, setMessage] = useState('');

  useEffect(() => {
    let cancelled = false;
    post('/account/email/confirm', { token })
      .then(async () => {
        await refresh();
        if (!cancelled) setState('done');
      })
      .catch((error) => {
        if (cancelled) return;
        setState('failed');
        setMessage(error instanceof ApiFailure ? error.message : 'Не удалось связаться с сервером.');
      });
    return () => {
      cancelled = true;
    };
  }, [token, refresh]);

  return (
    <main id="main" className={styles.page}>
      <Link href="/" className={styles.brand}>
        <Wordmark size={20} />
      </Link>
      <div className={styles.card}>
        <h1 className={styles.title}>Смена почты</h1>
        {state === 'working' ? <p className={styles.subtitle}>Проверяем ссылку…</p> : null}
        {state === 'done' ? (
          <>
            <p className={styles.subtitle}>Новый адрес подтверждён и уже используется для входа и писем.</p>
            <ButtonLink href="/settings" size="lg" block>
              К настройкам
            </ButtonLink>
          </>
        ) : null}
        {state === 'failed' ? (
          <>
            <p className={styles.alert} role="alert">
              {message}
            </p>
            <ButtonLink href="/settings" size="lg" block variant="secondary">
              К настройкам
            </ButtonLink>
          </>
        ) : null}
      </div>
    </main>
  );
}
