'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './welcome.module.css';
import { Wordmark } from '@/components/nav/Logo';
import { ApiFailure, post, setCsrfToken } from '@/lib/api';
import { useSession } from '@/lib/session';
import type { Session } from '@/lib/session';

type Choice = 'developer' | 'client';

/**
 * Один вопрос, две карточки.
 *
 * Он задаётся после регистрации, а не во время: человек уже внутри, аккаунт
 * уже есть, и ответ здесь ничего не «создаёт» — он открывает ту половину
 * площадки, ради которой человек пришёл. Вторую можно добавить потом в
 * настройках, и об этом сказано прямо здесь, чтобы выбор не казался
 * необратимым.
 */
export default function WelcomePage() {
  const router = useRouter();
  const { session, loading, refresh } = useSession();
  const [busy, setBusy] = useState<Choice | null>(null);
  const [error, setError] = useState('');
  // Выбор уже сделан в этой вкладке: сессия вот-вот станет «исполнителем», и
  // проверка ниже не должна перехватить человека по дороге в анкету.
  const decided = useRef(false);

  // Сюда попадают только те, у кого роли ещё нет. У остальных тут нет дела.
  useEffect(() => {
    if (loading || decided.current) return;
    if (!session) {
      router.replace('/login');
      return;
    }
    if (session.active_role && session.active_role !== 'pending') {
      router.replace(session.active_role === 'developer' ? '/feed' : '/dashboard');
    }
  }, [loading, session, router]);

  async function choose(role: Choice) {
    decided.current = true;
    setBusy(role);
    setError('');
    try {
      const next = await post<Session>('/auth/role/choose', { role });
      if (next.csrf_token) setCsrfToken(next.csrf_token);
      await refresh();
      // Исполнителю сразу анкета: без неё его никто не найдёт. Заказчику —
      // рабочий стол, где уже можно разместить заказ.
      router.replace(role === 'developer' ? '/onboarding' : '/dashboard');
    } catch (failure) {
      if (failure instanceof ApiFailure && failure.code === 'role_already_chosen') {
        await refresh();
        router.replace(role === 'developer' ? '/feed' : '/dashboard');
        return;
      }
      setError(
        failure instanceof ApiFailure ? failure.fields.role || failure.message : 'Не получилось. Попробуйте ещё раз.',
      );
      decided.current = false;
      setBusy(null);
    }
  }

  return (
    <main id="main" className={styles.page}>
      <Wordmark size={20} />

      <div className={styles.head}>
        <h1 className={styles.title}>Что вас сюда привело?</h1>
        <p className={styles.subtitle}>
          Выберите одно. Вторую сторону можно будет добавить в настройках — аккаунт останется тот же.
        </p>
      </div>

      {error ? (
        <p className={styles.alert} role="alert">
          {error}
        </p>
      ) : null}

      <div className={styles.cards}>
        <button
          type="button"
          className={styles.card}
          disabled={busy !== null}
          aria-busy={busy === 'developer'}
          onClick={() => void choose('developer')}
        >
          <span className={styles.icon}>
            <BriefcaseIcon />
          </span>
          <span className={styles.cardTitle}>Я хочу работать и зарабатывать</span>
          <span className={styles.cardBody}>
            Анкета, портфолио и услуги. Заказы приходят сами, когда подходят вам по профессии и цене.
          </span>
          <span className={styles.cardRole}>Исполнитель</span>
        </button>

        <button
          type="button"
          className={styles.card}
          disabled={busy !== null}
          aria-busy={busy === 'client'}
          onClick={() => void choose('client')}
        >
          <span className={styles.icon}>
            <OrderIcon />
          </span>
          <span className={styles.cardTitle}>Я хочу заказать услугу</span>
          <span className={styles.cardBody}>
            Опишите задачу — или купите готовую услугу с фиксированной ценой и сроком. Деньги держатся до
            приёмки.
          </span>
          <span className={styles.cardRole}>Заказчик</span>
        </button>
      </div>

      <p className={styles.note}>
        Ни документов, ни телефона сейчас не нужно. Проверка личности — добровольная, и живёт в настройках.
      </p>
    </main>
  );
}

/** Чемодан. Линии 1.6 на сетке 24 — как у всех иконок продукта. */
function BriefcaseIcon() {
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="2.5" y="7" width="19" height="13" rx="2.5" />
      <path d="M8.5 7V5.5A1.5 1.5 0 0 1 10 4h4a1.5 1.5 0 0 1 1.5 1.5V7" />
      <path d="M2.5 12.5h19" />
      <path d="M10 12.5v1.5h4v-1.5" />
    </svg>
  );
}

/** Корзина заказа. */
function OrderIcon() {
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M3 4h2.2l1.5 9.2a2 2 0 0 0 2 1.7h7.1a2 2 0 0 0 2-1.6L19.5 7H6" />
      <circle cx="10" cy="19" r="1.4" />
      <circle cx="16.5" cy="19" r="1.4" />
    </svg>
  );
}
