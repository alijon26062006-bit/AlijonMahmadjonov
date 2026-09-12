'use client';

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import styles from '../auth.module.css';
import { Wordmark } from '@/components/nav/Logo';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { useSession } from '@/lib/session';
import { ApiFailure } from '@/lib/api';
import { defaultHome } from '@/components/nav/TopBar';

function LoginForm() {
  const { signIn } = useSession();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get('next');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFields({});
    setMessage('');
    try {
      const session = await signIn(email.trim(), password);
      router.replace(next || defaultHome(session.active_role));
    } catch (error) {
      if (error instanceof ApiFailure) {
        setFields(error.fields);
        setMessage(error.message);
      } else {
        setMessage("We couldn't reach the server. Please check your connection and try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={styles.card} onSubmit={submit} noValidate>
      <h1 className={styles.title}>Sign in</h1>
      <p className={styles.subtitle}>Welcome back.</p>

      {message ? (
        <p className={styles.alert} role="alert">
          {message}
        </p>
      ) : null}

      <Input
        label="Email"
        type="email"
        name="email"
        autoComplete="email"
        inputMode="email"
        required
        value={email}
        error={fields.email}
        onChange={(event) => setEmail(event.target.value)}
      />
      <Input
        label="Password"
        type="password"
        name="password"
        autoComplete="current-password"
        required
        value={password}
        error={fields.password}
        onChange={(event) => setPassword(event.target.value)}
      />

      <Button type="submit" size="lg" block loading={busy}>
        Sign in
      </Button>

      <p className={styles.switch}>
        New to AVERIX? <Link href="/register">Create an account</Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main id="main" className={styles.page}>
      <Link href="/" className={styles.brand}>
        <Wordmark size={20} />
      </Link>
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
