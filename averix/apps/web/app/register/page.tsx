'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import styles from '../auth.module.css';
import { Wordmark } from '@/components/nav/Logo';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { GoogleButton } from '@/components/auth/GoogleButton';
import { ApiFailure, get, post, setCsrfToken } from '@/lib/api';
import { useSession } from '@/lib/session';
import type { Session } from '@/lib/session';

/**
 * Регистрация спрашивает ровно то, без чего аккаунта не существует.
 *
 * Кем человек будет на площадке — исполнителем или заказчиком — спрашивается
 * следующим экраном, двумя карточками. Этот вопрос заданный здесь, между
 * почтой и паролем, человек отвечает до того, как увидел площадку, и половина
 * отвечает наугад. Документов и телефона на этом шаге нет вовсе: проверка
 * личности — дело добровольное и позднее.
 */
function RegisterForm() {
  const router = useRouter();
  const { refresh } = useSession();

  const [form, setForm] = useState({ full_name: '', username: '', email: '', password: '' });
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [google, setGoogle] = useState(false);

  useEffect(() => {
    get<{ google: boolean }>('/auth/providers')
      .then((providers) => setGoogle(Boolean(providers.google)))
      .catch(() => setGoogle(false));
  }, []);

  function update(key: keyof typeof form) {
    return (event: React.ChangeEvent<HTMLInputElement>) =>
      setForm((current) => ({ ...current, [key]: event.target.value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFields({});
    setMessage('');
    try {
      const session = await post<Session>('/auth/register', {
        ...form,
        accept_terms: acceptTerms,
        email: form.email.trim(),
        username: form.username.trim().toLowerCase(),
        // Роль здесь не передаётся вовсе: вход один для всех, вопрос — на
        // следующем экране. API её принимает, но только ради старых ссылок.
        locale: 'ru',
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      if (session.csrf_token) setCsrfToken(session.csrf_token);
      await refresh();
      if (session.active_role === 'developer') router.replace('/onboarding');
      else if (session.active_role === 'client') router.replace('/dashboard');
      else router.replace('/welcome');
    } catch (error) {
      if (error instanceof ApiFailure) {
        setFields(error.fields);
        setMessage(error.fields && Object.keys(error.fields).length ? '' : error.message);
      } else {
        setMessage('Не удалось связаться с сервером. Проверьте подключение и попробуйте ещё раз.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={styles.card} onSubmit={submit} noValidate>
      <h1 className={styles.title}>Создать аккаунт</h1>
      <p className={styles.subtitle}>
        Две минуты. Кем вы будете здесь — исполнителем или заказчиком — спросим на следующем шаге.
      </p>

      {google ? (
        <>
          <GoogleButton label="Продолжить с Google" />
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
        label="Имя и фамилия"
        name="full_name"
        autoComplete="name"
        required
        value={form.full_name}
        error={fields.full_name}
        onChange={update('full_name')}
      />
      <Input
        label="Имя пользователя"
        name="username"
        autoComplete="username"
        required
        prefix="@"
        hint="Это адрес вашего профиля: averix.dev/@username. Латиница, цифры, дефис."
        value={form.username}
        error={fields.username}
        onChange={update('username')}
      />
      <Input
        label="Электронная почта"
        type="email"
        name="email"
        autoComplete="email"
        inputMode="email"
        required
        value={form.email}
        error={fields.email}
        onChange={update('email')}
      />
      <Input
        label="Пароль"
        type="password"
        name="password"
        autoComplete="new-password"
        required
        hint="Не короче 12 символов. Фразу из нескольких слов легче запомнить и труднее подобрать."
        value={form.password}
        error={fields.password}
        onChange={update('password')}
      />

      <label className={styles.terms}>
        <input
          type="checkbox"
          checked={acceptTerms}
          onChange={(event) => setAcceptTerms(event.target.checked)}
        />
        <span>
          Я принимаю условия использования AVERIX и политику конфиденциальности.
          {fields.accept_terms ? <span className={styles.termsError}> {fields.accept_terms}</span> : null}
        </span>
      </label>

      <Button type="submit" size="lg" block loading={busy} disabled={!acceptTerms}>
        Создать аккаунт
      </Button>

      <p className={styles.switch}>
        Уже есть аккаунт? <Link href="/login">Войти</Link>
      </p>
    </form>
  );
}

export default function RegisterPage() {
  return (
    <main id="main" className={styles.page}>
      <Link href="/" className={styles.brand}>
        <Wordmark size={20} />
      </Link>
      <Suspense fallback={null}>
        <RegisterForm />
      </Suspense>
    </main>
  );
}
