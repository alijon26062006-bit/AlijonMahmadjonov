'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './profile.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { ButtonLink } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ReviewCard } from '@/components/domain/ReviewPanel';
import { IconAlert, IconLock, IconShield, IconStarFilled } from '@/components/ui/Icon';
import { get } from '@/lib/api';
import { plural, shortDate } from '@/lib/format';
import { COMPANY_SIZE, countryName } from '@/lib/labels';
import { useSession } from '@/lib/session';
import type { ClientProfile, ContractCard, Review } from '@/lib/types';

/**
 * Your own profile.
 *
 * A freelancer's profile is the public one — what a client sees is exactly
 * what they should be looking at, so that redirect stays. A client has no
 * public page worth landing on, but they do have a history: what they have
 * posted, who they hired, what they are owed reviews on, and what they have
 * spent. That last figure is theirs alone and is never shown to anyone else.
 */
export default function ProfilePage() {
  const { session, loading } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (loading || !session) return;
    if (session.active_role === 'developer') {
      router.replace(`/developers/${session.username}`);
    }
  }, [session, loading, router]);

  if (!session || session.active_role === 'developer') {
    return (
      <>
        <TopBar title="Профиль" />
        <div className="av-page av-stack">
          <Skeleton height={120} radius="var(--av-radius-xl)" />
        </div>
      </>
    );
  }

  return <ClientProfileScreen />;
}

