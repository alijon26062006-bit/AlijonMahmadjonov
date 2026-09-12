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
import { useSession } from '@/lib/session';
import type { ContractCard, Project } from '@/lib/types';

export default function ClientDashboard() {
  const { session } = useSession();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [contracts, setContracts] = useState<ContractCard[] | null>(null);

  const load = useCallback(async () => {
    const [projectList, contractList] = await Promise.allSettled([
      get<Project[]>('/projects/mine/list'),
      get<ContractCard[]>('/contracts'),
    ]);
    setProjects(projectList.status === 'fulfilled' ? projectList.value : []);
    setContracts(contractList.status === 'fulfilled' ? contractList.value : []);
  }, []);

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
            {greeting()}, {session?.full_name?.split(' ')[0] ?? 'there'}
          </h1>
          <p className="av-muted">Here is what needs you today.</p>
        </header>

        {contracts === null || projects === null ? (
          <SkeletonList count={3} />
        ) : (
          <>
            {live.some((contract) => contract.needs_my_action) ? (
              <section className="av-stack-sm">
                <SectionHeading title="Waiting on you" />
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
                title="Active contracts"
                count={live.length}
                action={
                  live.length ? (
                    <Link href="/contracts" className={styles.seeAll}>
                      All contracts
                    </Link>
                  ) : undefined
                }
              />
              {live.length === 0 ? (
                <EmptyState
                  icon={<IconBriefcase size={20} />}
                  title="No active contracts"
                  description="When you accept a proposal, the contract and its workspace appear here."
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
                        Next: {contract.next_milestone.title} ·{' '}
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
                title="Open projects"
                count={open.length}
                action={
                  <ButtonLink href="/projects/new" size="sm" variant="secondary" icon={<IconPlus size={16} />}>
                    New
                  </ButtonLink>
                }
              />
              {open.length === 0 ? (
                <EmptyState
                  icon={<IconPlus size={20} />}
                  title="No open projects"
                  description="Describe what you want built and AVERIX will put it in front of developers who actually work with those technologies."
                  action={
                    <Button onClick={() => (window.location.href = '/projects/new')}>
                      Post a project
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
                          {project.budget.display} · posted {timeAgo(project.published_at)}
                        </p>
                      </div>
                      <Badge tone={project.proposals_count ? 'brand' : 'neutral'}>
                        {plural(project.proposals_count, 'proposal')}
                      </Badge>
                    </div>
                  </Card>
                ))
              )}
            </section>

            {drafts.length ? (
              <section className="av-stack-sm">
                <SectionHeading title="Drafts" count={drafts.length} />
                {drafts.map((project) => (
                  <Card key={project.id} href={`/projects/${project.slug}`}>
                    <div className="av-row-between">
                      <p className="av-strong">{project.title || 'Untitled project'}</p>
                      <Badge tone="warning" size="sm">
                        Draft
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
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function actionLabel(contract: ContractCard) {
  const status = contract.next_milestone?.status;
  if (status === 'submitted') return 'Work submitted for your review';
  if (status === 'draft') return 'Waiting to be funded';
  return 'Needs your attention';
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
      return 'Not funded';
    case 'funded':
      return 'Funded, ready to start';
    case 'in_progress':
      return 'In progress';
    case 'submitted':
      return 'Submitted for review';
    case 'revision_requested':
      return 'Revision requested';
    case 'approved':
      return 'Approved';
    case 'released':
      return 'Paid';
    case 'disputed':
      return 'Disputed';
    case 'cancelled':
      return 'Cancelled';
    default:
      return status;
  }
}
