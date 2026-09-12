'use client';

import { use, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import styles from './workspace.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Avatar } from '@/components/ui/Avatar';
import { Badge, StatusDot } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { Textarea } from '@/components/ui/Field';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { MilestoneCard } from '@/components/domain/MilestoneCard';
import { FundSheet } from '@/components/domain/FundSheet';
import { IconAlert, IconMessage, IconShield } from '@/components/ui/Icon';
import { ApiFailure, get, post } from '@/lib/api';
import { money, shortDate } from '@/lib/format';
import type { Contract, Milestone } from '@/lib/types';

type Action = { milestone: Milestone; kind: 'submit' | 'revision' | 'dispute' };

export default function WorkspacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [contract, setContract] = useState<Contract | null>(null);
  const [failed, setFailed] = useState(false);
  const [funding, setFunding] = useState<Milestone | null>(null);
  const [action, setAction] = useState<Action | null>(null);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      setContract(await get<Contract>(`/contracts/${id}`));
    } catch {
      setFailed(true);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (failed) {
    return (
      <>
        <TopBar back="/contracts" title="Contract" />
        <div className="av-page">
          <EmptyState
            tone="error"
            icon={<IconAlert size={20} />}
            title="We couldn't open this contract"
            description="Either it doesn't exist, or it isn't yours to see."
          />
        </div>
      </>
    );
  }

  if (!contract) {
    return (
      <>
        <TopBar back="/contracts" title="Contract" />
        <div className="av-page av-stack">
          <Skeleton height={100} />
          <Skeleton height={64} />
          <Skeleton height={140} />
        </div>
      </>
    );
  }

  const other = contract.my_role === 'client' ? contract.developer : contract.client;

  return (
    <>
      <TopBar back="/contracts" title={contract.reference} />
      <div className="av-page av-stack">
        <Card>
          <div className="av-row-between">
            <div className="av-grow">
              <h1 className={styles.title}>{contract.title}</h1>
              <p className="av-small av-muted">
                <Link href={`/projects/${contract.project.slug}`}>{contract.project.title}</Link>
                {contract.due_on ? ` · due ${shortDate(contract.due_on)}` : ''}
              </p>
            </div>
            <Badge tone={statusTone(contract.status)}>{statusLabel(contract.status)}</Badge>
          </div>

          <div className={styles.progress}>
            <div className={styles.track} aria-hidden="true">
              <span className={styles.fill} style={{ width: `${contract.progress_percent}%` }} />
            </div>
            <span className="av-small av-numeric av-muted">{contract.progress_percent}% approved</span>
          </div>

          {contract.amount_minor !== undefined ? (
            <div className={styles.money}>
              <div>
                <span className={styles.moneyLabel}>Contract</span>
                <span className={styles.moneyValue}>
                  {money(contract.amount_minor, contract.currency)}
                </span>
              </div>
              <div>
                <span className={styles.moneyLabel}>
                  {contract.my_role === 'developer' ? 'You receive' : 'Platform fee'}
                </span>
                <span className={styles.moneyValue}>
                  {money(
                    contract.my_role === 'developer' ? contract.payout_minor : contract.fee_minor,
                    contract.currency,
                  )}
                </span>
              </div>
              <div>
                <span className={styles.moneyLabel}>Released</span>
                <span className={styles.moneyValue}>
                  {money(contract.released_minor ?? 0, contract.currency)}
                </span>
              </div>
            </div>
          ) : (
            <p className={styles.observerNote}>
              <IconShield size={15} />
              You are on this workspace as an observer. What the work cost is between the client and
              the developer.
            </p>
          )}
        </Card>

        <div className={styles.people}>
          <div className={styles.person}>
            <Avatar src={other.photo_url} name={other.full_name} size={40} />
            <div className="av-grow">
              <p className="av-strong">{other.full_name}</p>
              <p className="av-small av-muted">
                {contract.my_role === 'client' ? 'Developer' : 'Client'}
                {other.title ? ` · ${other.title}` : ''}
              </p>
            </div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            icon={<IconMessage size={16} />}
            className={styles.messageButton}
            aria-label="Open the conversation"
            onClick={() => (window.location.href = `/messages?contract=${contract.id}`)}
          >
            <span className={styles.messageLabel}>Message</span>
          </Button>
        </div>

        <section className="av-stack-sm">
          <h2 className={styles.sectionTitle}>Milestones</h2>
          {contract.milestones.map((milestone) => (
            <MilestoneCard
              key={milestone.id}
              milestone={milestone}
              role={contract.my_role}
              can={contract.can}
              onFund={() => setFunding(milestone)}
              onAction={async (kind) => {
                if (kind === 'start') {
                  await post(`/milestones/${milestone.id}/start`);
                  void load();
                  return;
                }
                if (kind === 'approve') {
                  await post(`/milestones/${milestone.id}/approve`);
                  void load();
                  return;
                }
                setAction({ milestone, kind });
              }}
            />
          ))}
        </section>
      </div>

      <FundSheet
        milestone={funding}
        onClose={() => setFunding(null)}
        onFunded={() => {
          setFunding(null);
          void load();
        }}
      />

      <NoteSheet
        action={action}
        onClose={() => setAction(null)}
        onDone={() => {
          setAction(null);
          void load();
        }}
      />
    </>
  );
}

