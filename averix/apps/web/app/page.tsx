'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import styles from './landing.module.css';
import { Wordmark } from '@/components/nav/Logo';
import { Button, ButtonLink } from '@/components/ui/Button';
import { IconCheck, IconLock, IconShield } from '@/components/ui/Icon';
import { useSession } from '@/lib/session';
import { defaultHome } from '@/components/nav/TopBar';
import { SECTORS } from '@/lib/labels';

export default function Landing() {
  const { session, loading } = useSession();
  const router = useRouter();

  // Тому, кто уже вошёл, презентация не нужна.
  useEffect(() => {
    if (!loading && session) router.replace(defaultHome(session.active_role));
  }, [loading, session, router]);

  return (
    <main id="main" className={styles.page}>
      <header className={styles.header}>
        <Wordmark size={20} />
        <div className="av-row">
          <Link href="/login" className={styles.signIn}>
            Войти
          </Link>
          <Button size="sm" onClick={() => router.push('/register')}>
            Регистрация
          </Button>
        </div>
      </header>

      <section className={styles.hero}>
        <p className={styles.eyebrow}>Для заказчиков и исполнителей</p>
        <h1 className={styles.title}>
          Фриланс, где работу <span className={styles.accent}>можно проверить</span>
        </h1>
        <p className={styles.lede}>
          Дизайн, тексты, сайты, реклама, видео, бухгалтерия — исполнители в любой области.
          Каждая завершённая сделка сама попадает в профиль исполнителя вместе с отзывом
          заказчика и сроком сдачи. Такую историю нельзя написать руками — поэтому ей можно
          верить.
        </p>
        <div className={styles.actions}>
          <ButtonLink href="/register?role=client" size="lg">
            Заказать работу
          </ButtonLink>
          <ButtonLink href="/register?role=developer" size="lg" variant="secondary">
            Стать исполнителем
          </ButtonLink>
        </div>
      </section>

      <section className={styles.points}>
        {SECTORS.map((sector) => (
          <Link key={sector.slug} href={`/freelancers?sector=${sector.slug}`} className={styles.point}>
            <h2 className={styles.pointTitle}>{sector.name}</h2>
            <p className={styles.pointBody}>{sector.hint}</p>
          </Link>
        ))}
      </section>

      <section className={styles.points}>
        {[
          {
            icon: <IconShield size={18} />,
            title: 'Проверенная история, а не обещания',
            body: 'Завершённые на AVERIX заказы появляются в профиле автоматически и помечаются как подтверждённые. Работы из портфолио показываются отдельно — и подписаны как портфолио.',
          },
          {
            icon: <IconCheck size={18} />,
            title: 'Заказ находит нужных людей',
            body: 'Логотип видят дизайнеры, а не все подряд; Telegram-бот на Python — разработчики ботов. Подбор объясняет себя: каким требованиям вы соответствуете, а каким нет.',
          },
          {
            icon: <IconLock size={18} />,
            title: 'Безопасная сделка',
            body: 'Заказчик резервирует оплату по этапу, исполнитель сдаёт работу, деньги переходят после приёмки. Спор разбирает платформа, а не тот, кто громче.',
          },
        ].map((point) => (
          <article key={point.title} className={styles.point}>
            <span className={styles.pointIcon}>{point.icon}</span>
            <h2 className={styles.pointTitle}>{point.title}</h2>
            <p className={styles.pointBody}>{point.body}</p>
          </article>
        ))}
      </section>

      <footer className={styles.footer}>
        <Wordmark size={16} />
        <p className="av-small av-faint">
          Биржа удалённой работы. Оплата проходит по этапам и подтверждается платформой.
        </p>
      </footer>
    </main>
  );
}