function ClientProfileScreen() {
  const { session } = useSession();
  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [contracts, setContracts] = useState<ContractCard[] | null>(null);
  const [reviews, setReviews] = useState<Review[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    get<ClientProfile>('/clients/me')
      .then((data) => {
        if (cancelled) return;
        setProfile(data);
        get<Review[]>(`/clients/${data.username}/reviews`)
          .then((list) => !cancelled && setReviews(list ?? []))
          .catch(() => !cancelled && setReviews([]));
      })
      .catch(() => !cancelled && setFailed(true));
    get<ContractCard[]>('/contracts')
      .then((list) => !cancelled && setContracts(list ?? []))
      .catch(() => !cancelled && setContracts([]));
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) {
    return (
      <>
        <TopBar title="Профиль" />
        <div className="av-page">
          <EmptyState
            tone="error"
            icon={<IconAlert size={20} />}
            title="Не удалось загрузить профиль"
            description="Попробуйте обновить страницу через минуту."
          />
        </div>
      </>
    );
  }

  if (!profile) {
    return (
      <>
        <TopBar title="Профиль" />
        <div className="av-page av-stack">
          <Skeleton height={140} radius="var(--av-radius-xl)" />
          <Skeleton height={90} />
        </div>
      </>
    );
  }

  const active = (contracts ?? []).filter(
    (contract) => contract.status !== 'completed' && contract.status !== 'cancelled',
  ).length;
  const completed = (contracts ?? []).filter((contract) => contract.status === 'completed').length;
  const location = [profile.city, countryName(profile.country_code)].filter(Boolean).join(', ');

  return (
    <>
      <TopBar title="Профиль" />
      <div className={`av-page av-stack ${styles.shell}`}>
        <Card>
          <div className={styles.identity}>
            <Avatar
              src={session?.photo_url}
              name={profile.company_name || profile.full_name}
              size={64}
              verified={profile.identity_verified}
            />
            <div className="av-grow">
              <h1 className={styles.name}>{profile.company_name || profile.full_name}</h1>
              <p className={styles.handle}>
                @{profile.username}
                {profile.company_name ? ` · ${profile.full_name}` : ''}
              </p>
              <p className={styles.handle}>
                {location ? `${location} · ` : ''}
                на AVERIX с {shortDate(profile.member_since)}
              </p>
            </div>
          </div>

          <div className={styles.badges}>
            <Badge tone={session?.email_verified ? 'success' : 'warning'} size="sm">
              {session?.email_verified ? 'Почта подтверждена' : 'Почта не подтверждена'}
            </Badge>
            <Badge tone={profile.identity_verified ? 'verified' : 'neutral'} size="sm" icon={<IconShield size={13} />}>
              {profile.identity_verified ? 'Личность подтверждена' : 'Личность не подтверждена'}
            </Badge>
            {profile.payment_verified ? (
              <Badge tone="success" size="sm">
                Оплата подтверждена
              </Badge>
            ) : null}
          </div>

          <div className={styles.stats}>
            <Stat label="Заказов" value={String(profile.projects_posted)} note="размещено всего" />
            <Stat label="Нанято" value={String(profile.hires_made)} note={plural(profile.hires_made, 'исполнитель', 'исполнителя', 'исполнителей').replace(/^\d+\s/, '')} />
            <Stat
              label="В работе"
              value={contracts === null ? '—' : String(active)}
              note={contracts === null ? 'загружаем' : `завершено ${completed}`}
            />
            <Stat
              label="Рейтинг"
              value={profile.rating_avg ? profile.rating_avg.toFixed(1) : '—'}
              note={
                profile.rating_count
                  ? plural(profile.rating_count, 'отзыв', 'отзыва', 'отзывов')
                  : 'исполнители ещё не оценивали'
              }
            />
          </div>

          {profile.spent?.length ? (
            <>
              <div className={styles.stats}>
                {profile.spent.map((row) => (
                  <Stat
                    key={row.currency}
                    label="Оплачено"
                    value={row.display}
                    note="по подтверждённым платежам"
                  />
                ))}
              </div>
              <p className={styles.private}>
                <IconLock size={12} /> Эту сумму видите только вы. Исполнителям она не показывается.
              </p>
            </>
          ) : null}

          <div className={styles.links}>
            <ButtonLink href="/dashboard" size="sm">
              Мои заказы
            </ButtonLink>
            <ButtonLink href="/freelancers/saved" size="sm" variant="secondary">
              Избранные исполнители
            </ButtonLink>
            <ButtonLink href="/settings" size="sm" variant="secondary">
              Настройки
            </ButtonLink>
          </div>
        </Card>

        {profile.about || profile.company_name ? (
          <Card>
            <h2 className={styles.sectionTitle}>О компании</h2>
            {profile.company_name ? (
              <div className={styles.row}>
                <span className="av-muted">Название</span>
                <strong>{profile.company_name}</strong>
              </div>
            ) : null}
            {profile.company_size ? (
              <div className={styles.row}>
                <span className="av-muted">Размер</span>
                <strong>{COMPANY_SIZE[profile.company_size] ?? profile.company_size}</strong>
              </div>
            ) : null}
            {profile.industry ? (
              <div className={styles.row}>
                <span className="av-muted">Сфера</span>
                <strong>{profile.industry}</strong>
              </div>
            ) : null}
            {profile.company_website ? (
              <div className={styles.row}>
                <span className="av-muted">Сайт</span>
                <a href={profile.company_website} target="_blank" rel="noopener noreferrer nofollow">
                  {profile.company_website.replace(/^https?:\/\//, '')}
                </a>
              </div>
            ) : null}
            {profile.about ? <p className={styles.about}>{profile.about}</p> : null}
          </Card>
        ) : (
          <Card>
            <h2 className={styles.sectionTitle}>О компании</h2>
            <p className="av-small av-muted">
              Исполнители видят это, когда решают, браться ли за ваш заказ. Пара предложений о том,
              чем вы занимаетесь, заметно повышает качество откликов.
            </p>
            <div className={styles.links}>
              <ButtonLink href="/settings" size="sm" variant="secondary">
                Заполнить
              </ButtonLink>
            </div>
          </Card>
        )}

        <section className="av-stack-sm">
          <h2 className={styles.sectionTitle}>Отзывы исполнителей о вас</h2>
          {reviews === null ? (
            <Skeleton height={100} />
          ) : reviews.length === 0 ? (
            <EmptyState
              icon={<IconStarFilled size={20} />}
              title="Отзывов пока нет"
              description="Исполнитель оставляет отзыв после завершения сделки — о том, насколько понятно поставлена задача и вовремя ли прошла оплата. Отзыв виден обоим только после того, как обе стороны напишут свой."
            />
          ) : (
            reviews.map((review) => <ReviewCard key={review.id} review={review} />)
          )}
        </section>
      </div>
    </>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue}>{value}</span>
      <span className={styles.statNote}>{note}</span>
    </div>
  );
}