const NOTE_COPY = {
  submit: {
    title: 'Submit this milestone',
    label: 'What are you handing over?',
    placeholder: 'What is finished, where to find it, and anything the client should check first.',
    hint: 'The client reviews this. Be specific about what is done.',
    button: 'Submit for review',
    min: 1,
  },
  revision: {
    title: 'Request a revision',
    label: 'What needs changing?',
    placeholder: 'Be concrete: which part, what is wrong, what you expected instead.',
    hint: 'At least a sentence. A revision without a reason wastes everyone’s time.',
    button: 'Send back',
    min: 20,
  },
  dispute: {
    title: 'Open a dispute',
    label: 'What has gone wrong?',
    placeholder: 'Describe the problem and what you have already tried to resolve between you.',
    hint: 'A person at AVERIX reads this. Both sides see what you write.',
    button: 'Open dispute',
    min: 30,
  },
} as const;

function NoteSheet({
  action,
  onClose,
  onDone,
}: {
  action: Action | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (!action) return null;
  const copy = NOTE_COPY[action.kind];
  const path =
    action.kind === 'submit' ? 'submit' : action.kind === 'revision' ? 'request-revision' : 'dispute';

  return (
    <Sheet
      open
      onClose={onClose}
      title={copy.title}
      description={action.milestone.title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={busy}
            disabled={note.trim().length < copy.min}
            onClick={async () => {
              setBusy(true);
              setError('');
              try {
                await post(`/milestones/${action.milestone.id}/${path}`, { note: note.trim() });
                setNote('');
                onDone();
              } catch (failure) {
                setError(
                  failure instanceof ApiFailure
                    ? failure.fields.note || failure.message
                    : "That didn't go through. Please try again.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            {copy.button}
          </Button>
        </>
      }
    >
      <Textarea
        label={copy.label}
        placeholder={copy.placeholder}
        hint={copy.hint}
        error={error || undefined}
        rows={6}
        max={4000}
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
    </Sheet>
  );
}

function statusTone(status: string) {
  switch (status) {
    case 'completed':
      return 'success' as const;
    case 'active':
      return 'brand' as const;
    case 'disputed':
      return 'danger' as const;
    case 'cancelled':
      return 'neutral' as const;
    default:
      return 'warning' as const;
  }
}

function statusLabel(status: string) {
  switch (status) {
    case 'pending_funding':
      return 'Awaiting funding';
    case 'active':
      return 'In progress';
    case 'completed':
      return 'Completed';
    case 'cancelled':
      return 'Cancelled';
    case 'disputed':
      return 'Disputed';
    default:
      return status.replace('_', ' ');
  }
}

export { StatusDot };
