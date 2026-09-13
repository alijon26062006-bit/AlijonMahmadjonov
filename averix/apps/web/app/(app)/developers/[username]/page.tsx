'use client';

import { use, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import styles from './profile.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Tabs } from '@/components/ui/Tabs';
import { PortfolioGrid } from '@/components/domain/PortfolioGrid';
import { PreviewBrowser } from '@/components/domain/PreviewBrowser';
import { ReviewCard } from '@/components/domain/ReviewPanel';
import { ReportSheet } from '@/components/domain/ReportSheet';
import { ServiceCard } from '@/components/domain/ServiceCard';
import {
  IconAlert,
  IconCheck,
  IconClock,
  IconGitHub,
  IconShield,
  IconStarFilled,
} from '@/components/ui/Icon';
import { del, get, post } from '@/lib/api';
import { avatarURL } from '@/lib/photo';
import { days, money, plural, shortDate } from '@/lib/format';
import { AVAILABILITY } from '@/lib/labels';
import { useSession } from '@/lib/session';
import type { HistoryEntry, PortfolioCard, PublicProfile, Review, ServiceCard as ServiceCardType } from '@/lib/types';

const TABS = [
  { key: 'about', label: 'О себе' },
  { key: 'services', label: 'Услуги' },
  { key: 'portfolio', label: 'Портфолио' },
  { key: 'reviews', label: 'Отзывы' },
];

export default function ProfilePage({ params }: { params: Promise<{ username: string }> }) {
  const { username } = use(params);
  const { session } = useSession();
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioCard[] | null>(null);
  const [services, setServices] = useState<ServiceCardType[] | null>(null);
  const [reviews, setReviews] = useState<Review[] | null>(null);
  const [history, setHistory] = useState<HistoryEntry[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [previewing, setPreviewing] = useState<string | null>(null);
  const [tab, setTab] = useState('about');
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reporting, setReporting] = useState(false);

  const load = useCallback(() => {
    let cancelled = false;
    get<PublicProfile>(`/developers/${username}`)
      .then((data) => {
        if (cancelled) return;
        setProfile(data);
        setSaved(Boolean(data.is_saved));
      })
      .catch(() => !cancelled && setFailed(true));
    get<PortfolioCard[]>(`/developers/${username}/portfolio`)
      .then((data) => !cancelled && setPortfolio(data ?? []))
      .catch(() => !cancelled && setPortfolio([]));
    get<ServiceCardType[]>(`/developers/${username}/services`)
      .then((data) => !cancelled && setServices(data ?? []))
      .catch(() => !cancelled && setServices([]));
    get<Review[]>(`/developers/${username}/reviews`)
      .then((data) => !cancelled && setReviews(data ?? []))
      .catch(() => !cancelled && setReviews([]));
    get<HistoryEntry[]>(`/developers/${username}/history`)
      .then((data) => !cancelled && setHistory(data ?? []))
      .catch(() => !cancelled && setHistory([]));
    return () => {
      cancelled = true;
    };
  }, [username]);

  useEffect(() => load(), [load]);

  if (failed) {
    return (
      <>
        <TopBar back />
        <div className="av-page">
          <EmptyState
            tone="error"
            icon={<IconAlert size={20} />}
            title="Профиль не найден"
            description="Возможно, адрес указан неверно или исполнитель скрыл свой профиль."
          />
        </div>
      </>
    );
  }

  if (!profile) {
    return (
      <>
        <TopBar back />
        <div className="av-page av-stack">
          <Skeleton height={96} radius="var(--av-radius-xl)" />
          <Skeleton height={60} />
          <Skeleton height={140} />
        </div>
      </>
    );
  }

  const reputation = profile.reputation;
  const responseHours = reputation.response_time_seconds
    ? Math.max(1, Math.round(reputation.response_time_seconds / 3600))
    : null;
  const isClient = session?.active_role === 'client';
  const isOwner = profile.is_owner || session?.username === profile.username;

  async function toggleSave() {
    setSaving(true);
    try {
      if (saved) await del(`/freelancers/${profile!.username}/save`);
      else await post(`/freelancers/${profile!.username}/save`);
      setSaved(!saved);
    } catch {
      // Состояние не меняем: показывать «сохранено», когда это не так, хуже.
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <TopBar back title={profile.full_name} />
      <div className="av-page av-stack">
        <Card>
          <div className={styles.identity}>
            <Avatar
              src={avatarURL(profile.photo, 256)}
              name={profile.full_name}
              size={96}
              verified={profile.badges.some((badge) => badge.kind === 'identity_verified')}
            />
            <div className={styles.identityText}>
              <h1 className={styles.name}>{profile.full_name}</h1>
              <p className={styles.title}>
                {profile.professional_title ?? profile.primary_specialisation?.name}
              </p>
              <p className="av-small av-muted">
                {profile.location ? `${profile.location} · ` : ''}
                на AVERIX с {shortDate(profile.member_since)}
              </p>
            </div>
          </div>

          <div className={styles.badges}>
            {profile.badges.map((badge) => (
              <Badge key={badge.kind} tone={badgeTone(badge.kind)} size="sm" icon={badgeIcon(badge.kind)}>
                {badge.label}
              </Badge>
            ))}
          </div>

          <div className={styles.stats}>
            <Stat
              label="Рейтинг"
              value={reputation.rating_avg ? reputation.rating_avg.toFixed(1) : '—'}
              note={reputation.rating_count ? plural(reputation.rating_count, 'отзыв', 'отзыва', 'отзывов') : 'Отзывов пока нет'}
            />
            <Stat label="Выполнено" value={String(reputation.projects_completed)} note="сделок на AVERIX" />
            <Stat
              label="Успешно"
              value={reputation.success_rate ? `${Math.round(reputation.success_rate)}%` : '—'}
              note="завершено как договорились"
            />
            <Stat label="Отвечает" value={responseHours ? `${responseHours} ч` : '—'} note="медианный первый ответ" />
          </div>

          <div className={styles.availability}>
            <span className={styles.availabilityDot} data-state={profile.availability} aria-hidden="true" />
            {AVAILABILITY[profile.availability] ?? profile.availability}
            {profile.hours_per_week ? ` · около ${profile.hours_per_week} ч в неделю` : ''}
            {profile.hourly_rate_minor ? (
              <span className={styles.rate}>{money(profile.hourly_rate_minor, profile.rate_currency)}/ч</span>
            ) : null}
          </div>

          {isOwner ? (
            <div className={styles.actions}>
              <ButtonLink href="/onboarding" variant="secondary" block>
                Редактировать анкету
              </ButtonLink>
              <ButtonLink href="/services/mine" variant="secondary" block>
                Мои услуги
              </ButtonLink>
            </div>
          ) : session ? (
            <div className={styles.actions}>
              {isClient ? (
                <Button variant={saved ? 'primary' : 'secondary'} block loading={saving} onClick={() => void toggleSave()}>
                  {saved ? 'В избранном' : 'В избранное'}
                </Button>
              ) : null}
              <Button variant="ghost" block onClick={() => setReporting(true)}>
                Пожаловаться
              </Button>
            </div>
          ) : null}
        </Card>

        <Tabs items={TABS} active={tab} onChange={setTab} ariaLabel="Разделы профиля" />

        {tab === 'about' ? (
          <>
            {profile.bio ? (
              <Card>
                <h2 className={styles.sectionTitle}>О себе</h2>
                <p className={styles.bio}>{profile.bio}</p>
              </Card>
            ) : null}

            <Card>
              <h2 className={styles.sectionTitle}>Навыки</h2>
              <div className={styles.skills}>
                {profile.skills.map((skill) => (
                  <span key={skill.slug} className={[styles.skill, skill.is_primary ? styles.skillPrimary : ''].join(' ')}>
                    {skill.name}
                    {skill.evidence?.length ? (
                      <span className={styles.evidence} title={`Подтверждено: ${skill.evidence.join(', ')}`}>
                        <IconCheck size={12} />
                      </span>
                    ) : null}
                  </span>
                ))}
              </div>
              <p className={styles.skillsNote}>
                Галочка означает, что навык подтверждён завершёнными сделками на AVERIX или
                подключённым GitHub — а не только словами исполнителя.
              </p>
            </Card>

            {profile.additional_specialisations?.length ? (
              <Card>
                <h2 className={styles.sectionTitle}>Дополнительные направления</h2>
                <p className="av-muted">{profile.additional_specialisations.map((spec) => spec.name).join(' · ')}</p>
              </Card>
            ) : null}

            {profile.languages?.length ? (
              <Card>
                <h2 className={styles.sectionTitle}>Языки</h2>
                <p className="av-muted">
                  {profile.languages.map((item) => `${item.language} — ${proficiency(item.proficiency)}`).join(' · ')}
                </p>
              </Card>
            ) : null}

            {profile.github ? (
              <Card>
                <div className="av-row-between">
                  <h2 className={styles.sectionTitle}>
                    <IconGitHub size={17} /> GitHub
                  </h2>
                  <a className={styles.githubLink} href={profile.github.profile_url} target="_blank" rel="noopener noreferrer">
                    @{profile.github.login}
                  </a>
                </div>
                {profile.github.language_share?.length ? (
                  <>
                    <p className={styles.codeUsageLabel}>Доля кода по языкам в публичных репозиториях</p>
                    <div className={styles.shares}>
                      {profile.github.language_share.slice(0, 5).map((language) => (
                        <div key={language.name} className={styles.share}>
                          <div className={styles.shareHead}>
                            <span>{language.name}</span>
                            <span className="av-numeric av-muted av-small">{Math.round(language.share * 100)}%</span>
                          </div>
                          <div className={styles.shareTrack} aria-hidden="true">
                            <span className={styles.shareFill} style={{ width: `${Math.round(language.share * 100)}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                    <p className={styles.codeUsageNote}>
                      Это доля кода на каждом языке — показатель того, с чем человек работает, а не
                      оценка того, насколько хорошо он это знает.
                    </p>
                  </>
                ) : null}
                {profile.github.ai_summary ? (
                  <div className={styles.aiSummary}>
                    <span className={styles.aiLabel}>Краткое описание, сгенерированное ИИ</span>
                    <p>{profile.github.ai_summary}</p>
                  </div>
                ) : null}
              </Card>
            ) : null}

            <section className="av-stack-sm">
              <h2 className={styles.sectionTitle}>Подтверждённая история</h2>
              {history === null ? (
                <Skeleton height={80} />
              ) : history.length === 0 ? (
                <p className="av-small av-muted">Завершённых сделок на AVERIX пока нет.</p>
              ) : (
                history.map((entry) => (
                  <Card key={entry.id}>
                    <div className="av-row-between">
                      <div className="av-grow">
                        <p className="av-strong">{entry.title}</p>
                        <p className="av-small av-muted">
                          {entry.category ? `${entry.category} · ` : ''}
                          {shortDate(entry.completed_at)}
                          {entry.duration_days ? ` · ${days(entry.duration_days)}` : ''}
                        </p>
                      </div>
                      <div className={styles.historyRight}>
                        {entry.client_rating ? (
                          <span className={styles.historyRating}>
                            <IconStarFilled size={13} /> {entry.client_rating.toFixed(1)}
                          </span>
                        ) : null}
                        {entry.value_display ? <span className="av-small av-muted">{entry.value_display}</span> : null}
                      </div>
                    </div>
                    {entry.summary ? <p className="av-small av-muted">{entry.summary}</p> : null}
                  </Card>
                ))
              )}
            </section>
          </>
        ) : null}

        {tab === 'services' ? (
          services === null ? (
            <Skeleton height={180} radius="var(--av-radius-xl)" />
          ) : services.length === 0 ? (
            <EmptyState
              icon={<IconClock size={20} />}
              title="Услуг пока нет"
              description="Когда исполнитель опубликует услуги с фиксированной ценой, их можно будет заказать здесь в один шаг."
            />
          ) : (
            <div className={styles.serviceGrid}>
              {services.map((service) => (
                <ServiceCard key={service.id} service={service} />
              ))}
            </div>
          )
        ) : null}

        {tab === 'portfolio' ? (
          portfolio === null ? (
            <Skeleton height={180} radius="var(--av-radius-xl)" />
          ) : portfolio.length === 0 ? (
            <EmptyState
              icon={<IconClock size={20} />}
              title="Портфолио пока пусто"
              description="Опубликованные работы появятся здесь; сделки, подтверждённые AVERIX, отмечаются отдельно."
            />
          ) : (
            <PortfolioGrid items={portfolio} onPreview={(slug) => setPreviewing(slug)} username={profile.username} />
          )
        ) : null}

        {tab === 'reviews' ? (
          reviews === null ? (
            <Skeleton height={120} />
          ) : reviews.length === 0 ? (
            <EmptyState
              icon={<IconStarFilled size={20} />}
              title="Отзывов пока нет"
              description="Отзывы оставляют заказчики после завершения сделки. Написать отзыв без сделки нельзя."
            />
          ) : (
            <div className="av-stack-sm">
              {reviews.map((review) => (
                <ReviewCard key={review.id} review={review} onChanged={() => load()} />
              ))}
            </div>
          )
        ) : null}

        {!isOwner && session ? (
          <p className="av-xs av-faint">
            Хотите заказать работу у этого исполнителя? <Link href="/projects/new">Разместите заказ</Link> — он увидит его первым, если подходит по навыкам, или закажите готовую услугу.
          </p>
        ) : null}
      </div>

      {previewing ? (
        <PreviewBrowser username={profile.username} slug={previewing} onClose={() => setPreviewing(null)} />
      ) : null}
      <ReportSheet
        open={reporting}
        subjectType="user"
        subjectId={profile.user_id}
        title={profile.full_name}
        onClose={() => setReporting(false)}
      />
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

function badgeTone(kind: string) {
  if (kind === 'identity_verified' || kind === 'github_verified') return 'verified' as const;
  if (kind === 'available') return 'success' as const;
  if (kind === 'top_rated') return 'warning' as const;
  return 'neutral' as const;
}

function badgeIcon(kind: string) {
  if (kind === 'identity_verified') return <IconShield size={13} />;
  if (kind === 'github_verified') return <IconGitHub size={13} />;
  if (kind === 'top_rated') return <IconStarFilled size={13} />;
  return undefined;
}

function proficiency(level: string) {
  return { basic: 'базовый', conversational: 'разговорный', fluent: 'свободный', native: 'родной' }[level] ?? level;
}
