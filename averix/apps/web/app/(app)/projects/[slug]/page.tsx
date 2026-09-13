'use client';

import { use, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import styles from './project.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Badge, Tag } from '@/components/ui/Badge';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Avatar } from '@/components/ui/Avatar';
import { MatchExplainer } from '@/components/domain/MatchExplainer';
import { ProposalSheet } from '@/components/domain/ProposalSheet';
import { ReportSheet } from '@/components/domain/ReportSheet';
import { IconAlert, IconCheck, IconClock, IconShield } from '@/components/ui/Icon';
import { ApiFailure, del, get, post } from '@/lib/api';
import { days, plural, shortDate, timeAgo } from '@/lib/format';
import { EXPERIENCE, PROJECT_STATUS, countryName } from '@/lib/labels';
import { useSession } from '@/lib/session';
import type { Project } from '@/lib/types';

export default function ProjectPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { session } = useSession();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [failed, setFailed] = useState(false);
  const [proposing, setProposing] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [ownerBusy, setOwnerBusy] = useState(false);
  const [ownerError, setOwnerError] = useState('');

  const load = useCallback(async () => {
    setFailed(false);
    try {
      setProject(await get<Project>(`/projects/${slug}`));
    } catch {
      setFailed(true);
    }
  }, [slug]);

  useEffect(() => {
    void load();
  }, [load]);

  const isDeveloper = session?.active_role === 'developer';
  const isOwner = Boolean(project?.is_owner);

  async function toggleSave() {
    if (!project) return;
    setSaving(true);
    try {
      if (project.is_saved) await del(`/projects/${project.id}/save`);
      else await post(`/projects/${project.id}/save`);
      setProject({ ...project, is_saved: !project.is_saved });
    } catch {
      // Оставляем как было.
    } finally {
      setSaving(false);
    }
  }

  async function ownerAction(kind: 'publish' | 'cancel') {
    if (!project) return;
    if (kind === 'cancel' && !window.confirm('Закрыть заказ? Открытые отклики будут отклонены.')) return;
    setOwnerBusy(true);
    setOwnerError('');
    try {
      await post(`/projects/${project.id}/${kind}`);
      await load();
    } catch (error) {
      setOwnerError(error instanceof ApiFailure ? error.message : 'Не получилось. Попробуйте ещё раз.');
    } finally {
      setOwnerBusy(false);
    }
  }

  return (
    <>
      <TopBar back title="Заказ" />

      {failed ? (
        <div className="av-page">
          <EmptyState
            tone="error"
            icon={<IconAlert size={20} />}
            title="Не удалось открыть заказ"
            description="Возможно, его закрыли, или что-то пошло не так на нашей стороне."
            action={
              <Button variant="secondary" onClick={() => void load()}>
                Повторить
              </Button>
            }
          />
        </div>
      ) : !project ? (
        <div className="av-page av-stack">
          <Skeleton height={26} width="70%" />
          <Skeleton height={14} width="40%" />
          <Skeleton height={120} />
          <Skeleton height={90} />
        </div>
      ) : (
        <>
          <div className={`av-page ${styles.page}`}>
            <header className={styles.header}>
              <div className={styles.headerTop}>
                <Badge tone="neutral" size="sm">
                  {project.category.name}
                </Badge>
                {project.status === 'open' ? (
                  <Badge tone="success" size="sm">
                    Принимает отклики
                  </Badge>
                ) : (
                  <Badge tone="neutral" size="sm">
                    {PROJECT_STATUS[project.status] ?? project.status}
                  </Badge>
                )}
              </div>
              <h1 className={styles.title}>{project.title}</h1>
              <p className={styles.meta}>
                {project.reference}
                {project.published_at ? ` · опубликован ${timeAgo(project.published_at)}` : ' · черновик'}
                {project.views_count ? ` · ${plural(project.views_count, 'просмотр', 'просмотра', 'просмотров')}` : ''}
              </p>

              {project.match ? (
                <div className={styles.match}>
                  <MatchExplainer score={project.match.total} highlights={project.match.highlights} />
                </div>
              ) : null}
            </header>

            {isOwner ? (
              <Card>
                <div className="av-stack-sm">
                  <p className="av-strong">Это ваш заказ</p>
                  {ownerError ? (
                    <p className="av-small" role="alert" style={{ color: 'var(--av-danger)' }}>
                      {ownerError}
                    </p>
                  ) : null}
                  <div className="av-row av-wrap">
                    {project.status === 'draft' ? (
                      <>
                        <Button loading={ownerBusy} onClick={() => void ownerAction('publish')}>
                          Опубликовать
                        </Button>
                        <ButtonLink href={`/projects/new?edit=${project.id}`} variant="secondary">
                          Редактировать
                        </ButtonLink>
                      </>
                    ) : null}
                    {project.status === 'open' ? (
                      <>
                        <ButtonLink href={`/projects/${project.slug}/proposals`}>
                          Отклики ({project.proposals_count})
                        </ButtonLink>
                        <Button variant="danger" loading={ownerBusy} onClick={() => void ownerAction('cancel')}>
                          Закрыть заказ
                        </Button>
                      </>
                    ) : null}
                  </div>
                </div>
              </Card>
            ) : null}

            <div className={styles.facts}>
              <div className={styles.fact}>
                <span className={styles.factLabel}>Бюджет</span>
                <span className={styles.factValue}>{project.budget.display}</span>
              </div>
              {project.duration_days ? (
                <div className={styles.fact}>
                  <span className={styles.factLabel}>Срок</span>
                  <span className={styles.factValue}>{days(project.duration_days)}</span>
                </div>
              ) : null}
              {project.deadline ? (
                <div className={styles.fact}>
                  <span className={styles.factLabel}>Дедлайн</span>
                  <span className={styles.factValue}>{shortDate(project.deadline)}</span>
                </div>
              ) : null}
              <div className={styles.fact}>
                <span className={styles.factLabel}>Откликов</span>
                <span className={styles.factValue}>{project.proposals_count}</span>
              </div>
              {project.experience_wanted ? (
                <div className={styles.fact}>
                  <span className={styles.factLabel}>Уровень</span>
                  <span className={styles.factValue}>{EXPERIENCE[project.experience_wanted] ?? project.experience_wanted}</span>
                </div>
              ) : null}
            </div>

            <Card>
              <h2 className={styles.sectionTitle}>Что нужно сделать</h2>
              <p className={styles.description}>{project.description}</p>

              {project.features?.length ? (
                <ul className={styles.features}>
                  {project.features.map((feature) => (
                    <li key={feature.title}>
                      <IconCheck size={15} />
                      <span>
                        <strong>{feature.title}</strong>
                        {feature.detail ? <span className="av-muted"> — {feature.detail}</span> : null}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </Card>

            {project.skills.length ? (
              <Card>
                <h2 className={styles.sectionTitle}>Навыки</h2>
                <div className={styles.tags}>
                  {project.skills.map((skill) => (
                    <Tag key={skill.slug}>{skill.name}</Tag>
                  ))}
                </div>
                {project.targeting?.length ? (
                  <p className={styles.targeting}>
                    Показывается: {project.targeting.map((target) => target.name).join(', ')}.
                  </p>
                ) : null}
              </Card>
            ) : null}

            <Card>
              <h2 className={styles.sectionTitle}>О заказчике</h2>
              <div className={styles.client}>
                <Avatar
                  src={project.client.photo_url}
                  name={project.client.display_name}
                  size={48}
                  verified={project.client.verified}
                />
                <div className="av-grow">
                  <p className="av-strong">{project.client.display_name || 'Заказчик'}</p>
                  <p className="av-small av-muted">
                    {project.client.country_code ? `${countryName(project.client.country_code)} · ` : ''}
                    {plural(project.client.hires_made ?? 0, 'наём', 'найма', 'наймов')}
                    {project.client.member_since ? ` · на AVERIX с ${shortDate(project.client.member_since)}` : ''}
                  </p>
                </div>
                {project.client.verified ? (
                  <Badge tone="verified" size="sm" icon={<IconShield size={13} />}>
                    Проверен
                  </Badge>
                ) : null}
              </div>
            </Card>

            {project.match?.dimensions?.length ? (
              <Card>
                <h2 className={styles.sectionTitle}>Почему вы видите этот заказ</h2>
                <ul className={styles.dimensions}>
                  {project.match.dimensions.map((dimension) => (
                    <li key={dimension.key}>
                      <div className={styles.dimensionHead}>
                        <span>{dimension.label}</span>
                        <span className="av-numeric av-muted av-small">
                          {Math.round(dimension.points)} / {Math.round(dimension.weight * 100)}
                        </span>
                      </div>
                      <div className={styles.meter} aria-hidden="true">
                        <span className={styles.meterFill} style={{ width: `${Math.round(dimension.raw * 100)}%` }} />
                      </div>
                      {dimension.reasons?.length ? (
                        <p className="av-small av-muted">{dimension.reasons.map((reason) => reason.label).join(' · ')}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
                <p className={styles.weightsNote}>
                  Версия весов {project.match.weights_version}. Одни и те же шесть измерений применяются
                  ко всем исполнителям на всех заказах.
                </p>
              </Card>
            ) : null}

            {session && !isOwner ? (
              <div className="av-row av-wrap">
                {isDeveloper ? (
                  <Button variant="secondary" size="sm" loading={saving} onClick={() => void toggleSave()}>
                    {project.is_saved ? 'Убрать из сохранённых' : 'Сохранить'}
                  </Button>
                ) : null}
                <Button variant="ghost" size="sm" onClick={() => setReporting(true)}>
                  Пожаловаться
                </Button>
              </div>
            ) : null}
            {!session ? (
              <p className="av-small av-muted">
                <Link href={`/login?next=/projects/${project.slug}`}>Войдите</Link> как исполнитель, чтобы откликнуться.
              </p>
            ) : null}
          </div>

          {isDeveloper && project.status === 'open' ? (
            <div className={styles.actionBar}>
              <div className={styles.actionInfo}>
                <span className={styles.actionBudget}>{project.budget.display}</span>
                <span className="av-small av-muted">
                  <IconClock size={12} /> {plural(project.proposals_count, 'отклик', 'отклика', 'откликов')}
                </span>
              </div>
              <Button size="lg" disabled={project.has_proposed} onClick={() => setProposing(true)}>
                {project.has_proposed ? 'Отклик отправлен' : 'Откликнуться'}
              </Button>
            </div>
          ) : null}

          <ProposalSheet
            open={proposing}
            project={project}
            onClose={() => setProposing(false)}
            onSent={() => {
              setProposing(false);
              void load();
              router.refresh();
            }}
          />
          <ReportSheet
            open={reporting}
            subjectType="project"
            subjectId={project.id}
            title={project.title}
            onClose={() => setReporting(false)}
          />
        </>
      )}
    </>
  );
}
