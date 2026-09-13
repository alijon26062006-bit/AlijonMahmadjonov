'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import styles from './dashboard.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card, SectionHeading } from '@/components/ui/Card';
import { Badge, StatusDot } from '@/components/ui/Badge';
import { Button, ButtonLink } from '@/components/ui/Button';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Avatar } from '@/components/ui/Avatar';
import { IconBriefcase, IconChevronRight, IconPlus } from '@/components/ui/Icon';
import { get } from '@/lib/api';
import { money, plural, timeAgo } from '@/lib/format';
import { useRoleGuard, useSession } from '@/lib/session';
import type { ContractCard, Project } from '@/lib/types';

export default function ClientDashboard() {
  const { session } = useSession();
  const isClient = useRoleGuard('client');
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [contracts, setContracts] = useState<ContractCard[] | null>(null);

  const load = useCallback(async () => {
    if (!isClient) return;
    const [projectList, contractList] = await Promise.allSettled([
      get<Project[]>('/projects/mine/list'),
      get<ContractCard[]>('/contracts'),
    ]);
    setProjects(projectList.status === 'fulfilled' ? projectList.value : []);
    setContracts(contractList.status === 'fulfilled' ? contractList.value : []);
  }, [isClient]);

  useEffect(() => {
    void load();
  }, [load]);

  const live = (contracts ?? []).filter((contract) => contract.status !== 'completed' && contract.status !== 'cancelled');
  const open = (projects ?? []).filter((project) => project.status === 'open');
  const drafts = (projects ?? []).filter((project) => project.status === 'draft');

  return (
    <>
      <TopBar />
      <div className="av-page av-stack-lg">
        <header>
          <h1 className={styles.greeting}>
            {greeting()}, {session?.full_name?.split(' ')[0] ?? ''}
          </h1>
          <p className="av-muted">Вот что ждёт вашего решения сегодня.</p>
        </header>

        {contracts === null || projects === null ? (
          <SkeletonList count={3} />
        ) : (
          <>
            {live.some((contract) => contract.needs_my_action) ? (
              <section className="av-stack-sm">
                <SectionHeading title="Ждут вас" />
                {live
                  .filter((contract) => contract.needs_my_action)
                  .map((contract) => (
                    <Link key={contract.id} href={`/contracts/${contract.id}`} className={styles.actionRow}>
                      <Avatar
                        src={contract.counterparty.photo_url}
                        name={contract.counterparty.full_name}
                        size={40}
                      />
                      <div className="av-grow">
                        <p className="av-strong">{contract.next_milestone?.title ?? contract.title}</p>
                        <p className="av-small av-muted">
                          {actionLabel(contract)} · {contract.counterparty.full_name}
                        </p>
                      </div>
                      <IconChevronRight size={18} />
                    </Link>
                  ))}
              </section>
            ) : null}

            <section className="av-stack-sm">
              <SectionHeading
                title="Сделки в работе"
                count={live.length}
                action={
                  live.length ? (
                    <Link href="/contracts" className={styles.seeAll}>
                      Все сделки
                    </Link>
                  ) : undefined
                }
              />
              {live.length === 0 ? (
                <EmptyState
                  icon={<IconBriefcase size={20} />}
                  title="Нет сделок в работе"
                  description="Когда вы примете отклик или закажете услугу, сделка и её рабочее пространство появятся здесь."
                />
              ) : (
                live.map((contract) => (
                  <Card key={contract.id} href={`/contracts/${contract.id}`}>
                    <div className="av-row-between">
                      <div className="av-grow">
                        <p className="av-strong">{contract.title}</p>
                        <p className="av-small av-muted">
                          {contract.counterparty.full_name} · {contract.reference}
                        </p>
                      </div>
                      {contract.amount_minor !== undefined ? (
                        <span className={styles.amount}>
                          {money(contract.amount_minor, contract.currency)}
                        </span>
                      ) : null}
                    </div>
                    <div className={styles.progress}>
                      <div className={styles.progressTrack} aria-hidden="true">
                        <span
                          className={styles.progressFill}
                          style={{ width: `${contract.progress_percent}%` }}
                        />
                      </div>
                      <span className="av-small av-muted av-numeric">{contract.progress_percent}%</span>
                    </div>
                    {contract.next_milestone ? (
                      <p className="av-small av-muted">
                        Далее: {contract.next_milestone.title} ·{' '}
                        <StatusDot tone={milestoneTone(contract.next_milestone.status)}>
                          {milestoneLabel(contract.next_milestone.status)}
                        </StatusDot>
                      </p>
                    ) : null}
                  </Card>
                ))
              )}
            </section>

            <section className="av-stack-sm">
              <SectionHeading
                title="Открытые заказы"
                count={open.length}
                action={
                  <ButtonLink href="/projects/new" size="sm" variant="secondary" icon={<IconPlus size={16} />}>
                    Создать
                  </ButtonLink>
                }
              />
              {open.length === 0 ? (
                <EmptyState
                  icon={<IconPlus size={20} />}
                  title="Нет открытых заказов"
                  description="Опишите, что нужно сделать, — AVERIX покажет заказ исполнителям, которые действительно этим занимаются."
                  action={
                    <Button onClick={() => (window.location.href = '/projects/new')}>
                      Разместить заказ
                    </Button>
                  }
                />
              ) : (
                open.map((project) => (
                  <Card key={project.id} href={`/projects/${project.slug}/proposals`}>
                    <div className="av-row-between">
                      <div className="av-grow">
                        <p className="av-strong">{project.title}</p>
                        <p className="av-small av-muted">
                          {project.budget.display} · {timeAgo(project.published_at)}
                        </p>
                      </div>
                      <Badge tone={project.proposals_count ? 'brand' : 'neutral'}>
                        {plural(project.proposals_count, 'отклик', 'отклика', 'откликов')}
                      </Badge>
                    </div>
                  </Card>
                ))
              )}
            </section>

            {drafts.length ? (
              <section className="av-stack-sm">
                <SectionHeading title="Черновики" count={drafts.length} />
                {drafts.map((project) => (
                  <Card key={project.id} href={`/projects/${project.slug}`}>
                    <div className="av-row-between">
                      <p className="av-strong">{project.title || 'Заказ без названия'}</p>
                      <Badge tone="warning" size="sm">
                        Черновик
                      </Badge>
                    </div>
                  </Card>
                ))}
              </section>
            ) : null}
          </>
        )}
      </div>
    </>
  );
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Доброе утро';
  if (hour < 18) return 'Добрый день';
  return 'Добрый вечер';
}

function actionLabel(contract: ContractCard) {
  const status = contract.next_milestone?.status;
  if (status === 'submitted') return 'Работа сдана — нужна ваша проверка';
  if (status === 'draft') return 'Ждёт оплаты этапа';
  return 'Нужно ваше участие';
}

export function milestoneTone(status: string) {
  switch (status) {
    case 'approved':
    case 'released':
      return 'success' as const;
    case 'submitted':
      return 'info' as const;
    case 'revision_requested':
      return 'warning' as const;
    case 'disputed':
      return 'danger' as const;
    case 'in_progress':
      return 'brand' as const;
    default:
      return 'neutral' as const;
  }
}

export function milestoneLabel(status: string) {
  switch (status) {
    case 'draft':
      return 'Не оплачен';
    case 'funded':
      return 'Оплачен, можно начинать';
    case 'in_progress':
      return 'В работе';
    case 'submitted':
      return 'Сдан на проверку';
    case 'revision_requested':
      return 'На доработке';
    case 'approved':
      return 'Принят';
    case 'released':
      return 'Выплачен';
    case 'disputed':
      return 'Спор';
    case 'cancelled':
      return 'Отменён';
    default:
      return status;
  }
}
