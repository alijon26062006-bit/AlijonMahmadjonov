'use client';

import { useState } from 'react';
import Link from 'next/link';
import styles from '../auth.module.css';
import { Wordmark } from '@/components/nav/Logo';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { ApiFailure, post } from '@/lib/api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      await post('/auth/password/forgot', { email: email.trim() });
      setSent(true);
    } catch (error) {
      setMessage(error instanceof ApiFailure ? error.message : 'Не удалось связаться с сервером.');
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
        <h1 className={styles.title}>Восстановление пароля</h1>
        {sent ? (
          <p className={styles.subtitle}>
            Если на адрес <strong>{email}</strong> зарегистрирован аккаунт, мы отправили письмо со
            ссылкой для смены пароля. Ссылка действует ограниченное время.
          </p>
        ) : (
          <>
            <p className={styles.subtitle}>Укажите почту — пришлём ссылку для смены пароля.</p>
            {message ? (
              <p className={styles.alert} role="alert">
                {message}
              </p>
            ) : null}
            <Input
              label="Электронная почта"
              type="email"
              name="email"
              autoComplete="email"
              inputMode="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <Button type="submit" size="lg" block loading={busy}>
              Отправить ссылку
            </Button>
          </>
        )}
        <p className={styles.switch}>
          <Link href="/login">Вернуться ко входу</Link>
        </p>
      </form>
    </main>
  );
}
