'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import styles from '../../auth.module.css';
import { Wordmark } from '@/components/nav/Logo';
import { ApiFailure, post } from '@/lib/api';
import { useSession } from '@/lib/session';
import { ButtonLink } from '@/components/ui/Button';
import { defaultHome } from '@/components/nav/TopBar';

export default function VerifyEmailPage() {
  const { token } = useParams<{ token: string }>();
  const { session, refresh } = useSession();
  const [state, setState] = useState<'working' | 'done' | 'failed'>('working');
  const [message, setMessage] = useState('');

  useEffect(() => {
    let cancelled = false;
    post('/auth/email/verify', { token })
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
        <h1 className={styles.title}>Подтверждение почты</h1>
        {state === 'working' ? <p className={styles.subtitle}>Проверяем ссылку…</p> : null}
        {state === 'done' ? (
          <>
            <p className={styles.subtitle}>Адрес подтверждён. Теперь вам доступны все действия на платформе.</p>
            <ButtonLink href={session ? defaultHome(session.active_role) : '/login'} size="lg" block>
              Продолжить
            </ButtonLink>
          </>
        ) : null}
        {state === 'failed' ? (
          <>
            <p className={styles.alert} role="alert">
              {message}
            </p>
            <p className={styles.subtitle}>
              Ссылка могла устареть. Новую можно запросить в настройках аккаунта после входа.
            </p>
            <ButtonLink href="/login" size="lg" block variant="secondary">
              Войти
            </ButtonLink>
          </>
        ) : null}
      </div>
    </main>
  );
}
