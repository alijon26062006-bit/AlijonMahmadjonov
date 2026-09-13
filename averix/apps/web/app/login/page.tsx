'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import styles from '../auth.module.css';
import { Wordmark } from '@/components/nav/Logo';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { useSession } from '@/lib/session';
import { ApiFailure, get } from '@/lib/api';
import { GoogleButton } from '@/components/auth/GoogleButton';
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
  const [google, setGoogle] = useState(false);

  useEffect(() => {
    get<{ google: boolean }>('/auth/providers')
      .then((providers) => setGoogle(Boolean(providers.google)))
      .catch(() => setGoogle(false));
  }, []);

  // Возврат из Google, который не получился. Причину показываем словами, а не
  // кодом: «вы отменили вход» и «что-то сломалось» — разные вещи.
  const googleProblem = params.get('google');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFields({});
    setMessage('');
    try {
      const session = await signIn(email.trim(), password);
      // Роль ещё не выбрана — сначала тот самый вопрос, куда бы человек ни шёл.
      router.replace(
        session.active_role === 'pending' ? '/welcome' : next || defaultHome(session.active_role),
      );
    } catch (error) {
      if (error instanceof ApiFailure) {
        setFields(error.fields);
        setMessage(error.message);
      } else {
        setMessage('Не удалось связаться с сервером. Проверьте подключение и попробуйте ещё раз.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={styles.card} onSubmit={submit} noValidate>
      <h1 className={styles.title}>Вход</h1>
      <p className={styles.subtitle}>С возвращением.</p>

      {googleProblem ? (
        <p className={styles.alert} role="alert">
          {googleProblem === 'access_denied'
            ? 'Вход через Google отменён — ничего не изменилось.'
            : 'Через Google войти не удалось. Попробуйте ещё раз или войдите по почте.'}
        </p>
      ) : null}

      {google ? (
        <>
          <GoogleButton label="Войти через Google" next={next ?? undefined} />
          <div className={styles.divider}>
            <span>или почтой</span>
          </div>
        </>
      ) : null}

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
        error={fields.email}
        onChange={(event) => setEmail(event.target.value)}
      />
      <Input
        label="Пароль"
        type="password"
        name="password"
        autoComplete="current-password"
        required
        value={password}
        error={fields.password}
        onChange={(event) => setPassword(event.target.value)}
      />

      <Button type="submit" size="lg" block loading={busy}>
        Войти
      </Button>

      <p className={styles.switch}>
        <Link href="/forgot-password">Забыли пароль?</Link>
      </p>
      <p className={styles.switch}>
        Впервые на AVERIX? <Link href="/register">Создать аккаунт</Link>
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
