'use client';

import { use, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import styles from './proposals.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Tabs } from '@/components/ui/Tabs';
import { Card } from '@/components/ui/Card';
import { Avatar } from '@/components/ui/Avatar';
import { Badge, Tag } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { MatchExplainer } from '@/components/domain/MatchExplainer';
import { IconCheck, IconShield, IconStarFilled, IconUser } from '@/components/ui/Icon';
import { ApiFailure, get, post } from '@/lib/api';
import { money, plural, timeAgo } from '@/lib/format';
import type { Project, ProposalCard } from '@/lib/types';

const SORTS = [
  { key: 'recommended', label: 'Recommended' },
  { key: 'match', label: 'Best match' },
  { key: 'newest', label: 'Newest' },
  { key: 'price', label: 'Price' },
  { key: 'delivery', label: 'Fastest' },
  { key: 'rating', label: 'Highest rated' },
];

export default function ProposalsPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const [project, setProject] = useState<Project | null>(null);
  const [proposals, setProposals] = useState<ProposalCard[] | null>(null);
  const [sort, setSort] = useState('recommended');
  const [hiring, setHiring] = useState<ProposalCard | null>(null);

  const load = useCallback(
    async (nextSort: string) => {
      setProposals(null);
      const found = project ?? (await get<Project>(`/projects/${slug}`));
      setProject(found);
      try {
        setProposals(await get<ProposalCard[]>(`/projects/${found.id}/proposals?sort=${nextSort}`));
      } catch {
        setProposals([]);
      }
    },
    [slug, project],
  );

  useEffect(() => {
    void load(sort);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load is stable enough here
  }, [sort, slug]);

  return (
    <>
      <TopBar back={`/dashboard`} title="Proposals" />
      <div className="av-page av-stack">
        <header>
          <h1 className={styles.title}>{project?.title ?? 'Proposals'}</h1>
          <p className="av-muted av-small">
            {proposals ? plural(proposals.length, 'proposal') : 'Loading proposals'}
            {project ? ` · ${project.budget.display}` : ''}
          </p>
        </header>

        <Tabs items={SORTS} active={sort} onChange={setSort} ariaLabel="Sort proposals" />

        {proposals === null ? (
          <SkeletonList count={3} />
        ) : proposals.length === 0 ? (
          <EmptyState
            icon={<IconUser size={20} />}
            title="No proposals yet"
            description="Developers matching your project will appear here. Most projects get their first proposal within a day."
          />
        ) : (
          <div className="av-stack-sm">
            {proposals.map((proposal) => (
              <Card key={proposal.id}>
                <div className={styles.head}>
                  <Link href={`/developers/${proposal.developer.username}`} className={styles.person}>
                    <Avatar
                      src={proposal.developer.photo_url}
                      name={proposal.developer.full_name}
                      size={48}
                      verified={proposal.developer.identity_verified}
                    />
                    <div className="av-grow">
                      <p className="av-strong">{proposal.developer.full_name}</p>
                      <p className="av-small av-muted">
                        {proposal.developer.professional_title ?? 'Developer'}
                        {proposal.developer.country_code ? ` · ${proposal.developer.country_code}` : ''}
                      </p>
                      <div className={styles.stats}>
                        {proposal.developer.rating_avg ? (
                          <span className={styles.rating}>
                            <IconStarFilled size={13} />
                            {proposal.developer.rating_avg.toFixed(1)}
                          </span>
                        ) : null}
                        {proposal.developer.projects_completed ? (
                          <span>
                            {plural(proposal.developer.projects_completed, 'project')} on AVERIX
                          </span>
                        ) : (
                          <span className="av-faint">New to AVERIX</span>
                        )}
                        {proposal.developer.identity_verified ? (
                          <span className={styles.verified}>
                            <IconShield size={13} /> Verified
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </Link>

                  <div className={styles.quote}>
                    <span className={styles.amount}>{proposal.amount_display}</span>
                    <span className="av-small av-muted">{proposal.delivery_days} days</span>
                    {proposal.shortlisted_at ? (
                      <Badge tone="brand" size="sm">
                        Shortlisted
                      </Badge>
                    ) : null}
                  </div>
                </div>

                {proposal.match_score !== undefined ? (
                  <div className={styles.match}>
                    <MatchExplainer score={proposal.match_score} highlights={proposal.match_highlights} />
                  </div>
                ) : null}

                {proposal.preview ? (
                  <p className={`${styles.excerpt} av-clamp-3`}>{proposal.preview}</p>
                ) : null}

                {proposal.developer.skills?.length ? (
                  <div className={styles.tags}>
                    {proposal.developer.skills.map((skill) => (
                      <Tag key={skill}>{skill}</Tag>
                    ))}
                  </div>
                ) : null}

                {proposal.top_evidence ? (
                  <div className={styles.evidence}>
                    <Badge
                      tone={proposal.top_evidence.kind === 'averix_verified' ? 'verified' : 'neutral'}
                      size="sm"
                      icon={
                        proposal.top_evidence.kind === 'averix_verified' ? (
                          <IconShield size={12} />
                        ) : undefined
                      }
                    >
                      {proposal.top_evidence.kind === 'averix_verified'
                        ? 'AVERIX verified work'
                        : 'From their portfolio'}
                    </Badge>
                    <p className="av-small av-strong">{proposal.top_evidence.title}</p>
                    {proposal.top_evidence.technologies?.length ? (
                      <p className="av-xs av-faint">
                        {proposal.top_evidence.technologies.join(' · ')}
                      </p>
                    ) : null}
                  </div>
                ) : null}

                <footer className={styles.footer}>
                  <span className="av-small av-faint">Sent {timeAgo(proposal.created_at)}</span>
                  <div className="av-row">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={async () => {
                        await post(`/proposals/${proposal.id}/shortlist`, {
                          shortlisted: !proposal.shortlisted_at,
                        });
                        void load(sort);
                      }}
                    >
                      {proposal.shortlisted_at ? 'Remove from shortlist' : 'Shortlist'}
                    </Button>
                    <Button size="sm" onClick={() => setHiring(proposal)}>
                      Hire
                    </Button>
                  </div>
                </footer>
              </Card>
            ))}
          </div>
        )}
      </div>

      <HireSheet
        proposal={hiring}
        project={project}
        onClose={() => setHiring(null)}
        onHired={(contractId) => {
          setHiring(null);
          window.location.href = `/contracts/${contractId}`;
        }}
      />
    </>
  );
}

function HireSheet({
  proposal,
  project,
  onClose,
  onHired,
}: {
  proposal: ProposalCard | null;
  project: Project | null;
  onClose: () => void;
  onHired: (contractId: string) => void;
}) {
  const [visibility, setVisibility] = useState('range');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  if (!proposal) return null;

  const fee = Math.round(proposal.amount_minor * 0.1);

  return (
    <Sheet
      open={Boolean(proposal)}
      onClose={onClose}
      title={`Hire ${proposal.developer.full_name}`}
      description={project?.title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={busy}
            onClick={async () => {
              setBusy(true);
              setMessage('');
              try {
                const contract = await post<{ id: string }>('/contracts', {
                  proposal_id: proposal.id,
                  price_visibility: visibility,
                });
                onHired(contract.id);
              } catch (error) {
                setMessage(
                  error instanceof ApiFailure
                    ? error.message
                    : "We couldn't create the contract. Please try again.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            Create contract
          </Button>
        </>
      }
    >
      <div className="av-stack">
        {message ? (
          <p className={styles.alert} role="alert">
            {message}
          </p>
        ) : null}

        <ul className={styles.terms}>
          <li>
            <span className="av-muted">Agreed price</span>
            <strong>{proposal.amount_display}</strong>
          </li>
          <li>
            <span className="av-muted">Platform fee (from the developer)</span>
            <strong>{money(fee, proposal.currency)}</strong>
          </li>
          <li>
            <span className="av-muted">Delivery</span>
            <strong>{proposal.delivery_days} days</strong>
          </li>
        </ul>

        <div className="av-stack-sm">
          <p className="av-small av-strong">When this contract is finished, show its value as</p>
          <div className={styles.visibility}>
            {[
              { key: 'public', label: 'Exact amount' },
              { key: 'range', label: 'A range' },
              { key: 'hidden', label: 'Nothing' },
              { key: 'private', label: '“Private contract”' },
            ].map((option) => (
              <button
                key={option.key}
                type="button"
                className={[styles.option, visibility === option.key ? styles.optionActive : ''].join(' ')}
                onClick={() => setVisibility(option.key)}
                aria-pressed={visibility === option.key}
              >
                {visibility === option.key ? <IconCheck size={15} /> : null}
                {option.label}
              </button>
            ))}
          </div>
          <p className="av-small av-faint">
            This controls what appears on the developer&rsquo;s public profile. Their earnings and
            balance are never public whatever you choose.
          </p>
        </div>

        <p className={styles.note}>
          <IconShield size={15} />
          Accepting closes the other proposals on this project, with a reason sent to each
          developer. Milestones are funded one at a time — nothing is charged now.
        </p>
      </div>
    </Sheet>
  );
}
