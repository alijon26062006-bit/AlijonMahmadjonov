'use client';

import { use, useCallback, useEffect, useState } from 'react';
import styles from './project.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Badge, Tag } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Avatar } from '@/components/ui/Avatar';
import { MatchExplainer } from '@/components/domain/MatchExplainer';
import { ProposalSheet } from '@/components/domain/ProposalSheet';
import { IconAlert, IconCheck, IconClock, IconShield } from '@/components/ui/Icon';
import { get } from '@/lib/api';
import { plural, shortDate, timeAgo } from '@/lib/format';
import { useSession } from '@/lib/session';
import type { Project } from '@/lib/types';

export default function ProjectPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { session } = useSession();
  const [project, setProject] = useState<Project | null>(null);
  const [failed, setFailed] = useState(false);
  const [proposing, setProposing] = useState(false);

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

  return (
    <>
      <TopBar back title="Project" />

      {failed ? (
        <div className="av-page">
          <EmptyState
            tone="error"
            icon={<IconAlert size={20} />}
            title="We couldn't load this project"
            description="It may have been closed, or something went wrong on our end."
            action={
              <Button variant="secondary" onClick={() => void load()}>
                Try again
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
                    Open for proposals
                  </Badge>
                ) : (
                  <Badge tone="neutral" size="sm">
                    {project.status.replace('_', ' ')}
                  </Badge>
                )}
              </div>
              <h1 className={styles.title}>{project.title}</h1>
              <p className={styles.meta}>
                {project.reference} · posted {timeAgo(project.published_at)}
              </p>

              {project.match ? (
                <div className={styles.match}>
                  <MatchExplainer
                    score={project.match.total}
                    highlights={project.match.highlights}
                  />
                </div>
              ) : null}
            </header>

            <div className={styles.facts}>
              <div className={styles.fact}>
                <span className={styles.factLabel}>Budget</span>
                <span className={styles.factValue}>{project.budget.display}</span>
              </div>
              {project.duration_days ? (
                <div className={styles.fact}>
                  <span className={styles.factLabel}>Timeline</span>
                  <span className={styles.factValue}>{project.duration_days} days</span>
                </div>
              ) : null}
              <div className={styles.fact}>
                <span className={styles.factLabel}>Proposals</span>
                <span className={styles.factValue}>{project.proposals_count}</span>
              </div>
              {project.experience_wanted ? (
                <div className={styles.fact}>
                  <span className={styles.factLabel}>Looking for</span>
                  <span className={styles.factValue}>{project.experience_wanted}</span>
                </div>
              ) : null}
            </div>

            <Card>
              <h2 className={styles.sectionTitle}>What needs building</h2>
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
                <h2 className={styles.sectionTitle}>Technologies</h2>
                <div className={styles.tags}>
                  {project.skills.map((skill) => (
                    <Tag key={skill.slug}>{skill.name}</Tag>
                  ))}
                </div>
                {project.targeting?.length ? (
                  <p className={styles.targeting}>
                    Shown to {project.targeting.map((target) => target.name).join(', ')}.
                  </p>
                ) : null}
              </Card>
            ) : null}

            <Card>
              <h2 className={styles.sectionTitle}>About the client</h2>
              <div className={styles.client}>
                <Avatar
                  src={project.client.photo_url}
                  name={project.client.display_name}
                  size={48}
                  verified={project.client.verified}
                />
                <div className="av-grow">
                  <p className="av-strong">{project.client.display_name || 'Private client'}</p>
                  <p className="av-small av-muted">
                    {project.client.country_code ? `${project.client.country_code} · ` : ''}
                    {plural(project.client.hires_made ?? 0, 'hire')}
                    {project.client.member_since
                      ? ` · joined ${shortDate(project.client.member_since)}`
                      : ''}
                  </p>
                </div>
                {project.client.verified ? (
                  <Badge tone="verified" size="sm" icon={<IconShield size={13} />}>
                    Verified
                  </Badge>
                ) : null}
              </div>
            </Card>

            {project.match?.dimensions?.length ? (
              <Card>
                <h2 className={styles.sectionTitle}>Why this reached you</h2>
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
                        <span
                          className={styles.meterFill}
                          style={{ width: `${Math.round(dimension.raw * 100)}%` }}
                        />
                      </div>
                      {dimension.reasons?.length ? (
                        <p className="av-small av-muted">
                          {dimension.reasons.map((reason) => reason.label).join(' · ')}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
                <p className={styles.weightsNote}>
                  Weights version {project.match.weights_version}. The same six dimensions are used
                  for every developer on every project.
                </p>
              </Card>
            ) : null}
          </div>

          {isDeveloper && project.status === 'open' ? (
            <div className={styles.actionBar}>
              <div className={styles.actionInfo}>
                <span className={styles.actionBudget}>{project.budget.display}</span>
                <span className="av-small av-muted">
                  <IconClock size={12} /> {plural(project.proposals_count, 'proposal')} so far
                </span>
              </div>
              <Button
                size="lg"
                disabled={project.has_proposed}
                onClick={() => setProposing(true)}
              >
                {project.has_proposed ? 'Proposal sent' : 'Send a proposal'}
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
            }}
          />
        </>
      )}
    </>
  );
}
