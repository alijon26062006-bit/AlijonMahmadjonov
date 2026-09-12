'use client';

import { use, useEffect, useState } from 'react';
import styles from './profile.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Avatar } from '@/components/ui/Avatar';
import { Badge, Tag } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { PortfolioGrid } from '@/components/domain/PortfolioGrid';
import { PreviewBrowser } from '@/components/domain/PreviewBrowser';
import {
  IconAlert,
  IconCheck,
  IconClock,
  IconGitHub,
  IconShield,
  IconStarFilled,
} from '@/components/ui/Icon';
import { get } from '@/lib/api';
import { avatarURL } from '@/lib/photo';
import { money, plural, shortDate } from '@/lib/format';
import type { PortfolioCard, PublicProfile } from '@/lib/types';

export default function ProfilePage({ params }: { params: Promise<{ username: string }> }) {
  const { username } = use(params);
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioCard[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [previewing, setPreviewing] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    get<PublicProfile>(`/developers/${username}`)
      .then((data) => !cancelled && setProfile(data))
      .catch(() => !cancelled && setFailed(true));
    get<PortfolioCard[]>(`/developers/${username}/portfolio`)
      .then((data) => !cancelled && setPortfolio(data))
      .catch(() => !cancelled && setPortfolio([]));
    return () => {
      cancelled = true;
    };
  }, [username]);

  if (failed) {
    return (
      <>
        <TopBar back />
        <div className="av-page">
          <EmptyState
            tone="error"
            icon={<IconAlert size={20} />}
            title="We couldn't find that profile"
            description="The address may be wrong, or the developer may have made their profile private."
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
                member since {shortDate(profile.member_since)}
              </p>
            </div>
          </div>

          <div className={styles.badges}>
            {profile.badges.map((badge) => (
              <Badge
                key={badge.kind}
                tone={badgeTone(badge.kind)}
                size="sm"
                icon={badgeIcon(badge.kind)}
              >
                {badge.label}
              </Badge>
            ))}
          </div>

          <div className={styles.stats}>
            <Stat
              label="Rating"
              value={reputation.rating_avg ? reputation.rating_avg.toFixed(1) : '—'}
              note={reputation.rating_count ? plural(reputation.rating_count, 'review') : 'No reviews yet'}
            />
            <Stat
              label="Completed"
              value={String(reputation.projects_completed)}
              note="AVERIX contracts"
            />
            <Stat
              label="Success"
              value={reputation.success_rate ? `${Math.round(reputation.success_rate)}%` : '—'}
              note="finished as agreed"
            />
            <Stat
              label="Responds"
              value={responseHours ? `${responseHours}h` : '—'}
              note="median first reply"
            />
          </div>

          <div className={styles.availability}>
            <span className={styles.availabilityDot} data-state={profile.availability} aria-hidden="true" />
            {availabilityLabel(profile.availability, profile.hours_per_week)}
            {profile.hourly_rate_minor ? (
              <span className={styles.rate}>
                {money(profile.hourly_rate_minor, profile.rate_currency)}/hour
              </span>
            ) : null}
          </div>

          {!profile.is_owner ? (
            <div className={styles.actions}>
              <Button block>Invite to a project</Button>
              <Button variant="secondary" block>
                Save
              </Button>
            </div>
          ) : null}
        </Card>

        {profile.bio ? (
          <Card>
            <h2 className={styles.sectionTitle}>About</h2>
            <p className={styles.bio}>{profile.bio}</p>
          </Card>
        ) : null}

        <Card>
          <h2 className={styles.sectionTitle}>Technologies</h2>
          <div className={styles.skills}>
            {profile.skills.map((skill) => (
              <span
                key={skill.slug}
                className={[styles.skill, skill.is_primary ? styles.skillPrimary : ''].join(' ')}
              >
                {skill.name}
                {skill.evidence?.length ? (
                  <span className={styles.evidence} title={`Corroborated by ${skill.evidence.join(', ')}`}>
                    <IconCheck size={12} />
                  </span>
                ) : null}
              </span>
            ))}
          </div>
          <p className={styles.skillsNote}>
            A tick means the technology was corroborated by connected GitHub repositories or by
            completed AVERIX work — not self-declared alone.
          </p>
        </Card>

        {profile.github ? (
          <Card>
            <div className="av-row-between">
              <h2 className={styles.sectionTitle}>
                <IconGitHub size={17} /> GitHub
              </h2>
              <a
                className={styles.githubLink}
                href={profile.github.profile_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                @{profile.github.login}
              </a>
            </div>

            {profile.github.language_share?.length ? (
              <>
                <p className={styles.codeUsageLabel}>Code usage across public repositories</p>
                <div className={styles.shares}>
                  {profile.github.language_share.slice(0, 5).map((language) => (
                    <div key={language.name} className={styles.share}>
                      <div className={styles.shareHead}>
                        <span>{language.name}</span>
                        <span className="av-numeric av-muted av-small">
                          {Math.round(language.share * 100)}%
                        </span>
                      </div>
                      <div className={styles.shareTrack} aria-hidden="true">
                        <span
                          className={styles.shareFill}
                          style={{ width: `${Math.round(language.share * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <p className={styles.codeUsageNote}>
                  This is how much code is written in each language — a measure of what this
                  developer works on, not a rating of how well they know it.
                </p>
              </>
            ) : null}

            {profile.github.ai_summary ? (
              <div className={styles.aiSummary}>
                <span className={styles.aiLabel}>AI-generated summary</span>
                <p>{profile.github.ai_summary}</p>
              </div>
            ) : null}
          </Card>
        ) : null}

        <section className="av-stack-sm">
          <h2 className={styles.sectionTitle}>Portfolio</h2>
          {portfolio === null ? (
            <Skeleton height={180} radius="var(--av-radius-xl)" />
          ) : portfolio.length === 0 ? (
            <EmptyState
              icon={<IconClock size={20} />}
              title="No portfolio projects yet"
              description="Work this developer has published will appear here, with AVERIX-verified contracts shown separately from self-declared projects."
            />
          ) : (
            <PortfolioGrid
              items={portfolio}
              onPreview={(slug) => setPreviewing(slug)}
              username={profile.username}
            />
          )}
        </section>
      </div>

      {previewing ? (
        <PreviewBrowser
          username={profile.username}
          slug={previewing}
          onClose={() => setPreviewing(null)}
        />
      ) : null}
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

function availabilityLabel(availability: string, hours?: number) {
  switch (availability) {
    case 'available':
      return hours ? `Available now · about ${hours} hours a week` : 'Available now';
    case 'open':
      return 'Open to the right project';
    case 'busy':
      return 'Busy — booked for now';
    default:
      return 'Not taking work';
  }
}
