'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import styles from '../../auth.module.css';
import { Wordmark } from '@/components/nav/Logo';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { ApiFailure, post } from '@/lib/api';

export default function ResetPasswordPage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (password !== repeat) {
      setFields({ repeat: 'Пароли не совпадают.' });
      return;
    }
    setBusy(true);
    setFields({});
    setMessage('');
    try {
      await post('/auth/password/reset', { token, password });
      setDone(true);
      setTimeout(() => router.replace('/login'), 2500);
    } catch (error) {
      if (error instanceof ApiFailure) {
        setFields(error.fields);
        setMessage(Object.keys(error.fields).length ? '' : error.message);
      } else {
        setMessage('Не удалось связаться с сервером.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className={styles.page}>
      <Link href="/" className={styles.brand}>
        <Wordmark size={20} />
      </Link>
      <form className={styles.card} onSubmit={submit} noValidate>
        <h1 className={styles.title}>Новый пароль</h1>
        {done ? (
          <p className={styles.subtitle}>Пароль изменён. Сейчас перенаправим на страницу входа.</p>
        ) : (
          <>
            <p className={styles.subtitle}>Все другие сеансы будут завершены.</p>
            {message ? (
              <p className={styles.alert} role="alert">
                {message}
              </p>
            ) : null}
            <Input
              label="Новый пароль"
              type="password"
              autoComplete="new-password"
              required
              hint="Не короче 12 символов."
              value={password}
              error={fields.password ?? fields.token}
              onChange={(event) => setPassword(event.target.value)}
            />
            <Input
              label="Повторите пароль"
              type="password"
              autoComplete="new-password"
              required
              value={repeat}
              error={fields.repeat}
              onChange={(event) => setRepeat(event.target.value)}
            />
            <Button type="submit" size="lg" block loading={busy}>
              Сохранить пароль
            </Button>
          </>
        )}
        <p className={styles.switch}>
          <Link href="/forgot-password">Запросить новую ссылку</Link>
        </p>
      </form>
    </main>
  );
}
