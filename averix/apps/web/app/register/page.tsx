'use client';

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import styles from '../auth.module.css';
import { Wordmark } from '@/components/nav/Logo';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { ApiFailure, post, setCsrfToken } from '@/lib/api';
import { useSession } from '@/lib/session';
import type { Session } from '@/lib/session';

type Role = 'client' | 'developer';

function RegisterForm() {
  const params = useSearchParams();
  const router = useRouter();
  const { refresh } = useSession();

  const [role, setRole] = useState<Role>(params.get('role') === 'client' ? 'client' : 'developer');
  const [form, setForm] = useState({ full_name: '', username: '', email: '', password: '' });
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

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
        role,
        locale: 'ru',
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      if (session.csrf_token) setCsrfToken(session.csrf_token);
      await refresh();
      // Исполнителю сначала нужна анкета — без неё его никто не найдёт.
      router.replace(role === 'developer' ? '/onboarding' : '/dashboard');
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
        Один аккаунт — одна отправная точка. Вторую роль можно добавить позже.
      </p>

      <div className={styles.roles} role="radiogroup" aria-label="Я здесь, чтобы">
        {(
          [
            { key: 'developer', title: 'Выполнять заказы', body: 'Заполнить анкету, получать подходящие заказы' },
            { key: 'client', title: 'Заказать работу', body: 'Разместить заказ, выбрать исполнителя' },
          ] as const
        ).map((option) => (
          <button
            key={option.key}
            type="button"
            role="radio"
            aria-checked={role === option.key}
            className={[styles.role, role === option.key ? styles.roleActive : ''].join(' ')}
            onClick={() => setRole(option.key)}
          >
            <span className={styles.roleTitle}>{option.title}</span>
            <span className={styles.roleBody}>{option.body}</span>
          </button>
        ))}
      </div>

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
