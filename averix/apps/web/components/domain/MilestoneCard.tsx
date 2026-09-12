'use client';

import { useState } from 'react';
import styles from './MilestoneCard.module.css';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { IconCheck, IconChevronDown, IconExternal, IconPaperclip } from '@/components/ui/Icon';
import { money, shortDate, timeAgo } from '@/lib/format';
import type { Milestone } from '@/lib/types';

type ActionKind = 'start' | 'submit' | 'approve' | 'revision' | 'dispute';

/**
 * One milestone, with only the actions this person can actually take.
 *
 * The rules come from the API's `can` block and the milestone's own state, so
 * a button that would be refused is never drawn — a developer never sees an
 * Approve button, and neither side sees a Release one, because releasing is
 * the payment provider's word.
 */
export function MilestoneCard({
  milestone,
  role,
  can,
  onFund,
  onAction,
}: {
  milestone: Milestone;
  role: string;
  can: Record<string, boolean>;
  onFund: () => void;
  onAction: (kind: ActionKind) => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<ActionKind | null>(null);

  async function run(kind: ActionKind) {
    setBusy(kind);
    try {
      await onAction(kind);
    } finally {
      setBusy(null);
    }
  }

  const isClient = role === 'client';
  const isDeveloper = role === 'developer';

  const actions: { kind: ActionKind; label: string; variant?: 'primary' | 'secondary' | 'danger' }[] = [];
  if (milestone.status === 'funded' && isDeveloper) actions.push({ kind: 'start', label: 'Start work' });
  if ((milestone.status === 'in_progress' || milestone.status === 'revision_requested') && isDeveloper) {
    actions.push({ kind: 'submit', label: 'Submit work' });
  }
  if (milestone.status === 'submitted' && isClient) {
    actions.push({ kind: 'approve', label: 'Approve' });
    if (milestone.revision_count < milestone.revision_limit) {
      actions.push({ kind: 'revision', label: 'Request changes', variant: 'secondary' });
    }
  }
  if (
    ['funded', 'in_progress', 'submitted', 'revision_requested'].includes(milestone.status) &&
    (isClient || isDeveloper)
  ) {
    actions.push({ kind: 'dispute', label: 'Open dispute', variant: 'danger' });
  }

  return (
    <article className={[styles.card, styles[tone(milestone.status)]].join(' ')}>
      <header className={styles.header}>
        <div className={styles.headerText}>
          <p className={styles.position}>Milestone {milestone.position}</p>
          <h3 className={styles.title}>{milestone.title}</h3>
        </div>
        <div className={styles.headerRight}>
          {milestone.amount_minor !== undefined ? (
            <span className={styles.amount}>{money(milestone.amount_minor, milestone.currency)}</span>
          ) : null}
          <Badge tone={badgeTone(milestone.status)} size="sm">
            {label(milestone.status)}
          </Badge>
        </div>
      </header>

      {milestone.detail ? <p className={styles.detail}>{milestone.detail}</p> : null}

      {milestone.status === 'submitted' && milestone.submission_note ? (
        <blockquote className={styles.note}>
          <span className={styles.noteLabel}>Submitted {timeAgo(milestone.submitted_at)}</span>
          {milestone.submission_note}
        </blockquote>
      ) : null}

      {milestone.status === 'revision_requested' && milestone.revision_note ? (
        <blockquote className={[styles.note, styles.noteWarning].join(' ')}>
          <span className={styles.noteLabel}>
            Revision {milestone.revision_count} of {milestone.revision_limit}
          </span>
          {milestone.revision_note}
        </blockquote>
      ) : null}

      {milestone.deliverables?.length ? (
        <ul className={styles.deliverables}>
          {milestone.deliverables.map((deliverable) => (
            <li key={deliverable.id}>
              {deliverable.kind === 'file' ? <IconPaperclip size={15} /> : <IconExternal size={15} />}
              {deliverable.url ? (
                <a href={deliverable.url} target="_blank" rel="noopener noreferrer nofollow">
                  {deliverable.title}
                  <span className="av-faint"> · {deliverable.host || hostOf(deliverable.url)}</span>
                </a>
              ) : deliverable.file_url ? (
                <a href={deliverable.file_url} target="_blank" rel="noopener noreferrer">
                  {deliverable.title}
                  <span className="av-faint"> · {deliverable.file_name}</span>
                </a>
              ) : (
                <span>{deliverable.title}</span>
              )}
              {deliverable.accepted_at ? <IconCheck size={14} className={styles.accepted} /> : null}
            </li>
          ))}
        </ul>
      ) : null}

      <footer className={styles.footer}>
        <div className={styles.meta}>
          {milestone.due_on ? <span>Due {shortDate(milestone.due_on)}</span> : null}
          {milestone.events?.length ? (
            <button type="button" className={styles.historyToggle} onClick={() => setOpen(!open)}>
              History
              <IconChevronDown size={13} className={open ? styles.flip : undefined} />
            </button>
          ) : null}
        </div>

        <div className={styles.actions}>
          {milestone.status === 'draft' && isClient ? (
            <Button size="sm" onClick={onFund}>
              Fund milestone
            </Button>
          ) : null}
          {milestone.status === 'draft' && isDeveloper ? (
            <span className="av-small av-faint">Waiting for the client to fund this</span>
          ) : null}
          {actions.map((item) => (
            <Button
              key={item.kind}
              size="sm"
              variant={item.variant ?? 'primary'}
              loading={busy === item.kind}
              onClick={() => void run(item.kind)}
            >
              {item.label}
            </Button>
          ))}
        </div>
      </footer>

      {open && milestone.events?.length ? (
        <ol className={styles.history}>
          {milestone.events.map((event) => (
            <li key={event.id}>
              <span className={styles.historyDot} aria-hidden="true" />
              <div>
                <p className="av-small">
                  <strong>{label(event.to_status)}</strong>
                  {event.actor ? <span className="av-muted"> by {event.actor.full_name}</span> : null}
                </p>
                <p className="av-xs av-faint">{timeAgo(event.created_at)}</p>
                {event.note ? <p className="av-small av-muted">{event.note}</p> : null}
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </article>
  );
}

/** The host of a link, for the cases where the record predates storing it. */
function hostOf(url: string) {
  try {
    return new URL(url).host;
  } catch {
    return '';
  }
}

function tone(status: string) {
  if (status === 'submitted') return 'attention';
  if (status === 'approved' || status === 'released') return 'done';
  if (status === 'disputed') return 'trouble';
  return 'plain';
}

function badgeTone(status: string) {
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

function label(status: string) {
  switch (status) {
    case 'draft':
      return 'Not funded';
    case 'funded':
      return 'Funded';
    case 'in_progress':
      return 'In progress';
    case 'submitted':
      return 'Submitted';
    case 'revision_requested':
      return 'Changes requested';
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
