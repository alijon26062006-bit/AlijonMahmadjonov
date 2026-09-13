'use client';

import Link from 'next/link';
import { useState } from 'react';
import styles from './FreelancerCard.module.css';
import { Avatar } from '@/components/ui/Avatar';
import { Badge, Tag } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { IconCheck, IconShield, IconStarFilled } from '@/components/ui/Icon';
import { del, post } from '@/lib/api';
import { plural } from '@/lib/format';
import { AVAILABILITY } from '@/lib/labels';
import { useSession } from '@/lib/session';
import type { FreelancerCard as FreelancerCardType } from '@/lib/types';

/** Исполнитель в каталоге: кто, что умеет, сколько сделал, свободен ли. */
export function FreelancerCard({ card }: { card: FreelancerCardType }) {
  const { session } = useSession();
  const [saved, setSaved] = useState(Boolean(card.is_saved));
  const [busy, setBusy] = useState(false);
  const canSave = session?.active_role === 'client';

  async function toggleSave() {
    setBusy(true);
    try {
      if (saved) await del(`/freelancers/${card.username}/save`);
      else await post(`/freelancers/${card.username}/save`);
      setSaved(!saved);
    } catch {
      // Кнопка остаётся в прежнем состоянии — лучше, чем показать ложь.
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className={styles.card}>
      <Link href={`/developers/${card.username}`} className={styles.main}>
        <Avatar src={card.photo_url} name={card.full_name} size={64} verified={card.identity_verified} />
        <div className={styles.text}>
          <div className={styles.nameRow}>
            <h3 className={styles.name}>{card.full_name}</h3>
            {card.is_featured ? (
              <Badge tone="brand" size="sm">
                Рекомендуем
              </Badge>
            ) : null}
          </div>
          <p className={styles.title}>{card.professional_title || card.specialisation?.name}</p>
          <div className={styles.facts}>
            {card.rating_avg ? (
              <span className={styles.rating}>
                <IconStarFilled size={12} />
                {card.rating_avg.toFixed(1)}
                <span className="av-faint"> ({card.rating_count})</span>
              </span>
            ) : null}
            {card.projects_completed ? (
              <span>{plural(card.projects_completed, 'заказ', 'заказа', 'заказов')}</span>
            ) : (
              <span className="av-faint">Новичок</span>
            )}
            {card.rate_display ? <span>{card.rate_display}/ч</span> : null}
            {card.location ? <span>{card.location}</span> : null}
          </div>
          {card.skills?.length ? (
            <div className={styles.tags}>
              {card.skills.slice(0, 6).map((skill) => (
                <Tag key={skill.slug}>
                  {skill.name}
                  {skill.verified ? <IconCheck size={11} /> : null}
                </Tag>
              ))}
            </div>
          ) : null}
        </div>
      </Link>
      <footer className={styles.footer}>
        <span className={styles.availability} data-state={card.availability}>
          <span className={styles.dot} aria-hidden="true" />
          {AVAILABILITY[card.availability] ?? card.availability}
          {card.identity_verified ? (
            <span className={styles.verified}>
              <IconShield size={12} /> Личность подтверждена
            </span>
          ) : null}
        </span>
        {canSave ? (
          <Button size="sm" variant={saved ? 'primary' : 'secondary'} loading={busy} onClick={() => void toggleSave()}>
            {saved ? 'В избранном' : 'В избранное'}
          </Button>
        ) : null}
      </footer>
    </article>
  );
}
