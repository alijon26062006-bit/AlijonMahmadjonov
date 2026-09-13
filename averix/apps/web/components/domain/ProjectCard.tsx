import Link from 'next/link';
import styles from './ProjectCard.module.css';
import { Tag, Badge } from '@/components/ui/Badge';
import { MatchExplainer } from './MatchExplainer';
import { IconShield, IconClock } from '@/components/ui/Icon';
import { plural, timeAgo } from '@/lib/format';
import type { FeedCard } from '@/lib/types';

/**
 * One project in the feed.
 *
 * What a developer decides with, in the order they decide it: what the work
 * is, whether it matches them, what it pays, and how much competition there
 * is. Everything else waits for the detail page.
 */
export function ProjectCard({ card }: { card: FeedCard }) {
  return (
    <article className={styles.card}>
      <Link href={`/projects/${card.slug}`} className={styles.body}>
        <header className={styles.header}>
          <div className={styles.headerText}>
            <h3 className={styles.title}>{card.title}</h3>
            <p className={styles.meta}>
              {card.category.name}
              {card.published_at ? <> · {timeAgo(card.published_at)}</> : null}
            </p>
          </div>
          {card.has_proposed ? <Badge tone="brand" size="sm">Вы откликнулись</Badge> : null}
        </header>

        {card.excerpt ? <p className={`${styles.excerpt} av-clamp-2`}>{card.excerpt}</p> : null}

        {card.skills.length > 0 ? (
          <div className={styles.tags}>
            {card.skills.map((skill) => (
              <Tag key={skill.slug}>{skill.name}</Tag>
            ))}
          </div>
        ) : null}
      </Link>

      <footer className={styles.footer}>
        <div className={styles.facts}>
          <span className={styles.budget}>{card.budget.display}</span>
          <span className={styles.dot} aria-hidden="true" />
          <span className={styles.proposals}>
            <IconClock size={13} />
            {plural(card.proposals_count, 'отклик', 'отклика', 'откликов')}
          </span>
          {card.client_verified ? (
            <>
              <span className={styles.dot} aria-hidden="true" />
              <span className={styles.verified}>
                <IconShield size={13} />
                Проверенный заказчик
              </span>
            </>
          ) : null}
        </div>

        {card.match_score !== undefined ? (
          <MatchExplainer score={card.match_score} highlights={card.match_highlights} />
        ) : null}
      </footer>
    </article>
  );
}
